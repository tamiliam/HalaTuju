"""
Deterministic anomaly engine — Phase A of the post-shortlist interview-driven
profile (see ``docs/scholarship/post-shortlist-vision.md``).

Surfaces a "pre-interview flag list" on each application: data inconsistencies
the coordinator should ask about during the interview. Pure rule-based —
**no LLM calls**, no model writes. Three flag *sources* are envisioned in the
vision doc; this module is the **deterministic** one. The Vision/OCR signals
already feed in via the application's documents (S13), and Gemini-derived
narrative gaps come in Phase B.

Each rule is a small ``_detect_*`` function returning ``Anomaly | None``;
the aggregator collects what fired. The serializer exposes the list as plain
``{code, params}`` dicts — the frontend resolves the human-readable fact +
suggested question against its i18n bundle, so server-side stays locale-agnostic.

Adding a new rule = write ``_detect_xxx`` + register in ``_DETECTORS`` + add
two i18n keys (``scholarship.admin.anomaly.<code>.{fact,question}``) + one
test in ``test_anomaly_engine.py``.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Optional

from .models import ApplicantDocument, FundingNeed
from .services import age_from_nric
from .vision import MY_STATES, name_match


@dataclass(frozen=True)
class Anomaly:
    """One flagged-for-interview signal. ``params`` interpolates into the
    matching i18n strings on the frontend (no copy held server-side)."""
    code: str
    params: dict = field(default_factory=dict)


# ─── Helpers ────────────────────────────────────────────────────────────────

def _normalize_state(s: str) -> str:
    """Strip case + the W.P. prefix so 'Putrajaya' / 'W.P. Putrajaya' /
    'PUTRAJAYA' all compare equal."""
    if not s:
        return ''
    s = s.upper().strip()
    return re.sub(r'^W\.?\s*P\.?\s*', '', s)


_NORMALIZED_STATES = {_normalize_state(s) for s in MY_STATES}


def _state_from_address(addr: str) -> Optional[str]:
    """Pull the state segment out of a comma-separated MyKad address line."""
    if not addr:
        return None
    for seg in (s.strip() for s in addr.split(',')):
        if _normalize_state(seg) in _NORMALIZED_STATES:
            return seg
    return None


def _latest_ic_doc(application) -> Optional[ApplicantDocument]:
    return (
        application.documents
        .filter(doc_type='ic')
        .order_by('-uploaded_at')
        .first()
    )


def _latest_parent_ic_doc(application) -> Optional[ApplicantDocument]:
    return (
        application.documents
        .filter(doc_type='parent_ic')
        .order_by('-uploaded_at')
        .first()
    )


def _latest_active_consent(application):
    return application.consents.filter(is_active=True).order_by('-granted_at').first()


def _funding_need(application) -> Optional[FundingNeed]:
    try:
        return application.funding_need
    except FundingNeed.DoesNotExist:
        return None


# ─── The 10 rules ───────────────────────────────────────────────────────────

def _detect_vision_nric_mismatch(application) -> Optional[Anomaly]:
    """S13 OCR read a different NRIC from what the student typed."""
    ic = _latest_ic_doc(application)
    if ic is None or not ic.vision_run_at or ic.vision_error or not ic.vision_nric:
        return None
    profile_nric = (getattr(application.profile, 'nric', '') or '').strip()
    if not profile_nric:
        return None
    from .vision import nric_match
    if nric_match(ic.vision_nric, profile_nric):
        return None
    return Anomaly('vision_nric_mismatch', {
        'ocr_nric': ic.vision_nric,
        'profile_nric': profile_nric,
    })


def _detect_vision_name_mismatch(application) -> Optional[Anomaly]:
    """S13 OCR name doesn't fully match the profile name."""
    ic = _latest_ic_doc(application)
    if ic is None or not ic.vision_run_at or ic.vision_error or not ic.vision_name:
        return None
    profile_name = (getattr(application.profile, 'name', '') or '').strip()
    if not profile_name:
        return None
    verdict = name_match(ic.vision_name, profile_name)
    if verdict in ('match', 'mismatch'):
        # 'match' = no flag; 'mismatch' = a different kind of flag (the NRIC
        # mismatch already covers wrong-IC scenarios). 'partial' is the
        # interesting case — typo / missing middle name / order difference.
        if verdict == 'mismatch':
            return Anomaly('vision_name_mismatch', {
                'ocr_name': ic.vision_name, 'profile_name': profile_name,
            })
        return None
    # 'partial'
    return Anomaly('vision_name_mismatch', {
        'ocr_name': ic.vision_name, 'profile_name': profile_name,
    })


def _detect_address_state_mismatch(application) -> Optional[Anomaly]:
    """The state extracted from the MyKad address disagrees with what the
    student typed in /apply (profile.preferred_state). Often legitimate
    (relocated since IC was issued) — worth asking which is current."""
    profile = application.profile
    if not profile or not (profile.preferred_state or '').strip():
        return None
    ic = _latest_ic_doc(application)
    if ic is None or not (ic.vision_address or '').strip():
        return None
    ic_state = _state_from_address(ic.vision_address)
    if not ic_state:
        return None
    if _normalize_state(ic_state) == _normalize_state(profile.preferred_state):
        return None
    return Anomaly('address_state_mismatch', {
        'ic_state': ic_state,
        'profile_state': profile.preferred_state,
    })


def _detect_jkm_high_income(application) -> Optional[Anomaly]:
    """JKM aid is usually for low-income / disability / caregiver households;
    flag if the family is claiming JKM but reports income > RM3,000."""
    profile = application.profile
    if not profile or not profile.receives_jkm:
        return None
    income = profile.household_income or 0
    if income <= 3000:
        return None
    return Anomaly('jkm_high_income', {'income': income})


# Utilities eating more than this share of declared monthly income looks
# disproportionate (e.g. RM180 of bills on a declared RM600 income = 30%).
_UTILITY_INCOME_RATIO_FLOOR = 0.20


def _detect_utility_high_vs_income(application) -> Optional[Anomaly]:
    """P3 (Check 2): the household's utility bills look disproportionate to the income
    it declared — a soft consistency flag for the reviewer, never a gate. Fires only
    when both a monthly utility charge and a stated household income are known and the
    bills exceed ~20% of the declared monthly income (the actual numbers go to the
    reviewer so they can ask how a low-income household sustains the spend)."""
    from . import income_engine
    profile = application.profile
    income = (profile.household_income or 0) if profile else 0
    if income <= 0:
        return None
    total = income_engine.utility_monthly_total(application)
    if not total or total <= 0:
        return None
    ratio = total / income
    if ratio < _UTILITY_INCOME_RATIO_FLOOR:
        return None
    return Anomaly('utility_high_vs_income', {
        'utility': total, 'income': income, 'percent': round(ratio * 100),
    })


def _detect_household_size_one(application) -> Optional[Anomaly]:
    """Household of one is unusual — verify they aren't accidentally counting
    only themselves while still living with family."""
    profile = application.profile
    if not profile or profile.household_size != 1:
        return None
    return Anomaly('household_size_one', {})


def sibling_tertiary_count(application):
    """Authoritative number of siblings in TERTIARY education (P2, Check 2).

    Reads the school/tertiary split (the income wizard's two counters) first; it is
    authoritative. Falls back to the legacy combined ``siblings_studying_count`` ONLY
    when it is unambiguous — a legacy 0 means nobody is studying, so tertiary is 0.
    Returns ``None`` when the split is missing and the legacy count is a positive
    number that can't be broken down (→ a Check-2 clarify-query, not a guess)."""
    t = application.siblings_in_tertiary
    if t is not None:
        return t
    legacy = application.siblings_studying_count
    if legacy == 0:
        return 0
    return None  # ambiguous: split unknown, some siblings studying → ask


def _detect_first_in_family_with_siblings_studying(application) -> Optional[Anomaly]:
    """First-to-university + a sibling already in TERTIARY is a real contradiction
    (worth asking). Siblings only in *school* do NOT contradict it — so when the
    split says tertiary == 0, the first-gen claim auto-resolves and no flag is
    raised (P2). When the split is unknown but the legacy count says some siblings
    study, we still can't confirm → flag it for a clarify-query."""
    if not application.first_in_family:
        return None
    tertiary = sibling_tertiary_count(application)
    if tertiary is None:
        count = application.siblings_studying_count
        if count and count > 0:
            return Anomaly('first_in_family_with_siblings_studying', {'count': count})
        return None
    if tertiary > 0:
        return Anomaly('first_in_family_with_siblings_studying', {'count': tertiary})
    return None  # tertiary == 0 → first-gen holds, auto-resolved


def _detect_funding_other_without_note(application) -> Optional[Anomaly]:
    """Student ticked 'other' for funding but left the note blank — what did
    they have in mind?"""
    fn = _funding_need(application)
    if fn is None:
        return None
    cats = fn.categories if isinstance(fn.categories, list) else []
    if 'other' not in cats:
        return None
    if (fn.funding_note or '').strip():
        return None
    return Anomaly('funding_other_without_note', {})


def _detect_declaration_name_mismatch(application) -> Optional[Anomaly]:
    """Typed signature at submit time differs from the profile name. Token-set
    based so order + middle-name omission don't trip it; only true
    differences flag."""
    declaration = (application.declaration_name or '').strip()
    if not declaration:
        return None
    profile_name = (getattr(application.profile, 'name', '') or '').strip()
    if not profile_name:
        return None
    if name_match(declaration, profile_name) in ('match',):
        return None
    return Anomaly('declaration_name_mismatch', {
        'declaration': declaration, 'profile_name': profile_name,
    })


def _detect_device_in_funding(application) -> Optional[Anomaly]:
    """Student ticked 'device' (laptop/tablet) in funding. RM 3,000 won't cover
    a decent laptop plus the rest of the programme — worth understanding their
    bridge plan."""
    fn = _funding_need(application)
    if fn is None:
        return None
    cats = fn.categories if isinstance(fn.categories, list) else []
    if 'device' not in cats:
        return None
    return Anomaly('device_in_funding', {})


def _detect_parent_ic_name_mismatch(application) -> Optional[Anomaly]:
    """S17: Vision-OCR name on the parent_ic upload differs from the guardian
    name typed on the consent. Same name_match logic as the student's IC."""
    pic = _latest_parent_ic_doc(application)
    if pic is None or not pic.vision_run_at or pic.vision_error or not pic.vision_name:
        return None
    consent = _latest_active_consent(application)
    if consent is None or consent.granted_by != 'guardian':
        return None
    typed = (consent.guardian_name or '').strip()
    if not typed:
        return None
    verdict = name_match(pic.vision_name, typed)
    if verdict == 'match':
        return None
    return Anomaly('parent_ic_name_mismatch', {
        'ocr_name': pic.vision_name, 'typed_name': typed,
    })


def _detect_parent_ic_underage(application) -> Optional[Anomaly]:
    """S17: the 'guardian' uploaded an IC of someone <18 — they cannot
    legally consent for the minor applicant. Hard signal for the admin."""
    pic = _latest_parent_ic_doc(application)
    if pic is None or not pic.vision_run_at or pic.vision_error or not pic.vision_nric:
        return None
    age = age_from_nric(pic.vision_nric)
    if age is None or age >= 18:
        return None
    return Anomaly('parent_ic_underage', {
        'ocr_nric': pic.vision_nric, 'age': age,
    })


# ─── #8/#9 verification soft-signals (utility holder/address + payslip-vs-EPF) ──

def _detect_utility_holder_unknown(application) -> Optional[Anomaly]:
    """#8: a water/electricity bill is in a stranger's name — matches neither the student
    nor any uploaded parent IC. Raise a 'who is this?' question for the interview."""
    from . import income_engine
    name = income_engine.utility_holder_unknown(application)
    if not name:
        return None
    return Anomaly('utility_holder_unknown', {'name': name})


def _detect_utility_address_mismatch(application) -> Optional[Anomaly]:
    """#8: a utility bill's supply address is a HARD mismatch against the stated home
    address. A partial / missing-postcode read stays silent (handled upstream), so this
    only fires on a genuinely different address — worth confirming at interview."""
    from . import income_engine
    if income_engine.utility_address_mismatch(application):
        return Anomaly('utility_address_mismatch', {})
    return None


def _detect_payslip_epf_divergence(application) -> Optional[Anomaly]:
    """#9: a working member has BOTH a payslip and an EPF, and the payslip salary diverges
    a lot from the EPF-implied salary. Often overtime / late pay — surface the figures so
    the reviewer can confirm the regular income at interview. Never a gate."""
    from . import income_engine
    slip_members = {income_engine._proof_member(d)
                    for d in application.documents.filter(doc_type='salary_slip')}
    epf_members = {income_engine._proof_member(d)
                   for d in application.documents.filter(doc_type='epf')}
    for member in sorted(m for m in (slip_members & epf_members) if m):
        d = income_engine.slip_epf_divergence(application, member)
        if d:
            return Anomaly('payslip_epf_divergence', {
                'slip': d['slip'], 'epf_implied': d['epf_implied'],
            })
    return None


def _ic_authenticity_status(doc) -> str:
    """The stored genuineness status for an IC doc — '' if the check didn't run."""
    if doc is None or not isinstance(getattr(doc, 'vision_fields', None), dict):
        return ''
    a = doc.vision_fields.get('authenticity')
    return a.get('status', '') if isinstance(a, dict) else ''


def _detect_ic_low_confidence(application) -> Optional[Anomaly]:
    """The IC genuineness fingerprint says the uploaded image doesn't look like a real photo
    of a physical MyKad (likely typed / printed / a screenshot). Soft — confirm the physical
    card at interview; never gates. Flag-gated: only fires when the check actually ran."""
    from .genuineness.bands import canonical_status, needs_attention
    raw = _ic_authenticity_status(_latest_ic_doc(application))
    if not needs_attention(raw, 'ic'):
        return None
    return Anomaly('ic_low_confidence', {'status': canonical_status(raw, 'ic')})


def _detect_parent_ic_low_confidence(application) -> Optional[Anomaly]:
    """Same genuineness check for the parent / guardian IC."""
    from .genuineness.bands import canonical_status, needs_attention
    raw = _ic_authenticity_status(_latest_parent_ic_doc(application))
    if not needs_attention(raw, 'parent_ic'):
        return None
    return Anomaly('parent_ic_low_confidence', {'status': canonical_status(raw, 'parent_ic')})


# Sprint 2 — genuineness for the standardised supporting documents.
_GENUINENESS_DOC_LABELS = {
    'str': 'STR', 'results_slip': 'results slip',
    'birth_certificate': 'birth certificate', 'epf': 'EPF statement',
}


def _detect_document_not_genuine(application) -> Optional[Anomaly]:
    """A standardised supporting document (STR / results slip / BC / EPF) doesn't look like a
    genuine official document, or is the WRONG document type. Soft — confirm at interview;
    never gates. Flag-gated (only fires when the check ran). Returns the first hit; params carry
    a human doc label, the status, and what the AI thought the document actually was."""
    from .genuineness.bands import canonical_status, needs_attention
    for dt, label in _GENUINENESS_DOC_LABELS.items():
        doc = application.documents.filter(doc_type=dt).order_by('-uploaded_at').first()
        raw = _ic_authenticity_status(doc)   # reads vision_fields['authenticity'].status
        if needs_attention(raw, dt):         # canonical 'suspect' / 'not_<type>' (folds legacy)
            vf = doc.vision_fields if isinstance(getattr(doc, 'vision_fields', None), dict) else {}
            seen = (vf.get('authenticity') or {}).get('doc_seen', '')
            return Anomaly('document_not_genuine',
                           {'doc': label, 'status': canonical_status(raw, dt), 'seen': seen})
    return None


# ─── Aggregator ─────────────────────────────────────────────────────────────

_DETECTORS = (
    _detect_vision_nric_mismatch,
    _detect_vision_name_mismatch,
    _detect_address_state_mismatch,
    _detect_jkm_high_income,
    _detect_utility_high_vs_income,
    _detect_household_size_one,
    _detect_first_in_family_with_siblings_studying,
    _detect_funding_other_without_note,
    _detect_declaration_name_mismatch,
    _detect_device_in_funding,
    # S17 — minor consent flow
    _detect_parent_ic_name_mismatch,
    _detect_parent_ic_underage,
    # #8/#9 — verification soft-signals (utility holder/address + payslip vs EPF)
    _detect_utility_holder_unknown,
    _detect_utility_address_mismatch,
    _detect_payslip_epf_divergence,
    # Verification-assurance — document genuineness fingerprint (flag-gated)
    _detect_ic_low_confidence,
    _detect_parent_ic_low_confidence,
    _detect_document_not_genuine,
)


def detect_anomalies(application) -> list[dict]:
    """Run all rules against the application; return the flags that fired as
    plain dicts (JSON-ready for the serializer). Order matches ``_DETECTORS``
    so the admin always sees the same ordering for the same data."""
    return [asdict(a) for d in _DETECTORS if (a := d(application)) is not None]
