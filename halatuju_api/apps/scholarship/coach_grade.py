"""LL5 phase A - the monthly score and the coach grade. Pure, beside `ai_score.py`: no ORM, no AI call,
no settings read. Server only: no page and no job calls it yet (the replay job imports it lazily in a
later phase).

The PLAYER is the model (engine) version, scored in marks. The COACH is the learning loop, graded on
NEW cases only: each version is compared with the gradeable version before it, each on its OWN decided
cases.

INPUT: the record shape F4's `prediction_metrics.metrics` sends `ai_score.score_marks`, a 6-tuple
``(ai_verdict_snapshot, officer_verdict, ai_verdict_engine_version, verdict_decided_at,
verdict_decided_by, id)``. ``verdict_decided_by`` and ``id`` are never read past the door and never
appear in an output: the output holds version labels, month labels, counts and fixed codes only.

THE MIRROR CLAIM, in three parts:

* VALUES - every mark is `ai_score`'s: each group of records goes through `ai_score.score_marks`, the
  percent is `ai_score.percent`, the points of one fact are `ai_score.mark`, and which facts count (with
  their band) is read by `ai_score.decided_facts`, the reader `score_marks` itself uses. No points
  table, no band rule and no rounding is written here.
* ROWS - decided records only. This module itself drops any record whose ``verdict_decided_at`` is
  None, whatever the caller sent. A reject before interview carries no ``verdict_decided_at``, so it is
  out here exactly as it is out of F4's score.
* EDGE - a decided fact with no band in its snapshot is ``not_scored`` (counted, never marked), as in
  `ai_score`.

MALFORMED RECORDS never raise. A record whose ``verdict_decided_at`` is set but is not a datetime, or
whose facts the shared reader cannot read (TypeError, ValueError, AttributeError or KeyError, for
example a number where the snapshot or its evidence should be), is left out and only counted, in
``malformed_records``: no id, no text.

THE FLOOR OF 5 (``CELL_MIN_FACTS``) IS A SMALL-NUMBER GUARD, NOT A SECRECY RULE. A month cell or a side
with fewer than 5 marked facts shows ``too_few`` and no figures, so that nobody reads a percent off a
handful of answers. It does not hide those answers: a small group's figures CAN be worked out by
subtraction (a side minus its other month cells, the plain line minus the ``without_left_out`` line, one
run of the report minus an earlier run), and that is accepted. The readers are super users and the AI
team, who can already open every case and every reviewer answer. The live staff card (F4) already shows
figures for groups of 1 to 4 to a WIDER set of readers (every org-wide admin). Request #69 (the sponsor's
volunteer figures, "nothing below 5 answers") is the model for the number 5 only. If this report is ever
shown to a wider audience, the floor must be redone as a privacy rule first.

VERSIONS. A label is text stripped of whitespace. A label that is not text, is blank, or is exactly the
display label ``UNKNOWN_VERSION`` is the unknown version; the back-fill stamp
`verdict_engine.PRE_VERSIONING` (matched exactly after the strip: labels are stamped by server code, so
no case folding) keeps its own label. Both are UNKNOWN: they get month cells with ``unknown_version:
True``, sort after the known versions, and are never graded nor waiting. Versions run by their first
decided instant over all their decided records, ties by the NATURAL order of the label ('2026-11-15.9'
before '2026-11-15.10'; a digit run of any length is ordered without turning it into a number). A
version with no marked fact at all gets no cell, no side and no place in the chain; it is counted in
``versions_without_marks``.

MONTH CELLS: one per (version, calendar month in Malaysia time) that holds at least one marked fact.
Under ``CELL_MIN_FACTS`` it is ``too_few`` with no figures. Nothing is folded or merged.

A SIDE is a whole version (all its months, all its marked facts); under ``CELL_MIN_FACTS`` it shows
only ``{version, too_few: True}``.

THE COACH CHAIN: the KNOWN versions with at least ``COACH_MIN_FACTS`` marked facts ("gradeable"), in
version order. Each consecutive pair is graded. A change counts only when it is bigger than luck can
explain (the NOISE MARGIN, owner ruling R1 of 24 Nov 2026):

1. Guard 1, coverage must not drop: coverage = marked facts whose band is not Unsure / marked facts.
   BROKEN only when the new share is lower AND a one-sided Fisher exact test says a count this low on
   the new side, or lower, would happen by chance less than ``GUARD_ALPHA`` of the time.
2. Guard 2, generous-wrong must not rise: generous-wrong = marked facts the AI showed Certain or
   Probable that the reviewer failed / marked facts. BROKEN only when the new share is higher AND the
   chance of a count this high on the new side, or higher, is less than ``GUARD_ALPHA``.
   Either guard broken = ``fail`` whatever the score, naming the guard(s). A guard that moves the right
   way never breaks.
3. Else the score (mean points per marked fact): when the two means differ by more than ``SCORE_Z``
   standard errors, up = ``pass`` (``score_up``) and down = ``fail`` (``score_down``); otherwise
   ``no_change`` (``no_clear_change``).

Every test is exact (integers and fractions, no float, no square root); the % shown is
`ai_score.percent`. A pair's ``skipped_versions`` counts the known versions with marks, under the coach
floor, that lie between its two sides. Every known version with marks under the floor is listed in
``waiting``.

ONE STRUCTURE. Which versions are known, which cells exist, which cells and sides are ``too_few``, the
order, ``waiting``, the chain, ``skipped_versions``, ``versions_without_marks``, every grade and every
reason code come from the PLAIN marked facts and the PLAIN score. ``leave_out_reasons`` never changes
any of them.

THE EXTRA LINE (``leave_out_reasons``, default empty). The AI reads the documents and also asks the
student questions through Check 2 (owner ruling R2 of 24 Nov 2026), so the grade and both guards count
every Fail, whatever its reason. The extra line only lets the owner see the score both ways: every
month cell and every side that shows figures gains ``without_left_out``, the same figures scored by
`ai_score` on a copy of each verdict without its left-out Fails. A Fail is left out when its recorded
reason (`fail_reasons.given`) is in the set and its fact has a band (it would have been scored);
``left_out`` counts those. A Fail with such a reason on a fact with NO band stays ``not_scored`` and is
not counted. Under ``CELL_MIN_FACTS`` facts left to score the line is ``{too_few: True}``. The line has
no coverage, generous-wrong or grade. ``INTERVIEW_FAILS`` leaves out ``interview_differs``; the report
will label that line "score without interview Fails".

drift-test: halatuju_api/apps/scholarship/tests/test_coach_grade.py
"""
from __future__ import annotations

import datetime
import re
from fractions import Fraction
from math import comb
from zoneinfo import ZoneInfo

from . import ai_score
from .fact_bands import CERTAIN, PROBABLE, UNSURE
from .fail_reasons import CODES as FAIL_REASON_CODES
from .fail_reasons import INTERVIEW_DIFFERS, given

MALAYSIA = ZoneInfo('Asia/Kuala_Lumpur')

#: A small-number guard, not a secrecy rule (module docstring). The number is request #69's.
CELL_MIN_FACTS = 5
#: FINAL (owner ruling R3, 24 Nov 2026): a side needs 40 marked facts to be graded.
COACH_MIN_FACTS = 40
#: The noise margin: the lead's design under the owner's ruling R1 (24 Nov 2026). A guard breaks only
#: when a one-sided Fisher exact test gives a chance below 1 in 20; the score moves only when the two
#: means differ by more than 2 standard errors.
GUARD_ALPHA = Fraction(1, 20)
SCORE_Z = 2

UNKNOWN_VERSION = '(unknown version)'
INTERVIEW_FAILS = (INTERVIEW_DIFFERS,)

PASS, FAIL, NO_CHANGE = 'pass', 'fail', 'no_change'
GRADES = (PASS, FAIL, NO_CHANGE)
COVERAGE_DROPPED = 'coverage_dropped'
GENEROUS_WRONG_ROSE = 'generous_wrong_rose'
SCORE_UP = 'score_up'
NO_CLEAR_CHANGE = 'no_clear_change'
SCORE_DOWN = 'score_down'
#: The closed set of reason codes a coach grade can carry.
REASON_CODES = (COVERAGE_DROPPED, GENEROUS_WRONG_ROSE, SCORE_UP, NO_CLEAR_CHANGE, SCORE_DOWN)
_SCORE_GRADE = {SCORE_UP: PASS, NO_CLEAR_CHANGE: NO_CHANGE, SCORE_DOWN: FAIL}

_GENEROUS_BANDS = frozenset({CERTAIN, PROBABLE})
_DIGITS = re.compile(r'(\d+)')
#: What the shared reader can raise on a malformed record; caught around ONE record only.
_READ_ERRORS = (TypeError, ValueError, AttributeError, KeyError)
_MALFORMED = object()


def _left_out_codes(leave_out_reasons) -> frozenset:
    """The left-out Fail reasons. Anything that is not an iterable of known codes raises ValueError."""
    if leave_out_reasons is None:
        return frozenset()
    if isinstance(leave_out_reasons, (str, bytes)):
        raise ValueError('leave_out_reasons must be a set of Fail reason codes, not one text')
    try:
        codes = list(leave_out_reasons)
    except TypeError:
        raise ValueError('leave_out_reasons must be a set of Fail reason codes') from None
    if not all(isinstance(code, str) for code in codes):
        raise ValueError('leave_out_reasons must hold text codes only')
    codes = frozenset(codes)
    if codes - set(FAIL_REASON_CODES):
        raise ValueError('leave_out_reasons holds a code that is not a Fail reason')
    return codes


def _verdict_without_left_out(snapshot, verdict, leave_out: frozenset):
    """``(verdict, facts left out)``: a copy without each Fail whose recorded reason is left out, on a
    fact that has a band. A Fail with no band stays (it is ``not_scored``, never left out)."""
    if not leave_out or not isinstance(verdict, dict):
        return verdict, 0
    kept, dropped = dict(verdict), 0
    for fact, band, officer in ai_score.decided_facts(snapshot, verdict):
        if officer == 'fail' and band is not None and given(verdict, fact) in leave_out:
            del kept[fact]
            dropped += 1
    return kept, dropped


def _version_key(raw):
    """``(label, unknown)`` of a stored engine version. Not text, blank, or exactly the display label
    ``UNKNOWN_VERSION`` is the unknown version."""
    # In the function: `verdict_engine` imports the genuineness package; this module stays light.
    from .verdict_engine import PRE_VERSIONING
    label = raw.strip() if isinstance(raw, str) else ''
    if not label or label == UNKNOWN_VERSION:
        return UNKNOWN_VERSION, True
    return label, label == PRE_VERSIONING


def _natural(label: str) -> tuple:
    """A sort key reading each run of digits by its value: '.9' before '.10'. No `int()`: a run is
    ordered by its length, then its text, after its leading zeros are stripped (any length is safe)."""
    # split() with one group: the odd places are the digit runs, the even places the text between
    def part(i, p):
        if i % 2:
            digits = p.lstrip('0')
            return 0, len(digits), digits
        return 1, 0, p
    return tuple(part(i, p) for i, p in enumerate(_DIGITS.split(label))), label


def _malaysia_month(instant) -> str:
    """``YYYY-MM`` of an aware instant in Malaysia time."""
    local = instant.astimezone(MALAYSIA)
    return f'{local.year:04d}-{local.month:02d}'


def _decided_row(record):
    """One record as a row, None when undecided, ``_MALFORMED`` when its instant is not a datetime. The
    shared reader runs once here, so a record whose facts cannot be read raises here and only here."""
    instant = record[3] if len(record) > 3 else None
    if instant is None:
        return None
    if not isinstance(instant, datetime.datetime):
        return _MALFORMED
    if instant.tzinfo is None:   # a naive instant is read as UTC (what Django stores)
        instant = instant.replace(tzinfo=datetime.timezone.utc)
    snapshot, verdict = record[0], record[1]
    ai_score.decided_facts(snapshot, verdict)
    key = _version_key(record[2])
    return instant, key, _malaysia_month(instant), (snapshot, verdict, key[0])


def _decided_rows(records):
    """``([(instant, (label, unknown), month, (snapshot, verdict, label))], malformed count)``, one row
    per DECIDED record. Only the first three fields of a record go on; who decided and the row id stop
    here."""
    rows, malformed = [], 0
    for record in records:
        try:
            row = _decided_row(record)
        except _READ_ERRORS:
            row = _MALFORMED
        if row is _MALFORMED:
            malformed += 1
        elif row is not None:
            rows.append(row)
    return rows, malformed


def _plain_tally(group: list) -> dict:
    """The PLAIN figures of one group of decided rows, every mark through `ai_score`. ``squares`` is the
    sum of each marked fact's points squared (the spread the score margin needs)."""
    marked = [row[3] for row in group]
    marks = ai_score.score_marks(marked)
    covered = generous_wrong = squares = 0
    for snapshot, verdict, _version in marked:
        for _fact, band, officer in ai_score.decided_facts(snapshot, verdict):
            if band is None:
                continue
            covered += band != UNSURE
            generous_wrong += officer == 'fail' and band in _GENEROUS_BANDS
            squares += ai_score.mark(band, officer)[0] ** 2
    return {'facts': marks['facts'], 'points': marks['points'], 'best': marks['best'],
            'score_pct': marks['score_pct'], 'not_scored': marks['not_scored'],
            'outcomes': {o: marks[o] for o in ai_score.OUTCOMES},
            'covered': covered, 'generous_wrong': generous_wrong, 'squares': squares}


def _without_left_out_line(group: list, leave_out: frozenset) -> dict:
    """The extra line of one group: the same rows, each verdict without its left-out Fails."""
    kept, left_out = [], 0
    for _instant, _key, _month, (snapshot, verdict, label) in group:
        verdict, dropped = _verdict_without_left_out(snapshot, verdict, leave_out)
        kept.append((snapshot, verdict, label))
        left_out += dropped
    marks = ai_score.score_marks(kept)
    if marks['facts'] < CELL_MIN_FACTS:
        return {'too_few': True}
    return {'too_few': False, 'facts': marks['facts'], 'points': marks['points'], 'best': marks['best'],
            'score_pct': marks['score_pct'], 'left_out': left_out}


def _month_cells(key, by_month: dict, leave_out: frozenset) -> list:
    """One cell per month of one version that holds a marked fact, months in order."""
    label, unknown = key
    cells = []
    for month in sorted(by_month):
        tally = _plain_tally(by_month[month])
        if not tally['facts']:
            continue
        cell = {'version': label, 'unknown_version': unknown, 'month': month,
                'too_few': tally['facts'] < CELL_MIN_FACTS}
        if not cell['too_few']:
            for name in ('facts', 'points', 'best', 'score_pct', 'not_scored', 'outcomes'):
                cell[name] = tally[name]
            if leave_out:
                cell['without_left_out'] = _without_left_out_line(by_month[month], leave_out)
        cells.append(cell)
    return cells


def _side_view(version: str, tally: dict, line) -> dict:
    """A whole version; ``line`` is its ``without_left_out`` line, or None when nothing is left out."""
    if tally['facts'] < CELL_MIN_FACTS:
        return {'version': version, 'too_few': True}
    side = {'version': version, 'too_few': False, 'facts': tally['facts'], 'score_pct': tally['score_pct'],
            'coverage': {'count': tally['covered'], 'of': tally['facts']},
            'generous_wrong': {'count': tally['generous_wrong'], 'of': tally['facts']}}
    if line is not None:
        side['without_left_out'] = dict(line)
    return side


def _new_side_tail(prev_count: int, prev_of: int, new_count: int, new_of: int, low: bool) -> Fraction:
    """One-sided Fisher exact test, exact: with both sides' sizes and the total count fixed, the chance
    that the NEW side holds ``new_count`` or fewer (``low``) or ``new_count`` or more (not ``low``)."""
    total = prev_count + new_count
    least, most = max(0, total - prev_of), min(new_of, total)
    counts = range(least, new_count + 1) if low else range(new_count, most + 1)
    tail = sum(comb(new_of, x) * comb(prev_of, total - x) for x in counts)
    return Fraction(tail, comb(prev_of + new_of, total))


def _guards_broken(prev: dict, new: dict) -> list:
    """The guards a pair CLEARLY broke. a/b < c/d  <=>  a*d < c*b (both sides are gradeable)."""
    broken = []
    if (new['covered'] * prev['facts'] < prev['covered'] * new['facts']
            and _new_side_tail(prev['covered'], prev['facts'], new['covered'], new['facts'],
                               low=True) < GUARD_ALPHA):
        broken.append(COVERAGE_DROPPED)
    if (new['generous_wrong'] * prev['facts'] > prev['generous_wrong'] * new['facts']
            and _new_side_tail(prev['generous_wrong'], prev['facts'], new['generous_wrong'], new['facts'],
                               low=False) < GUARD_ALPHA):
        broken.append(GENEROUS_WRONG_ROSE)
    return broken


def _score_change(prev: dict, new: dict) -> str:
    """``score_up``, ``score_down`` or ``no_clear_change``: clear when (m2 - m1)^2 > SCORE_Z^2 x (v1/n1
    + v2/n2), means m and sample variances v (divisor n - 1) of the per-fact points, all exact."""
    def mean_and_spread(tally):
        n = tally['facts']
        mean = Fraction(tally['points'], n)
        variance = (tally['squares'] - n * mean * mean) / (n - 1)
        return mean, variance / n
    prev_mean, prev_spread = mean_and_spread(prev)
    new_mean, new_spread = mean_and_spread(new)
    if (new_mean - prev_mean) ** 2 <= SCORE_Z ** 2 * (prev_spread + new_spread):
        return NO_CLEAR_CHANGE   # with both variances zero, any difference at all is clear
    return SCORE_UP if new_mean > prev_mean else SCORE_DOWN


def _coach_verdict(prev: dict, new: dict):
    """``(grade, reason codes)`` for one pair of GRADEABLE version tallies, checks in the docstring's
    order: a clearly broken guard fails whatever the score."""
    broken = _guards_broken(prev, new)
    if broken:
        return FAIL, broken
    change = _score_change(prev, new)
    return _SCORE_GRADE[change], [change]


def _coach_chain(known: list, tallies: dict, lines: dict):
    """``(coach pairs, waiting sides)`` over the known versions with marks, in version order. The grade
    reads only the plain ``tallies``; ``lines`` (version: extra line or None) is display."""
    def side(label):
        return _side_view(label, tallies[label], lines[label])

    coach, waiting, previous, skipped = [], [], None, 0
    for label in known:
        if tallies[label]['facts'] < COACH_MIN_FACTS:
            waiting.append(side(label))
            skipped += 1
            continue
        if previous is not None:
            grade, reasons = _coach_verdict(tallies[previous], tallies[label])
            coach.append({'previous': side(previous), 'new': side(label), 'grade': grade,
                          'reasons': reasons, 'skipped_versions': skipped})
        previous, skipped = label, 0
    return coach, waiting


def coach_report(records, leave_out_reasons=()) -> dict:
    """The monthly score and the coach grade over ``records`` (F4's 6-tuples), JSON-safe, counts only:

    ``{cell_min_facts, coach_min_facts, guard_alpha: {count, of}, score_z, left_out_reasons: [code],
    decided_records, malformed_records, versions_without_marks, months: [cell], coach: [{previous: side,
    new: side, grade, reasons: [code], skipped_versions}], waiting: [side]}``.

    A cell is ``{version, unknown_version, month, too_few}`` plus, when not too_few, ``facts, points,
    best, score_pct, not_scored, outcomes: {outcome: count}`` and (only when ``leave_out_reasons`` is not
    empty) ``without_left_out``. A side is ``{version, too_few}`` plus, when not too_few, ``facts,
    score_pct, coverage: {count, of}, generous_wrong: {count, of}`` and the same ``without_left_out``. A
    ``without_left_out`` line is ``{too_few: True}`` or ``{too_few: False, facts, points, best,
    score_pct, left_out}``. ``months`` runs version by version in version order (unknown versions last),
    then month. ``leave_out_reasons`` that is not an iterable of known codes raises ValueError."""
    leave_out = _left_out_codes(leave_out_reasons)
    rows, malformed = _decided_rows(records)
    first_seen, months_of = {}, {}
    for row in rows:
        instant, key, month = row[0], row[1], row[2]
        if key not in first_seen or instant < first_seen[key]:
            first_seen[key] = instant
        months_of.setdefault(key, {}).setdefault(month, []).append(row)
    version_rows = {key: [row for group in months_of[key].values() for row in group] for key in first_seen}
    tallies = {key: _plain_tally(version_rows[key]) for key in first_seen}
    marked = [key for key in first_seen if tallies[key]['facts'] > 0]
    order = sorted(marked, key=lambda k: (k[1], first_seen[k], _natural(k[0])))
    months = [cell for key in order for cell in _month_cells(key, months_of[key], leave_out)]
    known = [key for key in order if not key[1]]
    lines = {key[0]: _without_left_out_line(version_rows[key], leave_out) if leave_out else None
             for key in known}
    coach, waiting = _coach_chain([key[0] for key in known], {key[0]: tallies[key] for key in known}, lines)
    return {'cell_min_facts': CELL_MIN_FACTS, 'coach_min_facts': COACH_MIN_FACTS,
            'guard_alpha': {'count': GUARD_ALPHA.numerator, 'of': GUARD_ALPHA.denominator},
            'score_z': SCORE_Z, 'left_out_reasons': sorted(leave_out), 'decided_records': len(rows),
            'malformed_records': malformed, 'versions_without_marks': len(first_seen) - len(marked),
            'months': months, 'coach': coach, 'waiting': waiting}
