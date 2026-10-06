"""A shop flagged for review by ONE organisation, and the notes log behind it (request #28
follow-up, 2026-10-06).

⚠⚠ **A FLAG IS AN ORGANISATION'S, A CATEGORY IS EVERYBODY'S.** `MerchantCategory` is one row per
shop for the whole platform (a shop's category is a fact about the shop). A flag is the opposite:
"we are looking into this shop" is one organisation's working note, and another organisation must
never see it, count it, or be told it exists. So the flag carries its organisation and is unique on
(organisation, merchant) — two organisations flagging the same shop hold two unrelated flags.

⚠ **A FLAG NEVER CHANGES THE MONEY.** Nothing here is read by the category, the chart or any total;
`spend_report` does not import this module. Flagging is a question a person is asking, not an
answer about where the money went.

⚠ **NOTHING IS EVER DELETED.** Clearing a flag closes it and writes the closing note; re-flagging
reopens the SAME row, so the history reads as one log. The notes are `PROTECT`ed against their flag
for the same reason.
"""
from django.db import models
from django.db.models import Q

#: The longest note a person may write. Bounded at the column, so an over-long body is a clean
#: `note_too_long` from `merchant_flags.py` rather than a database rollback.
NOTE_MAX = 2000


class MerchantFlag(models.Model):
    """One organisation's flag on one shop. Opened, noted, cleared and reopened — never deleted."""
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT, related_name='merchant_flags',
        help_text='The ONE organisation this flag belongs to. Never shown to any other.')
    #: Normalised by `spending_import.norm_text`, exactly as `BursarySpendTxn.merchant` is, so the
    #: flag and the shop's payments name the shop the same way.
    merchant = models.CharField(max_length=255)
    is_open = models.BooleanField(default=True)
    #: When it was last opened (or reopened), and by whom.
    opened_at = models.DateTimeField()
    opened_by_email = models.CharField(max_length=254, blank=True, default='')
    #: When it was last cleared; NULL while open. The notes keep every earlier clearing.
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by_email = models.CharField(max_length=254, blank=True, default='')

    class Meta:
        db_table = 'merchant_flags'
        constraints = [
            models.UniqueConstraint(fields=['organisation', 'merchant'],
                                    name='merchant_flag_one_per_org_shop'),
        ]

    def __str__(self):
        return f'MerchantFlag org={self.organisation_id} {self.merchant} open={self.is_open}'


class MerchantFlagNote(models.Model):
    """One entry in a flag's log: why it was opened, a note added, or why it was cleared."""
    KIND_CHOICES = [('open', 'Flagged'), ('note', 'Note'), ('close', 'Cleared')]

    flag = models.ForeignKey(MerchantFlag, on_delete=models.PROTECT, related_name='notes')
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    body = models.CharField(max_length=NOTE_MAX)
    author_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'merchant_flag_notes'
        # OLDEST FIRST: the log reads top to bottom as it happened — why it was flagged, what was
        # found, why it was cleared.
        ordering = ['created_at', 'id']
        constraints = [
            # A note with nothing in it is not a note. The service strips and refuses first; this
            # is the floor under it.
            models.CheckConstraint(condition=~Q(body=''), name='merchant_flag_note_not_blank'),
        ]

    def __str__(self):
        return f'MerchantFlagNote {self.kind} flag={self.flag_id}'
