"""
Data migration: Insert Matric colleges and STPM schools as Institution rows,
then create CourseInstitution links to the pre-U courses.

- 15 Kolej Matrikulasi → linked to matric-* courses by track
- 584 STPM schools → linked to stpm-* courses by stream
"""
import json
import os

from django.db import migrations


# 15 Kolej Matrikulasi — (id, name, state, tracks[], phone, website)
MATRIC_COLLEGES = [
    ('kmp', 'KM Perlis', 'Perlis', ['sains', 'perakaunan'], '04-9868613', 'kmp.matrik.edu.my'),
    ('kmk', 'KM Kedah', 'Kedah', ['sains', 'perakaunan'], '04-9286100', 'kmk.matrik.edu.my'),
    ('kmpp', 'KM Pulau Pinang', 'Pulau Pinang', ['sains', 'perakaunan'], '04-5756090', 'kmpp.matrik.edu.my'),
    ('kmpk', 'KM Perak', 'Perak', ['sains', 'sains_komputer', 'perakaunan'], '05-3594449', 'kmpk.matrik.edu.my'),
    ('kms', 'KM Selangor', 'Selangor', ['sains', 'perakaunan'], '03-31201410', 'kms.matrik.edu.my'),
    ('kmns', 'KM Negeri Sembilan', 'Negeri Sembilan', ['sains', 'perakaunan'], '06-4841825', 'kmns.matrik.edu.my'),
    ('kmm', 'KM Melaka', 'Melaka', ['sains', 'perakaunan'], '06-3832000', 'kmm.matrik.edu.my'),
    ('kmj', 'KM Johor', 'Johor', ['sains', 'sains_komputer', 'perakaunan'], '06-9781613', 'kmj.matrik.edu.my'),
    ('kmph', 'KM Pahang', 'Pahang', ['sains', 'perakaunan'], '09-5495000', 'kmph.matrik.edu.my'),
    ('kmkt', 'KM Kelantan', 'Kelantan', ['sains', 'sains_komputer', 'perakaunan'], '09-7808000', 'kmkt.matrik.edu.my'),
    ('kml', 'KM Labuan', 'Labuan', ['sains', 'sains_komputer', 'perakaunan'], '087-465311', 'kml.matrik.edu.my'),
    ('kmsw', 'KM Sarawak', 'Sarawak', ['sains'], '082-439100', 'kmsw.matrik.edu.my'),
    ('kmkk', 'KMK Kedah', 'Kedah', ['kejuruteraan'], '04-4682508', 'kmkk.matrik.edu.my'),
    ('kmkph', 'KMK Pahang', 'Pahang', ['kejuruteraan'], '09-4677103', 'kmkph.matrik.edu.my'),
    ('kmkj', 'KMK Johor', 'Johor', ['kejuruteraan'], '07-6881629', 'kmkj.matrik.edu.my'),
]

# Track name → course_id
MATRIC_TRACK_MAP = {
    'sains': 'matric-sains',
    'kejuruteraan': 'matric-kejuruteraan',
    'sains_komputer': 'matric-sains-komputer',
    'perakaunan': 'matric-perakaunan',
}

# STPM stream name → course_id
STPM_STREAM_MAP = {
    'Sains': 'stpm-sains',
    'Sains Sosial': 'stpm-sains-sosial',
}


def load_stpm_schools():
    """Load STPM schools from JSON bundled with the app."""
    json_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data', 'stpm-schools.json'
    )
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def forward(apps, schema_editor):
    Institution = apps.get_model('courses', 'Institution')
    CourseInstitution = apps.get_model('courses', 'CourseInstitution')

    # --- Matric colleges ---
    for inst_id, name, state, tracks, phone, website in MATRIC_COLLEGES:
        Institution.objects.update_or_create(
            institution_id=inst_id,
            defaults={
                'institution_name': name,
                'acronym': inst_id.upper(),
                'type': 'Kolej Matrikulasi',
                'category': '',
                'subcategory': '',
                'state': state,
                'phone': phone,
                'url': f'https://{website}',
            },
        )
        for track in tracks:
            course_id = MATRIC_TRACK_MAP.get(track)
            if course_id:
                CourseInstitution.objects.get_or_create(
                    course_id=course_id,
                    institution_id=inst_id,
                )

    # --- STPM schools ---
    schools = load_stpm_schools()
    for school in schools:
        code = school['code']
        Institution.objects.update_or_create(
            institution_id=code,
            defaults={
                'institution_name': school['name'],
                'acronym': '',
                'type': 'Sekolah Menengah',
                'category': '',
                'subcategory': '',
                'state': school['state'],
                'phone': school.get('phone', ''),
                'url': '',
            },
        )
        for stream in school.get('streams', []):
            course_id = STPM_STREAM_MAP.get(stream)
            if course_id:
                CourseInstitution.objects.get_or_create(
                    course_id=course_id,
                    institution_id=code,
                )


def reverse(apps, schema_editor):
    Institution = apps.get_model('courses', 'Institution')
    CourseInstitution = apps.get_model('courses', 'CourseInstitution')

    # Remove STPM school links and institutions
    stpm_course_ids = list(STPM_STREAM_MAP.values())
    CourseInstitution.objects.filter(course_id__in=stpm_course_ids).delete()

    # Remove matric links and institutions
    matric_course_ids = list(MATRIC_TRACK_MAP.values())
    CourseInstitution.objects.filter(course_id__in=matric_course_ids).delete()

    matric_ids = [m[0] for m in MATRIC_COLLEGES]
    Institution.objects.filter(institution_id__in=matric_ids).delete()
    Institution.objects.filter(type='Sekolah Menengah').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0017_insert_preu_courses'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
