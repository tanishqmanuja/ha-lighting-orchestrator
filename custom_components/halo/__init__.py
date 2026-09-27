"""HALO setup: per-area engine + listeners + panel + services."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import event as evt
from homeassistant.helpers.storage import Store

from .const import (
    CONF_ACTION,
    CONF_AREA_ID,
    CONF_AREA_NAME,
    CONF_DEBOUNCE,
    CONF_DEFAULT_PRESET,
    CONF_IGNORE_ATTRS,
    CONF_IGNORE_UNAVAILABLE,
    CONF_LOCK,
    CONF_MOODS,
    CONF_POST_ACTION,
    CONF_PRESETS,
    CONF_SETTLE,
    CONF_TOLERANCE,
    CONF_TRACKED_ENTITIES,
    CONF_TRANSITION,
    CONF_VERIFY,
    DEFAULT_DEBOUNCE,
    DEFAULT_SETTLE,
    DOMAIN,
    EVENT_POST_RAN,
    PLATFORMS,
    PRESET_NONE,
    STATUS_ACTIVE,
    STORAGE_KEY,
    STORAGE_VERSION,
    normalize_mood_cfg,
    normalize_verify,
)
from .engine import AreaEngine, MoodTuning

_LOGGER = logging.getLogger(__name__)


def _area_cfg(entry: ConfigEntry) -> dict[str, Any]:
    cfg: dict[str, Any] = dict(entry.data)
    cfg.update(entry.options or {})
    return cfg


def _build_targets(
    cfg: dict[str, Any],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, str], dict[str, str]]:
    """Build engine targets + per-mood default presets + post scripts.

    Legacy mood-level actions (the old "0 presets" model) are migrated to a
    single "base" preset via normalize_mood_cfg.
    """
    targets: dict[tuple[str, str], dict[str, Any]] = {}
    defaults: dict[str, str] = {}
    post_actions: dict[str, str] = {}
    for mood, raw_mcfg in (cfg.get(CONF_MOODS) or {}).items():
        mcfg = normalize_mood_cfg(raw_mcfg)
        presets = mcfg.get(CONF_PRESETS) or {}
        tuning = MoodTuning(
            transition=float(mcfg.get(CONF_TRANSITION, 2.0)),
            settle=float(mcfg.get(CONF_SETTLE, DEFAULT_SETTLE)),
            debounce=float(mcfg.get(CONF_DEBOUNCE, DEFAULT_DEBOUNCE)),
            tolerance=float(mcfg.get(CONF_TOLERANCE, 1.0)),
            ignore_attrs=tuple(mcfg.get(CONF_IGNORE_ATTRS, ())),
            ignore_unavailable=bool(
                mcfg.get(CONF_IGNORE_UNAVAILABLE, True)
            ),
        )
        tracked_default = list(mcfg.get(CONF_TRACKED_ENTITIES, []) or [])
        for preset, pcfg in presets.items():
            pcfg = pcfg or {}
            action = pcfg.get(CONF_ACTION)
            if not action:
                continue
            tracked = list(pcfg.get(CONF_TRACKED_ENTITIES, []) or tracked_default)
            targets[(mood, preset)] = {
                "action": action,
                "tracked": tracked,
                "tuning": tuning,
                "verify": normalize_verify(pcfg.get(CONF_VERIFY)),
            }
        if any((mood, p) in targets for p in presets):
            defaults[mood] = mcfg.get(CONF_DEFAULT_PRESET, "base")
        post = mcfg.get(CONF_POST_ACTION, "")
        if isinstance(post, str) and post.strip():
            post_actions[mood] = post.strip()
    return targets, defaults, post_actions


class HaloArea:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        cfg = _area_cfg(entry)
        self.area_key: str = cfg.get(CONF_AREA_ID) or entry.entry_id
        self.area_name: str = cfg.get(CONF_AREA_NAME) or self.area_key
        self.lock_entity: str | None = cfg.get(CONF_LOCK)
        targets, defaults, post_actions = _build_targets(cfg)
        self.engine = AreaEngine(
            area_key=self.area_key,
            targets=targets,
            defaults=defaults,
            post_actions=post_actions,
        )
        self._listeners: list = []
        self._refresh_cbs: list = []
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{self.area_key}")
        self._settle_task: asyncio.Task | None = None
        self._debounce_task: asyncio.Task | None = None
        self._apply_lock = asyncio.Lock()
        self._post_seq = 0
        self._yaml_snapshot_keys: set[tuple[str, str]] = set()
        self._scenes_mtime: float | None = None
        self._remove_state_listener = None

    # -- entity refresh plumbing --
    def register_refresh(self, cb) -> None:
        self._refresh_cbs.append(cb)

    @callback
    def refresh(self) -> None:
        for cb in list(self._refresh_cbs):
            try:
                cb()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("HALO refresh cb failed")

    # -- state snapshot of tracked entities --
    def live_states(self) -> dict[str, tuple[str | None, dict[str, Any]]]:
        out: dict[str, tuple[str | None, dict[str, Any]]] = {}
        seen: set[str] = set()
        for (_m, _p), t in self.engine.targets.items():
            for eid in t.get("tracked", []):
                seen.add(eid)
        # also include entities from learned snapshots so renames don't blind us
        for snap in self.engine.snapshots.values():
            seen.update(snap.keys())
        for eid in seen:
            st = self.hass.states.get(eid)
            if st is None:
                continue
            out[eid] = (st.state, dict(st.attributes))
        return out

    async def _load_snapshots(self) -> None:
        # 1) learned snapshots from storage
        try:
            data = await self._store.async_load()
        except Exception:  # noqa: BLE001
            data = None
        if isinstance(data, dict):
            for k, snap in (data.get("snapshots") or {}).items():
                try:
                    mood, preset = k.split("::", 1)
                    self.engine.snapshots[(mood, preset)] = snap
                except ValueError:
                    continue
            req = data.get("requested") or {}
            if req.get("mood"):
                self.engine.requested_mood = req["mood"]
                self.engine.requested_preset = req.get("preset")
        # 2) authoritative scene targets from scenes.yaml (overrides learned)
        try:
            await self._import_scenes_yaml()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("HALO[%s] scenes.yaml import skipped", self.area_key)
        # 3) drop stale snapshots (e.g. pre-"base" "none" keys) so dead
        # configs can't hijack decisions; migrate none->default instead.
        for key in list(self.engine.snapshots):
            if key in self.engine.targets:
                continue
            mood, preset = key
            if preset == PRESET_NONE:
                new_key = (mood, self.engine.default_preset_for(mood))
                if (
                    new_key in self.engine.targets
                    and new_key not in self.engine.snapshots
                ):
                    self.engine.snapshots[new_key] = self.engine.snapshots[key]
            del self.engine.snapshots[key]
        await self._save()

    async def _import_scenes_yaml(self) -> int:
        import yaml

        path = self.hass.config.path("scenes.yaml")

        def _read() -> Any:
            try:
                with open(path, encoding="utf-8") as f:
                    return yaml.safe_load(f)
            except FileNotFoundError:
                return None
            except (OSError, yaml.YAMLError) as err:
                _LOGGER.warning(
                    "HALO[%s] cannot parse %s (%s); scene snapshots skipped",
                    self.area_key, path, err,
                )
                return None

        docs = await self.hass.async_add_executor_job(_read)
        if docs is None:
            return 0
        if not isinstance(docs, list):
            return 0
        try:
            import os

            self._scenes_mtime = await self.hass.async_add_executor_job(
                os.path.getmtime, path
            )
        except OSError:
            pass
        by_id = {str(s.get("id")): s for s in docs if isinstance(s, dict)}
        for (mood, preset), t in self.engine.targets.items():
            # Reference scenes verify script outcomes: the expected snapshot
            # comes from the referenced scene, not the script's action.
            verify = t.get("verify") or {}
            slug = ""
            if verify.get("mode") == "scene" and verify.get("scene"):
                slug = str(verify["scene"]).split(".", 1)[1]
            else:
                action = t.get("action", "")
                if action.startswith("scene."):
                    slug = action.split(".", 1)[1]
            if not slug:
                continue
            scene = None
            for s in docs:
                if not isinstance(s, dict):
                    continue
                sname = str(s.get("name", ""))
                sid = str(s.get("id", ""))
                if sid == slug or sname.lower().replace(" ", "_") == slug:
                    scene = s
                    break
                if sid in by_id and sid == slug:
                    scene = by_id[sid]
                    break
            if not scene:
                _LOGGER.warning(
                    "HALO[%s] scene '%s' for %s/%s not found in scenes.yaml; "
                    "fill Tracked entities (Autofill helps) or fix the scene id, "
                    "or this preset can never verify",
                    self.area_key, slug, mood, preset,
                )
                continue
            entities = scene.get("entities") or {}
            snap: dict[str, dict[str, Any]] = {}
            for eid, attrs in entities.items():
                if not isinstance(attrs, dict):
                    snap[eid] = {"state": "on"}
                    continue
                sub = {"state": attrs.get("state", "on")}
                for k, v in attrs.items():
                    if k == "state":
                        continue
                    sub[k] = v
                snap[eid] = sub
            if snap:
                self.engine.snapshots[(mood, preset)] = snap
                self._yaml_snapshot_keys.add((mood, preset))
                if not t.get("tracked"):
                    t["tracked"] = sorted(snap.keys())
        self._subscribe_members()
        return len(self._yaml_snapshot_keys)

    def _tracked_entity_ids(self) -> set[str]:
        seen: set[str] = set()
        for t in self.engine.targets.values():
            seen.update(t.get("tracked", []))
        for snap in self.engine.snapshots.values():
            seen.update(snap.keys())
        return seen

    @callback
    def _subscribe_members(self) -> None:
        """(Re)subscribe manual-change detection to all tracked entities."""
        if self._remove_state_listener:
            self._remove_state_listener()
            self._remove_state_listener = None
        tracked = self._tracked_entity_ids()
        if tracked:
            self._remove_state_listener = evt.async_track_state_change_event(
                self.hass, list(tracked), self._member_changed
            )

    async def _maybe_refresh_scenes_yaml(self) -> None:
        """Re-import scenes.yaml if it changed since the last read.

        Scene edits (UI or yaml) otherwise stay invisible until something
        forces an entry reload. Cheap mtime check; full re-import plus
        listener refresh only on change.
        """
        import os

        path = self.hass.config.path("scenes.yaml")
        try:
            mtime = await self.hass.async_add_executor_job(
                os.path.getmtime, path
            )
        except OSError:
            return
        if self._scenes_mtime is not None and mtime <= self._scenes_mtime:
            return
        before = {
            k: v for k, v in self.engine.snapshots.items()
            if k in self._yaml_snapshot_keys
        }
        count = await self._import_scenes_yaml()
        after = {
            k: v for k, v in self.engine.snapshots.items()
            if k in self._yaml_snapshot_keys
        }
        if before != after:
            _LOGGER.debug(
                "HALO[%s] scenes.yaml changed; refreshed %d scene snapshot(s)",
                self.area_key, count,
            )

    async def _save(self) -> None:
        data = {
            "requested": {
                "mood": self.engine.requested_mood,
                "preset": self.engine.requested_preset,
            },
            "snapshots": {
                f"{m}::{p}": snap
                for (m, p), snap in self.engine.snapshots.items()
            },
        }
        try:
            await self._store.async_save(data)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("HALO[%s] save failed", self.area_key)

    # -- the single-input apply path --
    def _locked(self) -> bool:
        if not self.lock_entity:
            return False
        st = self.hass.states.get(self.lock_entity)
        return st is not None and st.state == "on"

    async def async_request(
        self, mood: str, preset: str | None, *, via: str = "select"
    ) -> None:
        # Serialize overlapping requests (quick / double mood changes) so
        # scene/script calls, persistence and settle scheduling stay ordered:
        # the *latest* request always wins.
        async with self._apply_lock:
            # Empty/missing presets resolve onto the mood's designated
            # default (usually "default", user-overridable per mood).
            # Explicit unknown presets pass through so the lookup below
            # still rejects typos instead of silently applying a default.
            preset = self.engine.resolve_preset(mood, preset)
            key = (mood, preset)
            target = self.engine.targets.get(key)
            if target is None:
                raise ValueError(f"Unknown mood/preset {mood}/{preset}")

            evt_payload = self.engine.note_requested(mood, preset)
            seq = self.engine.request_seq
            self.hass.bus.async_fire("halo_mood_applied", evt_payload)
            self.refresh()

            tune: MoodTuning = target["tuning"]
            action: str = target["action"]
            if self.hass.states.get(action) is None:
                _LOGGER.error(
                    "HALO[%s] action entity %s for %s/%s does not exist; "
                    "check the mapping (scene renamed?)",
                    self.area_key, action, mood, preset,
                )
            domain, _, obj = action.partition(".")
            try:
                if domain == "scene":
                    await self.hass.services.async_call(
                        "scene",
                        "turn_on",
                        {"entity_id": action, "transition": tune.transition},
                        blocking=False,
                    )
                elif domain == "script":
                    await self.hass.services.async_call(
                        "script",
                        obj,
                        {
                            "mood": mood,
                            "preset": preset,
                            "transition_time": tune.transition,
                            "target_areas": [self.area_key],
                        },
                        blocking=False,
                    )
                else:
                    _LOGGER.warning("HALO[%s] unsupported action %s", self.area_key, action)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("HALO[%s] apply failed", self.area_key)

            await self._save()
            # settle window: keep status=transitioning, then verify + learn.
            # Older settle tasks are cancelled, and each task carries its
            # request seq so a stale task can never overwrite a newer request.
            if self._settle_task and not self._settle_task.done():
                self._settle_task.cancel()
            if self._debounce_task and not self._debounce_task.done():
                self._debounce_task.cancel()
            self._settle_task = self.hass.async_create_task(
                self._settle_then_verify(key, tune, seq)
            )

    async def _settle_then_verify(
        self, key, tune: MoodTuning, seq: int
    ) -> None:
        await asyncio.sleep(tune.settle)
        if seq != self.engine.request_seq:
            # superseded by a newer (quick/double) request: stay silent.
            return
        # Scene edits land here without any re-save: refresh snapshots
        # (and tracking) before judging, so the check always uses the
        # current scene definition.
        await self._maybe_refresh_scenes_yaml()
        action_known = self.hass.states.get(
            (self.engine.targets.get(key) or {}).get("action", "")
        ) is not None
        if not action_known and key in self.engine.snapshots:
            # Heal snapshots learned from applies that could never verify
            # (renamed/deleted scene or script): drop them unless they came
            # from scenes.yaml, so the next apply starts honest.
            if key not in self._yaml_snapshot_keys:
                _LOGGER.warning(
                    "HALO[%s] dropping stale snapshot for %s/%s; its action "
                    "no longer exists",
                    self.area_key, key[0], key[1],
                )
                del self.engine.snapshots[key]
                await self._save()
        # learn live as expected ONLY where comparison needs it (see below).
        states = self.live_states()
        changed = self.engine.apply_decision(states)
        if changed:
            self.hass.bus.async_fire("halo_active_changed", changed)
        # if requested still not matching but a scene snapshot exists, keep truth.
        # Learn only where comparison needs it, and only from actions that
        # resolve: learning arbitrary live states as truth is how phantom
        # active/custom states are born.
        if (
            key not in self.engine.snapshots
            and states
            and self.engine.should_learn(key, known_action=action_known)
        ):
            self.engine.learn_snapshot(key[0], key[1], states)
            changed2 = self.engine.apply_decision(states)
            if changed2:
                self.hass.bus.async_fire("halo_active_changed", changed2)
            await self._save()
        # Post script: the requested mood just became current. Fire once per
        # request (seq-guarded) so re-evaluations never double-run it.
        if (
            self.engine.status == STATUS_ACTIVE
            and self.engine.active_mood == self.engine.requested_mood
            and seq != self._post_seq
        ):
            script = self.engine.post_script()
            if script:
                self._post_seq = seq
                await self._run_post_script(script, key)
        self.refresh()

    async def _run_post_script(self, script: str, key) -> None:
        domain, _, obj = script.partition(".")
        if domain != "script" or not obj:
            _LOGGER.warning(
                "HALO[%s] post action must be a script, got %s",
                self.area_key, script,
            )
            return
        try:
            await self.hass.services.async_call(
                "script",
                obj,
                {
                    "mood": key[0],
                    "preset": key[1],
                    "target_areas": [self.area_key],
                },
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("HALO[%s] post script failed", self.area_key)
            return
        self.hass.bus.async_fire(
            EVENT_POST_RAN,
            {"area": self.area_key, "mood": key[0], "preset": key[1],
             "script": script},
        )

    @callback
    def _member_changed(self, _event=None) -> None:
        # debounce re-evaluation (scene_state/stateful_scenes debounce concept)
        tune = MoodTuning()
        if self.engine.requested_mood:
            tune = self.engine.tuning_for(
                self.engine.requested_mood,
                self.engine.resolve_preset(
                    self.engine.requested_mood, self.engine.requested_preset
                ),
            )
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        seq = self.engine.request_seq

        async def _run() -> None:
            await asyncio.sleep(tune.debounce)
            if seq != self.engine.request_seq:
                # a newer request arrived while debouncing: its settle
                # task owns verification now.
                return
            # don't fight an ongoing settle window
            if time.monotonic() - self.engine.last_transition_ts < tune.settle:
                return
            await self._maybe_refresh_scenes_yaml()
            changed = self.engine.apply_decision(self.live_states())
            if changed:
                self.hass.bus.async_fire("halo_active_changed", changed)
            self.refresh()

        self._debounce_task = self.hass.async_create_task(_run())

    async def async_resync(self) -> None:
        """Re-apply the requested mood (clears manual 'custom' drift)."""
        if self.engine.requested_mood:
            await self.async_request(
                self.engine.requested_mood,
                self.engine.requested_preset,
                via="resync",
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    area = HaloArea(hass, entry)
    await area._load_snapshots()
    hass.data[DOMAIN][entry.entry_id] = area

    async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    # track member entities for manual-change -> custom detection
    # (idempotent; the scenes.yaml import above already subscribed once)
    area._subscribe_members()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # sidebar panel (manual frontend, registered only once)
    try:
        from homeassistant.components import panel_custom
        from homeassistant.components.http import StaticPathConfig

        if "halo" not in hass.data.get("_halo_panel_registered", set()):
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        "/halo_static",
                        hass.config.path("custom_components/halo/frontend"),
                        False,
                    )
                ]
            )
            # Cache-bust the bundle URL with the integration version: the
            # filename never changes, so without this browsers can sit on a
            # stale (or broken) copy forever and show a blank panel.
            try:
                from homeassistant.loader import async_get_integration

                integration = await async_get_integration(hass, DOMAIN)
                bundle_url = f"/halo_static/halo-panel.js?v={integration.version}"
            except Exception:  # noqa: BLE001
                bundle_url = "/halo_static/halo-panel.js"
            await panel_custom.async_register_panel(
                hass,
                frontend_url_path="halo",
                webcomponent_name="halo-panel",
                sidebar_title="HALO",
                sidebar_icon="mdi:lightbulb-group",
                module_url=bundle_url,
                embed_iframe=False,
                require_admin=False,
            )
            hass.data.setdefault("_halo_panel_registered", set()).add("halo")
    except Exception:  # noqa: BLE001
        _LOGGER.debug("HALO panel registration skipped", exc_info=True)

    async def _handle_apply(call) -> None:
        area_id = call.data.get("area")
        mood = call.data.get("mood")
        preset = call.data.get("preset")
        for a in hass.data[DOMAIN].values():
            if isinstance(a, HaloArea) and (a.area_key == area_id or area_id is None):
                if a._locked() and len(hass.data[DOMAIN]) > 1 and call.data.get("homewide"):
                    continue
                try:
                    await a.async_request(mood, preset, via="service")
                except ValueError:
                    _LOGGER.warning(
                        "HALO[%s] ignoring unknown mood/preset %s/%s",
                        a.area_key, mood, preset,
                    )

    async def _handle_resync(call) -> None:
        area_id = call.data.get("area")
        for a in hass.data[DOMAIN].values():
            if isinstance(a, HaloArea) and (a.area_key == area_id or area_id is None):
                await a.async_resync()

    if not hass.services.has_service(DOMAIN, "apply_mood"):
        hass.services.async_register(DOMAIN, "apply_mood", _handle_apply)
        hass.services.async_register(DOMAIN, "resync", _handle_resync)

    # websocket API powers in-panel mapping editing (best-effort: the
    # classic options dialog keeps working without it).
    try:
        from . import websocket as halo_ws

        halo_ws.async_register(hass)
    except Exception:  # noqa: BLE001
        _LOGGER.debug("HALO websocket API unavailable", exc_info=True)

    # initial evaluation so sensors show truth right after restart
    area.engine.apply_decision(area.live_states())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    area = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if area is not None:
        if area._remove_state_listener:
            area._remove_state_listener()
        for t in (area._settle_task, area._debounce_task):
            if t and not t.done():
                t.cancel()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
