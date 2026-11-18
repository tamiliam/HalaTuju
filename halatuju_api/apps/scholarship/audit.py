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

from zoneinfo import ZoneInfo

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
    per_fact: {fact: {decided, overrides}}, engine_versions: {version: applications}}`` plus the
    green / unsure counts (``overall``, ``fact_counts``, ``by_version``, ``by_month``,
    ``doubt_codes``; see ``_tally`` / ``_finish``). A record may also carry, as elements 4 and 5,
    ``verdict_decided_at`` (for ``by_month``) and the recorder (``decider_counts``).
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
    overall, fact_counts = _counts(), {f: _counts() for f in FACTS}
    by_version: dict = {}
    by_month: dict = {}
    doubt: dict = {}
    reasons = {f: _reason_block() for f in FACTS}
    for record in decided_records:
        ai_snapshot, officer_verdict = record[0], record[1]
        version = (record[2] if len(record) > 2 else '') or ''
        month = month_key(record[3] if len(record) > 3 else None)
        applications += 1
        engine_versions[version] = engine_versions.get(version, 0) + 1
        result = compute_overrides(ai_snapshot, officer_verdict)
        fact_decisions += result['decided_count']
        overrides += result['override_count']
        unresolved = _unresolved_map(ai_snapshot)
        for row in result['facts']:
            if row['decided']:
                per_fact[row['fact']]['decided'] += 1
            if row['overridden']:
                per_fact[row['fact']]['overrides'] += 1
            if not row['decided']:
                continue
            blocks = [overall, fact_counts[row['fact']], by_version.setdefault(version, _counts())]
            if month:
                blocks.append(by_month.setdefault(month, _counts()))
            for block in blocks:
                _tally(block, row['ai_pass'], row['officer'])
            if row['ai_pass'] and row['officer'] == 'fail':   # LL2: why a green fact was failed
                _tally_reason(reasons[row['fact']], officer_verdict, row['fact'])
            if not row['ai_pass']:
                for code in unresolved.get(row['fact'], ()):
                    entry = doubt.setdefault((row['fact'], code), {'passed': 0, 'failed': 0})
                    entry['passed' if row['officer'] == 'pass' else 'failed'] += 1
    rate = round(overrides / fact_decisions, 4) if fact_decisions else 0.0
    return {'applications': applications, 'fact_decisions': fact_decisions,
            'overrides': overrides, 'override_rate': rate, 'per_fact': per_fact,
            'engine_versions': engine_versions,
            'overall': _finish(overall),
            'fact_counts': {f: _finish(b) for f, b in fact_counts.items()},
            'by_version': {v: _finish(b) for v, b in by_version.items()},
            'by_month': {m: _finish(by_month[m]) for m in sorted(by_month)},
            'doubt_codes': _doubt_rows(doubt),
            'fail_reasons': {f: {c: b[c] for c in b if c != 'not_given'} for f, b in reasons.items()},
            'fail_reasons_not_given': {f: b['not_given'] for f, b in reasons.items()}}


def _reason_block() -> dict:
    from .fail_reasons import CODES   # in the function: fail_reasons imports this module
    return {**{c: 0 for c in CODES}, 'not_given': 0}


def _tally_reason(block: dict, officer_verdict, fact: str) -> None:
    """One green -> fail decision: its stored reason code, or 'not_given' (old rows, a dropped tap)."""
    from .fail_reasons import given
    block[given(officer_verdict, fact) or 'not_given'] += 1


# ── green / unsure counts (the AI prediction scoreboard) ─────────────────────────────────────────
#: A row whose denominator is under this many is flagged `few` — the page says "too few to judge".
#: ONE constant: the browser never decides what counts as few.
FEW_BELOW = 30
#: The month a decision belongs to is the Malaysian one (TD-209: never the UTC date).
_KL = ZoneInfo('Asia/Kuala_Lumpur')


def _counts() -> dict:
    return {'green': 0, 'green_failed': 0, 'unsure': 0, 'unsure_passed': 0}


def _tally(block: dict, green: bool, officer: str) -> None:
    """One DECIDED fact. ``green`` = the AI asserted it (``verified``); an undecided fact is never
    tallied here, the same convention as ``fact_decisions`` above."""
    if green:
        block['green'] += 1
        block['green_failed'] += officer == 'fail'
    else:
        block['unsure'] += 1
        block['unsure_passed'] += officer == 'pass'


def _finish(block: dict) -> dict:
    """Add what the browser shows without arithmetic: the two rates (rounded as ``override_rate``)
    and the ``few`` flags. ``green_fail_rate`` = green_failed / green; ``unsure_pass_rate`` =
    unsure_passed / unsure; ``few`` = the row's decided total is under ``FEW_BELOW``."""
    g, u = block['green'], block['unsure']
    block['green_agreed'] = g - block['green_failed']
    block['green_agree_rate'] = round(block['green_agreed'] / g, 4) if g else 0.0
    block['green_fail_rate'] = round(block['green_failed'] / g, 4) if g else 0.0
    block['unsure_pass_rate'] = round(block['unsure_passed'] / u, 4) if u else 0.0
    block['few_green'] = g < FEW_BELOW
    block['few_unsure'] = u < FEW_BELOW
    block['few'] = g + u < FEW_BELOW
    return block


def month_key(decided_at):
    """``YYYY-MM`` of an aware instant in Malaysia time, or None (no stamp given / naive)."""
    if decided_at is None or decided_at.tzinfo is None:
        return None
    local = decided_at.astimezone(_KL)
    return f'{local.year:04d}-{local.month:02d}'


def _unresolved_map(ai_verdict_snapshot) -> dict:
    """fact → the codes of its ``unresolved`` items in a stored snapshot."""
    out = {}
    for f in (ai_verdict_snapshot or []):
        if isinstance(f, dict) and f.get('fact'):
            codes = [u.get('code') for u in (f.get('unresolved') or [])
                     if isinstance(u, dict) and u.get('code')]
            out[f['fact']] = codes
    return out


def _doubt_rows(doubt: dict) -> list:
    rows = []
    for (fact, code), n in doubt.items():
        total = n['passed'] + n['failed']
        rows.append({'fact': fact, 'code': code, 'passed': n['passed'], 'failed': n['failed'],
                     'total': total,
                     'pass_rate': round(n['passed'] / total, 4) if total else 0.0,
                     'fail_rate': round(n['failed'] / total, 4) if total else 0.0,
                     'few': total < FEW_BELOW})
    rows.sort(key=lambda r: (-r['passed'], -r['total'], r['fact'], r['code']))
    return rows


def decider_counts(decided_records) -> dict:
    """The four counts per recorder, keyed by the record's 5th element (``verdict_decided_by``).
    Records without one are skipped. Pure; the caller turns the key into a person (and never ships
    the key itself): ``{key: {applications, green, green_failed, unsure, unsure_passed, …rates…}}``."""
    out: dict = {}
    for record in decided_records:
        key = record[4] if len(record) > 4 else None
        if not key:
            continue
        block = out.setdefault(key, {'applications': 0, **_counts()})
        block['applications'] += 1
        for row in compute_overrides(record[0], record[1])['facts']:
            if row['decided']:
                _tally(block, row['ai_pass'], row['officer'])
    return {k: _finish(b) for k, b in out.items()}
