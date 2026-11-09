"""A mentor's gifts — Invitations I4 (2026-11-08; owner ruling 2, open points C and D). The rules live in
`apps/scholarship/mentor_gift.py`; this module is the fence and the HTTP shape:

- `AdminMentorGiftsView` — `POST admin/mentors/<id>/gifts/` `{programme_ids: [..]}`: the WHOLE list of gifts
  this mentor mentors in; `[]` means EVERY gift (no rows, including gifts started later).

⚠ WHO: the Mentors page's ACTING roles and fence (`_MentorsBase._target`): super (any organisation) and
org_admin (their OWN organisation's mentors); anyone else 403; another organisation's mentor 404, never 403.
A staff member who mentors (S7d) has gifts too: their gifts limit their mentoring, not their staff work.

⚠ EVERY GIFT IS THE MENTOR'S OWN ORGANISATION'S (`mentor_gift.choose` against the MENTOR's organisation, so a
super cannot tag another organisation's gift either). Any other gift is 404, never 403.

⚠ NARROWING NEVER ENDS AN ASSIGNMENT (open point D): 409 `mentor_has_scholars_outside` with `count`, the
number of CURRENT scholars outside the new gifts. Nothing is written; an ended assignment never blocks.
"""
import logging

from rest_framework.response import Response

from .mentors import _MentorsBase

# ⚠ THE PACKAGE'S name, never `__name__` — an audit line must stay on the scrape metric (H11).
logger = logging.getLogger('apps.scholarship.views_admin')


class AdminMentorGiftsView(_MentorsBase):
    """POST admin/mentors/<id>/gifts/ `{programme_ids}` → 200 `{id, gifts: [{id, code, name}], every_gift}`.
    Refusals: 403 not super / org_admin; 404 another organisation's or an unknown mentor, or a gift that is
    not the mentor's organisation's; 400 `gift_required` (no list); 409 `mentor_has_scholars_outside`
    `{count}`."""

    def post(self, request, pk):
        from .. import mentor_gift
        admin, mentor, _login, err = self._target(request, pk)
        if err:
            return err
        data = request.data if isinstance(request.data, dict) else {}
        gifts, refusal = mentor_gift.choose(data.get('programme_ids'), mentor.organisation,
                                            active_only=False, required=True)
        if refusal is not None:
            return refusal
        old = ','.join(g['code'] for g in mentor_gift.gifts_by_mentor([mentor.pk]).get(mentor.pk, []))
        refused, n = mentor_gift.set_gifts(mentor, gifts)
        if refused:
            return mentor_gift.outside_refusal(n)
        logger.info('AUDIT mentor_gifts_set mentor=%s old=%s new=%s by=%s', mentor.pk,
                    old or '(every gift)', ','.join(g.code for g in gifts) or '(every gift)', admin.email or '')
        now = mentor_gift.gifts_by_mentor([mentor.pk]).get(mentor.pk, [])
        return Response({'id': mentor.pk, 'gifts': now, 'every_gift': not now})
