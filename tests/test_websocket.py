"""Unit tests for the websocket config API (no HA needed)."""
import asyncio
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


_const = _load("halo_ws_const", "const.py")
sys.modules["const"] = _const
ws = _load("halo_ws_mod", "websocket.py")


def test_validate_ok_with_presets():
    cfg = ws.validate_mood_payload(
        {
            "presets": {"default": "scene.a", "bright": "script.b"},
            "default_preset": "bright",
            "tracked_entities": "light.x, light.y",
            "transition": 1.5,
            "ignore_unavailable": False,
        }
    )
    assert cfg["presets"] == {
        "default": {"action": "scene.a",
                    "verify": {"mode": "auto", "scene": ""}},
        "bright": {"action": "script.b",
                   "verify": {"mode": "auto", "scene": ""}},
    }
    assert cfg["default_preset"] == "bright"
    assert cfg["tracked_entities"] == ["light.x", "light.y"]
    assert cfg["transition"] == 1.5
    assert cfg["ignore_unavailable"] is False


def test_validate_defaults_default_preset():
    cfg = ws.validate_mood_payload({"presets": {"party": "scene.p"}})
    assert cfg["default_preset"] == "party"
    legacy = ws.validate_mood_payload(
        {"presets": {"bright": "scene.b", "default": "scene.a"}}
    )
    assert legacy["default_preset"] == "default"


def test_validate_rejects_unknown_default_preset():
    try:
        ws.validate_mood_payload(
            {"presets": {"default": "scene.a"}, "default_preset": "party"}
        )
    except ValueError as err:
        assert "must be one of" in str(err)
    else:
        raise AssertionError("expected ValueError")


def test_validate_zero_presets_rejected():
    try:
        ws.validate_mood_payload({"presets": {}})
    except ValueError as err:
        assert "at least one preset" in str(err)
    else:
        raise AssertionError("expected ValueError")


def test_validate_rejects_bad_action():
    try:
        ws.validate_mood_payload({"presets": {"default": "light.x"}})
    except ValueError as err:
        assert "scene.x or script.y" in str(err)
    else:
        raise AssertionError("expected ValueError")


def test_validate_rejects_bad_tracked():
    try:
        ws.validate_mood_payload(
            {"presets": {"default": "scene.a"}, "tracked_entities": ["nope"]}
        )
    except ValueError as err:
        assert "entity ids" in str(err)
    else:
        raise AssertionError("expected ValueError")


def test_validate_mood_name():
    assert ws.validate_mood_name(" Evening-1 ") == "Evening-1"
    for bad in ["", "a/b", "x" * 65]:
        try:
            ws.validate_mood_name(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad!r}")


class _Entry:
    def __init__(self):
        self.data = {"area_id": "living_room", "area_name": "Living",
                     "moods": {"evening": {"presets": {"default": {"action": "scene.a"}}}}}
        self.options = {}


class _Engine:
    def __init__(self):
        self.snapshots = {}


class _Area:
    def __init__(self):
        self.area_key = "living_room"
        self.area_name = "Living"
        self.lock_entity = None
        self.entry = _Entry()
        self.engine = _Engine()
        self.saved = 0

    async def _save(self):
        self.saved += 1


class _States:
    def get(self, eid):
        return object() if eid == "scene.a" else None


class _ConfigEntries:
    def __init__(self):
        self.saved = []

    def async_update_entry(self, entry, options):
        self.saved.append(options)


class _Hass:
    def __init__(self):
        self.data = {"halo": {"eid1": _Area()}}
        self.states = _States()
        self.config_entries = _ConfigEntries()

    def async_create_task(self, coro):
        asyncio.run(coro)
        return coro


class _Conn:
    def __init__(self, admin=True):
        self.user = type("U", (), {"is_admin": admin})()
        self.results = {}
        self.errors = {}

    def send_result(self, _id, payload):
        self.results[_id] = payload

    def send_error(self, _id, code, message):
        self.errors[_id] = (code, message)


def test_get_serializes_area():
    conn = _Conn()
    ws._handle_get(_Hass(), conn, {"id": 1, "area": "living_room"})
    moods = conn.results[1]["moods"]
    assert moods["evening"]["presets"] == {
        "default": {"action": "scene.a", "verify": "auto"}
    }


def test_set_mood_persists_and_warns_missing():
    hass = _Hass()
    conn = _Conn()
    ws._handle_set_mood(
        hass, conn,
        {"id": 2, "area": "living_room", "mood": "movie",
         "config": {"presets": {"default": "script.gone"},
                    "default_preset": "default"}},
    )
    assert conn.results[2]["saved"] == "movie"
    assert conn.results[2]["missing_actions"] == ["script.gone"]
    assert "movie" in hass.config_entries.saved[0]["moods"]


def test_set_mood_rejects_non_admin_and_bad_payload():
    conn = _Conn(admin=False)
    ws._require_admin(ws._handle_get)(_Hass(), conn, {"id": 3, "area": "living_room"})
    assert conn.errors[3][0] == "unauthorized"
    conn2 = _Conn()
    ws._handle_set_mood(
        _Hass(), conn2,
        {"id": 4, "area": "living_room", "mood": "ok",
         "config": {"presets": {"x": "bogus"}}},
    )
    assert conn2.errors[4][0] == "invalid_format"


def test_delete_mood():
    hass = _Hass()
    area = hass.data["halo"]["eid1"]
    area.engine.snapshots[("evening", "base")] = {"light.x": {"state": "on"}}
    area.engine.snapshots[("other", "base")] = {"light.y": {"state": "on"}}
    conn = _Conn()
    ws._handle_delete_mood(
        hass, conn, {"id": 5, "area": "living_room", "mood": "evening"}
    )
    assert conn.results[5] == {"deleted": "evening"}
    assert "evening" not in hass.config_entries.saved[0]["moods"]
    # its snapshots go with it; other moods keep theirs; storage persisted
    assert ("evening", "base") not in area.engine.snapshots
    assert ("other", "base") in area.engine.snapshots
    assert area.saved == 1


def _write_scenes(tmp_path, docs):
    import yaml

    p = tmp_path / "scenes.yaml"
    p.write_text(yaml.safe_dump(docs), encoding="utf-8")
    return str(p)


def test_scene_entities_from_yaml(tmp_path):
    path = _write_scenes(
        tmp_path,
        [
            {"id": "evening_base", "name": "Evening Base",
             "entities": {"light.a": {"state": "on"}, "light.b": {"state": "off"}}},
            {"id": "other", "name": "Other",
             "entities": {"light.c": {"state": "on"}}},
        ],
    )
    assert ws.scene_entities_from_yaml(path, "evening_base") == ["light.a", "light.b"]
    # name-slug matching too
    assert ws.scene_entities_from_yaml(path, "other") == ["light.c"]
    assert ws.scene_entities_from_yaml(path, "missing") == []
    assert ws.scene_entities_from_yaml(str(tmp_path / "nope.yaml"), "x") == []


def test_suggest_tracked_unions_scenes_skips_scripts(tmp_path):
    path = _write_scenes(
        tmp_path,
        [
            {"id": "one", "name": "One", "entities": {"light.a": {}}},
            {"id": "two", "name": "Two", "entities": {"light.b": {}, "light.a": {}}},
        ],
    )

    class _Cfg:
        def path(self, _name):
            return path

    class _H:
        config = _Cfg()

    assert ws.suggest_tracked_entities(_H(), ["scene.one", "scene.two", "script.x"]) == [
        "light.a",
        "light.b",
    ]
    assert ws.suggest_tracked_entities(_H(), ["script.x"]) == []


def test_suggest_handler_validates_area():
    conn = _Conn()
    ws._handle_suggest(_Hass(), conn, {"id": 6, "area": "nope", "actions": []})
    assert conn.errors[6][0] == "not_found"


def test_suggest_handler_answers_from_task(tmp_path):
    import asyncio as _asyncio

    path = _write_scenes(
        tmp_path,
        [{"id": "one", "name": "One", "entities": {"light.a": {}}}],
    )

    class _Cfg:
        def path(self, _name):
            return path

    class _HassSuggest(_Hass):
        def __init__(self):
            super().__init__()
            self.config = _Cfg()
            self.tasks = []

        def async_create_task(self, coro):
            self.tasks.append(coro)
            return coro

        async def async_add_executor_job(self, func, *args):
            return func(*args)

    hass = _HassSuggest()
    conn = _Conn()
    ws._handle_suggest(
        hass, conn,
        {"id": 7, "area": "living_room", "actions": ["scene.one"]},
    )
    assert len(hass.tasks) == 1
    _asyncio.run(hass.tasks[0])
    assert conn.results[7] == {"entities": ["light.a"]}


def test_validate_post_action():
    cfg = ws.validate_mood_payload(
        {"presets": {"base": "scene.a"}, "post_action": "script.done"}
    )
    assert cfg["post_action"] == "script.done"
    for bad in ["light.x", "scene.a", "script with space"]:
        try:
            ws.validate_mood_payload(
                {"presets": {"base": "scene.a"}, "post_action": bad}
            )
        except ValueError as err:
            assert "post script" in str(err)
        else:
            raise AssertionError(f"expected ValueError for {bad!r}")


def test_serialize_includes_post_action():
    area = _Area()
    area.entry.data = {
        "area_id": "living_room",
        "area_name": "Living",
        "moods": {
            "evening": {
                "presets": {"base": {"action": "scene.a"}},
                "default_preset": "base",
                "post_action": "script.done",
            }
        },
    }
    moods = ws.serialize_area(area)["moods"]
    assert moods["evening"]["post_action"] == "script.done"


def test_validate_verify_forms():
    cfg = ws.validate_mood_payload(
        {"presets": {
            "dyn": {"action": "script.d", "verify": "off"},
            "ref": {"action": "script.r", "verify": "scene.s"},
        }}
    )
    assert cfg["presets"]["dyn"]["verify"] == {"mode": "off", "scene": ""}
    assert cfg["presets"]["ref"]["verify"] == {"mode": "scene", "scene": "scene.s"}
    snap = ws.validate_mood_payload(
        {"presets": {"x": {"action": "script.x", "verify": "snapshot"}}}
    )
    assert snap["presets"]["x"]["verify"] == {"mode": "snapshot", "scene": ""}
    try:
        ws.validate_mood_payload(
            {"presets": {"x": {"action": "script.x", "verify": "sometimes"}}}
        )
    except ValueError as err:
        assert "verify must be" in str(err)
    else:
        raise AssertionError("expected ValueError")


def test_validate_drops_blank_preset_rows():
    cfg = ws.validate_mood_payload(
        {"presets": {"default": "scene.a", "": ""}, "default_preset": "default"}
    )
    assert cfg["presets"] == {
        "default": {"action": "scene.a",
                    "verify": {"mode": "auto", "scene": ""}}
    }
