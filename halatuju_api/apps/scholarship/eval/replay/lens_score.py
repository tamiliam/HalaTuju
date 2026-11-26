"""The human lens's SCORE of an exam's valid cases (moved out of `lens_human`, unchanged). PURE: no
database, network, clock or environment read; the scoring modules are imported inside functions only.
Every mark goes through the house points (`ai_score`). `lens_human._sit_exam` is the only caller.
"""
from __future__ import annotations

from . import lens_human as L


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
    codes = [c for c in fail_reasons.CODES if c != fail_reasons.INTERVIEW_DIFFERS] + [L.NOT_GIVEN]
    table = {band: dict.fromkeys(codes, 0) for band in BANDS}
    interview = dict.fromkeys(BANDS, 0)
    total = 0
    for snapshot, verdict, _version in records:
        for fact, band, officer in ai_score.decided_facts(snapshot, verdict):
            if band is None or officer != 'fail':
                continue
            total += 1
            reason = fail_reasons.given(verdict, fact) or L.NOT_GIVEN
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


def exam_score(rows: list) -> dict:
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
    extra = {'label': L.EXTRA_LINE_LABEL, 'facts': other['facts'], 'points': other['points'],
             'best': other['best'], 'score_pct': other['score_pct'], 'left_out': left_out}
    return {'score': _small(score), 'score_without_interview_fails': _small(extra),
            'fails': _fails_table(records), 'limits': [f'a score on {marks["facts"]} facts', L.DROP_OUTS_LIMIT]}
