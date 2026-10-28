"""THE STPM SUBJECT LIST (`apps/courses/stpm_subjects.py`) — STPM CGPA sprint C1, 2026-10-28.

Every subject the STPM results form offers must be known to every backend reader of STPM subject
keys, and every subject a course requirement names must be one the form offers — otherwise a
student who took it (case #184, Sains Sukan) cannot enter it and the course can never be met.
The web half — `STPM_SUBJECTS` offers exactly these keys, in this order — is
`halatuju-web/src/lib/__tests__/stpmSubjectsDrift.test.ts`.
"""
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from apps.courses.stpm_engine import STPM_SUBJECT_BOOL_MAP
from apps.courses.stpm_subjects import PENGAJIAN_AM, STPM_SUBJECT_KEYS
from apps.reports.report_engine import STPM_SUBJECT_LABELS
from apps.scholarship.higher_results import _STPM_BY_NAME, _STPM_NAMES, _squash

FIXTURE = Path(__file__).resolve().parents[2] / 'courses' / 'fixtures' / 'stpm_requirements.json'

#: Distinct subject keys the requirement fixture's subject groups named on 2026-10-28: 22.
#: A MINIMUM — a fixture refresh may add more, never silently find none.
FIXTURE_KEY_FLOOR = 20


def _fixture_subject_keys():
    keys = set()
    for row in json.loads(FIXTURE.read_text(encoding='utf-8')):
        for group in row['fields'].get('stpm_subject_group') or []:
            keys.update(group.get('subjects') or [])
    return keys


class TestTheList(SimpleTestCase):
    def test_shape(self):
        self.assertEqual(STPM_SUBJECT_KEYS[0], PENGAJIAN_AM)
        self.assertEqual(len(STPM_SUBJECT_KEYS), len(set(STPM_SUBJECT_KEYS)), 'a key is listed twice')
        self.assertTrue(all(re.fullmatch(r'[A-Z][A-Z_]*', k) for k in STPM_SUBJECT_KEYS))

    def test_the_subjects_missing_before_c1_are_offered(self):
        """Case #184 could enter only three subjects: Sains Sukan was not on the form."""
        for key in ('SAINS_SUKAN', 'BAHASA_ARAB', 'LITERATURE_IN_ENGLISH', 'TAHFIZ_AL_QURAN'):
            with self.subTest(key=key):
                self.assertIn(key, STPM_SUBJECT_KEYS)

    def test_every_key_existing_before_c1_is_unchanged(self):
        """Stored `stpm_grades` rows key on these; renaming one would orphan a student's grade."""
        before = {'PA', 'MATH_T', 'PHYSICS', 'CHEMISTRY', 'BIOLOGY', 'FURTHER_MATH', 'ECONOMICS',
                  'ACCOUNTING', 'BUSINESS', 'GEOGRAFI', 'SEJARAH', 'KESUSASTERAAN_MELAYU',
                  'BAHASA_MELAYU', 'BAHASA_CINA', 'BAHASA_TAMIL', 'SENI_VISUAL', 'SYARIAH',
                  'USULUDDIN', 'ICT', 'MATH_M'}
        self.assertEqual(before - set(STPM_SUBJECT_KEYS), set())


class TestEveryReaderKnowsEverySubject(SimpleTestCase):
    def test_every_course_requirement_subject_is_on_the_form(self):
        found = _fixture_subject_keys()
        self.assertGreaterEqual(len(found), FIXTURE_KEY_FLOOR, (
            f'the requirement fixture named only {len(found)} STPM subject keys (floor '
            f'{FIXTURE_KEY_FLOOR}): `stpm_subject_group` has moved or changed shape, and this '
            'guard is reading nothing'))
        self.assertEqual(sorted(found - set(STPM_SUBJECT_KEYS)), [],
                         'a course requires a subject the STPM form does not offer')
        self.assertEqual(sorted(set(STPM_SUBJECT_BOOL_MAP.values()) - set(STPM_SUBJECT_KEYS)), [])

    def test_the_results_slip_check_names_every_subject(self):
        """`higher_results` matches a printed subject to the student's entry by these names."""
        self.assertEqual(sorted(set(STPM_SUBJECT_KEYS) - set(_STPM_NAMES)), [])
        self.assertEqual(sorted(set(_STPM_NAMES) - set(STPM_SUBJECT_KEYS)), [])

    def test_the_printed_names_resolve(self):
        for printed, key in (('SAINS SUKAN', 'SAINS_SUKAN'), ('BAHASA ARAB', 'BAHASA_ARAB'),
                             ('LITERATURE IN ENGLISH', 'LITERATURE_IN_ENGLISH'),
                             ('TAHFIZ AL-QURAN', 'TAHFIZ_AL_QURAN'),
                             ('KESUSASTERAAN MELAYU KOMUNIKATIF', 'KESUSASTERAAN_MELAYU'),
                             ('MATEMATIK (T)', 'MATH_T'), ('PENGAJIAN AM', 'PA')):
            with self.subTest(printed=printed):
                self.assertEqual(_STPM_BY_NAME.get(_squash(printed)), key)

    def test_the_counselling_report_labels_every_subject(self):
        self.assertEqual(sorted(set(STPM_SUBJECT_KEYS) - set(STPM_SUBJECT_LABELS)), [])
