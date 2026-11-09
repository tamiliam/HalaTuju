"""Shared fixtures for the A3.5 pins (course catalogue + a populated profile)."""
from unittest.mock import patch

from django.apps import apps

from apps.courses.models import (
    Course, CourseInstitution, CourseRequirement, FieldTaxonomy, Institution, StpmCourse,
    StpmRequirement,
)


def make_catalogue():
    # the 37-row taxonomy is seeded by a migration, so the keys exist already
    ft = FieldTaxonomy.objects.get(key='it-perisian')
    ft2 = FieldTaxonomy.objects.get(key='mekanikal')
    ft3 = FieldTaxonomy.objects.get(key='elektrik')
    i1 = Institution.objects.create(institution_id='I-PJ', institution_name='Politeknik Zeta',
                                    type='Politeknik', state='Selangor')
    i2 = Institution.objects.create(institution_id='I-KT', institution_name='Kolej Alpha',
                                    type='Kolej', state='Kedah')
    rows = [
        ('P-IT', 'Diploma Teknologi Maklumat', 'Diploma', 'Teknologi Maklumat', ft, 'poly', 70.0, False),
        ('P-ME', 'Diploma Kejuruteraan Mekanikal', 'Diploma', 'Kejuruteraan', ft2, 'poly', 65.0, False),
        ('T-IL', 'Sijil Teknologi Kimpalan', 'Sijil', 'Kejuruteraan', ft2, 'tvet', None, False),
        ('T-KB', 'Sijil Teknologi Elektrik', 'Sijil', 'Kejuruteraan', ft3, 'tvet', None, False),
        ('PI-1', 'Ijazah Sarjana Muda Pendidikan (Pendidikan Rendah)', 'Ijazah Sarjana Muda',
         'Pendidikan', ft3, 'pismp', 50.0, False),
        ('U-BM', 'Asasi Bumi Sahaja', 'Asasi', 'Sains', ft3, 'ua', 80.0, True),
    ]
    for cid, name, level, field, fk, st, merit, bumi in rows:
        c = Course.objects.create(course_id=cid, course=name, level=level, department='D',
                                  field=field, field_key=fk)
        CourseRequirement.objects.create(course=c, source_type=st, merit_cutoff=merit,
                                         req_bumiputera=bumi)
    for cid, inst in (('P-IT', i1), ('P-IT', i2), ('P-ME', i2), ('T-IL', i1), ('PI-1', i2),
                      ('U-BM', i1)):
        CourseInstitution.objects.create(course_id=cid, institution=inst)
    s1 = StpmCourse.objects.create(course_id='S-1', course_name='Ijazah Sains Komputer',
                                   university='UM', institution=i1, stream='science',
                                   merit_score=88.0, field='Teknologi Maklumat', field_key=ft)
    StpmRequirement.objects.create(course=s1)
    s2 = StpmCourse.objects.create(course_id='S-2', course_name='Ijazah Bumi', university='UiTM',
                                   stream='arts', merit_score=70.0, field='Sains', field_key=ft3)
    StpmRequirement.objects.create(course=s2, req_bumiputera=True)


PATHWAY_MAP = {'T-IL': 'iljtm', 'T-KB': 'ilkbs'}


def pathway_patch():
    return patch.object(apps.get_app_config('courses'), 'course_pathway_map', PATHWAY_MAP, create=True)
