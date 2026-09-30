"""Unit tests for the optional AHT sheet read.

Two things are being protected here. The first is parsing: a sheet kept by a
person has blank rows, notes columns and "20" where "20:00" was meant, and
none of that should cost the numbers that *are* there. The second is the
guard rails - this is the only part of the app that opens a socket, so the
tests pin down that it will only ever GET a Google Sheets URL, will not
follow a redirect off Google, and sends nothing about the machine.

No test here touches the network: the request path is exercised with a fake
``urllib`` opener.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checkmod import sheets

SHARE_LINK = "https://docs.google.com/spreadsheets/d/1AbC-dEf_9/edit#gid=1234567"


# ----------------------------------------------------------------------
# URL handling
# ----------------------------------------------------------------------
def test_a_share_link_becomes_a_csv_export_link():
    assert sheets.csv_url(SHARE_LINK) == (
        "https://docs.google.com/spreadsheets/d/1AbC-dEf_9/export?format=csv"
        "&gid=1234567")


def test_a_link_without_a_tab_still_exports_the_first_sheet():
    url = sheets.csv_url("https://docs.google.com/spreadsheets/d/XYZ/edit")
    assert url.endswith("/export?format=csv")


@pytest.mark.parametrize("url", [
    "",
    "not a url",
    "http://docs.google.com/spreadsheets/d/XYZ/edit",       # plain HTTP
    "https://evil.example.com/spreadsheets/d/XYZ/edit",     # wrong host
    "https://docs.google.com.attacker.net/spreadsheets/d/X/edit",
    "https://docs.google.com/document/d/XYZ/edit",          # not a sheet
    "https://drive.google.com/file/d/XYZ/view",
])
def test_anything_that_is_not_a_google_sheet_is_refused(url):
    """The configured URL cannot be turned into a request to somewhere else."""
    assert sheets.csv_url(url) is None


def test_host_allowed_accepts_googles_download_host():
    assert sheets.host_allowed("https://doc-0c-24-sheets.googleusercontent.com/x")
    assert not sheets.host_allowed("https://googleusercontent.com.evil.test/x")


# ----------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("15:00", 900),
    ("1:15:00", 4500),
    ("15 min", 900),
    ("15m", 900),
    ("15 minutes", 900),
    ("900 s", 900),
    ("900sec", 900),
    ("900 seconds", 900),
    ("20", 1200),           # a bare small number is minutes
    ("1200", 1200),         # a bare large number is already seconds
    ("12.5", 750),
    ("12,5", 750),          # a comma decimal, as European sheets write it
])
def test_targets_are_read_in_every_form_a_sheet_writes_them(text, expected):
    assert sheets.parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "TBC", "n/a", "-", "0:10", "9h",
                                  "20 packages", "1:2:3:4", "-5", "15:00:30"])
def test_a_cell_that_is_not_a_target_is_ignored(text):
    assert sheets.parse_duration(text) is None


@pytest.mark.parametrize("text,expected", [
    ("15:00:00", 900),
    ("10:00:00", 600),
    ("20:00:00", 1200),
])
def test_a_time_of_day_from_google_sheets_is_read_as_minutes(text, expected):
    """Typing "15:00" into Sheets exports as "15:00:00".

    Sheets treats it as 3 p.m. and writes all three fields. Fifteen hours is
    not a handle time, so the value is re-read as mm:ss - otherwise a sheet
    that looks perfectly correct to its author yields nothing at all.
    """
    assert sheets.parse_duration(text) == expected


def test_a_genuine_clock_duration_is_not_reinterpreted():
    """The fallback must only fire for values that cannot be real targets."""
    assert sheets.parse_duration("1:15:00") == 4500      # 1 h 15 min, in range
    assert sheets.parse_duration("0:20:00") == 1200
    assert sheets.parse_duration("3:00:00") == 3 * 3600  # implausible, but valid


def test_a_normal_sheet_parses():
    payload = (
        "Package,Target AHT,Notes\n"
        "Voice Chat,15:00,new this week\n"
        "Text Chat,10,\n"
        "Island,20 min,\n"
        "Social Overlay,600s,\n"
    )
    assert sheets.parse_csv(payload) == [
        {"label": "Voice Chat", "seconds": 900},
        {"label": "Text Chat", "seconds": 600},
        {"label": "Island", "seconds": 1200},
        {"label": "Social Overlay", "seconds": 600},
    ]


def test_a_messy_sheet_still_yields_the_rows_that_are_valid():
    payload = (
        "Week 39 targets,,\n"                 # a title row
        "Package,Target AHT,Owner\n"
        ",,\n"                                # a blank row
        "Voice Chat,15:00,Ana\n"
        "Escalations,TBC,Ana\n"               # not decided yet
        "Island,20,Ben\n"
    )
    assert sheets.parse_csv(payload) == [
        {"label": "Voice Chat", "seconds": 900},
        {"label": "Island", "seconds": 1200},
    ]


def test_a_headerless_two_column_sheet_works():
    assert sheets.parse_csv("Voice Chat,15:00\nIsland,20\n") == [
        {"label": "Voice Chat", "seconds": 900},
        {"label": "Island", "seconds": 1200},
    ]


def test_the_first_row_for_a_package_wins():
    payload = "Package,AHT\nIsland,20\nIsland,25\n"
    assert sheets.parse_csv(payload) == [{"label": "Island", "seconds": 1200}]


def test_an_empty_or_unparsable_sheet_yields_nothing():
    assert sheets.parse_csv("") == []
    assert sheets.parse_csv("just,some,words\nand,more,words\n") == []


# ----------------------------------------------------------------------
# Matching
# ----------------------------------------------------------------------
CASES = [
    {"id": "voice", "name": "Voice Chat", "target_s": 900},
    {"id": "text", "name": "Text Chat", "target_s": 600},
    {"id": "island", "name": "Island", "target_s": 1200},
]


def test_matching_reports_changed_unchanged_and_absent_rows():
    found = [{"label": "voice_chat", "seconds": 780},   # id spelling, changed
             {"label": "Island", "seconds": 1200}]      # name spelling, same
    rows = sheets.match_case_types(found, CASES)
    by_id = {row["case_id"]: row for row in rows if row["case_id"]}

    assert by_id["voice"]["new_s"] == 780 and by_id["voice"]["changed"] is True
    assert by_id["island"]["changed"] is False
    # Text Chat was not in the sheet: reported, with nothing to apply.
    assert by_id["text"]["new_s"] is None
    assert by_id["text"]["changed"] is False


def test_a_sheet_row_with_no_case_type_is_surfaced_not_silently_dropped():
    rows = sheets.match_case_types([{"label": "Ghost Queue", "seconds": 300}], CASES)
    extra = [row for row in rows if row.get("unknown")]
    assert [row["name"] for row in extra] == ["Ghost Queue"]
    # ... and it is never applied, because it has no case type to apply to.
    assert extra[0]["case_id"] == ""


# ----------------------------------------------------------------------
# The request itself
# ----------------------------------------------------------------------
class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> bool:
        return False


def fake_opener(monkeypatch, body: bytes = b"Package,AHT\nIsland,20\n",
                status: int = 200):
    """Replace ``build_opener`` and capture the request that was made."""
    import urllib.request

    seen = {}

    class Opener:
        def open(self, request, timeout=None):
            seen["url"] = request.full_url
            seen["method"] = request.get_method()
            seen["data"] = request.data
            seen["headers"] = dict(request.header_items())
            seen["timeout"] = timeout
            return FakeResponse(body, status)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **k: Opener())
    return seen


def test_the_fetch_is_a_plain_get_of_the_csv_export(monkeypatch):
    seen = fake_opener(monkeypatch)
    ok, payload, reason = sheets.fetch(SHARE_LINK)

    assert (ok, reason) == (True, "")
    assert payload.startswith("Package,AHT")
    assert seen["method"] == "GET"
    assert seen["data"] is None, "a GET must not carry a body"
    assert seen["url"] == sheets.csv_url(SHARE_LINK)
    assert seen["timeout"] == sheets.TIMEOUT


def test_the_request_says_nothing_about_the_machine_or_the_user(monkeypatch):
    """No cookies, no identifiers: the sheet cannot learn who read it."""
    seen = fake_opener(monkeypatch)
    sheets.fetch(SHARE_LINK)

    keys = {key.lower() for key in seen["headers"]}
    assert "cookie" not in keys
    assert "authorization" not in keys
    assert seen["headers"].get("User-agent") == "CheckMod"
    assert keys <= {"user-agent"}


def test_a_url_that_is_not_a_sheet_never_reaches_the_network(monkeypatch):
    seen = fake_opener(monkeypatch)
    assert sheets.fetch("https://evil.example.com/x.csv") == (False, "", "bad_url")
    assert seen == {}, "a request was made for a refused URL"


def test_a_sign_in_page_is_reported_as_a_sharing_problem(monkeypatch):
    fake_opener(monkeypatch, body=b"<!DOCTYPE html><html>Sign in</html>")
    assert sheets.fetch(SHARE_LINK)[2] == "not_shared"


def test_a_private_sheet_is_reported_as_a_sharing_problem(monkeypatch):
    import urllib.error
    import urllib.request

    class Opener:
        def open(self, request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **k: Opener())
    assert sheets.fetch(SHARE_LINK)[2] == "not_shared"


def test_no_connection_is_reported_rather_than_raised(monkeypatch):
    import urllib.error
    import urllib.request

    class Opener:
        def open(self, request, timeout=None):
            raise urllib.error.URLError("Name or service not known")

    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **k: Opener())
    assert sheets.fetch(SHARE_LINK) == (False, "", "offline")


def test_an_oversized_response_is_refused(monkeypatch):
    fake_opener(monkeypatch, body=b"x" * (sheets.MAX_BYTES + 10))
    assert sheets.fetch(SHARE_LINK)[2] == "too_large"


def test_a_redirect_away_from_google_is_blocked(monkeypatch):
    """Google redirects the export to its own file host - and only there.

    The handler is built inside ``fetch``, so it is captured from the
    ``build_opener`` call and asked to make the decision directly. That way
    the test exercises the shipped handler rather than a copy of it.
    """
    import urllib.error
    import urllib.request

    captured = {}

    class Opener:
        def open(self, request, timeout=None):
            return FakeResponse(b"Package,AHT\nIsland,20\n")

    def build_opener(*handlers, **_kwargs):
        captured["handlers"] = handlers
        return Opener()

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    sheets.fetch(SHARE_LINK)

    handler = captured["handlers"][0]()
    request = urllib.request.Request(sheets.csv_url(SHARE_LINK))
    # Google's own download host is followed...
    followed = handler.redirect_request(
        request, None, 302, "Found", {},
        "https://doc-0c-24-sheets.googleusercontent.com/pub")
    assert followed is not None
    # ... and anywhere else is refused before a second request is made.
    with pytest.raises(urllib.error.URLError):
        handler.redirect_request(request, None, 302, "Found", {},
                                 "https://evil.example.com/steal")


def test_sync_pairs_a_fetched_sheet_with_the_configured_case_types(monkeypatch):
    fake_opener(monkeypatch, body=b"Package,Target AHT\nVoice Chat,13:00\n")
    ok, rows, reason = sheets.sync(SHARE_LINK, CASES)
    assert (ok, reason) == (True, "")
    changed = [row for row in rows if row["changed"]]
    assert [(row["case_id"], row["new_s"]) for row in changed] == [("voice", 780)]


def test_sync_reports_a_sheet_with_no_targets_in_it(monkeypatch):
    fake_opener(monkeypatch, body=b"hello,world\n")
    assert sheets.sync(SHARE_LINK, CASES) == (False, [], "no_rows")


# ----------------------------------------------------------------------
# The shipped template
# ----------------------------------------------------------------------
#: ``tests/data/aht-sheet-export.csv`` is the "AHT Targets" tab of
#: ``docs/CheckMod-AHT-targets-template.xlsx`` exactly as Google Sheets
#: exports it. Both files come out of one generator, so a change to the
#: template that this parser could not read fails here.
TEMPLATE_CSV = Path(__file__).resolve().parent / "data" / "aht-sheet-export.csv"

TEMPLATE_CASES = [
    {"id": "voice", "name": "Voice Chat", "target_s": 900},
    {"id": "text", "name": "Text Chat", "target_s": 600},
    {"id": "island", "name": "Island", "target_s": 1200},
    {"id": "social", "name": "Social Overlay", "target_s": 600},
]


def template_payload() -> str:
    return TEMPLATE_CSV.read_text(encoding="utf-8")


def test_the_shipped_template_exists():
    assert TEMPLATE_CSV.is_file(), "the template's CSV export fixture is missing"


def test_the_template_exports_its_targets_with_the_unit_spelled_out():
    """The target column's number format is "15 min", and Sheets exports that.

    Worth pinning down: it means the export carries its own unit, so the
    value cannot be read as seconds by anything - including a person.
    """
    header, first = template_payload().splitlines()[:2]
    assert header.startswith("Package,Target AHT (minutes)")
    assert first == "Voice Chat,15 min,Week of 2026-09-27,"


def test_the_shipped_template_parses_to_its_three_published_targets():
    assert sheets.parse_csv(template_payload()) == [
        {"label": "Voice Chat", "seconds": 900},
        {"label": "Text Chat", "seconds": 600},
        {"label": "Island", "seconds": 1200},
    ]


def test_the_templates_instruction_lines_are_never_read_as_packages():
    """The legend sits in the same column as the package names."""
    labels = [row["label"] for row in sheets.parse_csv(template_payload())]
    assert not any(label.lower().startswith(("how to", "1.", "2.", "3.", "4.", "see "))
                   for label in labels)
    assert len(labels) == 3


def test_a_blank_target_in_the_template_leaves_that_case_type_alone():
    """Social Overlay has no published figure yet; blank must not mean zero."""
    rows = sheets.match_case_types(sheets.parse_csv(template_payload()),
                                   TEMPLATE_CASES)
    social = next(row for row in rows if row["case_id"] == "social")
    assert social["new_s"] is None
    assert social["changed"] is False


def test_every_template_row_matches_a_shipped_case_type():
    """A name in the template that the app would not recognise is a bug."""
    rows = sheets.match_case_types(sheets.parse_csv(template_payload()),
                                   TEMPLATE_CASES)
    assert not [row for row in rows if row.get("unknown")]


def test_the_template_is_understood_even_if_sheets_mangles_the_values():
    """Same table, but with the targets typed as "15:00" instead of minutes.

    Google Sheets exports those as times of day. The template asks for plain
    minutes precisely to avoid it, but a team lead who types the clock form
    anyway should still get the right numbers.
    """
    payload = template_payload()
    for minutes in (15, 10, 20):
        mangled = payload.replace(f",{minutes} min,", f",{minutes}:00:00,")
        assert mangled != payload, "the fixture no longer holds the expected form"
        payload = mangled
    assert sheets.parse_csv(payload) == [
        {"label": "Voice Chat", "seconds": 900},
        {"label": "Text Chat", "seconds": 600},
        {"label": "Island", "seconds": 1200},
    ]
