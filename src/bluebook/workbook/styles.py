"""Colour and number-format conventions shared by every sheet writer.

These are the visual signals a reader uses to judge how a cell was built:
blue = hardcoded input, black = formula computed on this sheet, green = a
link pulled in from another sheet. ``SheetWriter`` (see ``sheet.py``) is the
only place these are applied, so the convention cannot drift sheet to sheet.
"""

from __future__ import annotations

from openpyxl.styles import Font

INPUT_COLOR = "FF0000FF"
FORMULA_COLOR = "FF000000"
LINK_COLOR = "FF008000"
HEADER_COLOR = "FF000000"

INPUT_FONT = Font(color=INPUT_COLOR)
FORMULA_FONT = Font(color=FORMULA_COLOR)
LINK_FONT = Font(color=LINK_COLOR)
HEADER_FONT = Font(color=HEADER_COLOR, bold=True)
TITLE_FONT = Font(bold=True, size=14)

MONEY_FORMAT = '#,##0.0;(#,##0.0)'
PERCENT_FORMAT = '0.0%'
MULTIPLE_FORMAT = '0.0"x"'
PENCE_FORMAT = '#,##0"p"'

# Hardcoded numeric constants are permitted only on these five sheets (the
# model's inputs, transcribed reported figures, peer market data with no
# formula source, dates/identifiers, and check-formula thresholds). Every
# other sheet must contain formulas only. `SheetWriter` (sheet.py) enforces
# this at the point of writing; Task 16 imports this exact set rather than
# redefining it, so the two cannot drift.
HARDCODE_ALLOWED = {"Assumptions", "Historicals", "Comps", "Cover", "Checks"}
