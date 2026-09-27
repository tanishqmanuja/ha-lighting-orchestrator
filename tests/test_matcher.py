"""Unit tests for the framework-free matching engine (no HA needed)."""
import importlib.util
import sys
from pathlib import Path

HALO_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "halo"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HALO_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


_const = _load("halo_test_const", "const.py")
_matcher = _load("halo_test_matcher", "matcher.py")
sys.modules["const"] = _const
sys.modules["matcher"] = _matcher
_engine = _load("halo_test_engine", "engine.py")

PRESET_NONE = _const.PRESET_NONE
STATUS_ACTIVE = _const.STATUS_ACTIVE
STATUS_CUSTOM = _const.STATUS_CUSTOM
STATUS_TRANSITIONING = _const.STATUS_TRANSITIONING
AreaEngine = _engine.AreaEngine
MoodTuning = _engine.MoodTuning
entity_matches = _matcher.entity_matches
snapshot_matches = _matcher.snapshot_matches


def test_exact_match_active():
    eng = AreaEngine(area_key="living")
    eng.targets[("evening", "default")] = {"action": "scene.a", "tracked": ["light.x"], "tuning": MoodTuning()}
    eng.snapshots[("evening", "default")] = {"light.x": {"state": "on", "brightness": 100}}
    eng.note_requested("evening", "default")
    states = {"light.x": ("on", {"brightness": 100})}
    # force past settle
    eng.last_transition_ts -= 100
    mood, preset, status, _ = eng.decide(states)
    assert (mood, preset, status) == ("evening", "default", STATUS_ACTIVE)


def test_transitioning_inside_settle():
    eng = AreaEngine(area_key="living")
    eng.targets[("evening", "default")] = {"action": "scene.a", "tracked": ["light.x"], "tuning": MoodTuning(settle=60)}
    eng.snapshots[("evening", "default")] = {"light.x": {"state": "on", "brightness": 100}}
    eng.note_requested("evening", "default")
    states = {"light.x": ("on", {"brightness": 5})}
    mood, preset, status, _ = eng.decide(states)
    assert status == STATUS_TRANSITIONING


def test_custom_after_settle_with_manual_drift():
    eng = AreaEngine(area_key="living")
    eng.targets[("evening", "default")] = {"action": "scene.a", "tracked": ["light.x"], "tuning": MoodTuning(settle=0.001)}
    eng.snapshots[("evening", "default")] = {"light.x": {"state": "on", "brightness": 100}}
    eng.note_requested("evening", "default")
    eng.last_transition_ts -= 100
    states = {"light.x": ("on", {"brightness": 5})}
    mood, preset, status, mism = eng.decide(states)
    assert mood == "custom" and status == STATUS_CUSTOM and mism == ["light.x"]


def test_tolerance_and_ignore_attrs():
    ok, _ = entity_matches(
        {"state": "on", "brightness": 100, "effect": "x"},
        "on",
        {"brightness": 101, "effect": "y"},
        tolerance=1.0,
        ignore_attrs=["effect"],
    )
    assert ok
    ok2, _ = entity_matches(
        {"state": "on", "brightness": 100},
        "on",
        {"brightness": 110},
        tolerance=1.0,
    )
    assert not ok2


def test_zero_preset_mood():
    eng = AreaEngine(area_key="bed")
    eng.targets[("movie", PRESET_NONE)] = {"action": "scene.movie", "tracked": ["light.t"], "tuning": MoodTuning()}
    assert eng.presets_for_mood("movie") == [PRESET_NONE]


def test_snapshot_matches_reports_mismatched():
    ok, mism, _ = snapshot_matches(
        {"light.a": {"state": "on"}, "light.b": {"state": "off"}},
        {"light.a": ("on", {}), "light.b": ("on", {})},
    )
    assert not ok and mism == ["light.b"]


def test_null_attr_skipped_when_ignoring_unavailable():    # e.g. optimistic MQTT light reporting brightness: null
    ok, _ = entity_matches(
        {"state": "on", "brightness": 128},
        "on",
        {"brightness": None},
        ignore_unavailable=True,
    )
    assert ok
    ok2, _ = entity_matches(
        {"state": "on", "brightness": 128},
        "on",
        {"brightness": None},
        ignore_unavailable=False,
    )
    assert not ok2


def test_learn_snapshot_skips_null_attrs():
    eng = AreaEngine(area_key="living")
    eng.targets[("movie", PRESET_NONE)] = {
        "action": "script.x",
        "tracked": ["light.m"],
        "tuning": MoodTuning(),
    }
    eng.learn_snapshot(
        "movie", PRESET_NONE,
        {"light.m": ("on", {"brightness": 26, "rgb_color": None})},
    )
    assert eng.snapshots[("movie", PRESET_NONE)] == {
        "light.m": {"state": "on", "brightness": 26}
    }
