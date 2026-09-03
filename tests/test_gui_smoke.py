"""End-to-end smoke tests that actually build the Tk interface.

These are skipped automatically when Tk or a display is unavailable (a bare
CI container, a headless server without Xvfb), so the pure-logic suite still
runs everywhere. On a machine with a display - or under ``xvfb-run`` - they
construct the real window, walk every Dev Mode section and every theme, and
drive a full case from selection to completion.

Their job is to catch the failure mode unit tests cannot: a view that raises
while painting.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

tkinter = pytest.importorskip("tkinter", reason="Tk is not installed")

if not sys.platform.startswith("win") and sys.platform != "darwin" and not os.environ.get("DISPLAY"):
    pytest.skip("no X display; run under xvfb-run", allow_module_level=True)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """A fully built application pointed at a throw-away data folder."""
    monkeypatch.setenv("CHECKMOD_DATA_DIR", str(tmp_path))
    from checkmod.app import App

    try:
        instance = App()
    except tkinter.TclError as error:  # pragma: no cover - broken display
        pytest.skip(f"cannot open a Tk display: {error}")
    instance.config.set("first_run", False)
    if instance.tutorial is not None:
        instance.tutorial.close()
    instance.root.update()
    yield instance
    instance.shutdown()


def test_the_window_opens_in_user_mode_and_stays_on_top(app):
    from checkmod.ui.user_view import UserView

    assert isinstance(app.view, UserView)
    assert app.config.get("always_on_top") is True
    assert app.root.winfo_width() >= 280


def test_the_window_is_tall_enough_to_show_the_complete_button(app):
    """Auto-fit guarantees no control is clipped, whatever the text scale."""
    app.root.update_idletasks()
    assert app.root.winfo_height() >= app.view.winfo_reqheight()


def test_a_full_case_runs_from_selection_to_a_logged_record(app):
    cases = app.config.active_cases()
    app.select_case(cases[0]["id"])
    app.root.update()
    assert app.session.state == "running"          # auto_start_on_select

    for item in app.config.active_checks():
        app.session.toggle_check(item["id"])
    app.view.sync()
    app.root.update()
    assert app.session.all_clear

    app.complete_case()
    app.root.update()
    rows = app.history.load()
    assert len(rows) == 1
    assert rows[0]["case_name"] == cases[0]["name"]
    assert app.session.cleared_count == 0          # ready for the next case


def test_editing_an_aht_target_updates_settings_and_the_live_session(app):
    app.select_case(app.config.active_cases()[0]["id"])
    app.update_case_target("voice", 999)
    app.root.update()
    assert app.config.case_by_id("voice")["target_s"] == 999
    assert app.session.target_s == 999


def test_every_dev_mode_section_renders(app):
    from checkmod.ui.dev_view import DevView

    app.config.set("mode", "dev")
    app._restyle_now()
    app.root.update()
    assert isinstance(app.view, DevView)

    for key, _chip, _heading in DevView.SECTIONS:
        app.view.show(key)
        app.root.update()


def test_every_theme_renders_in_both_modes(app):
    from checkmod import theme as theme_module

    for mode in ("user", "dev"):
        app.config.set("mode", mode)
        for name in theme_module.PRESETS:
            app.config.set("theme", name)
            app._restyle_now()
            app.root.update()


def test_the_compact_layout_shrinks_the_window_and_keeps_the_checks(app):
    full_height = app.root.winfo_height()
    app.toggle_compact()
    app._restyle_now()
    app.root.update()
    assert app.root.winfo_height() < full_height
    assert len(app.view._mini_checks) == len(
        app.config.active_checks(app.session.case_id))


def test_the_tutorial_walks_through_every_step_and_closes(app):
    from checkmod.ui.tutorial import STEPS

    app.show_tutorial()
    app.root.update()
    assert app.tutorial is not None
    for _ in range(len(STEPS)):
        app.tutorial.next_step()
        app.root.update()
    assert app.tutorial is None
    assert app.config.get("first_run") is False


def test_turning_off_the_custom_title_bar_still_produces_a_window(app):
    app.config.set("frameless", False)
    app.rebuild_shell()
    app.root.update()
    assert app.titlebar is None
    app.config.set("frameless", True)
    app.rebuild_shell()
    app.root.update()
    assert app.titlebar is not None


def test_adding_a_checklist_item_reaches_the_session_and_the_rows(app):
    items = [dict(item) for item in app.config.get("checklist")]
    items.append({"id": "extra", "label": "Tagging Adherence", "hint": "", "enabled": True})
    app.config.set("checklist", items)
    app.sync_checklist()
    app.root.update()
    assert "extra" in app.session.checks
    assert "extra" in app.view.checklist.rows


# ----------------------------------------------------------------------
# Regressions
# ----------------------------------------------------------------------
def test_the_title_bar_paints_across_the_full_height_of_the_bar(app):
    """The bar used to draw everything at y~0 until something forced a repaint.

    ``winfo_height()`` returns 1 before a widget is first laid out, and 1 is
    truthy, so the old ``winfo_height() or HEIGHT`` fallback never triggered
    and the title ended up crammed into the top few pixels.
    """
    app.root.update()
    bar = app.titlebar
    height = bar.handle.winfo_height()
    bbox = bar.handle.bbox("all")
    assert bbox is not None, "the title bar painted nothing"
    assert bbox[3] > height * 0.55, (
        f"title bar content stops at y={bbox[3]} in a {height}px bar - it is clipped")
    assert bbox[1] < height * 0.45, "title bar content is not vertically centred"


def test_the_title_bar_repaints_when_it_is_resized(app):
    """A <Configure> binding keeps the bar correct after any layout change."""
    app.root.update()
    app.resize_window(520, app.root.winfo_height())
    app.root.update()
    before = app.titlebar.handle.bbox("all")
    app.resize_window(300, app.root.winfo_height())
    app.root.update()
    after = app.titlebar.handle.bbox("all")
    assert before is not None and after is not None


def test_the_title_bar_grows_with_the_text_scale(app):
    """Chrome sized from font metrics, so a bigger font is never clipped."""
    from checkmod.ui.titlebar import TitleBar

    previous = 0
    for scale in (0.8, 1.0, 1.2, 1.4):
        app.config.set("font_scale", scale)
        app._restyle_now()
        app.root.update()
        bar = app.titlebar
        needed = app.fonts.height("title")
        assert bar.height >= needed + 8, (
            f"at scale {scale} the bar is {bar.height}px but the title needs {needed}px")
        assert bar.height >= previous, "bar height should grow with the text scale"
        previous = bar.height
        assert bar.height == TitleBar.height_for(app.fonts)


def test_the_tutorial_leaves_the_title_bar_reachable(app):
    """A walkthrough that covers the drag handle traps the window."""
    app.show_tutorial()
    app.root.update()
    overlay = app.tutorial
    assert overlay is not None
    # The overlay lives inside the body, not over the whole window.
    assert overlay.winfo_toplevel() is app.root
    assert overlay.winfo_rooty() >= app.titlebar.winfo_rooty() + app.titlebar.winfo_height()
    # ...and the title bar is still mapped and on screen.
    assert app.titlebar.winfo_ismapped()
    overlay.close()


def test_the_window_can_be_dragged_while_the_tutorial_is_open(app):
    """The tutorial's own header moves the window too."""
    app.root.update()
    app.show_tutorial()
    app.root.update()

    class FakeEvent:
        x_root = 400
        y_root = 300

    app.tutorial._on_drag_press(FakeEvent())
    moved = FakeEvent()
    moved.x_root, moved.y_root = 460, 340
    app.tutorial._on_drag_motion(moved)
    app.root.update()
    app.tutorial.close()


# ----------------------------------------------------------------------
# Per-case checklists, adaptive targets, undo, resize
# ----------------------------------------------------------------------
def test_evidence_adherence_is_hidden_for_voice_and_text_chat(app):
    """Only Island cases carry evidence to attach."""
    labels = {}
    for case in app.config.active_cases():
        app.select_case(case["id"])
        app.root.update()
        labels[case["id"]] = list(app.view.checklist.rows)

    assert "evidence" not in labels["voice"]
    assert "evidence" not in labels["text"]
    assert "evidence" in labels["island"]
    assert len(labels["voice"]) == 3
    assert len(labels["island"]) == 4


def test_switching_case_type_reshapes_the_live_checklist(app):
    app.select_case("island")
    app.root.update()
    assert "evidence" in app.session.checks

    app.select_case("voice")
    app.root.update()
    assert "evidence" not in app.session.checks
    assert set(app.session.checks) == {"escalation", "enforcement", "comment"}


def test_the_resize_grip_survives_shrinking_the_window_to_its_minimum(app):
    """The grip used to be squeezed to zero height, trapping the window."""
    app.root.update()
    app.resize_window(280, 10)          # ask for far less than is possible
    app.root.update()

    assert app.grip.winfo_ismapped()
    assert app.grip.winfo_height() >= 8, "the resize grip collapsed"
    assert app.grip.winfo_width() >= 8
    # ...and the window can still be grown again afterwards.
    app.resize_window(360, 620)
    app.root.update()
    assert app.root.winfo_height() > 200


def test_the_window_cannot_shrink_below_its_own_chrome(app):
    app.root.update()
    app.resize_window(300, 1)
    app.root.update()
    assert app.root.winfo_height() >= app.chrome_height()


def test_the_adaptive_target_tightens_after_a_slow_case(app):
    """A case run over budget should pull the next target down."""
    app.config.set("adaptive_target", True)
    app.config.set("adaptive_recovery_cases", 10)
    app.select_case("voice")
    base = app.config.case_by_id("voice")["target_s"]
    assert app.session.target_s == base

    # Log one case that ran 10 minutes over target.
    app.history.append({
        "ts": int(__import__("time").time()), "case_id": "voice",
        "case_name": "Voice Chat", "duration_s": base + 600, "target_s": base,
        "effective_target_s": base, "paused_s": 0, "checks": {}, "cleared": 0,
        "total_checks": 0, "within_target": False,
    })
    app.apply_adaptive_target()
    app.root.update()

    assert app.session.target_s < base
    assert app.session.base_target_s == base          # configured value survives
    # ...and it is clamped, never absurd.
    floor = base * float(app.config.get("adaptive_min_factor"))
    assert app.session.target_s >= floor


def test_turning_adaptive_targeting_off_restores_the_configured_target(app):
    base = app.config.case_by_id("voice")["target_s"]
    app.select_case("voice")
    app.history.append({
        "ts": int(__import__("time").time()), "case_id": "voice",
        "case_name": "Voice Chat", "duration_s": base + 600, "target_s": base,
        "effective_target_s": base, "paused_s": 0, "checks": {}, "cleared": 0,
        "total_checks": 0, "within_target": False,
    })
    app.config.set("adaptive_target", False)
    app.apply_adaptive_target()
    assert app.session.target_s == base


def test_undo_removes_the_last_case_and_puts_it_back_on_the_clock(app, monkeypatch):
    from checkmod.ui import dialogs

    monkeypatch.setattr(dialogs, "confirm", lambda *a, **k: True)
    app.select_case("voice")
    app.session._accumulated = 42.0
    app.session.toggle_check("escalation")
    app.complete_case()
    app.root.update()
    assert len(app.history.load()) == 1
    assert app.session.cleared_count == 0

    app.undo_last_case()
    app.root.update()
    assert app.history.load() == []
    assert app.session.case_id == "voice"
    assert round(app.session.elapsed) == 42
    assert app.session.checks["escalation"] is True


def test_undo_with_nothing_logged_is_harmless(app, monkeypatch):
    from checkmod.ui import dialogs

    seen = []
    monkeypatch.setattr(dialogs, "alert", lambda _app, message: seen.append(message))
    app.undo_last_case()
    assert seen and app.history.load() == []


def test_the_prealert_fires_once_shortly_before_the_target(app):
    app.config.set("prealert_enabled", True)
    app.config.set("prealert_seconds", 10)
    app.select_case("voice")
    app.session.start()
    app.session._accumulated = app.session.target_s - 5   # inside the window
    app.session._started_at = app.session._clock()

    assert app.session.prealert_fired is False
    app._check_prealert()
    assert app.session.prealert_fired is True

    app.session.prealert_fired = False
    app.config.set("prealert_enabled", False)
    app._check_prealert()
    assert app.session.prealert_fired is False


# ----------------------------------------------------------------------
# Layout switching must never cost the agent their work
# ----------------------------------------------------------------------
def test_switching_to_compact_and_back_preserves_the_case(app):
    """Timer, ticks and case type all survive a layout change."""
    app.select_case("voice")
    app.session._accumulated = 300.0
    app.session.toggle_check("escalation")
    app.view.sync()
    app.root.update()

    app.toggle_compact()
    app._restyle_now()
    app.root.update()
    assert app.session.case_id == "voice"
    assert round(app.session.elapsed) == 300
    assert app.session.checks["escalation"] is True

    app.toggle_compact()
    app._restyle_now()
    app.root.update()
    assert app.session.case_id == "voice"
    assert round(app.session.elapsed) == 300
    assert app.session.checks["escalation"] is True
    # ...and the rebuilt rows reflect it, not just the model.
    assert app.view.checklist.rows["escalation"].checked is True


def test_ticks_made_in_compact_survive_the_return_to_full(app):
    app.select_case("voice")
    app.toggle_compact()
    app._restyle_now()
    app.root.update()

    app.view._toggle_one("enforcement")
    app.root.update()

    app.toggle_compact()
    app._restyle_now()
    app.root.update()
    assert app.view.checklist.rows["enforcement"].checked is True


def test_the_compact_strip_is_tall_enough_for_its_content(app):
    """A fixed strip height clipped the checklist chips at larger fonts."""
    for scale in (1.0, 1.4):
        app.config.set("font_scale", scale)
        app.config.set("compact", True)
        app._restyle_now()
        app.root.update()
        needed = app.view.winfo_reqheight() + app.chrome_height()
        assert app.root.winfo_height() >= needed, (
            f"compact strip clips its content at text scale {scale}")


def test_the_compact_complete_button_is_not_labelled_ok(app):
    """"OK" reads as "dismiss"; it files the case and clears the checklist."""
    app.toggle_compact()
    app._restyle_now()
    app.root.update()
    assert app.view.btn_complete.text != "OK"
    assert app.view.btn_complete.variant == "primary"


def test_taskbar_presence_is_harmless_off_windows(app):
    """The ctypes path is Windows-only and must never raise elsewhere."""
    app.config.set("show_in_taskbar", False)
    app._apply_taskbar_presence()
    app.config.set("show_in_taskbar", True)
    app._apply_taskbar_presence()
    app.root.update()
    assert app.root.winfo_exists()


def test_the_alert_sound_is_on_by_default(app):
    assert app.config.get("sound_enabled") is True
