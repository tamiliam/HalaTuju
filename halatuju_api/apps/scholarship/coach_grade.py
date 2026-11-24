"""LL5 phase A - the monthly score and the coach grade. Pure, beside `ai_score.py`: no ORM, no AI call,
no settings read. Server only: no page and no job calls it yet (the replay job imports it lazily in a
later phase).

The PLAYER is the model (engine) version, scored in marks. The COACH is the learning loop, graded on
NEW cases only: each version is compared with the version before it, each on its OWN decided cases.

INPUT: the record shape F4's `prediction_metrics.metrics` sends `ai_score.score_marks`, a 6-tuple
``(ai_verdict_snapshot, officer_verdict, ai_verdict_engine_version, verdict_decided_at,
verdict_decided_by, id)``. ``verdict_decided_by`` and ``id`` are never read past the door and never
appear in an output: the output holds version labels, month labels, counts and fixed codes only.

THE MIRROR CLAIM, in three parts:

* VALUES - every mark is `ai_score`'s: each group of records goes through `ai_score.score_marks`, the
  percent is `ai_score.percent`, and a band is read by `ai_score`'s own band reader (which is
  `fact_bands.fact_band`). No points table, no band rule and no rounding is written here.
* ROWS - decided records only. This module itself drops any record whose ``verdict_decided_at`` is
  None, whatever the caller sent. A reject before interview carries no ``verdict_decided_at``, so it is
  out here exactly as it is out of F4's score.
* EDGE - a cell (one version, one Malaysian month) with fewer than ``CELL_MIN_FACTS`` marked facts shows
  only ``too_few`` (no %, no points, no outcome split). A record with no engine version goes to the
  ``UNKNOWN_VERSION`` bucket: it gets a monthly line but is never graded. A decided fact with no band in
  its snapshot is ``not_scored`` (counted, never marked), as in `ai_score`.

THE COACH GRADE, per pair of consecutive versions (ordered by each version's first decided instant), in
this order:

1. ``not_enough`` when either side has fewer than ``COACH_MIN_FACTS`` marked facts.
2. Guard 1, coverage must not drop: coverage = marked facts whose band is not Unsure / marked facts.
3. Guard 2, generous-wrong must not rise: generous-wrong = marked facts the AI showed Certain or
   Probable that the reviewer failed / marked facts.
   Either guard broken = ``fail`` whatever the score, naming the guard(s).
4. Else ``pass`` if the score went up, ``fail`` with ``score_not_up`` if not (a tie is not up).

Every comparison is an exact fraction (integer cross-multiplication); the % shown is `ai_score.percent`.

"DOCUMENTS ONLY" (``leave_out_reasons``, default empty = the plain score): a Fail whose recorded reason
(`fail_reasons.given`) is in the set is left out entirely, counting in neither points nor best, in the
monthly score and the coach grade alike. ``DOCUMENTS_ONLY`` leaves out ``interview_differs`` (the AI
could not know it from documents). The owner has not yet decided whether the report shows that line.

drift-test: halatuju_api/apps/scholarship/tests/test_coach_grade.py
"""
from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

from . import ai_score
from .audit import FACTS
from .fact_bands import CERTAIN, PROBABLE, UNSURE
from .fail_reasons import CODES as FAIL_REASON_CODES
from .fail_reasons import INTERVIEW_DIFFERS, given

MALAYSIA = ZoneInfo('Asia/Kuala_Lumpur')

#: Owner ruling, request #69: nothing below 5 answers is shown.
CELL_MIN_FACTS = 5
#: PROVISIONAL - the owner has not confirmed this number. Change it on this one line only.
COACH_MIN_FACTS = 40

UNKNOWN_VERSION = '(unknown version)'
DOCUMENTS_ONLY = (INTERVIEW_DIFFERS,)

PASS, FAIL, NOT_ENOUGH = 'pass', 'fail', 'not_enough'
GRADES = (PASS, FAIL, NOT_ENOUGH)
PREVIOUS_TOO_FEW = 'previous_too_few'
NEW_TOO_FEW = 'new_too_few'
COVERAGE_DROPPED = 'coverage_dropped'
GENEROUS_WRONG_ROSE = 'generous_wrong_rose'
SCORE_UP = 'score_up'
SCORE_NOT_UP = 'score_not_up'
#: The closed set of reason codes a coach grade can carry.
REASON_CODES = (PREVIOUS_TOO_FEW, NEW_TOO_FEW, COVERAGE_DROPPED, GENEROUS_WRONG_ROSE, SCORE_UP,
                SCORE_NOT_UP)

_GENEROUS_BANDS = frozenset({CERTAIN, PROBABLE})


def _left_out_codes(leave_out_reasons) -> frozenset:
    codes = frozenset(leave_out_reasons or ())
    unknown = codes - set(FAIL_REASON_CODES)
    if unknown:
        raise ValueError('leave_out_reasons holds a code that is not a Fail reason')
    return codes


def _without_left_out(verdict, leave_out: frozenset):
    """``(verdict, facts left out)``: a copy without each Fail whose recorded reason is left out."""
    if not leave_out or not isinstance(verdict, dict):
        return verdict, 0
    kept, dropped = dict(verdict), 0
    for fact in FACTS:
        if kept.get(fact) == 'fail' and given(verdict, fact) in leave_out:
            del kept[fact]
            dropped += 1
    return kept, dropped


def _malaysia_month(instant) -> str:
    """``YYYY-MM`` of an aware instant in Malaysia time."""
    local = instant.astimezone(MALAYSIA)
    return f'{local.year:04d}-{local.month:02d}'


def _decided_rows(records, leave_out: frozenset) -> list:
    """``(instant, version or None, month, (snapshot, verdict, version), left out)`` per DECIDED record.
    Only the first three fields of a record go on; who decided and the row id stop here."""
    rows = []
    for record in records:
        instant = record[3] if len(record) > 3 else None
        if instant is None:
            continue
        if instant.tzinfo is None:   # a naive instant is read as UTC (what Django stores)
            instant = instant.replace(tzinfo=datetime.timezone.utc)
        version = record[2] or None
        verdict, dropped = _without_left_out(record[1], leave_out)
        rows.append((instant, version, _malaysia_month(instant), (record[0], verdict, version or ''),
                     dropped))
    return rows


def _tally_cell(group: list) -> dict:
    """The full figures of one group of decided rows, every mark through `ai_score`."""
    marked = [row[3] for row in group]
    marks = ai_score.score_marks(marked)
    covered = generous_wrong = 0
    for snapshot, verdict, _version in marked:
        bands = ai_score._bands(snapshot)
        verdict = verdict if isinstance(verdict, dict) else {}
        for fact in FACTS:
            officer, band = verdict.get(fact), bands.get(fact)
            if officer not in ('pass', 'fail') or band is None:
                continue
            covered += band != UNSURE
            generous_wrong += officer == 'fail' and band in _GENEROUS_BANDS
    return {'facts': marks['facts'], 'points': marks['points'], 'best': marks['best'],
            'score_pct': marks['score_pct'], 'not_scored': marks['not_scored'],
            'left_out': sum(row[4] for row in group),
            'outcomes': {o: marks[o] for o in ai_score.OUTCOMES},
            'covered': covered, 'generous_wrong': generous_wrong}


def _month_view(version, month: str, tally: dict) -> dict:
    cell = {'version': version or UNKNOWN_VERSION, 'unknown_version': version is None, 'month': month}
    if tally['facts'] < CELL_MIN_FACTS:
        cell['too_few'] = True
        return cell
    cell['too_few'] = False
    for key in ('facts', 'points', 'best', 'score_pct', 'not_scored', 'left_out', 'outcomes'):
        cell[key] = tally[key]
    return cell


def _side_view(version: str, tally: dict) -> dict:
    side = {'version': version}
    if tally['facts'] < CELL_MIN_FACTS:
        side['too_few'] = True
        return side
    side.update({'too_few': False, 'facts': tally['facts'], 'score_pct': tally['score_pct'],
                 'coverage': {'count': tally['covered'], 'of': tally['facts']},
                 'generous_wrong': {'count': tally['generous_wrong'], 'of': tally['facts']}})
    return side


def _coach_verdict(prev: dict, new: dict):
    """``(grade, reason codes)`` for one pair of version tallies, checks in the docstring's order."""
    reasons = []
    if prev['facts'] < COACH_MIN_FACTS:
        reasons.append(PREVIOUS_TOO_FEW)
    if new['facts'] < COACH_MIN_FACTS:
        reasons.append(NEW_TOO_FEW)
    if reasons:
        return NOT_ENOUGH, reasons
    # a/b < c/d  <=>  a*d < c*b, all denominators positive (both sides have >= COACH_MIN_FACTS facts)
    if new['covered'] * prev['facts'] < prev['covered'] * new['facts']:
        reasons.append(COVERAGE_DROPPED)
    if new['generous_wrong'] * prev['facts'] > prev['generous_wrong'] * new['facts']:
        reasons.append(GENEROUS_WRONG_ROSE)
    if reasons:
        return FAIL, reasons
    if new['points'] * prev['best'] > prev['points'] * new['best']:
        return PASS, [SCORE_UP]
    return FAIL, [SCORE_NOT_UP]


def coach_report(records, leave_out_reasons=()) -> dict:
    """The monthly score and the coach grade over ``records`` (F4's 6-tuples), JSON-safe, counts only:

    ``{cell_min_facts, coach_min_facts, left_out_reasons: [code], decided_records,
    months: [{version, unknown_version, month, too_few, (facts, points, best, score_pct, not_scored,
    left_out, outcomes: {outcome: count}) when not too_few}],
    coach: [{previous: side, new: side, grade, reasons: [code]}]}`` where a side is
    ``{version, too_few, (facts, score_pct, coverage: {count, of}, generous_wrong: {count, of}) when not
    too_few}``. ``months`` runs version by first decided instant (unknown version last), then month;
    ``coach`` pairs consecutive KNOWN versions in that order. ``leave_out_reasons`` - see the docstring
    ("documents only"); an unknown code raises ValueError."""
    leave_out = _left_out_codes(leave_out_reasons)
    rows = _decided_rows(records, leave_out)
    first_seen, cells, by_version = {}, {}, {}
    for row in rows:
        instant, version, month = row[0], row[1], row[2]
        if version not in first_seen or instant < first_seen[version]:
            first_seen[version] = instant
        cells.setdefault((version, month), []).append(row)
        by_version.setdefault(version, []).append(row)
    order = sorted(first_seen, key=lambda v: (v is None, first_seen[v], v or ''))
    months = [_month_view(version, month, _tally_cell(cells[(version, month)]))
              for version in order
              for month in sorted(m for v, m in cells if v == version)]
    known = [v for v in order if v is not None]
    tallies = {v: _tally_cell(by_version[v]) for v in known}
    coach = []
    for prev, new in zip(known, known[1:]):
        grade, reasons = _coach_verdict(tallies[prev], tallies[new])
        coach.append({'previous': _side_view(prev, tallies[prev]), 'new': _side_view(new, tallies[new]),
                      'grade': grade, 'reasons': reasons})
    return {'cell_min_facts': CELL_MIN_FACTS, 'coach_min_facts': COACH_MIN_FACTS,
            'left_out_reasons': sorted(leave_out), 'decided_records': len(rows),
            'months': months, 'coach': coach}
