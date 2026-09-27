"""HALO constants: single source of input is select.mood + select.preset per area.

Concepts merged from:
- hass_mood_controller: area -> moods -> presets, script dispatch, locks, events.
- stateful_scenes: tolerance/debounce/transition/ignore-unavailable matching.
- scene_state: grace + debounce timers, mismatched_entities reporting.
"""
from __future__ import annotations

from typing import Any

DOMAIN = "halo"
PLATFORMS = ["select", "sensor", "button"]
STORAGE_KEY = "halo"
STORAGE_VERSION = 1

# Config keys (per config entry = one user-defined area)
CONF_AREA_ID = "area_id"
CONF_AREA_NAME = "area_name"
CONF_MOODS = "moods"

# Per-mood config keys (tuning is per mood, not per area, per user answers)
CONF_PRESETS = "presets"  # dict[str, preset_cfg]; every mood has >= 1 preset
CONF_DEFAULT_PRESET = "default_preset"  # which preset a bare mood request resolves to
CONF_ACTION = "action"  # per-preset entity_id of scene.* or script.*
# Optional per-mood script ran once when the requested mood becomes active.
CONF_POST_ACTION = "post_action"  # entity_id of script.*, or ""
# Per-preset verification: "auto" (scene->own targets, script->trust),
# "snapshot" (learn live states after settle, then compare), "off"
# (trust the apply), or a "scene.<id>" whose yaml targets verify the outcome.
CONF_VERIFY = "verify"
VERIFY_AUTO = "auto"
VERIFY_SNAPSHOT = "snapshot"
VERIFY_OFF = "off"
CONF_TRACKED_ENTITIES = "tracked_entities"  # list[str]; [] = auto-discover
CONF_TRANSITION = "transition"  # seconds passed to scene.turn_on / light
CONF_SETTLE = "settle"  # grace seconds after apply: status=transitioning, no eval
CONF_DEBOUNCE = "debounce"  # seconds to wait after member change before re-eval
CONF_TOLERANCE = "tolerance"  # numeric tolerance (brightness, temp, position...)
CONF_IGNORE_ATTRS = "ignore_attrs"  # e.g. ["effect", "color_temp_kelvin"]
CONF_IGNORE_UNAVAILABLE = "ignore_unavailable"
CONF_LOCK = "lock"  # input_boolean entity_id that blocks home-wide applies

# Defaults
DEFAULT_TRANSITION = 2.0
DEFAULT_SETTLE = 5.0
DEFAULT_DEBOUNCE = 2.0
DEFAULT_TOLERANCE = 1.0
DEFAULT_IGNORE_UNAVAILABLE = True

# Status values for sensor.halo_<area>_status
STATUS_ACTIVE = "active"
STATUS_TRANSITIONING = "transitioning"
STATUS_CUSTOM = "custom"

# Display fallback when no preset is known yet (never a real target key)
PRESET_NONE = "none"

# Conventional name of the auto-applied preset. Users see
# "default preset: base" instead of the confusing "default preset: default".
# Older configs using a "default" preset keep working via the fallback chain.
BASE_PRESET = "base"
LEGACY_DEFAULT_PRESET = "default"

# Custom marker when no mood matches (display only)
MOOD_CUSTOM = "custom"


def pick_default_preset(
    presets: dict[str, Any] | list[str] | tuple,
    designated: str | None = None,
) -> str:
    """Choose the preset a bare mood request resolves to.

    Chain: user-designated -> "base" -> legacy "default" -> first sorted.
    The legacy step keeps pre-base configs behaving exactly as before.
    """
    names = list(presets) if isinstance(presets, dict) else list(presets or [])
    if designated in names:
        return designated  # type: ignore[return-value]
    for fallback in (BASE_PRESET, LEGACY_DEFAULT_PRESET):
        if fallback in names:
            return fallback
    return sorted(names)[0] if names else BASE_PRESET


def normalize_verify(value: Any) -> dict[str, str]:
    """Normalize a per-preset verify setting to {"mode", "scene"}.

    Accepts "auto"/"snapshot"/"off"/"" or a "scene.<id>" reference (or an
    already normalized dict, so stored configs round-trip); anything else
    is auto (compared strictly, never silently trusted).
    """
    if isinstance(value, dict):
        mode = value.get("mode", VERIFY_AUTO)
        scene = value.get("scene", "")
        if mode == VERIFY_OFF:
            return {"mode": VERIFY_OFF, "scene": ""}
        if mode == VERIFY_SNAPSHOT:
            return {"mode": VERIFY_SNAPSHOT, "scene": ""}
        if (
            mode == "scene"
            and isinstance(scene, str)
            and scene.startswith("scene.")
            and len(scene) > len("scene.")
        ):
            return {"mode": "scene", "scene": scene}
        return {"mode": VERIFY_AUTO, "scene": ""}
    text = str(value or "").strip()
    if text == VERIFY_OFF:
        return {"mode": VERIFY_OFF, "scene": ""}
    if text == VERIFY_SNAPSHOT:
        return {"mode": VERIFY_SNAPSHOT, "scene": ""}
    if text.startswith("scene.") and len(text) > len("scene."):
        return {"mode": "scene", "scene": text}
    return {"mode": VERIFY_AUTO, "scene": ""}


def normalize_mood_cfg(mcfg: dict | None) -> dict:
    """Return a mood config in the current shape.

    Migrates legacy configs: a mood-level action with no presets (the old
    "0 presets" model) becomes a single "base" preset. Pure: safe to
    call on every load from entry data/options, websocket payloads, flows.
    """
    mcfg = dict(mcfg or {})
    presets = dict(mcfg.get(CONF_PRESETS) or {})
    action = mcfg.get(CONF_ACTION)
    if isinstance(action, str):
        action = action.strip()
    if not presets and action:
        presets = {BASE_PRESET: {CONF_ACTION: action}}
    mcfg[CONF_PRESETS] = presets
    mcfg.pop(CONF_ACTION, None)
    mcfg[CONF_DEFAULT_PRESET] = pick_default_preset(
        presets, mcfg.get(CONF_DEFAULT_PRESET)
    )
    return mcfg

# Attributes compared for lights (subset of stateful_scenes supported attrs)
LIGHT_COMPARE_ATTRS = (
    "brightness",
    "rgb_color",
    "xy_color",
    "hs_color",
    "color_temp_kelvin",
    "effect",
)
COVER_ATTRS = ("position",)
FAN_ATTRS = ("percentage", "oscillating", "direction")
MEDIA_ATTRS = ("volume_level", "source")

EVENT_APPLIED = "halo_mood_applied"
EVENT_ACTIVE_CHANGED = "halo_active_changed"
EVENT_POST_RAN = "halo_post_action"
