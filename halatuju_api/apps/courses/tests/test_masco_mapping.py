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
