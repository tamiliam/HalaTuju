"""Programme → Announcements (student maintenance Sprint 8, 2026-11-01): an organisation's news to its
scholars. Part of the `views_admin` package; re-exported from `views_admin/__init__.py`. The rules live in
`apps/scholarship/announcements.py`; THIS module is the fence.

WHO (owner ruling, 2026-11-01): `announcements.may_post` — a super, an organisation admin, an admin. Every
other role (reviewer, QC, finance, partner, source, mentor) is refused 403, as on the other programme admin
pages. WHICH ORGANISATION: the gift named by `?programme=` (resolved INSIDE the caller's organisation —
another tenant's code is 404), else the caller's own; a super with no organisation must name a gift
(400 `programme_required`). One announcement outside the caller's organisation is 404, never 403.
One class per url shape. Each write leaves an AUDIT line; nothing is written on a scholar's file.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from .. import announcements as svc
from ..models import Announcement
from .base import _AdminBase
from .letters import _data

logger = logging.getLogger('apps.scholarship.views_admin')

_CONFLICT = {'withdrawn', 'published_locked', 'not_published', 'withdraw_instead'}


def _announcement_refusal(e):
    return Response({'error': e.code, 'code': e.code},
                    status=status.HTTP_409_CONFLICT if e.code in _CONFLICT else status.HTTP_400_BAD_REQUEST)


def _not_found():
    return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


class _AnnouncementsBase(_AdminBase):
    def _poster(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not svc.may_post(admin):
            return None, self._deny_role()
        return admin, None

    def _organisation(self, request, admin):
        programme, err = self._gift_narrowing(request, admin)
        if err:
            return None, err
        if programme is not None:
            return programme.organisation, None
        if admin.owning_organisation_id:
            return admin.owning_organisation, None
        return None, Response({'error': 'programme_required', 'code': 'programme_required'},
                              status=status.HTTP_400_BAD_REQUEST)

    def _announcement(self, request, pk):
        """`(admin, announcement, error)` — the row IFF it is the caller's organisation's (a super: any)."""
        admin, err = self._poster(request)
        if err:
            return None, None, err
        qs = Announcement.objects.select_related('organisation', 'programme').filter(pk=pk)
        if not admin.is_super:
            qs = qs.filter(organisation_id=admin.owning_organisation_id) if admin.owning_organisation_id else qs.none()
        a = qs.first()
        return (admin, a, None) if a is not None else (None, None, _not_found())

    def _row(self, a):
        return svc.staff_rows(a.organisation, only_id=a.id)[0]


class AdminAnnouncementsView(_AnnouncementsBase):
    """GET admin/scholarship/announcements/ `?programme=` — the organisation's announcements, the "For"
    picker with live counts, and whether its `announcement` email is switched on.
    POST — a new one `{title, body, programme (gift code or null), pinned, email, action: publish|schedule|draft,
    publish_at (ISO, for schedule)}`; 201 with its row."""

    def get(self, request):
        admin, err = self._poster(request)
        if err:
            return err
        org, err = self._organisation(request, admin)
        if err:
            return err
        from ..student_email_catalogue import may_send
        rows = svc.staff_rows(org)
        counts = {k: sum(1 for r in rows if r['status'] == k) for k in ('published', 'scheduled', 'draft', 'withdrawn')}
        return Response({'organisation': {'code': org.code, 'name': org.name}, 'announcements': rows,
                         'counts': counts, 'audiences': svc.audiences(org),
                         'email_switch_on': may_send(org, svc.EMAIL_KEY),
                         'limits': {'title': svc.TITLE_MAX, 'body': svc.BODY_MAX}})

    def post(self, request):
        admin, err = self._poster(request)
        if err:
            return err
        org, err = self._organisation(request, admin)
        if err:
            return err
        try:
            a = svc.create(org, _data(request), by_email=admin.email or '')
        except svc.AnnouncementError as e:
            return _announcement_refusal(e)
        logger.warning('AUDIT announcement_created id=%s org=%s status=%s email=%s by=%s',
                       a.id, org.code, a.status, a.email_requested, admin.email)
        return Response(self._row(a), status=status.HTTP_201_CREATED)


class AdminAnnouncementView(_AnnouncementsBase):
    """PATCH admin/scholarship/announcements/<pk>/ — edit (once published: title, message and pin only;
    "edited" is stamped; it never emails again). DELETE — a draft or a scheduled one only (409
    `withdraw_instead` once it is out)."""

    def patch(self, request, pk):
        admin, a, err = self._announcement(request, pk)
        if err:
            return err
        try:
            a = svc.update(a, _data(request), by_email=admin.email or '')
        except svc.AnnouncementError as e:
            return _announcement_refusal(e)
        logger.warning('AUDIT announcement_edited id=%s org=%s status=%s by=%s',
                       a.id, a.organisation.code, a.status, admin.email)
        return Response(self._row(a))

    def delete(self, request, pk):
        admin, a, err = self._announcement(request, pk)
        if err:
            return err
        try:
            svc.delete(a)
        except svc.AnnouncementError as e:
            return _announcement_refusal(e)
        logger.warning('AUDIT announcement_deleted id=%s org=%s by=%s', pk, a.organisation.code, admin.email)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminAnnouncementWithdrawView(_AnnouncementsBase):
    """POST admin/scholarship/announcements/<pk>/withdraw/ — hide a published one from scholars."""

    def post(self, request, pk):
        admin, a, err = self._announcement(request, pk)
        if err:
            return err
        try:
            a = svc.withdraw(a, by_email=admin.email or '')
        except svc.AnnouncementError as e:
            return _announcement_refusal(e)
        logger.warning('AUDIT announcement_withdrawn id=%s org=%s by=%s', a.id, a.organisation.code, admin.email)
        return Response(self._row(a))
