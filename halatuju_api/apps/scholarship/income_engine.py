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
    ('birth_certificate' / 'guardianship_letter'), or '' for a father (derived)."""
    return _RELATIONSHIP_DOC.get(earner or '', '')


# ── The requirement engine ───────────────────────────────────────────────────

def income_requirements(application) -> dict:
    """Given the wizard answers on *application*, the documents the family needs.

    Returns ``{compulsory: [doc_type], optional: [doc_type]}``. Always: the earner
    IC + the relationship proof. Then the income evidence per route/work-status.
    Optional docs add credibility but never block. Blank answers (wizard not yet
    walked) → just the earner IC compulsory; the verdict layer flags the gap."""
    route = (getattr(application, 'income_route', '') or '').strip()
    earner = (getattr(application, 'income_earner', '') or '').strip()
    work = (getattr(application, 'earner_work_status', '') or '').strip()

    compulsory = ['parent_ic']                 # the earner's IC — always
    rel_doc = relationship_doc_for(earner)
    if rel_doc:
        compulsory.append(rel_doc)             # mother→BC, guardian→letter; father→none

    optional: list[str] = []
    if route == 'str':
        compulsory.append('str')
        optional += ['water_bill', 'electricity_bill', 'salary_slip', 'epf']
    elif route == 'salary':
        if work == 'payslip':
            compulsory += ['salary_slip', 'epf']
            optional += ['water_bill', 'electricity_bill']
        elif work == 'not_working':
            compulsory.append('epf')
            optional += ['water_bill', 'electricity_bill']
        elif work == 'informal':
            # No payslip/EPF to demand — the bills tie the earner to the household;
            # a person judges the rest (never blocked).
            compulsory += ['water_bill', 'electricity_bill']
            optional.append('epf')
        else:                                  # work status not chosen yet
            optional += ['salary_slip', 'epf', 'water_bill', 'electricity_bill']
    # route blank → wizard not started; only the earner IC stands. Verdict flags it.

    # De-dup while preserving order; a doc is never both compulsory and optional.
    seen = set(compulsory)
    optional = [d for d in optional if not (d in seen or seen.add(d))]
    return {'compulsory': compulsory, 'optional': optional}
