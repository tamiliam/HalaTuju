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

import re

from .vision import name_match


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


def mother_relationship(bc_child_name: str, bc_mother_name: str,
                        student_name: str, earner_ic_name: str) -> str:
    """The Birth Certificate ties the earner (mother) to the student: its child
    must be the student AND its mother must be the earner IC. Either side disjoint
    → mismatch; both agree → match; not enough read yet → pending."""
    if not (bc_child_name or '').strip() and not (bc_mother_name or '').strip():
        return 'pending'                       # BC not uploaded / not read
    child_ok = (name_match(bc_child_name, student_name) != 'mismatch'
                if bc_child_name and student_name else None)
    mother_ok = (name_match(bc_mother_name, earner_ic_name) != 'mismatch'
                 if bc_mother_name and earner_ic_name else None)
    if child_ok is False or mother_ok is False:
        return 'mismatch'
    if child_ok and mother_ok:
        return 'match'
    return 'pending'


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


def member_relationship_status(member: str, student_name: str, member_ic_name: str,
                               bc_child_name: str = '', bc_mother_name: str = '',
                               letter_name: str = '') -> str:
    """The relationship verdict for one working member — routes to the right check.
    father/brother/sister → father_relationship (shared patronymic); mother → birth cert;
    guardian → guardianship letter. 'match' | 'mismatch' | 'unknown' | 'pending'."""
    if member in _PATRONYMIC_MEMBERS:
        return father_relationship(student_name, member_ic_name)
    if member == 'mother':
        return mother_relationship(bc_child_name, bc_mother_name, student_name, member_ic_name)
    if member == 'guardian':
        return guardian_relationship(letter_name, member_ic_name)
    return 'unknown'


def _relationship_inputs(application, member, member_ic_name):
    """Pull the relationship-proof inputs for one member from the application's
    documents (birth cert for a mother, guardianship letter for a guardian)."""
    bc_child = bc_mother = letter_name = ''
    if member == 'mother':
        bc = (application.documents.filter(doc_type='birth_certificate')
              .order_by('-uploaded_at').first())
        vf = (getattr(bc, 'vision_fields', None) if bc else None) or {}
        f = vf.get('fields', {}) if isinstance(vf, dict) else {}
        if isinstance(f, dict):
            bc_child, bc_mother = f.get('bc_child_name', ''), f.get('bc_mother_name', '')
    elif member == 'guardian':
        g = (application.documents.filter(doc_type='guardianship_letter')
             .order_by('-uploaded_at').first())
        letter_name = (getattr(g, 'vision_name', '') or '') if g else ''
    return bc_child, bc_mother, letter_name


def student_income_ic_check(doc):
    """For an income earner's IC (``parent_ic``): the OCR'd IC No / Name / Address +
    the RELATIONSHIP verdict (does this earner link to the student's family) — NOT an
    identity match against the student (the NRIC is the earner's, not the student's).
    The member is the document's ``household_member`` (salary route) or the
    application's ``income_earner`` (STR route). Returns
    ``{nric, name, address, member, name_status, readable}`` or None for non-parent_ic.

    ``name_status``: 'match' | 'mismatch' | 'unknown' (no patronymic / no member) |
    'pending' (not read / relationship doc not uploaded)."""
    if getattr(doc, 'doc_type', '') != 'parent_ic':
        return None
    app = doc.application
    member = ((getattr(doc, 'household_member', '') or '').strip()
              or (getattr(app, 'income_earner', '') or '').strip())
    name = (getattr(doc, 'vision_name', '') or '').strip()
    readable = bool(getattr(doc, 'vision_run_at', None)) and not getattr(doc, 'vision_error', '') and bool(name)

    name_status = 'pending'
    if not member or not name:
        name_status = 'unknown' if (readable and not member) else 'pending'
    else:
        student_name = getattr(getattr(app, 'profile', None), 'name', '') or ''
        bc_child, bc_mother, letter_name = _relationship_inputs(app, member, name)
        name_status = member_relationship_status(member, student_name, name,
                                                 bc_child, bc_mother, letter_name)
    return {
        'nric': getattr(doc, 'vision_nric', '') or '',
        'name': getattr(doc, 'vision_name', '') or '',
        'address': getattr(doc, 'vision_address', '') or '',
        'member': member,
        'name_status': name_status,
        'readable': readable,
    }


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
        compulsory = [('parent_ic', m)]
        rel = relationship_doc_for(m)
        if rel:
            compulsory.append((rel, ''))            # birth cert / letter — single, untagged
        optional = [('salary_slip', m), ('epf', m)]
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
        members = salary_member_blocks(working_members(application))
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
