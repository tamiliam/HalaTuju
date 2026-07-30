"""TD-201 — move the live clarification threads into ``org_request_comments``.

Data only, no DDL. Every ``OrgRequest.clarifications`` entry becomes ONE or TWO comments:

  * the question  → ``author_kind`` from ``asked_by`` ('ai' when absent, which is what it meant
    before 2026-07-30), ``awaiting_reply=True`` when no answer was ever given;
  * the answer    → ``author_kind='org'``, posted after it, and the question's ``awaiting_reply``
    cleared with ``replied_at`` stamped.

⚠ **This is an ADOPTED path, not a new one.** The standing lesson is that routing live behaviour
through new machinery switches it off silently — the threads here are real conversations on real
requests, and a bug that drops one is invisible at ship time because nothing errors. So the
counts are asserted per request, not in aggregate, and `test_migration_0139.py` runs the same
transform over the shapes actually on production (answered, unanswered, owner-asked, empty).

⚠ **``clarifications`` IS NOT CLEARED and the column is NOT DROPPED here.** Deleting replaced code
immediately is the standing rule, but dropping the source in the same change that copies it out
removes any way to verify the copy against the original on production. Nothing READS it after this
sprint; the drop is logged as its own follow-up so it happens deliberately rather than as a
side-effect of this migration.

Reverse: deletes only the comments this migration created, identified by the request+body+author
triple, so a re-run is safe and a rollback cannot eat a comment somebody typed afterwards.

MIGRATE-FIRST: run via Supabase MCP with 0138, then record the row:
    INSERT INTO django_migrations (app, name, applied)
        VALUES ('scholarship', '0139_clarifications_to_comments', NOW());
Because this one is Python, run it through the ORM against production (see the sprint retro), or
apply the equivalent INSERT ... SELECT and verify the per-request counts below.

POST-CHECK: for every request, comments == questions + answers present in `clarifications`.
"""
from django.db import migrations


def _author_kind(entry):
    """'ai' | 'owner'. Absent ``asked_by`` means the AI — that is all there was before
    2026-07-30, and the same default the frontend renders."""
    asked_by = (entry.get('asked_by') or 'ai').strip().lower()
    return 'owner' if asked_by == 'owner' else 'ai'


def forwards(apps, schema_editor):
    OrgRequest = apps.get_model('scholarship', 'OrgRequest')
    Comment = apps.get_model('scholarship', 'OrgRequestComment')

    for req in OrgRequest.objects.exclude(clarifications=[]).exclude(clarifications=None):
        entries = req.clarifications or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            question = (entry.get('question') or '').strip()
            if not question:
                continue
            answer = (entry.get('answer') or '').strip()
            # The question. Shared by definition — it was already sent to the requester.
            q = Comment.objects.create(
                org_request=req,
                author_kind=_author_kind(entry),
                body=question,
                visibility='shared',
                awaiting_reply=not answer,
            )
            if answer:
                Comment.objects.create(
                    org_request=req,
                    author_kind='org',
                    body=answer,
                    visibility='shared',
                    awaiting_reply=False,
                )
                # Stamp the question as replied. `answered_at` is an ISO string in the JSON;
                # `created_at` is auto_now_add so it cannot be set here — the ordering by id
                # already puts the reply after its question, which is what the thread renders.
                q.awaiting_reply = False
                q.replied_at = q.created_at
                q.save(update_fields=['awaiting_reply', 'replied_at'])


def backwards(apps, schema_editor):
    """Delete only what `forwards` created — matched on the request + body + author triple, so a
    comment typed after the migration is never collateral."""
    OrgRequest = apps.get_model('scholarship', 'OrgRequest')
    Comment = apps.get_model('scholarship', 'OrgRequestComment')

    for req in OrgRequest.objects.exclude(clarifications=[]).exclude(clarifications=None):
        entries = req.clarifications or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            question = (entry.get('question') or '').strip()
            answer = (entry.get('answer') or '').strip()
            if question:
                Comment.objects.filter(org_request=req, body=question,
                                       author_kind=_author_kind(entry)).delete()
            if answer:
                Comment.objects.filter(org_request=req, body=answer,
                                       author_kind='org').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0138_org_request_comments'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
