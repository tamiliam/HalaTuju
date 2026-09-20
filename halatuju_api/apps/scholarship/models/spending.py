"""
Vircle spending: a bursary transaction and the merchant category behind it.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

# ── Vircle spending (sponsor spending reporting) ──────────────────────────────
#
# Plan: docs/plans/2026-09-10-sponsor-spending-roadmap.md
# Requirements + the measured corpus: docs/plans/2026-09-09-sponsor-spending-reports-brief.md

#: The ten sponsor-facing spending categories. **CLOSED VOCABULARY** — every rung of the sorter,
#: including the AI one, may only answer with a code from this list; anything else is discarded.
#:
#: ⚠ `transfer` IS DECIDED BY `duitnow_type`, NEVER BY THE MERCHANT'S NAME. Half the real merchants
#: are registered under an individual's name (hawker stalls, sundry shops), so name-shape matching
#: would file a student's daily meals as money sent to a friend — the most damaging thing this
#: feature could get wrong. In two months of real data NO student sent money to a person; the
#: category exists for the day one does, and an empty slice is simply absent from the chart.
#:
#: ⚠ `unsorted` IS NOT A FAILURE STATE, IT IS AN HONEST ONE. It is what stops the other nine
#: reading as complete when they are not. Never fold it into "other" and never hide it.
SPEND_CATEGORY_CHOICES = [
    ('food', 'Food & drink'),
    ('groceries', 'Groceries'),
    ('transport', 'Transport'),
    ('study', 'Books & study supplies'),
    ('phone', 'Phone & internet'),
    ('hostel', 'Hostel & bills'),
    ('health', 'Health & pharmacy'),
    ('clothing', 'Clothing & shoes'),
    ('transfer', 'Sent to a person'),
    ('unsorted', 'Not yet sorted'),
]

#: WHICH RUNG of the sorter decided a category — see the roadmap's four-rung ladder.
#: ⚠ `owner` OUTRANKS EVERY OTHER RUNG AND IS NEVER OVERWRITTEN by a re-run. That is the whole
#: point of storing this: without it the card cannot tell a fact from an estimate, and the
#: assumptions note under the chart becomes unwriteable.
SPEND_DECIDED_BY_CHOICES = [
    ('', 'Not yet decided'),
    ('duitnow', 'From the DuitNow type'),
    ('rule', 'From the merchant name'),
    ('inferred', 'Inferred from the spending pattern'),
    ('ai', 'Decided by the model'),
    ('owner', 'Set by a person'),
]


class BursarySpendTxn(models.Model):
    """One transaction from a Vircle "Bursary Usage Report", filed against a student.

    ⚠ **`txn_id` UNIQUENESS IS THE ONLY THING STOPPING DOUBLE-COUNTING.** The weekly exports are
    pulled by hand and CAN overlap: the 2 August 2026 export was run with its date range a week
    early and re-included all 186 rows of 26 July. Every repeated pair was byte-identical, so
    first-copy-wins is safe — but a repeat whose fields DISAGREE is a corrected figure and must be
    reported to a human, never silently kept or silently replaced.

    ⚠ **THE STUDENT'S NAME FROM THE REPORT IS NOT HERE, DELIBERATELY.** It is read at import only
    to cross-check the wallet match and then discarded. `wallet_id` is kept because it is the join
    key and the thing an alert must name when no student matches.

    ⚠ **NON-SPEND ROWS ARE STORED.** Two rows in the first two months are `RECEIVED` — money into
    a wallet from a person. Filtering them at import would make this table unable to answer a
    question we were handed the data for. Readers narrow on `tx_type`; the importer does not.

    ⚠ **`entry_type` READS `CREDIT` ON A SPEND** — it is the counterparty's view of the ledger.
    It is stored for the record and gated on by nothing.
    """
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.PROTECT, related_name='spend_txns',
        help_text='Resolved from wallet_id. A row whose wallet matches no student is NOT stored '
                  '- it is reported, because money filed against nobody is worse than money we '
                  'have flagged.',
    )
    txn_id = models.CharField(
        max_length=64, unique=True,
        help_text="Vircle's own transaction id - the idempotency key.")
    txn_date = models.DateField(
        help_text='Date only. The time of day is discarded at import: newer reports no longer '
                  'carry it, and no sponsor may ever see what hour a student ate.')
    wallet_id = models.CharField(max_length=32, db_index=True)
    merchant = models.CharField(
        max_length=255,
        help_text='The shop, upper-cased and whitespace-collapsed. NEVER shown to a sponsor.')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    duitnow_type = models.CharField(max_length=64, blank=True, default='')
    entry_type = models.CharField(max_length=16, blank=True, default='')
    tx_type = models.CharField(max_length=16, blank=True, default='')
    status = models.CharField(max_length=8, blank=True, default='')
    #: Derived at import from `duitnow_type` and stored, so no reader re-derives it from a name.
    is_person_transfer = models.BooleanField(default=False)
    #: True when the wallet is held by a PARENT and the student rides on it as a child (Vircle
    #: refuses an own account to anyone born after 2008). Live on 28 of the first 1,368 rows.
    spender_is_child = models.BooleanField(default=False)
    category = models.CharField(
        max_length=16, blank=True, default='', choices=SPEND_CATEGORY_CHOICES,
        help_text="Blank until the sorter runs; 'unsorted' means it ran and could not place it. "
                  'The two are different states and must not be collapsed.')
    decided_by = models.CharField(
        max_length=16, blank=True, default='', choices=SPEND_DECIDED_BY_CHOICES)
    source_file = models.CharField(max_length=255, blank=True, default='')
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bursary_spend_txns'
        ordering = ['-txn_date', '-id']
        indexes = [
            models.Index(fields=['application', 'txn_date']),
            models.Index(fields=['merchant']),
        ]

    def __str__(self):
        return f'{self.txn_date} {self.merchant} RM{self.amount} [{self.txn_id}]'


class MerchantCategory(models.Model):
    """One shop's category, remembered so it is decided once and never re-asked.

    ⚠ **THIS TABLE IS WHY THE AI COST FALLS TO ALMOST NOTHING.** A student buys from the same stall
    every week. Asking the model per TRANSACTION would pay for the same answer for years; asking
    per MERCHANT and storing it means week one is expensive and week twenty is free. 290 distinct
    merchants produced 1,368 transactions in the first two months, and the list grows slowly.

    ⚠ **`decided_by='owner'` IS FINAL.** A re-run of any rung must leave it alone. A person
    correcting a category is the highest authority in the ladder, and losing that to the next
    sweep would make the correction screen a lie.

    ⚠ **`merchant` IS STORED NORMALISED** (upper-cased, whitespace-collapsed) by
    `spending_import.norm_text`, because `'99  Speedmart '` and `'99 SPEEDMART'` are one shop.
    Write it through that function or the same shop gets two rows and two answers.
    """
    merchant = models.CharField(max_length=255, unique=True)
    category = models.CharField(max_length=16, choices=SPEND_CATEGORY_CHOICES)
    decided_by = models.CharField(max_length=16, choices=SPEND_DECIDED_BY_CHOICES)
    #: Why the model or the rule chose it - kept for the officer's weekly review, never shown to
    #: a sponsor. Free text; may be blank for a rule, which explains itself.
    reason = models.CharField(max_length=255, blank=True, default='')
    decided_at = models.DateTimeField(auto_now=True)
    decided_by_email = models.CharField(
        max_length=254, blank=True, default='',
        help_text="Set only when decided_by='owner' - the audit trail for a human correction.")

    class Meta:
        db_table = 'merchant_categories'
        ordering = ['merchant']

    def __str__(self):
        return f'{self.merchant} -> {self.category} ({self.decided_by})'
