"""OCR-first Gate 1: may ONE lane (a document type + issuer) be read by rules alone? (S0, 2026-11-18)

Roadmap: ``docs/plans/ocr-first-roadmap.md``, section 2 ("The proposed THRESHOLD rule"). A PURE
function: counts in, a verdict and the reasons out. It never reads a file, a model or the database,
so every later sprint (S1 onwards) and the dry-run tool (``eval/ocr_first_dryrun.py``) share ONE rule.

A lane passes only when ALL of these hold on the HELD-OUT letters:

  1. SAMPLE      at least ``MIN_DOCS`` (20) documents the rules LOCKED and answered (not merely 20 in
                 the lane). A smaller lane stays on AI.
  2. AGREEMENT   at least ``MIN_AGREEMENT_PERCENT`` (98) per cent of the core-field cells the rules
                 answered are exact or blank-correct against the hand-checked answer. Compared in
                 whole numbers (``core_right * 100 >= 98 * core_total``), so 97.9 fails and 98.0
                 passes with no rounding doubt.
  3. NO WRONG    zero ``wrong`` on name, IC, institution and course (the programme). A blank is
                 acceptable (the document then goes to the AI); a wrong value is not.
  4. COURSE      the catalogue course match is never wrong: "a wrong course_id is worse than none".
                 A course match that was NOT RUN (``course_match_wrong=None``) fails: unmeasured is not safe.

Gate 2 (is THIS document trusted?) is per document and lives with the reader, not here.
Each lane also has its own switch that starts OFF; this function only says whether the lane has
EARNED the right to be switched on, never switches it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

MIN_DOCS = 20
MIN_AGREEMENT_PERCENT = 98
#: The fields where one WRONG fails the lane. ``programme`` is the course (the stream, for STPM /
#: matriculation); the catalogue match is guarded separately by ``course_match_wrong``.
GUARDED_FIELDS = ('name', 'nric', 'institution', 'programme')


@dataclass(frozen=True)
class GateResult:
    """The verdict and every reason it failed (empty when it passed)."""
    passed: bool
    reasons: tuple


def lane_gate(*, locked: int, core_right: int, core_total: int,
              wrong: Mapping[str, int] | None = None, course_match_wrong: int | None = 0) -> GateResult:
    """Gate 1 for one lane, from the held-out counts.

    locked              held-out documents in the lane the rules locked and answered
    core_right          core-field cells the rules answered that are exact or blank_correct
    core_total          core-field cells the rules answered (agreement is right / total)
    wrong               ``{field: count}`` of ``wrong`` outcomes; only ``GUARDED_FIELDS`` gate
    course_match_wrong  catalogue matches that set a course the answer does not name; None = the
                        course match was not run (fails)
    """
    reasons = []
    if locked < MIN_DOCS:
        reasons.append(f'only {locked} held-out documents locked by the rules (need {MIN_DOCS})')
    if core_total <= 0:
        reasons.append('the rules answered no core field')
    elif core_right * 100 < MIN_AGREEMENT_PERCENT * core_total:
        reasons.append(f'agreement {100.0 * core_right / core_total:.1f}% '
                       f'(need {MIN_AGREEMENT_PERCENT}%)')
    wrong = wrong or {}
    for field in GUARDED_FIELDS:
        if wrong.get(field, 0) > 0:
            reasons.append(f'{wrong[field]} wrong {field}')
    if course_match_wrong is None:
        reasons.append('course match not run')
    elif course_match_wrong > 0:
        reasons.append(f'{course_match_wrong} wrong course match')
    return GateResult(passed=not reasons, reasons=tuple(reasons))
