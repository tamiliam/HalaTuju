"""H6: a student may replace a sent / done document up to three times.

A document is its slot: (application, doc type, household member, request code), the same slot the
upload door supersedes into. The count lives in the database (`ApplicantDocument.replace_count`), so
it survives sessions and devices. A replace's new row carries the slot's highest count + 1; counting
the highest across ALL copies (superseded ones too) means a replace the read turned down still
counts, so a student cannot reset it by being refused.

Only an upload sent with `replace` is counted or capped. A re-upload of a returned document
("Needs you") is the normal retry and stays unlimited. The documents lock is checked first, in the
view, exactly as for any upload.
"""
from django.db.models import Max
from rest_framework import status
from rest_framework.response import Response

from .models import ApplicantDocument

REPLACE_LIMIT = 3
REPLACE_LIMIT_REACHED = 'replace_limit_reached'
_MESSAGE = ('You have already replaced this document 3 times. If it is still wrong, '
            'your reviewer will ask you for what is needed.')


def replaces_used(application_id, doc_type, members, request_code):
    """Replaces the slot has used so far (0 when none)."""
    top = ApplicantDocument.objects.filter(
        application_id=application_id, doc_type=doc_type, household_member__in=members,
        request_code=request_code).aggregate(m=Max('replace_count'))['m']
    return top or 0


def replace_refusal(used):
    """A 409 Response if the slot has used all its replaces, else None."""
    if used < REPLACE_LIMIT:
        return None
    return Response({'error': REPLACE_LIMIT_REACHED, 'code': REPLACE_LIMIT_REACHED,
                     'message': _MESSAGE, 'limit': REPLACE_LIMIT}, status=status.HTTP_409_CONFLICT)
