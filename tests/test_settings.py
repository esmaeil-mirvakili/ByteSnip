"""Tests for snipapp.core.settings — defaults, get/set, persistence, edge cases."""

import pytest

from snipapp.core.settings import Settings, _deep_merge, _dict_to_toml


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_theme_default(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        assert s.get("theme") == "dark"

    def test_search_in_body_default(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        assert s.get("search_in_body") is True

    def test_run_at_login_default(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        assert s.get("run_at_login") is False

    def test_default_folder_id_is_none(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        assert s.get("default_folder_id") is None

    def test_hotkey_picker_default(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        assert s.get("hotkeys.picker") == "<cmd>+<shift>+`"

    def test_hotkey_save_default(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        assert s.get("hotkeys.save") == "<ctrl>+<cmd>+c"


# ---------------------------------------------------------------------------
# get() — key access
# ---------------------------------------------------------------------------

class TestGet:
    def test_missing_key_returns_none(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        assert s.get("nonexistent_key") is None

    def test_missing_key_returns_explicit_default(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        assert s.get("nonexistent_key", "fallback") == "fallback"

    def test_nested_key_dot_notation(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        assert s.get("hotkeys.picker") is not None

    def test_nested_missing_key_returns_default(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        assert s.get("hotkeys.nonexistent") is None

    def test_top_level_key_not_dict(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        # "theme" is a string, not a dict — nested access returns default
        assert s.get("theme.sub") is None


# ---------------------------------------------------------------------------
# set() — in-memory mutations
# ---------------------------------------------------------------------------

class TestSet:
    def test_set_top_level(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        s.set("theme", "light")
        assert s.get("theme") == "light"

    def test_set_nested_existing_key(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        s.set("hotkeys.picker", "<ctrl>+space")
        assert s.get("hotkeys.picker") == "<ctrl>+space"

    def test_set_new_nested_key(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        s.set("new_section.key", "value")
        assert s.get("new_section.key") == "value"

    def test_set_boolean_false(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        s.set("search_in_body", False)
        assert s.get("search_in_body") is False

    def test_set_integer(self, tmp_path):
        s = Settings(path=tmp_path / "c.toml")
        s.set("default_folder_id", 42)
        assert s.get("default_folder_id") == 42


# ---------------------------------------------------------------------------
# save() and reload
# ---------------------------------------------------------------------------

class TestSaveAndReload:
    def test_string_round_trips(self, tmp_path):
        path = tmp_path / "c.toml"
        s = Settings(path=path)
        s.set("theme", "light")
        s.save()
        assert Settings(path=path).get("theme") == "light"

    def test_bool_true_round_trips(self, tmp_path):
        path = tmp_path / "c.toml"
        s = Settings(path=path)
        s.set("search_in_body", True)
        s.save()
        assert Settings(path=path).get("search_in_body") is True

    def test_bool_false_round_trips(self, tmp_path):
        path = tmp_path / "c.toml"
        s = Settings(path=path)
        s.set("run_at_login", False)
        s.save()
        assert Settings(path=path).get("run_at_login") is False

    def test_nested_key_round_trips(self, tmp_path):
        path = tmp_path / "c.toml"
        s = Settings(path=path)
        s.set("hotkeys.picker", "<ctrl>+p")
        s.save()
        assert Settings(path=path).get("hotkeys.picker") == "<ctrl>+p"

    def test_unlisted_defaults_preserved_after_partial_save(self, tmp_path):
        path = tmp_path / "c.toml"
        s = Settings(path=path)
        s.set("theme", "light")
        s.save()
        s2 = Settings(path=path)
        assert s2.get("hotkeys.save") == "<ctrl>+<cmd>+c"

    def test_saved_toml_uses_lowercase_booleans(self, tmp_path):
        path = tmp_path / "c.toml"
        s = Settings(path=path)
        s.save()
        content = path.read_text()
        assert "True" not in content
        assert "False" not in content

    def test_corrupt_file_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "c.toml"
        path.write_text("this is not valid toml ][{{")
        s = Settings(path=path)
        assert s.get("theme") == "dark"


# ---------------------------------------------------------------------------
# _deep_merge helper
# ---------------------------------------------------------------------------

class TestDeepMerge:
    def test_overrides_top_level(self):
        base = {"a": 1, "b": 2}
        _deep_merge(base, {"b": 99})
        assert base["b"] == 99
        assert base["a"] == 1

    def test_merges_nested_dicts(self):
        base = {"hotkeys": {"picker": "A", "save": "B"}}
        _deep_merge(base, {"hotkeys": {"picker": "X"}})
        assert base["hotkeys"]["picker"] == "X"
        assert base["hotkeys"]["save"] == "B"

    def test_non_dict_value_replaces_dict(self):
        base = {"section": {"key": "val"}}
        _deep_merge(base, {"section": "string"})
        assert base["section"] == "string"

    def test_adds_new_keys(self):
        base = {"a": 1}
        _deep_merge(base, {"b": 2})
        assert base["b"] == 2


# ---------------------------------------------------------------------------
# _dict_to_toml helper
# ---------------------------------------------------------------------------

class TestDictToToml:
    def test_string_value(self):
        out = _dict_to_toml({"key": "value"})
        assert 'key = "value"' in out

    def test_bool_true_lowercase(self):
        out = _dict_to_toml({"flag": True})
        assert "flag = true" in out
        assert "True" not in out

    def test_bool_false_lowercase(self):
        out = _dict_to_toml({"flag": False})
        assert "flag = false" in out
        assert "False" not in out

    def test_none_becomes_comment(self):
        out = _dict_to_toml({"key": None})
        assert out.startswith("#")

    def test_nested_dict_produces_section_header(self):
        out = _dict_to_toml({"section": {"key": "val"}})
        assert "[section]" in out
        assert 'key = "val"' in out

    def test_integer_value(self):
        out = _dict_to_toml({"count": 42})
        assert "count = 42" in out
