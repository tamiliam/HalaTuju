from django.db import migrations, models


def seed_trust_content(apps, schema_editor):
    """Seed ONE active TrustContent row with honest, illustrative placeholders.
    The organisation is not yet formalised — legal entity / trustees / auditor are
    deliberately empty (the FE shows trilingual 'to be published' copy); the
    sources/uses + assurance figures mirror the approved prototype and are flagged
    ``figures_are_illustrative`` so the hub conveys the IR-style SHAPE without
    fabricating real accounts."""
    TrustContent = apps.get_model('scholarship', 'TrustContent')
    if TrustContent.objects.exists():
        return
    TrustContent.objects.create(
        legal_entity='',
        contact_email='help@halatuju.xyz',
        trustees=[],
        sources=[
            {'label': 'Sponsor donations', 'amount': '312000'},
            {'label': 'Grants', 'amount': '40000'},
        ],
        uses=[
            {'label': 'Gifts to students', 'amount': '284000'},
            {'label': 'Held for committed students', 'amount': '52000'},
            {'label': 'Running costs', 'amount': '16000'},
        ],
        assurance={
            'fy': 'FY2025',
            'students_verified': 112,
            'disbursed': '284000',
            'auditor': '',
            'report_url': '',
        },
        figures_are_illustrative=True,
        is_active=True,
    )


def unseed_trust_content(apps, schema_editor):
    apps.get_model('scholarship', 'TrustContent').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0064_review_sla_nudges'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='enrolment_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='TrustContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('legal_entity', models.CharField(blank=True, default='', max_length=300)),
                ('contact_email', models.EmailField(blank=True, default='help@halatuju.xyz', max_length=254)),
                ('trustees', models.JSONField(blank=True, default=list)),
                ('sources', models.JSONField(blank=True, default=list)),
                ('uses', models.JSONField(blank=True, default=list)),
                ('assurance', models.JSONField(blank=True, default=dict)),
                ('figures_are_illustrative', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'trust_content',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.RunPython(seed_trust_content, unseed_trust_content),
    ]
