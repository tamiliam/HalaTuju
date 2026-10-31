"""Mentors — a person who guides a funded student, with their own sign-in (student maintenance S7a,
2026-10-31; owner rulings in docs/decisions.md the same day).

A mentor is INVITED by staff (name + email) and SIGNS IN on the source-partner pattern: the login is a
`courses.PartnerAdmin` row with role `mentor` and `mentor` pointing here (`PartnerAdmin.mentor`, a
database check). The mentor fills in their own profile — the common `/admin/profile` page, with the
reviewer's qualification, language and address cards and the `area` below. Staff cannot edit those.

⚠ KEPT SMALL ON PURPOSE. Sprint 7b adds `MentorAssignment` / `MentoringSession` pointing at this
model. What a mentor IS lives here; who they are (name, email, sign-in) lives on their login row.

⚠ NEVER DELETED. A mentor is DEACTIVATED (`deactivated_at`), which also switches their login off;
past meetings stay on each scholar's file (7b). Status is DERIVED (`mentor_invite.status_of`), never
stored: inactive when deactivated, invited until the login's first sign-in, else active.

⚠ MENTORS NEVER REACH SPONSORS OR PARTNERS. Nothing here is on a sponsor or partner serializer.
"""
from django.db import models


class Mentor(models.Model):
    """One mentor, owned by the organisation that invited them. See the module docstring."""

    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT, related_name='mentors',
        help_text='The organisation (tenant) that invited this mentor and alone may see them.',
    )
    #: The area of mentoring — written by the MENTOR (`PATCH admin/me/` `mentoring_area`), never by
    #: staff. Blank until the mentor fills in their profile.
    area = models.CharField(max_length=120, blank=True, default='')
    #: NULL = active (or invited). Set by Deactivate, cleared by Reactivate — never a delete.
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by_email = models.CharField(max_length=254, blank=True, default='')

    class Meta:
        db_table = 'mentors'
        ordering = ['id']

    def __str__(self):
        return f'Mentor {self.pk} org={self.organisation_id}'
