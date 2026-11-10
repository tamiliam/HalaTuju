"""Pins for the A3.13 facades: `apps/scholarship/public.py` (new) and the models added to
`apps/courses/public.py`. A facade re-exports; every name is the SAME object as at its home."""
from importlib import import_module

from django.test import SimpleTestCase

from apps.courses import models as courses_models
from apps.courses import public as courses_public
from apps.scholarship import public as scholarship_public

# name -> the module that really owns it
SCHOLARSHIP_HOMES = {
    'ApplicantDocument': 'apps.scholarship.models',
    'Programme': 'apps.scholarship.models',
    'DECIDED_STATUSES': 'apps.scholarship.family',
    'PROFILE_FAMILY_FIELDS': 'apps.scholarship.family',
    'PROFILE_PATHWAY_FIELDS': 'apps.scholarship.family',
    'copy_family_roster': 'apps.scholarship.family',
    'copy_pathway': 'apps.scholarship.family',
}
SCHOLARSHIP_MODULES = ('birth_state', 'constants', 'emails', 'identity', 'whatsapp')


class TestScholarshipFacadeIsTheSameObjects(SimpleTestCase):
    def test_every_listed_name_is_the_home_object(self):
        for name, home in SCHOLARSHIP_HOMES.items():
            with self.subTest(name=name):
                self.assertIs(getattr(scholarship_public, name), getattr(import_module(home), name))

    def test_every_listed_module_is_the_real_module(self):
        for name in SCHOLARSHIP_MODULES:
            with self.subTest(name=name):
                self.assertIs(getattr(scholarship_public, name),
                              import_module(f'apps.scholarship.{name}'))

    def test_the_facade_lists_exactly_these_names(self):
        self.assertEqual(set(scholarship_public.__all__),
                         set(SCHOLARSHIP_HOMES) | set(SCHOLARSHIP_MODULES))


class TestCoursesFacadeModels(SimpleTestCase):
    def test_the_models_reports_reads_are_the_real_models(self):
        self.assertIs(courses_public.StudentProfile, courses_models.StudentProfile)
        self.assertIs(courses_public.FieldTaxonomy, courses_models.FieldTaxonomy)

    def test_a_patch_on_a_module_still_reaches_the_caller(self):
        # courses calls `whatsapp.<fn>` on the module object, so patching the module attribute
        # at its home bites through the facade.
        from unittest import mock

        from apps.scholarship import whatsapp
        with mock.patch.object(whatsapp, 'send_otp', create=True) as m:
            self.assertIs(scholarship_public.whatsapp.send_otp, m)
