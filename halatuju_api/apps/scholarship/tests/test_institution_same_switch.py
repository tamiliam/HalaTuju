"""The "Course switched" note must not fire when one university is written two ways (acronym, full
name, English name, with or without a campus tail). Pairs are the real live institution strings."""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.genuineness.offer_signatures import _UA_NAMES
from apps.scholarship.institution_same import _UA_ALIASES, institutions_differ
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.pathway_engine import offer_pathway_switch

SAME = [
    ('UNIVERSITI PENDIDIKAN SULTAN IDRIS', 'UPSI'),
    ('Universiti Pendidikan Sultan Idris', 'UPSI'),
    ('SULTAN IDRIS EDUCATION UNIVERSITY', 'UPSI'),
    ('UiTM SHAH ALAM', 'UNIVERSITI TEKNOLOGI MARA'),
    ('Universiti Teknologi MARA', 'UiTM'),
    ('UTM', 'Universiti Teknologi Malaysia'),
    ('UNIVERSITI MALAYSIA SABAH', 'UMS Kampus Antarabangsa Labuan'),
    ('UNIVERSITI PENDIDIKAN SULTAN IDRIS (UPSI)', 'UPSI'),
]
SWITCHED = [
    ('KOLEJ MATRIKULASI KEJURUTERAAN JOHOR',
     'Kolej Kediaman Tun Pengiran Ahmad Raffae, UMS Kota Kinabalu, Sabah'),
    ('SEKOLAH MENENGAH KEBANGSAAN MAJAKIR, JLN MAJAKIR, KG SG PADANG, 89608 PAPAR, SABAH',
     'Universiti Malaysia Sabah, Kampus Antarabangsa Labuan'),
    ('Universiti Teknologi Malaysia', 'Universiti Pendidikan Sultan Idris'),
    ('UiTM Shah Alam', 'Universiti Teknologi MARA Kampus Dengkil'),     # two campuses of one university
]


class TestInstitutionsDiffer(TestCase):
    def test_same_university_two_ways_is_not_a_switch(self):
        for was, now in SAME:
            for a, b in ((was, now), (now, was)):
                self.assertFalse(institutions_differ(a, b), (a, b))

    def test_genuinely_different_institutions_still_switch(self):
        for was, now in SWITCHED:
            for a, b in ((was, now), (now, was)):
                self.assertTrue(institutions_differ(a, b), (a, b))

    def test_every_ua_name_has_its_aliases(self):
        self.assertEqual(set(_UA_NAMES), set(_UA_ALIASES))


class TestSwitchNoteEndToEnd(TestCase):
    def setUp(self):
        cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        profile = StudentProfile.objects.create(
            supabase_user_id='same-uni', name='TEST STUDENT', nric='080219-10-1512',
            household_income=1800, household_size=4)
        self.app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='profile_complete', chosen_pathway='poly')

    def _offer(self, institution, superseded):
        vf = {'fields': {'programme': 'Diploma Sains Komputer', 'institution': institution,
                         'candidate_nric': '080219101512'}, 'warnings': [], 'error': ''}
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='offer_letter',
            storage_path=f'{self.app.id}/offer/{"old" if superseded else "live"}',
            vision_fields=vf, vision_run_at=timezone.now(),
            superseded_at=timezone.now() if superseded else None)

    def test_acronym_replacement_is_not_a_switch(self):
        self._offer('UNIVERSITI PENDIDIKAN SULTAN IDRIS', superseded=True)
        self._offer('UPSI', superseded=False)
        self.assertIsNone(offer_pathway_switch(self.app))

    def test_other_university_is_a_switch(self):
        self._offer('Universiti Teknologi Malaysia', superseded=True)
        self._offer('Universiti Pendidikan Sultan Idris', superseded=False)
        self.assertIsNotNone(offer_pathway_switch(self.app))
