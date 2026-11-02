"""Development modules — short lessons an organisation gives its funded scholars, with an optional task at the
end (student maintenance Sprint 10, 2026-11-02; owner rulings in docs/decisions.md the same day). Rules:
`apps/scholarship/development.py`; staff payloads `development_progress.py`; files `development_files.py`;
emails `development_emails.py`.

⚠ STATUS: only draft / published / archived is stored; a published module READS as `scheduled` before
`publish_at` (`development.module_status`). Nothing waits for a job to see a module go live.

⚠ WHO IT IS FOR IS DECIDED WHEN READ, never stored per scholar: the organisation's scholars in maintenance,
narrowed to ONE gift when `programme` is set (Sprint 8's `announcements.audience_apps`). A scholar who has
STARTED (a `ModuleProgress` row) keeps a read-only sight of it after her file closes or the module is archived.

⚠ PROGRESS IS PER LESSON ID: a lesson is "read" when a `LessonRead` row names it. "Done" = every CURRENT
lesson read + the task sent (when there is one). Lessons may be added or removed after a start; a removed
lesson's reads go with it (CASCADE). The TASK TYPE locks at the first start.

⚠ FILES live in the private `b40-documents` bucket under an organisation-prefixed key; only a short signed URL
is ever served, on a tap. Never a public URL. Optional for the scholar: nothing here touches money, standing or
eligibility.
"""
from django.db import models

#: What is stored. `draft` is never shown to a scholar; `published` reads from `publish_at`; `archived` is hidden
#: from those who have not started (those who started keep a read-only sight).
MODULE_STATUSES = [
    ('draft', 'Draft'),
    ('published', 'Published'),
    ('archived', 'Archived'),
]

#: The task at the end (one per module). Locks once any scholar has started.
TASK_KINDS = [
    ('none', 'No task'),
    ('reflection', 'Written reflection'),
    ('upload', 'Upload a file'),
]

#: The two emails, each sent at most once per scholar per module.
MODULE_EMAIL_KINDS = [
    ('published', 'A new module is ready'),
    ('reminder', 'Not done yet: it is due soon'),
]

#: What happened to ONE scholar's copy of one email (`ModuleEmail.outcome`) — the `SurveyEmail` set.
MODULE_EMAIL_OUTCOMES = [
    ('sending', 'Claimed, being sent'),
    ('sent', 'Sent'),
    ('failed', 'The send failed'),
    ('no_address', 'No email address'),
    ('switched_off', 'The organisation had the email switched off'),
]


class DevelopmentModule(models.Model):
    """One module, owned by the organisation that wrote it."""
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.CASCADE, related_name='development_modules')
    #: NULL = every scholar of the organisation; else ONE of its gifts.
    programme = models.ForeignKey(
        'Programme', on_delete=models.PROTECT, null=True, blank=True, related_name='development_modules')
    title = models.CharField(max_length=150)
    summary = models.TextField(blank=True, default='')
    status = models.CharField(max_length=12, choices=MODULE_STATUSES, default='draft')
    #: When it goes live (published); a draft may hold a planned time. NULL on a draft saved "now".
    publish_at = models.DateTimeField(null=True, blank=True)
    #: Optional. After it, a scholar not done reads "Late" to staff and the mentor — never to money.
    due_on = models.DateField(null=True, blank=True)
    task_kind = models.CharField(max_length=12, choices=TASK_KINDS, default='none')
    task_prompt = models.TextField(blank=True, default='')
    #: "Email the scholars when it is published" — sent by the hourly `module-emails` job.
    email_on_publish = models.BooleanField(default=False)
    #: "Remind those not done, 3 days before the due date" — the same job (only with a due date).
    remind_before_due = models.BooleanField(default=False)
    published_emailed_at = models.DateTimeField(null=True, blank=True)
    reminded_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'development_modules'
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['organisation', 'status'], name='devmodule_org_status_idx')]

    def __str__(self):
        return f'module {self.id} ({self.status}) org={self.organisation_id}'


class ModuleLesson(models.Model):
    """One lesson, in its place: a title, text (plain, paragraphs; URLs become links on display) and at most
    ONE of a video link (YouTube / Vimeo) or a file (PDF / JPEG / PNG in the private bucket)."""
    module = models.ForeignKey(DevelopmentModule, on_delete=models.CASCADE, related_name='lessons')
    position = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=150)
    body = models.TextField(blank=True, default='')
    video_url = models.CharField(max_length=500, blank=True, default='')
    #: The private-bucket key (`<org>/development/<module>/<uuid>`); '' = no file.
    file_path = models.CharField(max_length=300, blank=True, default='')
    file_name = models.CharField(max_length=255, blank=True, default='')
    #: Decided from the bytes (`development_files.sniff`), never from the name or the browser.
    file_type = models.CharField(max_length=100, blank=True, default='')
    file_size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'module_lessons'
        ordering = ['position', 'id']

    def __str__(self):
        return f'lesson {self.position} of module {self.module_id}'


class ModuleProgress(models.Model):
    """ONE scholar's work on ONE module (unique per module x application): made at her first "I have read
    this" or her first task send. Holds her task (a reflection, or a file key under HER org/app path) and the
    staff review (who / when / the comment she sees)."""
    module = models.ForeignKey(DevelopmentModule, on_delete=models.CASCADE, related_name='progress')
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, related_name='module_progress')
    started_at = models.DateTimeField(auto_now_add=True)
    task_text = models.TextField(blank=True, default='')
    task_file_path = models.CharField(max_length=300, blank=True, default='')
    task_file_name = models.CharField(max_length=255, blank=True, default='')
    task_file_type = models.CharField(max_length=100, blank=True, default='')
    task_file_size = models.PositiveIntegerField(default=0)
    task_sent_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by_email = models.CharField(max_length=254, blank=True, default='')
    review_comment = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'module_progress'
        constraints = [
            models.UniqueConstraint(fields=['module', 'application'], name='module_progress_uniq'),
        ]

    def __str__(self):
        return f'progress module={self.module_id} app={self.application_id}'


class LessonRead(models.Model):
    """"I have read this" — one row per progress x lesson (unique: marking twice changes nothing)."""
    progress = models.ForeignKey(ModuleProgress, on_delete=models.CASCADE, related_name='reads')
    lesson = models.ForeignKey(ModuleLesson, on_delete=models.CASCADE, related_name='reads')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'module_lesson_reads'
        constraints = [
            models.UniqueConstraint(fields=['progress', 'lesson'], name='module_lesson_read_uniq'),
        ]

    def __str__(self):
        return f'read progress={self.progress_id} lesson={self.lesson_id}'


class ModuleEmail(models.Model):
    """ONE scholar's copy of one module email (`published` or `reminder`): CLAIMED (unique per module x
    application x kind) BEFORE the send — the `SurveyEmail` pattern — so the hourly job, a second run, or the
    Progress page's "Remind those not done" can never send it twice. A row left at `sending` is never retried."""
    module = models.ForeignKey(DevelopmentModule, on_delete=models.CASCADE, related_name='emails')
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, related_name='module_emails')
    kind = models.CharField(max_length=10, choices=MODULE_EMAIL_KINDS)
    outcome = models.CharField(max_length=12, choices=MODULE_EMAIL_OUTCOMES, default='sending')
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'module_emails'
        constraints = [
            models.UniqueConstraint(fields=['module', 'application', 'kind'], name='module_email_uniq'),
        ]

    def __str__(self):
        return f'module email {self.module_id} app={self.application_id} {self.kind} {self.outcome}'
