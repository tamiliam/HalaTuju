"""Who the earner is to the student, from NAMES alone: the IC patronymic, the
birth-certificate and guardianship links, the working-member roster, and the relationship
verdict for one member. Nothing here reads a document.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

import re

from ..document_snapshot import latest_doc, tagged_members
from ..vision import relationship_name_match as name_match


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


def student_name_for_link(application) -> str:
    """The student's name to use for the patronymic-based relationship checks.

    Students often TYPE their name without the connector ("THIVYADHAARSHINI THANGARAJAN")
    while their own IC prints it in full ("THIVYADHAARSHINI A/P THANGARAJAN") — and the
    typed form alone loses the deterministic father link, wrongly demoting a
    dispositive-STR household to Unsure (#88). So: prefer the typed profile name, but when
    it carries NO patronymic and the student's own VERIFIED IC read does, use the IC's name
    — it is the document form of the SAME identity (the Identity check anchors profile↔IC;
    we additionally require the two names not to mismatch), so deriving the father from it
    is grounded, never a guess. Falls back to the profile name in every other case."""
    profile_name = (getattr(getattr(application, 'profile', None), 'name', '') or '').strip()
    if father_name_from_ic(profile_name):
        return profile_name
    docs = getattr(application, 'documents', None)
    if docs is None:
        return profile_name
    ic = latest_doc(application, 'ic')
    ic_name = (getattr(ic, 'vision_name', '') or '').strip() if ic else ''
    if (ic_name and father_name_from_ic(ic_name)
            and profile_name and name_match(ic_name, profile_name) != 'mismatch'):
        return ic_name
    return profile_name


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


def effective_working_members(application, any_route: bool = False) -> list:
    """The salary-route working members, with a fallback for the prefill-not-saved gap.

    ``any_route=True`` lifts the salary-route restriction and reconstructs the earners on EITHER
    route — needed because income is satisfied by STR **or** salary (owner 2026-07-22), so a
    student who declared the STR route can still have fully documented an earner while never
    touching the salary checkboxes. OPT-IN on purpose: the default keeps the historical
    salary-route-only behaviour, so a caller that does not ask for the wider reading cannot have
    its answer moved. The PROFILE generator still takes the default. The VERDICT no longer always
    does: `_verdict_income` passes ``any_route=True`` on the one path where a household has no STR
    letter at all but a complete salary cluster (2026-08-01, str-proof-spec.md §6 rule 2) — such a
    student never ticked a salary checkbox, so the default reading would find no members and
    report "no earner declared" about a household that documented one.

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
    if not any_route and (getattr(application, 'income_route', '') or '').strip() != 'salary':
        return []
    # (1) Members the uploaded income docs are tagged to — what the student actually did.
    found: set = set()
    docs = getattr(application, 'documents', None)
    if docs is not None:
        try:
            tagged = tagged_members(application, ('parent_ic', 'salary_slip', 'epf'))
            found.update(m for m in tagged if m in _MEMBER_ORDER)
        except (AttributeError, TypeError):
            pass
    # (2) Else the declared earners from the family roster.
    if not found:
        try:
            from ..family import earning_members
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
        bc = latest_doc(application, 'birth_certificate')
        vf = (getattr(bc, 'vision_fields', None) if bc else None) or {}
        f = vf.get('fields', {}) if isinstance(vf, dict) else {}
        if isinstance(f, dict):
            bc_child = f.get('bc_child_name', '')
            bc_mother = f.get('bc_mother_name', '')
            bc_father = f.get('bc_father_name', '')
    elif member == 'guardian':
        g = latest_doc(application, 'guardianship_letter')
        letter_name = (getattr(g, 'vision_name', '') or '') if g else ''
    return bc_child, bc_mother, bc_father, letter_name
