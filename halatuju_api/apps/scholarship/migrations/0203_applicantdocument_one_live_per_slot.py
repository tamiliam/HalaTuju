"""TD-115 (audit A1.8, 2026-11-06): the DATABASE guard on the document slot.

One LIVE `applicant_documents` row per slot, where the slot is the 4-column key
(application, doc_type, household_member, request_code). request_code joined the key with TD-134
(0067), so each officer request is its own slot; a 3-column key would refuse the request-keyed
uploads TD-134 exists for. "Live" = `superseded_at IS NULL` (`ApplicantDocument.live`).

- A PARTIAL UNIQUE INDEX (Django `UniqueConstraint` with a `condition`). No column changes, no data
  change. Both text columns are NOT NULL with default '' (and the live data holds no NULL), so NULLS
  DISTINCT never comes into play and `nulls_distinct` is not needed.
- CARVE-OUT: `request_code = 'in_programme'` (`results_review.SLIP_REQUEST_CODE`). An in-programme
  results slip is EVIDENCE, one per semester, recorded and never replaced (`results_review.record_slip`),
  so several live ones per application are by design. The index leaves them out.
- The app layer already supersedes before a row goes live; A1.8 fixed the five writers that put the
  new row live FIRST (views upload create, refile_to_spm / refile_to_higher, dedupe_income_proof's STR
  re-tag, split_combined_results, backfill_untagged_income_docs). Two uploads at once now meet an
  IntegrityError instead of a silent duplicate; the upload door answers it cleanly (see views.py).
⚠ THIS ONE IS DEPLOY-FIRST, NOT MIGRATE-FIRST. The house rule (migrate first) exists so the OLD image
is safe on the NEW schema. Here it is not: the old image's upload door creates every re-upload LIVE
and supersedes after, so with the index in place every same-slot re-upload on the old image would
500. The NEW image is safe with or without the index (it only adds a guard). So: push -> CONFIRM the
new api revision serves 100% (`status.latestReadyRevisionName`) -> then steps 1-3 below, by hand
(scholarship ledger 0202 -> 0203). Until step 2 the ledger shows 0203 missing; that gap is expected
and is closed by step 2. `sqlmigrate` renders for the LOCAL backend (SQLite); this is the Postgres DDL,
rendered offline with Django's postgresql schema editor from this constraint.

1. PRE-CHECK (read-only). Must return 0 rows; any row -> STOP, the owner decides each duplicate by rule:

    SELECT application_id, doc_type, household_member, request_code, count(*) AS live_rows,
           array_agg(id ORDER BY uploaded_at DESC, id DESC) AS ids
    FROM applicant_documents
    WHERE superseded_at IS NULL AND request_code <> 'in_programme'
    GROUP BY application_id, doc_type, household_member, request_code
    HAVING count(*) > 1;

   And (must be 0): SELECT count(*) FROM applicant_documents
                    WHERE household_member IS NULL OR request_code IS NULL;

2. APPLY, one transaction, index and ledger row together. A plain CREATE (not CONCURRENTLY): the
   house rule puts the DDL and the ledger row in ONE transaction, and CONCURRENTLY cannot run inside
   one. The table is ~3.3k rows, so the build takes milliseconds; it holds a SHARE lock (reads go on,
   writes wait) only that long. The lock_timeout makes it give up, not queue, behind a long writer:

    BEGIN;
    SET LOCAL lock_timeout = '5s';
    CREATE UNIQUE INDEX "applicant_document_one_live_per_slot" ON "applicant_documents" ("application_id", "doc_type", "household_member", "request_code") WHERE ("superseded_at" IS NULL AND NOT ("request_code" = 'in_programme'));
    INSERT INTO django_migrations (app, name, applied) VALUES ('scholarship', '0203_applicantdocument_one_live_per_slot', now());
    COMMIT;

   If it fails with "could not create unique index" a duplicate slipped in after the pre-check: the
   transaction rolled back, nothing changed; re-run step 1.

3. READ BACK: SELECT indexdef FROM pg_indexes WHERE indexname = 'applicant_document_one_live_per_slot';
   and SELECT name FROM django_migrations WHERE app = 'scholarship' AND name LIKE '0203%';
   Then the Supabase Security Advisor (0 errors) and `list_migrations`.

ROLLBACK (one transaction; the code stays safe without the index, it only loses the guard):

    BEGIN;
    DROP INDEX IF EXISTS "applicant_document_one_live_per_slot";
    DELETE FROM django_migrations WHERE app = 'scholarship' AND name = '0203_applicantdocument_one_live_per_slot';
    COMMIT;
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0202_staff_activity_interview_drafted'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='applicantdocument',
            constraint=models.UniqueConstraint(condition=models.Q(('superseded_at__isnull', True), models.Q(('request_code', 'in_programme'), _negated=True)), fields=('application', 'doc_type', 'household_member', 'request_code'), name='applicant_document_one_live_per_slot'),
        ),
    ]
