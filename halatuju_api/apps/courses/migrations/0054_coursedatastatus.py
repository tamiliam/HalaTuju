# NOTE (parallel-branch numbering, lesson L#32): this is numbered 0054 off main's 0053.
# The `spm-catalogue` branch ALSO adds a 0054 (`0054_course_is_active`). They are independent
# (this adds a new model; that adds Course.is_active), both depending on 0053 → at merge they
# are two leaves: run `makemigrations --merge` (or renumber whichever lands second). Flagged in
# the retro + roadmap. New table → enable RLS at deploy (service-role-only, deny-by-default).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0053_alter_partneradmin_role'),
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
