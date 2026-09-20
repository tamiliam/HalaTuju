"""
Editorial and outbound odds and ends: trust content, standing gifts, WhatsApp.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

from .sponsors import Sponsor

class TrustContent(models.Model):
    """R5 (Trust & Transparency hub): the EDITABLE content behind the four-layer
    trust story — Who we are · Governance · Sources & uses of funds · Independent
    assurance. A single active row holds the fillable DATA (legal entity, trustees,
    annual figures, the auditor) as JSON so the organisation can fill it in over
    time as it formalises **without a code deploy** (edit the row directly / via
    admin). The UI CHROME (headings, "to be published" placeholders, explanatory
    copy) lives in trilingual i18n on the frontend — only the language-neutral,
    owner-authored data lives here, so i18n parity is never broken by DB content.

    Seeded with HONEST placeholders: the org is not yet formalised, figures are
    illustrative (``figures_are_illustrative``), trustees/auditor are empty. NEVER
    any student/sponsor PII — programme-level content only."""
    # Who we are — language-neutral facts; empty until the org registers.
    legal_entity = models.CharField(max_length=300, blank=True, default='')
    contact_email = models.EmailField(blank=True, default='help@halatuju.xyz')
    # Governance — list of {name, role, bio}; empty until trustees are appointed.
    trustees = models.JSONField(default=list, blank=True)
    # Sources & uses of funds — each a list of {label, amount} (RM). Illustrative
    # placeholders now; real figures (published annually) drop in as accounts mature.
    sources = models.JSONField(default=list, blank=True)
    uses = models.JSONField(default=list, blank=True)
    # Independent assurance — {fy, students_verified, disbursed, auditor, report_url}.
    assurance = models.JSONField(default=dict, blank=True)
    # True while the figures above are illustrative placeholders (the FE shows an
    # "illustrative" pill); flip to False once real audited figures are published.
    figures_are_illustrative = models.BooleanField(default=True)
    # Only the active row is served; lets a draft be staged without publishing.
    is_active = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trust_content'
        ordering = ['-updated_at']

    def __str__(self):
        return f'TrustContent active={self.is_active} updated={self.updated_at:%Y-%m-%d}'


class StandingGift(models.Model):
    """R6 (AutoSponsor): a sponsor's standing instruction to auto-direct their
    balance to the next matching pool student — an AutoInvest-style 'set it and
    forget it'. Each allocation still produces an OFFERED ``Sponsorship`` the
    student must accept (no real money moves) — the SAME safety model as a manual
    fund; it only automates the 'offer' click. One per sponsor (OneToOne).

    Matching (all optional): ``field_pref``/``state_pref`` empty = any; ``max_amount``
    empty = no cap. The sponsor's balance is the real throttle — each allocation
    holds the award, so the standing gift naturally stops when the balance runs low
    (skip silently, by owner decision) and resumes when it's topped up."""
    sponsor = models.OneToOneField(
        Sponsor, on_delete=models.CASCADE, related_name='standing_gift',
    )
    # Empty string = match any field/state (the student's `field_of_study` /
    # `profile.preferred_state`). Non-empty = only that exact value.
    field_pref = models.CharField(max_length=120, blank=True, default='')
    state_pref = models.CharField(max_length=60, blank=True, default='')
    # The most this sponsor will commit to a single student (caps which award
    # amounts qualify). Null = no per-student cap (balance is the only limit).
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    active = models.BooleanField(default=True)
    # When this gift last produced an allocation — used to spread allocations
    # fairly across standing gifts (least-recently-allocated goes next).
    last_allocated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'standing_gifts'

    def __str__(self):
        return f'StandingGift sponsor={self.sponsor_id} active={self.active}'


class WhatsAppMessage(models.Model):
    """Audit log of every outbound WhatsApp send attempt (Twilio).

    Comms are best-effort, so one row is written per attempt: delivery stays
    auditable and failures are visible. ``status`` mirrors Twilio's message status
    where known (queued→sent→delivered, or failed/undelivered)."""
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('undelivered', 'Undelivered'),
    ]
    # SET_NULL (not CASCADE): the message log outlives a deleted application.
    application = models.ForeignKey(
        'ScholarshipApplication', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='whatsapp_messages',
    )
    kind = models.CharField(max_length=50, blank=True, default='')  # e.g. 'interview_reminder_1day'
    to_number = models.CharField(max_length=32, blank=True, default='')  # E.164, or the raw value on a bad number
    body = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    provider_sid = models.CharField(max_length=64, blank=True, default='')  # Twilio message SID
    error = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'whatsapp_messages'
        ordering = ['-created_at']

    def __str__(self):
        return f'WA {self.kind} → {self.to_number} [{self.status}]'
