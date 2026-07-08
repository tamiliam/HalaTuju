"""Income verification — Check-1 item 3: earner identity + relationship.

Pure, deterministic helpers (no DB writes, no live calls) that the income verdict
(verdict_engine._verdict_income, Sprint I2) and the student wizard checklist
(Sprint I3) both consume, so they can never disagree.

The model: a guided wizard collects three answers on the application —
``income_route`` (str | salary), ``income_earner`` (father | mother | guardian),
``earner_work_status`` (payslip | informal | not_working). From those,
``income_requirements`` returns the documents the family must upload (compulsory)
plus credibility boosters (optional). Proving the earner is the student's family:

  - **father**  → the father's name is carried in the student's OWN IC patronymic
                  (``A/L`` / ``A/P`` / ``S/O`` / ``D/O`` / ``bin`` / ``binti``);
                  match it to the earner IC. No extra document.
  - **mother**  → a **Birth Certificate** (the patronymic names only the father):
                  its child-name must be the student and its mother-name the earner IC.
  - **guardian**→ a guardianship order/letter (presence; name match is a soft bonus).

Never blocks a genuinely poor family: a missing payslip/EPF for a non-working or
informal earner becomes an officer/interview judgement upstream, not a hard gate.
"""
from __future__ import annotations

import datetime
import re

# Every name comparison in this module is the SAME real person across TWO documents
# (relationships, earner-IC ↔ income-proof, STR-recipient ↔ IC, BC names) — never the student's
# own identity — so they all use the transliteration-tolerant matcher (#2, Sarawanan A/L case).
from .vision import relationship_name_match as name_match
from .vision import nric_close
from .vision import canonical_name_tokens   # token folding — reused for cross-bill holder reconciliation


# ── Father's name from the student's IC patronymic ───────────────────────────
# A Malaysian full name carries the FATHER's given name after the relationship
# connector: "DIVASHINI A/P MURUGAN" → father "MURUGAN"; "AHMAD BIN ALI" → "ALI".
_PATRONYMIC_RE = re.compile(
    r'\b(?:a\s*/\s*[lp]|s\s*/\s*o|d\s*/\s*o|bin|binti|anak\s+(?:lelaki|perempuan))\b',
    re.IGNORECASE,
)


def father_name_from_ic(student_name: str) -> str:
    """The father's name carried in the student's name (the part AFTER the
    patronymic connector). '' when there is no connector — e.g. a single given
    name or a Chinese-style name — so the caller knows it can't derive the father
    this way and must fall back to officer review rather than guess."""
    s = (student_name or '').strip()
    m = _PATRONYMIC_RE.search(s)
    if not m:
        return ''
    return s[m.end():].strip(' .,')


# ── Relationship checks (pure; statuses mirror the slip/offer checks) ─────────
# 'match' | 'mismatch' | 'unknown' (can't derive) | 'pending' (not yet read).

def father_relationship(student_name: str, earner_ic_name: str) -> str:
    """Does the earner IC belong to the student's father? The father's given name
    from the student IC must appear in the earner's full IC name. A subset match
    (the given name inside the earner's fuller name) COUNTS — only disjoint tokens
    are a real mismatch."""
    father = father_name_from_ic(student_name)
    if not father:
        return 'unknown'                       # no patronymic → officer reviews
    if not (earner_ic_name or '').strip():
        return 'pending'                       # earner IC not read yet
    return 'mismatch' if name_match(father, earner_ic_name) == 'mismatch' else 'match'


def _bc_link(bc_child_name: str, bc_parent_name: str,
             student_name: str, earner_ic_name: str) -> str:
    """Birth-Certificate linkage: the BC's child must be the student AND its named
    parent must be the earner IC. Either side disjoint → mismatch; both agree →
    match; not enough read yet → pending. Shared by mother_relationship (BC mother)
    and father_via_bc (BC father)."""
    if not (bc_child_name or '').strip() and not (bc_parent_name or '').strip():
        return 'pending'                       # BC not uploaded / not read
    child_ok = (name_match(bc_child_name, student_name) != 'mismatch'
                if bc_child_name and student_name else None)
    parent_ok = (name_match(bc_parent_name, earner_ic_name) != 'mismatch'
                 if bc_parent_name and earner_ic_name else None)
    if child_ok is False or parent_ok is False:
        return 'mismatch'
    if child_ok and parent_ok:
        return 'match'
    return 'pending'


def mother_relationship(bc_child_name: str, bc_mother_name: str,
                        student_name: str, earner_ic_name: str) -> str:
    """The Birth Certificate ties the earner (mother) to the student: its child
    must be the student AND its mother must be the earner IC. Either side disjoint
    → mismatch; both agree → match; not enough read yet → pending."""
    return _bc_link(bc_child_name, bc_mother_name, student_name, earner_ic_name)


def father_via_bc(bc_child_name: str, bc_father_name: str,
                  student_name: str, earner_ic_name: str) -> str:
    """Mononym fallback for the FATHER link: when the student's name carries no patronymic,
    father_relationship can't read the father off it (#55, DIVIYA) — so the Birth Certificate
    ties the earner (father) to the student instead: its child must be the student AND its
    FATHER must be the earner's IC. Mirrors mother_relationship (which uses the BC mother).
    Either side disjoint → mismatch; both agree → match; not enough read → pending."""
    return _bc_link(bc_child_name, bc_father_name, student_name, earner_ic_name)


def father_link(student_name: str, earner_ic_name: str,
                bc_child_name: str = '', bc_father_name: str = '') -> str:
    """The father→student link: the shared patronymic, OR — when the student is a mononym so
    the patronymic can't apply — the Birth Certificate's child+father (#55). The patronymic
    result wins; only its 'unknown' (no patronymic) defers to the BC, and only if one was
    uploaded. So a normal applicant is unaffected; a mononym applicant who adds their BC gets
    a deterministic father verdict instead of a permanent 'officer reviews'."""
    r = father_relationship(student_name, earner_ic_name)
    if r == 'unknown' and (bc_child_name or bc_father_name):
        return father_via_bc(bc_child_name, bc_father_name, student_name, earner_ic_name)
    return r


def guardian_relationship(letter_name: str, earner_ic_name: str) -> str:
    """Soft name check between a guardianship letter and the earner IC. The hard
    requirement is the letter's PRESENCE (handled by income_requirements); a name
    that disagrees is a flag, agreement a bonus, missing text → pending."""
    if not (letter_name or '').strip():
        return 'pending'
    if not (earner_ic_name or '').strip():
        return 'pending'
    return 'mismatch' if name_match(letter_name, earner_ic_name) == 'mismatch' else 'match'


_RELATIONSHIP_DOC = {'mother': 'birth_certificate', 'guardian': 'guardianship_letter'}


def relationship_doc_for(earner: str) -> str:
    """The extra document a given earner needs to prove the relationship
    ('birth_certificate' / 'guardianship_letter'), or '' for a father/sibling (derived
    from the shared student-IC patronymic — siblings carry the same father's name)."""
    return _RELATIONSHIP_DOC.get(earner or '', '')


# ── Salary route: multiple working household members ──────────────────────────
# Each ticked member gets their own IC + salary slip + EPF (tagged on the document
# via household_member). The relationship to the student:
#   - father / brother / sister → the SAME father's name from the student's IC
#     patronymic (siblings carry it too) → father_relationship, no extra doc.
#   - mother  → birth certificate.
#   - guardian→ guardianship letter.
_MEMBER_ORDER = ('father', 'mother', 'guardian', 'brother', 'sister')
# father/brother/sister all verify the same way (patronymic); only mother/guardian need a doc.
_PATRONYMIC_MEMBERS = {'father', 'brother', 'sister'}


def working_members(application) -> list:
    """The ticked salary-route members, de-duped and in display order. Tolerant of a
    blank/None/garbage JSON value (returns [])."""
    raw = getattr(application, 'income_working_members', None) or []
    if not isinstance(raw, (list, tuple)):
        return []
    chosen = {m for m in raw if m in _MEMBER_ORDER}
    return [m for m in _MEMBER_ORDER if m in chosen]


def effective_working_members(application) -> list:
    """The salary-route working members, with a fallback for the prefill-not-saved gap.

    ``working_members`` reads ONLY the persisted ``income_working_members`` list. The income
    wizard pre-ticks earners from the family roster and tags uploaded income docs to them, but
    only PERSISTS the list when the student toggles a checkbox — so a student who accepts the
    correct prefill and just uploads can leave ``income_working_members`` empty while their docs
    are already tagged (e.g. mother's IC + salary slip + EPF). The salary route requires at least
    one earner at submit, so an EMPTY list here is always that unsaved-prefill case, never a
    deliberate choice — making it safe to reconstruct from the authoritative signals, in order:
      1. the income docs the student actually uploaded + tagged (``household_member``), then
      2. the family roster's earning members.
    A non-empty explicit list always wins (a real selection is never overridden); off the salary
    route, or with no signal to fall back to, returns []. No side effects; tolerant of a test
    double without ``.documents`` / roster columns."""
    explicit = working_members(application)
    if explicit:
        return explicit
    if (getattr(application, 'income_route', '') or '').strip() != 'salary':
        return []
    # (1) Members the uploaded income docs are tagged to — what the student actually did.
    found: set = set()
    docs = getattr(application, 'documents', None)
    if docs is not None:
        try:
            tagged = (docs.filter(doc_type__in=('parent_ic', 'salary_slip', 'epf'),
                                  superseded_at__isnull=True)
                      .exclude(household_member='')
                      .values_list('household_member', flat=True))
            found.update(m for m in tagged if m in _MEMBER_ORDER)
        except (AttributeError, TypeError):
            pass
    # (2) Else the declared earners from the family roster.
    if not found:
        try:
            from .family import earning_members
            found.update(m for m in earning_members(application) if m in _MEMBER_ORDER)
        except (AttributeError, TypeError):
            pass
    return [m for m in _MEMBER_ORDER if m in found]


def member_relationship_status(member: str, student_name: str, member_ic_name: str,
                               bc_child_name: str = '', bc_mother_name: str = '',
                               letter_name: str = '', bc_father_name: str = '') -> str:
    """The relationship verdict for one working member — routes to the right check.
    father → patronymic, with a Birth-Certificate fallback for a mononym student (#55);
    brother/sister → father_relationship (shared patronymic only); mother → birth cert;
    guardian → guardianship letter. 'match' | 'mismatch' | 'unknown' | 'pending'."""
    if member == 'father':
        return father_link(student_name, member_ic_name, bc_child_name, bc_father_name)
    if member in _PATRONYMIC_MEMBERS:            # brother / sister — patronymic only
        return father_relationship(student_name, member_ic_name)
    if member == 'mother':
        return mother_relationship(bc_child_name, bc_mother_name, student_name, member_ic_name)
    if member == 'guardian':
        return guardian_relationship(letter_name, member_ic_name)
    return 'unknown'


def _relationship_inputs(application, member, member_ic_name):
    """Pull the relationship-proof inputs for one member from the application's documents
    (birth cert for a mother — also the FATHER fields for the #55 mononym father fallback;
    guardianship letter for a guardian)."""
    bc_child = bc_mother = bc_father = letter_name = ''
    if member in ('mother', 'father', 'brother', 'sister'):
        bc = (application.documents.filter(doc_type='birth_certificate', superseded_at__isnull=True)
              .order_by('-uploaded_at').first())
        vf = (getattr(bc, 'vision_fields', None) if bc else None) or {}
        f = vf.get('fields', {}) if isinstance(vf, dict) else {}
        if isinstance(f, dict):
            bc_child = f.get('bc_child_name', '')
            bc_mother = f.get('bc_mother_name', '')
            bc_father = f.get('bc_father_name', '')
    elif member == 'guardian':
        g = (application.documents.filter(doc_type='guardianship_letter', superseded_at__isnull=True)
             .order_by('-uploaded_at').first())
        letter_name = (getattr(g, 'vision_name', '') or '') if g else ''
    return bc_child, bc_mother, bc_father, letter_name


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
    from .genuineness.bands import canonical_status
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
    from .vision import nric_match
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
        student_name = getattr(getattr(app, 'profile', None), 'name', '') or ''
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
    from .vision import relationship_name_match
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


def _proof_member(doc):
    """The earner a salary slip / EPF belongs to: its own household_member tag (salary
    route), or the application's single income_earner (STR route). '' if no income
    context (e.g. the wizard hasn't been walked) — the caller then skips the check."""
    member = (getattr(doc, 'household_member', '') or '').strip()
    if member:
        return member
    app = doc.application
    if (getattr(app, 'income_route', '') or '').strip() == 'str':
        return (getattr(app, 'income_earner', '') or '').strip()
    return ''


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


_STR_REJECTED_WORDS = ('tolak', 'tidak layak', 'gagal', 'reject')
# Positive STR approval signals. 'lulus' also matches 'diLULUSkan'. NOTE: SARA's 'Layak' is
# deliberately NOT here — SARA (Sumbangan Asas Rahmah) is a different programme from STR, and the
# STR status on the MySTR portal is 'Lulus', never 'Layak'. (#5b SARA≠STR, 2026-06-11)
_STR_APPROVED_WORDS = ('lulus', 'approve')
_STR_YEAR_RE = re.compile(r'(20\d{2})')
# The three genuine MySTR proof formats (docs/scholarship/str-proof-spec.md). Anything else — a
# SALINAN / application copy, a SARA letter, a salary slip, a random doc — is classified 'unknown'
# by the extractor and is NOT an STR proof at all.
_STR_RECOGNISED_SOURCES = ('letter', 'semakan_status', 'dashboard')


# The RED band of the STR-currency ladder — states where the doc on file positively fails
# to prove a current STR (wrong kind of document, rejected, unreadable status, or a previous
# year's). Code-health S4 #13: this tuple is THE shared source of truth — the 8b4686b1
# state-split left three consumers (the cluster coach, the re-upload reconcile, the
# submission blocker) each carrying its own stale subset, so the two WORST states
# (wrong_type/unreadable) were silently treated as fine by some of them.
# NB 'unreadable' is deliberately NOT here: it is AMBER per the spec (the status token
# didn't read — misread ≠ disproven), and a never-scanned legacy doc also reads
# 'unreadable', so blocking on it would gate consent on our own extraction backlog.
STR_RED_STATES = ('wrong_type', 'rejected', 'stale')
# The student coach nudges on the fixable non-green states too (an unreadable status →
# re-upload cleanly; a dateless 'unconfirmed' approval → a dated proof confirms the cycle).
STR_COACH_STATES = STR_RED_STATES + ('unreadable', 'unconfirmed')


def _str_currency(status_raw, year_str, cohort_year, source_type=''):
    """Structured STR currency state for the verdict (docs/scholarship/str-proof-spec.md). The
    FORMAT GATE runs first: a document that is not one of the three genuine MySTR proofs is
    ``wrong_type`` — never softened to ``unconfirmed``.

      'rejected'    — a clear negative status (Ditolak / Tidak Layak / Gagal) → RED.
      'wrong_type'  — NOT a recognised STR proof (``source_type='unknown'``: a SALINAN / SARA
                      letter / salary slip / other). NOT an STR at all → RED; the income verdict
                      falls through to the salary route.
      'unreadable'  — a recognised format but the approval status did NOT read AND no current-cycle
                      date is shown, so approval can't be confirmed → AMBER (Unsure). NB not a claim
                      the page is cropped — the status token may simply have been misread.
      'stale'       — approved, but a readable year OLDER than the cohort year (STR is annual) → AMBER.
      'unconfirmed' — a recognised format, approved (Lulus), but NO date to pin the cycle
                      (dashboard / collapsed Semakan) → BLUE (probably current).
      'current'     — a recognised format, approved, DATED current (letter date / Semakan payment
                      date ≥ cohort year) → GREEN.

    The STR model is exactly Name · IC · Status · Year (owner 2026-07-07). Only two questions
    decide currency: **Status** — is it approved? (a readable "Lulus"/"diluluskan"; on a dashboard/
    Semakan the "Lulus" IS shown); and **Year** — is it for the current cycle? proven by a DATE (the
    letter date, or a Maklumat-Pembayaran credit date), NEVER by an amount. The approved/paid AMOUNT
    is ignored entirely — it varies without meaning and a prior-year figure is irrelevant (this
    RETIRES the old paid-amount rescue: a misread approval no longer greens off a number; a readable
    "Lulus" is required, else the doc reads 'unreadable' and a re-read / interview settles it).

    A dateless approved STR is not GREEN: a year-old dashboard/Semakan screenshot also shows
    "Lulus", so without a date we can't confirm the cycle (→ BLUE, confirm at interview / open
    Maklumat Pembayaran). A blank/legacy ``source_type`` (extracted before classification) is
    TOLERATED — it falls through to the status assessment rather than being forced to wrong_type;
    a re-run repopulates it."""
    s = (status_raw or '').lower()
    st = (source_type or '').strip().lower()
    if any(w in s for w in _STR_REJECTED_WORDS):
        return 'rejected'
    if st == 'unknown':
        return 'wrong_type'          # not a genuine STR proof at all (SALINAN / SARA / payslip / …)
    if not any(w in s for w in _STR_APPROVED_WORDS):
        return 'unreadable'          # no readable "Lulus"/"diluluskan" → STR approval can't be confirmed
    # SURFACE CEILING (owner 2026-07-07): a DASHBOARD confirms APPROVAL but is a self-service snapshot
    # that cannot certify the cycle to certainty — its max band is Probable. So an approved dashboard
    # caps at 'unconfirmed' (BLUE) regardless of any date read. Only the LETTER (dated) and the
    # SEMAKAN STATUS (dated Maklumat-Pembayaran) can reach 'current' (GREEN / Certain).
    if st == 'dashboard':
        return 'unconfirmed'
    # Letter / Semakan / blank-legacy. The Year question: a DATE (letter date / Maklumat-Pembayaran
    # credit date) pins the cycle. No date → unconfirmed (BLUE); prior-year → stale (AMBER);
    # current-or-later → current (GREEN).
    m = _STR_YEAR_RE.search(year_str or '')
    if not m:
        return 'unconfirmed'
    if cohort_year and int(m.group(1)) < int(cohort_year):
        return 'stale'
    return 'current'


def _str_recipient_household_match(application, name, nric, tagged_member=''):
    """Exhaustively match an STR recipient's NAME and NRIC — INDEPENDENTLY — against every
    parent/guardian (and any other roster member) whose IC is on file. Returns
    ``(name_status, nric_status, member)``.

    A genuine STR is a HOUSEHOLD benefit and the letter can carry either spouse's name/IC
    (owner 2026-07-07: "match the STR against ANY parent/guardian; only when ALL attempts fail is
    it breached"), so we try everyone — not just the declared earner — and each field settles on
    its own: a recipient whose NAME hits the father and whose NRIC hits the mother is a clean
    household match on BOTH (e.g. #45). 'match' iff the field hits any member's IC; 'mismatch' iff
    at least one IC was compared and none hit; 'no_ref' when there was nothing to compare against.
    ``member`` resolves to the name-matched member (preferred), else the nric-matched member, else
    the tagged/earner fallback."""
    members = list(dict.fromkeys([m for m in ([tagged_member] + list(_MEMBER_ORDER)) if m]))
    name_hit = nric_hit = None
    name_seen = nric_seen = False
    for m in members:
        ic = _member_ic_doc(application, m)
        if ic is None:
            continue
        ic_name = (getattr(ic, 'vision_name', '') or '').strip()
        ic_nric = (getattr(ic, 'vision_nric', '') or '').strip()
        if ic_name:
            name_seen = True
            if name_hit is None and _name_bucket(name, ic_name) == 'match':
                name_hit = m
        if ic_nric:
            nric_seen = True
            if nric_hit is None and _nric_bucket(nric, ic_nric) == 'match':
                nric_hit = m
    name_status = 'match' if name_hit else ('mismatch' if (name and name_seen) else 'no_ref')
    nric_status = 'match' if nric_hit else ('mismatch' if (nric and nric_seen) else 'no_ref')
    return name_status, nric_status, (name_hit or nric_hit or tagged_member or '')


# STR-proof QUALITY ranking for the upload keep-better guard (owner: #83 wrong-type, #30 dashboard
# < Semakan). A re-upload must never displace a live proof of STRICTLY HIGHER quality with a thinner
# one. Quality is a tuple (currency_rank, source_rank), CURRENCY FIRST — so #112 is correctly NOT a
# regression: its live Lulus DASHBOARD (unconfirmed) outranks the older 'Dalam Proses Rayuan'
# SEMAKAN (unreadable approval) on currency, which dominates the source tiebreak. The source tier
# only decides ties (both Lulus + dateless): a Semakan (shows the payment-dates page → can reach
# 'current') carries MORE than a Dashboard (home totals, capped at 'unconfirmed'), which carries
# more than an unrecognised page.
_STR_CURRENCY_RANK = {'current': 4, 'unconfirmed': 3, 'stale': 2, 'unreadable': 1, 'wrong_type': 0}
_STR_SOURCE_RANK = {'letter': 3, 'semakan_status': 2, 'dashboard': 1}


def str_proof_quality(doc):
    """A comparable (currency_rank, source_rank) quality tuple for an STR proof — HIGHER is better.
    Returns ``None`` for a non-STR doc OR a 'rejected' read: a genuine Ditolak is NEWS (a real
    negative status), so it must ALWAYS replace, never be kept out by the guard."""
    sc = student_str_check(doc)
    if not sc:
        return None
    cs = sc.get('current_status', '')
    if cs == 'rejected':
        return None
    vf = getattr(doc, 'vision_fields', None)
    src = (((vf.get('fields') or {}).get('source_type') or '') if isinstance(vf, dict) else '')
    return (_STR_CURRENCY_RANK.get(cs, 0), _STR_SOURCE_RANK.get(src.strip().lower(), 0))


def student_str_check(doc):
    """For an STR document: the recipient facts (name · NRIC · status · year) matched against the
    HOUSEHOLD — every parent/guardian's IC, on name OR nric independently — plus whether it's
    CURRENT (this cohort year + approved). Returns ``{name, nric, status, year, member,
    name_status, nric_status, current_status, ic_present}`` or None for a non-STR doc.

    name_status / nric_status: 'match' | 'mismatch' | 'no_ref' (household-level — see
    ``_str_recipient_household_match``). current_status: the STR-currency ladder (``_str_currency``)."""
    if getattr(doc, 'doc_type', '') != 'str':
        return None
    app = doc.application
    # Where the recipient resolves when neither name nor nric hits an IC: the declared earner on
    # the STR route, else the doc's own member tag.
    tagged = ((getattr(app, 'income_earner', '') or '').strip()
              or (getattr(doc, 'household_member', '') or '').strip())

    vf = doc.vision_fields if isinstance(getattr(doc, 'vision_fields', None), dict) else {}
    f = vf.get('fields', {}) if isinstance(vf.get('fields', {}), dict) else {}
    name = (f.get('recipient_name', '') or '').strip()
    nric = (f.get('recipient_nric', '') or '').strip()
    status = (f.get('status', '') or '').strip()
    year = (f.get('year', '') or '').strip()

    name_status, nric_status, member = _str_recipient_household_match(app, name, nric, tagged)
    # IC-NUMBER chain (#9): a BC↔STR IC-number match confirms the recipient is the verified earner,
    # regardless of a wrong/absent card in the slot. (Currency below is a separate test — a
    # confirmed recipient can still hold a stale/rejected STR.)
    if member and chain_verified_earner(app, member):
        name_status = nric_status = 'match'

    cohort_year = getattr(getattr(app, 'cohort', None), 'year', None)
    ic = _member_ic_doc(app, member) if member else None
    return {
        'name': name, 'nric': nric, 'status': status, 'year': year,
        'member': member, 'name_status': name_status, 'nric_status': nric_status,
        'current_status': _str_currency(status, year, cohort_year, f.get('source_type', '')),
        'ic_present': ic is not None,
    }


# ── Per-capita income from the documents (Check-1 I4, salary route) ──────────
_AMOUNT_RE = re.compile(r'(\d[\d,]*\.?\d*)')
# EPF total monthly contribution ≈ 11% (employee) + 13% (employer) = 24% of salary, so a
# salary estimate when there's no payslip: monthly_salary ≈ contribution / 0.24.
_EPF_CONTRIB_RATE = 0.24

# #9 payslip-vs-EPF tolerance. The payslip gross and the EPF-implied salary rarely match
# to the ringgit — overtime, late employer payments, and variable operator-grade pay all
# move them apart — so the flag stays QUIET unless they diverge a lot. Flag only when the
# ratio (slip ÷ epf_implied) falls outside this band (the bounds are reciprocals, so it is
# symmetric: more than ~1.67× apart in either direction).
_SLIP_EPF_LO = 0.6
_SLIP_EPF_HI = 1.67

# A backstop on a garbled salary read: net (take-home) can never exceed gross (net =
# gross − deductions). A small tolerance absorbs rounding/OCR noise; beyond it the read
# is inconsistent and must not be trusted for the income figure.
_NET_OVER_GROSS_TOL = 1.02


def _salary_monthly_amount(f):
    """A salary slip's representative MONTHLY pay — gross preferred, else net — but ONLY when the
    read is internally consistent. A garbled OCR of a hand-written voucher can mis-read the ruled
    ringgit|sen columns or grab the wrong cells; the tell is **net > gross**, impossible on a real
    payslip. When that happens the amount is unreliable → return None, so income falls to 'verify at
    interview' rather than asserting a false (often 100x-inflated) figure. (#66.)

    Prefers the ANNUALISED figure when the slip carries a YEAR-TO-DATE gross (``gross_income_ytd``):
    a single payslip month under-states a job with variable overtime (#13: basic RM3,800/mo but YTD
    ÷ 12 ≈ RM7,064/mo). YTD ÷ 12 is the representative monthly (the YTD period is ambiguous — a
    flagged interview item — so the headroom band routes a near-line annualised figure to 'unsure').
    Never lets a mis-read YTD DEFLATE the figure below the single month — which also means a YTD
    with NO readable monthly figure is unusable (the deflate guard can't run)."""
    gross = _parse_rm(f.get('gross_income'))
    net = _parse_rm(f.get('net_income'))
    if gross and net and net > gross * _NET_OVER_GROSS_TOL:
        return None
    month = gross or net
    ytd = _parse_rm(f.get('gross_income_ytd'))
    # YTD is trustworthy only ALONGSIDE a readable monthly figure (the >= deflate guard).
    # Alone, its period is unknowable: an early-year slip's YTD ÷ 12 understates income up
    # to 12× (January: RM3,800 actual → RM317 "monthly" → a false B40 green). Unreadable
    # monthly cells → None → 'verify at interview', same as the garbled-read rule above.
    if ytd and month is not None:
        annualised = round(ytd / 12.0, 2)
        if annualised >= month:
            return annualised
    return month


def _parse_rm(s):
    """Parse an RM figure ('RM 9,900.04' / '2400.00' / 'RM2,400') → float, or None."""
    if not s:
        return None
    m = _AMOUNT_RE.search(str(s).replace(' ', ''))
    if not m:
        return None
    try:
        return float(m.group(1).replace(',', ''))
    except ValueError:
        return None


def _arrears_amount(raw):
    """Parse a utility bill's arrears (unpaid balance), treating a CREDIT as zero owed.
    A negative balance ('-1.29', 'RM -1.29') or a 'CR'/'kredit' marker means the household
    is AHEAD on the account, not behind — so it must not read as arrears (``_parse_rm``
    strips the minus sign and would otherwise record a credit as a positive amount owed).
    Returns the arrears (float), 0.0 for a credit, or None when nothing parseable."""
    s = str(raw or '').strip()
    if not s:
        return None
    if re.search(r'-\s*\d', s) or re.search(r'\b(cr|kredit|credit)\b', s, re.IGNORECASE):
        return 0.0
    return _parse_rm(s)


def _doc_fields(doc):
    vf = doc.vision_fields if isinstance(getattr(doc, 'vision_fields', None), dict) else {}
    f = vf.get('fields', {})
    return f if isinstance(f, dict) else {}


def _epf_monthly_salary(f):
    """Estimate MONTHLY salary from an EPF statement (TD-123 contract). Returns a float
    (0.0 = unemployed), or None when nothing usable.

    - **Unemployed** iff ``No. Majikan == 000000000`` (the only employment check) → 0.0.
    - Otherwise reverse the statutory rates (hardcode employee **11%**, employer **13%**) from
      the contribution TOTALS over the statement + the month count ``n``:
      ``monthly_salary = max(Σ Caruman Majikan /(n·0.13),  Σ Caruman Ahli /(n·0.11))``.
      ``max()`` self-corrects across salary tiers without detecting them: above RM5,000 the
      employer share drops to 12% so the employer-via-13% term under-states, while the
      employee-via-11% term stays exact — ``max()`` selects it.
    - **Legacy fallback** (records extracted before the split totals existed): the old combined
      ``avg_monthly_contribution`` / ``monthly_contribution`` ÷ 0.24."""
    if re.sub(r'\D', '', str(f.get('employer_number') or '')) == '000000000':
        return 0.0
    try:
        n = int(re.sub(r'\D', '', str(f.get('months_counted') or '')) or 0) or 1
    except ValueError:
        n = 1
    cands = []
    er = _parse_rm(f.get('employer_contribution_total'))
    ee = _parse_rm(f.get('employee_contribution_total'))
    if er:
        cands.append(er / (n * 0.13))
    if ee:
        cands.append(ee / (n * 0.11))
    if cands:
        return round(max(cands), 2)
    contrib = _parse_rm(f.get('avg_monthly_contribution')) or _parse_rm(f.get('monthly_contribution'))
    return round(contrib / _EPF_CONTRIB_RATE, 2) if contrib else None


def has_valid_str(application):
    """True when the household has a VALID STR DOCUMENT on file — approved and at least
    'unconfirmed' currency (a genuine, un-rejected STR), on either income route. A valid STR
    is the household's own means-test, so it lets a working member's DECLARED informal income
    be ACCEPTED without a payslip (the STR already establishes B40 need — P5b). Reads the STR
    *document* via ``student_str_check``, never the ``receives_str`` self-tick."""
    docs = getattr(application, 'documents', None)
    if docs is None:
        return False
    str_doc = docs.filter(doc_type='str', superseded_at__isnull=True).order_by('-uploaded_at').first()
    if str_doc is None:
        return False
    sc = student_str_check(str_doc)
    return bool(sc and sc['current_status'] in ('current', 'unconfirmed'))


def household_str_status(application):
    """Owner 2026-07-07 — the single, ROUTE-AGNOSTIC "does this household hold a dispositive STR?".
    A genuine, approved, non-breached STR is the government's own means-test, so it settles B40 —
    on EITHER income route, before the route is even considered (STR PRECEDENCE; the CALLER hoists
    it above the route split). Returns ``(grade, member)`` where grade ∈ {'current','unconfirmed'}
    and member is the parent/guardian the recipient resolves to — or ``(None, None)`` when the STR
    is missing, BREACHED (rejected / wrong_type / stale / unreadable, or judged non-genuine), or its
    recipient matches NO household member (a stranger's STR proves nothing here).

    Supersedes ``salary_route_str``: the recipient match is now exhaustive across EVERY parent/
    guardian (name OR nric, independently — done inside ``student_str_check``), so "breached" is a
    LAST resort reached only when all matching attempts fail — not a first read off the declared
    earner. The CALLER still confirms the matched member's relationship to the student before it
    greens (so a matched-but-unrelated recipient can't settle B40)."""
    docs = getattr(application, 'documents', None)
    if docs is None:
        return None, None
    str_doc = docs.filter(doc_type='str', superseded_at__isnull=True).order_by('-uploaded_at').first()
    if str_doc is None:
        return None, None
    # Genuineness guard: a positively non-genuine STR is breached (mirrors str_not_breached).
    vf = getattr(str_doc, 'vision_fields', None) or {}
    auth = (vf.get('authenticity') or {}).get('status', '') if isinstance(vf, dict) else ''
    if auth and auth not in ('genuine', 'likely_genuine'):
        return None, None
    sc = student_str_check(str_doc)
    if not sc or sc['current_status'] not in ('current', 'unconfirmed'):
        return None, None
    if sc['name_status'] == 'match' or sc['nric_status'] == 'match':
        return sc['current_status'], sc['member']
    return None, None


def str_not_breached(application):
    """True when a genuine, NON-BREACHED STR is on file — approved-ish (any currency state EXCEPT
    wrong_type / rejected / unread) and not judged non-genuine. Mirrors the officer cockpit's
    ``strNotBreached`` (officerCockpit.ts): a non-breached STR makes the salary-route documents
    SUPPORTIVE, not compulsory, on EITHER route (owner 2026-07-05: "STR not breached → no full salary
    docs needed"). BROADER than ``has_valid_str`` (currency-only current/unconfirmed): a stale-but-
    genuine STR is also 'not breached'. Keeps the consent gate + the student's wizard checklist in step
    with what the student is SHOWN — otherwise the docs box says "not required" while the gate blocks."""
    docs = getattr(application, 'documents', None)
    if docs is None:
        return False
    str_doc = docs.filter(doc_type='str', superseded_at__isnull=True).order_by('-uploaded_at').first()
    if str_doc is None:
        return False
    sc = student_str_check(str_doc)
    cs = (sc or {}).get('current_status', '')
    if not cs or cs in ('wrong_type', 'rejected'):     # no read at all, or a failed STR → breached
        return False
    vf = getattr(str_doc, 'vision_fields', None) or {}
    auth = (vf.get('authenticity') or {}).get('status', '') if isinstance(vf, dict) else ''
    return not (auth and auth not in ('genuine', 'likely_genuine'))   # a positive non-genuine call → breached


def str_confirmed_current(application):
    """True when the household's latest live STR reads as CURRENT — approved AND showing a payment
    this cycle. This is the exact criterion the Action-Centre ``str_not_current`` request asks the
    student to satisfy ("confirm it's approved AND being paid"). An 'unconfirmed' (Lulus but no
    payment date), 'unreadable', 'stale' or rejected STR is NOT current — so re-uploading one must not
    silence that ask (the SUBMISSION gate still accepts it as Probable; only the request stays open)."""
    docs = getattr(application, 'documents', None)
    if docs is None:
        return False
    str_doc = docs.filter(doc_type='str', superseded_at__isnull=True).order_by('-uploaded_at').first()
    if str_doc is None:
        return False
    sc = student_str_check(str_doc)
    return bool(sc and sc['current_status'] == 'current')


def member_cluster_complete(application, member):
    """True when this working member's salary-route income cluster is COMPLETE and COHERENT on its
    own — the unit behind the "one complete, clean earner cluster is enough to submit" gate (owner
    2026-07-08). Requires:
      - the earner's IC present, readable, and LINKING to the student (name_status 'match' — the
        shared patronymic for a father/sibling, the birth certificate for a mother, the letter for
        a guardian);
      - this earner's income PROOF present (their salary slip, OR a non-breached household STR
        standing in per the P3 STR-precedence rule);
      - the relationship doc present where required (mother -> birth certificate, guardian ->
        letter; father/sibling need none);
      - NO person-mismatch between the IC and the salary slip.
    A member whose cluster clears this carries the application through the income gate; every OTHER
    member's missing docs or document errors then become soft Check-2 follow-ups (see
    `salary_income_satisfied`)."""
    if not member:
        return False
    ic = _member_ic_doc(application, member)
    if ic is None:
        return False
    icc = student_income_ic_check(ic)
    if not icc or not icc.get('readable') or icc.get('name_status') != 'match':
        return False
    if not (_cluster_docs(application, member, 'salary_slip').exists() or str_not_breached(application)):
        return False
    for p in _cluster_docs(application, member, 'salary_slip'):
        pc = student_income_proof_check(p)
        if pc and 'mismatch' in (pc.get('name_status'), pc.get('nric_status')):
            return False
    rel = relationship_doc_for(member)
    if rel and not application.documents.filter(
            doc_type=rel, superseded_at__isnull=True).exists():
        return False
    return True


def salary_income_satisfied(application):
    """Salary route: True when AT LEAST ONE selected working member has a complete, clean cluster
    (`member_cluster_complete`). This is the "one clean cluster is enough to submit" gate (owner
    2026-07-08): once one earner is fully and coherently documented, every OTHER member's missing
    docs AND document errors (e.g. an extraneous, misread second-parent IC) become soft Check-2
    follow-ups, never submission blockers. False off the salary route — the STR route has its own
    precedence rule (`household_str_status` / `str_not_breached`)."""
    if (getattr(application, 'income_route', '') or '').strip() != 'salary':
        return False
    return any(member_cluster_complete(application, m) for m in working_members(application))


def income_established(application):
    """True when the household's income is ALREADY established by a clean, dispositive document, on
    EITHER route: a complete salary cluster (`salary_income_satisfied`) OR a valid household STR
    (`household_str_status` — the government's means-test, matched to a parent/guardian). Owner
    2026-07-08: in either case an EXTRANEOUS or misread income document must NOT hard-block
    submission — it becomes a soft Check-2 follow-up. This is the route-agnostic form of "one clean
    cluster is enough"; it also covers the STR twin where the OTHER parent's IC is cross-checked
    against a single-recipient STR and 'mismatches' meaninglessly (a valid father's STR + an
    extraneous mother IC, #28)."""
    if salary_income_satisfied(application):
        return True
    grade, _member = household_str_status(application)
    return grade is not None


def declared_amount(application, member):
    """A working member's DECLARED average monthly income (RM, int > 0) from the income
    wizard, or None. Stored in ``ScholarshipApplication.income_declared = {member: amount}``.
    Tolerant of a blank/None/garbage value."""
    raw = getattr(application, 'income_declared', None)
    if not isinstance(raw, dict):
        return None
    try:
        amt = int(raw.get(member))
    except (TypeError, ValueError):
        return None
    return amt if amt > 0 else None


def has_income_support_doc(application, member):
    """True when a supporting income document is on file for this member AND IT READ —
    an ``income_support_doc`` (an employer/wage letter, bank statements showing income, OR a
    community/penghulu letter; D1 flexible evidence, any ONE suffices). Backs a DECLARED
    amount for a non-STR household. Accepts a doc tagged to the member OR untagged
    (household-level) — an Action-Centre request upload may land without a member tag, and
    one family-level supporting letter is enough under the flexible-evidence rule.

    **V1 (finding #2):** mere PRESENCE no longer counts — a blank/wrong image used to "prove"
    a declared informal income. The doc must have been READ: its stored ``student_verdict``
    (from the field-extraction on upload) is ``'ok'`` (a real support document with at least
    one field). A doc that read nothing (``'wrong_doc'``) or was never scanned does NOT clear
    the gap, so Check 2 keeps asking for real evidence."""
    docs = getattr(application, 'documents', None)
    if docs is None:
        return False
    for d in docs.filter(doc_type='income_support_doc', household_member__in=[member, ''],
                         superseded_at__isnull=True):
        sv = (getattr(d, 'vision_fields', None) or {}).get('student_verdict', '')
        if sv == 'ok':
            return True
    return False


# Foreign (Singapore) salary → MYR for the B40 means-test (owner 2026-07-05). A Malaysian working
# in Singapore submits an S$ payslip; counting the S$ figure as ringgit understates income ~3× and
# produces a FALSE B40 (e.g. #105: S$3,114 read as "RM3,114"). Convert an SGD slip to MYR at the
# configured rate — but ONLY while the application is still IN REVIEW; a case already decided
# (recommended and beyond) keeps its as-recorded basis, so the correction never disturbs a made
# decision (owner: "leave out #75").
_INCOME_CONVERT_STATUSES = frozenset({'submitted', 'shortlisted', 'profile_complete',
                                      'interviewing', 'interviewed'})
# The STRUCTURAL Singapore-company suffix: every Singapore company is a "Pte Ltd" / "Private
# Limited" (a Malaysian company is "Sdn Bhd"). This is the systemic anchor — NOT any particular
# company name — so ANY Singapore employer's payslip is detected. Dots/spacing normalised.
_SGD_EMPLOYER_RE = re.compile(r'\bpte\s*ltd\b|\bprivate\s+limited\b')


def _slip_is_sgd(fields):
    """True when a salary slip's amounts are in Singapore dollars, from two STRUCTURAL signals (no
    hard-coded company names):
      * the employer is a Singapore company — 'Pte Ltd' / 'Private Limited' (Malaysian = 'Sdn Bhd'),
      * OR the read ``currency`` is SGD / S$ — which the extractor sets from any Singapore tell-tale
        (an S$ sign, CPF / SDL deductions, a Singapore address / FIN), so a non-'Pte Ltd' issuer such
        as a statutory board or co-operative is still caught.
    The employer suffix is deterministic and stable across re-runs; the currency covers the rest."""
    emp = re.sub(r'[.\s]+', ' ', (fields.get('employer') or '').lower())
    if _SGD_EMPLOYER_RE.search(emp):
        return True
    cur = (fields.get('currency') or '').strip().upper()
    return 'SGD' in cur or 'S$' in cur


def sgd_to_myr_rate():
    from django.conf import settings
    try:
        return float(getattr(settings, 'SGD_TO_MYR_RATE', 3.15) or 3.15)
    except (TypeError, ValueError):
        return 3.15


def _to_myr(amt, fields, application):
    """A foreign (SGD) salary expressed in MYR for the means-test, at the configured rate — but only
    for an application still IN REVIEW. A decided case (recommended+) keeps its as-recorded figure."""
    if amt is None or not _slip_is_sgd(fields):
        return amt
    if (getattr(application, 'status', '') or '') not in _INCOME_CONVERT_STATUSES:
        return amt
    return amt * sgd_to_myr_rate()


def earner_monthly_income(application, member):
    """A working member's estimated MONTHLY income from their documents + the source.
    The salary slip's gross is primary; failing that, the EPF statement (the statutory-rate
    salary reverse, or 0 when unemployed); failing that, a DECLARED informal amount.
    Returns ``(amount: float | None, source)`` where source is
    ``'salary' | 'epf_estimate' | 'declared_str' | 'declared_evidenced' | 'declared_unproven' | 'unknown'``.

    Declared informal income (Phase 2A, P5b): a member with no payslip/EPF may declare an
    average monthly wage. It is ACCEPTED as a real figure when the household has a valid STR
    (``declared_str`` — the STR is the means-test) OR a supporting income document backs it
    (``declared_evidenced``); otherwise it is UNPROVEN — returns ``(None, 'declared_unproven')``
    so per-capita stays 'not all known' and the headroom band falls to Unsure until evidence
    lands (never inflates income on an unbacked self-report)."""
    for slip in _cluster_docs(application, member, 'salary_slip'):
        f = _doc_fields(slip)
        amt = _salary_monthly_amount(f)
        if amt:
            return _to_myr(amt, f, application), 'salary'   # SGD → MYR when the slip is Singaporean
    for epf in _cluster_docs(application, member, 'epf'):
        sal = _epf_monthly_salary(_doc_fields(epf))
        if sal is not None:
            return sal, 'epf_estimate'
    declared = declared_amount(application, member)
    if declared is not None:
        if has_valid_str(application):
            return float(declared), 'declared_str'
        if has_income_support_doc(application, member):
            return float(declared), 'declared_evidenced'
        return None, 'declared_unproven'
    return None, 'unknown'


def slip_epf_divergence(application, member):
    """#9: when a member has BOTH a salary slip (gross) AND an EPF statement (monthly
    contribution), cross-check the payslip salary against the EPF-implied salary
    (contribution ÷ 0.24). Returns ``{slip, epf_implied, ratio}`` only when they diverge
    beyond the generous ``_SLIP_EPF_LO``–``_SLIP_EPF_HI`` band, else None (also None when
    either figure is missing). A SOFT officer signal — overtime / late pay routinely move
    the two apart, so it is a 'verify at interview' nudge, never a gate."""
    slip = None
    for s in _cluster_docs(application, member, 'salary_slip'):
        amt = _parse_rm(_doc_fields(s).get('gross_income') or _doc_fields(s).get('net_income'))
        if amt:
            slip = amt
            break
    epf_implied = None
    for e in _cluster_docs(application, member, 'epf'):
        sal = _epf_monthly_salary(_doc_fields(e))
        if sal:                              # >0 (an unemployed EPF, 0.0, has no salary to compare)
            epf_implied = sal
            break
    if not slip or not epf_implied:
        return None
    ratio = slip / epf_implied
    if _SLIP_EPF_LO <= ratio <= _SLIP_EPF_HI:
        return None
    return {'slip': round(slip, 2), 'epf_implied': epf_implied, 'ratio': round(ratio, 2)}


def income_per_capita(application, members):
    """``(per_capita, all_known)`` — the document-derived household monthly income
    (sum of every working member's income) divided by the household size. ``all_known``
    is False when any member's income couldn't be read (so the per-capita is unreliable
    → the verdict falls to a human/interview). ``per_capita`` is None when income is
    unknown or there's no household size."""
    total, all_known = 0.0, True
    for m in (members or []):
        amt, _src = earner_monthly_income(application, m)
        if amt is None:
            all_known = False
        else:
            total += amt
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not all_known or not size:
        return None, all_known
    return total / size, all_known


# A breach-room below this (RM/month) means one undeclared earner could plausibly push the
# household over the B40 line — so an uncorroborated household size can't carry a confident pass.
# Yardstick = the per-capita ceiling itself (≈ one more head at the line). (str-proof-spec.md §7.1.)
_HEADROOM_THIN_RM = 1584.0


def income_headroom(application, members):
    """Margin-graded B40 confidence for the SALARY route (docs/scholarship/str-proof-spec.md §7.1).

    Returns ``(band, ctx)`` where band is:
      'unknown'  — income or household size couldn't be computed → assess at interview.
      'over'     — household income clears BOTH the gross ceiling AND the per-capita safety net →
                   above the B40 line (never auto-rejected; → interview).
      'unsure'   — B40, but only thinly: an undeclared earner could plausibly breach the line
                   (breach-room < one per-capita head), OR an earner's income couldn't be read.
                   The household size isn't corroborated enough to bank the pass.
      'probable' — B40 with large breach-room: an undeclared earner would need an implausibly high
                   wage to breach → confident-enough for 🔵 (interview confirms; GREEN is reserved
                   for a corroborated household, which the family roster will later supply).

    B40 holds while gross ≤ max(gross_ceiling, per_capita_ceiling × size) — the gross ceiling is
    primary, the per-capita ceiling a safety net above it. ``breach_room`` is how much more monthly
    income would tip the household out; grading by it is what separates #13 (thin → unsure) from the
    SARA case (large → probable). ``ctx`` carries the figures for the verdict copy / interview note."""
    cohort = getattr(application, 'cohort', None)
    gross_ceiling = getattr(cohort, 'income_ceiling', None)
    pc_ceiling = getattr(cohort, 'per_capita_ceiling', None)
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    pc, all_known = income_per_capita(application, members)
    if pc is None or not size or not pc_ceiling:
        return 'unknown', {'all_known': all_known}
    gross = pc * size
    # The more generous (binding) test. A cohort without a gross ceiling configured falls
    # back to the per-capita safety net alone (code-health S4 #14 made this the shared
    # B40 test for BOTH routes, so it must tolerate either ceiling being absent).
    ceiling = max([c for c in (gross_ceiling, pc_ceiling * size) if c])
    breach_room = ceiling - gross
    ctx = {'gross': int(round(gross)), 'per_capita': int(round(pc)), 'size': size,
           'breach_room': int(round(breach_room)), 'all_known': all_known,
           'gross_ceiling': int(gross_ceiling or 0), 'per_capita_ceiling': int(pc_ceiling)}
    if breach_room < 0:
        return 'over', ctx
    if not all_known or breach_room < _HEADROOM_THIN_RM:
        return 'unsure', ctx
    return 'probable', ctx


# ── Relationship-proof documents: birth certificate + guardianship letter ────
def _name_bucket(extracted, reference):
    if not (extracted or '').strip() or not (reference or '').strip():
        return 'no_ref'
    return 'mismatch' if name_match(extracted, reference) == 'mismatch' else 'match'


def _nric_bucket(extracted, reference):
    from .vision import nric_match
    if not (extracted or '').strip() or not (reference or '').strip():
        return 'no_ref'
    return 'match' if nric_match(extracted, reference) else 'mismatch'


def _combine_relationship(name_b, nric_b, nric_one_digit=False):
    """Combine a relationship row's NAME + NRIC buckets, treating the NAME as the primary
    proof of the link and the NRIC as corroboration. A birth-certificate / letter NRIC is
    AI-read off a security-printed JPN document, so a single misread digit (8↔9, 0↔6 over
    the green guilloche) is common; when the NAME matches, an NRIC clash is therefore amber
    ("look at the number"), NOT a red 'mismatch'. When the clash is exactly one digit
    (``nric_one_digit``) the amber is the more reassuring 'check_near' ("differs by one
    digit — likely a scan misread"); a larger clash is the plainer 'check'. Red is reserved
    for a real NAME mismatch (a genuinely different person) or an NRIC clash with no name to
    vouch for it. Strictly demotes false reds to amber — never turns a real mismatch green."""
    if name_b == 'mismatch':
        return 'mismatch'
    if name_b == 'match':
        if nric_b == 'mismatch':
            return 'check_near' if nric_one_digit else 'check'
        return 'match'
    # No NAME to compare (no_ref) — fall back to the NRIC alone.
    if nric_b == 'mismatch':
        return 'mismatch'
    if nric_b == 'match':
        return 'match'
    return 'no_ref'


def student_bc_check(doc):
    """Birth certificate: it links the student to their MOTHER (the income earner). Three
    rows: CHILD = the student (name + NRIC); MOTHER = the mother's IC (name + NRIC);
    FATHER = the student's patronymic. Returns the read fields + per-row status, or None."""
    if getattr(doc, 'doc_type', '') != 'birth_certificate':
        return None
    app = doc.application
    f = _doc_fields(doc)
    student = getattr(getattr(app, 'profile', None), 'name', '') or ''
    student_nric = getattr(getattr(app, 'profile', None), 'nric', '') or ''
    child_name = (f.get('bc_child_name', '') or '').strip()
    child_nric = (f.get('bc_child_nric', '') or '').strip()
    child_status = _combine_relationship(_name_bucket(child_name, student),
                                         _nric_bucket(child_nric, student_nric),
                                         nric_close(child_nric, student_nric))
    mother_name = (f.get('bc_mother_name', '') or '').strip()
    mother_nric = (f.get('bc_mother_nric', '') or '').strip()
    mic = _member_ic_doc(app, 'mother')
    mic_name = getattr(mic, 'vision_name', '') if mic else ''
    mic_nric = getattr(mic, 'vision_nric', '') if mic else ''
    mother_status = _combine_relationship(_name_bucket(mother_name, mic_name),
                                          _nric_bucket(mother_nric, mic_nric),
                                          nric_close(mother_nric, mic_nric))
    # IC-NUMBER chain (#9): the mother's IC NUMBER appears on the income proof → she is the
    # confirmed earner, regardless of a wrong card uploaded in her slot. The BC mother row is
    # exactly what the chain is built on, so it is verified (never red on the wrong card).
    if mother_status != 'match' and chain_verified_earner(app, 'mother'):
        mother_status = 'match'
    father_name = (f.get('bc_father_name', '') or '').strip()
    father_status = _name_bucket(father_name, father_name_from_ic(student))
    return {
        'child_name': child_name, 'child_status': child_status,
        'mother_name': mother_name, 'mother_nric': mother_nric, 'mother_status': mother_status,
        'father_name': father_name, 'father_status': father_status,
        'bc_number': (f.get('bc_number', '') or '').strip(),
    }


def student_guardianship_check(doc):
    """Guardianship order / authorisation letter: ties the legal guardian to the student
    (the ward). GUARDIAN = the guardian's IC (name + NRIC); WARD = the student. Returns
    the read fields + per-row status, or None for a non-guardianship doc."""
    if getattr(doc, 'doc_type', '') != 'guardianship_letter':
        return None
    app = doc.application
    f = _doc_fields(doc)
    student = getattr(getattr(app, 'profile', None), 'name', '') or ''
    g_name = (f.get('guardian_name', '') or '').strip()
    g_nric = (f.get('guardian_nric', '') or '').strip()
    gic = _member_ic_doc(app, 'guardian')
    gic_name = getattr(gic, 'vision_name', '') if gic else ''
    gic_nric = getattr(gic, 'vision_nric', '') if gic else ''
    guardian_status = _combine_relationship(_name_bucket(g_name, gic_name),
                                            _nric_bucket(g_nric, gic_nric),
                                            nric_close(g_nric, gic_nric))
    ward_name = (f.get('ward_name', '') or '').strip()
    return {
        'guardian_name': g_name, 'guardian_nric': g_nric, 'guardian_status': guardian_status,
        'ward_name': ward_name, 'ward_status': _name_bucket(ward_name, student),
        'doc_kind': (f.get('doc_kind', '') or '').strip(),
    }


def student_income_support_check(doc):
    """V1: a declared-income supporting document (employer/wage letter, bank statement, or
    community/penghulu letter). Returns the read fields + whether it READ as a real support
    document (``read_status``), or None for another doc type. It NAMES THE EARNER, not the
    student, so there is no student name-match — the READ itself is the officer's signal
    (#2: a blank image must not pass as evidence for a declared informal income)."""
    if getattr(doc, 'doc_type', '') != 'income_support_doc':
        return None
    f = _doc_fields(doc)
    sv = (getattr(doc, 'vision_fields', None) or {}).get('student_verdict', '')
    return {
        'name': (f.get('name', '') or '').strip(),
        'amount': (f.get('amount', '') or '').strip(),
        'issuer': (f.get('issuer', '') or '').strip(),
        'kind': (f.get('kind', '') or '').strip(),
        'read_status': 'read' if sv == 'ok' else 'unread',
    }


# ── Utility bills as a SOFT B40 proxy + hardship signal (imperfect; officer context) ─
# Utility spend is a WEAK, noisy wealth proxy (especially once STR already verifies B40),
# so the bands are deliberately generous: a normal household reads 'reasonable', and only
# a genuinely high per-capita is worth an officer's eye. No amber 'borderline' band — it
# only produced spurious "explain your utility spend" concerns on ordinary families.
_UTILITY_B40_CEILING = 40   # < RM40/capita/month combined → comfortably consistent with B40
_UTILITY_HIGH_FLOOR = 60    # > RM60/capita/month → only then worth an officer's eye (M40/T20)


# Reading a utility bill: a month-name → number map (Malay + English, common OCR forms)
# and a tolerant period parser, so "Mei 2026" / "05/2026" / "2026-05" all resolve.
_UTILITY_MONTHS = {
    'jan': 1, 'feb': 2, 'mac': 3, 'mar': 3, 'apr': 4, 'apl': 4, 'mei': 5, 'may': 5,
    'jun': 6, 'jul': 7, 'ogo': 8, 'aug': 8, 'sep': 9, 'okt': 10, 'oct': 10,
    'nov': 11, 'dis': 12, 'dec': 12,
}
_UTILITY_CURRENT_MONTHS = 3   # a bill within ~3 months of the review date counts as current


def _parse_billing_month(period):
    """``(year, month)`` from a free-form billing period ('Mei 2026', '05/2026',
    '2026-05', 'April 2026'), or None when nothing parseable is found."""
    if not period:
        return None
    t = str(period).lower()
    ym = re.search(r'(20\d{2})', t)
    year = int(ym.group(1)) if ym else None
    month = None
    for name, num in _UTILITY_MONTHS.items():
        if name in t:
            month = num
            break
    if month is None:                                  # numeric month
        m = re.search(r'\b(\d{1,2})[/\-.](20\d{2})\b', t)
        if m:
            month, year = int(m.group(1)), int(m.group(2))
        else:
            m = re.search(r'\b(20\d{2})[/\-.](\d{1,2})\b', t)
            if m:
                year, month = int(m.group(1)), int(m.group(2))
    if not year or not month or not (1 <= month <= 12):
        return None
    return year, month


def _utility_currency(period, today):
    """Is the bill recent? 'current' (within ~3 months of *today*) | 'stale' (older) |
    'unknown' (no readable date). Measured against the review date, not the application
    date — the question is whether this is a LIVE household paying bills now."""
    ym = _parse_billing_month(period)
    if not ym:
        return 'unknown'
    year, month = ym
    months_ago = (today.year - year) * 12 + (today.month - month)
    if months_ago < 0:                                 # future-dated (data entry) → treat current
        return 'current'
    return 'current' if months_ago <= _UTILITY_CURRENT_MONTHS else 'stale'


def utility_reasonable(application):
    """Combined household utility consumption as a soft B40 proxy, shown identically on
    every bill row. Water alone is a weak signal (cheap, flat across households) — so a
    verdict is only given when BOTH bills are present; one bill → 'partial' (can't judge).
    Returns ``{status, detail, per_capita}``:
      - status: 'reasonable' (≤ RM60/head — the normal case) | 'high' (> RM60/head, an
                officer/interview signal only, NEVER a student query) | 'partial' (only one
                bill) | 'unknown' (no amount / no household size). No amber 'borderline'.
      - detail: 'both' | 'water_only' | 'electricity_only' | '' — which bills informed it."""
    amounts = {}
    for dt in ('water_bill', 'electricity_bill'):
        d = _latest_doc(application, dt)
        amt = _parse_rm(_doc_fields(d).get('amount')) if d else None
        if amt is not None:
            amounts[dt] = amt
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not amounts or not size:
        return {'status': 'unknown', 'detail': '', 'per_capita': None}
    if len(amounts) < 2:                               # one bill alone can't judge consumption
        detail = 'water_only' if 'water_bill' in amounts else 'electricity_only'
        return {'status': 'partial', 'detail': detail, 'per_capita': None}
    pc = sum(amounts.values()) / size
    # Two outcomes only — no amber middle. A normal household is 'reasonable'; only a
    # genuinely high per-capita (> RM60/head) flags, and that is an officer/interview
    # signal (possible undeclared income), never something the student is queried about.
    status = 'high' if pc > _UTILITY_HIGH_FLOOR else 'reasonable'
    return {'status': status, 'detail': 'both', 'per_capita': round(pc, 2)}


def _utility_name_unrelated(application, bill_name):
    """True when the account-holder name matches NEITHER the student, NOR a declared parent /
    roster member (father / mother / named guardian / sibling), NOR any uploaded parent/earner
    IC — a soft 'bill is in someone else's name' note. Bills are routinely in a parent's name
    (fine — that matches the roster / IC); the note fires only when it's a genuine stranger.
    Never asserted on a blank read or with no reference name to compare against.

    Owner 2026-07-08: the DECLARED father/mother names (from 'My family') are now checked FIRST,
    so a bill in the father's name no longer triggers a 'whose bill?' query just because no parent
    IC happens to be on file (the SIVAKUMAR A/L KALIAPPAN over-ask)."""
    bill = (bill_name or '').strip()
    if not bill:
        return False
    candidates = []
    student = getattr(getattr(application, 'profile', None), 'name', '') or ''
    if student.strip():
        candidates.append(student)
    for _member, nm in _roster_candidates(application):   # declared father/mother/guardian/siblings
        if nm.strip():
            candidates.append(nm)
    for ic in application.documents.filter(doc_type='parent_ic', superseded_at__isnull=True):
        nm = (getattr(ic, 'vision_name', '') or '').strip()
        if nm:
            candidates.append(nm)
    if not candidates:
        return False
    return all(name_match(bill, c) == 'mismatch' for c in candidates)


def _utility_holder_names(application):
    """Every non-blank account-holder name read off the household's water + electricity
    bills (latest first)."""
    names = []
    for dt in ('water_bill', 'electricity_bill'):
        for doc in application.documents.filter(
                doc_type=dt, superseded_at__isnull=True).order_by('-uploaded_at'):
            nm = (_doc_fields(doc).get('name', '') or '').strip()
            if nm:
                names.append(nm)
    return names


def _same_utility_holder(a, b):
    """Two utility-bill holder names are the SAME person under an OCR cut/wrinkle: they
    share every name token but one EXACTLY, and the odd token is one CONTAINED in the other
    (a dropped letter — 'HANA' ⊂ 'THANA'). Deliberately strict — a pure substitution
    (Siva vs Sira) or a genuinely different name never merges, so reconciliation only ever
    swaps in a cleaner read of the SAME holder, never conflates two people. Token order is
    not significant (the canonical tokens are an unordered set)."""
    sa, sb = set(canonical_name_tokens(a)), set(canonical_name_tokens(b))
    if not sa or not sb or len(sa) != len(sb) or len(sa) < 2:
        return False
    only_a, only_b = sa - sb, sb - sa
    if not only_a:                       # identical token sets
        return True
    if len(only_a) == 1 and len(only_b) == 1:
        x, y = only_a.pop(), only_b.pop()
        return (x in y or y in x) and abs(len(x) - len(y)) <= 2
    return False


def _reconciled_holder_name(application, raw_name):
    """The cleanest read of THIS account holder across the household's utility bills.
    A wrinkled / cut bill can drop a letter — 'HANA BALAN A/L NARAYANAN' for the clean
    'THANA BALAN A/L NARAYANAN' — so when another bill carries the SAME person's name,
    prefer the LONGEST, most complete read. Deterministic + auditable; no AI guess.
    Returns ``raw_name`` unchanged when nothing reconciles."""
    raw = (raw_name or '').strip()
    if not raw:
        return raw
    best = raw
    for nm in _utility_holder_names(application):
        if nm != best and _same_utility_holder(nm, raw) and len(nm) > len(best):
            best = nm
    return best


def utility_check(doc, today=None):
    """For a water / electricity bill: the account-holder name (a data point — bills are in
    a parent's name), the home address (matched via the upload-time ``vision_address_match``),
    the monthly charge + any arrears, plus three soft facts — whether the bill is CURRENT
    (≤3 months old), whether household consumption is REASONABLE (combined per-capita, both
    bills), and whether ARREARS exceed the current charge (a hardship signal). All soft,
    never a gate. Returns the fact dict or None for a non-utility doc."""
    if getattr(doc, 'doc_type', '') not in ('water_bill', 'electricity_bill'):
        return None
    if today is None:
        today = datetime.date.today()
    app = doc.application
    f = _doc_fields(doc)
    # Reconcile OCR variants of the holder across the household's bills — a wrinkled bill
    # that dropped a letter is reported under its clean form, so the row + the flag quote
    # the full name (e.g. 'HANA BALAN' read from a creased bill → 'THANA BALAN').
    name = _reconciled_holder_name(app, (f.get('name', '') or '').strip())
    monthly = _parse_rm(f.get('amount'))
    arrears = _arrears_amount(f.get('unpaid_balance'))
    reasonable = utility_reasonable(app)
    return {
        'name': name,
        'address': (f.get('address', '') or '').strip(),
        'monthly_bill': (f.get('amount', '') or '').strip(),
        'unpaid_balance': (f.get('unpaid_balance', '') or '').strip(),
        'address_status': getattr(doc, 'vision_address_match', '') or '',
        'current_status': _utility_currency(f.get('billing_period'), today),
        'reasonable_status': reasonable['status'],
        'reasonable_detail': reasonable['detail'],
        # 'arrears' (shown green) only when arrears exceed the current charge; else hidden.
        'outstanding_status': 'arrears' if (arrears and monthly and arrears > monthly) else '',
        'name_note': 'unrelated' if _utility_name_unrelated(app, name) else '',
    }


def utility_holder_unknown(application):
    """#8: the account-holder name on a water/electricity bill matches NEITHER the student
    nor any uploaded parent IC — a 'whose bill is this?' query. Returns the holder name of
    the first such bill, or None. Bills routinely sit in a parent's name (fine — that
    matches the IC); this fires only when the holder is a stranger to the documents."""
    for dt in ('water_bill', 'electricity_bill'):
        for doc in application.documents.filter(
                doc_type=dt, superseded_at__isnull=True).order_by('-uploaded_at'):
            facts = utility_check(doc)
            if facts and facts.get('name_note') == 'unrelated' and facts.get('name'):
                return facts['name']
    return None


def utility_address_mismatch(application):
    """#8: a water/electricity bill's supply address is a HARD mismatch against the
    student's stated address. Returns True only on ``vision_address_match == 'mismatch'`` —
    a 'partial' (a missing postcode or a shortened/abbreviated street) deliberately stays
    silent, so only a genuinely different address raises the query. Soft, never a gate."""
    for dt in ('water_bill', 'electricity_bill'):
        for doc in application.documents.filter(doc_type=dt, superseded_at__isnull=True):
            if (getattr(doc, 'vision_address_match', '') or '') == 'mismatch':
                return True
    return False


def _latest_doc(application, doc_type):
    return (application.documents.filter(doc_type=doc_type, superseded_at__isnull=True)
            .order_by('-uploaded_at').first())


def utility_per_capita(application):
    """Combined water + electricity MONTHLY bill ÷ household size, with a soft B40 proxy.
    Returns ``{per_capita, signal}`` ('b40' | 'neutral' | 'high') or None when no bill
    amount / household size. IMPERFECT — officer context, never a verdict gate."""
    total, any_read = 0.0, False
    for dt in ('water_bill', 'electricity_bill'):
        doc = _latest_doc(application, dt)
        amt = _parse_rm(_doc_fields(doc).get('amount')) if doc else None
        if amt is not None:
            total += amt
            any_read = True
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not any_read or not size:
        return None
    pc = total / size
    signal = 'b40' if pc < _UTILITY_B40_CEILING else ('high' if pc > _UTILITY_HIGH_FLOOR else 'neutral')
    return {'per_capita': round(pc, 2), 'signal': signal}


def utility_monthly_total(application):
    """Combined water + electricity MONTHLY charge (RM), or None when neither bill
    amount could be read. Used for the 'utility spend high vs declared income' flag."""
    total, any_read = 0.0, False
    for dt in ('water_bill', 'electricity_bill'):
        doc = _latest_doc(application, dt)
        amt = _parse_rm(_doc_fields(doc).get('amount')) if doc else None
        if amt is not None:
            total += amt
            any_read = True
    return round(total, 2) if any_read else None


def utility_hardship(application):
    """True when the utility bills carry meaningful arrears (unpaid balance) — a soft
    hardship signal that SUPPORTS need. Sums arrears across water + electricity."""
    total = 0.0
    for dt in ('water_bill', 'electricity_bill'):
        doc = _latest_doc(application, dt)
        amt = _arrears_amount(_doc_fields(doc).get('unpaid_balance')) if doc else None
        if amt:
            total += amt
    return total > 100


def income_cluster_advice(application, member):
    """The SINGLE coach verdict for a household member's whole Income cluster — their IC
    (the anchor) + their income proofs (STR / salary slip / EPF) + their relationship doc —
    so Cikgu Gopal speaks ONCE per earner, at the foot of the cluster, not once per file.
    Income is a cluster (Father's IC + Father's payslip + …), unlike the single-document
    Identity / Academic / Pathway facts. The verdict is anchored on a POSITION (the cluster
    foot), so it speaks even before the IC arrives — it folds in the STR-currency and
    'add the IC' nudges that used to live on the STR / payslip rows.

    Precedence (most serious first):
      1. relationship — the IC does not link to the student (wrong person's card);
      2. readable     — the IC could not be read;
      3. STR currency — the STR is stale / rejected (STR route);
      4. coherence    — a payslip / EPF / STR is a DIFFERENT person from the IC;
      5. missing IC   — proofs are uploaded but the earner's IC is not, so we can't confirm.
    Returns '' when the cluster is consistent (or empty)."""
    if not member:
        return ''
    route = (getattr(application, 'income_route', '') or '').strip()
    str_doc = (application.documents.filter(doc_type='str', superseded_at__isnull=True)
               .order_by('-uploaded_at').first()
               if route == 'str' else None)
    proofs = [p for dt in ('salary_slip', 'epf') for p in _cluster_docs(application, member, dt)]
    has_proof = bool(proofs) or str_doc is not None

    ic = _member_ic_doc(application, member)
    if ic is None:
        # No IC yet. STR currency can still be judged from the STR alone; otherwise, if any
        # proof was uploaded, nudge to add the earner's IC so we can confirm the person.
        if str_doc is not None:
            sc = student_str_check(str_doc)
            if sc and sc['current_status'] in STR_COACH_STATES:
                return 'str_not_current'
        return 'income_ic_needed' if has_proof else ''

    # IC present — the full cluster, in precedence order.
    icc = student_income_ic_check(ic)
    if icc:
        if icc['name_status'] == 'mismatch':
            return 'income_relationship_mismatch'
        if getattr(ic, 'vision_run_at', None) and not icc['readable']:
            return 'unreadable'
    if str_doc is not None:
        sc = student_str_check(str_doc)
        if sc and sc['current_status'] in STR_COACH_STATES:
            return 'str_not_current'
    # Coherence — every proof (payslip / EPF, and the STR recipient) must be the SAME
    # person as the earner's IC.
    for p in proofs:
        pc = student_income_proof_check(p)
        if pc and 'mismatch' in (pc['name_status'], pc['nric_status']):
            return 'income_proof_person_mismatch'
    if str_doc is not None:
        sc = student_str_check(str_doc)
        if sc and 'mismatch' in (sc['name_status'], sc['nric_status']):
            return 'income_proof_person_mismatch'
    # Salary route: the salary slip is this earner's compulsory income PROOF — the document that
    # actually shows the income. If the IC is in and matches but the salary slip is still
    # missing, nudge it as the logical NEXT step, BEFORE the relationship doc (uploading a birth
    # certificate before any proof of income is out of order). EPF doesn't substitute it (gate v2).
    if route == 'salary' and not _cluster_docs(application, member, 'salary_slip').exists():
        return 'income_proof_needed'
    # IC present + coherent. The relationship-proof doc (mother → birth certificate, guardian
    # → letter) links the earner to the student — it's the LAST step (father/sibling need none:
    # the shared patronymic on the IC proves it).
    rel_doc = relationship_doc_for(member)
    if rel_doc:
        rel_obj = (application.documents.filter(doc_type=rel_doc, superseded_at__isnull=True)
                   .order_by('-uploaded_at').first())
        if rel_obj is None:
            return 'income_rel_doc_needed'             # not uploaded yet → nudge for it
        # Uploaded, but we still can't confirm the link. A name CLASH already returned
        # 'income_relationship_mismatch' above; a 'pending' here once the doc has been
        # PROCESSED means it was unreadable / the wrong document (e.g. an IC sent as a birth
        # cert). The relationship doc is a field-extraction doc (birth cert / letter), so its
        # "processed" stamp is vision_fields_run_at — NOT vision_run_at, which only the IC path
        # sets (a birth cert never has it). Accept either so the check survives doc-type quirks.
        rel_status = icc['name_status'] if icc else 'pending'
        rel_ran = (getattr(rel_obj, 'vision_fields_run_at', None)
                   or getattr(rel_obj, 'vision_run_at', None))
        # Code-health S4 #18: 'pending' can come from EITHER side of the comparison. Only
        # blame the relationship doc when the EARNER IC has actually been read — an IC whose
        # OCR is still pending (vision_run_at NULL, a known transient state the self-heal
        # cron clears) used to surface as 'income_rel_doc_unreadable', telling the student
        # to re-upload a perfectly fine birth certificate and blocking submission on it.
        ic_ran = bool(getattr(ic, 'vision_run_at', None))
        if rel_status == 'pending' and rel_ran and ic_ran:
            return 'income_rel_doc_unreadable'
    return ''


def salary_member_blocks(members) -> list:
    """Per-member document plan for the salary route. For each working member, the
    documents that person contributes — compulsory IC (+ relationship doc for a
    mother/guardian), optional salary slip + EPF. Income-evidence docs (parent_ic /
    salary_slip / epf) are TAGGED to the member; the relationship doc (birth cert /
    guardianship letter) is a single household doc, untagged.

    Returns ``[{member, compulsory: [(doc_type, member_tag)],
                optional: [(doc_type, member_tag)], rel_doc}]`` in display order."""
    chosen = {m for m in (members or []) if m in _MEMBER_ORDER}
    blocks = []
    for m in _MEMBER_ORDER:
        if m not in chosen:
            continue
        # Compulsory order (drives both the gate and the cockpit panel): the member's
        # IC → their salary slip → the relationship doc (mother/guardian only). The
        # salary slip is COMPULSORY (gate v2, 2026-06-05) — EPF does not substitute it.
        compulsory = [('parent_ic', m), ('salary_slip', m)]
        rel = relationship_doc_for(m)
        if rel:
            compulsory.append((rel, ''))            # birth cert / letter — single, untagged
        optional = [('epf', m)]
        blocks.append({'member': m, 'compulsory': compulsory,
                       'optional': optional, 'rel_doc': rel})
    return blocks


# ── The requirement engine ───────────────────────────────────────────────────

def income_requirements(application) -> dict:
    """Given the wizard answers on *application*, the documents the family needs.

    Returns ``{route, members, compulsory, optional}``:
      - ``route``      — '' | 'str' | 'salary'.
      - ``members``    — salary route only: the per-member blocks from
                         ``salary_member_blocks`` (empty for the STR route).
      - ``compulsory`` — flat doc-type list (STR route: earner IC + relationship + STR;
                         salary route: empty — everything is per-member).
      - ``optional``   — household-level credibility docs (utility bills).

    The STR route keeps the original single-earner shape; the salary route is driven
    by ``income_working_members`` (multi-select). Optional docs never block. Blank
    answers (wizard not walked) → just the earner IC compulsory; the verdict flags it."""
    route = (getattr(application, 'income_route', '') or '').strip()

    if route == 'salary':
        members = salary_member_blocks(effective_working_members(application))
        return {'route': 'salary', 'members': members,
                'compulsory': [], 'optional': ['water_bill', 'electricity_bill']}

    # STR route (single earner) + the blank fallback.
    earner = (getattr(application, 'income_earner', '') or '').strip()
    compulsory = ['parent_ic']                 # the earner's IC — always
    rel_doc = relationship_doc_for(earner)
    if rel_doc:
        compulsory.append(rel_doc)             # mother→BC, guardian→letter; father→none
    optional: list[str] = []
    if route == 'str':
        compulsory.append('str')
        optional += ['water_bill', 'electricity_bill', 'salary_slip', 'epf']
    # route blank → wizard not started; only the earner IC stands. Verdict flags it.

    # De-dup while preserving order; a doc is never both compulsory and optional.
    seen = set(compulsory)
    optional = [d for d in optional if not (d in seen or seen.add(d))]
    return {'route': route, 'members': [], 'compulsory': compulsory, 'optional': optional}


# ── Full-household-income completeness (reviewer-query automation S1) ─────────
# The sponsor counts the FULL household income, but apply only collects the ONE declared
# earner's documents — so reviewers repeatedly ask, by hand, for the OTHER parent's payslip
# (when they work) or their status (when their slot is blank). This is deterministic: every
# parent must be EITHER marked non-earning (status known) OR have income evidence on file.

def _parent_has_income_evidence(application, member):
    """True when an income DOCUMENT covers this parent: a salary slip / EPF tagged to them,
    or — on the STR route — they are the single STR earner with an STR doc, or the IC-number
    chain confirms them. (Roster-only 'they earn' is NOT evidence — that's the gap.)"""
    if (_cluster_docs(application, member, 'salary_slip').exists()
            or _cluster_docs(application, member, 'epf').exists()):
        return True
    route = (getattr(application, 'income_route', '') or '').strip()
    if (route == 'str'
            and (getattr(application, 'income_earner', '') or '').strip() == member
            and application.documents.filter(doc_type='str', superseded_at__isnull=True).exists()):
        return True
    if member in ('mother', 'father') and chain_verified_earner(application, member):
        return True
    return False


def parent_income_status(application, member):
    """One parent's income-completeness verdict (member = 'father' | 'mother'):
      'satisfied'  — non-earning status is recorded (homemaker/deceased/…), OR income
                     evidence is on file;
      'need_proof' — an EARNING occupation is recorded but NO income document covers them
                     (ask for that parent's salary slip / EPF);
      'need_status'— the parent's slot is blank (no occupation), so we don't know whether
                     they earn (ask their work/status — the "why one earner" question).
    Tolerant of a test double missing the roster columns."""
    from .family import NON_EARNING
    occ = (getattr(application, f'{member}_occupation', '') or '').strip()
    if occ in NON_EARNING:
        return 'satisfied'                       # status known, non-earning → answered
    if _parent_has_income_evidence(application, member):
        return 'satisfied'                       # documented income on file
    if occ:
        return 'need_proof'                      # earning occupation, no income doc
    return 'need_status'                         # blank slot → ask their work/status


def parent_income_gaps(application):
    """The household-income completeness gaps across BOTH parents, as
    ``[{'member': 'father'|'mother', 'need': 'proof'|'status'}, …]`` (empty when both are
    satisfied). Drives the auto-raised reviewer queries that today are typed by hand.
    (Superseded by ``household_status_gaps``; kept for any parent-only callers.)"""
    gaps = []
    for member in ('father', 'mother'):
        status = parent_income_status(application, member)
        if status == 'need_proof':
            gaps.append({'member': member, 'need': 'proof'})
        elif status == 'need_status':
            gaps.append({'member': member, 'need': 'status'})
    return gaps


def member_income_status(application, member):
    """Income-completeness verdict for ANY roster member (father/mother/guardian/brother/sister),
    from the roster occupation + income evidence. Same states as ``parent_income_status``:
    'satisfied' | 'need_proof' | 'need_status'. Reads the occupation via ``_member_occupation``
    (father/mother columns; guardian/brother/sister from ``other_family_members``). Only a parent
    slot can be blank → 'need_status'; an other_family_members entry always carries a chosen
    occupation, so it can only be 'satisfied' or 'need_proof'."""
    from .family import NON_EARNING
    occ = _member_occupation(application, member)
    if occ in NON_EARNING:
        return 'satisfied'
    if _parent_has_income_evidence(application, member):
        return 'satisfied'
    if occ:
        return 'need_proof'
    return 'need_status'


def household_status_gaps(application):
    """P2 — income-completeness gaps across the WHOLE household, not just the parents: father,
    mother, AND each ``other_family_members`` earner (guardian/brother/sister). Generalises
    ``parent_income_gaps`` so a working guardian/sibling with no income document is chased for
    proof too (the sponsor counts the full household income). ``[{'member','need'}]``, empty when
    all satisfied. Other-members always carry an occupation → they only ever surface 'proof'."""
    gaps = []
    for member in ('father', 'mother'):
        st = member_income_status(application, member)
        if st == 'need_proof':
            gaps.append({'member': member, 'need': 'proof'})
        elif st == 'need_status':
            gaps.append({'member': member, 'need': 'status'})
    seen = set()
    for m in (getattr(application, 'other_family_members', None) or []):
        if not isinstance(m, dict):
            continue
        role = m.get('role', '')
        if role in ('guardian', 'brother', 'sister') and role not in seen:
            seen.add(role)
            if member_income_status(application, role) == 'need_proof':
                gaps.append({'member': role, 'need': 'proof'})
    return gaps


# ── Household-size consistency (P4 — soft reviewer signal) ───────────────────
# Members a 'deceased' / 'not in contact' occupation marks as NOT part of the living household
# (they're family history, not a per-capita head).
_NOT_IN_HOUSEHOLD = frozenset({'deceased', 'no_contact'})


def _described_household_count(application):
    """A FLOOR on household size from what the applicant explicitly described: the student (+1),
    each parent with an in-household occupation, each ``other_family_members`` entry (excluding
    deceased / not-in-contact), plus the two sibling steppers. Not everyone is itemised, so this
    is a floor, never an exact size."""
    n = 1  # the student themselves
    for member in ('father', 'mother'):
        occ = _member_occupation(application, member)
        if occ and occ not in _NOT_IN_HOUSEHOLD:
            n += 1
    for m in (getattr(application, 'other_family_members', None) or []):
        if isinstance(m, dict) and m.get('role') \
                and (m.get('occupation', '') or '').strip() not in _NOT_IN_HOUSEHOLD:
            n += 1
    n += (getattr(application, 'siblings_in_school', None) or 0)
    n += (getattr(application, 'siblings_in_tertiary', None) or 0)
    return n


def household_size_shortfall(application):
    """P4 soft check: when the people EXPLICITLY described OUTNUMBER the stated household size, the
    per-capita denominator is too small → income is overstated and the student looks LESS needy
    than they are. Returns ``{'described', 'size'}`` for the reviewer to confirm, else None.

    Only the HARMFUL (over-count) direction flags — a household LARGER than the itemised roster is
    common and benign (grandparents, relatives not listed one-by-one), so under-count never fires.
    Advisory only; never a gate."""
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not size:
        return None
    described = _described_household_count(application)
    return {'described': described, 'size': int(size)} if described > size else None


def declared_income_gaps(application):
    """Working members who DECLARED an informal income (Phase 2A) that isn't yet accepted:
    the household has NO valid STR and no supporting income document for them. Each →
    a doc request for an ``income_support_doc`` (D1: flexible evidence). Returns
    ``[{'member': m}, …]`` (empty when every declared amount is backed).

    Salary route only. A valid STR accepts EVERY declared amount at once (no doc needed),
    so it short-circuits to no gaps."""
    if (getattr(application, 'income_route', '') or '').strip() != 'salary':
        return []
    if has_valid_str(application):
        return []
    gaps = []
    for m in effective_working_members(application):
        if declared_amount(application, m) is not None and not has_income_support_doc(application, m):
            gaps.append({'member': m})
    return gaps


# ── Stale income document (reviewer-query automation S2) ─────────────────────
# A salary slip is monthly; reviewers routinely ask "this slip is from December — do you
# have one from the last three months?". Deterministic: if a salary slip is on file but the
# MOST RECENT one is older than ~3 months, ask for a current one. (STR staleness is already
# handled by _str_currency → 'stale'; EPF statements are often annual, so this targets
# salary slips only — exactly the reviewer behaviour.)
_INCOME_DOC_CURRENT_MONTHS = 3


def _salary_period_age_months(f, today):
    """Months between *today* and a salary slip's pay period (from its OCR'd 'period'),
    or None when the period can't be read. Reuses the tolerant month-year parser."""
    ym = _parse_billing_month(f.get('period'))
    if not ym:
        return None
    year, month = ym
    return (today.year - year) * 12 + (today.month - month)


def stale_income_proof(application, today=None):
    """True when a salary slip is on file but NONE is current (every readable one is older
    than ~3 months) — the student should upload a recent slip. False when there is a current
    slip, no salary slip at all, or no slip period could be read (never guess from an
    unreadable date). Pure; tolerant of a test double without `.documents`."""
    if today is None:
        today = datetime.date.today()
    docs = getattr(application, 'documents', None)
    if docs is None:
        return False
    slips = list(docs.filter(doc_type='salary_slip', superseded_at__isnull=True))
    if not slips:
        return False
    ages = []
    for s in slips:
        age = _salary_period_age_months(_doc_fields(s), today)
        if age is not None:
            ages.append(age)
    if not ages:                                   # no readable period → don't guess
        return False
    return min(ages) > _INCOME_DOC_CURRENT_MONTHS  # the freshest slip is still stale


# ── One-live-copy dedup for income proof (owner 2026-07-05) ──────────────────────────────
# The student re-uploads the same/older salary slip or STR screenshot repeatedly; each officer
# re-request lands it in its own slot, so several LIVE copies of one person's proof pile up in the
# cockpit. We only need ONE — the most recent. This collapses a person's copies to a single live
# doc (the newest) and supersedes the rest into the Old / Replaced history. Recency:
#   salary_slip → the pay period (newest month wins); str → the shown year; epf → the statement
#   date (newest wins). A copy whose date can't be read never outranks a dated one; a non-genuine
#   copy never outranks a genuine one; ties fall to the latest upload (id).
_DEDUP_DOC_TYPES = ('salary_slip', 'str', 'epf', 'water_bill', 'electricity_bill')
# Dedup scope: these types are HOUSEHOLD-level (one per household, carry no reliable member tag),
# so they collapse across ALL members; salary_slip / epf are per-member (each earner has their own).
_HOUSEHOLD_WIDE_DEDUP = ('str', 'water_bill', 'electricity_bill')


def _doc_genuine_rank(doc):
    """1 when the doc is NOT flagged non-genuine (genuine / never-scored), 0 when its genuineness is
    suspect / not_<type> / wrong-type / low-confidence. Dedup ranks this FIRST so a non-genuine copy
    (a SARA letter in the STR slot, an EPF filed as a payslip) can NEVER supersede a genuine one — we
    keep the real document even when a fake / wrong-type copy is newer."""
    vf = getattr(doc, 'vision_fields', None)
    st = ''
    if isinstance(vf, dict) and isinstance(vf.get('authenticity'), dict):
        st = (vf['authenticity'].get('status') or '').strip()
    return 1 if st in ('', 'genuine', 'likely_genuine') else 0


def _income_doc_recency(doc):
    """A sortable recency value for a de-dupable income-proof doc (higher = keep), or None when no
    date can be read. salary_slip → (year, month) pay period; str → (year, 0) of the shown year;
    epf → (year, month) of the statement date (year-only if that's all that reads); water/electricity
    bill → (year, month) of the billing period."""
    dt = getattr(doc, 'doc_type', '')
    f = _doc_fields(doc)
    if dt == 'salary_slip':
        return _parse_billing_month(f.get('period'))          # (y, m) or None
    if dt in ('water_bill', 'electricity_bill'):
        return _parse_billing_month(f.get('billing_period'))  # newest billing month wins
    if dt == 'epf':
        ym = _parse_billing_month(f.get('statement_date'))
        if ym:
            return ym
        m = re.search(r'(20\d{2})', str(f.get('year') or f.get('statement_date') or ''))
        return (int(m.group(1)), 0) if m else None
    if dt == 'str':
        m = re.search(r'(20\d{2})', str(f.get('year') or ''))
        return (int(m.group(1)), 0) if m else None
    return None


def _dedup_clean_rank(doc):
    """A quality gate used ONLY for utility bills in the dedup sort (owner 2026-07-08): a genuine,
    readable bill in a KNOWN holder's name (student / declared parent / roster) outranks a
    stranger-named or unreadable one — so a newer wrong-name / unreadable scan can never bury a
    clean, verified bill. Returns 1 for every NON-utility doc, so the salary / STR / EPF ordering is
    unchanged."""
    dt = getattr(doc, 'doc_type', '')
    if dt not in ('water_bill', 'electricity_bill'):
        return 1
    app = getattr(doc, 'application', None)
    f = _doc_fields(doc)
    name = (f.get('name', '') or '').strip()
    if app is not None and _utility_name_unrelated(app, _reconciled_holder_name(app, name)):
        return 0                                              # a stranger's bill — demote
    if not (f.get('address', '') or '').strip():
        return 0                                              # address unreadable
    if _parse_rm(f.get('amount')) is None:
        return 0                                              # amount unreadable
    return 1


def dedupe_income_proof(application, member, doc_type):
    """Collapse LIVE copies of ``doc_type`` to a SINGLE best live doc, superseding the rest into
    Old / Replaced. Ranks by (genuine, has-a-date, recency, id): a genuine copy is never superseded
    by a non-genuine one, then the newest pay month / latest-dated STR wins, then the latest upload.
    Runs across request_codes (an officer re-request no longer leaves a parallel live copy). Retains
    the superseded rows + blobs — never a hard delete. Returns the superseded ids.

    Scope differs by type: salary_slip / epf are PER-MEMBER (each earner has their own), so they
    dedup within ``member``. STR + utility bills are HOUSEHOLD-level (``_HOUSEHOLD_WIDE_DEDUP``) —
    STR pays ONE recipient per household, and utility bills / STR screenshots are re-uploaded under
    an inconsistent (often blank) member tag — so they collapse across ALL members of the
    application, ignoring the passed ``member``. Utility bills additionally rank a clean, readable,
    known-holder bill above a stranger-named / unreadable one (``_dedup_clean_rank``) so a newer bad
    scan never buries a verified bill (owner 2026-07-08)."""
    if doc_type not in _DEDUP_DOC_TYPES:
        return []
    docs = getattr(application, 'documents', None)
    if docs is None:
        return []
    q = docs.filter(doc_type=doc_type, superseded_at__isnull=True)
    if doc_type not in _HOUSEHOLD_WIDE_DEDUP:   # salary/epf: per-member; STR + utility: household-wide
        q = q.filter(household_member=member)
    live = list(q)
    if len(live) < 2:
        return []
    live.sort(key=lambda d: (_doc_genuine_rank(d), _dedup_clean_rank(d),
                             1 if _income_doc_recency(d) else 0,
                             _income_doc_recency(d) or (0, 0), d.id), reverse=True)
    keep, losers = live[0], live[1:]
    # Preserve recipient attribution: if the kept STR copy is blank-tagged but a superseded sibling
    # names the recipient, inherit it so the cockpit still shows e.g. "Mother's STR proof".
    if doc_type == 'str' and not (getattr(keep, 'household_member', '') or '').strip():
        for d in losers:
            m = (getattr(d, 'household_member', '') or '').strip()
            if m:
                keep.household_member = m
                keep.save(update_fields=['household_member'])
                break
    ids = [d.id for d in losers]
    from django.utils import timezone as _tz
    docs.filter(id__in=ids).update(superseded_at=_tz.now(), superseded_by=keep)
    return ids


def sibling_tertiary_funding_unknown(application):
    """True when the student has a sibling in tertiary education — the reviewer's recurring
    "which institution + course is your sibling at (or if working, where), and how is it funded /
    what do they earn?" query (household burden + the not-double-funded picture). A one-line,
    non-sensitive question. (Fires on the count; the bundled copy invites all angles at once — the
    flat Check-2 queue has no branch-on-answer follow-up, owner 2026-07-08.)"""
    return (getattr(application, 'siblings_in_tertiary', None) or 0) > 0


def sibling_school_detail_unknown(application):
    """True when the student has a sibling still in SCHOOL — ask which school and what standard/form
    (household texture the counts alone don't capture). Distinct from the tertiary funding clarify;
    the two fire independently when a household has a sibling in each (the #130 gap: only the tertiary
    sibling was ever asked about)."""
    return (getattr(application, 'siblings_in_school', None) or 0) > 0


# ── Unemployment detail (Phase 2B, P7) ───────────────────────────────────────
def _member_occupation(application, member):
    """The roster occupation CODE for a member: father/mother from their own column;
    guardian/brother/sister from the first matching ``other_family_members`` entry. '' if
    unknown. (Mirrors how family.earning_members reads the roster.)"""
    if member == 'father':
        return (getattr(application, 'father_occupation', '') or '').strip()
    if member == 'mother':
        return (getattr(application, 'mother_occupation', '') or '').strip()
    for m in (getattr(application, 'other_family_members', None) or []):
        if isinstance(m, dict) and m.get('role') == member:
            return (m.get('occupation', '') or '').strip()
    return ''


def unemployed_members(application):
    """Roster members (father/mother/guardian/brother/sister) whose occupation is 'unemployed'."""
    return [m for m in _MEMBER_ORDER if _member_occupation(application, m) == 'unemployed']


def epf_confirms_unemployment(application, member, today=None):
    """True when an EPF statement on file for *member* corroborates unemployment: the employer
    number is all-zeros ('No. Majikan 000000000' — the deterministic signal, same as
    ``_epf_monthly_salary`` → 0.0), OR — best-effort, ONLY when a last-contribution date reads
    — the last contribution is older than ~3 months (no recent employment). Soft; never a gate.
    (``statement_date`` is deliberately NOT used for the age test — it's the issue date, not a
    contribution date, so it would misfire.)"""
    if today is None:
        today = datetime.date.today()
    for epf in _cluster_docs(application, member, 'epf'):
        f = _doc_fields(epf)
        if re.sub(r'\D', '', str(f.get('employer_number') or '')) == '000000000':
            return True
        ym = _parse_billing_month(f.get('last_contribution'))
        if ym and (today.year - ym[0]) * 12 + (today.month - ym[1]) > _INCOME_DOC_CURRENT_MONTHS:
            return True
    return False


def unemployment_status(application, member):
    """The unemployment picture for a roster member, for Check-2 queries + the reviewer:
    ``{unemployed, has_detail, has_epf, epf_corroborated}``. ``unemployed`` = the roster
    occupation is 'unemployed'; ``has_detail`` = a reason or since-when is captured in
    ``income_nonearning``. Soft throughout — never blocks (P3: trust the student)."""
    unemployed = _member_occupation(application, member) == 'unemployed'
    if not unemployed:
        return {'unemployed': False, 'has_detail': False, 'has_epf': False, 'epf_corroborated': False}
    detail = (getattr(application, 'income_nonearning', None) or {}).get(member) or {}
    has_detail = bool(isinstance(detail, dict) and (detail.get('reason') or detail.get('since')))
    return {
        'unemployed': True,
        'has_detail': has_detail,
        'has_epf': _cluster_docs(application, member, 'epf').exists(),
        'epf_corroborated': epf_confirms_unemployment(application, member),
    }


def unemployment_detail_gap(application):
    """True when a roster member is 'unemployed' but no reason/since is captured for them —
    the Check-2 clarify ("tell us why, and since when")."""
    return any(not unemployment_status(application, m)['has_detail']
               for m in unemployed_members(application))


def unemployment_epf_members(application):
    """'unemployed' members with no EPF statement on file — the per-member (soft, optional) Check-2
    doc-request to upload it for corroboration. Per-member so the request is TAGGED to that person
    (an EPF belongs to a specific member; a memberless request lands blank-tagged)."""
    return [m for m in unemployed_members(application)
            if not _cluster_docs(application, m, 'epf').exists()]


def unemployment_epf_gap(application):
    """True when any 'unemployed' member has no EPF on file (boolean form of
    ``unemployment_epf_members``)."""
    return bool(unemployment_epf_members(application))


def unemployment_corroborated_members(application):
    """Unemployed members whose EPF corroborates the unemployment — soft reviewer evidence."""
    return [m for m in unemployed_members(application) if epf_confirms_unemployment(application, m)]


# ── V4: promote the nine recurring HUMAN ask-themes into model queries (audit §E;
#      owner decision 2 + conservative raise-conditions confirmed 2026-07-03). Each is soft:
#      a doc-request (uncapped) or a one-line clarify (capped), never a gate. Conditions are
#      deliberately CONSERVATIVE (under-ask) — tune against the prod cohort post-deploy. ─────
_NON_EARNING_OCC = frozenset({'unemployed', 'homemaker', 'deceased', 'no_contact', ''})


def _docs_or_none(application):
    return getattr(application, 'documents', None)


def _has_read_doc(docs, doc_type):
    """A doc of this type that field-extracted OK (``student_verdict='ok'``) is on file — so a
    blank/wrong upload doesn't clear a V4 academic request (consistency with V1's read-requirement:
    a doc must READ to count, not merely be present)."""
    for d in docs.filter(doc_type=doc_type, superseded_at__isnull=True):
        if (getattr(d, 'vision_fields', None) or {}).get('student_verdict', '') == 'ok':
            return True
    return False


def school_leaving_cert_gap(application):
    """A post-SPM (SPM-track) applicant whose academic record can't be read from a results slip →
    ask for a school-leaving certificate (surat berhenti sekolah / testimonial) to corroborate.
    CONSERVATIVE: fires ONLY when there's no results slip on file (not for every post-SPM
    applicant). Clears when a leaving cert that READ OR a results slip is present."""
    prof = getattr(application, 'profile', None)
    if (getattr(prof, 'exam_type', 'spm') or 'spm') != 'spm':
        return False
    docs = _docs_or_none(application)
    if docs is None or _has_read_doc(docs, 'school_leaving_cert'):
        return False
    return not docs.filter(doc_type='results_slip', superseded_at__isnull=True).exists()


# The post-SPM pathways that run MULTI-YEAR (owner 2026-07-08): a student who joined one of these
# in a PREVIOUS year is a continuing student and owes their latest semester result (CGPA).
# Matriculation and Asasi are 10-MONTH programmes — a past intake there means COMPLETED, not
# continuing, so no semester-result request applies.
_MULTI_YEAR_PATHWAYS = frozenset({'stpm', 'pismp', 'poly', 'university'})


def semester_result_gap(application):
    """A CONTINUING student with no current-semester result slip that READ on file → ask for the
    latest CGPA. Continuing means (owner 2026-07-08, post-SPM focus):
      * the chosen pathway is MULTI-YEAR (STPM / PISMP / Poly / UA diploma — `_MULTI_YEAR_PATHWAYS`)
        AND the offer's normalised ``reporting_date`` is a year OLDER than the cohort (the same
        past-intake signal the continuing-STPM award rule uses); Matric/Asasi (10-month) excluded —
        a past intake there = completed, a different conversation; or
      * the legacy arm: the student applied with STPM credentials (``exam_type='stpm'`` — in Form 6
        by definition; the programme currently processes post-SPM applicants, so this rarely fires).
    Clears when a ``semester_result`` field-extracts."""
    docs = _docs_or_none(application)
    if docs is None or _has_read_doc(docs, 'semester_result'):
        return False
    prof = getattr(application, 'profile', None)
    if (getattr(prof, 'exam_type', '') or '') == 'stpm':
        return True
    pathway = (getattr(application, 'chosen_pathway', '') or '').strip().lower()
    if pathway not in _MULTI_YEAR_PATHWAYS:
        return False
    rd = getattr(application, 'reporting_date', None)
    cy = getattr(getattr(application, 'cohort', None), 'year', None)
    return bool(rd and cy and rd.year < cy)


def employed_epf_members(application):
    """EMPLOYED parents with a salary slip but no EPF on file → the per-member OPTIONAL request for
    the EPF as standard corroboration (mirrors ``unemployment_epf_members``). The payslip gate keeps
    it to genuinely-employed parents. Per-member so the request is TAGGED to that person (an EPF
    belongs to a specific member; a memberless request lands blank-tagged). Soft; never a gate."""
    docs = _docs_or_none(application)
    if docs is None:
        return []
    out = []
    for member in ('father', 'mother'):
        occ = _member_occupation(application, member)
        if occ and occ not in _NON_EARNING_OCC and not member_is_informal(application, member):
            has_slip = docs.filter(doc_type='salary_slip', household_member__in=[member, ''],
                                   superseded_at__isnull=True).exists()
            has_epf = docs.filter(doc_type='epf', household_member__in=[member, ''],
                                  superseded_at__isnull=True).exists()
            if has_slip and not has_epf:
                out.append(member)
    return out


def employed_epf_gap(application):
    """True when any employed parent has a salary slip but no EPF (boolean form of
    ``employed_epf_members``)."""
    return bool(employed_epf_members(application))


def utility_bill_gap(application):
    """DEPRECATED (owner 2026-07-08) — superseded by the per-bill ``utility_bill_recheck``. NEITHER
    a water nor an electricity bill on file → ask for one. Kept only for callers that still probe
    the either-or state; Check-2 now uses the per-bill recheck below."""
    docs = _docs_or_none(application)
    return docs is not None and not docs.filter(
        doc_type__in=('water_bill', 'electricity_bill'), superseded_at__isnull=True).exists()


def _bill_needs_upload(application, doc_type, today):
    """Why THIS bill type needs a (re)upload, or '' when the bill on file is usable. Reasons
    (owner 2026-07-08): 'missing' (none on file), 'stale' (older than ~3 months OR no readable
    date — we can't confirm it's current), 'address_unreadable' (no address text read),
    'amount_unreadable' (the charge couldn't be parsed). A HARD address MISMATCH is deliberately
    NOT here — that's the separate ``utility_address_mismatch`` 'whose address?' clarify, not a
    re-upload."""
    doc = _latest_doc(application, doc_type)
    if doc is None:
        return 'missing'
    facts = utility_check(doc, today)
    if not facts:
        return 'missing'
    if facts.get('current_status') in ('stale', 'unknown'):   # >3mo OR undated → not confirmably current
        return 'stale'
    if not (facts.get('address') or '').strip():
        return 'address_unreadable'
    if _parse_rm(facts.get('monthly_bill')) is None:
        return 'amount_unreadable'
    return ''


def utility_bill_recheck(application, today=None):
    """Per-bill re-upload map (owner 2026-07-08): ``{'water_bill'|'electricity_bill': reason}`` for
    each bill that is missing / stale / undated / unreadable. Empty when BOTH bills are on file,
    current, and readable — the 'both bills, current, clear' requirement enforced in logic, not just
    painted on the row. Drives the two per-bill Check-2 re-upload requests; a fresh clean upload
    supersedes the old one and clears its request."""
    if today is None:
        today = datetime.date.today()
    docs = _docs_or_none(application)
    if docs is None:
        return {}
    out = {}
    for dt in ('water_bill', 'electricity_bill'):
        reason = _bill_needs_upload(application, dt, today)
        if reason:
            out[dt] = reason
    return out


def deceased_parent_members(application):
    """Roster members marked 'deceased' — the officer's recurring 'when / what happened' texture
    query. One clarify covers all such members."""
    return [m for m in _MEMBER_ORDER if _member_occupation(application, m) == 'deceased']


def deceased_parent_detail_gap(application):
    return bool(deceased_parent_members(application))


def informal_work_detail_gap(application):
    """A member has a DECLARED informal wage (``income_declared``) → ask the own-account-vs-employer
    + average-monthly-wage texture officers ask by hand. One clarify covers all such members.
    (Distinct from ``unemployment_detail_gap`` — that's for the UNEMPLOYED.)"""
    raw = getattr(application, 'income_declared', None)
    if not isinstance(raw, dict):
        return False
    return any(declared_amount(application, m) is not None for m in _MEMBER_ORDER)


# ── Informal / self-employed earners (owner 2026-07-08, the #130 fisherman dead-end) ─────────
# A fisherman / hawker / e-hailing rider etc. rarely has a payslip and does NOT contribute to EPF,
# so demanding a salary slip / EPF from them is a dead-end: the request sits open against the SLA
# clock and the student uploads an irrelevant doc to clear it. Instead we ASK FIRST — a one-line
# clarify ("does he get a payslip or contribute to EPF? if not, roughly what does he earn a month?")
# — and route real proof through the flexible income-support-doc path (declared_income_gaps).
def member_is_informal(application, member):
    """True when *member*'s roster occupation is in the self-employed / informal block
    (``family.INFORMAL_OCC``) — the earners we must NOT chase for a payslip / EPF."""
    from .family import INFORMAL_OCC
    return _member_occupation(application, member) in INFORMAL_OCC


def informal_income_members(application):
    """Informal earners (father/mother/guardian/brother/sister) with NO income document on file —
    the ones a formal salary-slip / EPF demand would dead-end on. Household-wide (mirrors how
    ``household_status_gaps`` walks parents + other_family_members)."""
    out = []
    for member in _MEMBER_ORDER:
        if member_is_informal(application, member) and not _parent_has_income_evidence(application, member):
            out.append(member)
    return out


def informal_income_detail_gap(application):
    """True when an informal earner has no income document AND no declared amount yet → the ASK-FIRST
    clarify. Carved so it does NOT overlap ``informal_work_detail_gap`` (which fires once an amount is
    DECLARED): here we still need the rough monthly figure + whether any payslip/EPF exists at all.
    One clarify covers every such member."""
    return any(declared_amount(application, m) is None for m in informal_income_members(application))


def _member_occupation_label(application, member):
    """The human occupation LABEL for a roster member (the declared job, e.g. 'Driver (taxi / bus /
    lorry)'), honouring the free-text 'other' when the code is 'other'. '' when unknown."""
    from .family import occupation_label
    if member == 'father':
        return occupation_label(_member_occupation(application, member),
                                getattr(application, 'father_occupation_other', '') or '')
    if member == 'mother':
        return occupation_label(_member_occupation(application, member),
                                getattr(application, 'mother_occupation_other', '') or '')
    for m in (getattr(application, 'other_family_members', None) or []):
        if isinstance(m, dict) and m.get('role') == member:
            return occupation_label((m.get('occupation', '') or '').strip(),
                                    (m.get('occupation_other', '') or '').strip())
    return ''


def informal_income_context(application):
    """Params for the ``informal_income_detail`` clarify so its copy NAMES the members the student
    ALREADY declared (owner 2026-07-08 — 'the information is already in My Family'): ``members`` is
    the list of informal-earner member codes (the FE localises them to relation labels), ``jobs`` is
    their declared occupation label(s) joined for display. Only the members whose amount is still
    unknown (the ones the gap is actually about). Empty ``members`` when the gap isn't live."""
    members = [m for m in informal_income_members(application) if declared_amount(application, m) is None]
    jobs = [lbl for lbl in (_member_occupation_label(application, m) for m in members) if lbl]
    return {'members': members, 'jobs': '; '.join(jobs)}


_ROSTER_UNDERCOUNT_MARGIN = 2   # conservative: only a gap of ≥2 unlisted people (tune post-deploy)


def household_roster_undercount(application):
    """The MISSING direction of 2C: the stated household size is LARGER than the people explicitly
    described → ask who else is in the household (the officers' '6 members, 5 listed' query).
    Opposite of ``household_size_shortfall`` (the over-count). A gap of ≥2 (an under-count of one
    is common/benign — grandparents, an un-itemised relative). Returns ``{'described','size'}`` or
    None. Advisory only."""
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not size:
        return None
    described = _described_household_count(application)
    return ({'described': described, 'size': int(size)}
            if int(size) - described >= _ROSTER_UNDERCOUNT_MARGIN else None)


def other_scholarships_followup_gap(application):
    """The student listed other scholarships at apply → follow up on their status (the
    not-double-funded picture). Fires when ``other_scholarships`` is non-empty."""
    raw = getattr(application, 'other_scholarships', None)
    if isinstance(raw, (list, tuple)):
        return len(raw) > 0
    if isinstance(raw, str):
        return bool(raw.strip())
    return bool(raw)


def high_utility_expense_gap(application):
    """Owner decision 2 (V4): promote ``utility_reasonable``'s 'high' officer signal to a student
    clarify — a high per-capita utility spend, ask them to explain it (a possible undeclared income,
    or a legitimate reason). Fires only when BOTH bills are on file AND per-capita is above the high
    floor (so it can't fire on a partial/unknown read)."""
    return utility_reasonable(application).get('status') == 'high'


def high_utility_expense_context(application):
    """Params for the high-usage clarify (owner 2026-07-08 — state the amount, ask point-blank):
    the combined monthly bill total (RM), the declared household income (RM), and whether the
    household holds a VALID STR (so the query references STR status rather than an income figure).
    Returns None when there is no high signal (the caller then raises nothing)."""
    if utility_reasonable(application).get('status') != 'high':
        return None
    amount = utility_monthly_total(application)
    income = getattr(getattr(application, 'profile', None), 'household_income', None)
    return {
        'amount': int(round(amount)) if amount is not None else None,
        'income': int(round(income)) if income else None,
        'on_str': has_valid_str(application),
    }
