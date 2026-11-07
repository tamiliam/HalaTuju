"""Notes for the reviewer (request #55, 2026-11-07) — model 88, NEW.

Before she assigns a student, the organisation admin reads the application and picks out what the
reviewer should explore. She used to text it; now she writes it on the application page, where it
stays as a record. Written ONLY by `apps/scholarship/reviewer_notes.add_note`; read by the cockpit's
"Notes for the reviewer" card through `views_admin/reviewer_notes.py`.

⚠ STAFF-ONLY, AND NOTHING ELSE READS IT. No student serializer, no sponsor serializer (that one is
an allowlist and stays one), and NEVER an AI prompt: the case summary, the profile generation and
the verdict never see a note. `tests/test_reviewer_notes.py` lists every module allowed to name this
model and fails when another one does.

⚠ APPEND-ONLY. There is no edit and no delete endpoint; `save()` refuses an update. To correct a
note the org admin adds another (owner, 2026-11-07). The notes go with the application on a
purge (CASCADE), as the rest of the file does.

`author` is SET_NULL and `author_email` is the house stamp beside it: `staff_footprint.EMAIL_STAMPS`
counts it, so a person who has written a note is revoked, never deleted, and the FK stays filled.
"""
from django.db import models
from django.db.models import Q

#: The longest note (owner, 2026-11-07, "like the reviewer's Recommend box"). Bounded at the column
#: too, so an over-long body is a clean `too_long` from the service, never a database error.
NOTE_MAX = 2000


class ReviewerNote(models.Model):
    """One note from an organisation admin (or a platform super) to the reviewer of one application."""
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, related_name='reviewer_notes')
    body = models.CharField(max_length=NOTE_MAX)
    author = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    author_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reviewer_notes'
        # OLDEST FIRST: the card reads top to bottom as it was written, newest last (owner).
        ordering = ['created_at', 'id']
        constraints = [
            # The service strips and refuses a blank note first; this is the floor under it.
            models.CheckConstraint(condition=~Q(body=''), name='reviewer_note_not_blank'),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('A reviewer note is append-only: add another note instead.')
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'ReviewerNote app={self.application_id} by={self.author_id}'
