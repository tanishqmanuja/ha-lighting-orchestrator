"""Approximator tests: nearest mood by 0-100 confidence (no HA needed)."""
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


_const = _load("halo_approx_const", "const.py")
_matcher = _load("halo_approx_matcher", "matcher.py")
sys.modules["const"] = _const
sys.modules["matcher"] = _matcher
_engine = _load("halo_approx_engine", "engine.py")

AreaEngine = _engine.AreaEngine


def _engine_with(snaps):
    eng = AreaEngine(area_key="living")
    for key, snap in snaps.items():
        eng.targets[key] = {"action": f"scene.{key[0]}", "tracked": list(snap)}
        eng.snapshots[key] = snap
    return eng


def _at(eng, ts):
    eng.last_transition_ts = ts


def test_non_custom_active_mirrors_at_100():
    eng = _engine_with({("evening", "base"): {"light.x": {"state": "on"}}})
    eng.requested_mood, eng.requested_preset = "evening", "base"
    _at(eng, 1000.0)
    eng.apply_decision({"light.x": ("on", {})}, now=1060.0)
    assert (eng.active_mood, eng.status) == ("evening", "active")
    assert (eng.approx_mood, eng.approx_confidence) == ("evening", 100)


def test_custom_picks_highest_confidence_mood():
    eng = _engine_with(
        {
            ("evening", "base"): {
                "light.a": {"state": "on"},
                "light.b": {"state": "on"},
                "light.c": {"state": "on"},
            },
            ("movie", "base"): {
                "light.a": {"state": "off"},
                "light.b": {"state": "off"},
                "light.c": {"state": "off"},
            },
        }
    )
    eng.requested_mood, eng.requested_preset = "evening", "base"
    _at(eng, 1000.0)
    live = {
        "light.a": ("on", {}),
        "light.b": ("on", {}),
        "light.c": ("off", {}),
    }
    eng.apply_decision(live, now=1060.0)
    assert eng.status == "custom"
    # evening matches 2/3 entities (67), movie 1/3 (33): evening wins.
    assert (eng.approx_mood, eng.approx_confidence) == ("evening", 67)


def test_best_preset_wins_within_mood():
    eng = _engine_with(
        {
            ("evening", "base"): {
                "light.a": {"state": "on", "brightness": 100}
            },
            ("evening", "dim"): {
                "light.a": {"state": "on"},
                "light.b": {"state": "on"},
                "light.c": {"state": "on"},
            },
        }
    )
    eng.requested_mood, eng.requested_preset = "evening", "base"
    _at(eng, 1000.0)
    live = {
        "light.a": ("on", {"brightness": 200}),
        "light.b": ("on", {}),
        "light.c": ("off", {}),
    }
    eng.apply_decision(live, now=1060.0)
    assert eng.status == "custom"
    # dim: 2/3 (67); base: 0/1 brightness mismatch (0) -> mood scores 67 via dim.
    assert (eng.approx_mood, eng.approx_confidence) == ("evening", 67)


def test_below_threshold_stays_custom():
    eng = _engine_with(
        {
            ("evening", "base"): {
                "light.a": {"state": "on"},
                "light.b": {"state": "on"},
                "light.c": {"state": "on"},
            },
        }
    )
    eng.requested_mood, eng.requested_preset = "evening", "base"
    _at(eng, 1000.0)
    live = {
        "light.a": ("on", {}),
        "light.b": ("off", {}),
        "light.c": ("off", {}),
    }
    eng.apply_decision(live, now=1060.0)
    assert eng.status == "custom"
    # best is 1/3 (33) < 50: approximated stays custom, confidence kept.
    assert (eng.approx_mood, eng.approx_confidence) == ("custom", 33)


def test_no_snapshots_stays_custom_at_zero():
    eng = AreaEngine(area_key="living")
    # scene-backed target (not trusted) but no snapshot learned/imported yet.
    eng.targets[("evening", "base")] = {"action": "scene.x", "tracked": []}
    eng.requested_mood, eng.requested_preset = "evening", "base"
    _at(eng, 1000.0)
    eng.apply_decision({"light.a": ("on", {})}, now=1060.0)
    assert eng.status == "custom"
    assert (eng.approx_mood, eng.approx_confidence) == ("custom", 0)


def test_state_agreement_outweighs_attributes():
    # "zebra" gets on/off right but brightness wrong; "apple" gets on/off
    # wrong. State must win even though apple sorts first alphabetically.
    eng = _engine_with(
        {
            ("zebra", "base"): {"light.x": {"state": "on", "brightness": 100}},
            ("apple", "base"): {"light.x": {"state": "off"}},
        }
    )
    eng.requested_mood, eng.requested_preset = "zebra", "base"
    _at(eng, 1000.0)
    eng.apply_decision({"light.x": ("on", {"brightness": 200})}, now=1060.0)
    assert eng.status == "custom"
    # zebra: state hit, brightness miss (67); apple: state miss (0).
    assert (eng.approx_mood, eng.approx_confidence) == ("zebra", 67)


def test_attributes_break_state_ties():
    # Both moods agree with live on on/off for x and y and miss z, so
    # states tie 2/3; only brightness differs, and it decides.
    eng = _engine_with(
        {
            ("evening", "base"): {
                "light.x": {"state": "on", "brightness": 100},
                "light.y": {"state": "on"},
                "light.z": {"state": "on"},
            },
            ("morning", "base"): {
                "light.x": {"state": "on", "brightness": 200},
                "light.y": {"state": "on"},
                "light.z": {"state": "on"},
            },
        }
    )
    eng.requested_mood, eng.requested_preset = "evening", "base"
    _at(eng, 1000.0)
    live = {
        "light.x": ("on", {"brightness": 200}),
        "light.y": ("on", {}),
        "light.z": ("off", {}),
    }
    eng.apply_decision(live, now=1060.0)
    assert eng.status == "custom"
    # evening 57, morning 71: morning wins on attributes alone.
    assert (eng.approx_mood, eng.approx_confidence) == ("morning", 71)


def test_attributes_scored_when_states_disagree():
    # Both moods get on/off wrong; brightness still scores, but neither
    # reaches the threshold so approximated stays custom.
    eng = _engine_with(
        {
            ("evening", "base"): {
                "light.x": {"state": "off", "brightness": 100}
            },
            ("morning", "base"): {
                "light.x": {"state": "off", "brightness": 200}
            },
        }
    )
    eng.requested_mood, eng.requested_preset = "evening", "base"
    _at(eng, 1000.0)
    eng.apply_decision({"light.x": ("on", {"brightness": 200})}, now=1060.0)
    assert eng.status == "custom"
    # evening 0, morning 33: attrs differentiate, nobody wins.
    assert (eng.approx_mood, eng.approx_confidence) == ("custom", 33)
