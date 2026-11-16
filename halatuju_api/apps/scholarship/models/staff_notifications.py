"""Staff notifications (request #73, 2026-11-16) — model 90, NEW: "something new for you on this case".

One row per (person, thing they have not seen). Today the only kind is a note in the two-way org admin and
reviewer notes; the table is shaped so a later kind can share it. It drives the "New
note" mark on the applications table and the bell line, and it is cleared when the person opens the
student's page with the notes on screen.

⚠ NO TEXT AND NO STUDENT DATA. The row names the recipient, the organisation, the application, the kind
and the id of the thing (`source_id`); never what the note says.

⚠ ONE WRITER: `apps/scholarship/staff_notifications.py`. `tests/test_staff_notifications.py` lists the
modules allowed to name this model and fails when another one does.

The reverse names are '+' on purpose: a person or an organisation does not reach its notices by an
attribute (the one module reads them), and the split-pins test (`a37_pins.json`) stays as it was.
"""
from django.db import models
from django.db.models import Q

REVIEWER_NOTE = 'reviewer_note'
KINDS = ((REVIEWER_NOTE, 'A note in the org admin and reviewer notes'),)


class StaffNotification(models.Model):
    """One unseen-or-seen notice for one staff member about one application."""
    recipient = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.CASCADE, related_name='+')
    org = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    kind = models.CharField(max_length=32, choices=KINDS)
    source_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'staff_notifications'
        constraints = [
            models.UniqueConstraint(fields=['recipient', 'kind', 'source_id'],
                                    name='staff_notification_once'),
        ]
        indexes = [
            models.Index(fields=['recipient', 'seen_at'], name='staff_notif_recipient_seen'),
            # The reads ask only for what is unseen: the mark, the bell count and the clearing.
            models.Index(fields=['recipient', 'application'], condition=Q(seen_at__isnull=True),
                         name='staff_notif_unseen'),
        ]

    def __str__(self):
        return f'StaffNotification {self.kind} to={self.recipient_id} app={self.application_id}'
