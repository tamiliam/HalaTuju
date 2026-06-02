# Generated for Verification-verdict Sprint 5 — additive verdict-audit / override capture.
# Additive ALTERs on an existing table → deploy migrate-first via the simpler MCP
# execute_sql path (no contenttypes/auth workaround needed; that is only for new models).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0036_resolutionitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='ai_verdict_snapshot',
            field=models.JSONField(blank=True, default=list, help_text='The four-fact verification verdict (build_verdict) captured when the officer recorded their decision. List of {fact,status,evidence,unresolved}.'),
        ),
        migrations.AddField(
            model_name='scholarshipapplication',
            name='officer_verdict',
            field=models.JSONField(blank=True, default=dict, help_text="The officer's own four-fact decision at the cockpit: {identity,academic,income,pathway: 'pass'|'fail', overall: 'accept'|'decline'|'hold'}."),
        ),
        migrations.AddField(
            model_name='scholarshipapplication',
            name='verdict_reason',
            field=models.TextField(blank=True, default='', help_text="The officer's free-text reason/notes recorded with the verdict."),
        ),
        migrations.AddField(
            model_name='scholarshipapplication',
            name='verdict_decided_by',
            field=models.CharField(blank=True, default='', help_text='Email of the PartnerAdmin who recorded the verification verdict.', max_length=254),
        ),
        migrations.AddField(
            model_name='scholarshipapplication',
            name='verdict_decided_at',
            field=models.DateTimeField(blank=True, null=True, help_text='When the officer recorded their verification verdict (the audit anchor).'),
        ),
    ]
