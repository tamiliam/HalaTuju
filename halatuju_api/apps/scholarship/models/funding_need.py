"""
`FundingNeed` — "how you'd use the support" for one application.

Moved here VERBATIM from `models/applications.py` (sources-and-referrals Sprint C, 2026-10-19) so
that file — at its size cap — has room for the per-application source. Moves only: no field, no
`Meta`, no `db_table`, no `related_name` was touched. See `__init__.py`.
"""
from django.db import models

from .applications import ScholarshipApplication


class FundingNeed(models.Model):
    """
    "How you'd use the support" for one application — the S3 funding reframe
    (v2.4.2). Assistance is capped at RM3,000; instead of asking for an itemised
    total, the student ticks the categories the support would help with, may
    add an open note (incl. how they'd cope without), and gives a rough
    programme length. (The legacy per-line-item amount columns were dropped in
    TD-059 cleanup.)
    """
    application = models.OneToOneField(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='funding_need',
    )
    categories = models.JSONField(
        default=list, blank=True,
        help_text="Selected support categories: living/transport/accommodation/books/device/tuition/other",
    )
    funding_note = models.TextField(
        blank=True, default='',
        help_text="Open: how they'd use it / plan to fund studies / cope without",
    )
    programme_months = models.IntegerField(
        null=True, blank=True,
        help_text="Programme length in months",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'funding_needs'

    def __str__(self):
        return f'FundingNeed for application #{self.application_id}'
