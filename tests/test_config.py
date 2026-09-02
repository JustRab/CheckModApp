"""Unit tests for settings persistence, validation and self-healing.

A settings file is something a team lead may hand-edit or copy between
machines, so the tests focus on what happens when it is wrong: truncated,
corrupt, out of range, or written by an older version.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checkmod.config import DEFAULTS, SCHEMA_VERSION, Config, new_id


def make_config(tmp_path) -> Config:
    return Config(path=tmp_path / "settings.json")


# ----------------------------------------------------------------------
# Defaults and round-tripping
# ----------------------------------------------------------------------
def test_defaults_cover_the_documented_requirements(tmp_path):
    config = make_config(tmp_path)
    names = [case["name"] for case in config.get("case_types")]
    assert names == ["Voice Chat", "Text Chat", "Island"]
    labels = [item["label"] for item in config.get("checklist")]
    assert labels == [
        "Escalation Adherence", "Enforcement Adherence",
        "Evidence Adherence", "Comment Adherence",
    ]
    assert config.get("always_on_top") is True
    assert config.get("mode") == "user"


def test_dotted_get_and_set_round_trip_through_the_file(tmp_path):
    config = make_config(tmp_path)
    config.set("window.w", 420)
    assert config.get("window.w") == 420

    reloaded = make_config(tmp_path)
    assert reloaded.get("window.w") == 420


def test_get_returns_the_default_for_an_unknown_path(tmp_path):
    config = make_config(tmp_path)
    assert config.get("nope.not.here", "fallback") == "fallback"


def test_update_applies_several_keys_with_one_notification(tmp_path):
    config = make_config(tmp_path)
    seen = []
    config.subscribe(seen.append)
    config.update({"opacity": 0.8, "theme": "nord"})
    assert config.get("opacity") == 0.8
    assert config.get("theme") == "nord"
    assert seen == ["*"]


# ----------------------------------------------------------------------
# Robustness
# ----------------------------------------------------------------------
def test_a_corrupt_settings_file_is_quarantined_not_lost(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ this is not json", encoding="utf-8")

    config = Config(path=path)
    assert config.get("theme") == DEFAULTS["theme"]      # started on defaults
    assert list(tmp_path.glob("settings.json.broken-*"))  # original preserved


def test_a_partial_file_is_merged_onto_the_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "nord"}), encoding="utf-8")

    config = Config(path=path)
    assert config.get("theme") == "nord"
    assert config.get("opacity") == DEFAULTS["opacity"]   # filled in
    assert len(config.get("checklist")) == 4


def test_out_of_range_values_are_clamped(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"opacity": 9.0, "font_scale": 0.01,
                                "window": {"w": 10, "h": 99999}}), encoding="utf-8")

    config = Config(path=path)
    assert config.get("opacity") == 1.0
    assert config.get("font_scale") == 0.8
    assert config.get("window.w") == 280
    assert config.get("window.h") == 1400


def test_malformed_case_types_are_dropped_and_never_left_empty(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"case_types": [{"nope": 1}, "garbage"]}), encoding="utf-8")

    config = Config(path=path)
    assert config.get("case_types") == DEFAULTS["case_types"]


def test_a_case_type_with_a_bad_target_falls_back_to_a_usable_value(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"case_types": [{"id": "x", "name": "X",
                                                "target_s": "banana"}]}), encoding="utf-8")

    config = Config(path=path)
    assert config.get("case_types")[0]["target_s"] == 300


def test_an_unknown_language_falls_back_to_english(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"language": "klingon"}), encoding="utf-8")
    assert Config(path=path).get("language") == "en"


def test_schema_version_is_stamped_on_load(tmp_path):
    config = make_config(tmp_path)
    assert config.get("schema") == SCHEMA_VERSION


# ----------------------------------------------------------------------
# Domain helpers
# ----------------------------------------------------------------------
def test_active_lists_hide_disabled_entries(tmp_path):
    config = make_config(tmp_path)
    cases = [dict(case) for case in config.get("case_types")]
    cases[1]["enabled"] = False
    config.set("case_types", cases)

    assert len(config.active_cases()) == 2
    assert len(config.get("case_types")) == 3   # disabled, not deleted


def test_case_by_id_finds_a_case_or_returns_none(tmp_path):
    config = make_config(tmp_path)
    assert config.case_by_id("voice")["name"] == "Voice Chat"
    assert config.case_by_id("missing") is None


def test_new_id_is_prefixed_and_unique():
    first, second = new_id("case"), new_id("case")
    assert first.startswith("case_") and first != second


# ----------------------------------------------------------------------
# Presets
# ----------------------------------------------------------------------
def test_settings_export_and_import_share_a_team_preset(tmp_path):
    source = make_config(tmp_path)
    source.set("theme", "aurora")
    source.set("accent", "#B478FF")
    preset = tmp_path / "preset.json"
    assert source.export_to(preset)

    target = Config(path=tmp_path / "other.json")
    assert target.import_from(preset)
    assert target.get("theme") == "aurora"
    assert target.get("accent") == "#B478FF"


def test_importing_a_preset_does_not_replay_the_first_run_tutorial(tmp_path):
    preset = tmp_path / "preset.json"
    preset.write_text(json.dumps({"first_run": True, "theme": "nord"}), encoding="utf-8")

    config = make_config(tmp_path)
    config.set("first_run", False)
    config.import_from(preset)
    assert config.get("first_run") is False


def test_importing_junk_is_refused_without_touching_settings(tmp_path):
    config = make_config(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    assert config.import_from(bad) is False
    assert config.get("theme") == DEFAULTS["theme"]


def test_reset_restores_factory_values_but_not_the_tutorial(tmp_path):
    config = make_config(tmp_path)
    config.set("theme", "paper")
    config.reset()
    assert config.get("theme") == DEFAULTS["theme"]
    assert config.get("first_run") is False


def test_subscribers_are_notified_and_a_broken_one_cannot_break_the_app(tmp_path):
    config = make_config(tmp_path)
    seen = []

    def explode(_key):
        raise RuntimeError("view already destroyed")

    config.subscribe(explode)
    config.subscribe(seen.append)
    config.set("theme", "nord")
    assert seen == ["theme"]
