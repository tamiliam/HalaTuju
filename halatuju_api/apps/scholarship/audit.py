"""
Verdict audit / override metrics — Verification-verdict Sprint 5.

Pure + deterministic (no Django ORM, no LLM): given the AI's four-fact verdict
snapshot (``build_verdict`` output, stored at decision time) and the officer's
own per-fact decision, work out where the human *overrode* the machine. The
roll-up over many decided applications is the "how good is the AI" signal the
plan calls for — an honest override rate, computed from stored evidence.

The trust model (verdict_engine): the AI only **asserts** a fact green when its
status is ``verified`` (it under-claims everything else — review/recommend/gap —
to a human). So an *override* is any fact where the officer's pass/fail decision
disagrees with whether the AI asserted it:

    AI asserted (verified) + officer FAIL   → override (AI was too generous)
    AI did NOT assert      + officer PASS    → override (AI was too cautious)

Facts the officer left undecided (no pass/fail) are not counted — you can't
override a decision you didn't make.
"""
from __future__ import annotations

FACTS = ('identity', 'academic', 'pathway', 'income')

# The only verdict status where the AI ASSERTS the fact is good (under-claim design).
_AI_ASSERTS = {'verified'}
# Officer per-fact decisions that count as a made decision.
_OFFICER_DECISIONS = {'pass', 'fail'}


def ai_fact_pass(status) -> bool:
    """True iff the AI asserted this fact green (``verified``)."""
    return (status or '') in _AI_ASSERTS


def _snapshot_status_map(ai_verdict_snapshot) -> dict:
    """fact → status from a stored ``build_verdict`` snapshot (a list of dicts)."""
    out = {}
    for f in (ai_verdict_snapshot or []):
        if isinstance(f, dict) and f.get('fact'):
            out[f['fact']] = f.get('status', '')
    return out


def compute_overrides(ai_verdict_snapshot, officer_verdict) -> dict:
    """Per-fact comparison of the AI's assertion vs the officer's decision.

    Returns ``{facts: [{fact, ai_status, ai_pass, officer, decided, overridden}],
    override_count, decided_count}`` — one row per fact, in fixed order. Pure.
    """
    statuses = _snapshot_status_map(ai_verdict_snapshot)
    ov = officer_verdict if isinstance(officer_verdict, dict) else {}
    rows = []
    override_count = decided_count = 0
    for fact in FACTS:
        ai_status = statuses.get(fact, '')
        ai_pass = ai_fact_pass(ai_status)
        officer = (ov.get(fact) or '')
        decided = officer in _OFFICER_DECISIONS
        overridden = decided and (ai_pass != (officer == 'pass'))
        if decided:
            decided_count += 1
        if overridden:
            override_count += 1
        rows.append({
            'fact': fact,
            'ai_status': ai_status,
            'ai_pass': ai_pass,
            'officer': officer,
            'decided': decided,
            'overridden': overridden,
        })
    return {'facts': rows, 'override_count': override_count,
            'decided_count': decided_count}


def override_metrics(decided_records) -> dict:
    """Aggregate override stats across decided applications. ``decided_records`` is an iterable of
    ``(ai_verdict_snapshot, officer_verdict)`` pairs, or ``(…, …, engine_version)`` TRIPLES (already
    filtered to verdict_decided_at IS NOT NULL by the caller).

    Returns ``{applications, fact_decisions, overrides, override_rate,
    per_fact: {fact: {decided, overrides}}, engine_versions: {version: applications}}``.
    ``override_rate`` is fact-level (overrides / fact_decisions), 0.0 when nothing is decided.

    ⚠ ``engine_versions`` IS THE HONESTY FIELD, and it is why the rate above may not mean what a
    reader assumes. Every prediction here came from ``verdict_engine``, and that engine CHANGES —
    `_declared_pathway` changed on 2026-09-10, for one. Until 2026-09-11 nothing recorded which
    generation produced a snapshot, so this roll-up averaged them all as if they were one model.
    A caller that shows `override_rate` must show this beside it when it holds more than one key.

    ⚠ THE RATE IS STILL BLENDED, DELIBERATELY (owner, 2026-09-11: *"A now, and B in future"*).
    Splitting the roll-up per version was the alternative; with 88 decisions banked under
    `pre-versioning` and a handful under anything newer, per-version rates would be noise for
    months. This surfaces the mix NOW and leaves the split for when there is enough to compare.

    Tuples stay accepted so existing callers and fixtures are not a rewrite; a 2-tuple counts its
    application under ``''`` (unknown), which reads as "this caller did not say".
    """
    per_fact = {f: {'decided': 0, 'overrides': 0} for f in FACTS}
    engine_versions: dict = {}
    applications = fact_decisions = overrides = 0
    for record in decided_records:
        ai_snapshot, officer_verdict = record[0], record[1]
        version = record[2] if len(record) > 2 else ''
        applications += 1
        engine_versions[version or ''] = engine_versions.get(version or '', 0) + 1
        result = compute_overrides(ai_snapshot, officer_verdict)
        fact_decisions += result['decided_count']
        overrides += result['override_count']
        for row in result['facts']:
            if row['decided']:
                per_fact[row['fact']]['decided'] += 1
            if row['overridden']:
                per_fact[row['fact']]['overrides'] += 1
    rate = round(overrides / fact_decisions, 4) if fact_decisions else 0.0
    return {'applications': applications, 'fact_decisions': fact_decisions,
            'overrides': overrides, 'override_rate': rate, 'per_fact': per_fact,
            'engine_versions': engine_versions}
