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
    assert len(app.view._mini_checks) == len(app.config.active_checks())


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
