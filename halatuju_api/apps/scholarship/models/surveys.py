"""Surveys — an organisation's questions to its funded scholars (student maintenance Sprint 9, 2026-11-02;
owner rulings in docs/decisions.md the same day). Rules: `apps/scholarship/surveys.py`.

⚠ STATUS IS READ FROM THE DATES. Only `draft` / `published` is stored; a published survey READS as
`scheduled` before `opens_at`, `open` until `closes_at`, then `closed` (`surveys.effective_status`).
"Close now" sets `closes_at` to now. Nothing waits for a job to see a survey open or closed.

⚠ WHO IT IS FOR IS DECIDED WHEN READ, never stored per scholar: the organisation's scholars in maintenance
(`maintenance_scope.in_maintenance_q`), narrowed to ONE gift when `programme` is set. A file closed later
keeps a read-only sight of what it already answered. Nothing here is ever served to a sponsor, a partner or
a source; answers carry the scholar's name for STAFF only.

⚠ THE QUESTIONS LOCK at the first answer (`surveys.has_answers`): no add, remove, reorder or edit. The
closing date, the title and the introduction may still change. A survey with answers is closed, never
deleted.
"""
from django.db import models

#: What is stored. `draft` is never shown to a scholar; `published` reads from its dates.
SURVEY_STATUSES = [
    ('draft', 'Draft'),
    ('published', 'Published'),
]

#: The six question types (owner, 2026-11-02).
QUESTION_KINDS = [
    ('one', 'One choice'),
    ('many', 'Several choices'),
    ('rating', 'Rating 1-5'),
    ('yes_no', 'Yes or no'),
    ('short', 'Short answer'),
    ('long', 'Long answer'),
]

#: The two emails, each sent at most once per scholar per survey.
EMAIL_KINDS = [
    ('open', 'The survey is open'),
    ('reminder', 'Not answered yet: it closes soon'),
]

#: What happened to ONE scholar's copy of one email (`SurveyEmail.outcome`).
EMAIL_OUTCOMES = [
    ('sending', 'Claimed, being sent'),
    ('sent', 'Sent'),
    ('failed', 'The send failed'),
    ('no_address', 'No email address'),
    ('switched_off', 'The organisation had the email switched off'),
]


class Survey(models.Model):
    """One survey, owned by the organisation that wrote it."""
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.CASCADE, related_name='surveys')
    #: NULL = every scholar of the organisation; else ONE of its gifts.
    programme = models.ForeignKey(
        'Programme', on_delete=models.PROTECT, null=True, blank=True, related_name='surveys')
    title = models.CharField(max_length=150)
    intro = models.TextField(blank=True, default='')
    status = models.CharField(max_length=12, choices=SURVEY_STATUSES, default='draft')
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()
    #: "Email the scholars when it opens" — sent by the hourly `survey-emails` job.
    email_on_open = models.BooleanField(default=False)
    #: "Remind those who have not answered, 3 days before it closes" — the same job.
    remind_before_close = models.BooleanField(default=False)
    #: When the job finished the opening emails (every scholar of the audience then has a row).
    opened_emailed_at = models.DateTimeField(null=True, blank=True)
    #: When the job (or the Results page's button) finished the reminders.
    reminded_at = models.DateTimeField(null=True, blank=True)
    created_by_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'surveys'
        ordering = ['-opens_at', '-id']
        indexes = [models.Index(fields=['organisation', 'status'], name='survey_org_status_idx')]

    def __str__(self):
        return f'survey {self.id} ({self.status}) org={self.organisation_id}'


class SurveyQuestion(models.Model):
    """One question, in its place. Locked (with every other question of its survey) at the first answer."""
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
    position = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=8, choices=QUESTION_KINDS)
    text = models.CharField(max_length=300)
    #: A short line under the question ("1 = not useful, 5 = very useful").
    hint = models.CharField(max_length=200, blank=True, default='')
    required = models.BooleanField(default=True)
    #: Shown only to a scholar with a mentor NOW (an open `MentorAssignment`).
    mentor_only = models.BooleanField(default=False)
    #: The choices of a `one` / `many` question (2-12, each <= 120); `[]` otherwise.
    options = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'survey_questions'
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(fields=['survey', 'position'], name='survey_question_position_uniq'),
        ]

    def __str__(self):
        return f'question {self.position} of survey {self.survey_id} ({self.kind})'


class SurveyResponse(models.Model):
    """ONE scholar's answers to ONE survey. Unique per survey x application (a second submit, or two at
    once, changes this row; it never makes a second). Answers are replaced whole, in one transaction."""
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='responses')
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, related_name='survey_responses')
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'survey_responses'
        constraints = [
            models.UniqueConstraint(fields=['survey', 'application'], name='survey_response_uniq'),
        ]

    def __str__(self):
        return f'response survey={self.survey_id} app={self.application_id}'


class SurveyAnswer(models.Model):
    """One answer: `value` is the option text (one), a list of option texts (many), 1-5 (rating), true /
    false (yes_no) or the text written (short, long)."""
    response = models.ForeignKey(SurveyResponse, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE, related_name='answers')
    value = models.JSONField()

    class Meta:
        db_table = 'survey_answers'
        constraints = [
            models.UniqueConstraint(fields=['response', 'question'], name='survey_answer_uniq'),
        ]

    def __str__(self):
        return f'answer response={self.response_id} question={self.question_id}'


class SurveyEmail(models.Model):
    """ONE scholar's copy of one survey email (`open` or `reminder`): CLAIMED (unique per survey x
    application x kind) BEFORE the send, so the hourly job, a second run, or the Results page's "Remind"
    button can never send it twice. A row left at `sending` is never retried — at most once, by design."""
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='emails')
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, related_name='survey_emails')
    kind = models.CharField(max_length=8, choices=EMAIL_KINDS)
    outcome = models.CharField(max_length=12, choices=EMAIL_OUTCOMES, default='sending')
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'survey_emails'
        constraints = [
            models.UniqueConstraint(fields=['survey', 'application', 'kind'], name='survey_email_uniq'),
        ]

    def __str__(self):
        return f'survey email {self.survey_id} app={self.application_id} {self.kind} {self.outcome}'
