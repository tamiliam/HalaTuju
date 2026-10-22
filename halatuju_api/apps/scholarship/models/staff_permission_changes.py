"""The history of a staff member's permissions (request #39 Sprint 4, 2026-10-21).

One row each time what a person may do CHANGES: an edit on People → a person → "What <name> can
do" (`kind='edit'`), or a Change role that put a saved custom set back to the new role's preset
(`kind='role_change'`). `before` and `after` are the RESOLVED keys (never NULL), so a row reads on
its own without knowing the presets of the day.

⚠ WHY A TABLE AND NOT ONLY A LOG LINE. A role change was audited by an `AUDIT` line alone, which
Cloud Logging keeps for 30 days. Two of these permissions release money (`payments_approve`) or open
students' files (`see_all`, `review`), so "who gave Rohini the approval, and when" must still be
answerable next year — the reasoning behind `guardian_contact_changes`. The `AUDIT
staff_permissions_changed` line is written as well.

⚠ SET_NULL, NEVER CASCADE: deleting a staff row (only ever one with no recorded work) keeps its
history, and `target_email` still names who it was about.

READERS: the person page's "Changes" list, through `GET admin/admins/<id>/permissions/`
(`views_admin/staff.py` `_permission_history`, 2026-10-22) — the latest rows for a LIVE target
only, and never a super's address to an organisation; the Django admin and the database read the
rest.
"""
from django.db import models


class StaffPermissionChange(models.Model):
    """Who changed whose permissions, from what to what, and when."""
    KIND_CHOICES = [('edit', 'Edited on People'), ('role_change', 'Reset by a role change')]

    target = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='permission_changes')
    #: The person's address when the change was made — survives a delete of the row above.
    target_email = models.CharField(max_length=254, blank=True, default='')
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='staff_permission_changes')
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default='edit')
    #: The preset label (`role`) the person held when the change was made.
    role = models.CharField(max_length=20, blank=True, default='')
    before = models.JSONField(default=list, blank=True)
    after = models.JSONField(default=list, blank=True)
    changed_by_email = models.CharField(max_length=254, blank=True, default='')
    changed_by_role = models.CharField(max_length=20, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'staff_permission_changes'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.target_email}: {self.before} -> {self.after}'
