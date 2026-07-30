"""Additive, nullable: the award_amount snapshot a cancelled decline restores from.

Pairs with services._record_reject now clearing award_amount on EVERY reject path (it was
cleared only by the verdict recorder, so an accept → reopen → interview-bucket decline kept
the amount; apps 21 and 71 did). No backfill: the column only ever describes a decline made
AFTER this ships, and NULL correctly means "nothing to restore" for every existing row —
including the two already-cleared records, whose amounts are deliberately not coming back.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0136_heal_missing_sponsor_memberships'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='pre_decline_award_amount',
            field=models.DecimalField(
                blank=True, decimal_places=2,
                help_text='award_amount snapshot taken when a decline cleared it; '
                          'cancel_pending_decline restores it (NULL = nothing to restore)',
                max_digits=10, null=True),
        ),
    ]
