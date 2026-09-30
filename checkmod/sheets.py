"""Optional, opt-in read of a team AHT sheet.

Targets change from week to week, and they are published by a team lead in a
spreadsheet rather than in this app. Retyping them into Dev Mode on every
change is exactly the kind of chore that gets skipped, so this module can
read the sheet and offer the new numbers.

Everything here is deliberately narrow, because it is the *only* part of
CheckMod that touches a network:

* **Opt-in.** With no sheet URL configured nothing in this module runs, and
  :mod:`urllib` is imported inside the fetch call rather than at import time -
  so a copy of the app that was never pointed at a sheet never loads a
  networking module at all.
* **User-initiated.** There is no polling and no background thread waiting on
  a timer. A fetch happens when somebody presses Sync.
* **Read-only.** One HTTPS ``GET``. No request body, no credentials, no
  cookies, no headers carrying anything about the machine or the person; no
  history, settings or case data leaves the computer, because none of it is
  ever put into a request.
* **Host-restricted.** The URL must be a Google Sheets link, and a redirect
  is followed only to Google's own file hosts (:data:`ALLOWED_HOSTS`). A
  configured URL cannot be turned into a request to somewhere else.
* **Bounded.** A ten-second timeout and a 512 KiB read cap, so a wrong URL
  cannot hang or flood the app.
* **Preview before apply.** The parsed numbers are shown next to the current
  ones and written only when the user accepts them.

The sheet needs no add-on and no API key: it only has to be shared as
"anyone with the link can view", and this module reads the CSV that Google
already serves for such a sheet.

Sheet layout
------------
One row per package type, with a header row naming the columns. Anything
resembling "package", "case" or "type" is taken as the name column, and
anything resembling "AHT" or "target" as the value column::

    Package        Target AHT
    Voice Chat     15:00
    Text Chat      10
    Island         20 min
    Social Overlay 600s

Values are accepted as ``mm:ss``, ``hh:mm:ss``, minutes, or seconds - see
:func:`parse_duration`.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

#: Hosts a sheet fetch may talk to. ``docs.google.com`` serves the CSV;
#: ``*.googleusercontent.com`` is where it redirects the actual download.
ALLOWED_HOSTS = ("docs.google.com", "googleusercontent.com")

#: Seconds before a fetch gives up.
TIMEOUT = 10.0

#: Largest response read, in bytes. A targets sheet is a few hundred bytes;
#: this is generous and still bounded.
MAX_BYTES = 512 * 1024

#: Header words that identify the two columns of interest.
NAME_HINTS = ("package", "case", "type", "queue", "channel", "name")
VALUE_HINTS = ("aht", "target", "handle", "time", "seconds", "minutes", "goal")

#: Sanity bounds on a value read from the sheet, in seconds. A target of four
#: seconds or nine hours is a typo or a misread column, not a new policy.
MIN_SECONDS = 30
MAX_SECONDS = 4 * 3600

#: Unit suffixes accepted on a value. Anything else is not a duration, so
#: "20 packages" is ignored rather than read as twenty minutes.
SECOND_UNITS = ("s", "sec", "secs", "second", "seconds")
MINUTE_UNITS = ("m", "min", "mins", "minute", "minutes")
HOUR_UNITS = ("h", "hr", "hrs", "hour", "hours")

_SHEET_ID = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")
_GID = re.compile(r"[#&?]gid=([0-9]+)")


def host_allowed(url: str) -> bool:
    """Whether ``url`` is HTTPS on one of :data:`ALLOWED_HOSTS`."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return any(host == allowed or host.endswith("." + allowed)
               for allowed in ALLOWED_HOSTS)


def csv_url(url: str) -> Optional[str]:
    """Rewrite a Google Sheets link into its CSV export address.

    Accepts what a person actually copies out of the browser - an ``/edit``
    link, with or without a ``gid`` for a particular tab - and returns
    ``None`` for anything that is not a Google Sheets URL, which is what
    keeps this from becoming a general-purpose fetcher.
    """
    url = (url or "").strip()
    if not url or not host_allowed(url):
        return None
    match = _SHEET_ID.search(urlparse(url).path)
    if not match:
        return None
    sheet_id = match.group(1)
    export = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    gid = _GID.search(url)
    if gid:
        export += "&gid=" + gid.group(1)
    return export


def parse_duration(text: str) -> Optional[int]:
    """Read a target from a spreadsheet cell into whole seconds.

    Accepted: ``15:00`` and ``1:15:00`` (clock), ``15 min`` / ``15m``
    (minutes), ``900 s`` / ``900sec`` (seconds). A bare number is read as
    minutes up to 120 and as seconds above that, because a sheet saying
    "20" means twenty minutes while one saying "1200" means the same span in
    seconds - and no team sets a two-hour-plus target per case.

    ``15:00:00`` is read as fifteen *minutes*: Google Sheets turns a typed
    "15:00" into a time of day and exports it that way, and a fifteen-hour
    handle time is not a thing. The template in
    ``docs/CheckMod-AHT-targets-template.xlsx`` avoids the ambiguity
    entirely by asking for whole minutes.

    Returns ``None`` when the cell is empty, not a number, or outside
    :data:`MIN_SECONDS` .. :data:`MAX_SECONDS`.
    """
    raw = (text or "").strip().lower().replace(",", ".")
    if not raw:
        return None

    seconds: Optional[float] = None
    if ":" in raw:
        parts = raw.split(":")
        if len(parts) > 3:
            return None
        try:
            values = [float(part.strip() or 0) for part in parts]
        except ValueError:
            return None
        if any(value < 0 for value in values):
            return None
        seconds = 0.0
        for value in values:                      # h:m:s, m:s, or plain
            seconds = seconds * 60.0 + value
        if len(values) == 3 and seconds > MAX_SECONDS and values[2] == 0:
            # Google Sheets reads a typed "15:00" as a time of day and
            # exports it as "15:00:00". Fifteen hours is not an AHT target,
            # so a three-field value that is out of range with an empty
            # seconds field is re-read as mm:ss - which is what the person
            # who typed it meant. A genuine "1:15:00" is inside the range
            # and never reaches this branch.
            seconds = values[0] * 60.0 + values[1]
    else:
        match = re.match(r"^([0-9]*\.?[0-9]+)\s*([a-z]*)$", raw)
        if not match:
            return None
        number = float(match.group(1))
        unit = match.group(2)
        if unit in SECOND_UNITS:
            seconds = number
        elif unit in MINUTE_UNITS:
            seconds = number * 60.0
        elif unit in HOUR_UNITS:
            seconds = number * 3600.0
        elif unit:
            return None         # "20 packages" is a count, not a target
        else:
            seconds = number * 60.0 if number <= 120 else number

    if seconds is None:
        return None
    seconds = int(round(seconds))
    if seconds < MIN_SECONDS or seconds > MAX_SECONDS:
        return None
    return seconds


def _normalise(text: str) -> str:
    """Lowercase and strip everything but letters and digits, for matching."""
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _pick_columns(rows: Sequence[Sequence[str]]) -> Tuple[int, int, int]:
    """Locate the name column, the value column and the first data row.

    Falls back to "first column is the name, first parsable column is the
    value" when there is no recognisable header, so a bare two-column sheet
    still works.
    """
    for index, row in enumerate(rows[:5]):
        cells = [(_normalise(cell)) for cell in row]
        name_at = value_at = -1
        for position, cell in enumerate(cells):
            if name_at < 0 and any(hint in cell for hint in NAME_HINTS):
                name_at = position
            elif value_at < 0 and any(hint in cell for hint in VALUE_HINTS):
                value_at = position
        if name_at >= 0 and value_at >= 0:
            return name_at, value_at, index + 1

    for index, row in enumerate(rows):
        for position in range(1, len(row)):
            if parse_duration(row[position]) is not None:
                return 0, position, index
    return 0, 1, 0


def parse_csv(payload: str) -> List[Dict[str, Any]]:
    """Parse sheet CSV into ``[{"label", "seconds"}, ...]``.

    Unreadable rows are skipped rather than failing the whole sync: a sheet
    kept by a person will have a blank line, a notes row, or a "TBC" in it,
    and none of that should cost the numbers that are there.
    """
    try:
        rows = [row for row in csv.reader(io.StringIO(payload)) if any(
            (cell or "").strip() for cell in row)]
    except csv.Error:
        return []
    if not rows:
        return []

    name_at, value_at, start = _pick_columns(rows)
    found: List[Dict[str, Any]] = []
    seen = set()
    for row in rows[start:]:
        if len(row) <= max(name_at, value_at):
            continue
        label = (row[name_at] or "").strip()
        seconds = parse_duration(row[value_at])
        if not label or seconds is None:
            continue
        key = _normalise(label)
        if not key or key in seen:
            continue                              # first row for a name wins
        seen.add(key)
        found.append({"label": label, "seconds": seconds})
    return found


def match_case_types(found: Sequence[Dict[str, Any]],
                     case_types: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pair sheet rows with configured case types.

    Matching is on the case id or its display name, ignoring case, spaces and
    punctuation ("Voice Chat", "voice_chat" and "voicechat" are one thing).
    Every configured type is reported, matched or not, so the preview can say
    "no row in the sheet" instead of silently leaving a target behind.
    """
    by_key: Dict[str, Dict[str, Any]] = {}
    for entry in found:
        by_key.setdefault(_normalise(entry["label"]), entry)

    matched: List[Dict[str, Any]] = []
    used = set()
    for case in case_types:
        keys = [_normalise(case.get("id", "")), _normalise(case.get("name", ""))]
        entry = None
        for key in keys:
            if key and key in by_key:
                entry = by_key[key]
                used.add(key)
                break
        current = int(case.get("target_s", 0) or 0)
        row: Dict[str, Any] = {
            "case_id": case.get("id", ""),
            "name": case.get("name", ""),
            "current_s": current,
            "new_s": None,
            "changed": False,
            "label": entry["label"] if entry else "",
        }
        if entry is not None:
            row["new_s"] = int(entry["seconds"])
            row["changed"] = row["new_s"] != current
        matched.append(row)

    unmatched = [entry for entry in found if _normalise(entry["label"]) not in used]
    for entry in unmatched:                       # reported, never auto-added
        matched.append({
            "case_id": "",
            "name": entry["label"],
            "current_s": None,
            "new_s": int(entry["seconds"]),
            "changed": False,
            "label": entry["label"],
            "unknown": True,
        })
    return matched


def fetch(url: str) -> Tuple[bool, str, str]:
    """Download the sheet as CSV. Returns ``(ok, payload, reason)``.

    ``reason`` is a short code the interface turns into a sentence:
    ``bad_url``, ``not_shared``, ``not_found``, ``blocked``, ``offline``,
    ``timeout``, ``too_large`` or ``http_<status>``.
    """
    export = csv_url(url)
    if not export:
        return False, "", "bad_url"

    # Imported here, not at module scope: an install with no sheet URL never
    # reaches this line, so it never loads a networking module.
    import urllib.error
    import urllib.request

    class _Redirects(urllib.request.HTTPRedirectHandler):
        """Follow Google's download redirect, and nothing off Google."""

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not host_allowed(newurl):
                raise urllib.error.URLError("redirect to disallowed host")
            return urllib.request.HTTPRedirectHandler.redirect_request(
                self, req, fp, code, msg, headers, newurl)

    # No cookie handler and no proxy-auth handler: nothing stored on this
    # machine is attached to the request.
    opener = urllib.request.build_opener(_Redirects)
    request = urllib.request.Request(export, method="GET")
    request.add_header("User-Agent", "CheckMod")     # deliberately generic

    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            status = getattr(response, "status", 200) or 200
            if status != 200:
                return False, "", f"http_{status}"
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        code = getattr(error, "code", 0)
        if code in (401, 403):
            return False, "", "not_shared"
        if code == 404:
            return False, "", "not_found"
        return False, "", f"http_{code}"
    except urllib.error.URLError as error:
        text = str(getattr(error, "reason", error)).lower()
        if "disallowed" in text:
            return False, "", "blocked"
        if "timed out" in text or "timeout" in text:
            return False, "", "timeout"
        return False, "", "offline"
    except Exception:
        return False, "", "offline"

    if len(raw) > MAX_BYTES:
        return False, "", "too_large"
    payload = raw.decode("utf-8", "replace")
    if payload.lstrip()[:15].lower().startswith("<!doctype html") or \
            payload.lstrip()[:5].lower().startswith("<html"):
        # Google serves a sign-in page instead of a 403 for a private sheet.
        return False, "", "not_shared"
    return True, payload, ""


def sync(url: str, case_types: Sequence[Dict[str, Any]]
         ) -> Tuple[bool, List[Dict[str, Any]], str]:
    """Fetch and parse in one call. Returns ``(ok, rows, reason)``.

    ``rows`` is what :func:`match_case_types` produced, ready for the preview
    dialog. Nothing is written here: applying the numbers is the caller's
    decision, after the user has seen them.
    """
    ok, payload, reason = fetch(url)
    if not ok:
        return False, [], reason
    found = parse_csv(payload)
    if not found:
        return False, [], "no_rows"
    return True, match_case_types(found, case_types), ""
