"""The documents stage lock: once querying is locked the student can no longer add or remove documents.

`services.querying_locked` is the one definition of "locked" (the interview concluded, or any later
stage; a reopened decision unlocks again). The student's document upload (sign + record) and delete
refuse from there with `documents_locked`. Reviewer / admin document paths live in `views_admin` and
do not pass through here.

Three uploads stay open after the lock because the case itself asks for them then:
* the post-award bank statement (`BANK_CAPTURE_STATES`, awarded / active);
* the funded student's semester results (the in-programme upload: `semester_result`, awarded / active /
  maintenance);
* the two higher-results asks, which Check 2 may raise while interviewing / interviewed
  (`higher_owed.LATE_ASK_STATUSES`, owner 2026-11-07).
"""
from rest_framework import status
from rest_framework.response import Response

from ..higher_owed import ASK_SPECS, LATE_ASK_STATUSES
from ..resolution_postaward import BANK_CAPTURE_STATES
from ..services import querying_locked
from .common import _FUNDED_STATES

DOCUMENTS_LOCKED = 'documents_locked'
_MESSAGE = ('Your interview stage has started, so documents can no longer be added or removed here. '
            'If something is missing, your reviewer will ask you for it.')
_LATE_DOC_TYPES = frozenset(spec['doc_type'] for spec in ASK_SPECS.values())


def doc_type_open(app, doc_type):
    """True if the student may add / remove `doc_type` documents on `app` right now."""
    if not querying_locked(app):
        return True
    if doc_type == 'bank_statement' and app.status in BANK_CAPTURE_STATES:
        return True
    if doc_type == 'semester_result' and app.status in _FUNDED_STATES:
        return True
    return doc_type in _LATE_DOC_TYPES and app.status in LATE_ASK_STATUSES


def lock_state(app):
    """What the student's pages need to know, served with the document list: `locked` (querying is
    locked) and `open_doc_types` (the exempt types that stay open while locked; empty when unlocked,
    because then everything is open)."""
    if app is None or not querying_locked(app):
        return {'locked': False, 'open_doc_types': []}
    open_types = sorted(t for t in {'bank_statement', 'semester_result'} | _LATE_DOC_TYPES
                        if doc_type_open(app, t))
    return {'locked': True, 'open_doc_types': open_types}


def documents_locked_refusal(app, doc_type):
    """A 409 Response if the student may not change `doc_type` documents on `app` now, else None."""
    if doc_type_open(app, doc_type):
        return None
    return Response({'error': DOCUMENTS_LOCKED, 'code': DOCUMENTS_LOCKED, 'message': _MESSAGE},
                    status=status.HTTP_409_CONFLICT)
