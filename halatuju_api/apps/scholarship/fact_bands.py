"""The AI Prediction band of each verdict fact - ONE home, on the server (sprint F2 of the fix plan).

The case page shows, per fact (Identity, Academic, Pathway, Income), the band the AI predicts in five
words: Certain / Probable / Unsure / Can't verify / Rule not met. Until F2 that band was computed only
in the browser (`cockpitVerdict.ts` `factTileTone` / `factBandKey`), while the grey "AI Prediction" line
and the QC floor read the RAW engine status, so the three could disagree. Now this module is the one
answer: the case detail serves it (`ai_fact_bands`), the tiles and the grey line render it, the QC
accept refuses on it (`floor_facts`), and the LL5 replay tool imports it.

Pure: it reads a `build_verdict` result (a list of fact dicts) and nothing else. No database write,
no AI call. `application_fact_bands` is the one helper that runs the engine, for a caller that holds
only the application.

The band keys are the web's i18n keys (`admin.scholarship.verdict.band.<key>`):

    certain       green  the checks passed (status `verified`)
    probable      blue   `review` backed by at least one REAL verified value
    unsure        amber  `review` with no real value, `recommend`, or the other-kind cap
    unverifiable  red    `gap` (missing / unreadable evidence), or higher results unreadable
    ruleNotMet    red    any status carrying a confident disqualifier (a gift rule is broken)

Display rules carried over exactly (owner rulings 2026-11-17, #804, IPTS 2026-11-18), in precedence:
a confident disqualifier beats everything (`ruleNotMet`); an unreadable higher-results slip is red
(`unverifiable`) on any non-gap status; an other-kind slip (`higher_results_kind_differs` /
`higher_results_is_spm`) caps a verified or review fact at `unsure`; "Probable needs a green": a review
fact whose evidence is only soft signals or the "not checked" note is `unsure`.
"""
from __future__ import annotations

from .award import CONFIDENT_DISQUALIFIERS

CERTAIN = 'certain'
PROBABLE = 'probable'
UNSURE = 'unsure'
UNVERIFIABLE = 'unverifiable'
RULE_NOT_MET = 'ruleNotMet'
BANDS = (CERTAIN, PROBABLE, UNSURE, UNVERIFIABLE, RULE_NOT_MET)

# Evidence codes that are NOT a verified value - a self-declaration or a soft signal. "Probable" must
# rest on at least one real verified value, so a fact backed only by these (or by nothing) is "Unsure".
# PINNED to the engine: every `_item('<code>', ...)  # SOFT` line in `verdict_engine.py` is here and
# nothing else is (`tests/test_fact_bands.py`, the drift guard that was the web's
# `soft-evidence-drift.test.ts` until F2).
SOFT_EVIDENCE = frozenset({
    'pathway_declared',               # the student's own declared pathway (unverified)
    'utility_percapita_b40',          # soft income proxy from the utility bills
    'utility_percapita_high',
    'utility_hardship',
    'unemployment_epf_corroborated',  # Phase 2B: EPF (all-zeros/lapsed) hinting unemployment
    'household_size_confirm',         # Phase 2C: described people > stated household size
})

# Display-only "not proof": the note that genuineness was not checked says nothing is verified. Kept
# apart from SOFT_EVIDENCE, which is pinned to the engine's `# SOFT` markers.
HIGHER_RESULTS_NOT_CHECKED = 'higher_results_not_checked'
NOT_PROOF_EVIDENCE = frozenset({HIGHER_RESULTS_NOT_CHECKED})
HIGHER_RESULTS_UNREADABLE = 'higher_results_unreadable'
HIGHER_RESULTS_KIND_CODES = frozenset({'higher_results_kind_differs', 'higher_results_is_spm'})

_DISQUALIFIERS = frozenset(CONFIDENT_DISQUALIFIERS)


def _codes(items) -> set:
    return {it.get('code') for it in (items or []) if isinstance(it, dict)}


def has_rule_not_met(fact) -> bool:
    """True when the fact carries a confident disqualifier (a broken gift rule), whatever its status."""
    return bool(_codes(fact.get('unresolved')) & _DISQUALIFIERS)


def fact_band(fact) -> str:
    """The band key of ONE `build_verdict` fact dict (see the module docstring)."""
    unresolved = _codes(fact.get('unresolved'))
    status = fact.get('status')
    if unresolved & _DISQUALIFIERS:
        return RULE_NOT_MET
    if status != 'gap' and HIGHER_RESULTS_UNREADABLE in unresolved:
        return UNVERIFIABLE
    kind_differs = bool(unresolved & HIGHER_RESULTS_KIND_CODES)
    if status == 'verified':
        return UNSURE if kind_differs else CERTAIN
    if status == 'recommend':
        return UNSURE
    if status == 'review':
        has_verified = any(
            e.get('code') not in SOFT_EVIDENCE and e.get('code') not in NOT_PROOF_EVIDENCE
            for e in (fact.get('evidence') or []) if isinstance(e, dict))
        return PROBABLE if has_verified and not kind_differs else UNSURE
    return UNVERIFIABLE   # gap, or any status the engine does not send


def fact_bands(verdict) -> dict:
    """``{fact: band}`` for a `build_verdict` result (a list of fact dicts), in its order."""
    return {f['fact']: fact_band(f) for f in (verdict or []) if isinstance(f, dict) and f.get('fact')}


def application_fact_bands(application) -> dict:
    """``{fact: band}`` for an application, running the deterministic verdict engine (no AI call)."""
    from .verdict_engine import build_verdict
    return fact_bands(build_verdict(application))


def floor_facts(verdict) -> list:
    """The facts that stop a QC accept of a Recommend (`verdict_gap_floor`), in verdict order: every
    fact whose raw status is 'gap' (V5 #5) and every fact whose band is Rule not met even when its
    status is not 'gap' (I-10, owner decision D1 = A, 2026-11-21). A QC or super may pass the floor
    only with a recorded reason. Birth state joins at the caller (`views_admin.verdict`)."""
    return [f['fact'] for f in (verdict or [])
            if isinstance(f, dict) and (f.get('status') == 'gap' or fact_band(f) == RULE_NOT_MET)]
