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
from .vision import _MY_STATES, name_match


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


_NORMALIZED_STATES = {_normalize_state(s) for s in _MY_STATES}


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


def _detect_household_size_one(application) -> Optional[Anomaly]:
    """Household of one is unusual — verify they aren't accidentally counting
    only themselves while still living with family."""
    profile = application.profile
    if not profile or profile.household_size != 1:
        return None
    return Anomaly('household_size_one', {})


def _detect_first_in_family_with_siblings_studying(application) -> Optional[Anomaly]:
    """First-to-university + siblings studying is a mild contradiction — could
    be younger siblings still in school (not at university), in which case
    both are true. Worth asking."""
    if not application.first_in_family:
        return None
    count = application.siblings_studying_count
    if count is None or count <= 0:
        return None
    return Anomaly('first_in_family_with_siblings_studying', {'count': count})


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


def _detect_str_claimed_no_doc(application) -> Optional[Anomaly]:
    """Student says the family receives STR but hasn't uploaded the STR
    confirmation document — verify quickly + request the doc."""
    profile = application.profile
    if not profile or not profile.receives_str:
        return None
    has_str_doc = application.documents.filter(doc_type='str').exists()
    if has_str_doc:
        return None
    return Anomaly('str_claimed_no_doc', {})


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


# ─── Aggregator ─────────────────────────────────────────────────────────────

_DETECTORS = (
    _detect_vision_nric_mismatch,
    _detect_vision_name_mismatch,
    _detect_address_state_mismatch,
    _detect_jkm_high_income,
    _detect_household_size_one,
    _detect_first_in_family_with_siblings_studying,
    _detect_funding_other_without_note,
    _detect_declaration_name_mismatch,
    _detect_str_claimed_no_doc,
    _detect_device_in_funding,
)


def detect_anomalies(application) -> list[dict]:
    """Run all rules against the application; return the flags that fired as
    plain dicts (JSON-ready for the serializer). Order matches ``_DETECTORS``
    so the admin always sees the same ordering for the same data."""
    return [asdict(a) for d in _DETECTORS if (a := d(application)) is not None]
