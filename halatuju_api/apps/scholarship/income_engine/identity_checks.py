"""The per-document identity reads: the identity a proof cluster is anchored to, the earner
IC check, the cluster a document belongs to, which member a document resolves to, and the
income-proof check.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

from ..vision import nric_close, relationship_name_match as name_match
from .buckets import _name_bucket, _nric_bucket
from .relationships import _relationship_inputs, member_relationship_status, student_name_for_link
from .salary_figures import _doc_fields


def _cluster_proof_identity(application, member):
    """The income proof's recipient identity ``(kind, name, nric)`` that the earner IC must
    match — the whole point of uploading the IC. STR route → the STR (recipient_name/nric);
    salary route → the member's salary slip, then EPF (name/nric). ('', '', '') when no
    income proof is present yet to compare against."""
    route = (getattr(application, 'income_route', '') or '').strip()
    if route == 'str':
        p = (application.documents.filter(doc_type='str', superseded_at__isnull=True)
             .order_by('-uploaded_at').first())
        if p:
            f = _doc_fields(p)
            return 'str', (f.get('recipient_name', '') or '').strip(), (f.get('recipient_nric', '') or '').strip()
        return '', '', ''
    for dt in ('salary_slip', 'epf'):
        p = _cluster_docs(application, member, dt).first()
        if p:
            f = _doc_fields(p)
            return dt, (f.get('name', '') or '').strip(), (f.get('nric', '') or '').strip()
    return '', '', ''


# ── IC-NUMBER chain: verify an earner from the BC's printed parent IC number ──────
# The Birth Certificate carries the PARENTS' IC NUMBERS, and every income proof (STR recipient /
# salary slip / EPF) carries the recipient's NRIC. The NUMBER is the strong cross-document join
# key — it doesn't transliterate the way a romanised name does — so when the BC's parent number
# matches the proof's number, the earner is confirmed as that parent EVEN IF the IC physically
# uploaded in their slot is the wrong card or absent (#9: father's IC in the mother slot, but the
# BC-mother / STR / EPF all carry the mother's 750721-04-5130). The chain only ever turns a would-be
# red into a verified green; it never asserts a mismatch.

def _bc_doc(application):
    return (application.documents.filter(doc_type='birth_certificate', superseded_at__isnull=True)
            .order_by('-uploaded_at').first())


def _bc_anchorable(bc) -> bool:
    """A birth certificate may anchor the IC-number chain UNLESS Layer-1 genuineness has positively
    flagged it ('suspect' / 'not_birth_certificate') — a doc that failed Layer 1 can't vouch for a
    number. A BC with no genuineness signal yet is *indeterminate* and may still anchor: the chain
    only ever DEMOTES a red to a verified-green (never asserts a mismatch), so leaning on the strong
    number corroboration is safe and the reviewer stays the authority."""
    from ..genuineness.bands import canonical_status
    vf = getattr(bc, 'vision_fields', None)
    raw = (vf.get('authenticity') or {}).get('status', '') if isinstance(vf, dict) else ''
    return canonical_status(raw, 'birth_certificate') in ('genuine', '')


def _bc_parent_identity(application, member):
    """The (name, nric) the birth certificate carries for this PARENT — 'mother' → bc_mother_*,
    'father' → bc_father_* — but only when the BC genuinely ties to the student (its child = the
    student) and is anchorable (Layer-1). ('', '') otherwise. This is the EARNER IDENTITY the income
    proof is verified against when the physically-uploaded parent_ic is the wrong card or absent."""
    if member not in ('mother', 'father'):
        return '', ''
    bc = _bc_doc(application)
    if bc is None or not _bc_anchorable(bc):
        return '', ''
    f = _doc_fields(bc)
    bc_child = (f.get('bc_child_name', '') or '').strip()
    student = getattr(getattr(application, 'profile', None), 'name', '') or ''
    if not bc_child or not student or name_match(bc_child, student) == 'mismatch':
        return '', ''
    pre = 'bc_mother' if member == 'mother' else 'bc_father'
    return (f.get(pre + '_name', '') or '').strip(), (f.get(pre + '_nric', '') or '').strip()


def chain_verified_earner(application, member) -> bool:
    """True when the IC-NUMBER chain confirms this earner independent of the physical parent_ic card:
    a Layer-1 birth certificate (child = student) carries this parent's IC NUMBER, and that number
    matches the income proof's recipient NRIC (STR recipient / salary slip / EPF). A one-digit number
    drift (OCR over the JPN guilloche) still chains WHEN the parent NAME corroborates. Mother/father
    only — a normal father chains via the patronymic, which needs no number."""
    bc_name, bc_nric = _bc_parent_identity(application, member)
    if not bc_nric:
        return False
    _, p_name, p_nric = _cluster_proof_identity(application, member)
    if not p_nric:
        return False
    from ..vision import nric_match
    if nric_match(bc_nric, p_nric):
        return True
    # One-digit drift is acceptable ONLY when the parent NAME corroborates the near-miss number.
    return nric_close(bc_nric, p_nric) and _name_bucket(bc_name, p_name) == 'match'


def student_income_ic_check(doc):
    """For an income earner's IC (``parent_ic``): the OCR'd IC No / Name / Address, the
    RELATIONSHIP verdict (``name_status`` — does this earner link to the student's family,
    via patronymic / birth cert / letter), AND — the student-facing point — whether this IC
    MATCHES the cluster's income proof (the STR / salary slip it must belong to). The NRIC is
    the earner's, never matched to the student. Returns ``{nric, name, address, member,
    name_status, readable, proof_kind, proof_name_status, proof_nric_status}`` or None.

    ``name_status`` (relationship): 'match' | 'mismatch' | 'unknown' | 'pending'.
    ``proof_name_status`` / ``proof_nric_status`` (vs the income proof): 'match' | 'mismatch'
    | 'no_ref' (no proof uploaded yet, or the field wasn't read). ``proof_kind``: 'str' |
    'salary_slip' | 'epf' | '' — drives the "Matches the STR document" student label."""
    if getattr(doc, 'doc_type', '') != 'parent_ic':
        return None
    app = doc.application
    member = ((getattr(doc, 'household_member', '') or '').strip()
              or (getattr(app, 'income_earner', '') or '').strip())
    name = (getattr(doc, 'vision_name', '') or '').strip()
    nric = (getattr(doc, 'vision_nric', '') or '').strip()
    readable = bool(getattr(doc, 'vision_run_at', None)) and not getattr(doc, 'vision_error', '') and bool(name)

    name_status = 'pending'
    if not member or not name:
        name_status = 'unknown' if (readable and not member) else 'pending'
    else:
        # IC-aware (#88): a typed profile name without the A/P connector must not lose the
        # patronymic link when the student's own verified IC carries it.
        student_name = student_name_for_link(app)
        bc_child, bc_mother, bc_father, letter_name = _relationship_inputs(app, member, name)
        name_status = member_relationship_status(member, student_name, name,
                                                 bc_child, bc_mother, letter_name, bc_father)

    # Cross-check against the cluster's income proof (STR / salary slip) — the reason the
    # earner IC is uploaded. Green when the IC's name + number match the proof's recipient.
    proof_kind, p_name, p_nric = _cluster_proof_identity(app, member) if member else ('', '', '')
    proof_name_status = _name_bucket(name, p_name)
    proof_nric_status = _nric_bucket(nric, p_nric)

    # IC-NUMBER chain: the earner can also be confirmed by the BC's printed parent IC number
    # matching the income proof's number (#9) — which verifies e.g. the mother even when the card
    # uploaded in her slot is a DIFFERENT family member's. When the chain holds the relationship is
    # confirmed; a card whose own name/number then disagree with the proof is a soft WRONG-CARD note
    # (the earner is verified another way), never a red block (doc_match_verdict skips it).
    chain_verified = bool(member) and chain_verified_earner(app, member)
    wrong_card = False
    if chain_verified:
        wrong_card = 'mismatch' in (name_status, proof_name_status, proof_nric_status)
        name_status = 'match'

    return {
        'nric': getattr(doc, 'vision_nric', '') or '',
        'name': getattr(doc, 'vision_name', '') or '',
        'address': getattr(doc, 'vision_address', '') or '',
        'member': member,
        'name_status': name_status,
        'readable': readable,
        'proof_kind': proof_kind,
        'proof_name_status': proof_name_status,
        'proof_nric_status': proof_nric_status,
        'chain_verified': chain_verified,
        'wrong_card': wrong_card,
    }


def _cluster_docs(application, member, doc_type):
    """The documents of *doc_type* in *member*'s income cluster, latest first.

    Slot model (TD-115): income docs are tagged by household member. The SALARY route has
    always tagged each doc; the STR route historically stored the single earner's docs
    UNTAGGED (blank). This reads **tolerantly** during the migration to per-person tagging:
    on the STR route a blank-member doc still counts as the (single) earner's, so the check
    works whether or not the backfill has run; once tightened it reads the member tag only.
    The salary route reads the member tag (a blank there is ambiguous, never attributed)."""
    # Phase 2 (version history): every branch filters `superseded_at__isnull=True` so a
    # replaced income doc can never re-enter the cluster verdict.
    route = (getattr(application, 'income_route', '') or '').strip()
    if route == 'salary':
        qs = application.documents.filter(
            doc_type=doc_type, household_member=member, superseded_at__isnull=True)
    else:
        # STR route (single earner) or blank wizard: the earner's docs — tagged OR legacy-blank.
        # Code-health S4 #15: when the wizard HAS named the earner, the legacy-blank fallback
        # belongs to that earner only — reading a blank doc as "whichever member is asked
        # about" let one untagged slip satisfy the income-evidence check for BOTH parents,
        # suppressing the other parent's proof-missing query. A blank wizard (legacy app,
        # no earner recorded) keeps the fully tolerant reading.
        earner = (getattr(application, 'income_earner', '') or '').strip()
        if earner and member != earner:
            allowed = [member]
        else:
            allowed = [member, '']
        qs = application.documents.filter(
            doc_type=doc_type, household_member__in=allowed, superseded_at__isnull=True)
    return qs.order_by('-uploaded_at')


def _member_ic_doc(application, member):
    """That earner's IC (parent_ic) — salary route: tagged with the member; STR route:
    the single untagged earner IC. None if not uploaded."""
    if not member:
        return None
    return _cluster_docs(application, member, 'parent_ic').first()


# ── Blank-tag resolution (officer Documents box) ─────────────────────────────
# Income docs SHOULD carry a household_member tag, but some arrive blank — an Action-Centre /
# officer-requested upload lands without one (e.g. #63's father IC came in untagged). Rather than
# strand them in an "unassigned" pile, resolve the person from the NAME printed on the document
# against the family roster. Display-facing (the cockpit box + the correcting tag-guard place them
# under the right person). STR is included so a salary-route STR (the recipient may differ from the
# declared income_earner — #45) files under its actual RECIPIENT, matching the verdict's own
# recipient match (household_str_status) rather than falling back to income_earner.
_RESOLVABLE_INCOME_DOCS = ('parent_ic', 'salary_slip', 'epf', 'str')


def _doc_person_name(doc):
    """The person a (parent_ic / salary_slip / epf / str) document is about: the IC's OCR'd name, the
    payslip/EPF's extracted holder name, or the STR's recipient. '' when nothing read."""
    dt = getattr(doc, 'doc_type', '')
    if dt == 'parent_ic':
        return (getattr(doc, 'vision_name', '') or '').strip()
    if dt == 'str':
        return (_doc_fields(doc).get('recipient_name', '') or '').strip()
    return (_doc_fields(doc).get('name', '') or '').strip()


def _roster_candidates(application):
    """(member, name) pairs from the structured family roster — father, mother, and any named
    other-family members (siblings / guardian) — for resolving a blank-tagged doc to a person."""
    out = []
    fn = (getattr(application, 'father_name', '') or '').strip()
    mn = (getattr(application, 'mother_name', '') or '').strip()
    if fn:
        out.append(('father', fn))
    if mn:
        out.append(('mother', mn))
    for om in (getattr(application, 'other_family_members', None) or []):
        if isinstance(om, dict) and (om.get('name') or '').strip():
            rel = (om.get('relationship') or om.get('role') or '').strip().lower()
            member = rel if rel in ('brother', 'sister', 'guardian') else 'guardian'
            out.append((member, om['name'].strip()))
    return out


def _name_matched_members(application, doc):
    """The DISTINCT roster members whose name tolerant-matches the NAME read off this income doc,
    in roster order. [] when the doc has no readable name / isn't a resolvable income doc / matches
    nobody. Ignores the doc's own tag — this is purely 'who does the NAME on the paper point to'."""
    if getattr(doc, 'doc_type', '') not in _RESOLVABLE_INCOME_DOCS:
        return []
    name = _doc_person_name(doc)
    if not name:
        return []
    from ..vision import relationship_name_match
    out = []
    for member, cand in _roster_candidates(application):
        if relationship_name_match(name, cand) in ('match', 'partial') and member not in out:
            out.append(member)
    return out


def resolved_member_for(application, doc):
    """The household member an income document belongs to — its own tag if set, else resolved by
    matching the NAME on the doc against the family roster (tolerant of Tamil/Indian romanisation).
    '' when it can't be resolved (a blank doc with no readable name / no roster match) — the cockpit
    then shows it in the SALARY 'unassigned' catch-all. Display helper; does not change the tag."""
    tag = (getattr(doc, 'household_member', '') or '').strip()
    if tag:
        return tag
    matched = _name_matched_members(application, doc)
    return matched[0] if matched else ''


def name_contradicts_tag(application, doc):
    """The member this income doc UNAMBIGUOUSLY belongs to when that CONTRADICTS its current tag —
    else ''. Fires only when: the doc is tagged, the name read off it is readable, and it matches
    EXACTLY ONE roster member who is NOT the current tag. Deliberately strict: overriding an existing
    tag (unlike filling a blank) demands zero ambiguity, so a name that matches nobody (e.g. a roster
    with NRICs instead of names) or two members never triggers a correction — the tag stands.

    This is the airtight backstop for the #80/#112 class: a father's payslip that a pre-consent
    STR-route force-tag stamped onto the mother. The upload guard uses it to self-correct at source."""
    tag = (getattr(doc, 'household_member', '') or '').strip()
    if not tag:
        return ''
    matched = _name_matched_members(application, doc)
    if len(matched) == 1 and matched[0] != tag:
        return matched[0]
    return ''


def implied_single_member(application):
    """The household member an UNTAGGED income document can only belong to — the STR route's
    declared ``income_earner``. '' on the salary route (several members may each hold documents,
    so an untagged one is genuinely ambiguous) or when no earner has been declared.

    ⚠ ONE DEFINITION, TWO CALLERS, AND THEY MUST NOT DIVERGE. The readers have always assumed it
    (``_proof_member`` below, and TD-115's "blank-as-earner" leniency). Since BrightPath #20 the
    upload tag guard WRITES with it as well, because a document the readers treat as the earner's
    while the SLOT SWEEP treats it as nobody's is exactly the duplicate that outlives its own
    replacement: application 73's blurry payslip was uploaded untagged, landed in the empty blank
    slot, won it by default (an empty slot has nothing to lose to), and sat beside the good copy
    in the live documents for a fortnight.

    Guessing here cannot bury good evidence: a re-tagged doc goes through STAGE → JUDGE → PROMOTE
    like any other, and an unreadable one is not `usable`, so it can only ever land in Replaced.
    """
    if (getattr(application, 'income_route', '') or '').strip() != 'str':
        return ''
    return (getattr(application, 'income_earner', '') or '').strip()


def _proof_member(doc):
    """The earner a salary slip / EPF belongs to: its own household_member tag (salary
    route), or the application's single income_earner (STR route). '' if no income
    context (e.g. the wizard hasn't been walked) — the caller then skips the check."""
    member = (getattr(doc, 'household_member', '') or '').strip()
    if member:
        return member
    return implied_single_member(doc.application)


def student_income_proof_check(doc):
    """For a salary slip / EPF: the earner facts read off the document (name · NRIC ·
    amount · period) cross-checked against THAT earner's IC — NOT the student. So a
    father's payslip is verified against the father's IC, and the coach never tells the
    student to edit their own name. Works for both routes (salary = the member-tagged
    IC; STR = the single untagged earner IC). Returns
    ``{name, nric, amount, period, member, name_status, nric_status, ic_present}`` or
    None when it is not a salary_slip/epf with an income context.

    name_status / nric_status: 'match' | 'mismatch' | 'no_ref' (that earner's IC not
    uploaded yet, or the field wasn't read) — a soft, never-blocking signal."""
    dt = getattr(doc, 'doc_type', '')
    if dt not in ('salary_slip', 'epf'):
        return None
    member = _proof_member(doc)
    if not member:
        return None

    f = _doc_fields(doc)
    name = (f.get('name', '') or '').strip()
    nric = (f.get('nric', '') or '').strip()
    # Data points shown on the card. Salary → gross + period. EPF → the MONTHLY
    # contribution (the income figure) + the total accumulated + the year (so the big
    # lifetime balance is never mistaken for monthly income).
    if dt == 'salary_slip':
        raw_points = [('amount', f.get('gross_income') or f.get('net_income')),
                      ('period', f.get('period'))]
    else:                                          # epf
        # The contribution income figure is the AVERAGE over the months shown (steadier than
        # one row; RM0.00 when the statement shows no contributions — a 'no active salary'
        # signal). The lifetime balance + statement date + member address are context.
        avg = (f.get('avg_monthly_contribution') or f.get('monthly_contribution') or '').strip()
        raw_points = [('avgContribution', avg),
                      ('monthsAveraged', f.get('months_counted')),
                      ('totalAccumulated', f.get('latest_balance')),
                      ('statementDate', f.get('statement_date') or f.get('year') or f.get('last_contribution')),
                      ('address', f.get('address'))]
    points = [{'key': k, 'value': (v or '').strip()} for k, v in raw_points if (v or '').strip()]

    ic = _member_ic_doc(doc.application, member)
    ic_name = (getattr(ic, 'vision_name', '') or '').strip() if ic else ''
    ic_nric = (getattr(ic, 'vision_nric', '') or '').strip() if ic else ''

    name_status = _name_bucket(name, ic_name)
    nric_status = _nric_bucket(nric, ic_nric)
    # IC-NUMBER chain (#9): the earner is confirmed by the BC↔proof IC-number match, so this
    # slip/EPF belongs to the verified earner — it is NOT red against a wrong card in the slot
    # (father's IC in the mother slot, but the EPF is the mother's). The number already settled
    # identity, so trust it over an exact name/number re-compare (which a one-digit OCR drift fails).
    if chain_verified_earner(doc.application, member):
        name_status = nric_status = 'match'

    return {
        'name': name, 'nric': nric, 'points': points,
        'member': member, 'name_status': name_status, 'nric_status': nric_status,
        'ic_present': ic is not None,
    }
