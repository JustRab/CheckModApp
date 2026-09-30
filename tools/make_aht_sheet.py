"""Generate the AHT targets sheet a team lead keeps and CheckMod reads.

Two files come out of one recipe, which is the point: the workbook handed to
whoever publishes the week's targets, and the CSV export of its first tab,
committed as a test fixture. ``tests/test_sheets.py`` parses that fixture with
the real parser, so a change to the template that CheckMod could not read
fails the suite instead of failing in front of a team lead.

Outputs
-------
``docs/CheckMod-AHT-targets-template.xlsx``
    Upload to Google Drive, share as "anyone with the link can view", paste
    the link into Dev Mode -> Data -> AHT sheet.
``tests/data/aht-sheet-export.csv``
    The first tab as Google Sheets exports it, legend rows included.

Design notes - each of these is load-bearing for the parser in
``checkmod/sheets.py``:

* Row 1 holds the two headers it looks for: something naming the package
  ("Package") and something naming the value ("Target AHT (minutes)").
  Anything after those two columns is ignored, so extra columns are free.
* The target column asks for **whole minutes**, not ``15:00``. Google Sheets
  reads "15:00" as a time of day and exports "15:00:00"; the parser now
  recovers from that, but a sheet that cannot be misread is better than one
  that has to be.
* Cell validation on that column rejects anything but 1-240, which stops the
  clock form being typed in the first place, and its number format shows the
  unit ("15 min") without changing the stored value.
* There are deliberately **no formulas**. openpyxl writes a formula with no
  cached value, so it reads as blank to anything reading cached values until
  something recalculates the file - and a workbook with nothing to recalculate
  cannot hand a team lead a ``#NAME?``.
* The legend sits below the table in column A with the target column empty,
  because a row whose target cell holds no duration is skipped - so
  instructions can live on the same tab without being read as packages.
* The instructions tab is second. CheckMod exports whichever tab the link's
  ``gid`` names, and a link copied from the share dialog carries no gid,
  which means the first tab.

Unlike ``make_icon.py`` this needs ``openpyxl`` (``pip install openpyxl``).
It is a maintainer tool: neither the app nor CI depends on it.

Usage::

    python tools/make_aht_sheet.py
"""

import csv
import pathlib

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "CheckMod-AHT-targets-template.xlsx"
OUT_CSV = ROOT / "tests" / "data" / "aht-sheet-export.csv"

INK = "1F2933"
HEADER_BG = "1F2933"
HEADER_FG = "FFFFFF"
EDIT_BG = "FFF7D6"          # the cells the team lead fills in
LINE = "C7CED6"

ARIAL = "Arial"
thin = Side(style="thin", color=LINE)
box = Border(left=thin, right=thin, top=thin, bottom=thin)

# (package name, minutes, effective week, note)
ROWS = [
    ("Voice Chat", 15, "Week of 2026-09-27", ""),
    ("Text Chat", 10, "Week of 2026-09-27", ""),
    ("Island", 20, "Week of 2026-09-27", ""),
    ("Social Overlay", None, "", "Target not published yet"),
]

HEADERS = [
    ("Package", 24),
    ("Target AHT (minutes)", 22),
    ("Effective week", 22),
    ("Notes", 38),
]

wb = Workbook()

# ----------------------------------------------------------------------
# Sheet 1 - the one CheckMod reads. It must stay first.
# ----------------------------------------------------------------------
ws = wb.active
ws.title = "AHT Targets"
ws.sheet_view.showGridLines = False

for index, (label, width) in enumerate(HEADERS, start=1):
    cell = ws.cell(row=1, column=index, value=label)
    cell.font = Font(name=ARIAL, size=10, bold=True, color=HEADER_FG)
    cell.fill = PatternFill("solid", fgColor=HEADER_BG)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = box
    ws.column_dimensions[get_column_letter(index)].width = width
ws.row_dimensions[1].height = 32

for offset, (name, minutes, week, note) in enumerate(ROWS):
    row = 2 + offset
    for column, value in enumerate([name, minutes, week, note], start=1):
        cell = ws.cell(row=row, column=column, value=value)
        cell.font = Font(name=ARIAL, size=10)
        cell.border = box
        cell.alignment = Alignment(
            horizontal="center" if column == 2 else "left", vertical="center")
        if column == 2:
            # Yellow = the only column the team lead edits. The number format
            # spells out the unit at the point of entry, which is where the
            # "15 or 15:00?" mistake would otherwise be made. It is a display
            # format, not a formula: nothing here needs recalculating, and the
            # stored value stays the plain number 15.
            cell.fill = PatternFill("solid", fgColor=EDIT_BG)
            cell.number_format = '0" min"'
    ws.row_dimensions[row].height = 20

last = 1 + len(ROWS)
ws.freeze_panes = "A2"
ws.auto_filter.ref = f"A1:D{last}"

# Whole minutes only: this is what stops "15:00" being typed, which Sheets
# would turn into a time of day.
rule = DataValidation(
    type="whole", operator="between", formula1="1", formula2="240",
    allow_blank=True, showErrorMessage=True,
    errorTitle="Enter whole minutes",
    error="Type the number of minutes only - 15, not 15:00.\n"
          "Leave the cell empty if the target is not decided yet.",
    promptTitle="Target AHT",
    prompt="Whole minutes, 1-240. Example: 15",
    showInputMessage=True,
)
ws.add_data_validation(rule)
rule.add("B2:B200")

# Legend, well below the table. Column A only, column B left empty: CheckMod
# skips any row whose target cell does not hold a duration, so these lines
# can never be mistaken for a package.
legend = [
    "",
    "HOW TO UPDATE THIS SHEET",
    "1. Type the new target in the yellow column, in whole minutes (15, not 15:00).",
    "2. Leave a cell empty if the target is not decided yet - CheckMod keeps the old one.",
    "3. Add a row for a new package; the name must match the one in CheckMod.",
    "4. Do not rename the headers in row 1, and keep this tab first.",
    "See the 'How to use' tab for sharing and for how CheckMod reads this.",
]
for offset, text in enumerate(legend):
    row = last + 2 + offset
    cell = ws.cell(row=row, column=1, value=text)
    bold = text.isupper() and bool(text)
    cell.font = Font(name=ARIAL, size=9, bold=bold,
                     color=INK if bold else "5B6570")
    cell.alignment = Alignment(horizontal="left", vertical="center")

# ----------------------------------------------------------------------
# Sheet 2 - the instructions. CheckMod never reads this tab.
# ----------------------------------------------------------------------
guide = wb.create_sheet("How to use")
guide.sheet_view.showGridLines = False
guide.column_dimensions["A"].width = 4
guide.column_dimensions["B"].width = 104

BLOCKS = [
    ("title", "AHT targets for CheckMod"),
    ("body", "CheckMod is the moderation checklist and AHT timer the Trust & Safety "
             "agents run on their desktops. This sheet is where the week's targets "
             "live: an agent presses one button in the app and it reads the numbers "
             "from here, so nobody has to retype them."),
    ("head", "Filling it in"),
    ("body", "Only the yellow column on the 'AHT Targets' tab needs editing. "
             "Type whole minutes - 15, not 15:00."),
    ("body", "Google Sheets reads \"15:00\" as a time of day (3 p.m.) rather than a "
             "duration, which is why the sheet asks for plain minutes. CheckMod "
             "understands 15, 15 min and 900s too, so any of those is safe."),
    ("body", "An empty target cell means \"not decided yet\". CheckMod reports that "
             "row as absent and leaves the agent's current target untouched, so a "
             "blank is never read as zero."),
    ("head", "Adding or renaming a package"),
    ("body", "Add a row for a new package type. The name has to match the one in "
             "CheckMod, but spacing, punctuation and capitals do not matter - "
             "\"Voice Chat\", \"voice chat\" and \"voice_chat\" all match. A row whose "
             "name matches nothing in the app is shown to the agent as unmatched "
             "rather than ignored, which is the signal that a package was renamed."),
    ("head", "Two things to keep as they are"),
    ("body", "Keep the 'AHT Targets' tab first in the workbook, and keep the two "
             "headers in row 1 ('Package' and 'Target AHT (minutes)'). Those are how "
             "CheckMod finds the columns. Everything else - extra columns, notes, "
             "colours, filters, more rows - is yours to change."),
    ("head", "Sharing it so CheckMod can read it"),
    ("body", "Share > General access > Anyone with the link > Viewer. Then copy the "
             "link and send it to the team."),
    ("body", "View access is required because CheckMod sends no password or account "
             "with the request. A sheet restricted to named people cannot be read by "
             "the app at all - it sees Google's sign-in page and says so."),
    ("head", "What the app does with this sheet"),
    ("body", "One read, when an agent presses Sync. There is no polling and no "
             "background connection."),
    ("body", "The agent is shown what the sheet says next to their current targets, "
             "and nothing changes until they accept it."),
    ("body", "Nothing is sent to this sheet or anywhere else. CheckMod has no upload "
             "path: no handle times, no case data, no agent names. Reading is all it "
             "can do."),
    ("body", "The sheet's edit history stays the record of who changed a target and "
             "when, exactly as it is now."),
]

row = 2
for kind, text in BLOCKS:
    cell = guide.cell(row=row, column=2, value=text)
    if kind == "title":
        cell.font = Font(name=ARIAL, size=16, bold=True, color=INK)
        guide.row_dimensions[row].height = 26
    elif kind == "head":
        cell.font = Font(name=ARIAL, size=11, bold=True, color=INK)
        guide.row_dimensions[row].height = 30
    else:
        cell.font = Font(name=ARIAL, size=10, color="3E4C59")
        guide.row_dimensions[row].height = 14 * max(1, (len(text) // 96) + 1)
    cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    row += 1

guide.cell(row=row + 1, column=2,
           value="CheckMod - Iván Licea (@JustRab) - "
                 "github.com/JustRab/CheckModApp").font = Font(
    name=ARIAL, size=9, color="8A94A0")

wb.save(OUT)
print("wrote", OUT)

# ----------------------------------------------------------------------
# The same tab as Google Sheets exports it, committed as a test fixture so
# the shipped template and the parser cannot drift apart. Column C carries
# the value the formula computes.
# ----------------------------------------------------------------------
def shown(minutes):
    """The target cell as the sheet displays it, and exports it."""
    return "" if minutes is None else f"{minutes} min"


path = pathlib.Path(OUT_CSV)
path.parent.mkdir(parents=True, exist_ok=True)
with open(path, "w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow([label for label, _width in HEADERS])
    for name, minutes, week, note in ROWS:
        # Google Sheets applies the display format on export, so the target
        # column comes out as "15 min". The parser reads that and a bare "15"
        # identically; the fixture uses the formatted form because that is
        # what a real export of this template contains.
        writer.writerow([name, shown(minutes), week, note])
    for text in legend:
        writer.writerow([text, "", "", ""])
print("wrote", OUT_CSV)
