"""The birth-certificate, guardianship and income-support document checks.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

from ..vision import nric_close
from .buckets import _combine_relationship, _name_bucket, _nric_bucket
from .identity_checks import _member_ic_doc, chain_verified_earner
from .relationships import father_name_from_ic
from .salary_figures import _doc_fields


_REL_DOC_READ_FIELDS = {
    'birth_certificate': ('bc_child_name', 'bc_child_nric', 'bc_mother_name',
                          'bc_mother_nric', 'bc_father_name', 'bc_father_nric'),
    'guardianship_letter': ('guardian_name', 'guardian_nric', 'ward_name'),
}


def relationship_doc_unreadable(doc) -> bool:
    """True when a relationship document is ON FILE but yielded NOTHING to check.

    ⚠ UNREADABLE IS NOT CLEAN. Every row of such a document buckets to ``no_ref``, which reads
    as "nothing disagrees" — so a certificate we could not read scored exactly like one that
    checked out, and nobody was asked for a better copy (BrightPath #23, owner: *"today
    'we could not read it' scores the same as 'it checked out'"*).

    The rule is DOCUMENT-level, never row-level: a blank father row on a certificate that
    names no father is a real absence, not a failed read. Only when EVERY field we know how
    to read is blank did the document tell us nothing. A wrong-type document is a separate,
    already-handled state (``verdict_engine._doc_wrong_type``) — it is a different message to
    the student ("that is not a birth certificate") from "we could not read yours".
    """
    fields = _REL_DOC_READ_FIELDS.get(getattr(doc, 'doc_type', ''))
    if doc is None or not fields:
        return False
    f = _doc_fields(doc)
    return not any((f.get(k) or '').strip() for k in fields)


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
        # Nothing read at all → the officer must see ONE amber, not three greys that look like
        # an absent optional document (#23). The three row statuses stay as they are; the
        # surface decides what to draw.
        'unreadable': relationship_doc_unreadable(doc),
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
        'unreadable': relationship_doc_unreadable(doc),   # nothing read ≠ nothing wrong (#23)
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
