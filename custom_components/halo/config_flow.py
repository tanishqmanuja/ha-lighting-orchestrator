"""Config flow: one entry per user-defined area; per-mood tuning in options.

V1 keeps the flow approachable:
- Step 1 (user): pick HA area (or custom key), friendly name.
- Step 2 (moods): comma-separated mood list + quick defaults. Detailed
  per-mood / per-preset scene+script mapping + tolerance/debounce/settle/
  ignore rules are edited in Options (one mood at a time) so each mood can
  have its own preset list (including 0 presets).
"""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar, selector

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
    DEFAULT_TOLERANCE,
    DOMAIN,
)

PRESET_SPLIT = "presets (`base=scene.x, party=script.y@off`, at least one)"


def _validate_post_action(value: Any) -> str:
    """Normalize the optional post script ("" or script.*)."""
    text = str(value or "").strip()
    if text and not re.match(r"^script\.[A-Za-z0-9_]+$", text):
        raise ValueError("post script must look like script.x")
    return text


def _format_preset(name: str, pcfg: dict | None) -> str:
    """Render a preset back to `name=action` (verify lives in the panel)."""
    if not isinstance(pcfg, dict) or not pcfg.get(CONF_ACTION):
        return name
    return f"{name}={pcfg[CONF_ACTION]}"


def _parse_presets(text: str, *, keep_verify_from: dict | None = None) -> dict:
    """Parse `name=action[@verify]` pairs; bare names become unmapped presets.

    An explicit @verify suffix wins (`@off`, `@snapshot`, `@scene.<id>`,
    `@auto`); otherwise a preset that already exists keeps its stored verify
    mapping so an options-flow save never resets a panel-configured
    `off`/`snapshot`/`scene` back to auto.
    """
    from .const import normalize_verify

    keep = keep_verify_from or {}
    presets: dict = {}
    for chunk in [c.strip() for c in (text or "").split(",") if c.strip()]:
        if "=" in chunk:
            pname, action = [x.strip() for x in chunk.split("=", 1)]
            prev_verify = (keep.get(pname) or {}).get(CONF_VERIFY)
            verify = normalize_verify(
                prev_verify if prev_verify is not None else ""
            )
            if "@" in action:
                # Entity ids never contain "@", so this must be verify syntax.
                maybe_action, _, suffix = action.rpartition("@")
                suffix = suffix.strip()
                if suffix == "auto" or normalize_verify(suffix)["mode"] != "auto":
                    verify = normalize_verify(suffix)
                    action = maybe_action.strip()
            presets[pname] = (
                {CONF_ACTION: action, CONF_VERIFY: verify}
                if action
                else {}
            )
        else:
            presets[chunk] = {}
    return presets


class HaloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._area_id = ""
        self._area_name = ""

    async def async_step_user(self, user_input=None):
        areas = ar.async_get(self.hass)
        choices = {a.id: a.name for a in areas.async_list_areas()}
        if choices:
            area_schema = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in choices.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        else:
            # no HA areas yet: accept a free-form area key
            area_schema = str
        schema = vol.Schema(
            {
                vol.Required(CONF_AREA_ID): area_schema,
                vol.Optional(CONF_AREA_NAME, default=""): str,
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=schema)
        area_id = str(user_input[CONF_AREA_ID])
        await self.async_set_unique_id(f"{DOMAIN}_{area_id}")
        self._abort_if_unique_id_configured()
        self._area_id = area_id
        name = user_input.get(CONF_AREA_NAME) or area_id
        self._area_name = name
        return await self.async_step_moods()

    async def async_step_moods(self, user_input=None):
        schema = vol.Schema(
            {
                vol.Required("moods", default="morning, day, evening, unwind, night"): str,
                vol.Optional("transition", default=2.0): vol.Coerce(float),
                vol.Optional("settle", default=DEFAULT_SETTLE): vol.Coerce(float),
                vol.Optional("debounce", default=DEFAULT_DEBOUNCE): vol.Coerce(float),
                vol.Optional("tolerance", default=DEFAULT_TOLERANCE): vol.Coerce(float),
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="moods", data_schema=schema)
        moods: dict = {}
        for m in [x.strip() for x in user_input["moods"].split(",") if x.strip()]:
            moods[m] = {
                CONF_PRESETS: {"base": {}},
                CONF_DEFAULT_PRESET: "base",
                CONF_TRANSITION: user_input["transition"],
                CONF_SETTLE: user_input["settle"],
                CONF_DEBOUNCE: user_input["debounce"],
                CONF_TOLERANCE: user_input["tolerance"],
                CONF_IGNORE_ATTRS: [],
                CONF_IGNORE_UNAVAILABLE: True,
                CONF_TRACKED_ENTITIES: [],
            }
        return self.async_create_entry(
            title=f"HALO {self._area_name}",
            data={
                CONF_AREA_ID: self._area_id,
                CONF_AREA_NAME: self._area_name,
                CONF_MOODS: moods,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry):
        return HaloOptionsFlow(entry)


class HaloOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input=None):
        cfg = dict(self._entry.data)
        cfg.update(self._entry.options or {})
        moods = cfg.get(CONF_MOODS, {})
        return self.async_show_menu(
            step_id="init",
            menu_options=["mood", "add_mood", "done"],
            description_placeholders={"moods": ", ".join(moods) or "(none)"},
        )

    async def async_step_done(self, user_input=None):
        return self.async_create_entry(title="", data=self._entry.options or {})

    async def async_step_add_mood(self, user_input=None):
        schema = vol.Schema(
            {
                vol.Required("mood"): str,
                vol.Optional(PRESET_SPLIT, default=""): str,
                vol.Optional(CONF_DEFAULT_PRESET, default="base"): str,
                vol.Optional(CONF_POST_ACTION, default=""): str,
                vol.Optional(CONF_TRANSITION, default=2.0): vol.Coerce(float),
                vol.Optional(CONF_SETTLE, default=DEFAULT_SETTLE): vol.Coerce(float),
                vol.Optional(CONF_DEBOUNCE, default=DEFAULT_DEBOUNCE): vol.Coerce(float),
                vol.Optional(CONF_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
                vol.Optional("ignore_attrs", default=""): str,
                vol.Optional(CONF_IGNORE_UNAVAILABLE, default=True): bool,
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="add_mood", data_schema=schema)
        presets = _parse_presets(user_input[PRESET_SPLIT])
        default = (user_input.get(CONF_DEFAULT_PRESET) or "").strip()
        errors: dict[str, str] = {}
        if not presets:
            errors["base"] = "need_preset"
        elif default not in presets:
            errors[CONF_DEFAULT_PRESET] = "bad_default"
        try:
            post_action = _validate_post_action(user_input.get(CONF_POST_ACTION))
        except ValueError:
            errors[CONF_POST_ACTION] = "bad_post"
            post_action = ""
        if errors:
            return self.async_show_form(
                step_id="add_mood", data_schema=schema, errors=errors
            )
        opts = dict(self._entry.options or {})
        data = dict(self._entry.data)
        base = dict(data)
        base.update(opts)
        moods = dict(base.get(CONF_MOODS, {}))
        moods[user_input["mood"]] = {
            CONF_PRESETS: presets,
            CONF_DEFAULT_PRESET: default,
            CONF_POST_ACTION: post_action,
            CONF_TRANSITION: user_input[CONF_TRANSITION],
            CONF_SETTLE: user_input[CONF_SETTLE],
            CONF_DEBOUNCE: user_input[CONF_DEBOUNCE],
            CONF_TOLERANCE: user_input[CONF_TOLERANCE],
            CONF_IGNORE_ATTRS: [
                x.strip() for x in user_input["ignore_attrs"].split(",") if x.strip()
            ],
            CONF_IGNORE_UNAVAILABLE: user_input[CONF_IGNORE_UNAVAILABLE],
            CONF_TRACKED_ENTITIES: [],
        }
        new_opts = dict(opts)
        merged = dict(data)
        merged.update(new_opts)
        merged[CONF_MOODS] = moods
        # persist full moods map in options to avoid mutating data
        new_opts[CONF_MOODS] = moods
        if CONF_LOCK in merged:
            new_opts[CONF_LOCK] = merged[CONF_LOCK]
        return self.async_create_entry(title="", data=new_opts)

    async def async_step_mood(self, user_input=None):
        cfg = dict(self._entry.data)
        cfg.update(self._entry.options or {})
        moods = cfg.get(CONF_MOODS, {})
        if user_input is None:
            return self.async_show_form(
                step_id="mood",
                data_schema=vol.Schema({vol.Required("mood"): vol.In(list(moods) or ["-"])}),
            )
        self._editing = user_input["mood"]
        return await self.async_step_edit_mood()

    async def async_step_edit_mood(self, user_input=None):
        cfg = dict(self._entry.data)
        cfg.update(self._entry.options or {})
        moods = dict(cfg.get(CONF_MOODS, {}))
        mood = getattr(self, "_editing", next(iter(moods), ""))
        cur = moods.get(mood, {})
        presets = cur.get(CONF_PRESETS, {})
        flat = ", ".join(
            _format_preset(k, v) for k, v in presets.items()
        )
        schema = vol.Schema(
            {
                vol.Optional(PRESET_SPLIT, default=flat): str,
                vol.Optional(
                    CONF_DEFAULT_PRESET,
                    default=cur.get(CONF_DEFAULT_PRESET, "base"),
                ): str,
                vol.Optional(
                    CONF_POST_ACTION, default=cur.get(CONF_POST_ACTION, "")
                ): str,
                vol.Optional("tracked_entities (csv, empty=auto)", default=", ".join(cur.get(CONF_TRACKED_ENTITIES, []))): str,
                vol.Optional(CONF_TRANSITION, default=float(cur.get(CONF_TRANSITION, 2.0))): vol.Coerce(float),
                vol.Optional(CONF_SETTLE, default=float(cur.get(CONF_SETTLE, DEFAULT_SETTLE))): vol.Coerce(float),
                vol.Optional(CONF_DEBOUNCE, default=float(cur.get(CONF_DEBOUNCE, DEFAULT_DEBOUNCE))): vol.Coerce(float),
                vol.Optional(CONF_TOLERANCE, default=float(cur.get(CONF_TOLERANCE, DEFAULT_TOLERANCE))): vol.Coerce(float),
                vol.Optional("ignore_attrs (csv)", default=", ".join(cur.get(CONF_IGNORE_ATTRS, []))): str,
                vol.Optional(CONF_IGNORE_UNAVAILABLE, default=bool(cur.get(CONF_IGNORE_UNAVAILABLE, True))): bool,
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="edit_mood", data_schema=schema)
        presets2 = _parse_presets(
            user_input[PRESET_SPLIT], keep_verify_from=cur.get(CONF_PRESETS, {})
        )
        default2 = (user_input.get(CONF_DEFAULT_PRESET) or "").strip()
        errors2: dict[str, str] = {}
        if not presets2:
            errors2["base"] = "need_preset"
        elif default2 not in presets2:
            errors2[CONF_DEFAULT_PRESET] = "bad_default"
        try:
            post_action2 = _validate_post_action(user_input.get(CONF_POST_ACTION))
        except ValueError:
            errors2[CONF_POST_ACTION] = "bad_post"
            post_action2 = ""
        if errors2:
            return self.async_show_form(
                step_id="edit_mood", data_schema=schema, errors=errors2
            )
        moods[mood] = {
            CONF_PRESETS: presets2,
            CONF_DEFAULT_PRESET: default2,
            CONF_POST_ACTION: post_action2,
            CONF_TRACKED_ENTITIES: [x.strip() for x in user_input["tracked_entities (csv, empty=auto)"].split(",") if x.strip()],
            CONF_TRANSITION: user_input[CONF_TRANSITION],
            CONF_SETTLE: user_input[CONF_SETTLE],
            CONF_DEBOUNCE: user_input[CONF_DEBOUNCE],
            CONF_TOLERANCE: user_input[CONF_TOLERANCE],
            CONF_IGNORE_ATTRS: [x.strip() for x in user_input["ignore_attrs (csv)"].split(",") if x.strip()],
            CONF_IGNORE_UNAVAILABLE: user_input[CONF_IGNORE_UNAVAILABLE],
        }
        opts = dict(self._entry.options or {})
        opts[CONF_MOODS] = moods
        return self.async_create_entry(title="", data=opts)
