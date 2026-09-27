"""HALO per-area engine: single input -> apply -> settle -> verify.

Flow (per user spec):
1. User changes select.halo_<area>_mood / select.halo_<area>_preset (single source).
2. Engine treats it as a *request*: calls the user-mapped scene.* / script.*,
   sets status=transitioning immediately for display.
3. Waits settle (grace, per mood) + debounce, then compares live states
   against expected snapshots with per-mood tolerance/ignore rules.
4. If requested (mood, preset) fully matches -> status=active,
   active_mood/active_preset sensors show the mood name.
5. If something else fully matches -> active_* follows reality, status=active
   (user's selects stay as requested; sensors show truth).
6. If nothing matches -> active_* = custom, status=custom (display only,
   engine never writes the input selects on its own).

Expected snapshots come from two sources (mirrors stateful_scenes external
learn + scene_state yaml read):
- scene-mapped presets: parsed from scenes.yaml (authoritative) when available.
- anything else (scripts, missing yaml): learned by snapshotting tracked
  entities after a successful apply (persisted in .storage).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

try:
    from .const import (
        CONF_DEBOUNCE,
        CONF_IGNORE_ATTRS,
        CONF_IGNORE_UNAVAILABLE,
        CONF_SETTLE,
        CONF_TOLERANCE,
        DEFAULT_DEBOUNCE,
        DEFAULT_IGNORE_UNAVAILABLE,
        DEFAULT_SETTLE,
        DEFAULT_TOLERANCE,
        EVENT_ACTIVE_CHANGED,
        EVENT_APPLIED,
        MOOD_CUSTOM,
        PRESET_NONE,
        STATUS_ACTIVE,
        STATUS_CUSTOM,
        STATUS_TRANSITIONING,
        pick_default_preset,
    )
    from .matcher import diff_snapshot, snapshot_matches
except ImportError:  # loaded standalone in unit tests
    from const import (  # type: ignore[no-redef]
        CONF_DEBOUNCE,
        CONF_IGNORE_ATTRS,
        CONF_IGNORE_UNAVAILABLE,
        CONF_SETTLE,
        CONF_TOLERANCE,
        DEFAULT_DEBOUNCE,
        DEFAULT_IGNORE_UNAVAILABLE,
        DEFAULT_SETTLE,
        DEFAULT_TOLERANCE,
        EVENT_ACTIVE_CHANGED,
        EVENT_APPLIED,
        MOOD_CUSTOM,
        PRESET_NONE,
        STATUS_ACTIVE,
        STATUS_CUSTOM,
        STATUS_TRANSITIONING,
        pick_default_preset,
    )
    from matcher import diff_snapshot, snapshot_matches  # type: ignore[no-redef]

_LOGGER = logging.getLogger(__name__)

COMPARE_ATTR_KEYS = (
    "brightness",
    "rgb_color",
    "xy_color",
    "hs_color",
    "color_temp_kelvin",
    "effect",
    "position",
    "percentage",
    "volume_level",
)


@dataclass
class MoodTuning:
    transition: float = 2.0
    settle: float = DEFAULT_SETTLE
    debounce: float = DEFAULT_DEBOUNCE
    tolerance: float = DEFAULT_TOLERANCE
    ignore_attrs: tuple = ()
    ignore_unavailable: bool = DEFAULT_IGNORE_UNAVAILABLE

    @classmethod
    def from_cfg(cls, cfg: dict[str, Any]) -> "MoodTuning":
        return cls(
            transition=float(cfg.get("transition", 2.0)),
            settle=float(cfg.get(CONF_SETTLE, DEFAULT_SETTLE)),
            debounce=float(cfg.get(CONF_DEBOUNCE, DEFAULT_DEBOUNCE)),
            tolerance=float(cfg.get(CONF_TOLERANCE, DEFAULT_TOLERANCE)),
            ignore_attrs=tuple(cfg.get(CONF_IGNORE_ATTRS, ())),
            ignore_unavailable=bool(
                cfg.get(CONF_IGNORE_UNAVAILABLE, DEFAULT_IGNORE_UNAVAILABLE)
            ),
        )


@dataclass
class AreaEngine:
    """Framework-free state machine so it can be unit-tested.

    The HA glue (hass calls, listeners, persistence) is injected via callbacks
    by __init__.py; this class owns the transition/custom decision logic.
    """

    area_key: str
    # (mood, preset) -> {"action": entity_id, "tracked": [entity_ids], "tuning": MoodTuning}
    targets: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    # mood -> preset a bare mood request resolves to ("default" normally,
    # but the user may designate e.g. "party").
    defaults: dict[str, str] = field(default_factory=dict)
    # mood -> script.* ran once when the requested mood becomes active.
    post_actions: dict[str, str] = field(default_factory=dict)
    snapshots: dict[tuple[str, str], dict[str, dict[str, Any]]] = field(
        default_factory=dict
    )

    requested_mood: str | None = None
    requested_preset: str | None = None
    active_mood: str = MOOD_CUSTOM
    active_preset: str = PRESET_NONE
    status: str = STATUS_CUSTOM
    mismatched: list[str] = field(default_factory=list)
    mismatch_details: dict[str, dict[str, list]] = field(default_factory=dict)
    last_transition_ts: float = 0.0
    # Monotonic generation of the latest request. HA glue stamps settle /
    # debounce tasks with the seq at schedule time and drops them if a
    # newer request arrived (quick / double / overlapping mood changes).
    request_seq: int = 0

    _settle_task: asyncio.Task | None = field(default=None, repr=False)
    _debounce_task: asyncio.Task | None = field(default=None, repr=False)

    # ---- configuration helpers ----
    def presets_for_mood(self, mood: str) -> list[str]:
        out = sorted({p for (m, p) in self.targets if m == mood})
        return out or [PRESET_NONE]

    def default_preset_for(self, mood: str) -> str:
        """Preset a bare mood request resolves to (user-designated default)."""
        presets = self.presets_for_mood(mood)
        if presets == [PRESET_NONE]:
            return PRESET_NONE
        return pick_default_preset(presets, self.defaults.get(mood))

    def resolve_preset(self, mood: str, preset: str | None) -> str:
        """Empty/none preset requests resolve onto the mood's default.

        Explicit but unknown presets pass through untouched so callers can
        still reject typos instead of silently applying something else.
        """
        if not preset or preset == PRESET_NONE:
            return self.default_preset_for(mood)
        return preset

    def tuning_for(self, mood: str, preset: str) -> MoodTuning:
        t = self.targets.get((mood, preset))
        if t and isinstance(t.get("tuning"), MoodTuning):
            return t["tuning"]
        return MoodTuning()

    def tracked_for(self, mood: str, preset: str) -> list[str]:
        t = self.targets.get((mood, preset))
        return list((t or {}).get("tracked", []))

    def verify_for(self, mood: str, preset: str) -> dict[str, Any]:
        """Verification policy: auto | snapshot | off | reference scene."""
        t = self.targets.get((mood, preset)) or {}
        verify = t.get("verify") or {}
        if not isinstance(verify, dict):
            verify = {}
        mode = verify.get("mode", "auto")
        if mode not in ("auto", "snapshot", "off", "scene"):
            mode = "auto"
        return {"mode": mode, "scene": verify.get("scene", "")}

    def is_script_target(self, mood: str, preset: str) -> bool:
        """True when the target's action is a script (not a scene)."""
        action = str((self.targets.get((mood, preset)) or {}).get("action", ""))
        return not action.startswith("scene.")

    def is_trusted(self, mood: str, preset: str) -> bool:
        """True when a settled request needs no comparison.

        Explicit off, plus auto for scripts (Auto means same-scene for
        scenes and trust-apply for scripts).
        """
        mode = self.verify_for(mood, preset)["mode"]
        return mode == "off" or (
            mode == "auto" and self.is_script_target(mood, preset)
        )

    def should_learn(self, key: tuple[str, str], *, known_action: bool = True) -> bool:
        """Whether a settle may snapshot live states for this target.

        Explicit snapshot mode always learns on first apply (from a real
        apply); auto learns only for scene-backed targets missing their
        yaml snapshot. Trusted targets never learn. Learning from an
        action that doesn't resolve would enshrine arbitrary live states
        as truth, so unknown actions veto learning entirely.
        """
        if not known_action:
            return False
        if key in self.snapshots:
            return False
        mode = self.verify_for(key[0], key[1])["mode"]
        if mode == "snapshot":
            return True
        return mode == "auto" and not self.is_script_target(key[0], key[1])

    def post_script(self) -> str | None:
        """Post script for the requested mood (None when unconfigured)."""
        if not self.requested_mood:
            return None
        return self.post_actions.get(self.requested_mood)

    # ---- core decisions (pure, testable) ----
    def decide(
        self,
        states: dict[str, tuple[str | None, dict[str, Any]]],
        now: float | None = None,
    ) -> tuple[str, str, str, list[str]]:
        """Return (active_mood, active_preset, status, mismatched).

        - Full match on requested -> active.
        - Full match on something else -> active (sensors follow reality).
        - Within settle window of last request -> transitioning.
        - Requested target with verify=off past settle -> active on trust
          (dynamic scripts nothing could be compared against). Auto behaves
          the same for script actions; scenes always compare.
        - Else custom.
        """
        now = time.monotonic() if now is None else now
        req = (self.requested_mood, self.requested_preset)

        def _check(key: tuple[str, str]) -> tuple[bool, list[str]]:
            snap = self.snapshots.get(key)
            if not snap:
                return False, []
            tune = self.tuning_for(key[0], key[1])
            ok, mism, _unk = snapshot_matches(
                snap,
                states,
                tolerance=tune.tolerance,
                ignore_attrs=tune.ignore_attrs,
                ignore_unavailable=tune.ignore_unavailable,
            )
            return ok, mism

        if req[0] and req in self.snapshots:
            ok, mism = _check(req)
            if ok:
                return req[0], req[1] or PRESET_NONE, STATUS_ACTIVE, []
            # requested known but not matching: maybe still settling?
            tune = self.tuning_for(req[0], req[1] or PRESET_NONE)
            if now - self.last_transition_ts < tune.settle:
                return req[0], req[1] or PRESET_NONE, STATUS_TRANSITIONING, mism
            # fall through: check other candidates before declaring custom

        for key in self.snapshots:
            if key == req:
                continue
            ok, _mism = _check(key)
            if ok:
                ret_preset = key[1] or PRESET_NONE
                return key[0], ret_preset, STATUS_ACTIVE, []

        # nothing matches
        if req[0]:
            tune = self.tuning_for(req[0], req[1] or PRESET_NONE)
            if now - self.last_transition_ts < tune.settle:
                return req[0], req[1] or PRESET_NONE, STATUS_TRANSITIONING, []
            if self.is_trusted(req[0], req[1] or PRESET_NONE):
                return req[0], req[1] or PRESET_NONE, STATUS_ACTIVE, []
            # report mismatches of requested for the panel
            _, mism = _check(req) if req in self.snapshots else (False, [])
            return MOOD_CUSTOM, PRESET_NONE, STATUS_CUSTOM, mism
        return MOOD_CUSTOM, PRESET_NONE, STATUS_CUSTOM, []

    def diff_requested(
        self,
        states: dict[str, tuple[str | None, dict[str, Any]]],
    ) -> dict[str, dict[str, list]]:
        """Per-attribute diffs of the requested mood vs live states.

        Powers the panel's "why not active" display and the
        `mismatch_details` sensor attribute. Empty when the request is
        unknown or fully matches.
        """
        req = (self.requested_mood, self.requested_preset)
        snap = self.snapshots.get(req) if req[0] else None
        if not snap:
            return {}
        tune = self.tuning_for(req[0], req[1] or PRESET_NONE)
        return diff_snapshot(
            snap,
            states,
            tolerance=tune.tolerance,
            ignore_attrs=tune.ignore_attrs,
            ignore_unavailable=tune.ignore_unavailable,
        )

    def apply_decision(
        self,
        states: dict[str, tuple[str | None, dict[str, Any]]],
        now: float | None = None,
    ) -> dict[str, Any]:
        """Run decide() and update fields + change event payload (or {})."""
        old = (self.active_mood, self.active_preset, self.status)
        mood, preset, status, mism = self.decide(states, now=now)
        self.active_mood, self.active_preset, self.status = mood, preset, status
        self.mismatched = mism
        self.mismatch_details = self.diff_requested(states)
        if old != (mood, preset, status):
            return {
                "area": self.area_key,
                "active_mood": mood,
                "active_preset": preset,
                "status": status,
                "mismatched": mism,
                "event": EVENT_ACTIVE_CHANGED,
            }
        return {}

    # ---- lifecycle hooks used by HA glue ----
    def note_requested(self, mood: str, preset: str) -> dict[str, Any]:
        self.requested_mood = mood
        self.requested_preset = preset
        self.last_transition_ts = time.monotonic()
        self.status = STATUS_TRANSITIONING
        self.request_seq += 1
        return {
            "area": self.area_key,
            "mood": mood,
            "preset": preset,
            "seq": self.request_seq,
            "event": EVENT_APPLIED,
        }

    def learn_snapshot(
        self,
        mood: str,
        preset: str,
        states: dict[str, tuple[str | None, dict[str, Any]]],
    ) -> None:
        """Persist current live states as expected for (mood, preset).

        Only stores COMPARE_ATTR_KEYS subset (like scene_state stores only
        attrs the scene defines) so unrelated attrs don't break matching.
        """
        tracked = self.tracked_for(mood, preset) or list(states.keys())
        snap: dict[str, dict[str, Any]] = {}
        for eid in tracked:
            st = states.get(eid)
            if st is None:
                continue
            state, attrs = st
            if state in (None, "unavailable", "unknown", ""):
                continue
            sub = {"state": state}
            for k in COMPARE_ATTR_KEYS:
                # skip attrs the device doesn't report (None) so learned
                # snapshots stay clean and comparable.
                if k in attrs and attrs[k] is not None:
                    sub[k] = attrs[k]
            snap[eid] = sub
        if snap:
            self.snapshots[(mood, preset)] = snap
            _LOGGER.debug("HALO[%s] learned %s/%s: %d entities", self.area_key, mood, preset, len(snap))
