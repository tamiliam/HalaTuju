"""Check-2 case summary — a short, prescriptive briefing that "talks to the reviewer".

The deterministic verdict (verdict_engine) decides the band and the items; this module only
NARRATES that structured verdict as a 2-4 sentence case, so the officer AUDITS a reasoned call
instead of assembling a bullet list. It NEVER computes or changes the verdict — the LLM is fed
the already-decided band + glossed items and told to narrate faithfully (docs/scholarship/
str-proof-spec.md §4; the two-persona split — Check 2 is the firm fiscal steward).

Grounding: the summary is built ONLY from the structured verdict. The LLM is instructed to use
only the facts/figures/names given and never to invent or change the band. Cached per
(application, verdict-signature) so it runs at verdict-time, not on every cockpit open. Flag-gated
by ``VERDICT_CASE_SUMMARY_ENABLED`` (dark by default).
"""
import hashlib
import json
import logging

from django.conf import settings
from django.core.cache import cache

from .verdict_engine import build_verdict
from .profile_engine import _call_gemini_text

logger = logging.getLogger(__name__)

# Bump when the prompt or gloss changes so cached summaries regenerate.
CASE_SUMMARY_VERSION = '2026-07-01.1'

# ── Band label — MUST mirror officerCockpit.factTileTone + TONE_BAND_KEY (halatuju-web).
# A divergence would make the summary state a different band than the tile shows. Keep in step.
_SOFT_EVIDENCE = frozenset({
    'pathway_declared', 'utility_percapita_b40', 'utility_percapita_high', 'utility_hardship',
})


def _fact_band(fact):
    """Certain / Probable / Unsure / Can't-verify — the tile's band for this fact."""
    status = fact.get('status')
    if status == 'verified':
        return 'Certain'
    if status == 'recommend':
        return 'Unsure'
    if status == 'review':
        # Probable needs a green — ≥1 verified value, not just a soft/declared signal.
        has_green = any(e['code'] not in _SOFT_EVIDENCE for e in fact.get('evidence', []))
        return 'Probable' if has_green else 'Unsure'
    return "Can't verify"          # gap / unknown


# ── Item gloss — concise English per verdict item code (income covered thoroughly; other
# facts fall back to a humanised code). This is the grounding the LLM narrates; keep it factual
# and short (the model writes the prose, this only states the fact). {params} are interpolated.
_CODE_GLOSS = {
    # STR (status-specific)
    'str_not_current': {
        'wrong_type': 'the document in the STR slot is NOT an STR — it does not count as STR proof',
        'rejected': 'the STR application was rejected (Ditolak) — not approved',
        'stale': 'the STR is approved but from a PRIOR cycle (stale)',
        'unreadable': 'the STR approval status could not be read and no payment is shown',
        'unconfirmed': 'the STR is approved (Lulus) but has NO payment date to pin the current cycle',
    },
    'str_verified': 'a current, approved STR whose recipient is the declared earner',
    'str_recipient_mismatch': 'the STR recipient is not the declared earner ({members})',
    'str_present_unverified': 'an STR is present but its recipient could not be confirmed',
    'income_proof_missing': 'no STR document was uploaded (this household is on the STR route)',
    # earner identity + relationship
    'earner_ic_present': "the earner's IC is on file: {name}",
    'earner_ic_missing': 'no IC uploaded for the earner ({members})',
    'earner_ic_unreadable': "the earner's IC could not be read ({members})",
    'relationship_confirmed': "the earner is confirmed as the student's parent/guardian",
    'father_patronymic_mismatch': "the earner IC name does not match the father's name in the student's IC ({members})",
    'birth_cert_missing': 'a working member is the mother but no birth certificate links her to the student',
    'birth_cert_mismatch': 'the birth certificate does not link the named mother to the student',
    'guardianship_letter_missing': "income shown is a guardian's, but no guardianship letter was uploaded",
    'income_earner_undeclared': 'the student has not said whose income is shown (the income wizard is incomplete)',
    # salary route / per-capita (GROSS income → per-capita; never take-home/net)
    'income_salary_probable': 'gross household income ~RM{amount}/month is clearly UNDER the B40 line — supports approval',
    'income_salary_unsure': ('gross household income ~RM{amount}/month sits NEAR the B40 line — not a clear pass; the '
                             'household composition (its size, and whether another member works) sets the true gross and per-capita'),
    'income_above_b40_line': 'per-capita income RM{amount} is OVER the B40 line (RM{ceiling}) — income does not support B40',
    'income_per_capita_ok': 'per-capita income RM{amount} is below the B40 line (RM{ceiling})',
    'income_unverified_needs_interview': 'income cannot be document-verified (informal / no payslip) — confirm at interview',
    # utility (soft signals)
    'utility_hardship': 'the utility bills carry meaningful arrears (unpaid balance) — supports financial need',
    'utility_percapita_b40': 'utility proxy ~RM{amount}/capita/month — consistent with a B40 household (soft signal)',
    'utility_percapita_high': 'utility proxy ~RM{amount}/capita/month — high (M40/T20 pattern); probe at interview (soft signal)',
}


def _render_item(item):
    """One glossed English line for a verdict item, params interpolated."""
    code = item.get('code', '')
    params = dict(item.get('params', {}) or {})
    if isinstance(params.get('members'), list):
        params['members'] = ', '.join(str(m) for m in params['members'])
    gloss = _CODE_GLOSS.get(code)
    if isinstance(gloss, dict):                       # status-specific (str_not_current)
        gloss = gloss.get(str(params.get('status', ''))) or gloss.get('unconfirmed')
    if not gloss:
        gloss = code.replace('_', ' ')                # graceful fallback for un-glossed codes
    for k, v in params.items():
        gloss = gloss.replace('{' + k + '}', str(v))
    return gloss


def _verdict_context(facts):
    """Plain-text grounding block for the non-Certain facts (Certain facts are hidden on the
    checklist, so the case is about what still needs the reviewer)."""
    lines = []
    for f in facts:
        band = _fact_band(f)
        if band == 'Certain':
            continue
        lines.append(f"FACT: {f['fact']} — verdict band: {band}")
        for it in f.get('unresolved', []):
            lines.append(f"  OPEN: {_render_item(it)}")
        for it in f.get('evidence', []):
            lines.append(f"  CONFIRMED: {_render_item(it)}")
    return '\n'.join(lines)


_PROMPT_HEAD = (
    "You are Check 2, a firm-but-fair scholarship-verification officer briefing a human reviewer "
    "who will AUDIT your call. From the structured verdict below (the band + CONFIRMED facts + OPEN "
    "findings), write a SHORT case — 2 to 4 sentences — that: (1) opens with the verdict and the "
    "single most decisive reason; (2) connects the reasoning into one thread; (3) states plainly why "
    "it is THIS band and NOT the next one up — the specific thing that would lift it; (4) ends with "
    "the action (what has been requested from the student / what the reviewer must confirm).\n"
    "RULES: use ONLY the facts, names and figures in the verdict — never invent or alter a number, "
    "name, document, or the band. Income is assessed on GROSS household income and the resulting "
    "PER-CAPITA income (gross / household size) against the B40 line — NEVER take-home or net pay; "
    "when income is the sticking point the gap is usually the household composition (its size, and "
    "whether another member works). State the earner's relationship precisely ('confirmed as the "
    "student's parent/guardian', never 'a confirmed parent'). Firm fiscal-steward voice guarding the "
    "donors' money — not a pushover, never cruel; the interview path stays open. British English, no "
    "fluff, no headings, no bullet points — just the paragraph.\n\nVERDICT:\n"
)


def _signature(facts_context):
    return hashlib.sha1(facts_context.encode('utf-8')).hexdigest()[:16]


def verdict_case_summary(application):
    """Return {'summary', 'cached', 'model', 'enabled'} or {'error'|'enabled'}. Cached per
    (application, verdict-signature, version) so it does not re-run on every cockpit open."""
    if not getattr(settings, 'VERDICT_CASE_SUMMARY_ENABLED', False):
        return {'enabled': False}
    facts = build_verdict(application)
    context = _verdict_context(facts)
    if not context.strip():
        return {'summary': '', 'enabled': True}       # every fact Certain → no case to make
    sig = _signature(context)
    key = f'vcs:{application.id}:{CASE_SUMMARY_VERSION}:{sig}'
    hit = cache.get(key)
    if hit is not None:
        return {'summary': hit, 'cached': True, 'enabled': True}
    from . import usage
    with usage.usage_context(application=application, source='verdict_summary'):
        res = _call_gemini_text(_PROMPT_HEAD + context, 'English')
    if res.get('error'):
        logger.warning('verdict_case_summary gemini error app=%s: %s', application.id, res['error'])
        return {'error': res['error'], 'enabled': True}
    text = (res.get('markdown') or '').strip()
    cache.set(key, text, 60 * 60 * 24 * 7)            # 7 days; regenerates when the verdict changes
    return {'summary': text, 'cached': False, 'model': res.get('model_used'), 'enabled': True}
