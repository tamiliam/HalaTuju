"""LL5 phase C2 - the ALLOW-LIST the coach grade's result must pass before the `new` child writes it to
`child.COACH_GRADE_FILE`, and again after the parent reads it back. That file skips the scrubber, so this
check stands in for it: a change to `coach_grade` or to `coach_rows` must never be able to put a case id,
a name, a reason text or any free text in it.

THE RULE. Every dict has exactly one of a few fixed key sets for its level (a key that is unknown OR
missing fails). The result is one of three shapes: the report (`TOP_KEYS`), the DEBUG refusal
(``{"refusal": "debug_on"}``) or an error (``{"error": <code in COACH_FILE_ERROR_CODES>}``). Anything else: the
whole result becomes exactly ``{"error": "schema"}``, with nothing of the bad result in it. The checker
walks only known keys of a fixed depth, so it never recurses into what it does not know.

Ints are ``type(v) is int`` (a bool or a float is NOT an int): every count, ``points``, ``best``,
``score_pct`` (`ai_score.percent` gives an int; a shown line always has ``best`` > 0, so it is never
None here), ``left_out``, ``skipped_versions`` and the ``count`` / ``of`` pairs. Fixed codes come from
`coach_grade`'s and `fail_reasons`'s public constants: ``grade`` (`coach_grade.GRADES`), ``reasons``
(`coach_grade.REASON_CODES`, one or more, no repeat), ``left_out_reasons`` (`fail_reasons.CODES`, sorted,
no repeat), the ``outcomes`` keys (exactly `ai_score.OUTCOMES`), ``refusal`` (`lens_human.DEBUG_ON`) and
``error`` (`COACH_FILE_ERROR_CODES`).

EVERY VALUE THAT IS NOT AN INT OR A FIXED CODE, with its rule:
* ``version`` of a month cell: with ``unknown_version`` False, the verdict engine's version shape
  (`lens_result_schema.engine_version_ok`: ``YYYY-MM-DD.N``, at most 14 characters); with it True, exactly
  `coach_grade.UNKNOWN_VERSION` or `verdict_engine.PRE_VERSIONING`.
* ``version`` of a side (``coach`` pairs and ``waiting``): known versions only, so the engine version shape.
* ``month``: `MONTH_SHAPE`, ``YYYY-MM`` with a real month (01 to 12).
* ``cell_min_facts``, ``coach_min_facts``, ``score_z``: ints that must EQUAL `coach_grade`'s constants;
  ``guard_alpha``: ``{count, of}`` that must equal `coach_grade.GUARD_ALPHA`'s numerator and denominator.
* the KEYS of ``malformed_by_error`` (`malformed_kind_ok`, the ONE predicate; `coach_rows` uses it too):
  one of `coach_grade.MALFORMED_LABELS`, or `coach_grade.OTHER_ERROR`, or an error class name: `ERROR_NAME_SHAPE`
  (``[A-Z][A-Za-z0-9]{0,59}``: a capital, then ASCII letters and digits, at most 60 characters) that ends
  in ``Error`` or ``Exception``. Any other key fails the whole result. The values are ints that add up to
  ``malformed_records``. Before this check, the reader (`coach_rows.fold_odd_kinds`) moves the count of
  any key of another form into ``other_error``, so a real but oddly named class never fails the run.
  Known limit: a class name could still spell a short word ending in ``Error``.
* true / false: ``unknown_version`` (a cell) and ``too_few`` (a cell, a side, a ``without_left_out``
  line), each tied to its block's own shape (too few = the short key set).
* None: nowhere. The report never holds None; a field it does not fill is simply absent from the short
  key set.
* ``without_left_out``: present in every shown cell and side exactly when ``left_out_reasons`` is not
  empty, absent otherwise.
"""
from __future__ import annotations

import json
import re

from . import lens_human as L
from .lens_result_schema import BAD_OUTPUT, MAX_RESULT_BYTES, NO_OUTPUT, SCHEMA, engine_version_ok

__all__ = ('SCHEMA', 'NO_OUTPUT', 'BAD_OUTPUT', 'MAX_RESULT_BYTES')

COACH_SCHEMA_TEXT = json.dumps({'error': SCHEMA})
#: A caught coach-reader error is recorded by the NEAREST of these classes (a KeyError as LookupError).
COACH_ERROR_CLASSES = (ValueError, TypeError, LookupError)
#: The only error codes the coach file may hold (the child writes them); the parent adds NO_OUTPUT and
#: BAD_OUTPUT itself, never from the file.
COACH_FILE_ERROR_CODES = frozenset({SCHEMA, *(c.__name__ for c in COACH_ERROR_CLASSES)})

TOP_KEYS = frozenset({'cell_min_facts', 'coach_min_facts', 'guard_alpha', 'score_z', 'left_out_reasons',
                      'decided_records', 'malformed_records', 'malformed_by_error', 'versions_without_marks',
                      'months', 'coach', 'waiting'})
ERROR_KEYS = frozenset({'error'})
REFUSAL_KEYS = frozenset({'refusal'})
CELL_SMALL_KEYS = frozenset({'version', 'unknown_version', 'month', 'too_few'})
CELL_KEYS = CELL_SMALL_KEYS | {'facts', 'points', 'best', 'score_pct', 'not_scored', 'outcomes'}
SIDE_SMALL_KEYS = frozenset({'version', 'too_few'})
SIDE_KEYS = SIDE_SMALL_KEYS | {'facts', 'score_pct', 'coverage', 'generous_wrong'}
LINE_SMALL_KEYS = frozenset({'too_few'})
LINE_KEYS = LINE_SMALL_KEYS | {'facts', 'points', 'best', 'score_pct', 'left_out'}
PAIR_KEYS = frozenset({'previous', 'new', 'grade', 'reasons', 'skipped_versions'})
COUNT_OF_KEYS = frozenset({'count', 'of'})
EXTRA_LINE = 'without_left_out'
MONTH_SHAPE = re.compile(r'[0-9]{4}-(0[1-9]|1[0-2])', re.ASCII)
#: An error class name kind of ``malformed_by_error``: this shape (whole text) and one of these endings.
ERROR_NAME_SHAPE = re.compile(r'[A-Z][A-Za-z0-9]{0,59}', re.ASCII)
ERROR_NAME_ENDINGS = ('Error', 'Exception')


def coach_error_name(exc) -> str:
    """The nearest `COACH_ERROR_CLASSES` name of a caught coach-reader error (`SCHEMA` for any other)."""
    return next((k.__name__ for k in type(exc).__mro__ if k in COACH_ERROR_CLASSES), SCHEMA)


def malformed_kind_ok(kind) -> bool:
    """True only for a ``malformed_by_error`` key of the three allowed forms: one of
    `coach_grade.MALFORMED_LABELS`, `coach_grade.OTHER_ERROR`, or an error class name (the whole text
    matches `ERROR_NAME_SHAPE` and ends in one of `ERROR_NAME_ENDINGS`). Only real text counts."""
    from apps.scholarship import coach_grade
    if type(kind) is not str:
        return False
    if kind in coach_grade.MALFORMED_LABELS or kind == coach_grade.OTHER_ERROR:
        return True
    return ERROR_NAME_SHAPE.fullmatch(kind) is not None and kind.endswith(ERROR_NAME_ENDINGS)


def _is_whole(value) -> bool:
    return type(value) is int


def _keys(value, *key_sets) -> bool:
    return type(value) is dict and frozenset(value) in key_sets


def _ints(value, keys) -> bool:
    return _keys(value, frozenset(keys)) and all(_is_whole(v) for v in value.values())


def _codes():
    """The fixed sets, from the modules' own public constants (imported here: light at import time)."""
    from apps.scholarship import ai_score, coach_grade, fail_reasons
    from apps.scholarship.verdict_engine import PRE_VERSIONING
    return {'outcomes': frozenset(ai_score.OUTCOMES), 'grades': frozenset(coach_grade.GRADES),
            'reasons': frozenset(coach_grade.REASON_CODES), 'fail_reasons': frozenset(fail_reasons.CODES),
            'unknown': frozenset({coach_grade.UNKNOWN_VERSION, PRE_VERSIONING}),
            'constants': {'cell_min_facts': coach_grade.CELL_MIN_FACTS,
                          'coach_min_facts': coach_grade.COACH_MIN_FACTS, 'score_z': coach_grade.SCORE_Z},
            'guard_alpha': {'count': coach_grade.GUARD_ALPHA.numerator,
                            'of': coach_grade.GUARD_ALPHA.denominator}}


def _code_list(value, allowed, *, empty_ok, in_order) -> bool:
    if type(value) is not list or (not value and not empty_ok):
        return False
    if not all(type(v) is str and v in allowed for v in value) or len(set(value)) != len(value):
        return False
    return not in_order or value == sorted(value)


def _line_ok(line) -> bool:
    if not _keys(line, LINE_SMALL_KEYS, LINE_KEYS) or line['too_few'] is not (frozenset(line) == LINE_SMALL_KEYS):
        return False
    return all(_is_whole(line[k]) for k in LINE_KEYS - LINE_SMALL_KEYS if k in line)


def _shown_ok(block, small, full, extra) -> bool:
    """The short key set (too few) or the full one, plus the extra line exactly when one is asked for."""
    keys = frozenset(block) if type(block) is dict else None
    if keys is None:
        return False
    if keys == small:
        return block['too_few'] is True
    if keys != (full | {EXTRA_LINE} if extra else full) or block['too_few'] is not False:
        return False
    return not extra or _line_ok(block[EXTRA_LINE])


def _cell_ok(cell, codes, extra) -> bool:
    if not _shown_ok(cell, CELL_SMALL_KEYS, CELL_KEYS, extra):
        return False
    version, unknown, month = cell['version'], cell['unknown_version'], cell['month']
    if unknown is True:
        version_ok = type(version) is str and version in codes['unknown']
    else:
        version_ok = unknown is False and engine_version_ok(version)
    if not (version_ok and type(month) is str and MONTH_SHAPE.fullmatch(month)):
        return False
    if cell['too_few']:
        return True
    return (all(_is_whole(cell[k]) for k in ('facts', 'points', 'best', 'score_pct', 'not_scored'))
            and _ints(cell['outcomes'], codes['outcomes']))


def _side_ok(side, extra) -> bool:
    if not _shown_ok(side, SIDE_SMALL_KEYS, SIDE_KEYS, extra) or not engine_version_ok(side['version']):
        return False
    if side['too_few']:
        return True
    return (_is_whole(side['facts']) and _is_whole(side['score_pct']) and _ints(side['coverage'], COUNT_OF_KEYS)
            and _ints(side['generous_wrong'], COUNT_OF_KEYS))


def _pair_ok(pair, codes, extra) -> bool:
    return (_keys(pair, PAIR_KEYS) and _side_ok(pair['previous'], extra) and _side_ok(pair['new'], extra)
            and type(pair['grade']) is str and pair['grade'] in codes['grades']
            and _code_list(pair['reasons'], codes['reasons'], empty_ok=False, in_order=False)
            and _is_whole(pair['skipped_versions']))


def _report_ok(report, codes) -> bool:
    if any(report[k] != v or not _is_whole(report[k]) for k, v in codes['constants'].items()):
        return False
    if not _ints(report['guard_alpha'], COUNT_OF_KEYS) or report['guard_alpha'] != codes['guard_alpha']:
        return False
    if not all(_is_whole(report[k]) for k in ('decided_records', 'malformed_records', 'versions_without_marks')):
        return False
    by_error = report['malformed_by_error']
    if type(by_error) is not dict or not all(malformed_kind_ok(k) and _is_whole(v) for k, v in by_error.items()):
        return False
    if sum(by_error.values()) != report['malformed_records']:
        return False
    if not _code_list(report['left_out_reasons'], codes['fail_reasons'], empty_ok=True, in_order=True):
        return False
    extra = bool(report['left_out_reasons'])
    months, coach, waiting = report['months'], report['coach'], report['waiting']
    if not (type(months) is list and type(coach) is list and type(waiting) is list):
        return False
    return (all(_cell_ok(cell, codes, extra) for cell in months)
            and all(_pair_ok(pair, codes, extra) for pair in coach)
            and all(_side_ok(side, extra) for side in waiting))


def coach_result_allowed(result) -> bool:
    """True only when ``result`` (plain JSON values) passes the allow-list (module docstring)."""
    if _keys(result, ERROR_KEYS):
        return type(result['error']) is str and result['error'] in COACH_FILE_ERROR_CODES
    if _keys(result, REFUSAL_KEYS):
        return result['refusal'] == L.DEBUG_ON
    return _keys(result, TOP_KEYS) and _report_ok(result, _codes())


def checked_coach_text(result) -> str:
    """The JSON text the child writes: ``result`` itself when its JSON form passes the allow-list (the
    check runs on exactly what would be written), else `COACH_SCHEMA_TEXT`."""
    try:
        text = json.dumps(result, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError, RecursionError):     # not JSON: an odd type, a NaN, a loop
        return COACH_SCHEMA_TEXT
    if len(text) > MAX_RESULT_BYTES:                    # ASCII text (ensure_ascii): one byte a character
        return COACH_SCHEMA_TEXT
    return text if coach_result_allowed(json.loads(text)) else COACH_SCHEMA_TEXT


def _no_repeated_key(pairs):
    if len({k for k, _v in pairs}) != len(pairs):
        raise ValueError('a key repeats')
    return dict(pairs)


def _no_json_constant(_text):
    raise ValueError('not plain JSON')


def parse_coach_grade_bytes(raw: bytes) -> dict:
    """The parent's reading of the coach file's bytes: ``{"error": "bad_output"}`` when they are too many,
    not UTF-8 JSON (a repeated key, NaN or too deep included) or not a JSON object; ``{"error": "schema"}``
    when the object fails the allow-list; else the object. Never raises, never echoes the content."""
    if len(raw) > MAX_RESULT_BYTES:
        return {'error': BAD_OUTPUT}
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_no_repeated_key, parse_constant=_no_json_constant)
    except (ValueError, RecursionError):                # UnicodeDecodeError is a ValueError
        return {'error': BAD_OUTPUT}
    if type(data) is not dict:
        return {'error': BAD_OUTPUT}
    return data if coach_result_allowed(data) else {'error': SCHEMA}
