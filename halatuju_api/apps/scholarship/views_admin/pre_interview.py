"""Request #75: POST .../<pk>/reject-before-interview/ {reason, comments}.

The door onto `services/pre_interview.reject_before_interview`. Its own module because
`applications.py` sits at the 600-line standard; re-exported from `views_admin/__init__.py`.
"""
from rest_framework import status
from rest_framework.response import Response

from ..services.pre_interview import reject_before_interview
from .applications import _detail_payload
from .base import _AdminBase

#: The refusals, worded once in English for the API. The cockpit shows its own words for each
#: code in en / ms / ta (`admin.scholarship.preInterview.error.<code>`).
_REFUSALS = {
    'bad_status': 'Only a student at Awaiting review can be rejected before interview.',
    'has_reviewer': 'This student has a reviewer now, so they cannot be rejected before interview.',
    'reason_required': 'Choose the main reason.',
    'comments_required': 'Say why you are rejecting. The note stays on the file for your team.',
    'comments_too_long': 'The note can be 2,000 characters at most.',
}


class AdminRejectBeforeInterviewView(_AdminBase):
    """Gate: the organisation fence and the case write gate (`_require_app_write`: a case in
    another organisation is a 404), then the `qc` permission key, which super, org admins and QC
    hold and a reviewer never does (403). No new permission (the analysis said so)."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        if not admin.has_perm('qc'):
            return self._deny_role()
        reason = request.data.get('reason')
        comments = request.data.get('comments')
        try:
            reject_before_interview(app, admin, reason if isinstance(reason, str) else '',
                                    comments if isinstance(comments, str) else '')
        except ValueError as e:
            code = str(e)
            return Response({'error': _REFUSALS.get(code, _REFUSALS['bad_status']), 'code': code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(_detail_payload(app, admin))
