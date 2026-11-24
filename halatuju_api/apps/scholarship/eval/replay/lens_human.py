"""LL5 phase B2a - the replay's HUMAN LENS: a frozen exam of decided cases, and its score. PURE: no
database, network, clock or environment read; the scoring modules are imported inside functions only.
It marks the replayed engine's fresh bands against the human's Pass / Fail with the house points
(`ai_score`). The case list is FROZEN, so two engine versions sit the SAME exam.

THE CASE ROW (one plain dict per case, built by phase B2b). Exactly these keys:
* ``application_id`` int (not bool); in the exam file only, never in an output.
* ``verdict_decided_at`` datetime or None (None = not decided); no zone = UTC.
* ``stored_context`` the stored ``ai_verdict_context``: ``{}``, FULL (``fingerprint`` and ``key_check``,
  both text) or FAILED (``error``, no fingerprint).
* ``recomputed_fingerprint`` text, or None when it could not be recomputed.
* ``human_verdict`` the stored ``officer_verdict`` or None; no fact marked pass or fail = no verdict.
* ``qc_answers`` ``second_look.stored(officer_verdict)`` (``officer_verdict['qc_fact_checks']``) or None.
  It judges the reviewer's Fails only: ``disagreed`` turns that Fail to Pass (its reason dropped),
  ``agreed`` keeps it; an answer on any other fact is not read.
* ``fresh_snapshot`` the replayed verdict list, or None. ``engine_version`` text, the same in every row.
* ``recompute_note`` on a decided FULL row only: `RECOVERED_BY_TWIN` with a fingerprint, else None; a
  `RECOMPUTE_REASONS` code when the fingerprint is None (it must be). It only splits the counts.
A wrong-shaped row raises `BadCaseRow` naming the field, never its value, and the whole run stops.

THE TWO EXAMS, chosen by the stored context's shape, never by a date: ``exam-1`` (FULL context) is the
first 50 by decision time, ties by id; ``exam-old`` (``{}``) is all of them. A FAILED context is in
neither exam and has its own count. A FREEZE IS ASKED FOR, never automatic: only ``freeze=True`` writes
a missing exam file (exam-1 once 50 exist, exam-old once one exists). A normal run (``freeze=False``)
never writes: a missing file is EXAM_MISSING with the candidate count, so a deleted or lost exam file is
never replaced by a new exam unless a person asks for it.

THE EXAM FILE ``<folder>/<exam>.json``: exactly ``exam, format, application_ids, decided_at, size,
frozen_at`` (+ ``key_check``, exam-1 only: `KEY_CHECK_LENGTH` lower-case hex characters) and ``digest``
= sha256 hex of the canonical JSON (sorted keys, no spaces, ASCII) of the other fields. ``decided_at``
holds each listed case's decision time at the freeze, in the same order; it and ``frozen_at`` are UTC
ISO 8601 text with microseconds and ``+00:00``. Written to a temp file, then hard-linked to its name (a
link, unlike a POSIX rename, never replaces a file). Never overwritten.

THE FOLDER is checked once per run, before any load: missing, not a folder, an empty or non-path
argument (all ``folder_missing``), a relative path (``folder_not_absolute``) or inside a git repository
after resolving links (``.git`` in it or any parent) refuses both exams. A folder that cannot take the
write gives ``folder_not_writable``.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import tempfile

EXAM_1, EXAM_OLD = 'exam-1', 'exam-old'
EXAM_NAMES, FORMAT_VERSION, EXAM_1_SIZE = (EXAM_1, EXAM_OLD), 1, 50
WEAK_LABEL = 'weaker exam: evidence state unknown'
EXAM_1_LABEL = 'same evidence, checked by fingerprint'
EXTRA_LINE_LABEL = 'score without interview Fails'
DROP_OUTS_LIMIT = 'drop-outs shrink the exam'
FAILED_CONTEXT_LINE = 'decided cases whose context record failed (in neither exam)'

FULL, EMPTY, FAILED = 'full', 'empty', 'failed'
CASE_FIELDS = ('application_id', 'verdict_decided_at', 'stored_context', 'recomputed_fingerprint',
               'human_verdict', 'qc_answers', 'fresh_snapshot', 'engine_version', 'recompute_note')
_BASE_FIELDS = {'exam', 'format', 'application_ids', 'decided_at', 'size', 'frozen_at', 'digest'}
_ALLOWED = {EXAM_1: _BASE_FIELDS | {'key_check'}, EXAM_OLD: _BASE_FIELDS}
NOT_GIVEN = 'not_given'   # a Fail with no stored reason (old rows)
# A key check's one form, restated from `verdict_context.key_check` (the first 8 characters of an
# HMAC-SHA256 ``hexdigest()``, so lower-case hex); that module defines no public pattern for it.
KEY_CHECK_LENGTH, KEY_CHECK_ALPHABET = 8, frozenset('0123456789abcdef')

# Reason codes: loading an exam file; freezing (writing) one; the key check (exam-1).
UNREADABLE, UNKNOWN_FIELD, MISSING_FIELD = 'file_unreadable', 'unknown_field', 'missing_field'
WRONG_EXAM_NAME, WRONG_FORMAT = 'wrong_exam_name', 'wrong_format_version'
BAD_FIELD_TYPE, NON_INTEGER_ID, DUPLICATE_ID = 'bad_field_type', 'non_integer_id', 'duplicate_id'
SIZE_MISMATCH, DIGEST_MISMATCH = 'size_mismatch', 'digest_mismatch'
ID_BELOW_ONE, EMPTY_EXAM, BAD_DECIDED_AT = 'id_below_one', 'empty_exam', 'bad_decided_at'
BAD_FROZEN_AT, BAD_KEY_CHECK, EXAM_MISSING = 'bad_frozen_at', 'bad_key_check', 'exam_missing'
FOLDER_MISSING, INSIDE_GIT_REPO, ALREADY_FROZEN = 'folder_missing', 'inside_git_repo', 'already_frozen'
FOLDER_NOT_WRITABLE, FOLDER_NOT_ABSOLUTE = 'folder_not_writable', 'folder_not_absolute'
DEBUG_ON = 'debug_on'   # the database door refuses the whole run: Django DEBUG logs SQL with case ids
KEY_BLANK, KEY_CHECKS_MIXED = 'key_blank', 'candidate_key_checks_differ'
KEY_CHECK_MISSING, CANDIDATES_NOT_CURRENT = 'current_key_check_missing', 'candidate_key_check_not_current'
KEY_CHECK_DIFFERS_EXAM, KEY_CHECK_DIFFERS_CASES = 'key_check_differs_from_exam', 'key_check_differs_from_cases'
VALIDITY = ('valid', 'evidence_changed', 'could_not_recompute', 'missing', 'context_changed',
            'no_longer_decided', 'decided_again')
RECOVERED_BY_TWIN = 'twin'   # the case row's ``recompute_note`` vocabulary: this, or a reason below
RECOMPUTE_REASONS = ('past_award_stage', 'decided_group_twin', 'twin_not_unique', 'recompute_error',
                     'key_not_current')


class BadCaseRow(ValueError):
    """A case row of the wrong shape. The message names the field, never a value."""

    def __init__(self, field: str, problem: str):
        super().__init__(f'case row: {field} {problem}')
        self.field = field


def exam_context_shape(context) -> str:
    """FULL, EMPTY or FAILED for a stored ``ai_verdict_context``; any other shape raises BadCaseRow."""
    if not isinstance(context, dict):
        raise BadCaseRow('stored_context', 'is not an object')
    if not context:
        return EMPTY
    if 'fingerprint' in context:
        for name in ('fingerprint', 'key_check'):
            if not isinstance(context.get(name), str):
                raise BadCaseRow(f'stored_context.{name}', 'is missing or not text')
        return FULL
    if 'error' in context:
        return FAILED
    raise BadCaseRow('stored_context', 'has neither a fingerprint nor an error')


def _typed(row, field, types, allow_none):
    value = row[field]
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, types):
        raise BadCaseRow(field, 'has the wrong type')
    return value


def _read_case(row) -> dict:
    """One validated row as the lens's own plain dict (see the module docstring)."""
    from apps.scholarship import ai_score, second_look
    if not isinstance(row, dict):
        raise BadCaseRow('row', 'is not an object')
    for field in CASE_FIELDS:
        if field not in row:
            raise BadCaseRow(field, 'is missing')
    if set(row) - set(CASE_FIELDS):
        raise BadCaseRow('row', 'has an unknown field')
    when = _typed(row, 'verdict_decided_at', datetime.datetime, True)
    if when is not None:
        try:
            when = _as_utc(when)
        except (OverflowError, ValueError):   # an aware year-1 / year-9999 time off UTC; a bad zone
            raise BadCaseRow('verdict_decided_at', 'cannot be read as a UTC instant') from None
    verdict = _typed(row, 'human_verdict', dict, True)
    qc = _typed(row, 'qc_answers', dict, True)
    if qc is not None and not all(isinstance(a, str) and a in second_look.ANSWERS for a in qc.values()):
        raise BadCaseRow('qc_answers', 'holds an answer that is not agreed or disagreed')
    context = _typed(row, 'stored_context', dict, False)
    answer, turned = _human_answer(verdict, qc)
    if _typed(row, 'application_id', int, False) < 1:
        raise BadCaseRow('application_id', 'is below 1')
    shape, recomputed = exam_context_shape(context), _typed(row, 'recomputed_fingerprint', str, True)
    note = _typed(row, 'recompute_note', str, True)
    fits = ((None,) if when is None or shape != FULL else (None, RECOVERED_BY_TWIN) if recomputed is not None
            else RECOMPUTE_REASONS)
    if note not in fits:
        raise BadCaseRow('recompute_note', 'is not a known note or does not fit the fingerprint')
    return {'id': row['application_id'], 'when': when, 'context': context, 'shape': shape,
            'recomputed': recomputed, 'note': note,
            'has_verdict': bool(verdict and ai_score.decided_facts(None, verdict)),
            'answer': answer, 'qc_turned': turned,
            'snapshot': _typed(row, 'fresh_snapshot', list, True),
            'version': _typed(row, 'engine_version', str, False)}


def _human_answer(verdict, qc):
    """``(verdict to score, Fails the QC turned to Pass)``: the QC wins on each Fail it judged."""
    from apps.scholarship import fail_reasons, second_look
    if not verdict or not qc:
        return verdict, 0
    answer, turned = dict(verdict), 0
    stored = verdict.get(fail_reasons.KEY)
    reasons = dict(stored) if isinstance(stored, dict) else {}
    for fact, qc_answer in qc.items():
        if verdict.get(fact) == 'fail' and qc_answer == second_look.DISAGREED:
            answer[fact] = 'pass'
            reasons.pop(fact, None)
            turned += 1
    answer[fail_reasons.KEY] = reasons
    return answer, turned


def exam_digest(exam: dict) -> str:
    """sha256 (hex) of the canonical JSON of every field of ``exam`` but ``digest``."""
    body = {k: v for k, v in exam.items() if k != 'digest'}
    text = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(text.encode('ascii')).hexdigest()


def _no_repeated_keys(pairs):
    if len({k for k, _v in pairs}) != len(pairs):
        raise ValueError('a key repeats')
    return dict(pairs)


def _refuse_constant(_text):
    raise ValueError('not plain JSON')


def _exam_file_refusal(name: str, data) -> str | None:
    """The reason code that refuses a loaded exam file, or None when it may be scored."""
    if not isinstance(data, dict):
        return UNREADABLE
    if set(data) - _ALLOWED[name]:
        return UNKNOWN_FIELD
    if _ALLOWED[name] - set(data):
        return MISSING_FIELD
    if data['exam'] != name:
        return WRONG_EXAM_NAME
    if type(data['format']) is not int or data['format'] != FORMAT_VERSION:
        return WRONG_FORMAT
    ids, times = data['application_ids'], data['decided_at']
    texts = [data[k] for k in ('frozen_at', 'digest', 'key_check') if k in data]
    if not isinstance(ids, list) or not isinstance(times, list) or not all(isinstance(t, str) for t in texts):
        return BAD_FIELD_TYPE
    if not ids:
        return EMPTY_EXAM
    if not all(type(i) is int for i in ids):
        return NON_INTEGER_ID
    if min(ids) < 1:
        return ID_BELOW_ONE
    if len(set(ids)) != len(ids):
        return DUPLICATE_ID
    if type(data['size']) is not int or data['size'] != len(ids) \
            or (name == EXAM_1 and data['size'] != EXAM_1_SIZE):
        return SIZE_MISMATCH
    if len(times) != len(ids) or not all(_stored_time(t) is not None for t in times):
        return BAD_DECIDED_AT
    if _stored_time(data['frozen_at']) is None:
        return BAD_FROZEN_AT
    if name == EXAM_1 and not is_key_check(data['key_check']):
        return BAD_KEY_CHECK
    if data['digest'] != exam_digest(data):
        return DIGEST_MISMATCH
    return None


def is_key_check(value) -> bool:
    """True only for a key check's one form: `KEY_CHECK_LENGTH` characters of `KEY_CHECK_ALPHABET`."""
    return isinstance(value, str) and len(value) == KEY_CHECK_LENGTH and set(value) <= KEY_CHECK_ALPHABET


def _as_utc(when: datetime.datetime) -> datetime.datetime:
    """The same instant in UTC; no zone (or a zone with no offset) = UTC. Raises OverflowError when the
    instant does not fit in UTC (an aware year-1 or year-9999 time off UTC), ValueError on a bad zone."""
    if when.utcoffset() is None:
        return when.replace(tzinfo=datetime.timezone.utc)
    return when.astimezone(datetime.timezone.utc)


def _decided_text(when) -> str:
    """The one stored form of a decision time or freeze time: UTC, microseconds, ``+00:00``."""
    if not isinstance(when, datetime.datetime):
        raise ValueError('a decision time must be a datetime')
    try:
        return _as_utc(when).isoformat(timespec='microseconds')
    except OverflowError:
        raise ValueError('a decision time does not fit in UTC') from None


def _stored_time(text):
    """The UTC instant of a stored decision time, or None unless it is exactly `_decided_text`'s form."""
    if not isinstance(text, str):
        return None
    try:
        when = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if when.utcoffset() != datetime.timedelta(0) or _decided_text(when) != text:
        return None
    return when


def load_exam(folder, name: str):
    """``(exam, None)``; ``(None, None)`` when no exam file exists yet; ``(None, reason code)`` when the
    file must not be scored (see the reason codes above)."""
    if name not in EXAM_NAMES:
        raise ValueError('unknown exam name')
    path = os.path.join(os.fspath(folder), f'{name}.json')
    if not os.path.lexists(path):
        return None, None
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh, object_pairs_hook=_no_repeated_keys, parse_constant=_refuse_constant)
    except (OSError, ValueError, RecursionError):   # RecursionError: JSON nested too deep to read
        return None, UNREADABLE
    refusal = _exam_file_refusal(name, data)
    return (None, refusal) if refusal else (data, None)


def exam_folder_refusal(folder) -> str | None:
    """FOLDER_MISSING (an empty text or not a text path), FOLDER_NOT_ABSOLUTE (a relative path, such as
    ``.``), FOLDER_MISSING (missing or not a folder), INSIDE_GIT_REPO or None, checked in that order.
    Links are resolved first; then the folder and every parent up to the root is checked for a ``.git``
    entry (a folder or a file)."""
    try:
        text = os.fspath(folder) if isinstance(folder, (str, os.PathLike)) else None
    except TypeError:   # a path-like object that gives neither text nor bytes
        return FOLDER_MISSING
    if not isinstance(text, str) or not text:
        return FOLDER_MISSING
    if not os.path.isabs(text):   # a relative path would depend on where the process happens to run
        return FOLDER_NOT_ABSOLUTE
    try:
        real = pathlib.Path(text).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):   # ValueError: a NUL in the path
        return FOLDER_MISSING
    if not real.is_dir():
        return FOLDER_MISSING
    return next((INSIDE_GIT_REPO for p in (real, *real.parents) if os.path.lexists(p / '.git')), None)


def _utc_text(now) -> str:
    """``now`` as a freeze time (`_decided_text`'s form); ValueError naming ``now`` unless it is an aware
    datetime that fits in UTC."""
    try:
        if isinstance(now, datetime.datetime) and now.utcoffset() is not None:
            return _decided_text(now)
    except ValueError:   # does not fit in UTC, or a zone whose offset is out of range
        pass
    raise ValueError('now must be a datetime with a time zone that fits in UTC')


def freeze_exam(folder, name: str, application_ids, decided_at, now, key_check=None):
    """Write a NEW exam file and return ``(exam, None)``, or ``(None, reason code)``. ``decided_at``: one
    decision time per id, same order. ``key_check`` (`is_key_check`) is required for exam-1 and refused
    for exam-old. Never overwrites: an existing file = ALREADY_FROZEN; a folder that cannot take it =
    FOLDER_NOT_WRITABLE."""
    if name not in EXAM_NAMES:
        raise ValueError('unknown exam name')
    ids = list(application_ids)
    if not ids or not all(type(i) is int and i >= 1 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('application_ids must be distinct whole numbers from 1, at least one')
    times = [_decided_text(when) for when in decided_at]
    if len(times) != len(ids):
        raise ValueError('decided_at needs one time per application id')
    if not (is_key_check(key_check) if name == EXAM_1 else key_check is None):
        raise ValueError('key_check is 8 lower-case hex characters for exam-1 and absent for exam-old')
    exam = {'exam': name, 'format': FORMAT_VERSION, 'application_ids': ids, 'decided_at': times,
            'size': len(ids), 'frozen_at': _utc_text(now)}
    if name == EXAM_1:
        exam['key_check'] = key_check
    exam['digest'] = exam_digest(exam)
    refusal = exam_folder_refusal(folder)
    if refusal:
        return None, refusal
    real = pathlib.Path(os.fspath(folder)).resolve(strict=True)
    target = real / f'{name}.json'
    if os.path.lexists(target):
        return None, ALREADY_FROZEN
    try:
        handle, temp = tempfile.mkstemp(prefix=f'.{name}.', suffix='.tmp', dir=real)
    except OSError:   # a read-only folder
        return None, FOLDER_NOT_WRITABLE
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(exam, sort_keys=True, indent=1))
            fh.flush()
            os.fsync(fh.fileno())
        os.link(temp, target)   # atomic, and fails when the name exists
    except FileExistsError:
        return None, ALREADY_FROZEN
    except OSError:   # a full disk, or no hard links (a mounted bucket, FAT/exFAT, another device)
        return None, FOLDER_NOT_WRITABLE
    finally:
        try:
            os.unlink(temp)
        except OSError:   # clean-up only: a good link stands; a failed one keeps its reason code
            pass
    return exam, None


def _small(line: dict) -> dict:
    """The small-number rule: under `coach_grade.CELL_MIN_FACTS` facts, the count only."""
    from apps.scholarship.coach_grade import CELL_MIN_FACTS
    if line['facts'] < CELL_MIN_FACTS:
        return {'label': line['label'], 'facts': line['facts'], 'too_few': True}
    return dict(line, too_few=False)


def _fails_table(records) -> dict:
    """Fails by AI band x reviewer reason (scored facts only), interview Fails in their own block."""
    from apps.scholarship import ai_score, fail_reasons
    from apps.scholarship.coach_grade import CELL_MIN_FACTS
    from apps.scholarship.fact_bands import BANDS
    codes = [c for c in fail_reasons.CODES if c != fail_reasons.INTERVIEW_DIFFERS] + [NOT_GIVEN]
    table = {band: dict.fromkeys(codes, 0) for band in BANDS}
    interview = dict.fromkeys(BANDS, 0)
    total = 0
    for snapshot, verdict, _version in records:
        for fact, band, officer in ai_score.decided_facts(snapshot, verdict):
            if band is None or officer != 'fail':
                continue
            total += 1
            reason = fail_reasons.given(verdict, fact) or NOT_GIVEN
            if reason == fail_reasons.INTERVIEW_DIFFERS:
                interview[band] += 1
            else:
                table[band][reason] += 1
    other = sum(row[fail_reasons.OTHER] for row in table.values())
    share = {'count': other, 'of': total, 'too_few': total < CELL_MIN_FACTS}
    if not share['too_few']:
        share['pct'] = ai_score.percent(other, total)
    return {'fails': total, 'by_band_and_reason': table, 'interview_by_band': interview,
            'share_other': share}


def _exam_score(rows: list) -> dict:
    """The score, the extra line and the Fails table of the VALID cases, every mark through `ai_score`."""
    from apps.scholarship import ai_score, fail_reasons
    from apps.scholarship.fact_bands import CERTAIN, PROBABLE, UNSURE
    records = [(row['snapshot'], row['answer'], row['version']) for row in rows]
    marks = ai_score.score_marks(records)
    covered = generous_wrong = left_out = 0
    without = []
    for snapshot, verdict, version in records:
        kept = dict(verdict)
        for fact, band, officer in ai_score.decided_facts(snapshot, verdict):
            if band is None:
                continue
            covered += band != UNSURE
            generous_wrong += officer == 'fail' and band in (CERTAIN, PROBABLE)
            if officer == 'fail' and fail_reasons.given(verdict, fact) == fail_reasons.INTERVIEW_DIFFERS:
                del kept[fact]
                left_out += 1
        without.append((snapshot, kept, version))
    other = ai_score.score_marks(without)
    score = {'label': 'score', 'facts': marks['facts'], 'points': marks['points'], 'best': marks['best'],
             'score_pct': marks['score_pct'], 'not_scored': marks['not_scored'],
             'outcomes': {o: marks[o] for o in ai_score.OUTCOMES},
             'coverage': {'count': covered, 'of': marks['facts']},
             'generous_wrong': {'count': generous_wrong, 'of': marks['facts']}}
    extra = {'label': EXTRA_LINE_LABEL, 'facts': other['facts'], 'points': other['points'],
             'best': other['best'], 'score_pct': other['score_pct'], 'left_out': left_out}
    return {'score': _small(score), 'score_without_interview_fails': _small(extra),
            'fails': _fails_table(records), 'limits': [f'a score on {marks["facts"]} facts', DROP_OUTS_LIMIT]}


def _blank_exam(name: str, version: str) -> dict:
    return {'exam': name, 'label': WEAK_LABEL if name == EXAM_OLD else EXAM_1_LABEL, 'frozen': False,
            'status': '', 'size': None, 'digest': None, 'frozen_at': None, 'key_check': None,
            'engine_version': version, 'refusal': None, 'cases_with_other_key_check': None,
            'validity': None, 'still_valid': None, 'valid_split': None, 'could_not_recompute_reasons': None,
            'qc_turned_to_pass': None, 'score': None,
            'score_without_interview_fails': None, 'fails': None, 'candidates': None,
            'known_limits': [WEAK_LABEL] if name == EXAM_OLD else []}


def _exam_refused(out: dict, code: str) -> dict:
    out.update(refusal=code, status=f'refused: {code}')
    return out


def _exam_missing(out: dict, pool: list, of: str) -> dict:
    """A normal run with no exam file: refused, never frozen; the candidate count says if a freeze could be."""
    out.update(refusal=EXAM_MISSING, candidates=len(pool), status=f'refused: {EXAM_MISSING} ({len(pool)}{of})')
    return out


def _validity(exam: dict, by_id: dict, shape: str):
    """``(counts, valid rows)`` of the listed cases for THIS run (E4), in the exam's order. First match
    wins: missing, no longer decided, decided again (another UTC instant than the stored one), context
    changed, could not recompute, evidence changed, else valid. Also the could-not-recompute count by the
    row's reason: validity comes from the fingerprint compare alone, never from the row's note."""
    counts, valid, reasons = dict.fromkeys(VALIDITY, 0), [], dict.fromkeys(RECOMPUTE_REASONS, 0)
    for application_id, stored in zip(exam['application_ids'], exam['decided_at']):
        row = by_id.get(application_id)
        if row is None:
            state = 'missing'
        elif row['when'] is None or not row['has_verdict']:
            state = 'no_longer_decided'
        elif row['when'] != _stored_time(stored):
            state = 'decided_again'
        elif row['shape'] != shape:
            state = 'context_changed'
        elif shape == FULL and row['recomputed'] is None:
            state = 'could_not_recompute'
            reasons[row['note']] += 1
        elif shape == FULL and row['recomputed'] != row['context']['fingerprint']:
            state = 'evidence_changed'
        else:
            state = 'valid'
            valid.append(row)
        counts[state] += 1
    return counts, valid, reasons


def _sit_exam(out: dict, exam: dict, by_id: dict, shape: str) -> dict:
    """Fill ``out`` with a frozen exam's header, its validity counts and the score of its valid cases.
    exam-1 only: the valid split (matched directly / recovered by twin) and the reasons counted."""
    out.update(frozen=True, status='frozen', size=exam['size'], digest=exam['digest'][:12],
               frozen_at=exam['frozen_at'], key_check=exam.get('key_check'))
    counts, valid, reasons = _validity(exam, by_id, shape)
    out.update(validity=counts, still_valid=f'{counts["valid"]} of {exam["size"]} still valid')
    if shape == FULL:
        twin = sum(1 for row in valid if row['note'] == RECOVERED_BY_TWIN)
        out.update(valid_split={'matched_directly': len(valid) - twin, 'recovered_by_twin': twin},
                   could_not_recompute_reasons=reasons)
    out['qc_turned_to_pass'] = sum(row['qc_turned'] for row in valid)
    scored = _exam_score(valid)
    out.update({k: scored[k] for k in ('score', 'score_without_interview_fails', 'fails')})
    out['known_limits'] = out['known_limits'] + scored['limits']
    return out


def _exam_1(pool, by_id, folder, key_is_blank, current_key_check, now, version, freeze) -> dict:
    out = _blank_exam(EXAM_1, version)
    exam, refusal = load_exam(folder, EXAM_1)
    if refusal:
        return _exam_refused(out, refusal)
    if exam is None and not freeze:
        return _exam_missing(out, pool, f' of {EXAM_1_SIZE} candidates')
    if exam is None and len(pool) < EXAM_1_SIZE:
        out['status'] = f'not frozen yet: {len(pool)} of {EXAM_1_SIZE}'
        return out
    if key_is_blank:
        return _exam_refused(out, KEY_BLANK)
    if exam is None:
        if current_key_check is None:
            return _exam_refused(out, KEY_CHECK_MISSING)
        chosen = sorted(pool, key=lambda r: (r['when'], r['id']))[:EXAM_1_SIZE]
        differ = sum(1 for r in chosen if r['context']['key_check'] != current_key_check)
        if differ:
            out['cases_with_other_key_check'] = differ
            mixed = len({r['context']['key_check'] for r in chosen}) > 1
            return _exam_refused(out, KEY_CHECKS_MIXED if mixed else CANDIDATES_NOT_CURRENT)
        exam, refusal = freeze_exam(folder, EXAM_1, [r['id'] for r in chosen], [r['when'] for r in chosen],
                                    now, current_key_check)
        if refusal:
            return _exam_refused(out, refusal)
    if current_key_check is None or current_key_check != exam['key_check']:
        return _exam_refused(out, KEY_CHECK_DIFFERS_EXAM)
    listed = [by_id[i] for i in exam['application_ids'] if i in by_id and by_id[i]['shape'] == FULL]
    differ = sum(1 for r in listed if r['context']['key_check'] != current_key_check)
    if differ:
        out['cases_with_other_key_check'] = differ
        return _exam_refused(out, KEY_CHECK_DIFFERS_CASES)
    return _sit_exam(out, exam, by_id, FULL)


def _exam_old(pool, by_id, folder, now, version, freeze) -> dict:
    out = _blank_exam(EXAM_OLD, version)
    exam, refusal = load_exam(folder, EXAM_OLD)
    if refusal:
        return _exam_refused(out, refusal)
    if exam is None and not freeze:
        return _exam_missing(out, pool, ' candidate cases')
    if exam is None:
        if not pool:
            out['status'] = 'not frozen yet: 0 cases'
            return out
        ordered = sorted(pool, key=lambda r: (r['when'], r['id']))
        exam, refusal = freeze_exam(folder, EXAM_OLD, [r['id'] for r in ordered], [r['when'] for r in ordered],
                                    now)
        if refusal:
            return _exam_refused(out, refusal)
    return _sit_exam(out, exam, by_id, EMPTY)


def run_human_lens(cases, *, exam_folder, key_is_blank: bool, current_key_check, now,
                   freeze: bool = False) -> dict:
    """Score each frozen exam. Only with ``freeze=True`` is a missing exam file frozen first (the only
    write); with ``freeze=False`` a missing file is EXAM_MISSING. Counts only: ``{engine_version,
    cases_read, not_decided, no_human_verdict, context_failed, context_failed_line, exams: {name:
    `_blank_exam` keys filled}}``. A refused exam-1 has no score; exam-old needs no key. A
    ``current_key_check`` text not of the one form (`is_key_check`) counts as none (None)."""
    if not isinstance(key_is_blank, bool):
        raise ValueError('key_is_blank must be True or False')
    if not isinstance(freeze, bool):
        raise ValueError('freeze must be True or False')
    if current_key_check is not None and not isinstance(current_key_check, str):
        raise ValueError('current_key_check must be text or None')
    current_key_check = current_key_check if is_key_check(current_key_check) else None
    _utc_text(now)
    rows = [_read_case(case) for case in cases]
    by_id = {}
    for row in rows:
        if row['id'] in by_id:
            raise BadCaseRow('application_id', 'repeats')
        by_id[row['id']] = row
    versions = {row['version'] for row in rows}
    if len(versions) > 1:
        raise BadCaseRow('engine_version', 'differs between cases')
    version = versions.pop() if versions else None
    entered = [r for r in rows if r['when'] is not None and r['has_verdict']]
    failed = sum(1 for r in entered if r['shape'] == FAILED)
    folder_refusal = exam_folder_refusal(exam_folder)   # once, before any load: a bad folder refuses both
    if folder_refusal:
        exams = {name: _exam_refused(_blank_exam(name, version), folder_refusal) for name in EXAM_NAMES}
    else:
        exams = {EXAM_1: _exam_1([r for r in entered if r['shape'] == FULL], by_id, exam_folder,
                                 key_is_blank, current_key_check, now, version, freeze),
                 EXAM_OLD: _exam_old([r for r in entered if r['shape'] == EMPTY], by_id, exam_folder, now,
                                     version, freeze)}
    return {'engine_version': version, 'cases_read': len(rows),
            'not_decided': sum(1 for r in rows if r['when'] is None),
            'no_human_verdict': sum(1 for r in rows if r['when'] is not None and not r['has_verdict']),
            'context_failed': failed, 'context_failed_line': f'{FAILED_CONTEXT_LINE}: {failed}',
            'exams': exams}
