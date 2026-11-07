"""CSV cells a spreadsheet cannot run — ONE home for every export (TD-515 / SEC-04, A1.9).

A cell that starts with = + - @ (or a tab / carriage return) is a formula to Excel and Sheets, and
several exported fields are typed by students themselves (name, address, school). Prefixing a `'`
makes the spreadsheet show the text instead of running it.

Moved here unchanged from `apps.scholarship.survey_results._cell` (which still answers to that name)
so the courses app's partner export can use it without a courses -> scholarship import.
"""
import csv

_FORMULA_STARTS = ('=', '+', '-', '@', '\t', '\r')


def csv_cell(value):
    """A CSV cell that a spreadsheet cannot run: a leading = + - @ (or a tab / carriage return) gets a '."""
    text = '' if value is None else str(value)
    return "'" + text if text[:1] in _FORMULA_STARTS else text


class _SafeWriter:
    """`csv.writer` whose every cell goes through `csv_cell`."""

    def __init__(self, stream):
        self._writer = csv.writer(stream)

    def writerow(self, row):
        return self._writer.writerow([csv_cell(v) for v in row])


def writer(stream):
    """A drop-in for `csv.writer(stream)` that guards every cell (only `writerow` is offered)."""
    return _SafeWriter(stream)
