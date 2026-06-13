# Renumbered 0054→0055 at merge: `spm-catalogue` landed `0054_course_is_active` first, so this
# (the new CourseDataStatus model) chains after it for a linear history. New table → enable RLS
# at deploy (service-role-only, deny-by-default).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0054_course_is_active'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseDataStatus',
            fields=[
                ('key', models.CharField(
                    choices=[
                        ('epanduan_stpm', 'e-Panduan — STPM refresh'),
                        ('epanduan_spm', 'e-Panduan — SPM refresh'),
                        ('uptvet', 'UP_TVET inventory'),
                        ('emasco', 'eMASCO occupations'),
                        ('link_health', 'Catalogue link health'),
                        ('audit', 'Data audit'),
                    ],
                    max_length=40, primary_key=True, serialize=False)),
                ('last_run_at', models.DateTimeField(help_text='When the tool that writes this key last completed')),
                ('summary', models.JSONField(blank=True, default=dict, help_text='Run summary (counts/findings) for display')),
                ('detail', models.TextField(blank=True, default='', help_text='Optional human note / command used')),
            ],
            options={
                'db_table': 'course_data_status',
                'verbose_name_plural': 'Course data statuses',
            },
        ),
    ]
