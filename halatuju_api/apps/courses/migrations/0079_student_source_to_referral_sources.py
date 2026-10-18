"""Sources and referral partners, Sprint B (2026-10-18): `StudentProfile.source` names the new
`referral_sources` table (scholarship 0173) instead of `partner_organisations`.

A CONSTRAINT SWAP, not a data change: scholarship 0173 copied every source row keeping its id, and
refused to run if any `api_student_profiles.source_id` named a row it did not copy. The column, its
name and every value stay. `referred_by_org` (the REFERRAL PARTNER column) is untouched — it keeps
naming `partner_organisations`, where the platform's referral partners stay.

⚠ MIGRATE-FIRST with scholarship 0173, in the SAME transaction — `docs/scholarship/sources-b-cutover-sql.md`.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0078_two_referral_columns'),
        ('scholarship', '0173_referral_sources'),
    ]

    operations = [
        migrations.AlterField(
            model_name='studentprofile',
            name='source',
            field=models.ForeignKey(blank=True, help_text='The SOURCE the student named on the bursary form (NULL for a fixed choice). Independent of referred_by_org.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sourced_students', to='scholarship.referralsource'),
        ),
    ]
