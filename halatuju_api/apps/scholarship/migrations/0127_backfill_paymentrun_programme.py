"""Payment runs carry their programme (P2b, 2026-07-26) — backfill.

Sets each existing run's programme from the students already in it. This asserts nothing new: a
run's items already point at applications that already carry a programme (P1a), so the backfill
only writes down a fact the data already implied.

**INVARIANT — the one that matters:** this migration must not change ANY run's item set, amount,
status or signature. It writes exactly one column. Verified on prod before applying: all 5 runs
belong to org 11 and **each already spans exactly one programme**, so there is no run for which
"its programme" is ambiguous.

A run whose items span MORE than one programme is left NULL rather than guessed — that would be a
run this sprint's rule says should never have existed, and silently picking one of its programmes
would attribute another gift's students to it. It surfaces as an unassigned run instead.
A run with no items is left NULL (nothing to derive from).

Reverse: clears the column. Safe — nothing reads it until the code that follows this migration
deploys, and re-running the forward pass reproduces the same values from the same items.

MIGRATE-FIRST PROD SQL (hand-written; run AFTER 0126):

    -- assign each run the single programme its items share
    UPDATE payment_runs r SET programme_id = s.pid
    FROM (
        SELECT i.run_id, MIN(a.programme_id) AS pid
        FROM payment_run_items i
        JOIN scholarship_applications a ON a.id = i.application_id
        WHERE a.programme_id IS NOT NULL
        GROUP BY i.run_id
        HAVING COUNT(DISTINCT a.programme_id) = 1
    ) s
    WHERE r.id = s.run_id AND r.programme_id IS NULL;

Post-checks (all three must hold):
  1. every run with items has a programme:
     SELECT count(*) FROM payment_runs r WHERE r.programme_id IS NULL
       AND EXISTS (SELECT 1 FROM payment_run_items i WHERE i.run_id = r.id);   -- expect 0
  2. no run disagrees with its own students:
     SELECT count(*) FROM payment_run_items i
       JOIN payment_runs r ON r.id = i.run_id
       JOIN scholarship_applications a ON a.id = i.application_id
      WHERE r.programme_id IS NOT NULL AND a.programme_id IS DISTINCT FROM r.programme_id;  -- 0
  3. the OPEN DRAFT run PR-2026-08-01 still has exactly 30 items and the same total as before.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    PaymentRun = apps.get_model('scholarship', 'PaymentRun')
    for run in PaymentRun.objects.filter(programme__isnull=True):
        programme_ids = set(
            run.items.exclude(application__programme__isnull=True)
            .values_list('application__programme_id', flat=True)
        )
        if len(programme_ids) == 1:
            run.programme_id = programme_ids.pop()
            run.save(update_fields=['programme'])
        # 0 → nothing to derive from; >1 → ambiguous, leave for a human. Never guess.


def unbackfill(apps, schema_editor):
    PaymentRun = apps.get_model('scholarship', 'PaymentRun')
    PaymentRun.objects.update(programme=None)


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0126_paymentrun_programme'),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
