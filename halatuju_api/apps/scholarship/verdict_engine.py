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


def _latest_doc_for_member(application, doc_type, member):
    """The latest income document of *doc_type* tagged to a specific household
    *member* (salary route). The (doc_type, household_member) pair is the
    single-instance key, so this returns that member's current IC / payslip / EPF."""
    return (application.documents.filter(doc_type=doc_type, household_member=member)
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

    # NOTE: the IC's registered-address state is deliberately NOT an identity caveat.
    # A MyKad carries the *least-current* address on file (people relocate; the IC is
    # not reissued — fresher addresses come from the offer letter / bills / STR) and it
    # is not an identity key: name + NRIC are. A state divergence therefore stays a
    # pre-interview flag ("ask which is current" — `_detect_address_state_mismatch` in
    # anomaly_engine), NOT a verdict downgrade. So identity reads green when name + NRIC
    # match, consistent with the Documents panel and the student's own identity card.

    # Genuineness fingerprint (soft, flag-gated — only present when the check ran): if the
    # IC doesn't look like a real card, the AI cannot be CERTAIN of identity even when the
    # typed name + NRIC match — so it caps the verdict at 'review' (the reviewer confirms
    # the physical card at interview). It NEVER auto-fails on genuineness alone — we don't
    # accuse; we lower confidence (see the verification-assurance roadmap's threat model).
    auth = ic.vision_fields.get('authenticity') if isinstance(ic.vision_fields, dict) else None
    if isinstance(auth, dict) and auth.get('status') in ('low_confidence', 'not_an_ic'):
        unresolved.append(_item('ic_low_confidence', status=auth['status'],
                                reason=auth.get('reason', '')))
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
    if name_status == 'mismatch':
        # A slip in someone else's name is unusable — these results can't be attributed
        # to the student. Hard stop (red, can't verify): re-upload the correct slip. Also
        # a submission blocker (application_completeness), so it can't be submitted as-is.
        return _fact('academic', 'gap', evidence, [_item('results_slip_name_mismatch')])
    name_ok = name_status == 'match'
    if name_status == 'unreadable':
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

def _utility_context(application):
    """Soft, officer-facing income context from the utility bills (never a gate): the
    combined water+electricity per-capita as a B40 proxy, + an arrears hardship signal.
    Imperfect — surfaced as evidence the coordinator weighs, not a verdict driver."""
    from .income_engine import utility_per_capita, utility_hardship
    items = []
    pc = utility_per_capita(application)
    if pc and pc['signal'] == 'b40':
        items.append(_item('utility_percapita_b40', amount=int(round(pc['per_capita']))))
    elif pc and pc['signal'] == 'high':
        items.append(_item('utility_percapita_high', amount=int(round(pc['per_capita']))))
    if utility_hardship(application):
        items.append(_item('utility_hardship'))
    return items

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
    name-matched STR already settles it on its own.

    The SALARY route delegates to ``_verdict_income_salary`` (multi-earner)."""
    from .income_engine import (father_link, mother_relationship,
                                guardian_relationship)
    evidence, gap, review = _utility_context(application), [], []
    present = _present_doc_types(application)
    student_name = getattr(application.profile, 'name', '') or ''
    earner = (getattr(application, 'income_earner', '') or '').strip()
    route = (getattr(application, 'income_route', '') or '').strip()

    str_doc = _latest_doc(application, 'str')

    # Salary (non-STR) route → multi-earner path.
    if route == 'salary':
        return _verdict_income_salary(application, student_name, present)

    # Wizard not walked → no income information at all yet. Like a missing IC / slip /
    # offer, "nothing provided" is a hard red (can't verify), not a soft amber — the
    # student must complete the income wizard (and its docs) before we can check anything.
    if not earner or not route:
        return _fact('income', 'gap', evidence, [_item('income_earner_undeclared')])

    # ── Earner IC (the income docs are issued in their name) ──────────────────
    # `members=[earner]` keeps the IC/relationship reason-code copy uniform with the
    # salary route (which lists several) — both render "… for {members}".
    ic_doc = _latest_doc(application, 'parent_ic')
    earner_ic_name = (getattr(ic_doc, 'vision_name', '') or '').strip() if ic_doc else ''
    if ic_doc is None:
        gap.append(_item('earner_ic_missing', members=[earner]))
    elif not earner_ic_name:
        review.append(_item('earner_ic_unreadable', members=[earner]))
    else:
        evidence.append(_item('earner_ic_present', name=earner_ic_name))

    # ── Relationship: prove the earner is the student's family ────────────────
    rel = None
    if earner == 'father':
        # Patronymic, with a BC fallback for a mononym student (#55) when a BC is uploaded.
        bcf = _doc_assist_fields(_latest_doc(application, 'birth_certificate'))
        rel = father_link(student_name, earner_ic_name,
                          bcf.get('bc_child_name', ''), bcf.get('bc_father_name', ''))
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
        if earner == 'father':
            review.append(_item('father_patronymic_mismatch', members=[earner]))
        else:
            review.append(_item('birth_cert_mismatch'))
    # 'unknown' (no patronymic — e.g. a Chinese name) / 'pending' → no claim; officer eyeballs.

    # ── Income evidence — the STR document (recipient = the earner, and CURRENT) ──
    # STR is annual/rolling: a stale or rejected STR no longer proves B40 (review). Its
    # recipient must be the earner (matched to the earner IC) — not just a name present.
    from .income_engine import student_str_check
    sc = student_str_check(str_doc) if str_doc is not None else None
    str_verified = False
    if str_doc is None:
        gap.append(_item('income_proof_missing'))
    elif sc and sc['current_status'] in ('stale', 'rejected', 'unconfirmed'):
        review.append(_item('str_not_current', status=sc['current_status']))
    elif sc and 'mismatch' in (sc['name_status'], sc['nric_status']):
        review.append(_item('str_recipient_mismatch', members=[earner]))
    elif sc and (sc['name_status'] == 'match' or sc['nric_status'] == 'match'):
        str_verified = True
        evidence.append(_item('str_verified'))
    else:
        # Present but the recipient couldn't be confirmed (earner IC missing/unreadable,
        # or the STR didn't read) — a human looks.
        review.append(_item('str_present_unverified'))

    # ── Place the verdict ─────────────────────────────────────────────────────
    if gap:
        return _fact('income', 'gap', evidence, gap + review)
    if review:
        return _fact('income', 'review', evidence, review)
    # Income GREEN only when the whole cluster adds up: a CURRENT STR whose recipient is
    # the earner + the earner IC present + the relationship CONFIRMED (mother→BC,
    # father→patronymic, guardian→letter). An unconfirmed relationship → a human places it.
    if str_verified and rel == 'match':
        return _fact('income', 'verified', evidence, [])
    return _fact('income', 'recommend', evidence, [_item('income_unverified_needs_interview')])


def _verdict_income_salary(application, student_name, present):
    """Salary (non-STR) route: one or more working household members, each with their
    own IC + (optional) payslip + EPF, tagged via ``household_member``. Relationship to
    the student: father/brother/sister via the SHARED student-IC patronymic (siblings
    carry the same father's name); mother via birth certificate; guardian via letter.

      - no member ticked          → 'review' (`income_earner_undeclared`).
      - a required IC / relationship doc missing → 'gap' (member-tagged).
      - a relationship/IC that FAILS reading or matching → 'review'.
      - every IC present + every relationship confirmed + ≥1 payslip/EPF → 'verified'
        (the document DATA checks out; the income AMOUNT/B40 test is a later sprint).
      - **never blocks**: assembled but thin proof (no payslip/EPF = informal) or an
        unprovable relationship (e.g. a Chinese-style name with no patronymic) →
        'recommend' + `income_unverified_needs_interview`, for the officer to place."""
    from .income_engine import (working_members, member_relationship_status,
                                relationship_doc_for)
    members = working_members(application)
    if not members:
        # No working member declared → no income information yet → red (see STR route).
        return _fact('income', 'gap', _utility_context(application),
                     [_item('income_earner_undeclared')])

    evidence = _utility_context(application)
    any_financial = False          # at least one member supplied a payslip or EPF
    all_confirmed = True           # every member's relationship is a positive 'match'
    # Per-member gaps are AGGREGATED by code into one item carrying a `members` list —
    # the resolution layer keys tickets by code (one per code per application), so
    # emitting the same code twice would collapse/collide. One ticket lists everyone.
    ic_missing, ic_unreadable, patronymic_mismatch = [], [], []
    bc_missing = bc_mismatch = False
    letter_missing = False

    # Birth certificate / guardianship letter are single household docs (read once).
    bcf = _doc_assist_fields(_latest_doc(application, 'birth_certificate'))
    bc_child, bc_mother = bcf.get('bc_child_name', ''), bcf.get('bc_mother_name', '')
    bc_father = bcf.get('bc_father_name', '')      # #55: mononym father fallback
    g_doc = _latest_doc(application, 'guardianship_letter')
    letter_name = (getattr(g_doc, 'vision_name', '') or '') if g_doc else ''

    for m in members:
        ic_doc = _latest_doc_for_member(application, 'parent_ic', m)
        ic_name = (getattr(ic_doc, 'vision_name', '') or '').strip() if ic_doc else ''
        if ic_doc is None:
            ic_missing.append(m)
            all_confirmed = False
        elif not ic_name:
            ic_unreadable.append(m)
            all_confirmed = False
        else:
            evidence.append(_item('earner_ic_present', member=m, name=ic_name))

        # Relationship proof document (mother → BC, guardian → letter; single docs).
        rel_doc = relationship_doc_for(m)
        if rel_doc == 'birth_certificate' and 'birth_certificate' not in present:
            bc_missing = True
            all_confirmed = False
        elif rel_doc == 'guardianship_letter' and 'guardianship_letter' not in present:
            letter_missing = True
            all_confirmed = False

        # Relationship verdict (father/brother/sister share the patronymic; father also has
        # the #55 BC fallback for a mononym student).
        rel = member_relationship_status(m, student_name, ic_name, bc_child, bc_mother,
                                         letter_name, bc_father)
        if rel == 'match':
            evidence.append(_item('relationship_confirmed', member=m))
        elif rel == 'mismatch':
            if m == 'mother':
                bc_mismatch = True
            else:
                patronymic_mismatch.append(m)
            all_confirmed = False
        else:                       # 'unknown' (no patronymic) / 'pending' (not read) — no claim
            all_confirmed = False

        if (_latest_doc_for_member(application, 'salary_slip', m)
                or _latest_doc_for_member(application, 'epf', m)):
            any_financial = True

    if any_financial:
        evidence.append(_item('income_proof_present'))

    # Assemble the aggregated unresolved items (one per code).
    gap, review = [], []
    if ic_missing:
        gap.append(_item('earner_ic_missing', members=ic_missing))
    if bc_missing:
        gap.append(_item('birth_cert_missing'))
    if letter_missing:
        gap.append(_item('guardianship_letter_missing'))
    if ic_unreadable:
        review.append(_item('earner_ic_unreadable', members=ic_unreadable))
    if patronymic_mismatch:
        review.append(_item('father_patronymic_mismatch', members=patronymic_mismatch))
    if bc_mismatch:
        review.append(_item('birth_cert_mismatch'))

    if gap:
        return _fact('income', 'gap', evidence, gap + review)
    if review:
        return _fact('income', 'review', evidence, review)
    # The cluster adds up (every IC + relationship confirmed, financial evidence present).
    # Income GREEN also needs the AMOUNT to clear the B40 line: sum the earners' pay from
    # the documents → per-capita vs the cohort ceiling (I4). Never blocks — anything we
    # can't compute, or income above the line, goes to the officer/interview.
    if any_financial and all_confirmed:
        from .income_engine import income_per_capita
        ceiling = getattr(getattr(application, 'cohort', None), 'per_capita_ceiling', None)
        pc, _all_known = income_per_capita(application, members)
        if pc is not None and ceiling:
            if pc < ceiling:
                evidence.append(_item('income_per_capita_ok', amount=int(round(pc)), ceiling=ceiling))
                return _fact('income', 'verified', evidence, [])
            return _fact('income', 'recommend', evidence,
                         [_item('income_above_b40_line', amount=int(round(pc)), ceiling=ceiling)])
        # Couldn't compute the per-capita (income unreadable / informal / no household size).
        return _fact('income', 'recommend', evidence, [_item('income_unverified_needs_interview')])
    # Assembled but a human still places it: no payslip/EPF (informal) or a relationship
    # we couldn't machine-confirm. Never blocks.
    return _fact('income', 'recommend', evidence, [_item('income_unverified_needs_interview')])


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
        # The offer letter is compulsory: the programme supports a CONFIRMED place, so
        # without an offer there is nothing to fund (income can be settled at interview,
        # a pathway cannot). Red + submission blocker; the declared pathway rides along
        # as context when present.
        decl = [_item('pathway_declared', pathway=chosen)] if chosen else []
        return _fact('pathway', 'gap', decl, [_item('offer_letter_missing')])

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
