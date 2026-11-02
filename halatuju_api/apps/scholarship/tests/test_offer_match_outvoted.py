"""A course named only as a SUBSET of a longer letter name is no match when another course at the
same institution shares more of the letter's words (#337, S4 dry run 2026-11-02)."""
from django.test import TestCase

from apps.courses.models import FieldTaxonomy, Institution, StpmCourse
from apps.scholarship.offer_course_match import match_offer_course, pinned_match

UUM = 'Universiti Utara Malaysia'


class OutvotedSubsetTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        ft, _ = FieldTaxonomy.objects.get_or_create(key='outvoted', defaults={
            'name_en': 'x', 'name_ms': 'x', 'name_ta': 'x', 'image_slug': 'outvoted'})
        inst = Institution.objects.create(
            institution_id='T-UUM', institution_name=UUM, acronym='UUM', type='UA', state='Kedah')
        for cid, name in (
                ('UU6224001', 'Sarjana Muda Linguistik Terapan dan Pentadbiran Perniagaan dengan Kepujian'),
                ('UU6345003', 'Sarjana Muda Pentadbiran Perniagaan dengan Kepujian'),
                ('UU6340001', 'Sarjana Muda Perakaunan dengan Kepujian'),
                ('UU6345004', 'Sarjana Muda Pentadbiran Perniagaan (Pemasaran) dengan Kepujian'),
                ('UU6481001', 'Sarjana Muda Sains Komputer'),
                ('UU6481002', 'Sarjana Muda Sains Komputer (Rangkaian Komputer) dengan Kepujian'),
                ('UU6442001', 'Sarjana Muda Sains Kimia (Kepujian)'),
                ('UU6442002', 'Sarjana Muda Sains Kimia Gunaan dengan Kepujian')):
            StpmCourse.objects.create(course_id=cid, course_name=name, university=UUM, institution=inst,
                                      field_key=ft)

    def _cid(self, programme):
        return (match_offer_course(programme, UUM, '') or {}).get('course_id')

    def test_the_letters_own_typo_does_not_fall_back_to_the_shorter_course(self):
        letter = 'SARJANA MUDA LINGUSTIK TERAPAN DAN PENTADBIRAN PERNIAGAAN DENGAN KEPUJIAN'
        self.assertIsNone(self._cid(letter))
        self.assertEqual(pinned_match(letter, UUM), ('unresolved', None))

    def test_the_full_name_never_resolves_to_the_shorter_course(self):
        # Both courses are named (one is a subset), so no one course: unchanged behaviour, never UU6345003.
        self.assertNotEqual(
            self._cid('SARJANA MUDA LINGUISTIK TERAPAN DAN PENTADBIRAN PERNIAGAAN DENGAN KEPUJIAN'), 'UU6345003')

    def test_the_short_course_still_resolves_on_its_own_letter(self):
        self.assertEqual(self._cid('Sarjana Muda Pentadbiran Perniagaan dengan Kepujian'), 'UU6345003')

    def test_an_extra_word_no_other_course_shares_still_resolves(self):
        # A letter-only word (a faculty abbreviation, a code) that no course here carries outvotes nothing.
        self.assertEqual(self._cid('SARJANA MUDA PERAKAUNAN DENGAN KEPUJIAN TISSA'), 'UU6340001')

    def test_a_typo_in_the_one_word_that_tells_two_courses_apart_resolves_nothing(self):
        # Review 2026-11-02: both courses share three words, so only the near-spelling rule catches it.
        self.assertIsNone(self._cid('SARJANA MUDA PENTADBIRAN PERNIAGAAN (PEMASARRAN) DENGAN KEPUJIAN'))

    def test_a_specialised_sibling_does_not_outvote_the_plain_course(self):
        # Review 2026-11-02: the TD-150 filter already refuses the sibling; it must not then outvote.
        self.assertEqual(self._cid('SARJANA MUDA SAINS KOMPUTER DENGAN KEPUJIAN'), 'UU6481001')

    def test_one_misread_letter_in_a_short_word_resolves_nothing(self):
        # Round-2 review: "GUNAAM" / "gunaan" is one edit but only 83% alike; the plain course must not win.
        self.assertIsNone(self._cid('SARJANA MUDA SAINS KIMIA GUNAAM (KEPUJIAN)'))
        self.assertEqual(self._cid('SARJANA MUDA SAINS KIMIA (KEPUJIAN)'), 'UU6442001')
