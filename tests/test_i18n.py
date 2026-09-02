"""Unit tests for the string table and its fallback behaviour."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checkmod.i18n import DEFAULT_LANGUAGE, LANGUAGES, STRINGS, Translator

PACKAGE = Path(__file__).resolve().parent.parent / "checkmod"


def test_default_language_is_shipped_and_listed():
    assert DEFAULT_LANGUAGE in STRINGS
    assert DEFAULT_LANGUAGE in dict(LANGUAGES)


def test_every_listed_language_has_a_string_table():
    for code, _name in LANGUAGES:
        assert code in STRINGS


def test_translation_formats_placeholders():
    translator = Translator()
    assert translator.t("user.pending_many", n=3) == "3 items left to clear"


def test_a_missing_placeholder_returns_the_raw_string_instead_of_raising():
    translator = Translator()
    assert "{n}" in translator.t("user.pending_many")


def test_an_unknown_key_returns_the_key_itself():
    assert Translator().t("does.not.exist") == "does.not.exist"


def test_an_unknown_language_falls_back_to_the_default():
    translator = Translator("klingon")
    assert translator.language == DEFAULT_LANGUAGE


def test_every_key_used_in_the_ui_exists_in_the_string_table():
    """Guards against a typo shipping as literal 'dev.tpye' text in the UI."""
    declared = set(STRINGS[DEFAULT_LANGUAGE])
    used = set()
    for path in PACKAGE.rglob("*.py"):
        if path.name == "i18n.py":
            continue
        source = path.read_text(encoding="utf-8")
        used |= set(re.findall(r'\.t\(\s*"([a-z][a-z0-9_.]*\.[a-z0-9_.]+)"', source))
        used |= set(re.findall(r'app\.t\(\s*"([a-z][a-z0-9_.]*\.[a-z0-9_.]+)"', source))

    # Keys built from tables rather than written inline.
    used |= {f"tut.{index}.{part}" for index in range(1, 8) for part in ("title", "body")}
    used |= {f"dev.tab.{name}" for name in
             ("appearance", "window", "cases", "checklist", "behavior", "data",
              "stats", "about")}
    used.discard("window.w")   # config paths, not translation keys
    used.discard("window.h")

    missing = sorted(used - declared)
    assert not missing, f"UI references untranslated keys: {missing}"
