"""The record of changes to a student's parent/guardian contact (request #26, 2026-10-05).

The contact itself is NOT here and did not move: it is entry 0 of `StudentProfile.guardians`
(`{name, phone}`), written by the apply form and now also by `guardian_contact.py`, and its phone
is the one number the bursary-signing PIN is sent to (`bursary.guarantor_phone_for`). Because a
change to that number changes who can vouch for the student, every REAL change made through the
product — the profile, the admin correction, a later application form — is written here: who made
it, in which role, from what to what. A save that changes nothing writes nothing. ⚠ Django's
staff-only `/admin/` site can also edit `guardians` and records NOTHING here; it is the one exception.
"""
from django.db import models

from .applications import ScholarshipApplication


class GuardianContactChange(models.Model):
    """One entry in the trail of a student's parent/guardian contact: a CHANGE to entry 0's name
    or phone (by the student or an admin), or a CALL an admin made to the parent (request #26,
    the owner's consent framing of 2026-10-05). One table, so a dispute reads as one chronological
    trail for that contact."""
    ROLE_CHOICES = [('student', 'Student'), ('admin', 'Administrator')]
    KIND_CHOICES = [('change', 'Change'), ('call', 'Call')]
    OUTCOME_CHOICES = [
        ('shared_confirmed', 'Shared number - parent confirmed'),
        ('parent_number_confirmed', "Parent's own number confirmed"),
        ('parent_number_corrected', "Parent's number corrected"),
        ('could_not_reach', 'Could not reach'),
    ]
    #: The outcomes that, WITH consent, clear the shared-phone flag for the number called.
    CLEARING_OUTCOMES = ('shared_confirmed', 'parent_number_confirmed')

    # ⚠ SET_NULL, NOT CASCADE (owner, 2026-10-05). A signed BursaryAgreement deliberately survives
    # the student's account deletion (`ScholarshipApplication.profile` is SET_NULL and the agreement
    # hangs off the application). This trail is the evidence that the parent was on board, so it
    # must live exactly as long: its retention basis is the agreement's (defence of legal claims),
    # and the agreement already holds the parent's name, NRIC and phone. See docs/decisions.md.
    profile = models.ForeignKey(
        'courses.StudentProfile', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='guardian_contact_changes')
    # The application the entry was made through (the admin's case, or the student's latest).
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='guardian_contact_changes')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='change')
    # The contact before and after. A call that changes nothing records the contact as it stood.
    old_name = models.CharField(max_length=255, blank=True, default='')
    new_name = models.CharField(max_length=255, blank=True, default='')
    old_phone = models.CharField(max_length=32, blank=True, default='')
    new_phone = models.CharField(max_length=32, blank=True, default='')
    # ── A call (kind='call') ───────────────────────────────────────────────────────────────────
    called_number = models.CharField(max_length=32, blank=True, default='')
    call_outcome = models.CharField(max_length=32, choices=OUTCOME_CHOICES, blank=True, default='')
    # "The parent was told about the bursary and agreed." NULL when nobody was reached.
    consent_given = models.BooleanField(null=True, blank=True)
    parent_name_given = models.CharField(max_length=255, blank=True, default='')
    note = models.TextField(blank=True, default='')
    changed_by_email = models.CharField(max_length=254, blank=True, default='')
    changed_by_role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'guardian_contact_changes'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'GuardianContactChange {self.kind} profile={self.profile_id} by={self.changed_by_role}'
