"""TD-204 — the engineer's analysis becomes a record (owner, 2026-07-31).

Creates ``org_request_analyses``: the working paper behind ONE comment. The prose still travels as
an ``OrgRequestComment``, so the discussion stays one stream; this table holds the evidence (cited
files, hours) and the approval lifecycle a comment cannot carry. See the model docstring for why it
is not columns on ``OrgRequestComment``, and for why ``cited_files`` and ``estimated_hours`` are
OWNER-ONLY.

Also widens ``OrgRequestComment.author_kind`` with ``engineer``. That half is CHOICES-ONLY — Django
emits no DDL for it on Postgres (there is no CHECK constraint on the column), so the only thing the
production database needs is the new table plus the ``django_migrations`` row.

⚠ **MIGRATE-FIRST. Cloud Build NEVER runs `migrate`** — apply this to production via Supabase MCP
BEFORE pushing, or the new code 500s on a table that does not exist. Additive only, so the old code
keeps working between the DDL and the deploy.

⚠ The dev DB here is SQLite, so `sqlmigrate` emits SQLite DDL — do NOT paste that at Postgres. The
statement below is the Postgres form, its column types matched against the sibling table
``org_request_comments`` (id `bigserial`, timestamps `timestamptz`, FKs `bigint`, JSON `jsonb`).
The index NAMES are Django's own (taken from `sqlmigrate`, which is dialect-specific but names are
not) — they must match, or a later `migrate` will try to create them again.

    CREATE TABLE org_request_analyses (
        id                bigserial     PRIMARY KEY,
        org_request_id    bigint        NOT NULL REFERENCES org_requests (id) ON DELETE CASCADE
                                            DEFERRABLE INITIALLY DEFERRED,
        body              text          NOT NULL,
        estimated_hours   numeric(6,1)  NULL,
        cited_files       jsonb         NOT NULL,
        authored_by       varchar(50)   NOT NULL,
        repo_sha          varchar(40)   NOT NULL,
        description_sha   varchar(64)   NOT NULL,
        approved_at       timestamptz   NULL,
        approved_by_id    bigint        NULL REFERENCES partner_admins (id) ON DELETE SET NULL
                                            DEFERRABLE INITIALLY DEFERRED,
        posted_comment_id bigint        NULL REFERENCES org_request_comments (id) ON DELETE SET NULL
                                            DEFERRABLE INITIALLY DEFERRED,
        superseded_at     timestamptz   NULL,
        created_at        timestamptz   NOT NULL,
        updated_at        timestamptz   NOT NULL
    );
    CREATE INDEX org_request_analyses_org_request_id_cdb34604
        ON org_request_analyses (org_request_id);
    CREATE INDEX org_request_analyses_approved_by_id_fa55c942
        ON org_request_analyses (approved_by_id);
    CREATE INDEX org_request_analyses_posted_comment_id_a2db6d60
        ON org_request_analyses (posted_comment_id);
    CREATE INDEX org_request_org_req_fc3c08_idx
        ON org_request_analyses (org_request_id, id);

    -- RLS in the SAME transaction as the CREATE (docs/incident-001-rls-disabled.md). Django
    -- reaches Postgres as the service role; nothing else may read an analysis — and this table
    -- holds the file paths and hours the requesting organisation must never see.
    ALTER TABLE org_request_analyses ENABLE ROW LEVEL SECURITY;
    CREATE POLICY "Backend service role only" ON org_request_analyses
        FOR ALL TO service_role USING (true) WITH CHECK (true);

    INSERT INTO django_migrations (app, name, applied)
        VALUES ('scholarship', '0140_org_request_analysis', NOW());

POST-CHECK, and check the table the MODEL uses — a same-named legacy twin has swallowed an ALTER
silently on this project before:
  * `SELECT count(*) FROM org_request_analyses;` → 0 (nothing is backfilled; every analysis is
    written deliberately by the engineer);
  * `SELECT relrowsecurity FROM pg_class WHERE relname='org_request_analyses';` → true;
  * `SELECT count(*) FROM pg_policies WHERE tablename='org_request_analyses';` → 1;
  * Supabase Security Advisor reports no new finding.

⚠ `manage.py migrate` can exit NON-ZERO on success here (`django_content_type` missing, TD-058).
A non-zero exit is not a failure — verify the columns and the `django_migrations` row directly.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0067_reconcile_module_flags'),
        ('scholarship', '0139_clarifications_to_comments'),
    ]

    operations = [
        migrations.AlterField(
            model_name='orgrequestcomment',
            name='author_kind',
            field=models.CharField(choices=[('ai', 'AI reviewer'), ('owner', 'Platform owner'), ('org', 'Requesting organisation'), ('engineer', 'Engineer')], max_length=10),
        ),
        migrations.CreateModel(
            name='OrgRequestAnalysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField()),
                ('estimated_hours', models.DecimalField(blank=True, decimal_places=1, max_digits=6, null=True)),
                ('cited_files', models.JSONField(blank=True, default=list)),
                ('authored_by', models.CharField(blank=True, default='', max_length=50)),
                ('repo_sha', models.CharField(blank=True, default='', max_length=40)),
                ('description_sha', models.CharField(blank=True, default='', max_length=64)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('superseded_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_org_request_analyses', to='courses.partneradmin')),
                ('org_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analyses', to='scholarship.orgrequest')),
                ('posted_comment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='scholarship.orgrequestcomment')),
            ],
            options={
                'verbose_name_plural': 'org request analyses',
                'db_table': 'org_request_analyses',
                'ordering': ['id'],
                'indexes': [models.Index(fields=['org_request', 'id'], name='org_request_org_req_fc3c08_idx')],
            },
        ),
    ]
