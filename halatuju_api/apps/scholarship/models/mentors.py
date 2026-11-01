"""Mentors — a person who guides a funded student, with their own sign-in (student maintenance S7a,
2026-10-31; owner rulings in docs/decisions.md the same day).

A mentor is INVITED by staff (name + email) and SIGNS IN on the source-partner pattern: the login is a
`courses.PartnerAdmin` row with role `mentor` and `mentor` pointing here (`PartnerAdmin.mentor`, a
database check). The mentor fills in their own profile — the common `/admin/profile` page, with the
reviewer's qualification, language and address cards and the `area` below. Staff cannot edit those.

⚠ KEPT SMALL ON PURPOSE. What a mentor IS lives here; who they are (name, email, sign-in) lives on
their login row. Sprint 7b adds `MentorAssignment` / `MentoringSession` below (rules:
`apps/scholarship/mentoring.py`).

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


class MentorAssignment(models.Model):
    """One mentor's time with one scholar (student maintenance S7b, 2026-11-01).

    ⚠ ONE OPEN ROW PER APPLICATION, held by the DATABASE (a partial unique index on
    `ended_at IS NULL`), not only by the code: two racing "assign" requests cannot both leave an
    open row. A CHANGE ends the open row (it stays, the history) and starts a new one, in one
    transaction (`mentoring.assign`). Never deleted; never reopened.

    `end_reason` is STAFF ONLY (never on a student payload). `emailed_student` records whether the
    "You have a mentor" email actually went (set after the send).
    """
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, related_name='mentor_assignments')
    mentor = models.ForeignKey(Mentor, on_delete=models.PROTECT, related_name='assignments')
    started_at = models.DateTimeField(auto_now_add=True)
    started_by_email = models.CharField(max_length=254, blank=True, default='')
    #: NULL = the current assignment.
    ended_at = models.DateTimeField(null=True, blank=True)
    ended_by_email = models.CharField(max_length=254, blank=True, default='')
    end_reason = models.TextField(blank=True, default='')
    emailed_student = models.BooleanField(default=False)

    class Meta:
        db_table = 'mentor_assignments'
        ordering = ['-started_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['application'], condition=models.Q(ended_at__isnull=True),
                                    name='mentor_assignment_one_open'),
        ]

    def __str__(self):
        return f'MentorAssignment {self.pk} app={self.application_id} mentor={self.mentor_id}'


class MentoringSession(models.Model):
    """One meeting between a scholar and their mentor, logged by STAFF (S7b) or by the MENTOR
    (S7c, `mentor_desk.log_own_session`). Logged only while an assignment is open, with that
    assignment's mentor. Never edited once saved, by anyone.

    ⚠ `notes` and `next_step` are never the STUDENT's: the student sees the date and how, nothing
    else. Staff read every note; the mentor reads the notes of the meetings THEY logged only.

    ⚠ S7c: `logged_by_mentor` is SET by the mentor's own write, never inferred from an email.
    `concern` is the mentor's "Tell the team I am worried about this student"; staff clear it with
    "Mark as handled" (`concern_handled_at` / `_by_email`). All four keep a DATABASE default
    (`db_default`) so the image still serving inserts rows between the migrate and the deploy.
    """
    MODE_IN_PERSON, MODE_VIDEO, MODE_PHONE = 'in_person', 'video', 'phone'
    MODE_CHOICES = [(MODE_IN_PERSON, 'In person'), (MODE_VIDEO, 'Video call'), (MODE_PHONE, 'Phone call')]

    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, related_name='mentoring_sessions')
    #: The mentor at the time (kept even after a change).
    mentor = models.ForeignKey(Mentor, on_delete=models.PROTECT, related_name='sessions')
    assignment = models.ForeignKey(MentorAssignment, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='sessions')
    met_on = models.DateField()
    mode = models.CharField(max_length=12, choices=MODE_CHOICES)
    minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    next_step = models.TextField(blank=True, default='')
    logged_by_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    #: S7c: True when the MENTOR logged it (their own write sets it; every 7b row is staff-logged).
    logged_by_mentor = models.BooleanField(default=False, db_default=False)
    #: S7c: the mentor raised a concern with this meeting; open until staff mark it handled.
    concern = models.BooleanField(default=False, db_default=False)
    concern_handled_at = models.DateTimeField(null=True, blank=True)
    concern_handled_by_email = models.CharField(max_length=254, blank=True, default='', db_default='')

    class Meta:
        db_table = 'mentoring_sessions'
        ordering = ['-met_on', '-id']
        indexes = [models.Index(fields=['application', '-met_on'], name='mentoring_session_app_idx')]

    def __str__(self):
        return f'MentoringSession {self.pk} app={self.application_id} on={self.met_on}'
