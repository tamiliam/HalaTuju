from django.test import TestCase
from apps.courses.masco_mapping import FIELD_KEY_TO_MASCO, filter_masco_by_field_key
from apps.courses.models import MascoOccupation


class TestFieldKeyToMasco(TestCase):
    """Test the field_key -> MASCO 2-digit group mapping."""

    def test_all_field_keys_covered(self):
        active_keys = [
            'aero', 'alam-sekitar', 'automotif', 'elektrik', 'farmasi',
            'hospitaliti', 'it-perisian', 'it-rangkaian', 'kecantikan',
            'kejuruteraan-am', 'kimia-proses', 'kulinari', 'marin',
            'mekanikal', 'mekatronik', 'minyak-gas', 'multimedia',
            'pendidikan', 'pengajian-islam', 'pengurusan', 'perakaunan',
            'perniagaan', 'pertanian', 'perubatan', 'sains-hayat',
            'sains-sosial', 'senibina', 'senireka', 'sivil',
            'umum', 'undang-undang',
        ]
        for key in active_keys:
            self.assertIn(key, FIELD_KEY_TO_MASCO, f"Missing mapping for {key}")

    def test_mapping_returns_list_of_strings(self):
        for key, groups in FIELD_KEY_TO_MASCO.items():
            self.assertIsInstance(groups, list, f"{key} should map to a list")
            self.assertGreater(len(groups), 0, f"{key} has no groups")
            for g in groups:
                self.assertIsInstance(g, str, f"{key} groups should be strings")

    def test_engineering_maps_to_relevant_groups(self):
        eng_keys = ['mekanikal', 'elektrik', 'sivil', 'kejuruteraan-am']
        for key in eng_keys:
            groups = FIELD_KEY_TO_MASCO[key]
            has_eng = any(g in ('21', '31', '71', '72', '74', '81') for g in groups)
            self.assertTrue(has_eng, f"{key} should map to engineering MASCO groups")

    def test_health_maps_to_health_groups(self):
        for key in ['perubatan', 'farmasi']:
            groups = FIELD_KEY_TO_MASCO[key]
            has_health = any(g in ('22', '32') for g in groups)
            self.assertTrue(has_health, f"{key} should map to health groups")

    def test_education_maps_to_teaching(self):
        self.assertIn('23', FIELD_KEY_TO_MASCO['pendidikan'])


class TestFilterMascoByFieldKey(TestCase):
    """Test filtering MASCO records by field_key."""

    def setUp(self):
        MascoOccupation.objects.create(
            masco_code='2141-01', job_title='Jurutera Industri',
            emasco_url='https://emasco.mohr.gov.my/masco/2141-01')
        MascoOccupation.objects.create(
            masco_code='3113-01', job_title='Juruteknik Elektrik',
            emasco_url='https://emasco.mohr.gov.my/masco/3113-01')
        MascoOccupation.objects.create(
            masco_code='2512-01', job_title='Pembangun Perisian',
            emasco_url='https://emasco.mohr.gov.my/masco/2512-01')
        MascoOccupation.objects.create(
            masco_code='2211-01', job_title='Doktor Perubatan',
            emasco_url='https://emasco.mohr.gov.my/masco/2211-01')

    def test_filter_returns_relevant_jobs(self):
        jobs = filter_masco_by_field_key('elektrik')
        codes = [j.masco_code for j in jobs]
        self.assertIn('2141-01', codes)   # 21xx engineering
        self.assertIn('3113-01', codes)   # 31xx associate eng
        self.assertNotIn('2211-01', codes) # 22xx health

    def test_filter_unknown_key_returns_empty(self):
        jobs = filter_masco_by_field_key('nonexistent-key')
        self.assertEqual(jobs.count(), 0)

    def test_filter_returns_queryset(self):
        from django.db.models import QuerySet
        jobs = filter_masco_by_field_key('it-perisian')
        self.assertIsInstance(jobs, QuerySet)


# ---------------------------------------------------------------------------
# map_course_careers management command tests
# ---------------------------------------------------------------------------

import csv
from unittest.mock import patch, MagicMock


class TestMapCourseCareersCommand(TestCase):
    """Test the map_course_careers management command."""

    def setUp(self):
        from apps.courses.models import Course, CourseRequirement, FieldTaxonomy
        # Ensure field_key exists
        FieldTaxonomy.objects.get_or_create(
            key='mekanikal',
            defaults={'name_en': 'Mechanical', 'name_ms': 'Mekanikal', 'name_ta': 'இயந்திரவியல்', 'image_slug': 'mekanikal'})
        self.course = Course.objects.create(
            course_id='test-map-01',
            course='Diploma Kejuruteraan Mekanikal',
            level='Diploma',
            department='Kejuruteraan',
            field='Mekanikal',
            field_key_id='mekanikal',
        )
        CourseRequirement.objects.create(
            course=self.course, source_type='poly')
        MascoOccupation.objects.create(
            masco_code='2141-01', job_title='Jurutera Industri',
            emasco_url='https://emasco.mohr.gov.my/masco/2141-01')
        MascoOccupation.objects.create(
            masco_code='7233-01', job_title='Mekanik Jentera Pertanian',
            emasco_url='https://emasco.mohr.gov.my/masco/7233-01')
        MascoOccupation.objects.create(
            masco_code='2141-03', job_title='Jurutera Mekanikal',
            emasco_url='https://emasco.mohr.gov.my/masco/2141-03')

    @patch('apps.courses.management.commands.map_course_careers.call_gemini')
    def test_generates_csv(self, mock_gemini):
        mock_gemini.return_value = ['2141-01', '2141-03', '7233-01']
        from django.core.management import call_command
        from io import StringIO
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, 'review.csv')
            call_command(
                'map_course_careers',
                '--output', csv_path,
                '--source-type', 'poly',
                stdout=StringIO(),
            )
            self.assertTrue(os.path.exists(csv_path))
            with open(csv_path) as f:
                content = f.read()
            self.assertIn('test-map-01', content)
            self.assertIn('2141-01', content)

    @patch('apps.courses.management.commands.map_course_careers.call_gemini')
    def test_skips_already_mapped(self, mock_gemini):
        occ = MascoOccupation.objects.get(masco_code='2141-01')
        self.course.career_occupations.add(occ)
        from django.core.management import call_command
        from io import StringIO
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, 'review.csv')
            call_command(
                'map_course_careers',
                '--output', csv_path,
                '--source-type', 'poly',
                stdout=StringIO(),
            )
            mock_gemini.assert_not_called()


class TestMapCourseCareersApply(TestCase):
    """Test the --apply mode."""

    def setUp(self):
        from apps.courses.models import Course, CourseRequirement, FieldTaxonomy
        FieldTaxonomy.objects.get_or_create(
            key='elektrik',
            defaults={'name_en': 'Electrical', 'name_ms': 'Elektrik', 'name_ta': 'மின்னியல்', 'image_slug': 'elektrik'})
        FieldTaxonomy.objects.get_or_create(
            key='it-perisian',
            defaults={'name_en': 'Software IT', 'name_ms': 'IT Perisian', 'name_ta': 'மென்பொருள்', 'image_slug': 'it-perisian'})
        self.course = Course.objects.create(
            course_id='test-apply-01',
            course='Diploma Kejuruteraan Elektrik',
            level='Diploma',
            department='Kejuruteraan',
            field='Elektrik',
            field_key_id='elektrik',
        )
        CourseRequirement.objects.create(
            course=self.course, source_type='poly')
        MascoOccupation.objects.create(
            masco_code='2151-01', job_title='Jurutera Elektrik',
            emasco_url='https://emasco.mohr.gov.my/masco/2151-01')
        MascoOccupation.objects.create(
            masco_code='3113-01', job_title='Juruteknik Elektrik',
            emasco_url='https://emasco.mohr.gov.my/masco/3113-01')

    def test_apply_creates_m2m_links(self):
        from django.core.management import call_command
        from io import StringIO
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, 'approved.csv')
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'course_id', 'course_name', 'field_key',
                    'masco_code', 'job_title', 'type'])
                writer.writeheader()
                writer.writerow({
                    'course_id': 'test-apply-01', 'course_name': 'Diploma Kejuruteraan Elektrik',
                    'field_key': 'elektrik', 'masco_code': '2151-01',
                    'job_title': 'Jurutera Elektrik', 'type': 'spm'})
                writer.writerow({
                    'course_id': 'test-apply-01', 'course_name': 'Diploma Kejuruteraan Elektrik',
                    'field_key': 'elektrik', 'masco_code': '3113-01',
                    'job_title': 'Juruteknik Elektrik', 'type': 'spm'})

            call_command('map_course_careers', '--apply', csv_path, stdout=StringIO())

        self.assertEqual(self.course.career_occupations.count(), 2)
        codes = list(self.course.career_occupations.values_list('masco_code', flat=True))
        self.assertIn('2151-01', codes)
        self.assertIn('3113-01', codes)

    def test_apply_stpm_course(self):
        from apps.courses.models import StpmCourse
        from django.core.management import call_command
        from io import StringIO
        import tempfile, os

        stpm = StpmCourse.objects.create(
            course_id='stpm-test-apply',
            course_name='BSc Sains Komputer',
            university='UM',
            field_key_id='it-perisian',
        )
        # Reuse existing MASCO record
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, 'approved.csv')
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'course_id', 'course_name', 'field_key',
                    'masco_code', 'job_title', 'type'])
                writer.writeheader()
                writer.writerow({
                    'course_id': 'stpm-test-apply', 'course_name': 'BSc Sains Komputer',
                    'field_key': 'it-perisian', 'masco_code': '2151-01',
                    'job_title': 'Jurutera Elektrik', 'type': 'stpm'})

            call_command('map_course_careers', '--apply', csv_path, stdout=StringIO())

        self.assertEqual(stpm.career_occupations.count(), 1)
