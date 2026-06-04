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
    """The slip must be the student's (name match), every subject on it must be
    entered (completeness), and the typed grades must match the slip (accuracy).
    All three clean → 'verified'. The slip's grades and the typed grades are two
    independent readings: agreement is strong verification, a disagreement
    pinpoints the one cell to check."""
    from .academic_engine import compare_academics, read_slip, _slip_name_status
    evidence, unresolved = [], []
    slip = _latest_doc(application, 'results_slip')
    if slip is None:
        return _fact('academic', 'gap', evidence, [_item('results_slip_missing')])

    # Name — use the slip's OWN sv-authoritative status (the candidate-name logic the
    # student checklist uses), NOT the supporting-doc `vision_name_match` column. That
    # column is an unreliable full-text heuristic for a results slip: a perfectly-read
    # slip can carry 'not_found' there for some name spellings, and must never be mistaken
    # for "the slip could not be read" (it falsely flagged Sharvani's clean, fully-read slip).
    name_status = _slip_name_status(slip)
    name_ok = name_status == 'match'
    if name_status == 'mismatch':
        unresolved.append(_item('results_slip_name_mismatch'))
    elif name_status == 'unreadable':
        unresolved.append(_item('results_slip_unreadable'))
    elif name_status == 'match':
        evidence.append(_item('results_slip_name_ok'))
    # 'pending' → the slip's name is not yet decided; make no claim either way.

    data = read_slip(slip)
    if not data['names']:
        # The slip hasn't been field-extracted yet (legacy upload) — grades
        # unread, so honest under-claim: review until it's re-OCR'd.
        unresolved.append(_item('grades_unverified'))
        return _fact('academic', 'review', evidence, unresolved)

    cmp = compare_academics(getattr(application.profile, 'grades', None), data)
    if cmp['missing']:
        unresolved.append(_item('academic_missing_subjects',
                                entered=cmp['slip_count'] - len(cmp['missing']),
                                total=cmp['slip_count'],
                                subjects=', '.join(cmp['missing'])))
    for m in cmp['mismatched']:
        unresolved.append(_item('academic_grade_mismatch',
                                subject=m['subject'], typed=m['typed'], slip=m['slip']))
    # The slip's letter and band disagree for this subject — the grade read can't be
    # trusted, so surface it as "check by eye", NOT a confident mismatch.
    for u in cmp['uncertain']:
        unresolved.append(_item('academic_grade_uncertain',
                                subject=u['subject'], typed=u['typed'], slip=u['slip'], band=u['band']))

    if not cmp['have_grades']:
        # Names extracted (so completeness is real) but no grades yet — accuracy
        # still pending. Confirmed-complete is progress, but not 'verified'.
        unresolved.append(_item('grades_unverified'))
        return _fact('academic', 'review', evidence, unresolved)

    if name_ok and cmp['complete'] and cmp['accurate']:
        evidence.append(_item('grades_verified', count=cmp['slip_count']))
        return _fact('academic', 'verified', evidence, unresolved)
    return _fact('academic', 'review', evidence, unresolved)


# ── Income (the hard one) ────────────────────────────────────────────────────

def _verdict_income(application):
    """Income Check-1 (item 3): the guided wizard says which documents the family
    needs (income_engine.income_requirements); this assembles whether they're present,
    whether the EARNER is the student's family (father=patronymic, mother=Birth
    Certificate, guardian=letter), and places the verdict:

      - STR route, all compulsory present + relationship OK → 'verified' (gold standard).
      - salary route assembled → 'recommend' (a human still places the B40 amount call).
      - a compulsory DOC missing → 'gap'; a relationship/check that FAILS → 'review'.
      - **never blocks** a genuinely poor family: an informal/no-EPF earner whose income
        can't be document-proven gets 'recommend' + `income_unverified_needs_interview`,
        which the officer confirms via the interview (lifestyle, household, burden).

    Wizard not walked yet → 'review' (`income_earner_undeclared`), unless a present,
    name-matched STR already settles it on its own."""
    from .income_engine import (income_requirements, relationship_doc_for,
                                father_relationship, mother_relationship, guardian_relationship)
    evidence, gap, review = [], [], []
    present = _present_doc_types(application)
    student_name = getattr(application.profile, 'name', '') or ''
    earner = (getattr(application, 'income_earner', '') or '').strip()
    route = (getattr(application, 'income_route', '') or '').strip()

    str_doc = _latest_doc(application, 'str')
    str_verified = str_doc is not None and str_doc.vision_name_match == 'found'

    # Wizard not walked → can't compute requirements. A verified STR still settles it;
    # otherwise ask the student to tell us whose income they're showing (the wizard).
    if not earner or not route:
        if str_verified:
            return _fact('income', 'verified', [_item('str_verified')], [])
        return _fact('income', 'review', evidence, [_item('income_earner_undeclared')])

    reqs = income_requirements(application)
    rel_doc = relationship_doc_for(earner)

    # ── Earner IC (the income docs are issued in their name) ──────────────────
    ic_doc = _latest_doc(application, 'parent_ic')
    earner_ic_name = (getattr(ic_doc, 'vision_name', '') or '').strip() if ic_doc else ''
    if ic_doc is None:
        gap.append(_item('earner_ic_missing'))
    elif not earner_ic_name:
        review.append(_item('earner_ic_unreadable'))
    else:
        evidence.append(_item('earner_ic_present', name=earner_ic_name))

    # ── Relationship: prove the earner is the student's family ────────────────
    rel = None
    if earner == 'father':
        rel = father_relationship(student_name, earner_ic_name)
    elif earner == 'mother':
        if 'birth_certificate' not in present:
            gap.append(_item('birth_cert_missing'))
        else:
            bcf = _doc_assist_fields(_latest_doc(application, 'birth_certificate'))
            rel = mother_relationship(bcf.get('bc_child_name', ''), bcf.get('bc_mother_name', ''),
                                      student_name, earner_ic_name)
    elif earner == 'guardian':
        if 'guardianship_letter' not in present:
            gap.append(_item('guardianship_letter_missing'))
        else:
            g = _latest_doc(application, 'guardianship_letter')
            rel = guardian_relationship(getattr(g, 'vision_name', '') or '', earner_ic_name)
    if rel == 'match':
        evidence.append(_item('relationship_confirmed'))
    elif rel == 'mismatch':
        review.append(_item('father_patronymic_mismatch' if earner == 'father' else 'birth_cert_mismatch'))
    # 'unknown' (no patronymic — e.g. a Chinese name) / 'pending' → no claim; officer eyeballs.

    # ── Income evidence — the compulsory income docs for this route/work-status ─
    income_docs = [d for d in reqs['compulsory'] if d not in ('parent_ic', rel_doc)]
    if route == 'str':
        if str_verified:
            evidence.append(_item('str_verified'))
        elif str_doc is not None:
            review.append(_item('str_present_unverified'))
        else:
            gap.append(_item('income_proof_missing'))
    else:  # salary route
        missing = [d for d in income_docs if d not in present]
        if missing:
            gap.append(_item('income_proof_missing'))
        else:
            evidence.append(_item('income_proof_present'))

    # ── Place the verdict ─────────────────────────────────────────────────────
    if gap:
        return _fact('income', 'gap', evidence, gap + review)
    if review:
        return _fact('income', 'review', evidence, review)
    if route == 'str' and str_verified:
        return _fact('income', 'verified', evidence, [])
    # Salary assembled, nothing missing/failed. A human still places the B40 amount call;
    # when the proof is thin (informal / no payslip) flag it for the interview, never block.
    if (getattr(application, 'earner_work_status', '') or '') == 'informal':
        review.append(_item('income_unverified_needs_interview'))
    return _fact('income', 'recommend', evidence, review)


# ── Pathway (offer letter) ───────────────────────────────────────────────────

def _verdict_pathway(application):
    """The offer letter settles the FINAL chosen pathway. Identity on the letter
    (name + IC — the IC is the strong check) must be the applicant's, then the
    offer is reconciled against what the student declared at apply time:

      - the offer agrees (or there's nothing specific to clash with) → 'verified':
        the offer IS the evidence; nagging a student whose offer matches is pointless.
      - the offer is for a genuinely DIFFERENT place/field than declared → ask the
        student to confirm which is final (an AI-raised query, no human officer);
        on Yes the record is realigned + stamped → 'verified'.

    No offer is fine (many apply pre-offer) — the pathway is then merely declared
    → 'review'."""
    from .pathway_engine import student_offer_check
    evidence, unresolved = [], []
    offer = _latest_doc(application, 'offer_letter')
    chosen = (application.chosen_pathway or application.intended_pathway or '').strip()

    if offer is None:
        if chosen:
            return _fact('pathway', 'review',
                         [_item('pathway_declared', pathway=chosen)], unresolved)
        return _fact('pathway', 'review', evidence, [_item('pathway_undeclared')])

    chk = student_offer_check(offer)
    # Identity guard: a wrong name OR IC means a wrong-person letter.
    if chk['ic'] == 'mismatch' or chk['name'] == 'mismatch':
        return _fact('pathway', 'review', evidence, [_item('offer_name_mismatch')])
    # No identity read off the letter. Distinguish a general NOTICE / wrong document
    # (the body read fine — issuer/institution/programme present — but it carries no
    # name or IC, e.g. a "your offer will be released later" memo) from a genuinely
    # blurry scan. Telling the officer to "ask for a clearer copy" on a crisp notice
    # is misleading; a clearer copy won't add a name that was never there.
    if chk['name'] in ('unreadable', 'pending') and chk['ic'] in ('unreadable', 'pending'):
        if chk['programme'] or chk['institution']:
            return _fact('pathway', 'review', evidence, [_item('offer_no_identity')])
        return _fact('pathway', 'review', evidence, [_item('offer_unreadable')])

    prog, inst = chk['programme'], chk['institution']
    # Already confirmed (the student answered the reconciliation query) → verified.
    if application.pathway_confirmed_at is not None:
        evidence.append(_item('pathway_confirmed', programme=prog, institution=inst))
        return _fact('pathway', 'verified', evidence, unresolved)

    if prog or inst:
        evidence.append(_item('offer_programme', institution=inst, programme=prog))

    # The offer is for a genuinely different place/field than declared → ask the
    # student to confirm which is final (Check 2 backstop; record realigns on Yes).
    if chk['pathway'] == 'mismatch':
        unresolved.append(_item('pathway_confirm', programme=prog, institution=inst,
                                declared_programme=chk['declared_programme'],
                                declared_institution=chk['declared_institution']))
        return _fact('pathway', 'review', evidence, unresolved)

    # Offer agrees with the declaration (or nothing specific to clash with) AND we
    # could read a programme/institution off it → the offer settles the pathway.
    if prog or inst:
        return _fact('pathway', 'verified', evidence, unresolved)
    # Identity matched but the offer body didn't read a programme — under-claim.
    return _fact('pathway', 'review', evidence, [_item('offer_unreadable')])


# ── Aggregator ───────────────────────────────────────────────────────────────

def build_verdict(application) -> list[dict]:
    """The four-fact verification verdict in fixed order (identity, academic,
    pathway, income). Pure + deterministic — safe to call inside a serializer
    GET. Each fact: ``{fact, status, evidence[], unresolved[]}`` where evidence
    and unresolved items are ``{code, params}`` dicts resolved on the frontend."""
    return [
        _verdict_identity(application),
        _verdict_academic(application),
        _verdict_pathway(application),
        _verdict_income(application),
    ]
