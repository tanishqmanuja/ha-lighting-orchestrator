"""Edge-case tests: quick / double / overlapping mood changes (no HA needed)."""
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


_const = _load("halo_edge_const", "const.py")
_matcher = _load("halo_edge_matcher", "matcher.py")
sys.modules["const"] = _const
sys.modules["matcher"] = _matcher
_engine = _load("halo_edge_engine", "engine.py")

PRESET_NONE = _const.PRESET_NONE
STATUS_ACTIVE = _const.STATUS_ACTIVE
STATUS_CUSTOM = _const.STATUS_CUSTOM
STATUS_TRANSITIONING = _const.STATUS_TRANSITIONING
AreaEngine = _engine.AreaEngine
MoodTuning = _engine.MoodTuning


def _two_mood_engine(settle_a=5.0, settle_b=5.0):
    eng = AreaEngine(area_key="living")
    eng.targets[("mood_a", "default")] = {
        "action": "scene.a",
        "tracked": ["light.x"],
        "tuning": MoodTuning(settle=settle_a),
    }
    eng.targets[("mood_b", "default")] = {
        "action": "scene.b",
        "tracked": ["light.x"],
        "tuning": MoodTuning(settle=settle_b),
    }
    eng.snapshots[("mood_a", "default")] = {
        "light.x": {"state": "on", "brightness": 100}
    }
    eng.snapshots[("mood_b", "default")] = {
        "light.x": {"state": "on", "brightness": 200}
    }
    return eng


def _at(eng, ts):
    """Pin the last-request timestamp (note_requested uses real monotonic)."""
    eng.last_transition_ts = ts


def test_request_seq_increments_and_reported():
    eng = _two_mood_engine()
    p1 = eng.note_requested("mood_a", "default")
    p2 = eng.note_requested("mood_b", "default")
    assert (p1["seq"], p2["seq"]) == (1, 2)
    assert eng.request_seq == 2


def test_quick_change_latest_wins():
    eng = _two_mood_engine()
    eng.note_requested("mood_a", "default")
    _at(eng, 1000.0)
    eng.note_requested("mood_b", "default")
    _at(eng, 1001.0)
    live_b = {"light.x": ("on", {"brightness": 200})}
    assert eng.decide(live_b, now=1001.0 + 5.0 + 1)[2] == STATUS_ACTIVE
    assert eng.decide(live_b, now=1001.0 + 5.0 + 1)[:2] == ("mood_b", "default")


def test_double_same_request_is_idempotent():
    eng = _two_mood_engine()
    eng.note_requested("mood_a", "default")
    _at(eng, 1000.0)
    eng.note_requested("mood_a", "default")
    _at(eng, 1000.5)
    live_a = {"light.x": ("on", {"brightness": 100})}
    mood, preset, status, _ = eng.decide(live_a, now=1000.5 + 5.0 + 1)
    assert (mood, preset, status) == ("mood_a", "default", STATUS_ACTIVE)
    assert eng.request_seq == 2


def test_latest_settle_window_governs():
    # A settles fast, B settles slow: after a quick A->B change the long
    # B window (not A's expired one) decides transitioning vs custom.
    eng = _two_mood_engine(settle_a=2.0, settle_b=100.0)
    eng.note_requested("mood_a", "default")
    _at(eng, 0.0)
    eng.note_requested("mood_b", "default")
    _at(eng, 1.0)
    live_neither = {"light.x": ("on", {"brightness": 10})}
    assert eng.decide(live_neither, now=50.0)[2] == STATUS_TRANSITIONING
    assert eng.decide(live_neither, now=150.0)[2] == STATUS_CUSTOM


def test_stale_match_yields_to_new_transition_then_truth():
    # Lights still show A while B is in flight: transitioning first...
    eng = _two_mood_engine()
    eng.note_requested("mood_a", "default")
    _at(eng, 0.0)
    eng.note_requested("mood_b", "default")
    _at(eng, 3.0)
    live_a = {"light.x": ("on", {"brightness": 100})}
    assert eng.decide(live_a, now=4.0)[2] == STATUS_TRANSITIONING
    # ...and once B's window passes with A still physically on, sensors
    # honestly follow reality instead of the unfulfilled request.
    mood, _, status, _ = eng.decide(live_a, now=9.0)
    assert (mood, status) == ("mood_a", STATUS_ACTIVE)


def test_rapid_toggle_aba_settles_on_final():
    eng = _two_mood_engine()
    eng.note_requested("mood_a", "default")
    _at(eng, 0.0)
    eng.note_requested("mood_b", "default")
    _at(eng, 1.0)
    eng.note_requested("mood_a", "default")
    _at(eng, 2.0)
    live_a = {"light.x": ("on", {"brightness": 100})}
    mood, preset, status, _ = eng.decide(live_a, now=2.0 + 5.0 + 1)
    assert (mood, preset, status) == ("mood_a", "default", STATUS_ACTIVE)
    assert (eng.requested_mood, eng.requested_preset) == ("mood_a", "default")


def test_unknown_request_falls_back_to_truth():
    # A request for an unknown mood has no snapshot to verify against, so
    # sensors follow physical truth (mood_a) rather than showing a stale
    # transition. (Unreachable via selects; defensive path for services.)
    eng = _two_mood_engine()
    eng.note_requested("ghost", PRESET_NONE)
    _at(eng, 0.0)
    live = {"light.x": ("on", {"brightness": 100})}
    mood, _, status, _ = eng.decide(live, now=1.0)
    assert (mood, status) == ("mood_a", STATUS_ACTIVE)
    mood, _, status, _ = eng.decide(live, now=100.0)
    assert (mood, status) == ("mood_a", STATUS_ACTIVE)


def _off_engine():
    eng = AreaEngine(area_key="living")
    eng.targets[("dyn", "base")] = {
        "action": "script.dyn",
        "tracked": ["light.x"],
        "tuning": MoodTuning(settle=5.0),
        "verify": {"mode": "off", "scene": ""},
    }
    return eng


def test_verify_off_trusts_apply_past_settle():
    eng = _off_engine()
    eng.note_requested("dyn", "base")
    _at(eng, 0.0)
    live_anything = {"light.x": ("off", {})}
    # in flight: still transitioning, never a premature active
    assert eng.decide(live_anything, now=1.0)[2] == STATUS_TRANSITIONING
    # past settle with nothing matching: trusted active (dynamic script)
    mood, preset, status, mism = eng.decide(live_anything, now=100.0)
    assert (mood, preset, status, mism) == ("dyn", "base", STATUS_ACTIVE, [])
    assert eng.verify_for("dyn", "base") == {"mode": "off", "scene": ""}


def test_verify_for_defaults_to_auto():
    eng = _two_mood_engine()
    assert eng.verify_for("mood_a", "default") == {"mode": "auto", "scene": ""}
    assert eng.verify_for("nope", "nope") == {"mode": "auto", "scene": ""}


def test_snapshot_mode_learns_then_compares():
    eng = AreaEngine(area_key="living")
    eng.targets[("m", "film")] = {
        "action": "script.film", "tracked": ["light.x"],
        "tuning": MoodTuning(settle=5.0),
        "verify": {"mode": "snapshot", "scene": ""},
    }
    assert eng.should_learn(("m", "film")) is True
    eng.note_requested("m", "film")
    _at(eng, 0.0)
    live = {"light.x": ("on", {"brightness": 77})}
    # nothing learned yet and past settle: custom (honest, not trusted)
    assert eng.decide(live, now=100.0)[2] == STATUS_CUSTOM
    eng.learn_snapshot("m", "film", live)
    assert eng.should_learn(("m", "film")) is False
    assert eng.decide(live, now=100.0)[2] == STATUS_ACTIVE
    # drift after learning: custom with the culprit listed
    drifted = {"light.x": ("on", {"brightness": 5})}
    mood, _, status, mism = eng.decide(drifted, now=100.0)
    assert (mood, status, mism) == ("custom", STATUS_CUSTOM, ["light.x"])


def test_auto_trusts_scripts_compares_scenes():
    eng = AreaEngine(area_key="living")
    eng.targets[("m", "film")] = {
        "action": "script.film", "tracked": ["light.x"],
        "tuning": MoodTuning(settle=5.0), "verify": {"mode": "auto", "scene": ""},
    }
    eng.targets[("m", "still")] = {
        "action": "scene.still", "tracked": ["light.x"],
        "tuning": MoodTuning(settle=5.0), "verify": {"mode": "auto", "scene": ""},
    }
    eng.snapshots[("m", "still")] = {"light.x": {"state": "on", "brightness": 50}}
    # script, nothing matching, past settle -> trusted active
    eng.note_requested("m", "film")
    _at(eng, 0.0)
    assert eng.decide({"light.x": ("off", {})}, now=100.0)[2] == STATUS_ACTIVE
    # scene, nothing matching, past settle -> custom (comparison applies)
    eng.note_requested("m", "still")
    _at(eng, 200.0)
    mood, _, status, mism = eng.decide({"light.x": ("off", {})}, now=300.0)
    assert (mood, status) == ("custom", STATUS_CUSTOM)
    assert mism == ["light.x"]


def test_should_learn_only_scene_auto_without_snapshot():
    eng = AreaEngine(area_key="living")
    eng.targets[("m", "film")] = {
        "action": "script.film", "tracked": [],
        "tuning": MoodTuning(), "verify": {"mode": "auto", "scene": ""},
    }
    eng.targets[("m", "still")] = {
        "action": "scene.still", "tracked": [],
        "tuning": MoodTuning(), "verify": {"mode": "auto", "scene": ""},
    }
    eng.targets[("m", "dyn")] = {
        "action": "script.dyn", "tracked": [],
        "tuning": MoodTuning(), "verify": {"mode": "off", "scene": ""},
    }
    assert eng.should_learn(("m", "film")) is False
    assert eng.should_learn(("m", "still")) is True
    assert eng.should_learn(("m", "dyn")) is False
    eng.snapshots[("m", "still")] = {"light.x": {"state": "on"}}
    assert eng.should_learn(("m", "still")) is False


def test_post_script_returns_configured_script():
    eng = _two_mood_engine()
    eng.post_actions["mood_a"] = "script.done"
    assert eng.post_script() is None  # nothing requested yet
    eng.note_requested("mood_a", "default")
    assert eng.post_script() == "script.done"
    eng.note_requested("mood_b", "default")
    assert eng.post_script() is None  # no post for mood_b
