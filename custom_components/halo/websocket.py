"""Websocket API so the HALO panel can manage mappings without the HA dialog.

Commands (admin only):
- halo/config/get {area} -> full per-mood config for one area.
- halo/config/set_mood {area, mood, config} -> validate, persist to entry
  options (the entry auto-reloads via its update listener).
- halo/config/delete_mood {area, mood}
- halo/config/suggest_tracked {area, actions} -> union of scene entities

Validation lives in pure helpers so it stays unit-testable; entity
*existence* is reported as warnings (not errors) so scenes/scripts can be
created after the mapping.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

try:
    from homeassistant.components import websocket_api
except ImportError:  # pragma: no cover - standalone unit tests
    websocket_api = None  # type: ignore[assignment]

try:
    from .const import (
        CONF_ACTION,
        CONF_DEBOUNCE,
        CONF_DEFAULT_PRESET,
        CONF_IGNORE_ATTRS,
        CONF_IGNORE_UNAVAILABLE,
        CONF_MOODS,
        CONF_POST_ACTION,
        CONF_PRESETS,
        CONF_SETTLE,
        CONF_TOLERANCE,
        CONF_TRACKED_ENTITIES,
        CONF_TRANSITION,
        CONF_VERIFY,
        DOMAIN,
        normalize_mood_cfg,
        normalize_verify,
        pick_default_preset,
    )
except ImportError:  # loaded standalone in unit tests
    from const import (  # type: ignore[no-redef]
        CONF_ACTION,
        CONF_DEBOUNCE,
        CONF_DEFAULT_PRESET,
        CONF_IGNORE_ATTRS,
        CONF_IGNORE_UNAVAILABLE,
        CONF_MOODS,
        CONF_POST_ACTION,
        CONF_PRESETS,
        CONF_SETTLE,
        CONF_TOLERANCE,
        CONF_TRACKED_ENTITIES,
        CONF_TRANSITION,
        CONF_VERIFY,
        DOMAIN,
        normalize_mood_cfg,
        normalize_verify,
        pick_default_preset,
    )

_LOGGER = logging.getLogger(__name__)

_MOOD_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\- ]{0,63}$")
_ACTION_RE = re.compile(r"^(scene|script)\.[A-Za-z0-9_]+$")
_ENTITY_RE = re.compile(r"^[a-z_]+\.[A-Za-z0-9_]+$")


def _num(value: Any, name: str, *, minimum: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{name} must be a number") from err
    if number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return number


def _csv(value: Any, name: str) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        items = [x.strip() for x in value.split(",")]
    elif isinstance(value, (list, tuple)):
        items = [str(x).strip() for x in value]
    else:
        raise ValueError(f"{name} must be a list or comma-separated string")
    items = [x for x in items if x]
    if name == "tracked_entities":
        bad = [x for x in items if not _ENTITY_RE.match(x)]
        if bad:
            raise ValueError(f"tracked_entities has bad entity ids: {bad}")
    return items


def validate_mood_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an editor payload, return normalized mood config.

    Raises ValueError with a human message the panel can display.
    Shape mirrors the options-flow storage so both editors interoperate.
    Every mood has >= 1 preset plus one designated default preset.
    """
    if not isinstance(payload, dict):
        raise ValueError("config must be an object")
    presets_in = payload.get("presets") or {}
    if not isinstance(presets_in, dict):
        raise ValueError("presets must be an object")
    presets: dict[str, dict[str, Any]] = {}
    for raw_name, raw_preset in presets_in.items():
        name = str(raw_name or "").strip()
        if isinstance(raw_preset, dict):
            action = str(raw_preset.get("action") or "").strip()
            verify_raw = str(raw_preset.get("verify") or "auto").strip()
        else:
            action = str(raw_preset or "").strip()
            verify_raw = "auto"
        if not name and not action:
            continue  # blank editor row: ignore, don't error
        if not name:
            raise ValueError(f"preset action '{action}' is missing its name")
        if len(name) > 64:
            raise ValueError(f"preset name too long: {name}")
        if not action:
            raise ValueError(f"preset '{name}' needs a scene or script")
        if not _ACTION_RE.match(action):
            raise ValueError(
                f"preset '{name}': '{action}' must look like scene.x or script.y"
            )
        verify = normalize_verify(verify_raw)
        if verify["mode"] == "auto" and verify_raw not in ("", "auto"):
            raise ValueError(
                f"preset '{name}': verify must be auto, snapshot, off, or a scene"
            )
        presets[name] = {CONF_ACTION: action, CONF_VERIFY: verify}
    if not presets:
        raise ValueError("map at least one preset")

    default = str(payload.get("default_preset") or "").strip()
    if not default:
        default = pick_default_preset(presets)
    if default not in presets:
        raise ValueError(
            f"default preset '{default}' must be one of: {', '.join(sorted(presets))}"
        )

    post_action = str(payload.get("post_action") or "").strip()
    if post_action and not re.match(r"^script\.[A-Za-z0-9_]+$", post_action):
        raise ValueError("post script must look like script.x")

    return {
        CONF_PRESETS: presets,
        CONF_DEFAULT_PRESET: default,
        CONF_POST_ACTION: post_action,
        CONF_TRACKED_ENTITIES: _csv(
            payload.get("tracked_entities"), "tracked_entities"
        ),
        CONF_TRANSITION: _num(payload.get("transition", 2.0), "transition"),
        CONF_SETTLE: _num(payload.get("settle", 5.0), "settle"),
        CONF_DEBOUNCE: _num(payload.get("debounce", 2.0), "debounce"),
        CONF_TOLERANCE: _num(payload.get("tolerance", 1.0), "tolerance"),
        CONF_IGNORE_ATTRS: _csv(payload.get("ignore_attrs"), "ignore_attrs"),
        CONF_IGNORE_UNAVAILABLE: bool(payload.get("ignore_unavailable", True)),
    }


def validate_mood_name(mood: Any) -> str:
    mood = str(mood or "").strip()
    if not _MOOD_RE.match(mood):
        raise ValueError(
            "mood names use letters, numbers, spaces, _ and -, max 64 chars"
        )
    return mood


def serialize_area(area) -> dict[str, Any]:
    """Full editable config for one HaloArea (entry data + options merged)."""
    cfg: dict[str, Any] = dict(area.entry.data)
    cfg.update(area.entry.options or {})
    moods: dict[str, Any] = {}
    for mood, raw_mcfg in (cfg.get(CONF_MOODS) or {}).items():
        mcfg = normalize_mood_cfg(raw_mcfg)
        presets: dict[str, Any] = {}
        for pname, pcfg in ((mcfg.get(CONF_PRESETS) or {}).items()):
            pcfg = pcfg or {}
            verify = normalize_verify(pcfg.get(CONF_VERIFY))
            presets[pname] = {
                "action": pcfg.get(CONF_ACTION, ""),
                "verify": (
                    verify["scene"]
                    if verify["mode"] == "scene"
                    else verify["mode"]
                ),
            }
        moods[mood] = {
            "presets": presets,
            "default_preset": mcfg.get(CONF_DEFAULT_PRESET, "base"),
            "post_action": mcfg.get(CONF_POST_ACTION, ""),
            "tracked_entities": list(mcfg.get(CONF_TRACKED_ENTITIES, []) or []),
            "transition": mcfg.get(CONF_TRANSITION, 2.0),
            "settle": mcfg.get(CONF_SETTLE, 5.0),
            "debounce": mcfg.get(CONF_DEBOUNCE, 2.0),
            "tolerance": mcfg.get(CONF_TOLERANCE, 1.0),
            "ignore_attrs": list(mcfg.get(CONF_IGNORE_ATTRS, []) or []),
            "ignore_unavailable": bool(mcfg.get(CONF_IGNORE_UNAVAILABLE, True)),
        }
    return {
        "area": area.area_key,
        "area_name": area.area_name,
        "lock": area.lock_entity,
        "moods": moods,
    }


def _find_area(hass, area_key: str):
    for candidate in hass.data.get(DOMAIN, {}).values():
        if getattr(candidate, "area_key", None) == area_key:
            return candidate
    raise ValueError(f"unknown HALO area '{area_key}'")


def _missing_actions(hass, mood_cfg: dict[str, Any]) -> list[str]:
    actions = [
        (v or {}).get(CONF_ACTION, "")
        for v in (mood_cfg[CONF_PRESETS] or {}).values()
    ]
    return [a for a in actions if a and hass.states.get(a) is None]


def scene_entities_from_yaml(scenes_path: str, slug: str) -> list[str]:
    """Entity ids a scene.* action addresses, read from scenes.yaml.

    Same id-or-name matching as the setup-time importer. Returns [] when
    pyyaml/scenes.yaml is missing or the scene isn't found — the caller
    unions across actions, so partial knowledge is fine.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover
        return []
    try:
        with open(scenes_path, encoding="utf-8") as f:
            docs = yaml.safe_load(f)
    except (FileNotFoundError, OSError):
        return []
    if not isinstance(docs, list):
        return []
    for scene in docs:
        if not isinstance(scene, dict):
            continue
        sid = str(scene.get("id", ""))
        sname = str(scene.get("name", ""))
        if sid == slug or sname.lower().replace(" ", "_") == slug:
            entities = scene.get("entities") or {}
            return sorted(entities.keys()) if isinstance(entities, dict) else []
    return []


def suggest_tracked_entities(hass, actions: list[str]) -> list[str]:
    """Union of entities addressed by scene actions (scripts unresolvable).

    Used by the editor's Autofill: drafts what empty (auto-detect) would
    track, so users can tweak instead of typing from scratch.
    """
    try:
        scenes_path = hass.config.path("scenes.yaml")
    except Exception:  # noqa: BLE001
        return []
    found: set[str] = set()
    for action in actions or []:
        domain, _, slug = str(action).partition(".")
        if domain != "scene" or not slug:
            continue
        found.update(scene_entities_from_yaml(scenes_path, slug))
    return sorted(found)


def _persist_moods(hass, area, moods: dict[str, Any]) -> None:
    options = dict(area.entry.options or {})
    options[CONF_MOODS] = moods
    hass.config_entries.async_update_entry(area.entry, options=options)


def _handle_get(hass, connection, msg: dict[str, Any]) -> None:
    try:
        area = _find_area(hass, msg.get("area"))
    except ValueError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return
    connection.send_result(msg["id"], serialize_area(area))


def _handle_set_mood(hass, connection, msg: dict[str, Any]) -> None:
    try:
        area = _find_area(hass, msg.get("area"))
        mood = validate_mood_name(msg.get("mood"))
        mood_cfg = validate_mood_payload(msg.get("config") or {})
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    cfg: dict[str, Any] = dict(area.entry.data)
    cfg.update(area.entry.options or {})
    moods = dict(cfg.get(CONF_MOODS, {}) or {})
    moods[mood] = mood_cfg
    _persist_moods(hass, area, moods)
    connection.send_result(
        msg["id"],
        {"saved": mood, "missing_actions": _missing_actions(hass, mood_cfg)},
    )


def _handle_delete_mood(hass, connection, msg: dict[str, Any]) -> None:
    try:
        area = _find_area(hass, msg.get("area"))
        mood = validate_mood_name(msg.get("mood"))
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    cfg: dict[str, Any] = dict(area.entry.data)
    cfg.update(area.entry.options or {})
    moods = dict(cfg.get(CONF_MOODS, {}) or {})
    if mood not in moods:
        connection.send_error(msg["id"], "not_found", f"no such mood '{mood}'")
        return
    del moods[mood]
    _persist_moods(hass, area, moods)
    connection.send_result(msg["id"], {"deleted": mood})


def _handle_suggest(hass, connection, msg: dict[str, Any]) -> None:
    try:
        _find_area(hass, msg.get("area"))
    except ValueError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return
    actions = msg.get("actions") or []
    if not isinstance(actions, list):
        connection.send_error(msg["id"], "invalid_format", "actions must be a list")
        return
    # scenes.yaml read must not block the event loop, but HA also drops
    # coroutine results from handlers — so schedule the work and answer
    # from the task instead.
    msg_id = msg["id"]

    async def _run() -> None:
        try:
            entities = await hass.async_add_executor_job(
                suggest_tracked_entities, hass, actions
            )
        except Exception:  # noqa: BLE001
            entities = []
        try:
            connection.send_result(msg_id, {"entities": entities})
        except Exception:  # noqa: BLE001
            pass  # client went away; nothing to answer

    hass.async_create_task(_run())


def _require_admin(handler):
    # NOTE: HA invokes websocket handlers synchronously and drops the
    # return value, so handlers (and this wrapper) must stay sync and
    # answer via connection.send_result / send_error directly.
    def wrapper(hass, connection, msg):
        user = getattr(connection, "user", None)
        if user is None or not getattr(user, "is_admin", False):
            connection.send_error(msg["id"], "unauthorized", "admin required")
            return
        handler(hass, connection, msg)

    return wrapper


COMMANDS: list[tuple[dict[str, Any], Any]] = [
    (
        {"type": "halo/config/get", vol.Required("area"): str},
        _require_admin(_handle_get),
    ),
    (
        {
            "type": "halo/config/set_mood",
            vol.Required("area"): str,
            vol.Required("mood"): str,
            vol.Required("config"): dict,
        },
        _require_admin(_handle_set_mood),
    ),
    (
        {
            "type": "halo/config/delete_mood",
            vol.Required("area"): str,
            vol.Required("mood"): str,
        },
        _require_admin(_handle_delete_mood),
    ),
    (
        {
            "type": "halo/config/suggest_tracked",
            vol.Required("area"): str,
            vol.Required("actions"): list,
        },
        _require_admin(_handle_suggest),
    ),
]


def async_register(hass) -> None:
    """Register WS commands; safe to call even if websocket_api is missing."""
    if websocket_api is None:  # pragma: no cover
        _LOGGER.debug("HALO websocket_api unavailable, panel editing disabled")
        return
    for schema, handler in COMMANDS:
        websocket_api.async_register_command(hass, websocket_api.websocket_command(schema)(handler))
