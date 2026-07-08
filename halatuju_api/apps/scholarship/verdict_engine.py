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

Statuses (colour = the cockpit's Kent band, `officerCockpit.factTileTone` +
`docs/scholarship/verdict-confidence-bands.md`):
  verified  — green (Certain);  the AI asserts this fact.
  review    — blue (Probable) when ≥1 genuinely-verified value backs it, else
              amber (Unsure) — "blue needs a green"; confirm the flagged item.
  recommend — amber (Unsure);  evidence assembled, a HUMAN must place the verdict.
  gap       — red (Can't verify); a required input is missing/unreadable/unusable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .services import ic_identity_blockers
from .vision import name_match
from .genuineness.bands import canonical_status


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

# Phase 2 (version history): these three are the MAIN verdict read funnel — every one
# filters `superseded_at__isnull=True` so a replaced document can never count in a verdict.
def _latest_doc(application, doc_type):
    return (application.documents.filter(doc_type=doc_type, superseded_at__isnull=True)
            .order_by('-uploaded_at').first())


def _latest_doc_for_member(application, doc_type, member):
    """The latest LIVE income document of *doc_type* tagged to a specific household
    *member* (salary route). The (doc_type, household_member) pair is the
    single-instance key, so this returns that member's current IC / payslip / EPF."""
    return (application.documents.filter(
                doc_type=doc_type, household_member=member, superseded_at__isnull=True)
            .order_by('-uploaded_at').first())


def _present_doc_types(application):
    return set(application.documents.filter(superseded_at__isnull=True)
               .values_list('doc_type', flat=True))


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


def _doc_wrong_type(doc):
    """True when the doc's genuineness verdict says it is NOT that kind of document at all
    (canonical ``not_<type>``). Its extracted fields then prove nothing — e.g. a non-BC in the
    birth-certificate slot must not confirm a mother↔student relationship (#27, owner 2026-07-08)."""
    if doc is None:
        return False
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    raw = (vf.get('authenticity') or {}).get('status', '')
    return canonical_status(raw, getattr(doc, 'doc_type', None)).startswith('not_')


def _usable_relationship_fields(application, doc_type):
    """The latest live relationship doc of ``doc_type`` + its fields, with a WRONG-TYPE doc treated
    as unusable (doc returned, fields blanked) so no relationship can be read off it. Returns
    ``(doc, fields, unusable)``."""
    d = _latest_doc(application, doc_type)
    if d is not None and _doc_wrong_type(d):
        return d, {}, True
    return d, _doc_assist_fields(d), False


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
    blockers = ic_identity_blockers(application)
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

    # NB the IC genuineness fingerprint is applied AFTER this by the genuineness LADDER
    # (_apply_genuineness_ladder): the band is rebuilt as max(this base, genuineness_step + red chips),
    # where the red chips are the Name/NRIC mismatches emitted here (counted by _identity_red_chips) and
    # the step is the IC fingerprint (suspect −1 / not_ic −2). This function returns the CONTENT base
    # (verified when clean, review when a value mismatches or a sub-read is pending).
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
        # A slip in a different name is a RED Name chip (owner 2026-07-07 red-chip ladder), no longer
        # a hard gap: the ladder deducts −1 (→ Probable) for the lone mismatch, and it stacks with any
        # subject/grade chip + the genuineness step (so someone-else's slip whose grades also diverge
        # still lands Fail). Still an `application_completeness` submission blocker — a SEPARATE gate
        # (services.py), unchanged. We continue below so subject/grade chips are surfaced too.
        unresolved.append(_item('results_slip_name_mismatch'))
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
        # band_confirmed (#71, owner 2026-07-08): the slip's letter AND Malay band agree, so a
        # ±-modifier difference is NOT an OCR blind spot — the read is double-confirmed and the
        # TYPED grade is what's wrong. Distinct copy says so plainly instead of "check by eye".
        code = 'academic_grade_band_mismatch' if m.get('band_confirmed') else 'academic_grade_mismatch'
        unresolved.append(_item(code, subject=m['subject'], typed=m['typed'], slip=m['slip']))
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
    from .income_engine import (utility_per_capita, utility_hardship,
                                unemployment_corroborated_members, household_size_shortfall)
    # Every code emitted here is SOFT evidence — it must sit in officerCockpit.ts SOFT_EVIDENCE
    # (blue needs a green). The `# SOFT` markers are machine-pinned by the jest guard test
    # `soft-evidence-drift.test.ts`; tag any new soft code the same way.
    items = []
    pc = utility_per_capita(application)
    if pc and pc['signal'] == 'b40':
        items.append(_item('utility_percapita_b40', amount=int(round(pc['per_capita']))))  # SOFT
    elif pc and pc['signal'] == 'high':
        items.append(_item('utility_percapita_high', amount=int(round(pc['per_capita']))))  # SOFT
    if utility_hardship(application):
        items.append(_item('utility_hardship'))  # SOFT
    # Phase 2B (P7): an EPF (all-zeros / lapsed) corroborating a member's unemployment — soft
    # reviewer evidence for the "why little income" story. Household context, both routes; never a gate.
    corroborated = unemployment_corroborated_members(application)
    if corroborated:
        items.append(_item('unemployment_epf_corroborated', members=corroborated))  # SOFT
    # Phase 2C (P4): the people described outnumber the stated household size → the per-capita
    # denominator may be too small (income overstated). Soft reviewer flag to confirm; never a gate.
    hs = household_size_shortfall(application)
    if hs:
        items.append(_item('household_size_confirm', described=hs['described'], size=hs['size']))  # SOFT
    return items

def _str_precedence_verdict(application):
    """STR PRECEDENCE (owner 2026-07-07), route-agnostic. A genuine, approved, non-breached STR whose
    recipient matches — exhaustively, name OR nric (``household_str_status``) — a parent/guardian whose
    relationship to the student is CONFIRMED settles income B40 BEFORE the route split; the salary
    route is explored ONLY when no such STR exists (str-proof-spec.md §8). Returns an income ``_fact``,
    or None when there is no dispositive STR (→ the route-specific assessment runs unchanged).

      - current STR + confirmed parent/guardian recipient → 'verified' (Certain).
      - unconfirmed STR (approved, no date) + confirmed → 'review' (Probable / blue).
      - recipient matches an on-file IC but the parent/guardian LINK isn't confirmed → None (fall
        through): an unproven relationship isn't an established parent/guardian yet, so the route
        logic asks for the missing tie (BC / patronymic) — the fraud guard the salary route already
        applied via ``confirmed_members``."""
    from .income_engine import (household_str_status, _member_ic_doc,
                                member_relationship_status, chain_verified_earner,
                                student_name_for_link)
    grade, member = household_str_status(application)
    if not grade or not member:
        return None
    # The IC-aware name: a typed profile name without the A/P connector must not lose the
    # patronymic father link when the student's own verified IC carries it (#88).
    student_name = student_name_for_link(application)
    ic_doc = _member_ic_doc(application, member)
    ic_name = (getattr(ic_doc, 'vision_name', '') or '').strip() if ic_doc else ''
    # Confirm the matched recipient really is the student's parent/guardian: father → patronymic,
    # mother → birth certificate, guardian → letter, or the BC↔proof IC-number chain (#9).
    # A WRONG-TYPE relationship doc is unusable — its fields must not confirm anything (#27).
    _, bcf, _ = _usable_relationship_fields(application, 'birth_certificate')
    g_doc, _, g_unusable = _usable_relationship_fields(application, 'guardianship_letter')
    rel = member_relationship_status(member, student_name, ic_name,
                                     bcf.get('bc_child_name', ''), bcf.get('bc_mother_name', ''),
                                     ('' if g_unusable else (getattr(g_doc, 'vision_name', '') or '')),
                                     bcf.get('bc_father_name', ''))
    if rel != 'match' and member in ('mother', 'father') and chain_verified_earner(application, member):
        rel = 'match'
    if rel != 'match':
        return None            # recipient not yet an established parent/guardian → route logic runs
    evidence = _utility_context(application)
    if ic_name:
        evidence.append(_item('earner_ic_present', member=member, name=ic_name))
    evidence.append(_item('relationship_confirmed', member=member))
    evidence.append(_item('str_verified'))
    if grade == 'current':
        return _fact('income', 'verified', evidence, [])
    # unconfirmed (approved, no date) → Probable (blue); confirm the cycle at interview.
    return _fact('income', 'review', evidence, [_item('str_not_current', status='unconfirmed')])


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
                                guardian_relationship, chain_verified_earner,
                                student_name_for_link)
    evidence, gap, review = _utility_context(application), [], []
    present = _present_doc_types(application)
    # IC-aware (#88): prefer the student's verified IC read when the typed name lacks the
    # patronymic connector, so the father link doesn't silently die on a typing habit.
    student_name = student_name_for_link(application)
    earner = (getattr(application, 'income_earner', '') or '').strip()
    route = (getattr(application, 'income_route', '') or '').strip()

    # STR PRECEDENCE (owner 2026-07-07): a genuine, approved, non-breached STR whose recipient
    # matches ANY parent/guardian settles B40 before the income route is even considered — the
    # salary route is explored ONLY when no such STR exists. Route- and tag-agnostic, so a
    # misfiled route/earner (e.g. #45 on the salary route with the STR tagged 'mother') no longer
    # drops a genuine-STR household to salary.
    settled = _str_precedence_verdict(application)
    if settled is not None:
        return settled

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
    # Code-health S4 #17: select the EARNER'S IC (member-tagged, with the earner-only
    # legacy-blank fallback) — the member-agnostic latest parent_ic could pick another
    # member's card after a route switch with several ICs on file, making this verdict
    # contradict the student checklist (which uses _member_ic_doc) on identical data.
    from .income_engine import _member_ic_doc
    ic_doc = _member_ic_doc(application, earner)
    earner_ic_name = (getattr(ic_doc, 'vision_name', '') or '').strip() if ic_doc else ''
    if ic_doc is None:
        gap.append(_item('earner_ic_missing', members=[earner]))
    elif not earner_ic_name:
        review.append(_item('earner_ic_unreadable', members=[earner]))
    else:
        evidence.append(_item('earner_ic_present', name=earner_ic_name))

    # ── Relationship: prove the earner is the student's family ────────────────
    # A WRONG-TYPE relationship doc (#27: a non-BC in the birth-certificate slot) is UNUSABLE —
    # its fields prove nothing, and the student gets a specific re-upload ticket (gap, like a
    # missing doc) instead of the officer-only generic genuineness caveat.
    rel = None
    if earner == 'father':
        # Patronymic, with a BC fallback for a mononym student (#55) when a BC is uploaded.
        _, bcf, _ = _usable_relationship_fields(application, 'birth_certificate')
        rel = father_link(student_name, earner_ic_name,
                          bcf.get('bc_child_name', ''), bcf.get('bc_father_name', ''))
    elif earner == 'mother':
        if 'birth_certificate' not in present:
            gap.append(_item('birth_cert_missing'))
        else:
            _, bcf, bc_unusable = _usable_relationship_fields(application, 'birth_certificate')
            if bc_unusable:
                gap.append(_item('birth_cert_not_genuine'))
            else:
                rel = mother_relationship(bcf.get('bc_child_name', ''), bcf.get('bc_mother_name', ''),
                                          student_name, earner_ic_name)
    elif earner == 'guardian':
        if 'guardianship_letter' not in present:
            gap.append(_item('guardianship_letter_missing'))
        else:
            g, _, g_unusable = _usable_relationship_fields(application, 'guardianship_letter')
            if g_unusable:
                gap.append(_item('guardianship_letter_not_genuine'))
            else:
                rel = guardian_relationship(getattr(g, 'vision_name', '') or '', earner_ic_name)
    # IC-number chain: the BC's parent number matching the income proof's number confirms a
    # mother/father earner even when the IC uploaded in their slot is the wrong card (#9).
    if rel != 'match' and earner in ('mother', 'father') and chain_verified_earner(application, earner):
        rel = 'match'
    if rel == 'match':
        evidence.append(_item('relationship_confirmed'))
    elif rel == 'mismatch':
        if earner == 'father':
            review.append(_item('father_patronymic_mismatch', members=[earner]))
        else:
            review.append(_item('birth_cert_mismatch'))
    # 'unknown' (no patronymic — e.g. a Chinese name) / 'pending' → no claim; officer eyeballs.

    # ── Income evidence — the STR document (recipient = the earner, and CURRENT) ──
    # The STR currency state (docs/scholarship/str-proof-spec.md) carries its own decisive copy via
    # the `status` param: wrong_type (not an STR at all) / rejected (Ditolak) / stale (prior-year) /
    # unreadable (cropped) / unconfirmed (approved, no date → confirm currency). Anything that isn't
    # a CURRENT approved STR keeps the income fact off green — a human looks (and, post Sprint-2, the
    # salary route is assessed when the STR is wrong_type/rejected).
    from .income_engine import student_str_check, income_headroom
    sc = student_str_check(str_doc) if str_doc is not None else None
    str_verified = False
    # A wrong_type (not an STR at all) or rejected (Ditolak) STR is definitively NOT a current STR;
    # the family may still be B40 on their salary/benefit docs, so we fall through to the salary
    # route below rather than freezing on the failed STR (str-proof-spec.md §6).
    str_failed = bool(sc and sc['current_status'] in ('wrong_type', 'rejected'))
    # STR-proof band matrix (str-proof-spec.md): approval Status × cycle Current →
    #   Lulus + dated-current → Certain (verified) ; Lulus + no date → Probable (review, needs a green)
    #   Lulus + prior-year (stale) OR approval-unread (unreadable) → Unsure (recommend → amber)
    #   Ditolak / not-an-STR → Fail, with the salary route as the net beneath it (str_failed).
    # 'stale'/'unreadable' → Unsure (NOT the blue 'review'): a review tile would read BLUE off the
    # verified earner-IC/relationship greens, overstating a doc whose cycle is old or whose approval
    # never read. Same reasoning as the salary unsure/over bands below.
    str_unsure = bool(sc and sc['current_status'] in ('stale', 'unreadable'))
    # V5 (#10): a POSITIVE recipient mismatch (the STR is in someone else's name) bands Unsure
    # (amber) per str-proof-spec.md §8 — never a blue 'review' read off the earner-IC/relationship
    # greens, which would overstate an STR that provably belongs to a different person.
    str_mismatch = False
    if str_doc is None:
        gap.append(_item('income_proof_missing'))
    elif sc and sc['current_status'] in ('stale', 'rejected', 'unconfirmed', 'wrong_type', 'unreadable'):
        review.append(_item('str_not_current', status=sc['current_status']))
    elif sc and 'mismatch' in (sc['name_status'], sc['nric_status']):
        str_mismatch = True
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
    # Evidence-driven fall-through (§6): the STR isn't a current STR, but salary/benefit docs on file
    # may still show B40 — assess the salary route and let the headroom band drive the income tile.
    # NB unsure/over return 'recommend' (→ amber) rather than 'review': a review tile reads BLUE off
    # the verified earner-IC/relationship greens, which would overstate an unsure income.
    if str_failed:
        # Code-health S4 #19: assess EVERY member with income evidence, not just the single
        # STR-route earner — after a route switch, tagged payslips/EPF for other members can
        # exist, and excluding them understates the household gross (a genuinely-over
        # household could band 'probable' off one earner's slip).
        from .income_engine import effective_working_members
        hh_members = list(dict.fromkeys([earner] + list(effective_working_members(application))))
        band, ctx = income_headroom(application, hh_members)
        if band == 'over':
            # Salary route FAILS — household income is over the B40 line → income fact FAILS (RED).
            # (Advisory only: the tiles guide, the officer still places the final verdict — not an
            # auto-reject; circumstances may still apply at interview.)
            return _fact('income', 'gap', evidence, review + [
                _item('income_above_b40_line', amount=ctx['per_capita'], ceiling=ctx['per_capita_ceiling'])])
        if band == 'unsure':
            return _fact('income', 'recommend', evidence, review + [
                _item('income_salary_unsure', amount=ctx['gross'])])
        if band == 'probable':
            evidence.append(_item('income_salary_probable', amount=ctx['gross']))
            return _fact('income', 'review', evidence, review)
        # 'unknown' — the STR failed AND there are no usable salary docs to assess → Unsure (amber):
        # we simply can't confirm B40, a human looks. NOT a blue review off incidental earner greens.
        return _fact('income', 'recommend', evidence, review)
    if str_unsure:
        # Lulus-but-stale or approval-unread → Unsure (amber), not a blue review off incidental greens.
        return _fact('income', 'recommend', evidence, review)
    if str_mismatch:
        # Recipient ≠ earner → Unsure (amber) per spec §8: an approved STR provably in someone
        # ELSE'S name proves nothing about this household; a human owns the call.
        return _fact('income', 'recommend', evidence, review)
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
    from .income_engine import (effective_working_members, member_relationship_status,
                                relationship_doc_for, chain_verified_earner,
                                earner_monthly_income, has_valid_str)
    members = effective_working_members(application)
    if not members:
        # No working member declared → no income information yet → red (see STR route).
        return _fact('income', 'gap', _utility_context(application),
                     [_item('income_earner_undeclared')])

    evidence = _utility_context(application)
    any_financial = False          # at least one member supplied a payslip/EPF (or an ACCEPTED declared income)
    all_confirmed = True           # every member's relationship is a positive 'match'
    declared_backed, declared_unproven = [], []   # Phase 2A: members carried by a declared amount
    # Per-member gaps are AGGREGATED by code into one item carrying a `members` list —
    # the resolution layer keys tickets by code (one per code per application), so
    # emitting the same code twice would collapse/collide. One ticket lists everyone.
    ic_missing, ic_unreadable, patronymic_mismatch = [], [], []
    bc_missing = bc_mismatch = False
    letter_missing = False

    # Birth certificate / guardianship letter are single household docs (read once). A WRONG-TYPE
    # doc in the slot is UNUSABLE (#27): fields blanked so no relationship reads off it, and the
    # student gets a specific re-upload ticket below.
    _, bcf, bc_unusable = _usable_relationship_fields(application, 'birth_certificate')
    bc_child, bc_mother = bcf.get('bc_child_name', ''), bcf.get('bc_mother_name', '')
    bc_father = bcf.get('bc_father_name', '')      # #55: mononym father fallback
    g_doc, _, letter_unusable = _usable_relationship_fields(application, 'guardianship_letter')
    letter_name = ('' if letter_unusable else ((getattr(g_doc, 'vision_name', '') or '') if g_doc else ''))

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
        # IC-number chain: BC parent number == income-proof number confirms a mother/father earner
        # even when the IC uploaded in their slot is the wrong card or absent (#9).
        if rel != 'match' and m in ('mother', 'father') and chain_verified_earner(application, m):
            rel = 'match'
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
        else:
            # Phase 2A: no payslip/EPF for this member — a DECLARED informal amount may still
            # carry their income (accepted via a valid STR or a supporting doc), else it's unproven.
            _amt, _src = earner_monthly_income(application, m)
            if _src in ('declared_str', 'declared_evidenced'):
                any_financial = True
                declared_backed.append(m)
            elif _src == 'declared_unproven':
                declared_unproven.append(m)

    if any_financial:
        evidence.append(_item('income_proof_present'))

    # Assemble the aggregated unresolved items (one per code).
    gap, review = [], []
    if ic_missing:
        gap.append(_item('earner_ic_missing', members=ic_missing))
    if bc_missing:
        gap.append(_item('birth_cert_missing'))
    elif bc_unusable and any(relationship_doc_for(m) == 'birth_certificate' for m in members):
        gap.append(_item('birth_cert_not_genuine'))       # required + wrong-type → re-upload (#27)
    if letter_missing:
        gap.append(_item('guardianship_letter_missing'))
    elif letter_unusable and any(relationship_doc_for(m) == 'guardianship_letter' for m in members):
        gap.append(_item('guardianship_letter_not_genuine'))
    if ic_unreadable:
        review.append(_item('earner_ic_unreadable', members=ic_unreadable))
    if patronymic_mismatch:
        review.append(_item('father_patronymic_mismatch', members=patronymic_mismatch))
    if bc_mismatch:
        review.append(_item('birth_cert_mismatch'))

    if gap:
        return _fact('income', 'gap', evidence, gap + review)
    # Phase 2A: an ACCEPTED declared income is honest evidence — surface it, and say WHY the
    # self-report counts (a valid STR is the means-test, else a supporting doc backs it). Two
    # distinct codes, not an ICU `select` param: the custom `t` has no MessageFormat engine.
    if declared_backed:
        code = 'income_declared_accepted_str' if has_valid_str(application) else 'income_declared_accepted_evidenced'
        evidence.append(_item(code, members=declared_backed))
    # A declared income with NO valid STR and NO supporting doc can't count yet. Firm-steward
    # stance: Unsure = proof required from the student (Check 2 raises the income_support_doc
    # request). Route to 'recommend' (amber) — never a blue read off the earner-IC/relationship
    # greens. Code-health S4 #20: this must run BEFORE the 'review' return — 'review' is the
    # BLUE band, so an unrelated review item (e.g. an unreadable IC) used to hide the unproven
    # declaration behind blue, contradicting the amber rule above.
    if declared_unproven:
        return _fact('income', 'recommend', evidence,
                     review + [_item('income_declared_needs_evidence', members=declared_unproven)])

    # NB a valid non-breached STR no longer needs handling here: STR PRECEDENCE (_str_precedence_verdict)
    # settles it BEFORE the route split, so this salary path is only reached when there is no dispositive
    # STR. Salary is the genuine fallback (str-proof-spec.md §8).
    if review:
        return _fact('income', 'review', evidence, review)
    # The cluster adds up (every IC + relationship confirmed, financial evidence present).
    # Income GREEN also needs the AMOUNT to clear the B40 line (I4) — via the SAME
    # ``income_headroom`` band the STR fall-through uses (code-health S4 #14: the old
    # per-capita-only strict-< test here contradicted spec §7's two-test rule — gross
    # ceiling primary, per-capita a safety net — so the two routes could give opposite
    # answers for one household, and pc == ceiling read as "over"). Never blocks —
    # over-the-line or uncomputable goes to the officer/interview.
    if any_financial and all_confirmed:
        from .income_engine import income_headroom
        band, ctx = income_headroom(application, members)
        pc = ctx.get('per_capita')
        ceiling = ctx.get('per_capita_ceiling')
        if band == 'over':
            # V5 (#10): over-the-line = RED on BOTH routes (spec §8 rule 1). The STR fall-through
            # already banded the identical household economics 'gap'; the assembled salary route
            # banding it amber was the three-way seam inconsistency. Advisory only — the officer
            # still places the final verdict; circumstances may apply at interview.
            return _fact('income', 'gap', evidence,
                         [_item('income_above_b40_line', amount=pc, ceiling=ceiling)])
        if band in ('probable', 'unsure'):
            # Under the (two-test) line — I4 keeps its historical binary green here: the
            # cluster is fully confirmed on this path, so the fall-through's thin-margin
            # 'unsure' demotion deliberately does NOT apply (that grading compensates for
            # an UNverified household; the salary-track redesign will revisit).
            evidence.append(_item('income_per_capita_ok', amount=pc, ceiling=ceiling))
            return _fact('income', 'verified', evidence, [])
        # 'unknown' — couldn't compute (unreadable income / no household size) and no dispositive STR
        # (precedence would have settled one) → a human places it at interview.
        return _fact('income', 'recommend', evidence, [_item('income_unverified_needs_interview')])
    # Assembled but a human still places it: no payslip/EPF (informal) or a relationship
    # we couldn't machine-confirm. Never blocks. (A dispositive STR would already have been
    # settled by STR precedence upstream, so there is none to lean on here.)
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

    No offer letter → 'gap' (red) AND a submission blocker (`offer_letter_missing`
    in consent_blockers): the programme funds a CONFIRMED place, so without an offer
    there is nothing to fund. (An older design tolerated "declared-only → review";
    that changed with the 2026-06-07 confidence-scale alignment.)"""
    from .pathway_engine import student_offer_check
    evidence, unresolved = [], []
    offer = _latest_doc(application, 'offer_letter')
    chosen = (application.chosen_pathway or application.intended_pathway or '').strip()

    if offer is None:
        # The offer letter is compulsory: the programme supports a CONFIRMED place, so
        # without an offer there is nothing to fund (income can be settled at interview,
        # a pathway cannot). Red + submission blocker; the declared pathway rides along
        # as context when present.
        decl = [_item('pathway_declared', pathway=chosen)] if chosen else []  # SOFT
        return _fact('pathway', 'gap', decl, [_item('offer_letter_missing')])

    chk = student_offer_check(offer)
    # Identity on the letter (name + IC): a wrong name OR IC is a RED content chip the ladder counts
    # (owner 2026-07-07), NOT an early return — a lone name/IC slip → −1 (Probable), both → −2
    # (Unsure), and it stacks with the offer's genuineness step (so #12's fake offer + name+IC+pathway
    # mismatch → Fail). Amber-not-red by decision (decisions.md 2026-07-04): usually a family upload
    # slip-up, the offer is not the identity anchor the IC is, no submission block wanted. We DON'T
    # early-return, so the pathway chip below is also evaluated (all three chips are independent).
    if chk['ic'] == 'mismatch' or chk['name'] == 'mismatch':
        unresolved.append(_item('offer_name_mismatch'))
    # A general NOTICE / wrong document (body read fine — issuer/programme present — but no name or
    # IC, e.g. a "your offer will be released later" memo) vs a genuinely blurry scan → grey/pending
    # (an under-read, capped at Probable), NOT a red chip. Only when identity didn't already flag.
    elif chk['name'] in ('unreadable', 'pending') and chk['ic'] in ('unreadable', 'pending'):
        if chk['programme'] or chk['institution']:
            return _fact('pathway', 'review', evidence, [_item('offer_no_identity')])
        return _fact('pathway', 'review', evidence, [_item('offer_unreadable')])

    prog, inst = chk['programme'], chk['institution']
    confirmed = application.pathway_confirmed_at is not None
    if confirmed:
        evidence.append(_item('pathway_confirmed', programme=prog, institution=inst))
    elif prog or inst:
        evidence.append(_item('offer_programme', institution=inst, programme=prog))

    # The offer names a genuinely different place/field than declared → a RED Pathway chip + the
    # confirm query (Check-2 backstop; record realigns on Yes). Suppressed once the student confirms.
    if chk['pathway'] == 'mismatch' and not confirmed:
        unresolved.append(_item('pathway_confirm', programme=prog, institution=inst,
                                declared_programme=chk['declared_programme'],
                                declared_institution=chk['declared_institution']))

    # Base band (the ladder then applies the genuineness step + red-chip deductions): a clean letter
    # with a readable programme (or an already-confirmed pathway) settles it → verified; any red chip
    # or an unread programme is an under-claim → review.
    if not unresolved:
        if prog or inst or confirmed:
            return _fact('pathway', 'verified', evidence, unresolved)
        return _fact('pathway', 'review', evidence, [_item('offer_unreadable')])
    return _fact('pathway', 'review', evidence, unresolved)


# ── Aggregator ───────────────────────────────────────────────────────────────

# Which documents feed each fact's genuineness FLAT CAP. As of the 2026-07-07 ladder, identity,
# academic and pathway use `_apply_genuineness_ladder` instead (a graded step, not a flat cap), so
# only INCOME remains on the flat cap — computed per-route (see `_income_genuineness_docs`), only the
# docs REQUIRED to prove income can cap it.
_FACT_GENUINENESS_DOCS: dict = {}


def _income_genuineness_docs(application):
    """Documents whose genuineness may lower the INCOME verdict — ONLY the docs REQUIRED to prove
    income on the application's route. Optional corroboration (EPF, salary slip) never caps the
    verdict: a dodgy optional doc still raises the officer ``document_not_genuine`` flag / a
    Check-2 query, but the route's own required proof decides the verdict.

    - STR route → the STR (+ the birth certificate when the earner is the mother, the required
      relationship proof). A future-dated / typed *optional* EPF does NOT cap.
    - Salary route → the required salary slip isn't fingerprintable and EPF is optional, so no
      fingerprint-driven income cap applies."""
    route = (getattr(application, 'income_route', '') or '').lower()
    if route == 'str':
        docs = ['str']
        if (getattr(application, 'income_earner', '') or '').lower() == 'mother':
            docs.append('birth_certificate')
        return docs
    return []


def _fact_genuineness_docs(application, fact_name):
    if fact_name == 'income':
        return _income_genuineness_docs(application)
    return _FACT_GENUINENESS_DOCS.get(fact_name, [])


def _suspect_genuineness(application, doc_types):
    """The CANONICAL genuineness status among the latest of the given doc types if it warrants a
    soft cap ('suspect' / 'not_<type>'), else ''. Reads vision_fields only and folds any value —
    current or legacy — via ``canonical_status``, so old stored authenticity still caps. SOFT: the
    reviewer is the authority."""
    for dt in doc_types:
        d = _latest_doc(application, dt)
        vf = d.vision_fields if (d and isinstance(d.vision_fields, dict)) else {}
        raw = (vf.get('authenticity') or {}).get('status', '')
        st = canonical_status(raw, getattr(d, 'doc_type', None) or dt)
        if st and st != 'genuine':
            return st
    return ''


def _str_wrong_type(application):
    """True when the latest STR doc is a GENUINE document of the WRONG kind in the STR slot (a
    payslip / SARA letter / SALINAN) — its currency state is 'wrong_type'. Used to suppress the
    misleading "not a genuine original" genuineness caveat (str-proof-spec.md §4)."""
    from .income_engine import student_str_check
    d = _latest_doc(application, 'str')
    if d is None:
        return False
    sc = student_str_check(d)
    return bool(sc and sc.get('current_status') == 'wrong_type')


def _apply_genuineness_caps(application, facts):
    """Soft post-cap (Sprint 2): a suspect/wrong-type feeding document lowers a fact from
    'verified' to 'review' and adds a `document_not_genuine` caveat — the AI is less certain
    when the evidence may not be a genuine document. NEVER moves a fact to 'gap'/fail and
    never upgrades. Only bites when the (flag-gated) genuineness check has run."""
    for fact in facts:
        dts = _fact_genuineness_docs(application, fact['fact'])
        # A wrong_type STR — a GENUINE non-STR document in the STR slot (a payslip, a SARA letter) —
        # is already explained by the str_not_current('wrong_type') item; the genuineness "may not be
        # a genuine original" caveat is misleading (the doc IS genuine, just the wrong KIND), so don't
        # double-flag it. (str-proof-spec.md §4.)
        if 'str' in dts and _str_wrong_type(application):
            dts = [d for d in dts if d != 'str']
        # Same principle for a wrong-type RELATIONSHIP doc (#27): the specific re-upload ticket
        # (birth_cert_not_genuine / guardianship_letter_not_genuine) already explains it — don't
        # stack the generic officer-only caveat on top.
        specific = {i['code'] for i in fact['unresolved']}
        if 'birth_cert_not_genuine' in specific:
            dts = [d for d in dts if d != 'birth_certificate']
        if 'guardianship_letter_not_genuine' in specific:
            dts = [d for d in dts if d != 'guardianship_letter']
        if not dts or any(i['code'] == 'document_not_genuine' for i in fact['unresolved']):
            continue
        st = _suspect_genuineness(application, dts)
        if st:
            if fact['status'] == 'verified':
                fact['status'] = 'review'
            fact['unresolved'].append(_item('document_not_genuine', status=st))
    return facts


# ── Genuineness / eligibility LADDER (identity + academic + pathway) — owner 2026-07-07 ──
# The band is REBUILT explicitly (not "step the bespoke content band"):
#
#     band_index = max(base_index, genuineness_step + red_chip_count),  floored at 'gap'
#     _BAND_LADDER = ('verified'=Certain, 'review'=Probable, 'recommend'=Unsure, 'gap'=Fail)
#
#   • genuineness_step — by SCORE, uniform for every signature-scored doc (offers INCLUDED as of
#     MODEL_VERSION 1.4.0): genuine (p≥0.70) → 0, suspect (0.35–0.70) → 1, fake (p<0.35) → 2.
#   • red_chip_count — one −1 per RED content variable: Identity Name·NRIC; Academic Name·Subjects·
#     Results; Pathway Name·IC·Pathway. A variable is red when its value MISMATCHES or is
#     required-but-missing on an extracted offer (merely unread/pending → grey, the base band's
#     under-claim). The PATHWAY variable is additionally red when the document cannot establish any
#     pathway — a non-genuine offer (suspect/fake: interview slip, pemakluman, private-IPTS letter)
#     proves no pathway, so its chip stacks with the genuineness step (owner arithmetic: #31/#131
#     suspect −1 + pathway −1 = Unsure; #84 fake −2 + pathway −1 = Fail).
#   • base_index — the `_verdict_*` band, which carries only the missing→gap and unread→review
#     under-claims (mismatches are NOT baked into it any more, they are chips); `max` keeps an
#     unread-but-genuine doc at Probable rather than letting 0 chips + step 0 read Certain.
#
# Worked (owner-verified): #12 offer p=0.30 → fake(2) + Name+IC+Pathway(3) = 5 → Fail; #31 pemakluman
# p=0.40 → suspect(1) + Pathway(1), Name+IC green = 2 → Unsure. A lone academic name mismatch on a
# genuine slip → 0+1 = Probable (softens the old hard-Fail — owner accepted, rare / OCR misread).
# Income keeps its own model (STR-precedence + headroom / flat cap).
_BAND_LADDER = ('verified', 'review', 'recommend', 'gap')

# The document whose genuineness fingerprint scores each card's step.
_LADDER_DOCS = {'identity': ['ic'], 'academic': ['results_slip'], 'pathway': ['offer_letter']}


def _genuineness_step(application, doc_types):
    """0 (genuine / not scored), 1 (suspect), or 2 (fake / wrong-type) from the feeding docs'
    fingerprint — by SCORE (``canonical_status`` folds band_for's genuine/suspect/not_<type>)."""
    st = _suspect_genuineness(application, doc_types)
    if not st:
        return 0
    return 2 if st.startswith('not_') else 1


def _genuineness_reason(application, doc_types):
    """The human reason string from the first non-genuine feeding doc (for the ic_low_confidence copy)."""
    for dt in doc_types:
        d = _latest_doc(application, dt)
        vf = d.vision_fields if (d and isinstance(d.vision_fields, dict)) else {}
        auth = vf.get('authenticity') or {}
        if canonical_status(auth.get('status'), getattr(d, 'doc_type', None) or dt) not in ('', 'genuine'):
            return auth.get('reason', '')
    return ''


def _identity_red_chips(application):
    """RED identity content chips — Name and/or NRIC MISMATCH (0–2). Mirrors the name/NRIC reads in
    ``_verdict_identity`` (and the cockpit's identity chips). A missing/unreadable IC is a gap
    pre-empt, not a chip."""
    if _latest_doc(application, 'ic') is None:
        return 0
    blockers = ic_identity_blockers(application)
    return (1 if 'ic_nric_mismatch' in blockers else 0) + \
           (1 if 'ic_name_mismatch' in blockers else 0)


def _academic_red_chips(application):
    """RED academic content chips — Name (slip in a different name), Subjects (a slip subject the
    student never entered), Results (a CONFIRMED typed-vs-slip grade mismatch). 0–3. An uncertain
    grade (band disagreement) and an unread slip are grey/pending, not red."""
    from .academic_engine import compare_academics, read_slip, _slip_name_status
    slip = _latest_doc(application, 'results_slip')
    if slip is None:
        return 0
    n = 1 if _slip_name_status(slip) == 'mismatch' else 0
    data = read_slip(slip)
    if data['names']:
        cmp = compare_academics(getattr(application.profile, 'grades', None), data)
        if cmp['missing']:
            n += 1
        if cmp['mismatched']:
            n += 1
    return n


# A pathway identity chip (Name / IC) is RED when its value MISMATCHES **or** is required-but-missing
# on an extracted offer (owner 2026-07-07: "missing-required on an offer = red"). This mirrors the
# cockpit's own chip tone exactly — `officerCockpit.factStatus` reds 'mismatch' AND 'unreadable' (an
# empty candidate field on an offer that WAS OCR'd), so the verdict band and the visible chips agree.
# 'pending' (not yet extracted) is NOT red — it's a genuine unknown.
_OFFER_CHIP_RED = {'mismatch', 'unreadable'}


def _pathway_effective_step(application):
    """The offer's genuineness step AFTER the reporting-date BONUS (owner 2026-07-08): a VALIDATED
    official registration summons (``offer_reporting_bonus`` — the issuer family's own Malay label +
    the public-issuer signature on the page + no private-company marker) is genuineness evidence and
    lifts the step one band, floored at 0 (suspect→0, fake→1). The bonus is genuineness-only: the
    Name/IC/pathway-mismatch content chips, the Official chip's colour, ``offer_official_status``
    and the Check-2 official-doc request are all UNTOUCHED."""
    from .pathway_engine import offer_reporting_bonus
    step = _genuineness_step(application, ['offer_letter'])
    if step and offer_reporting_bonus(_latest_doc(application, 'offer_letter')):
        step -= 1
    return step


def _pathway_red_chips(application):
    """RED pathway content chips — Name, IC (wrong-person OR the offer doesn't show one) and Pathway.
    0–3. Reads the SAME ``student_offer_check`` the cockpit chips + ``_verdict_pathway`` read.

    The Pathway VARIABLE (owner 2026-07-08, off #131/#84 — refining the locked #31 example) asks
    "does this document establish the declared pathway?" — red when the offer names a genuinely
    DIFFERENT place/field than declared (unreconciled), **or** when the document cannot establish ANY
    pathway because it is not a genuine official offer (suspect / fake / non-official — an interview
    slip, a pemakluman, a private-IPTS letter). This mirrors the cockpit chip exactly
    (officerCockpit ``documentFacts``: notOfficial → Pathway red), so the tile counts precisely the
    chips the reviewer sees. NB it deliberately STACKS with the genuineness step — the owner's
    arithmetic: #31/#131 suspect(−1) + pathway-not-established(−1) = Unsure; #84 fake(−2) +
    pathway(−1) = Fail. 'Official' remains the step's own display chip, never counted here.

    Reporting-date BONUS (owner 2026-07-08): "not official" is judged on the EFFECTIVE step — a
    suspect offer carrying a validated official registration summons (step lifted to 0) DOES
    establish the pathway (the letter provably summons the student to register at a public
    institution), so its Pathway chip is not red. A fake offer stays not-official even with the
    bonus (effective step 1). The mismatch arm is untouched — the bonus never offsets a genuine
    declared-vs-offer clash."""
    from .pathway_engine import student_offer_check
    offer = _latest_doc(application, 'offer_letter')
    if offer is None:
        return 0
    chk = student_offer_check(offer)
    n = (1 if chk['name'] in _OFFER_CHIP_RED else 0) + (1 if chk['ic'] in _OFFER_CHIP_RED else 0)
    not_official = _pathway_effective_step(application) > 0
    if not_official or (chk['pathway'] == 'mismatch' and application.pathway_confirmed_at is None):
        n += 1
    return n


_LADDER_CHIPS = {'identity': _identity_red_chips, 'academic': _academic_red_chips,
                 'pathway': _pathway_red_chips}


def _add_genuineness_caveat(application, fact, docs, step):
    """Surface WHY the genuineness step bit (the 'Official' dimension), decoupled from the content
    chips. Identity → ``ic_low_confidence``; academic → ``document_not_genuine``; pathway → the
    confident ``offer_not_official`` when fake (step 2, an award CONFIDENT_DISQUALIFIER), else the
    softer ``document_not_genuine`` (suspect / cropped)."""
    if step == 0:
        return
    st = _suspect_genuineness(application, docs)
    if fact['fact'] == 'identity':
        code = 'ic_low_confidence'
    elif fact['fact'] == 'pathway' and step == 2:
        code = 'offer_not_official'
    else:
        code = 'document_not_genuine'
    if any(i['code'] == code for i in fact['unresolved']):
        return
    if code == 'ic_low_confidence':
        fact['unresolved'].append(_item('ic_low_confidence', status=st,
                                        reason=_genuineness_reason(application, docs)))
    elif code == 'offer_not_official':
        fact['unresolved'].append(_item('offer_not_official'))
    else:
        fact['unresolved'].append(_item('document_not_genuine', status=st))


def _apply_genuineness_ladder(application, facts):
    """Rebuild the identity/academic/pathway band as ``max(base, genuineness_step + red_chips)``,
    floored at 'gap' (income keeps the flat cap). Downgrade-only: a genuine doc with clean content
    (step 0, 0 chips) leaves the base untouched.

    PATHWAY uses the EFFECTIVE step (raw − the reporting-date bonus) for the BAND, but the RAW step
    for the caveat — so a suspect-with-bonus offer can read Certain while the tile still carries the
    truthful "may not be a genuine original" line (the Official chip stays amber, Check-2 still
    requests the official copy). A ``str_verified``-style evidence line explains the lift."""
    for fact in facts:
        docs = _LADDER_DOCS.get(fact['fact'])
        if not docs:
            continue
        step = _genuineness_step(application, docs)
        band_step = step
        if fact['fact'] == 'pathway':
            band_step = _pathway_effective_step(application)
            if band_step < step:                 # the bonus fired — say why the band lifted
                fact['evidence'].append(_item('offer_reporting_official'))
        chips = _LADDER_CHIPS[fact['fact']](application)
        try:
            base_i = _BAND_LADDER.index(fact['status'])
        except ValueError:
            base_i = 0
        fact['status'] = _BAND_LADDER[min(max(base_i, band_step + chips), len(_BAND_LADDER) - 1)]
        _add_genuineness_caveat(application, fact, docs, step)
    return facts


def build_verdict(application) -> list[dict]:
    """The four-fact verification verdict in fixed order (identity, academic,
    pathway, income). Pure + deterministic — safe to call inside a serializer
    GET. Each fact: ``{fact, status, evidence[], unresolved[]}`` where evidence
    and unresolved items are ``{code, params}`` dicts resolved on the frontend.

    Genuineness is applied last: the LADDER (identity/academic/pathway) + the flat cap (income)."""
    facts = [
        _verdict_identity(application),
        _verdict_academic(application),
        _verdict_pathway(application),
        _verdict_income(application),
    ]
    return _apply_genuineness_ladder(application, _apply_genuineness_caps(application, facts))
