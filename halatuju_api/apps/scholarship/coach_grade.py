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
  percent is `ai_score.percent`, and which facts count (with their band) is read by
  `ai_score.decided_facts`, the reader `score_marks` itself uses. No points table, no band rule and no
  rounding is written here.
* ROWS - decided records only. This module itself drops any record whose ``verdict_decided_at`` is
  None, whatever the caller sent. A reject before interview carries no ``verdict_decided_at``, so it is
  out here exactly as it is out of F4's score.
* EDGE - a decided fact with no band in its snapshot is ``not_scored`` (counted, never marked), as in
  `ai_score`.

THE FLOOR OF 5 (``CELL_MIN_FACTS``) IS A SMALL-NUMBER GUARD, NOT A SECRECY RULE. A month cell or a side
with fewer than 5 marked facts shows ``too_few`` and no figures, so that nobody reads a percent off a
handful of answers. It does not hide those answers: a small group's figures CAN be worked out by
subtraction (a side minus its other month cells, the plain line minus the "documents only" line, one
run of the report minus an earlier run), and that is accepted. The readers are super users and the AI
team, who can already open every case and every reviewer answer (the live staff card shows the same
readers figures for groups of 1 to 4). Request #69 (the sponsor's volunteer figures, "nothing below 5
answers") is the model for the number 5 only. If this report is ever shown to a wider audience, the
floor must be redone as a privacy rule first.

VERSIONS. A label is text stripped of whitespace. A label that is not text, or is blank, is
``UNKNOWN_VERSION``; the back-fill stamp `verdict_engine.PRE_VERSIONING` (matched exactly after the
strip: labels are stamped by server code, so no case folding) keeps its own label. Both are UNKNOWN:
they get month cells with ``unknown_version: True``, sort after the known versions, and are never graded
nor waiting. Versions run by their first decided instant over all their decided records, ties by the
NATURAL order of the label ('2026-11-15.9' before '2026-11-15.10'). A version with no marked fact at
all gets no cell, no side and no place in the chain; it is counted in ``versions_without_marks``.

MONTH CELLS: one per (version, calendar month in Malaysia time) that holds at least one marked fact.
Under ``CELL_MIN_FACTS`` it is ``too_few`` with no figures. Nothing is folded or merged.

A SIDE is a whole version (all its months, all its marked facts); under ``CELL_MIN_FACTS`` it shows
only ``{version, too_few: True}``.

THE COACH CHAIN: the KNOWN versions with at least ``COACH_MIN_FACTS`` marked facts ("gradeable"), in
version order. Each consecutive pair is graded, in this order:

1. Guard 1, coverage must not drop: coverage = marked facts whose band is not Unsure / marked facts.
2. Guard 2, generous-wrong must not rise: generous-wrong = marked facts the AI showed Certain or
   Probable that the reviewer failed / marked facts.
   Either guard broken = ``fail`` whatever the score, naming the guard(s).
3. Else the score: up = ``pass`` (``score_up``), exactly equal = ``no_change`` (``score_same``), down =
   ``fail`` (``score_down``).

Every comparison is an exact fraction (integer cross-multiplication); the % shown is `ai_score.percent`.
A pair's ``skipped_versions`` counts the known versions with marks, under the coach floor, that lie
between its two sides. Every known version with marks under the floor is listed in ``waiting``.

ONE STRUCTURE. Which versions are known, which cells exist, which cells and sides are ``too_few``, the
order, ``waiting``, the chain, ``skipped_versions``, ``versions_without_marks``, every grade and every
reason code come from the PLAIN marked facts and the PLAIN score. ``leave_out_reasons`` never changes
any of them.

"DOCUMENTS ONLY" (``leave_out_reasons``, default empty) is an EXTRA LINE, not a second report: every
month cell and every side that shows figures gains ``documents_only``, scored by `ai_score` on a copy of
each verdict without its left-out Fails. A Fail is left out when its recorded reason
(`fail_reasons.given`) is in the set and its fact has a band (it would have been scored); ``left_out``
counts those. A Fail with such a reason on a fact with NO band stays ``not_scored`` and is not counted.
Under ``CELL_MIN_FACTS`` facts left to score the line is ``{too_few: True}``. There is no
documents-only coverage, generous-wrong or grade. ``DOCUMENTS_ONLY`` leaves out ``interview_differs``
(the AI could not know it from documents). The owner has not yet decided whether the report shows that
line.

drift-test: halatuju_api/apps/scholarship/tests/test_coach_grade.py
"""
from __future__ import annotations

import datetime
import re
from zoneinfo import ZoneInfo

from . import ai_score
from .fact_bands import CERTAIN, PROBABLE, UNSURE
from .fail_reasons import CODES as FAIL_REASON_CODES
from .fail_reasons import INTERVIEW_DIFFERS, given

MALAYSIA = ZoneInfo('Asia/Kuala_Lumpur')

#: A small-number guard, not a secrecy rule (module docstring). The number is request #69's.
CELL_MIN_FACTS = 5
#: PROVISIONAL - the owner has not confirmed this number. Change it on this one line only.
COACH_MIN_FACTS = 40

UNKNOWN_VERSION = '(unknown version)'
DOCUMENTS_ONLY = (INTERVIEW_DIFFERS,)

PASS, FAIL, NO_CHANGE = 'pass', 'fail', 'no_change'
GRADES = (PASS, FAIL, NO_CHANGE)
COVERAGE_DROPPED = 'coverage_dropped'
GENEROUS_WRONG_ROSE = 'generous_wrong_rose'
SCORE_UP = 'score_up'
SCORE_SAME = 'score_same'
SCORE_DOWN = 'score_down'
#: The closed set of reason codes a coach grade can carry.
REASON_CODES = (COVERAGE_DROPPED, GENEROUS_WRONG_ROSE, SCORE_UP, SCORE_SAME, SCORE_DOWN)

_GENEROUS_BANDS = frozenset({CERTAIN, PROBABLE})
_DIGITS = re.compile(r'(\d+)')


def _left_out_codes(leave_out_reasons) -> frozenset:
    codes = frozenset(leave_out_reasons or ())
    unknown = codes - set(FAIL_REASON_CODES)
    if unknown:
        raise ValueError('leave_out_reasons holds a code that is not a Fail reason')
    return codes


def _without_left_out(snapshot, verdict, leave_out: frozenset):
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
    """``(label, unknown)`` of a stored engine version. Not text, or blank, is the unknown version."""
    # In the function: `verdict_engine` imports the genuineness package; this module stays light.
    from .verdict_engine import PRE_VERSIONING
    label = raw.strip() if isinstance(raw, str) else ''
    if not label:
        return UNKNOWN_VERSION, True
    return label, label == PRE_VERSIONING


def _natural(label: str) -> tuple:
    """A sort key reading each run of digits as a number: '.9' before '.10'."""
    # split() with one group: the odd places are the digit runs, the even places the text between
    parts = tuple((0, int(p), '') if i % 2 else (1, 0, p) for i, p in enumerate(_DIGITS.split(label)))
    return parts, label


def _malaysia_month(instant) -> str:
    """``YYYY-MM`` of an aware instant in Malaysia time."""
    local = instant.astimezone(MALAYSIA)
    return f'{local.year:04d}-{local.month:02d}'


def _decided_rows(records) -> list:
    """``(instant, (label, unknown), month, (snapshot, verdict, label))`` per DECIDED record. Only the
    first three fields of a record go on; who decided and the row id stop here."""
    rows = []
    for record in records:
        instant = record[3] if len(record) > 3 else None
        if instant is None:
            continue
        if instant.tzinfo is None:   # a naive instant is read as UTC (what Django stores)
            instant = instant.replace(tzinfo=datetime.timezone.utc)
        key = _version_key(record[2])
        rows.append((instant, key, _malaysia_month(instant), (record[0], record[1], key[0])))
    return rows


def _plain_tally(group: list) -> dict:
    """The PLAIN figures of one group of decided rows, every mark through `ai_score`."""
    marked = [row[3] for row in group]
    marks = ai_score.score_marks(marked)
    covered = generous_wrong = 0
    for snapshot, verdict, _version in marked:
        for _fact, band, officer in ai_score.decided_facts(snapshot, verdict):
            if band is None:
                continue
            covered += band != UNSURE
            generous_wrong += officer == 'fail' and band in _GENEROUS_BANDS
    return {'facts': marks['facts'], 'points': marks['points'], 'best': marks['best'],
            'score_pct': marks['score_pct'], 'not_scored': marks['not_scored'],
            'outcomes': {o: marks[o] for o in ai_score.OUTCOMES},
            'covered': covered, 'generous_wrong': generous_wrong}


def _documents_only(group: list, leave_out: frozenset) -> dict:
    """The "documents only" line of one group: the same rows, each verdict without its left-out Fails."""
    kept, left_out = [], 0
    for _instant, _key, _month, (snapshot, verdict, label) in group:
        verdict, dropped = _without_left_out(snapshot, verdict, leave_out)
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
                cell['documents_only'] = _documents_only(by_month[month], leave_out)
        cells.append(cell)
    return cells


def _side_view(version: str, tally: dict, documents_only) -> dict:
    """A whole version; ``documents_only`` is its line, or None when nothing is left out."""
    if tally['facts'] < CELL_MIN_FACTS:
        return {'version': version, 'too_few': True}
    side = {'version': version, 'too_few': False, 'facts': tally['facts'], 'score_pct': tally['score_pct'],
            'coverage': {'count': tally['covered'], 'of': tally['facts']},
            'generous_wrong': {'count': tally['generous_wrong'], 'of': tally['facts']}}
    if documents_only is not None:
        side['documents_only'] = dict(documents_only)
    return side


def _coach_verdict(prev: dict, new: dict):
    """``(grade, reason codes)`` for one pair of GRADEABLE version tallies, checks in the docstring's
    order. a/b < c/d  <=>  a*d < c*b, all denominators positive (both sides are gradeable)."""
    reasons = []
    if new['covered'] * prev['facts'] < prev['covered'] * new['facts']:
        reasons.append(COVERAGE_DROPPED)
    if new['generous_wrong'] * prev['facts'] > prev['generous_wrong'] * new['facts']:
        reasons.append(GENEROUS_WRONG_ROSE)
    if reasons:
        return FAIL, reasons
    new_score, prev_score = new['points'] * prev['best'], prev['points'] * new['best']
    if new_score > prev_score:
        return PASS, [SCORE_UP]
    if new_score == prev_score:
        return NO_CHANGE, [SCORE_SAME]
    return FAIL, [SCORE_DOWN]


def _coach_chain(known: list, tallies: dict, lines: dict):
    """``(coach pairs, waiting sides)`` over the known versions with marks, in version order. The grade
    reads only the plain ``tallies``; ``lines`` (version: documents-only line or None) is display."""
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

    ``{cell_min_facts, coach_min_facts, left_out_reasons: [code], decided_records,
    versions_without_marks, months: [cell], coach: [{previous: side, new: side, grade, reasons: [code],
    skipped_versions}], waiting: [side]}``.

    A cell is ``{version, unknown_version, month, too_few}`` plus, when not too_few, ``facts, points,
    best, score_pct, not_scored, outcomes: {outcome: count}`` and (only when ``leave_out_reasons`` is not
    empty) ``documents_only``. A side is ``{version, too_few}`` plus, when not too_few, ``facts,
    score_pct, coverage: {count, of}, generous_wrong: {count, of}`` and the same ``documents_only``. A
    ``documents_only`` line is ``{too_few: True}`` or ``{too_few: False, facts, points, best, score_pct,
    left_out}``. ``months`` runs version by version in version order (unknown versions last), then
    month. An unknown ``leave_out_reasons`` code raises ValueError."""
    leave_out = _left_out_codes(leave_out_reasons)
    rows = _decided_rows(records)
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
    lines = {key[0]: _documents_only(version_rows[key], leave_out) if leave_out else None for key in known}
    coach, waiting = _coach_chain([key[0] for key in known], {key[0]: tallies[key] for key in known}, lines)
    return {'cell_min_facts': CELL_MIN_FACTS, 'coach_min_facts': COACH_MIN_FACTS,
            'left_out_reasons': sorted(leave_out), 'decided_records': len(rows),
            'versions_without_marks': len(first_seen) - len(marked),
            'months': months, 'coach': coach, 'waiting': waiting}
