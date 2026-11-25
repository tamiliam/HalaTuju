"""LL5 phase C1c - the ALLOW-LIST the human lens's result must pass before the `new` child writes it to
`child.HUMAN_LENS_FILE`, and again after the parent reads it back. That file skips the scrubber, so this
check stands in for it: a future lens change must never be able to put a case id, a name or free text in it.

THE RULE. Every dict has exactly one of a few fixed key sets for its level (a key that is unknown OR
missing fails). A value is one of:
* an int (``type(v) is int``: a bool or a float is NOT an int);
* a bool only at ``frozen`` (exam block) and ``too_few`` (score lines, the share of Other), each tied to
  the block's own shape;
* None only where the lens leaves a field empty (a refused or unfrozen exam; the DEBUG refusal);
* text that is a member of a fixed set of codes: refusal codes, exam names, labels, the limit line, and
  the error codes `FILE_ERROR_CODES`;
* text built by the lens from fixed words and an int the result already holds (``status``,
  ``still_valid``, ``context_failed_line``, the ``a score on N facts`` limit): checked by rebuilding it
  from that int, so it can carry nothing new; or ``not frozen yet: N of 50`` with N from 0 to 49;
* one of four SHAPED values, each with a strict rule (the lead's rule is "ints or fixed codes only"; these
  are the only exceptions): ``engine_version`` (`ENGINE_VERSION_SHAPE`, the verdict engine's
  ``YYYY-MM-DD.N`` form, at most 14 characters, and the same in every exam as at the top); ``digest``
  (exactly 12 lower-case hex characters); ``key_check`` (`lens_human.is_key_check`: 8 lower-case hex);
  ``frozen_at`` (`FROZEN_AT_SHAPE`, a UTC ISO time with microseconds and ``+00:00`` that parses back to
  the same text);
* a nested dict or list of the same.
Anything else: the whole result becomes exactly ``{"error": "schema"}``, with nothing of the bad result
in it (not a value, not a key name). The checker only walks known keys of a fixed depth, so it never
recurses into what it does not know, and never raises on a JSON value.

EVERY FIELD THAT IS NOT AN INT OR A FIXED CODE, with its rule (taken from the checks below):
* ``engine_version`` (top and each exam block): `engine_version_ok`, or None at the top; each exam's must
  equal the top one (so None in an exam only when the top is None).
* ``digest``: exactly 12 lower-case hex characters (`DIGEST_SHAPE`); None until the exam is frozen.
* ``key_check``: 8 lower-case hex (`lens_human.is_key_check`), exam-1 once frozen only; else None.
* ``frozen_at``: `FROZEN_AT_SHAPE` and it parses back to the same text; None until frozen.
* ``status``: rebuilt from the block: ``refused: <refusal code>``; for exam_missing ``refused: exam_missing
  (N of 50 candidates)`` (exam-1) or ``(N candidate cases)`` (exam-old); ``frozen``; ``not frozen yet: N of
  50`` with N from 0 to 49 (exam-1) or ``not frozen yet: 0 cases`` (exam-old).
* ``still_valid``: ``V of S still valid``, V the valid count and S the size; None until frozen.
* ``context_failed_line``: ``<lens_human.FAILED_CONTEXT_LINE>: N`` with N = ``context_failed``; None
  exactly when ``context_failed`` is None.
* ``known_limits``: a list, exactly the weak label (exam-old only), then, when there is a score,
  ``a score on N facts`` (N = the score's facts) and `lens_human.DROP_OUTS_LIMIT`.
* ``frozen`` (bool): True exactly when ``status`` is ``frozen``; False with any refusal.
* ``too_few`` (bool): True exactly when the score line has the small key set, or the share of Other has
  no ``pct``.
* None is allowed only at: the top ``engine_version`` and the four top counts (the DEBUG refusal or
  nothing read) and ``context_failed_line`` as above; an exam's ``refusal``; ``candidates`` (except with
  exam_missing); ``cases_with_other_key_check``; the fields of `_SAT_FIELDS` until frozen; ``key_check``,
  ``valid_split`` and ``could_not_recompute_reasons`` until frozen and always for exam-old.

The code sets come from the lens's own public constants (and `ai_score`, `fail_reasons`, `fact_bands`,
imported inside a function); a new KEY needs a deliberate change here and in the test that pins the keys.
"""
from __future__ import annotations

import datetime
import json
import re

from . import lens_human as L

SCHEMA, NO_OUTPUT, BAD_OUTPUT = 'schema', 'no_output', 'bad_output'
SCHEMA_TEXT = json.dumps({'error': SCHEMA})
#: A caught lens error is recorded by the NEAREST of these classes (a subclass's own name never reaches
#: the file: a FileNotFoundError is recorded as OSError, a UnicodeDecodeError as ValueError).
LENS_ERROR_CLASSES = (L.BadCaseRow, ValueError, TypeError, OSError)
#: The only error codes the lens file may hold (the child writes them); the parent adds NO_OUTPUT and
#: BAD_OUTPUT itself, never from the file.
FILE_ERROR_CODES = frozenset({SCHEMA, *(c.__name__ for c in LENS_ERROR_CLASSES)})
#: A result file bigger than this is not read (the real result is a few kB).
MAX_RESULT_BYTES = 1 << 20

TOP_KEYS = frozenset({'engine_version', 'cases_read', 'not_decided', 'no_human_verdict', 'context_failed',
                      'context_failed_line', 'exams'})
ERROR_KEYS = frozenset({'error'})
EXAM_KEYS = frozenset({'exam', 'label', 'frozen', 'status', 'size', 'digest', 'frozen_at', 'key_check',
                       'engine_version', 'refusal', 'cases_with_other_key_check', 'validity', 'still_valid',
                       'valid_split', 'could_not_recompute_reasons', 'qc_turned_to_pass', 'score',
                       'score_without_interview_fails', 'fails', 'candidates', 'known_limits'})
#: The DEBUG refusal's exam block (`lens_human_rows`): nothing read, the exam refused.
EXAM_DEBUG_KEYS = frozenset({'exam', 'refusal', 'status'})
SMALL_LINE_KEYS = frozenset({'label', 'facts', 'too_few'})
SCORE_KEYS = SMALL_LINE_KEYS | {'points', 'best', 'score_pct', 'not_scored', 'outcomes', 'coverage',
                                'generous_wrong'}
EXTRA_LINE_KEYS = SMALL_LINE_KEYS | {'points', 'best', 'score_pct', 'left_out'}
COUNT_OF_KEYS = frozenset({'count', 'of'})
VALID_SPLIT_KEYS = frozenset({'matched_directly', 'recovered_by_twin'})
FAILS_KEYS = frozenset({'fails', 'by_band_and_reason', 'interview_by_band', 'share_other'})
SHARE_SMALL_KEYS = COUNT_OF_KEYS | {'too_few'}
SHARE_KEYS = SHARE_SMALL_KEYS | {'pct'}

REFUSAL_CODES = frozenset({
    L.UNREADABLE, L.UNKNOWN_FIELD, L.MISSING_FIELD, L.WRONG_EXAM_NAME, L.WRONG_FORMAT, L.BAD_FIELD_TYPE,
    L.NON_INTEGER_ID, L.DUPLICATE_ID, L.SIZE_MISMATCH, L.DIGEST_MISMATCH, L.ID_BELOW_ONE, L.EMPTY_EXAM,
    L.BAD_DECIDED_AT, L.BAD_FROZEN_AT, L.BAD_KEY_CHECK, L.EXAM_MISSING, L.FOLDER_MISSING, L.INSIDE_GIT_REPO,
    L.ALREADY_FROZEN, L.FOLDER_NOT_WRITABLE, L.FOLDER_NOT_ABSOLUTE, L.DEBUG_ON, L.KEY_BLANK,
    L.KEY_CHECKS_MIXED, L.KEY_CHECK_MISSING, L.CANDIDATES_NOT_CURRENT, L.KEY_CHECK_DIFFERS_EXAM,
    L.KEY_CHECK_DIFFERS_CASES})
EXAM_LABELS = {L.EXAM_1: L.EXAM_1_LABEL, L.EXAM_OLD: L.WEAK_LABEL}
SCORE_LABEL = 'score'
#: The verdict engine's version form (`verdict_engine.VERDICT_ENGINE_VERSION`, e.g. 2026-11-18.2).
ENGINE_VERSION_SHAPE = re.compile(r'20[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])\.[0-9]{1,3}', re.ASCII)
DIGEST_SHAPE = re.compile(r'[0-9a-f]{12}', re.ASCII)
FROZEN_AT_SHAPE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}\+00:00', re.ASCII)
_NOT_FROZEN_EXAM_1 = frozenset(f'not frozen yet: {n} of {L.EXAM_1_SIZE}' for n in range(L.EXAM_1_SIZE))
_NOT_FROZEN_EXAM_OLD = 'not frozen yet: 0 cases'
#: The fields an exam has only once it sat (frozen); None before.
_SAT_FIELDS = ('size', 'digest', 'frozen_at', 'validity', 'still_valid', 'qc_turned_to_pass', 'score',
               'score_without_interview_fails', 'fails')


def lens_error_name(exc) -> str:
    """The nearest `LENS_ERROR_CLASSES` name of a caught lens error (`SCHEMA` for any other class)."""
    return next((k.__name__ for k in type(exc).__mro__ if k in LENS_ERROR_CLASSES), SCHEMA)


def _known_codes() -> tuple:
    """``(bands, fail reasons in the Fails table, score outcomes)`` from the scoring modules' constants."""
    from apps.scholarship import ai_score, fail_reasons
    from apps.scholarship.fact_bands import BANDS
    reasons = frozenset(c for c in fail_reasons.CODES if c != fail_reasons.INTERVIEW_DIFFERS) | {L.NOT_GIVEN}
    return frozenset(BANDS), reasons, frozenset(ai_score.OUTCOMES)


def _is_count(value) -> bool:
    return type(value) is int


def _count_or_none(value) -> bool:
    return value is None or type(value) is int


def _keys_are(value, *key_sets) -> bool:
    return type(value) is dict and frozenset(value) in key_sets


def _count_map(value, keys) -> bool:
    return _keys_are(value, frozenset(keys)) and all(_is_count(v) for v in value.values())


def _code_in(value, codes) -> bool:
    return type(value) is str and value in codes


def _frozen_at_ok(text) -> bool:
    if type(text) is not str or not FROZEN_AT_SHAPE.fullmatch(text):
        return False
    try:
        when = datetime.datetime.fromisoformat(text)
    except ValueError:
        return False
    return when.isoformat(timespec='microseconds') == text


def engine_version_ok(value) -> bool:
    """True for the verdict engine's version form: `ENGINE_VERSION_SHAPE`, at most 14 characters."""
    return type(value) is str and len(value) <= 14 and ENGINE_VERSION_SHAPE.fullmatch(value) is not None


def _score_block_ok(block, label, full_keys, extra_counts, outcomes) -> bool:
    """A score line: the count only under the small-number rule, else every figure (`lens_human._small`)."""
    if block is None:
        return True
    if not _keys_are(block, SMALL_LINE_KEYS, full_keys) or block['label'] != label or not _is_count(block['facts']):
        return False
    if block['too_few'] is not (frozenset(block) == SMALL_LINE_KEYS):
        return False
    if block['too_few']:
        return True
    if not all(_is_count(block[k]) for k in ('points', 'best', 'score_pct', *extra_counts)):
        return False
    if full_keys is SCORE_KEYS:
        return (_count_map(block['outcomes'], outcomes) and _count_map(block['coverage'], COUNT_OF_KEYS)
                and _count_map(block['generous_wrong'], COUNT_OF_KEYS))
    return True


def _fails_block_ok(block, bands, reasons) -> bool:
    if block is None:
        return True
    if not _keys_are(block, FAILS_KEYS) or not _is_count(block['fails']):
        return False
    table, share = block['by_band_and_reason'], block['share_other']
    if not (_keys_are(table, bands) and all(_count_map(row, reasons) for row in table.values())):
        return False
    if not _count_map(block['interview_by_band'], bands) or not _keys_are(share, SHARE_SMALL_KEYS, SHARE_KEYS):
        return False
    if not (_is_count(share['count']) and _is_count(share['of'])) or share['too_few'] is not ('pct' not in share):
        return False
    return 'pct' not in share or _is_count(share['pct'])


def _exam_status_ok(name, block) -> bool:
    """``status`` rebuilt from the block's own refusal, candidate count and frozen flag."""
    status, refusal, frozen = block['status'], block['refusal'], block['frozen']
    if refusal is not None:
        if not _code_in(refusal, REFUSAL_CODES) or frozen is not False:
            return False
        if refusal == L.EXAM_MISSING:
            tail = f' of {L.EXAM_1_SIZE} candidates' if name == L.EXAM_1 else ' candidate cases'
            return _is_count(block['candidates']) and status == f'refused: {refusal} ({block["candidates"]}{tail})'
        return block['candidates'] is None and status == f'refused: {refusal}'
    if block['candidates'] is not None:
        return False
    if frozen is True:
        return status == 'frozen'
    if frozen is not False:
        return False
    return status == _NOT_FROZEN_EXAM_OLD if name == L.EXAM_OLD else _code_in(status, _NOT_FROZEN_EXAM_1)


def _sat_fields_ok(name, block, codes) -> bool:
    """The fields an exam has once it sat: all None before, all filled and consistent after."""
    bands, reasons, outcomes = codes
    exam_1 = name == L.EXAM_1
    later = (block['key_check'], block['valid_split'], block['could_not_recompute_reasons'])
    if block['frozen'] is not True:
        return all(block[k] is None for k in _SAT_FIELDS) and all(v is None for v in later)
    validity, size, score = block['validity'], block['size'], block['score']
    if not (_is_count(size) and _count_map(validity, L.VALIDITY) and sum(validity.values()) == size):
        return False
    if block['still_valid'] != f'{validity["valid"]} of {size} still valid':
        return False
    digest = block['digest']
    if not (type(digest) is str and DIGEST_SHAPE.fullmatch(digest)):
        return False
    if not (_frozen_at_ok(block['frozen_at']) and _is_count(block['qc_turned_to_pass'])):
        return False
    split, reasons_count = block['valid_split'], block['could_not_recompute_reasons']
    if exam_1:                                          # exam-1 only: the key check and the valid split
        extras_ok = (L.is_key_check(block['key_check']) and _count_map(split, VALID_SPLIT_KEYS)
                     and _count_map(reasons_count, L.RECOMPUTE_REASONS))
    else:
        extras_ok = block['key_check'] is None and split is None and reasons_count is None
    if not extras_ok:
        return False
    return (score is not None and _score_block_ok(score, SCORE_LABEL, SCORE_KEYS, ('not_scored',), outcomes)
            and block['score_without_interview_fails'] is not None
            and _score_block_ok(block['score_without_interview_fails'], L.EXTRA_LINE_LABEL, EXTRA_LINE_KEYS,
                                ('left_out',), outcomes)
            and block['fails'] is not None and _fails_block_ok(block['fails'], bands, reasons))


def _exam_block_ok(name, block, version, codes) -> bool:
    if _keys_are(block, EXAM_DEBUG_KEYS):                  # the DEBUG refusal: nothing was read
        return (block['exam'] == name and block['refusal'] == L.DEBUG_ON
                and block['status'] == f'refused: {L.DEBUG_ON}')
    if not _keys_are(block, EXAM_KEYS) or block['exam'] != name or block['label'] != EXAM_LABELS[name]:
        return False
    if block['engine_version'] != version or not _count_or_none(block['cases_with_other_key_check']):
        return False
    if not (_exam_status_ok(name, block) and _sat_fields_ok(name, block, codes)):
        return False
    limits = [L.WEAK_LABEL] if name == L.EXAM_OLD else []
    if block['score'] is not None:
        limits += [f'a score on {block["score"]["facts"]} facts', L.DROP_OUTS_LIMIT]
    return block['known_limits'] == limits


def human_lens_result_allowed(result) -> bool:
    """True only when ``result`` (plain JSON values) passes the allow-list (module docstring)."""
    if _keys_are(result, ERROR_KEYS):
        return _code_in(result['error'], FILE_ERROR_CODES)
    if not _keys_are(result, TOP_KEYS):
        return False
    version, failed = result['engine_version'], result['context_failed']
    if not (version is None or engine_version_ok(version)):
        return False
    if not all(_count_or_none(result[k]) for k in ('cases_read', 'not_decided', 'no_human_verdict', 'context_failed')):
        return False
    line = None if failed is None else f'{L.FAILED_CONTEXT_LINE}: {failed}'
    if result['context_failed_line'] != line or not _keys_are(result['exams'], frozenset(L.EXAM_NAMES)):
        return False
    codes = _known_codes()
    return all(_exam_block_ok(name, result['exams'][name], version, codes) for name in L.EXAM_NAMES)


def checked_result_text(result) -> str:
    """The JSON text the child writes: ``result`` itself when its JSON form passes the allow-list (the
    check runs on exactly what would be written), else `SCHEMA_TEXT`."""
    try:
        text = json.dumps(result, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError, RecursionError):     # not JSON: an odd type, a NaN, a loop
        return SCHEMA_TEXT
    if len(text) > MAX_RESULT_BYTES:                    # ASCII text (ensure_ascii): one byte a character
        return SCHEMA_TEXT
    return text if human_lens_result_allowed(json.loads(text)) else SCHEMA_TEXT


def _once_each(pairs):
    if len({k for k, _v in pairs}) != len(pairs):
        raise ValueError('a key repeats')
    return dict(pairs)


def _refuse_json_constant(_text):
    raise ValueError('not plain JSON')


def parse_human_lens_bytes(raw: bytes) -> dict:
    """The parent's reading of the lens file's bytes: ``{"error": "bad_output"}`` when they are too many,
    not UTF-8 JSON (a repeated key, NaN or too deep included) or not a JSON object; ``{"error": "schema"}``
    when the object fails the allow-list; else the object. Never raises, never echoes the content."""
    if len(raw) > MAX_RESULT_BYTES:
        return {'error': BAD_OUTPUT}
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_once_each, parse_constant=_refuse_json_constant)
    except (ValueError, RecursionError):                # UnicodeDecodeError is a ValueError
        return {'error': BAD_OUTPUT}
    if type(data) is not dict:
        return {'error': BAD_OUTPUT}
    return data if human_lens_result_allowed(data) else {'error': SCHEMA}
