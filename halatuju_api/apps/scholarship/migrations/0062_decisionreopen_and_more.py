# Generated for the decision-reopen sprint 2026-06-18

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0057_studentprofile_chosen_pathway_and_more'),
        ('scholarship', '0061_scholarshipapplication_interview_booked_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='decision_reopened_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='DecisionReopen',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reopened_by', models.CharField(blank=True, default='', help_text='Email of the superadmin who reopened the decision.', max_length=254)),
                ('reason', models.TextField(help_text='Why the decision was reopened (the asserted reviewer error).')),
                ('was_published', models.BooleanField(default=False)),
                ('resulted_in_change', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('application', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='decision_reopens', to='scholarship.scholarshipapplication')),
                ('reviewer', models.ForeignKey(blank=True, help_text='The reviewer the correction is attributed to (assigned reviewer at reopen).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='decision_reopens_attributed', to='courses.partneradmin')),
            ],
            options={
                'db_table': 'decision_reopens',
                'ordering': ['-created_at'],
            },
        ),
    ]
