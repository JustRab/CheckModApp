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


# ----------------------------------------------------------------------
# Clicking checklist rows must reach the session
# ----------------------------------------------------------------------
def test_clicking_a_row_records_the_tick_in_the_session(app):
    """The row used to update only its own visuals; the tick was never stored."""
    app.select_case("voice")
    app.root.update()
    row = app.view.checklist.rows["escalation"]

    row._on_click()
    app.root.update()
    assert row.checked is True
    assert app.session.checks["escalation"] is True

    row._on_click()
    app.root.update()
    assert app.session.checks["escalation"] is False


def test_ticking_rows_one_by_one_satisfies_require_all_checks(app):
    """Complete stayed disabled unless "Check all" was used."""
    app.config.set("require_all_checks", True)
    app.select_case("voice")
    app.view.sync()
    app.root.update()
    assert app.view.btn_complete.enabled is False

    for row in list(app.view.checklist.rows.values()):
        row._on_click()
    app.root.update()

    assert app.session.all_clear is True
    assert app.view.btn_complete.enabled is True


def test_checks_clicked_in_the_ui_reach_the_history_record(app):
    """Clicked ticks were being logged as false, corrupting the statistics."""
    app.select_case("voice")
    app.root.update()
    app.view.checklist.rows["escalation"]._on_click()
    app.view.checklist.rows["comment"]._on_click()
    app.root.update()

    app.complete_case()
    app.root.update()
    checks = app.history.load()[0]["checks"]
    assert checks == {"escalation": True, "enforcement": False, "comment": True}


def test_the_pending_count_follows_clicked_rows(app):
    app.select_case("voice")
    app.root.update()
    assert app.session.pending_count == 3
    app.view.checklist.rows["enforcement"]._on_click()
    app.root.update()
    assert app.session.pending_count == 2


# ----------------------------------------------------------------------
# Leaks and write amplification
# ----------------------------------------------------------------------
def test_refreshing_the_title_bar_does_not_pile_up_tooltip_bindings(app):
    """A new Tooltip per refresh left every stale one still firing."""
    app.root.update()
    button = app.titlebar.btn_pin
    before = button.bind("<Enter>")
    for _ in range(10):
        app.titlebar.refresh()
    assert button.bind("<Enter>") == before


def test_a_rebuilt_dev_view_does_not_pile_up_global_wheel_bindings(app):
    """ScrollFrame binds the wheel globally; it must release on destroy."""
    def handler_count():
        # The callback id changes with each new ScrollFrame, so count the
        # handlers rather than comparing the binding script verbatim.
        return app.root.bind_all("<MouseWheel>").count("_on_wheel")

    app.config.set("mode", "dev")
    app._restyle_now()
    app.root.update()
    before = handler_count()
    assert before >= 1, "the wheel was never bound"

    for name in ("nord", "aurora", "forest", "paper", "midnight"):
        app.config.set("theme", name)
        app._restyle_now()
        app.root.update()

    assert handler_count() == before, "global wheel handlers accumulated"


def test_dragging_a_slider_does_not_write_settings_on_every_step(app):
    """Each assignment used to rewrite settings.json and copy the backup."""
    writes = []
    real_save = app.config.save
    app.config.save = lambda: (writes.append(1), real_save())[1]

    for step in range(40):
        app.config.set("opacity", 0.60 + step * 0.005)
    assert writes == [], "settings were written mid-drag"

    # ...but the change is not lost: the debounce flushes it.
    app._flush_config()
    assert writes, "the debounced save never ran"
    app.config.save = real_save


def test_shutdown_flushes_a_pending_settings_change(app, tmp_path):
    import json

    app.config.set("opacity", 0.42)
    app.shutdown()
    with open(app.config.path, encoding="utf-8") as handle:
        assert json.load(handle)["opacity"] == 0.42


# ----------------------------------------------------------------------
# No Content (1.4.0)
# ----------------------------------------------------------------------
class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def fake_no_content(app):
    """Replace the app's cycle with one on a controllable clock."""
    from checkmod.session import NoContentCycle

    clock = FakeClock()
    app.no_content = NoContentCycle(
        clock=clock, duration_s=int(app.config.get("no_content_seconds")),
        warn_s=int(app.config.get("no_content_warn_seconds")))
    return clock


def test_the_no_content_button_is_visible_in_both_layouts(app):
    for compact in (False, True):
        app.config.set("compact", compact)
        app._restyle_now()
        app.root.update()
        panel = app.view.nocontent
        assert panel is not None, f"no No Content strip (compact={compact})"
        assert panel.winfo_ismapped()
        assert panel.btn_start.winfo_ismapped()


def test_pressing_no_content_starts_a_three_minute_countdown(app):
    app.root.update()
    assert app.config.get("no_content_seconds") == 180

    app.start_no_content()
    app.root.update()
    assert app.no_content.active is True
    assert round(app.no_content.remaining) == 180
    # The strip swaps to the two answers the moderator owes.
    panel = app.view.nocontent
    assert panel.btn_content.winfo_ismapped()
    assert panel.btn_again.winfo_ismapped()
    assert not panel.btn_start.winfo_ismapped()


def test_the_countdown_is_shown_on_screen_and_counts_down(app):
    clock = fake_no_content(app)
    app.start_no_content()
    app.root.update()
    first = app.view.nocontent.countdown.cget("text")
    clock.advance(30)
    app.view.tick()
    app.root.update()
    assert app.view.nocontent.countdown.cget("text") != first
    assert "02:30" in app.view.nocontent.countdown.cget("text")


def test_the_no_content_alerts_ignore_the_case_timer_alert_switches(app, monkeypatch):
    """Somebody who muted the AHT heads-up still pressed No Content."""
    played = []
    monkeypatch.setattr(app, "play_alert",
                        lambda kind, **kwargs: played.append(kind) or True)
    app.config.set("prealert_enabled", False)
    app.config.set("alert_on_over", False)
    clock = fake_no_content(app)
    app.start_no_content()

    clock.advance(120)
    app._check_no_content()
    clock.advance(60)
    app._check_no_content()
    assert played == ["nudge", "over"]


def test_the_calm_alert_lands_at_two_minutes_and_the_loud_one_at_three(app, monkeypatch):
    played = []
    monkeypatch.setattr(app, "play_alert",
                        lambda kind, **kwargs: played.append(kind) or True)
    clock = fake_no_content(app)
    app.start_no_content()

    clock.advance(119)
    app._check_no_content()
    assert played == []

    clock.advance(1)                       # 2:00
    app._check_no_content()
    assert played == ["nudge"]

    clock.advance(59)
    app._check_no_content()
    assert played == ["nudge"], "the loud alert came early"

    clock.advance(1)                       # 3:00
    app._check_no_content()
    assert played == ["nudge", "over"]


def test_pressing_no_content_again_restarts_the_countdown(app):
    clock = fake_no_content(app)
    app.start_no_content()
    clock.advance(170)
    app.start_no_content()
    app.root.update()
    assert round(app.no_content.remaining) == 180
    assert app.no_content.cycles == 2
    assert app.view.nocontent.note.cget("text")


def test_pressing_content_returns_the_app_to_normal(app):
    clock = fake_no_content(app)
    app.start_no_content()
    clock.advance(100)
    app.end_no_content()
    app.root.update()

    assert app.no_content.active is False
    panel = app.view.nocontent
    assert panel.btn_start.winfo_ismapped()
    assert not panel.btn_content.winfo_ismapped()


def test_the_no_content_wait_does_not_disturb_the_case_timer(app):
    """The two clocks are independent: answering a wait is not a case."""
    app.select_case("voice")
    app.session._accumulated = 90.0
    app.start_no_content()
    app.root.update()
    assert app.session.case_id == "voice"
    assert round(app.session.elapsed) >= 90
    app.end_no_content()
    app.root.update()
    assert round(app.session.elapsed) >= 90


def test_the_no_content_button_can_be_hidden(app):
    app.config.set("no_content_enabled", False)
    app._restyle_now()
    app.root.update()
    assert app.view.nocontent is None
    # ...and the tick loop still runs without it.
    app._tick()
    app.root.update()


def test_changing_the_countdown_length_reaches_the_cycle(app):
    app.config.set("no_content_seconds", 300)
    app.root.update()
    app.start_no_content()
    assert round(app.no_content.remaining) == 300
    app.end_no_content()


# ----------------------------------------------------------------------
# Alert styles (1.4.0)
# ----------------------------------------------------------------------
def test_the_configured_style_is_the_one_that_gets_played(app, monkeypatch):
    from checkmod import alerts

    seen = {}
    monkeypatch.setattr(alerts, "play",
                        lambda kind, **kwargs: seen.update(kind=kind, **kwargs) or True)
    app.config.set("alert_style", "calm")
    app.play_alert("over")
    assert seen["style"] == "calm"
    assert seen["custom_path"] is None


def test_a_custom_sound_is_validated_copied_and_selected(app, tmp_path):
    from checkmod import alerts

    source = tmp_path / "chosen.wav"
    source.write_bytes(alerts.render([(440.0, 0.2)]))

    assert app.install_custom_alert(source) == (True, "")
    assert app.config.get("alert_style") == "custom"
    stored = app.custom_alert_path()
    assert stored is not None and stored.exists()
    # Copied, not referenced: deleting the original must not break the alarm.
    source.unlink()
    assert app.custom_alert_path() is not None
    assert app.alert_style() == "custom"


def test_a_file_that_is_not_a_wav_is_rejected_with_a_reason(app, tmp_path):
    bad = tmp_path / "song.mp3"
    bad.write_bytes(b"ID3\x04not audio")
    ok, reason = app.install_custom_alert(bad)
    assert (ok, reason) == (False, "not_wav")
    assert app.config.get("alert_style") != "custom"


def test_a_custom_style_whose_file_vanished_falls_back_to_default(app):
    app.config.set("alert_style", "custom")
    app.config.set("custom_alert_file", "gone.wav")
    assert app.custom_alert_path() is None
    assert app.alert_style() == "default", "a missing file must not mean silence"


# ----------------------------------------------------------------------
# AHT sheet sync (1.4.0)
# ----------------------------------------------------------------------
SHEET_LINK = "https://docs.google.com/spreadsheets/d/TEST/edit#gid=0"


def drain(app, seconds=3.0):
    """Let the poll loop run until the sheet exchange has finished."""
    import time as _time

    deadline = _time.monotonic() + seconds
    while app._sheet_busy and _time.monotonic() < deadline:
        app.root.update()
        _time.sleep(0.02)
    app.root.update()


def test_a_sheet_sync_previews_before_it_writes_anything(app, monkeypatch):
    from checkmod import sheets
    from checkmod.ui import dialogs

    monkeypatch.setattr(sheets, "fetch",
                        lambda url: (True, "Package,Target AHT\nVoice Chat,13:00\n", ""))
    shown = {}

    def refuse(_app, rows):
        shown["rows"] = rows
        return False               # the user cancels

    monkeypatch.setattr(dialogs, "sheet_preview", refuse)
    app.config.set("aht_sheet_url", SHEET_LINK)
    app.sync_aht_from_sheet()
    drain(app)

    assert shown["rows"], "the preview was not shown"
    assert app.config.case_by_id("voice")["target_s"] == 900, "wrote without consent"


def test_accepting_the_preview_writes_the_new_targets(app, monkeypatch):
    from checkmod import sheets
    from checkmod.ui import dialogs

    monkeypatch.setattr(sheets, "fetch", lambda url: (
        True, "Package,Target AHT\nVoice Chat,13:00\nIsland,25 min\n", ""))
    monkeypatch.setattr(dialogs, "sheet_preview", lambda *a, **k: True)
    app.select_case("voice")
    app.config.set("aht_sheet_url", SHEET_LINK)

    app.sync_aht_from_sheet()
    drain(app)

    assert app.config.case_by_id("voice")["target_s"] == 780
    assert app.config.case_by_id("island")["target_s"] == 1500
    # Untouched by the sheet, so untouched here.
    assert app.config.case_by_id("text")["target_s"] == 600
    assert app.config.get("aht_sheet_last_sync") > 0


def test_a_sheet_row_with_no_matching_case_type_is_never_applied(app, monkeypatch):
    from checkmod import sheets
    from checkmod.ui import dialogs

    monkeypatch.setattr(sheets, "fetch", lambda url: (
        True, "Package,Target AHT\nGhost Queue,7:00\n", ""))
    monkeypatch.setattr(dialogs, "sheet_preview", lambda *a, **k: True)
    # Nothing matched, so the app reports "no changes" - keep that notice from
    # opening a real modal that would block the test run.
    messages = []
    monkeypatch.setattr(dialogs, "alert", lambda _app, message: messages.append(message))
    before = [dict(case) for case in app.config.get("case_types")]
    app.config.set("aht_sheet_url", SHEET_LINK)

    app.sync_aht_from_sheet()
    drain(app)
    assert app.config.get("case_types") == before
    assert messages, "the user was not told the sheet changed nothing"


def test_a_failed_sync_explains_itself_and_changes_nothing(app, monkeypatch):
    from checkmod import sheets
    from checkmod.ui import dialogs

    monkeypatch.setattr(sheets, "fetch", lambda url: (False, "", "not_shared"))
    messages = []
    monkeypatch.setattr(dialogs, "alert", lambda _app, message: messages.append(message))
    app.config.set("aht_sheet_url", SHEET_LINK)

    app.sync_aht_from_sheet()
    drain(app)

    assert messages and "shared" in messages[0].lower()
    assert app.config.case_by_id("voice")["target_s"] == 900


def test_syncing_without_a_sheet_link_asks_for_one(app, monkeypatch):
    from checkmod.ui import dialogs

    messages = []
    monkeypatch.setattr(dialogs, "alert", lambda _app, message: messages.append(message))
    app.config.set("aht_sheet_url", "")
    app.sync_aht_from_sheet()
    app.root.update()
    assert messages and "Dev Mode" in messages[0]
    assert app._sheet_busy is False


def test_a_sync_never_leaves_the_app_busy_when_the_worker_explodes(app, monkeypatch):
    from checkmod import sheets
    from checkmod.ui import dialogs

    def boom(_url):
        raise RuntimeError("something unexpected")

    monkeypatch.setattr(sheets, "fetch", boom)
    monkeypatch.setattr(dialogs, "alert", lambda *_a: None)
    app.config.set("aht_sheet_url", SHEET_LINK)
    app.sync_aht_from_sheet()
    drain(app)
    assert app._sheet_busy is False


def test_an_http_error_code_is_shown_as_a_sentence_not_a_key(app):
    text = app.sheet_error_text("http_500")
    assert "500" in text and "sheet.err" not in text
    assert "sheet.err" not in app.sheet_error_text("something_unheard_of")


def test_the_error_message_for_every_fetch_reason_is_real_copy(app):
    for reason in ("bad_url", "not_shared", "not_found", "blocked", "offline",
                   "timeout", "too_large", "no_rows"):
        text = app.sheet_error_text(reason)
        assert text and not text.startswith("sheet.")


# ----------------------------------------------------------------------
# Ranged CSV export (1.4.0)
# ----------------------------------------------------------------------
def test_the_export_asks_for_a_period_and_writes_only_that_period(app, monkeypatch, tmp_path):
    import time as _time

    from checkmod.ui import dialogs

    app.config.set("mode", "dev")
    app._restyle_now()
    app.view.show("data")
    app.root.update()

    now = _time.time()
    app.history.append({"ts": int(now), "case_id": "voice", "case_name": "Voice Chat",
                        "duration_s": 120, "target_s": 900, "paused_s": 0,
                        "checks": {}, "cleared": 0, "total_checks": 0,
                        "within_target": True})
    app.history.append({"ts": int(now - 40 * 86400), "case_id": "voice",
                        "case_name": "Voice Chat", "duration_s": 999, "target_s": 900,
                        "paused_s": 0, "checks": {}, "cleared": 0, "total_checks": 0,
                        "within_target": False})

    from checkmod.history import range_bounds

    since, until = range_bounds("today")
    target = tmp_path / "today.csv"
    monkeypatch.setattr(dialogs, "export_range", lambda *a, **k: (since, until, "Today"))
    monkeypatch.setattr(dialogs, "alert", lambda *_a: None)
    monkeypatch.setattr(app.view, "_ask_save_path", lambda *a, **k: str(target))

    app.view._export_csv()
    app.root.update()

    import csv as _csv

    with open(target, newline="", encoding="utf-8-sig") as handle:
        rows = list(_csv.DictReader(handle))
    assert [row["duration_s"] for row in rows] == ["120"]


def test_cancelling_the_period_dialog_writes_nothing(app, monkeypatch):
    from checkmod.ui import dialogs

    app.config.set("mode", "dev")
    app._restyle_now()
    app.view.show("data")
    app.root.update()

    monkeypatch.setattr(dialogs, "export_range", lambda *a, **k: None)
    asked = []
    monkeypatch.setattr(app.view, "_ask_save_path",
                        lambda *a, **k: asked.append(a) or "")
    app.view._export_csv()
    assert asked == [], "asked where to save after the export was cancelled"


def test_typing_a_sheet_link_enables_sync_without_destroying_the_field(app):
    """The commit also runs on FocusOut, so the rebuild has to be deferred."""
    app.config.set("aht_sheet_url", "")      # a team that cleared the default
    app.config.set("mode", "dev")
    app._restyle_now()
    app.view.show("data")
    app.root.update()
    assert app.view._sheet_button.enabled is False

    app.view._commit_sheet_url(SHEET_LINK)
    app.root.update()
    app.root.update_idletasks()
    app.root.update()

    assert app.config.get("aht_sheet_url") == SHEET_LINK
    assert app.view._sheet_button.enabled is True


def test_clearing_the_sheet_link_disables_sync_again(app):
    app.config.set("aht_sheet_url", SHEET_LINK)
    app.config.set("mode", "dev")
    app._restyle_now()
    app.view.show("data")
    app.root.update()
    assert app.view._sheet_button.enabled is True

    app.view._commit_sheet_url("")
    app.root.update()
    app.root.update_idletasks()
    app.root.update()
    assert app.view._sheet_button.enabled is False


def test_sync_is_ready_to_press_on_a_fresh_install(app):
    """The team's sheet ships as the default, so there is nothing to set up."""
    from checkmod.config import TEAM_AHT_SHEET_URL

    assert app.config.get("aht_sheet_url") == TEAM_AHT_SHEET_URL
    app.config.set("mode", "dev")
    app._restyle_now()
    app.view.show("data")
    app.root.update()
    assert app.view._sheet_button.enabled is True


def test_a_fresh_install_still_makes_no_request_until_sync_is_pressed(app, monkeypatch):
    """Shipping a link must not mean the app reaches out on its own."""
    from checkmod import sheets

    calls = []
    monkeypatch.setattr(sheets, "fetch",
                        lambda url: calls.append(url) or (False, "", "offline"))
    for _ in range(12):
        app._tick()                     # the loop that drives everything else
        app.root.update()
    app.select_case("voice")
    app.complete_case()
    app.start_no_content()
    app.end_no_content()
    app._restyle_now()
    app.root.update()
    assert calls == [], "something fetched the sheet without being asked"
