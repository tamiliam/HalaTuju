"""The small readers that turn a string into the value several modules want out of it.

Two of them, both pulled together by code health H7 from copies that had drifted apart in the
usual way — not by anyone changing one, but by each being written fresh where it was needed:

  * `digits_only` was `_digits` in `vircle_airtable` and again in the Vircle CSV import. Those two
    agreed on every input either could receive; the third copy, in `offer_parse`, does NOT and is
    deliberately left where it is — see `offer_parse._decimal_digits` for why a function that
    reads OCR text cannot share this one.
  * `id_list` was `_ids`, byte-identical in four management commands, each reading a
    comma-separated list of application ids out of an environment variable.

No Django import here, and none wanted: these are string functions, and a module a `models.py`
could import without thinking about it is worth more than a tidier name.
"""


def digits_only(value) -> str:
    """Every digit in `value`, in order, as a string. `None` and a blank give `''`.

    `str()`-coerces first, so a caller holding an `int`, a `Decimal` or a database value it has
    not looked at gets an answer rather than a `TypeError`. That defensiveness is why THIS copy
    is the one that survived: the strict version was in the CSV importer, where a column may be
    absent, and a crash there loses the whole file's progress.

    Filters on `str.isdigit()`, which admits every character Unicode calls a digit — an
    Arabic-Indic `٣` and a superscript `³` alike. `offer_parse` needs the narrower
    decimal-digits-only rule and keeps its own function; the two are NOT interchangeable and
    `tests/test_helper_characterisation.py` pins the exact strings on which they disagree.
    """
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def id_list(raw) -> list:
    """A comma-separated list of row ids → a list of `int`.

    Anything that is not a run of digits is DROPPED, silently and on purpose: these read an
    environment variable an operator typed by hand before a one-off send, and a stray space or
    trailing comma must not stop the run. Note what that means for a leading minus — `'-1,2'`
    reads as `[2]`, not `[-1]` and not an error — which is right for a list of row ids and would
    be wrong for almost anything else. Do not reach for this to parse numbers.
    """
    return [int(x) for x in str(raw or '').replace(' ', '').split(',') if x.isdigit()]
