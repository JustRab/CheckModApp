"""Tiny translation layer.

There is no gettext, no ``.po`` files and no external dependency: the whole
string table lives here so the app stays a single self-contained package and
the portable executable stays small.

Every piece of user-visible copy in the app goes through :meth:`Translator.t`.
That indirection is worth keeping even with a single language shipped,
because it gives one place to review, spell-check or rewrite the product's
wording without touching view code.

Adding a language
-----------------
1. Copy the ``"en"`` dictionary below under a new language code.
2. Translate the values (leave the keys alone).
3. Add ``("code", "Display name")`` to :data:`LANGUAGES`.

Missing keys fall back to English and then to the key itself, so a partial
translation degrades gracefully instead of crashing a view.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

#: Languages offered in the UI, in display order.
LANGUAGES: List[Tuple[str, str]] = [("en", "English")]

#: Language used when the settings file has no valid choice.
DEFAULT_LANGUAGE = "en"

STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        # --- window chrome ----------------------------------------------
        "app.tagline": "Moderation checklist & AHT",
        "tb.pin_on": "Always on top: on",
        "tb.pin_off": "Always on top: off",
        "tb.compact": "Compact mode",
        "tb.close": "Close",
        "tb.help": "Tutorial",
        "mode.user": "User Mode",
        "mode.dev": "Dev Mode",
        "mode.to_dev": "Switch to Dev Mode",
        "mode.to_user": "Back to User Mode",
        # --- user view ---------------------------------------------------
        "user.case_type": "Case type",
        "user.checklist": "Adherence checklist",
        "user.start": "Start",
        "user.pause": "Pause",
        "user.resume": "Resume",
        "user.reset": "Reset",
        "user.complete": "Complete case",
        "user.target": "Target",
        "user.idle": "Ready to start",
        "user.running": "Running",
        "user.paused": "Paused",
        "user.no_cases": "No active case types. Enable them in Dev Mode.",
        "user.no_checks": "No active checklist items.",
        "user.edit_aht": "Edit AHT target",
        "user.pending_one": "1 item left to clear",
        "user.pending_many": "{n} items left to clear",
        "user.all_clear": "All clear",
        "user.mark_all": "Check all",
        "user.clear_all": "Uncheck all",
        # --- footer ------------------------------------------------------
        "footer.today": "Today",
        "footer.cases": "cases",
        "footer.avg": "Avg AHT",
        "footer.clean": "clean",
        "footer.history_off": "History disabled",
        # --- Dev Mode sections -------------------------------------------
        "dev.appearance": "Appearance",
        "dev.window": "Window",
        "dev.cases": "Case types & AHT",
        "dev.checklist": "Checklist",
        "dev.behavior": "Behaviour",
        "dev.data": "Data & privacy",
        "dev.stats": "Statistics",
        "dev.about": "About",
        # Short forms for the section chips (4 per row, ~70 px each).
        "dev.tab.appearance": "Style",
        "dev.tab.window": "Window",
        "dev.tab.cases": "AHT",
        "dev.tab.checklist": "Checks",
        "dev.tab.behavior": "Rules",
        "dev.tab.data": "Data",
        "dev.tab.stats": "Stats",
        "dev.tab.about": "Info",
        # --- Dev Mode controls -------------------------------------------
        "dev.theme": "Theme",
        "dev.accent": "Accent colour",
        "dev.custom_color": "Custom colour",
        "dev.reset_accent": "Use the theme's own accent",
        "dev.opacity": "Opacity",
        "dev.font": "Font",
        "dev.font_scale": "Text scale",
        "dev.radius": "Corner radius",
        "dev.show_ring": "Show progress ring",
        "dev.show_footer": "Show stats bar",
        "dev.always_on_top": "Always on top",
        "dev.frameless": "Custom title bar",
        "dev.snap": "Snap to screen edges",
        "dev.snap_threshold": "Snap distance",
        "dev.remember_pos": "Remember position",
        "dev.reset_pos": "Centre window",
        "dev.auto_start": "Start timer when a type is picked",
        "dev.warn_pct": "Amber warning at",
        "dev.alert_over": "Alert when the AHT target is passed",
        "dev.sound": "Alert sound",
        "dev.confirm_reset": "Confirm before resetting",
        "dev.require_all": "Require a full checklist to complete",
        "dev.count_paused": "Count paused time",
        "dev.history_enabled": "Keep local history",
        "dev.retention": "Keep history for",
        "dev.export_csv": "Export history (CSV)",
        "dev.export_settings": "Export settings",
        "dev.import_settings": "Import settings",
        "dev.open_folder": "Open data folder",
        "dev.portable": "Portable mode (data next to the app)",
        "dev.wipe": "Erase all data",
        "dev.reset_settings": "Restore factory settings",
        "dev.add_case": "Add case type",
        "dev.add_check": "Add item",
        "dev.name": "Name",
        "dev.target": "AHT target",
        "dev.hint": "Description shown on hover",
        "dev.delete": "Delete",
        "dev.move_up": "Move up",
        "dev.move_down": "Move down",
        "dev.storage": "Storage",
        "dev.no_history": "No cases logged yet.",
        "dev.stats_today": "Today",
        "dev.stats_week": "Last 7 days",
        "dev.stats_all": "All time",
        "dev.stats_cases": "Cases",
        "dev.stats_avg": "Average AHT",
        "dev.stats_within": "Within target",
        "dev.stats_clean": "Clean checklist",
        "dev.stats_misses": "Most missed items",
        "dev.privacy_note": ("CheckMod never connects to the internet, sends no telemetry "
                             "and stores no personal data or case identifiers. Everything "
                             "lives in plain text files on this machine."),
        # --- tutorial ------------------------------------------------------
        "tut.title": "How to use CheckMod",
        "tut.next": "Next",
        "tut.prev": "Back",
        "tut.skip": "Skip",
        "tut.done": "Get started",
        "tut.1.title": "Welcome to CheckMod",
        "tut.1.body": ("A floating window that stays on top of your moderation tools. "
                       "Drag the top bar to move it anywhere on screen."),
        "tut.2.title": "1. Pick the case type",
        "tut.2.body": ("Voice Chat, Text Chat or Island. Each type carries its own AHT "
                       "target and the timer starts as soon as you pick one."),
        "tut.3.title": "2. Watch the AHT",
        "tut.3.body": ("The ring turns amber as you approach the target and red once you "
                       "pass it. Pause any time and resume without losing elapsed time."),
        "tut.4.title": "3. Clear the checklist",
        "tut.4.body": ("Tick Escalation, Enforcement, Evidence and Comment Adherence as "
                       "you verify them. Green means cleared."),
        "tut.5.title": "4. Complete the case",
        "tut.5.body": ("Complete stores the local record, resets the checklist and leaves "
                       "you ready for the next case."),
        "tut.6.title": "5. Dev Mode",
        "tut.6.body": ("Everything is configurable: themes, colours, opacity, case types, "
                       "AHT targets, checklist items and statistics. Hit DEV in the "
                       "title bar."),
        "tut.7.title": "Privacy by design",
        "tut.7.body": ("No internet, no telemetry, no installer and no admin rights. Your "
                       "data stays on this machine and one button erases it."),
        # --- dialogs -------------------------------------------------------
        "dlg.confirm": "Confirm",
        "dlg.cancel": "Cancel",
        "dlg.ok": "OK",
        "dlg.reset_q": "Reset the current case? Elapsed time and checklist will be lost.",
        "dlg.wipe_q": "This erases settings and history on this machine. Continue?",
        "dlg.reset_settings_q": "Restore every setting to its factory value?",
        "dlg.delete_case_q": "Delete the case type '{name}'?",
        "dlg.delete_check_q": "Delete the item '{name}'?",
        "dlg.require_checks": "Tick every checklist item before completing.",
        "dlg.saved": "Saved to {path}",
        "dlg.failed": "The operation could not be completed.",
        "dlg.close_q": "Close CheckMod? A case is still running.",
        # --- misc ------------------------------------------------------------
        "misc.version": "Version",
        "misc.shortcuts": "Keyboard shortcuts",
        "misc.none": "Unlimited",
        "misc.days": "days",
        "misc.auto": "auto",
    },
}


class Translator:
    """Resolve string keys for the active language.

    Views hold a reference to the shared instance and call ``app.t("key")``;
    :meth:`set_language` swaps the table in place, so a language change is a
    repaint rather than a restart.
    """

    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self.language = language if language in STRINGS else DEFAULT_LANGUAGE

    def set_language(self, language: str) -> None:
        self.language = language if language in STRINGS else DEFAULT_LANGUAGE

    def t(self, key: str, **fmt) -> str:
        """Return the localised string for ``key``, formatted with ``fmt``."""
        table = STRINGS.get(self.language, STRINGS[DEFAULT_LANGUAGE])
        text = table.get(key) or STRINGS[DEFAULT_LANGUAGE].get(key) or key
        if fmt:
            try:
                return text.format(**fmt)
            except (KeyError, IndexError, ValueError):
                return text
        return text

    #: Convenience alias so the translator can be passed around as a callable.
    __call__ = t
