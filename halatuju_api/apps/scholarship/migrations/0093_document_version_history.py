# Document version history (Documents-box reorg Phase 2): retain replaced
# documents as "superseded" instead of hard-deleting them. Additive, 0-row-safe,
# applied migrate-first via Supabase MCP (the deploy does NOT run migrate).

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0092_qc_gap_override'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicantdocument',
            name='superseded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='applicantdocument',
            name='superseded_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='supersedes', to='scholarship.applicantdocument'),
        ),
    ]
