"""The AI score — how good the AI's prediction was, in MARKS (sprint F4 of the fix plan, owner design
2026-11-23). Pure: no ORM, no AI call. `prediction_metrics.metrics` feeds it the decided records.

Each DECIDED fact (the reviewer pressed Pass or Fail) is marked by the band the AI showed AT DECISION
TIME (`fact_bands.fact_band` of the stored `ai_verdict_snapshot`, the same five words the case page
showed) against the reviewer's pass / fail:

    band            pass   fail
    Certain          +2    -10
    Probable         +1     -3
    Unsure            0      0
    Can't verify     -1     +1
    Rule not met    -10     +2

The ten cells fall into five OUTCOMES: right_sure (+2), right_leaning (+1), unsure (0), wrong_leaning
(-3 / -1), wrong_sure (-10). ``score_pct = points / best`` with ``best = +2 x facts marked`` (an Unsure
fact counts in best: sitting on the fence is not free), rounded to a whole percent half away from zero.
It CAN go below 0%. 100% = sure and right on every fact; 0% = no better than Unsure on every fact.

NOT SCORED: a decided fact whose snapshot has no entry for it (a decision recorded before the snapshot
existed, or a malformed row). Counted in ``not_scored``, never in the marks.

⚠ THE CALLER SENDS ONLY RECORDED DECISIONS (`verdict_decided_at` set). A reject before interview writes
its four facts onto the case without that stamp, and onto its `declined` activity row; neither reaches
here, so the learning loop never learns from them.

Where points were lost: for a lost point on a reviewer FAIL the reason is the reviewer's own Fail
reason (`fail:<code>`, `fail:not_given` for old rows); on a reviewer PASS it is what the AI said
(`pass:ruleNotMet`, `pass:unverifiable`). The browser turns the key into words.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .audit import FACTS
from .fact_bands import CERTAIN, PROBABLE, RULE_NOT_MET, UNSURE, UNVERIFIABLE, fact_band

POINTS = {
    (CERTAIN, 'pass'): 2, (CERTAIN, 'fail'): -10,
    (PROBABLE, 'pass'): 1, (PROBABLE, 'fail'): -3,
    (UNSURE, 'pass'): 0, (UNSURE, 'fail'): 0,
    (UNVERIFIABLE, 'pass'): -1, (UNVERIFIABLE, 'fail'): 1,
    (RULE_NOT_MET, 'pass'): -10, (RULE_NOT_MET, 'fail'): 2,
}
OUTCOMES = ('right_sure', 'right_leaning', 'unsure', 'wrong_leaning', 'wrong_sure')
OUTCOME = {
    (CERTAIN, 'pass'): 'right_sure', (RULE_NOT_MET, 'fail'): 'right_sure',
    (PROBABLE, 'pass'): 'right_leaning', (UNVERIFIABLE, 'fail'): 'right_leaning',
    (UNSURE, 'pass'): 'unsure', (UNSURE, 'fail'): 'unsure',
    (PROBABLE, 'fail'): 'wrong_leaning', (UNVERIFIABLE, 'pass'): 'wrong_leaning',
    (CERTAIN, 'fail'): 'wrong_sure', (RULE_NOT_MET, 'pass'): 'wrong_sure',
}
BEST_PER_FACT = 2
TOP_REASONS = 2


def mark(band: str, officer: str):
    """``(points, outcome)`` for one decided fact."""
    return POINTS[(band, officer)], OUTCOME[(band, officer)]


def percent(points: int, best: int):
    """``points / best`` as a whole percent, half away from zero; None when nothing was marked."""
    if not best:
        return None
    return int((Decimal(points) * 100 / Decimal(best)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def reason_key(band: str, officer: str, officer_verdict, fact: str) -> str:
    """The key of a LOST point: the reviewer's Fail reason, or what the AI said on a pass."""
    if officer == 'fail':
        from .fail_reasons import given
        return f'fail:{given(officer_verdict, fact) or "not_given"}'
    return f'pass:{band}'


def _mark_tally() -> dict:
    return {'facts': 0, 'points': 0, 'lost': 0, **{o: 0 for o in OUTCOMES}}


def _close_tally(block: dict) -> dict:
    block['best'] = BEST_PER_FACT * block['facts']
    block['score_pct'] = percent(block['points'], block['best'])
    return block


def _bands(snapshot) -> dict:
    return {f['fact']: fact_band(f) for f in (snapshot or [])
            if isinstance(f, dict) and isinstance(f.get('fact'), str) and f['fact']}


def decided_facts(snapshot, officer_verdict) -> list:
    """``[(fact, band or None, 'pass' | 'fail')]`` for each fact of ONE record the reviewer passed or
    failed, in `FACTS` order; band None = not scored (no snapshot entry). The one reader of which facts
    count: `score_marks` reads it, and so does `coach_grade`, so the two cannot drift."""
    verdict = officer_verdict if isinstance(officer_verdict, dict) else {}
    bands = _bands(snapshot)
    return [(fact, bands.get(fact), verdict[fact])
            for fact in FACTS if verdict.get(fact) in ('pass', 'fail')]


def score_marks(records) -> dict:
    """The marks over ``records``: ``(ai_verdict_snapshot, officer_verdict, engine_version, …)``
    tuples of RECORDED decisions. Returns ``{facts, points, best, score_pct, lost, outcomes counts,
    not_scored, most_lost: {fact, points} | None, by_fact: {fact: block + top_reasons}, by_version:
    [block + version]}``; ``by_version`` is for the AI team only (the caller decides who gets it)."""
    total, by_fact = _mark_tally(), {f: _mark_tally() for f in FACTS}
    reasons = {f: {} for f in FACTS}
    by_version: dict = {}
    not_scored = 0
    for record in records:
        snapshot, verdict = record[0], record[1]
        version = (record[2] if len(record) > 2 else '') or ''
        for fact, band, officer in decided_facts(snapshot, verdict):
            if band is None:
                not_scored += 1
                continue
            points, outcome = mark(band, officer)
            for block in (total, by_fact[fact], by_version.setdefault(version, _mark_tally())):
                block['facts'] += 1
                block['points'] += points
                block[outcome] += 1
                if points < 0:
                    block['lost'] += points
            if points < 0:
                key = reason_key(band, officer, verdict, fact)
                reasons[fact][key] = reasons[fact].get(key, 0) + points
    for fact in FACTS:
        ranked = sorted(reasons[fact].items(), key=lambda kv: (kv[1], kv[0]))
        by_fact[fact]['top_reasons'] = [{'key': k, 'points': p} for k, p in ranked[:TOP_REASONS]]
        _close_tally(by_fact[fact])
    worst = min(FACTS, key=lambda f: (by_fact[f]['lost'], FACTS.index(f)))
    out = _close_tally(total)
    out['not_scored'] = not_scored
    out['most_lost'] = ({'fact': worst, 'points': by_fact[worst]['lost']}
                        if by_fact[worst]['lost'] < 0 else None)
    out['by_fact'] = by_fact
    out['by_version'] = [{'version': v, **_close_tally(by_version[v])} for v in sorted(by_version)]
    return out
