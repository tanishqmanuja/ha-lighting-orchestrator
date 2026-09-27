"""Resolution tests: bare mood requests land on the designated default."""
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


_const = _load("halo_res_const", "const.py")
_matcher = _load("halo_res_matcher", "matcher.py")
sys.modules["const"] = _const
sys.modules["matcher"] = _matcher
_engine = _load("halo_res_engine", "engine.py")

PRESET_NONE = _const.PRESET_NONE
AreaEngine = _engine.AreaEngine
MoodTuning = _engine.MoodTuning
normalize_mood_cfg = _const.normalize_mood_cfg


def _party_engine():
    eng = AreaEngine(area_key="living")
    eng.targets[("party", "default")] = {"action": "scene.pd", "tracked": [],
                                         "tuning": MoodTuning()}
    eng.targets[("party", "wild")] = {"action": "scene.pw", "tracked": [],
                                      "tuning": MoodTuning()}
    eng.defaults["party"] = "wild"
    return eng


def test_default_preset_for_prefers_designated():
    assert _party_engine().default_preset_for("party") == "wild"


def test_default_preset_for_falls_back_to_default_name():
    eng = AreaEngine(area_key="living")
    eng.targets[("m", "default")] = {"action": "s", "tracked": [],
                                     "tuning": MoodTuning()}
    eng.targets[("m", "bright")] = {"action": "s", "tracked": [],
                                    "tuning": MoodTuning()}
    assert eng.default_preset_for("m") == "default"


def test_resolve_preset_empty_and_none():
    eng = _party_engine()
    assert eng.resolve_preset("party", None) == "wild"
    assert eng.resolve_preset("party", "") == "wild"
    assert eng.resolve_preset("party", PRESET_NONE) == "wild"
    assert eng.resolve_preset("party", "default") == "default"


def test_resolve_preset_unknown_passes_through():
    eng = _party_engine()
    assert eng.resolve_preset("party", "typo") == "typo"


def test_normalize_migrates_legacy_mood_action():
    mcfg = normalize_mood_cfg({"presets": {}, "action": "scene.old"})
    assert mcfg["presets"] == {"base": {"action": "scene.old"}}
    assert mcfg["default_preset"] == "base"
    assert "action" not in mcfg


def test_normalize_keeps_presets_and_default():
    mcfg = normalize_mood_cfg(
        {"presets": {"default": {"action": "a"}, "party": {"action": "b"}},
         "default_preset": "party"}
    )
    assert mcfg["default_preset"] == "party"


def test_normalize_repairs_unknown_default():
    mcfg = normalize_mood_cfg(
        {"presets": {"default": {"action": "a"}}, "default_preset": "gone"}
    )
    assert mcfg["default_preset"] == "default"


def test_pick_default_preset_chain():
    pick = _const.pick_default_preset
    assert pick({"base": 1, "bright": 1}, "bright") == "bright"
    assert pick({"base": 1, "bright": 1}) == "base"
    assert pick({"default": 1, "bright": 1}) == "default"
    assert pick({"x": 1, "y": 1}) == "x"
    assert pick({}) == "base"


def test_normalize_verify_forms():
    norm = _const.normalize_verify
    assert norm("off") == {"mode": "off", "scene": ""}
    assert norm("snapshot") == {"mode": "snapshot", "scene": ""}
    assert norm("scene.foo") == {"mode": "scene", "scene": "scene.foo"}
    assert norm("") == {"mode": "auto", "scene": ""}
    assert norm("garbage") == {"mode": "auto", "scene": ""}
    # stored dicts round-trip
    assert norm({"mode": "off", "scene": "scene.x"}) == {"mode": "off", "scene": ""}
    assert norm({"mode": "scene", "scene": "scene.x"}) == {
        "mode": "scene",
        "scene": "scene.x",
    }
    assert norm({"mode": "scene", "scene": "nope"}) == {"mode": "auto", "scene": ""}
