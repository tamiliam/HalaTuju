"""Sources-and-referrals Sprint D (2026-10-19), the CONTRACT half — IMAGE-FIRST.

Drops two columns nothing reads any more:
- `api_student_profiles.source_id` — the profile's bursary source (Sprint A). Since Sprint C every
  bursary reader uses the APPLICATION's own source (`ScholarshipApplication.source`); since Sprint D
  nothing writes it either.
- `partner_organisations.show_in_apply` — the old "offered on the apply form" flag; sources carry
  their own (`referral_sources.show_in_apply`) since Sprint B.

⚠ IMAGE-FIRST — THE OPPOSITE OF MIGRATE-FIRST. Every image before Sprint D SELECTs both columns on
every read of its table (they are in the models' field lists), so dropping them while such an image
serves 500s every profile and organisation read. The order:
1. courses 0081 by hand (migrate-first), push, confirm the new revision is the one serving
   (`status.latestReadyRevisionName`, no older revision carrying traffic);
2. THEN the OWNER runs this drop in the Supabase SQL Editor with its backup table and ledger row —
   the "After the deploy" section of `docs/scholarship/sources-d-cutover-sql.md`.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0081_retire_old_source_rows'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='partnerorganisation',
            name='show_in_apply',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='source',
        ),
    ]
