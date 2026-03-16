"""Make field_key non-nullable on Course and StpmCourse.

All rows already have field_key populated in production (390 SPM + 1113 STPM).
The RunPython step handles any NULLs from migration 0017 (pre-U courses)
or local dev DBs that haven't run the backfill commands.
"""
from django.db import migrations, models
import django.db.models.deletion


# Deterministic field_key mapping for pre-U courses created by migration 0017
PREU_FIELD_KEYS = {
    'matric-sains': 'sains-hayat',
    'matric-kejuruteraan': 'mekanikal',
    'matric-sains-komputer': 'it-perisian',
    'matric-perakaunan': 'perakaunan',
    'stpm-sains': 'sains-hayat',
    'stpm-sains-sosial': 'sains-sosial',
}


def populate_null_field_keys(apps, schema_editor):
    """Set field_key for any Course/StpmCourse rows that still have NULL."""
    Course = apps.get_model('courses', 'Course')
    StpmCourse = apps.get_model('courses', 'StpmCourse')

    # Pre-U courses from migration 0017
    for course_id, key in PREU_FIELD_KEYS.items():
        Course.objects.filter(
            course_id=course_id, field_key__isnull=True
        ).update(field_key=key)

    # Fallback: any remaining NULL → 'lain-lain'
    Course.objects.filter(field_key__isnull=True).update(field_key='umum')
    StpmCourse.objects.filter(field_key__isnull=True).update(field_key='umum')


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0026_populate_field_taxonomy'),
    ]

    operations = [
        migrations.RunPython(
            populate_null_field_keys,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='course',
            name='field_key',
            field=models.ForeignKey(
                help_text='Canonical field classification',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='courses',
                to='courses.fieldtaxonomy',
            ),
        ),
        migrations.AlterField(
            model_name='stpmcourse',
            name='field_key',
            field=models.ForeignKey(
                help_text='Canonical field classification',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='stpm_courses',
                to='courses.fieldtaxonomy',
            ),
        ),
    ]
