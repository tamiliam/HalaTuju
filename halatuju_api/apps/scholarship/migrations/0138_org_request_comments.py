"""TD-201 — the Requests thread becomes a DISCUSSION (owner, 2026-07-31).

Creates ``org_request_comments``, which replaces ``OrgRequest.clarifications`` (a JSONField of
``{question, answer}`` PAIRS). A question becomes a comment awaiting a reply, so statements, second
voices and remarks-expecting-no-reply all live in one stream. See the model docstring for why
``visibility`` exists from the first migration rather than being retrofitted.

⚠ **MIGRATE-FIRST. Cloud Build NEVER runs `migrate`** — apply this to production via Supabase MCP
BEFORE pushing, or the new code 500s on a table that does not exist. Additive only, so old code
keeps working between the DDL and the deploy.

⚠ The dev DB here is SQLite, so `sqlmigrate` emits SQLite DDL — do NOT paste that at Postgres. The
statement below is the Postgres form, its column types matched against the sibling table
``org_request_attachments`` on production (id `bigserial`, timestamps `timestamptz`, FKs `bigint`).

    CREATE TABLE org_request_comments (
        id              bigserial     PRIMARY KEY,
        org_request_id  bigint        NOT NULL REFERENCES org_requests (id) ON DELETE CASCADE
                                          DEFERRABLE INITIALLY DEFERRED,
        author_kind     varchar(10)   NOT NULL,
        author_admin_id bigint        NULL REFERENCES partner_admins (id) ON DELETE SET NULL
                                          DEFERRABLE INITIALLY DEFERRED,
        body            text          NOT NULL,
        visibility      varchar(10)   NOT NULL DEFAULT 'shared',
        awaiting_reply  boolean       NOT NULL DEFAULT false,
        replied_at      timestamptz   NULL,
        created_at      timestamptz   NOT NULL
    );
    CREATE INDEX org_request_comments_author_admin_id_ab807327
        ON org_request_comments (author_admin_id);
    CREATE INDEX org_request_comments_org_request_id_344516a6
        ON org_request_comments (org_request_id);
    CREATE INDEX org_request_org_req_be446d_idx
        ON org_request_comments (org_request_id, id);

    -- RLS in the SAME transaction as the CREATE (docs/incident-001-rls-disabled.md). Django
    -- reaches Postgres as the service role; nothing else may read a comment.
    ALTER TABLE org_request_comments ENABLE ROW LEVEL SECURITY;
    CREATE POLICY "Backend service role only" ON org_request_comments
        FOR ALL TO service_role USING (true) WITH CHECK (true);

    INSERT INTO django_migrations (app, name, applied)
        VALUES ('scholarship', '0138_org_request_comments', NOW());

POST-CHECK, and check the table the MODEL uses — a same-named legacy twin has swallowed an ALTER
silently on this project before:
  * `SELECT count(*) FROM org_request_comments;` → 0 (0139 backfills it, not this one);
  * `SELECT relrowsecurity FROM pg_class WHERE relname='org_request_comments';` → true;
  * Supabase Security Advisor reports no new finding.

⚠ `manage.py migrate` can exit NON-ZERO on success here (`django_content_type` missing, TD-058).
A non-zero exit is not a failure — verify the columns and the `django_migrations` row directly.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0067_reconcile_module_flags'),
        ('scholarship', '0137_pre_decline_award_amount'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrgRequestComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('author_kind', models.CharField(choices=[('ai', 'AI reviewer'), ('owner', 'Platform owner'), ('org', 'Requesting organisation')], max_length=10)),
                ('body', models.TextField()),
                ('visibility', models.CharField(choices=[('shared', 'Shared with the organisation'), ('internal', 'Platform-internal only')], default='shared', max_length=10)),
                ('awaiting_reply', models.BooleanField(default=False)),
                ('replied_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author_admin', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='org_request_comments', to='courses.partneradmin')),
                ('org_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='scholarship.orgrequest')),
            ],
            options={
                'db_table': 'org_request_comments',
                'ordering': ['id'],
                'indexes': [models.Index(fields=['org_request', 'id'], name='org_request_org_req_be446d_idx')],
            },
        ),
    ]
