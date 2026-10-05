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
    """One change to `profile.guardians[0]`'s name and/or phone, by the student or an admin."""
    ROLE_CHOICES = [('student', 'Student'), ('admin', 'Administrator')]

    # CASCADE, like the other per-student rows (`login_aliases`, `email_verifications`): these
    # rows hold a parent's name and phone, and they must not outlive the student's account.
    profile = models.ForeignKey(
        'courses.StudentProfile', on_delete=models.CASCADE,
        related_name='guardian_contact_changes')
    # The application the change was made through (the admin's case, or the student's latest).
    # SET_NULL: the history of a contact is the student's, not the case's.
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='guardian_contact_changes')
    old_name = models.CharField(max_length=255, blank=True, default='')
    new_name = models.CharField(max_length=255, blank=True, default='')
    old_phone = models.CharField(max_length=32, blank=True, default='')
    new_phone = models.CharField(max_length=32, blank=True, default='')
    changed_by_email = models.CharField(max_length=254, blank=True, default='')
    changed_by_role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'guardian_contact_changes'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'GuardianContactChange profile={self.profile_id} by={self.changed_by_role}'
