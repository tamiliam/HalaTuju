"""Formal letters to a funded student, and an organisation's own wording for them (student
maintenance Sprint 6b, 2026-10-31; owner rulings 2026-10-30 in docs/decisions.md).

⚠ A LETTER IS A DOCUMENT ONLY. Issuing one never changes the application's status, sub-state or
payments — a termination letter is followed, if the officer chooses, by the file's existing Close
control. Nothing in this module or `letters.py` writes `status`, `maintenance_substate` or money.

⚠ NEVER EDITED, NEVER DELETED. An issued letter is evidence: its subject and body are FROZEN as
rendered, its PDF stored once. The only way out is Withdraw, with a reason — the row stays.
"""
from django.db import models

#: The five kinds (owner, 2026-10-30). Suspension and termination: super / org_admin only.
LETTER_KINDS = [
    ('general', 'General'),
    ('discipline', 'Discipline'),
    ('suspension', 'Suspension'),
    ('termination', 'Termination'),
    ('close_out', 'Close-out'),
]
#: The PDF is English or Malay ONLY (owner ruling: the PDF stack cannot shape Tamil). The notice
#: email and the screens are in her own language.
LETTER_LANGUAGES = [('en', 'English'), ('ms', 'Malay')]


class LetterTemplate(models.Model):
    """An ORGANISATION's own wording for one kind of letter, in one PDF language. A row exists only
    where the organisation changed the wording; otherwise `letter_defaults.DEFAULTS` applies, so
    nothing is seeded (the `StudentEmailTemplate` rule, S4b)."""
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.CASCADE, related_name='letter_templates')
    kind = models.CharField(max_length=20, choices=LETTER_KINDS)
    language = models.CharField(max_length=2, choices=LETTER_LANGUAGES)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    updated_by_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'letter_templates'
        ordering = ['organisation_id', 'kind', 'language']
        constraints = [
            models.UniqueConstraint(fields=['organisation', 'kind', 'language'],
                                    name='letter_template_org_kind_lang_uniq'),
        ]

    def __str__(self):
        return f'{self.kind}/{self.language} org={self.organisation_id}'


class Letter(models.Model):
    """One issued letter. Subject and body are stored AS RENDERED at issue; `response_due_on` is
    STAMPED at issue from `letter_response_days` (lessons 2026-10-07: a promise is stamped, never
    re-read from a setting). `emailed_at` is set only when the notice email actually went."""
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, related_name='letters')
    kind = models.CharField(max_length=20, choices=LETTER_KINDS)
    language = models.CharField(max_length=2, choices=LETTER_LANGUAGES)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    clause = models.CharField(max_length=40, blank=True, default='')
    note = models.TextField(blank=True, default='')
    #: `<org>/<app>/letters/<id>.pdf` in the PRIVATE bucket (`storage.build_doc_key`).
    pdf_path = models.CharField(max_length=500, blank=True, default='')
    issued_by_email = models.CharField(max_length=254, blank=True, default='')
    issued_by_name = models.CharField(max_length=200, blank=True, default='')
    issued_by_role = models.CharField(max_length=20, blank=True, default='')
    issued_at = models.DateTimeField(auto_now_add=True)
    response_due_on = models.DateField()
    emailed_at = models.DateTimeField(null=True, blank=True)
    emailed_to = models.CharField(max_length=254, null=True, blank=True)
    #: When she first opened it on My Bursary (the unread dot); never shown to staff as a reading.
    read_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawn_by_email = models.CharField(max_length=254, blank=True, default='')
    withdrawn_by_name = models.CharField(max_length=200, blank=True, default='')
    withdrawn_reason = models.TextField(blank=True, default='')
    #: The issue dialog's own id for ONE press of "Issue and email" (review 3): a repeat POST with the
    #: same key returns this letter instead of issuing a second. Nullable — a caller without one still
    #: issues; unique per application where present (NULLs never collide).
    issue_key = models.CharField(max_length=64, null=True, blank=True)
    #: The last time an officer pressed Resend (review 6): at most once every 10 minutes per letter.
    last_resend_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'letters'
        ordering = ['-issued_at', '-id']
        indexes = [models.Index(fields=['application', '-issued_at'], name='letter_app_issued_idx')]
        constraints = [
            models.UniqueConstraint(fields=['application', 'issue_key'], name='letter_app_issue_key_uniq'),
        ]

    def __str__(self):
        return f'letter {self.id} {self.kind} app={self.application_id}'
