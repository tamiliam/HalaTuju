"""
Verification Verdict engine — the synthesis layer over the post-shortlist
signals (see ``docs/scholarship/verification-verdict-plan.md``, Sprint 1).

Rolls the scattered per-document signals (Vision OCR matchers, doc-assist
fields, completeness, the anomaly engine) into ONE four-fact verdict the
coordinator AUDITS rather than assembles:

    Identity  — name + NRIC, checkable by matching → the AI may ASSERT 'verified'
    Academic  — the results slip is the student's (grade-accuracy lands in S2)
    Income    — the hard one; the AI asserts green ONLY on a verified STR
                document, else it RECOMMENDS and a human decides
    Pathway   — the offer letter

Pure + deterministic — **no LLM calls**, no model writes (mirrors
``anomaly_engine``). Each ``_verdict_*`` builder returns a fact dict;
``build_verdict`` collects the four in a fixed order. The serializer exposes the
list; the frontend resolves the human-readable labels from
``admin.scholarship.verdict.*`` by code (params interpolate), so the server
stays locale-agnostic.

Design rules encoded here (settled in the plan):
  - **Green is expensive** — when in doubt the status drops to 'review', never up.
  - **Resolve before you escalate** — an OCR name truncation (the IC's name token
    set is a SUBSET of the typed name, e.g. a patronymic that spilled onto a
    second line) is settled silently as evidence, NOT raised as a mismatch; the
    NRIC is the hard identity key.
  - **Income green needs a verified STR *document***, not the self-declared flag.
  - **Address is a coherence test** — only a state-level (major) divergence
    escalates; sub-state postcode drift is noise and never flags.

Statuses:
  verified  — green;  the AI asserts this fact.
  review    — amber;  confirm / look — the under-claim default.
  recommend — blue;   evidence assembled, a HUMAN must place the verdict (income).
  gap       — red;    a required input is missing or unreadable; action needed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .anomaly_engine import _detect_address_state_mismatch
from .services import _ic_identity_blockers
from .vision import name_match


@dataclass(frozen=True)
class Item:
    """One evidence / unresolved line. ``params`` interpolate into the matching
    ``admin.scholarship.verdict.item.<code>`` i18n string on the frontend."""
    code: str
    params: dict = field(default_factory=dict)


def _item(code, **params):
    return asdict(Item(code, params))


def _fact(name, status, evidence, unresolved):
    return {'fact': name, 'status': status,
            'evidence': evidence, 'unresolved': unresolved}


# ── document readers ─────────────────────────────────────────────────────────

def _latest_doc(application, doc_type):
    return (application.documents.filter(doc_type=doc_type)
            .order_by('-uploaded_at').first())


def _present_doc_types(application):
    return set(application.documents.values_list('doc_type', flat=True))


def _doc_assist_verdict(doc):
    """The deterministic student_verdict stored by doc-assist (ok / name_mismatch
    / address_mismatch / wrong_doc / unreadable), or '' if never run."""
    if doc is None:
        return ''
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    return vf.get('student_verdict', '') or ''


def _doc_assist_fields(doc):
    if doc is None:
        return {}
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    f = vf.get('fields', {})
    return f if isinstance(f, dict) else {}


# ── Identity (name + NRIC) ───────────────────────────────────────────────────

def _verdict_identity(application):
    """Identity is checkable by matching, so the AI may assert 'verified'. It
    NEVER auto-fails: every mismatch has an innocent cause more likely than
    fraud (OCR truncation, a typo, a missing connector), so the worst the engine
    does is 'review' (confirm) or 'gap' (re-upload an unreadable IC)."""
    evidence, unresolved = [], []
    ic = _latest_doc(application, 'ic')
    if ic is None:
        return _fact('identity', 'gap', evidence, [_item('ic_missing')])

    # Reuse the consent-gate identity logic so the verdict and the consent gate
    # can never disagree. It returns at most: ic_service_down / ic_unreadable /
    # ic_nric_mismatch / ic_name_mismatch (a 'partial' name is NOT a blocker).
    blockers = _ic_identity_blockers(application)
    if 'ic_service_down' in blockers:
        # The OCR *service* failed (not a bad image) — confirm later, never fail.
        return _fact('identity', 'review', evidence, [_item('ic_service_down')])
    if 'ic_unreadable' in blockers:
        return _fact('identity', 'gap', evidence, [_item('ic_unreadable')])

    profile = application.profile
    pnric = (getattr(profile, 'nric', '') or '').strip()
    pname = (getattr(profile, 'name', '') or '').strip()

    # NRIC — the hard identity key.
    if 'ic_nric_mismatch' in blockers:
        unresolved.append(_item('nric_mismatch',
                                ocr_nric=ic.vision_nric, profile_nric=pnric))
    elif ic.vision_nric and pnric:
        evidence.append(_item('nric_match', nric=pnric))

    # Name — disjoint tokens raise a flag; a subset (OCR truncation) is RESOLVED
    # silently because the NRIC already anchors identity.
    if ic.vision_name and pname:
        verdict = name_match(ic.vision_name, pname)
        if verdict == 'match':
            evidence.append(_item('name_match', name=pname))
        elif verdict == 'partial':
            evidence.append(_item('name_resolved_truncation',
                                  ocr_name=ic.vision_name, profile_name=pname))
        else:  # 'mismatch'
            unresolved.append(_item('name_mismatch',
                                    ocr_name=ic.vision_name, profile_name=pname))

    # Address coherence — only a state-level (major) divergence escalates;
    # sub-state postcode drift is deliberately ignored as noise.
    addr_anomaly = _detect_address_state_mismatch(application)
    if addr_anomaly is not None:
        unresolved.append(_item('address_state_mismatch', **addr_anomaly.params))

    return _fact('identity', 'verified' if not unresolved else 'review',
                 evidence, unresolved)


# ── Academic (results slip) ──────────────────────────────────────────────────

def _verdict_academic(application):
    """S1 confirms the slip is the student's (name match). Grade ACCURACY —
    do the typed grades match the slip — is verified in S2; until then the fact
    stays 'review', never 'verified' (honest under-claim)."""
    evidence, unresolved = [], []
    slip = _latest_doc(application, 'results_slip')
    if slip is None:
        return _fact('academic', 'gap', evidence, [_item('results_slip_missing')])

    dv = _doc_assist_verdict(slip)
    if dv == 'name_mismatch':
        unresolved.append(_item('results_slip_name_mismatch'))
    elif dv in ('wrong_doc', 'unreadable') or slip.vision_name_match == 'not_found':
        unresolved.append(_item('results_slip_unreadable'))
    else:
        evidence.append(_item('results_slip_name_ok'))

    # Grade cross-check is a later step (S2) — flag it as the one thing still
    # owed so the officer eyeballs the grades against the slip in the meantime.
    unresolved.append(_item('grades_unverified'))
    return _fact('academic', 'review', evidence, unresolved)


# ── Income (the hard one) ────────────────────────────────────────────────────

def _verdict_income(application):
    """STR is the gold standard: a verified STR *document* → the AI asserts
    'verified'. Otherwise it assembles the weaker evidence (EPF / salary /
    utility-bill proxy) and a HUMAN decides ('recommend'). No income proof at
    all → 'gap' (chase a document)."""
    evidence, unresolved = [], []
    profile = application.profile
    present = _present_doc_types(application)
    receives_str = bool(getattr(profile, 'receives_str', False))

    str_doc = _latest_doc(application, 'str')
    if str_doc is not None:
        if str_doc.vision_name_match == 'found':
            return _fact('income', 'verified', [_item('str_verified')], unresolved)
        # Present but the household name isn't matched on it yet → confirm.
        return _fact('income', 'review', evidence, [_item('str_present_unverified')])

    # No STR document — assemble the weaker evidence; a human places the verdict.
    if receives_str:
        unresolved.append(_item('str_claimed_no_doc'))
    has_epf = 'epf' in present
    has_salary = 'salary_slip' in present
    if has_epf:
        evidence.append(_item('income_proof_epf'))
    if has_salary:
        evidence.append(_item('income_proof_salary'))
    if present & {'water_bill', 'electricity_bill'}:
        evidence.append(_item('utility_bills_present'))

    if not (has_epf or has_salary):
        unresolved.append(_item('income_proof_missing'))
        return _fact('income', 'gap', evidence, unresolved)
    return _fact('income', 'recommend', evidence, unresolved)


# ── Pathway (offer letter) ───────────────────────────────────────────────────

def _verdict_pathway(application):
    """An offer letter whose candidate name matches → 'verified'. No offer is
    fine (many apply pre-offer) — the pathway is then merely declared, so the
    fact stays 'review'."""
    evidence, unresolved = [], []
    offer = _latest_doc(application, 'offer_letter')
    chosen = (application.chosen_pathway or application.intended_pathway or '').strip()

    if offer is None:
        if chosen:
            return _fact('pathway', 'review',
                         [_item('pathway_declared', pathway=chosen)], unresolved)
        return _fact('pathway', 'review', evidence, [_item('pathway_undeclared')])

    dv = _doc_assist_verdict(offer)
    if dv == 'name_mismatch':
        return _fact('pathway', 'review', evidence, [_item('offer_name_mismatch')])
    if dv in ('wrong_doc', 'unreadable'):
        return _fact('pathway', 'review', evidence, [_item('offer_unreadable')])

    fields = _doc_assist_fields(offer)
    inst = (fields.get('institution') or '').strip()
    prog = (fields.get('programme') or '').strip()
    if inst or prog:
        evidence.append(_item('offer_programme', institution=inst, programme=prog))
    else:
        evidence.append(_item('offer_name_ok'))
    return _fact('pathway', 'verified', evidence, unresolved)


# ── Aggregator ───────────────────────────────────────────────────────────────

def build_verdict(application) -> list[dict]:
    """The four-fact verification verdict in fixed order (identity, academic,
    income, pathway). Pure + deterministic — safe to call inside a serializer
    GET. Each fact: ``{fact, status, evidence[], unresolved[]}`` where evidence
    and unresolved items are ``{code, params}`` dicts resolved on the frontend."""
    return [
        _verdict_identity(application),
        _verdict_academic(application),
        _verdict_income(application),
        _verdict_pathway(application),
    ]
