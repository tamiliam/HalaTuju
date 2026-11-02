"""Announcements — news an organisation posts to its funded scholars (student maintenance Sprint 8,
2026-11-01; owner rulings in docs/decisions.md the same day). Rules: `apps/scholarship/announcements.py`.

⚠ ONE TEXT FOR EVERYONE. A title and a plain-text message (line breaks kept, links made clickable on
display) — no per-language copies, no pictures, no attachments.

⚠ WHO SEES IT IS DECIDED WHEN READ, never stored per scholar: the organisation's scholars in
maintenance (`maintenance_scope.in_maintenance_q`), narrowed to ONE gift when `programme` is set, and a
file closed AFTER the announcement went out keeps it (read-only). A scholar who joins later sees the
published ones of their audience. Nothing here is ever served to a sponsor, a partner or a source.

⚠ A PUBLISHED ANNOUNCEMENT IS WITHDRAWN, NEVER DELETED (the row stays under Withdrawn for staff); only a
draft or a scheduled one may be deleted. An edit after publishing changes the text and stamps
`edited_at`; it NEVER emails again.
"""
from django.db import models

#: The four states (owner, 2026-11-01). A `scheduled` one whose `publish_at` has passed READS as
#: published everywhere (`announcements.live_q`) whether or not the hourly job has flipped it yet.
ANNOUNCEMENT_STATUSES = [
    ('draft', 'Draft'),
    ('scheduled', 'Scheduled'),
    ('published', 'Published'),
    ('withdrawn', 'Withdrawn'),
]

#: What happened to ONE scholar's copy of the email (`AnnouncementEmail.outcome`).
EMAIL_OUTCOMES = [
    ('sending', 'Claimed, being sent'),
    ('sent', 'Sent'),
    ('failed', 'The send failed'),
    ('no_address', 'No email address'),
    ('switched_off', 'The organisation had the email switched off'),
]


class Announcement(models.Model):
    """One announcement, owned by the organisation that posted it."""
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.CASCADE, related_name='announcements')
    #: NULL = every scholar of the organisation; else ONE of its gifts.
    programme = models.ForeignKey(
        'Programme', on_delete=models.PROTECT, null=True, blank=True, related_name='announcements')
    title = models.CharField(max_length=150)
    body = models.TextField()
    status = models.CharField(max_length=12, choices=ANNOUNCEMENT_STATUSES, default='draft')
    #: The chosen time of a scheduled one (NULL for "now" and for a draft).
    publish_at = models.DateTimeField(null=True, blank=True)
    #: When it went out: the moment of "Publish now", or the scheduled `publish_at` once flipped.
    published_at = models.DateTimeField(null=True, blank=True)
    pinned = models.BooleanField(default=False)
    #: "Also email it to the scholars" — sent by the hourly `announcement-emails` job.
    email_requested = models.BooleanField(default=False)
    #: When the job finished this announcement's emails (every scholar of the audience then has a row).
    emailed_at = models.DateTimeField(null=True, blank=True)
    #: Stamped by an edit AFTER publishing — the "edited" mark staff and scholars see.
    edited_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawn_by_email = models.CharField(max_length=254, blank=True, default='')
    created_by_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'announcements'
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['organisation', 'status'], name='announcement_org_status_idx')]

    def __str__(self):
        return f'announcement {self.id} ({self.status}) org={self.organisation_id}'


class AnnouncementRead(models.Model):
    """ONE scholar's file has been shown ONE announcement on My Bursary → News (the unread count and
    staff's "read N of M"). Written only for an announcement that file may see; never twice."""
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='reads')
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, related_name='announcement_reads')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'announcement_reads'
        constraints = [
            models.UniqueConstraint(fields=['announcement', 'application'], name='announcement_read_uniq'),
        ]

    def __str__(self):
        return f'read {self.announcement_id} app={self.application_id}'


class AnnouncementEmail(models.Model):
    """ONE scholar's copy of an announcement's email: CLAIMED (unique per announcement x application)
    BEFORE the send, so a second run of the job — or two at once — can never send it twice. The outcome
    is written after: sent / failed / no_address / switched_off. A row left at `sending` (the process
    died mid-send) is never retried — at most once, by design."""
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='emails')
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, related_name='announcement_emails')
    outcome = models.CharField(max_length=12, choices=EMAIL_OUTCOMES, default='sending')
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'announcement_emails'
        constraints = [
            models.UniqueConstraint(fields=['announcement', 'application'], name='announcement_email_uniq'),
        ]

    def __str__(self):
        return f'email {self.announcement_id} app={self.application_id} {self.outcome}'
