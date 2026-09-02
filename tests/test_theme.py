"""Unit tests for the colour system.

Contrast is a real accessibility requirement here: the app runs all day next
to moderation queues, and a low-contrast accent would make the AHT ring hard
to read at a glance.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checkmod import theme as th
from checkmod.config import Config


def test_every_preset_defines_every_token():
    for name, palette in th.PRESETS.items():
        missing = [token for token in th.TOKENS if token not in palette]
        assert not missing, f"{name} is missing {missing}"


def test_every_preset_keeps_body_text_readable_on_its_background():
    for name, palette in th.PRESETS.items():
        ratio = th.contrast_ratio(palette["text"], palette["bg"])
        assert ratio >= 7.0, f"{name}: text/bg contrast is only {ratio:.1f}:1"


def test_every_preset_keeps_secondary_text_legible():
    for name, palette in th.PRESETS.items():
        ratio = th.contrast_ratio(palette["text_dim"], palette["surface"])
        assert ratio >= 4.5, f"{name}: dim text contrast is only {ratio:.1f}:1"


def test_hex_conversion_round_trips_and_accepts_shorthand():
    assert th.hex_to_rgb("#5B8CFF") == (91, 140, 255)
    assert th.hex_to_rgb("#fff") == (255, 255, 255)
    assert th.rgb_to_hex((91, 140, 255)) == "#5b8cff"


def test_mix_interpolates_between_two_colours():
    assert th.mix("#000000", "#ffffff", 0.0) == "#000000"
    assert th.mix("#000000", "#ffffff", 1.0) == "#ffffff"
    assert th.mix("#000000", "#ffffff", 0.5) == "#808080"


def test_readable_on_picks_the_higher_contrast_foreground():
    assert th.readable_on("#ffffff") == "#101418"
    assert th.readable_on("#000000") == "#FFFFFF"


def test_is_valid_hex_rejects_anything_that_is_not_a_colour():
    assert th.is_valid_hex("#abc")
    assert th.is_valid_hex("#AABBCC")
    for value in ("", "abc", "#12345", "#gggggg", None):
        assert not th.is_valid_hex(value)


def test_an_accent_override_also_picks_a_readable_foreground():
    theme = th.Theme("midnight", accent="#FFFFFF")
    assert theme["accent"] == "#FFFFFF"
    assert th.contrast_ratio(theme["accent_text"], theme["accent"]) > 4.5


def test_an_invalid_accent_is_ignored_rather_than_breaking_the_theme():
    theme = th.Theme("midnight", accent="not-a-colour")
    assert theme["accent"] == th.PRESETS["midnight"]["accent"]


def test_unknown_preset_names_fall_back_to_the_default_theme():
    assert th.Theme("does-not-exist").name == "midnight"


def test_token_overrides_win_over_the_preset(tmp_path):
    theme = th.Theme("midnight", overrides={"bg": "#123456", "bogus": "#000000"})
    assert theme["bg"] == "#123456"


def test_status_colours_map_to_the_ok_warn_danger_tokens():
    theme = th.Theme("midnight")
    assert theme.status_color("ok") == theme["ok"]
    assert theme.status_color("warn") == theme["warn"]
    assert theme.status_color("over") == theme["danger"]


def test_build_theme_reads_the_configuration(tmp_path):
    config = Config(path=tmp_path / "settings.json")
    config.set("theme", "paper")
    config.set("accent", "#B4601F")
    theme = th.build_theme(config)
    assert theme.name == "paper" and theme["accent"] == "#B4601F"
