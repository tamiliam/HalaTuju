"""H6: a student may replace a sent / done document up to three times.

A document is its slot: (application, doc type, household member, request code), the same slot the
upload door supersedes into. The count lives in the database (`ApplicantDocument.replace_count`), so
it survives sessions and devices.

THE RULE (the server decides; the client's `replace` flag changes nothing). Every student upload into
a slot that already has a LIVE copy is a replace, and it counts, UNLESS the live copy is one the
student must fix (`must_fix`): returned by a reviewer (rejected), a problem verdict from the read, or
authenticity failed (`not_<type>`). Fixing a returned document is the normal retry: never counted,
never capped. A live copy still being read, or one that read fine, counts - otherwise rapid
re-uploads would skip the cap.

A counted upload's new row carries the slot's highest count + 1; an exempt one carries the highest
unchanged. The highest is taken across ALL copies (superseded ones too), so a replace the read turned
down still counts and a refusal cannot reset it. The list serves that same highest (`slot_max`), not
the live row's own value. The documents lock is checked first, in the view, exactly as for any upload.
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


_OK_VERDICTS = ('', 'ok', 'review_manually')


def must_fix(live):
    """True when the live copy is one the student has to fix, so a re-upload is a retry, not a replace."""
    if live.verification_status == 'rejected':
        return True
    vf = live.vision_fields if isinstance(live.vision_fields, dict) else {}
    if (vf.get('student_verdict') or '') not in _OK_VERDICTS:
        return True
    auth = vf.get('authenticity')
    if isinstance(auth, dict) and auth.get('status'):
        from .genuineness.bands import shown_status
        return shown_status(auth.get('status'), live.doc_type, auth.get('doc_seen', '')).startswith('not_')
    return False


def slot_max_annotation():
    """Queryset annotation `slot_max`: the slot's highest replace_count over every copy, in the same query."""
    from django.db.models import OuterRef, Subquery
    top = (ApplicantDocument.objects
           .filter(application_id=OuterRef('application_id'), doc_type=OuterRef('doc_type'),
                   household_member=OuterRef('household_member'), request_code=OuterRef('request_code'))
           .order_by().values('application_id', 'doc_type', 'household_member', 'request_code')
           .annotate(m=Max('replace_count')).values('m'))
    return Subquery(top)


def replace_refusal(used):
    """A 409 Response if the slot has used all its replaces, else None."""
    if used < REPLACE_LIMIT:
        return None
    return Response({'error': REPLACE_LIMIT_REACHED, 'code': REPLACE_LIMIT_REACHED,
                     'message': _MESSAGE, 'limit': REPLACE_LIMIT}, status=status.HTTP_409_CONFLICT)
