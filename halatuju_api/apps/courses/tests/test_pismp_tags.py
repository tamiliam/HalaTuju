"""
Tests for PISMP course tag backfill command.

Covers:
- Specialisation keyword matching (all 12 specialisations)
- Base tags applied to all PISMP courses
- Specialisation overrides applied correctly
- Unmatched courses get base tags
- Existing tags not overwritten
- Dry run vs apply mode
"""
from django.test import TestCase
from apps.courses.models import Course, CourseRequirement, CourseTag
from apps.courses.management.commands.backfill_pismp_tags import (
    _match_specialisation,
    PISMP_BASE_TAGS,
)


class TestSpecialisationMatching(TestCase):
    """Test keyword matching for PISMP specialisations."""

    def test_sains(self):
        spec = _match_specialisation('Sains Pendidikan Rendah')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['environment'], 'lab')
        self.assertEqual(spec['tags']['cognitive_type'], 'abstract')

    def test_matematik(self):
        spec = _match_specialisation('Matematik Pendidikan Rendah (SJKT)')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['environment'], 'office')
        self.assertEqual(spec['tags']['cognitive_type'], 'abstract')

    def test_jasmani(self):
        spec = _match_specialisation('Pendidikan Jasmani Pendidikan Rendah')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['environment'], 'field')
        self.assertEqual(spec['tags']['load'], 'physically_demanding')
        self.assertEqual(spec['tags']['work_modality'], 'hands_on')

    def test_seni_visual(self):
        spec = _match_specialisation('Pendidikan Seni Visual Pendidikan Rendah')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['environment'], 'workshop')
        self.assertEqual(spec['tags']['creative_output'], 'expressive')

    def test_muzik(self):
        spec = _match_specialisation('Pendidikan Muzik Pendidikan Rendah (SJKC)')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['environment'], 'workshop')
        self.assertEqual(spec['tags']['creative_output'], 'expressive')

    def test_reka_bentuk(self):
        spec = _match_specialisation('Reka Bentuk dan Teknologi Pendidikan (SJKT)')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['environment'], 'workshop')
        self.assertEqual(spec['tags']['creative_output'], 'design')
        self.assertEqual(spec['tags']['cognitive_type'], 'problem_solving')

    def test_kaunseling(self):
        spec = _match_specialisation('Bimbingan dan Kaunseling (SJKT)')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['environment'], 'office')
        self.assertEqual(spec['tags']['service_orientation'], 'high')

    def test_khas_masalah(self):
        spec = _match_specialisation('Pendidikan Khas Masalah Pembelajaran')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['cognitive_type'], 'procedural')
        self.assertEqual(spec['tags']['service_orientation'], 'high')

    def test_khas_pendengaran(self):
        spec = _match_specialisation('Pendidikan Khas Masalah Pendengaran (SJKC)')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['cognitive_type'], 'procedural')

    def test_khas_penglihatan(self):
        spec = _match_specialisation('Pendidikan Khas Masalah Penglihatan')
        self.assertIsNotNone(spec)

    def test_kanak_kanak(self):
        spec = _match_specialisation('Pendidikan Awal Kanak-Kanak (SJKT)')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['load'], 'balanced_load')
        self.assertEqual(spec['tags']['cognitive_type'], 'procedural')

    def test_sejarah(self):
        spec = _match_specialisation('Sejarah Pendidikan Rendah')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['environment'], 'office')
        self.assertIn('assessment_heavy', spec['tags']['learning_style'])

    def test_islam(self):
        spec = _match_specialisation('Pendidikan Islam Pendidikan Rendah')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['environment'], 'office')

    def test_bahasa_melayu(self):
        spec = _match_specialisation('Bahasa Melayu Pendidikan Rendah')
        self.assertIsNotNone(spec)
        self.assertEqual(spec['tags']['environment'], 'office')

    def test_bahasa_tamil(self):
        spec = _match_specialisation('Bahasa Tamil Pendidikan Rendah (SJKT)')
        self.assertIsNotNone(spec)

    def test_bahasa_cina(self):
        spec = _match_specialisation('Bahasa Cina Pendidikan Rendah (SJKC)')
        self.assertIsNotNone(spec)

    def test_bahasa_arab(self):
        spec = _match_specialisation('Bahasa Arab Pendidikan Rendah')
        self.assertIsNotNone(spec)

    def test_bahasa_inggeris(self):
        spec = _match_specialisation(
            'Pengajaran Bahasa Inggeris Sebagai Bahasa'
        )
        self.assertIsNotNone(spec)

    def test_bahasa_iban(self):
        spec = _match_specialisation('Bahasa Iban Pendidikan Rendah')
        self.assertIsNotNone(spec)

    def test_elektif_variant(self):
        """Elektif variants should match the base specialisation."""
        spec = _match_specialisation(
            'Bahasa Melayu Pendidikan Rendah Elektif (SJKT)'
        )
        self.assertIsNotNone(spec)

    def test_unknown_returns_none(self):
        spec = _match_specialisation('Completely Unknown Course')
        self.assertIsNone(spec)


class TestBaseTags(TestCase):
    """Test that base tags have correct values for teacher training."""

    def test_all_teaching_is_high_people(self):
        self.assertEqual(PISMP_BASE_TAGS['people_interaction'], 'high_people')

    def test_all_teaching_is_regulated(self):
        self.assertEqual(PISMP_BASE_TAGS['outcome'], 'regulated_profession')
        self.assertEqual(PISMP_BASE_TAGS['credential_status'], 'regulated')

    def test_all_teaching_is_stable_career(self):
        self.assertEqual(PISMP_BASE_TAGS['career_structure'], 'stable')

    def test_all_teaching_is_service(self):
        self.assertEqual(PISMP_BASE_TAGS['service_orientation'], 'high')

    def test_base_has_all_required_fields(self):
        required = [
            'work_modality', 'people_interaction', 'cognitive_type',
            'learning_style', 'load', 'outcome', 'environment',
            'credential_status', 'creative_output', 'service_orientation',
            'interaction_type', 'career_structure',
        ]
        for field in required:
            self.assertIn(field, PISMP_BASE_TAGS, f'{field} missing from base')


class TestBackfillCommand(TestCase):
    """Test the management command creates correct CourseTag rows."""

    def setUp(self):
        self.sains = Course.objects.create(
            course_id='PISMP-SAINS',
            course='Sains Pendidikan Rendah',
            field_key_id='pendidikan',
        )
        CourseRequirement.objects.create(
            course=self.sains,
            source_type='pismp',
            min_credits=5,
            pass_bm=True,
        )

        self.jasmani = Course.objects.create(
            course_id='PISMP-JASMANI',
            course='Pendidikan Jasmani Pendidikan Rendah',
            field_key_id='pendidikan',
        )
        CourseRequirement.objects.create(
            course=self.jasmani,
            source_type='pismp',
            min_credits=5,
            pass_bm=True,
        )

        self.muzik = Course.objects.create(
            course_id='PISMP-MUZIK',
            course='Pendidikan Muzik Pendidikan Rendah (SJKT)',
            field_key_id='pendidikan',
        )
        CourseRequirement.objects.create(
            course=self.muzik,
            source_type='pismp',
            min_credits=5,
            pass_bm=True,
        )

    def test_dry_run_creates_nothing(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('backfill_pismp_tags', stdout=out)
        self.assertEqual(CourseTag.objects.count(), 0)
        self.assertIn('Would create', out.getvalue())

    def test_apply_creates_tags(self):
        from django.core.management import call_command
        call_command('backfill_pismp_tags', '--apply')
        self.assertEqual(CourseTag.objects.count(), 3)

    def test_sains_gets_lab_environment(self):
        from django.core.management import call_command
        call_command('backfill_pismp_tags', '--apply')
        tag = CourseTag.objects.get(course_id='PISMP-SAINS')
        self.assertEqual(tag.environment, 'lab')
        self.assertEqual(tag.cognitive_type, 'abstract')
        # Base tags should still apply
        self.assertEqual(tag.people_interaction, 'high_people')
        self.assertEqual(tag.outcome, 'regulated_profession')

    def test_jasmani_gets_field_environment(self):
        from django.core.management import call_command
        call_command('backfill_pismp_tags', '--apply')
        tag = CourseTag.objects.get(course_id='PISMP-JASMANI')
        self.assertEqual(tag.environment, 'field')
        self.assertEqual(tag.load, 'physically_demanding')
        self.assertEqual(tag.work_modality, 'hands_on')

    def test_muzik_gets_workshop_and_expressive(self):
        from django.core.management import call_command
        call_command('backfill_pismp_tags', '--apply')
        tag = CourseTag.objects.get(course_id='PISMP-MUZIK')
        self.assertEqual(tag.environment, 'workshop')
        self.assertEqual(tag.creative_output, 'expressive')

    def test_skips_existing_tags(self):
        from django.core.management import call_command
        # Pre-create a tag
        CourseTag.objects.create(
            course_id='PISMP-SAINS',
            work_modality='theoretical',
            people_interaction='high_people',
            cognitive_type='abstract',
            load='mentally_demanding',
            outcome='regulated_profession',
            environment='office',  # Intentionally wrong
        )
        call_command('backfill_pismp_tags', '--apply')
        # Should have created 2 new + kept 1 existing = 3 total
        self.assertEqual(CourseTag.objects.count(), 3)
        # Existing tag should NOT be overwritten
        tag = CourseTag.objects.get(course_id='PISMP-SAINS')
        self.assertEqual(tag.environment, 'office')  # Not changed to 'lab'

    def test_non_pismp_courses_ignored(self):
        from django.core.management import call_command
        poly = Course.objects.create(
            course_id='POLY-TEST',
            course='Diploma Sains Komputer',
            field_key_id='pendidikan',
        )
        CourseRequirement.objects.create(
            course=poly,
            source_type='poly',
            min_credits=5,
            pass_bm=True,
        )
        call_command('backfill_pismp_tags', '--apply')
        # Only 3 PISMP courses tagged, not the poly course
        self.assertEqual(CourseTag.objects.count(), 3)
        self.assertFalse(
            CourseTag.objects.filter(course_id='POLY-TEST').exists()
        )
