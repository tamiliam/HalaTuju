"""Insert 6 pre-university courses and their requirements."""
from django.db import migrations


def insert_preu_courses(apps, schema_editor):
    Course = apps.get_model('courses', 'Course')
    CourseRequirement = apps.get_model('courses', 'CourseRequirement')

    courses_data = [
        {
            'course_id': 'matric-sains',
            'course': 'Matrikulasi — Sains',
            'level': 'Pra-U',
            'department': 'KPM',
            'field': 'Sains & Teknologi',
            'frontend_label': 'Sains & Teknologi',
        },
        {
            'course_id': 'matric-kejuruteraan',
            'course': 'Matrikulasi — Kejuruteraan',
            'level': 'Pra-U',
            'department': 'KPM',
            'field': 'Kejuruteraan',
            'frontend_label': 'Kejuruteraan',
        },
        {
            'course_id': 'matric-sains-komputer',
            'course': 'Matrikulasi — Sains Komputer',
            'level': 'Pra-U',
            'department': 'KPM',
            'field': 'Teknologi Maklumat',
            'frontend_label': 'Teknologi Maklumat',
        },
        {
            'course_id': 'matric-perakaunan',
            'course': 'Matrikulasi — Perakaunan',
            'level': 'Pra-U',
            'department': 'KPM',
            'field': 'Perakaunan & Kewangan',
            'frontend_label': 'Perakaunan & Kewangan',
        },
        {
            'course_id': 'stpm-sains',
            'course': 'Tingkatan 6 — Sains',
            'level': 'Pra-U',
            'department': 'KPM',
            'field': 'Sains & Teknologi',
            'frontend_label': 'Sains & Teknologi',
        },
        {
            'course_id': 'stpm-sains-sosial',
            'course': 'Tingkatan 6 — Sains Sosial',
            'level': 'Pra-U',
            'department': 'KPM',
            'field': 'Sains Sosial',
            'frontend_label': 'Sains Sosial',
        },
    ]

    requirements_data = [
        {
            'course_id': 'matric-sains',
            'source_type': 'matric',
            'merit_type': 'matric',
            'merit_cutoff': 94,
            'credit_bm': True,
            'pass_history': True,
            'complex_requirements': {
                'or_groups': [
                    {'count': 1, 'grade': 'B', 'subjects': ['math']},
                    {'count': 1, 'grade': 'C', 'subjects': ['addmath']},
                    {'count': 1, 'grade': 'C', 'subjects': ['chem']},
                    {'count': 1, 'grade': 'C', 'subjects': ['phy', 'bio']},
                ],
            },
            'min_credits': 5,
        },
        {
            'course_id': 'matric-kejuruteraan',
            'source_type': 'matric',
            'merit_type': 'matric',
            'merit_cutoff': 94,
            'credit_bm': True,
            'pass_history': True,
            'complex_requirements': {
                'or_groups': [
                    {'count': 1, 'grade': 'B', 'subjects': ['math']},
                    {'count': 1, 'grade': 'C', 'subjects': ['addmath']},
                    {'count': 1, 'grade': 'C', 'subjects': ['phy']},
                ],
            },
            'min_credits': 5,
        },
        {
            'course_id': 'matric-sains-komputer',
            'source_type': 'matric',
            'merit_type': 'matric',
            'merit_cutoff': 94,
            'credit_bm': True,
            'pass_history': True,
            'complex_requirements': {
                'or_groups': [
                    {'count': 1, 'grade': 'C', 'subjects': ['math']},
                    {'count': 1, 'grade': 'C', 'subjects': ['addmath']},
                    {'count': 1, 'grade': 'C', 'subjects': ['comp_sci']},
                ],
            },
            'min_credits': 5,
        },
        {
            'course_id': 'matric-perakaunan',
            'source_type': 'matric',
            'merit_type': 'matric',
            'merit_cutoff': 94,
            'credit_bm': True,
            'pass_history': True,
            'complex_requirements': {
                'or_groups': [
                    {'count': 1, 'grade': 'C', 'subjects': ['math']},
                ],
            },
            'min_credits': 5,
        },
        {
            'course_id': 'stpm-sains',
            'source_type': 'stpm',
            'merit_type': 'stpm_mata_gred',
            'merit_cutoff': 18,
            'credit_bm': True,
            'pass_history': True,
            'min_credits': 3,
        },
        {
            'course_id': 'stpm-sains-sosial',
            'source_type': 'stpm',
            'merit_type': 'stpm_mata_gred',
            'merit_cutoff': 18,
            'credit_bm': True,
            'pass_history': True,
            'min_credits': 3,
        },
    ]

    for cd in courses_data:
        Course.objects.create(**cd)

    for rd in requirements_data:
        course_id = rd.pop('course_id')
        CourseRequirement.objects.create(course_id=course_id, **rd)


def remove_preu_courses(apps, schema_editor):
    Course = apps.get_model('courses', 'Course')
    Course.objects.filter(course_id__in=[
        'matric-sains', 'matric-kejuruteraan', 'matric-sains-komputer',
        'matric-perakaunan', 'stpm-sains', 'stpm-sains-sosial',
    ]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('courses', '0016_add_merit_type_and_preu_source_types'),
    ]

    operations = [
        migrations.RunPython(insert_preu_courses, remove_preu_courses),
    ]
