"""Offer reader S4's institution / campus split (hand-over 2026-11-02) — the matcher rejoins them.

S4 stores ``institution`` = the name only and a new ``campus`` = the campus as printed. The catalogue
holds a row PER CAMPUS for polytechnics, KK, IPG, IKBN / IKM / KKTM, so a matcher that read only the
name would lose every multi-campus pin. ``offer_course_match.letter_institution`` is the one join;
``pathway_engine.student_offer_check`` feeds it to every caller (match, ``letter_place``, the ticks).
Catalogue rows are ``test_offer_course_match``'s; the letters are S4's shape, no names or IC numbers.
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.offer_course_match import (
    letter_institution, letter_place, match_offer_course, pinned_match)
from apps.scholarship.pathway_engine import student_offer_check
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_offer_course_match import seed_realign_catalogue


def _offer(app, fields):
    prof = app.profile
    return ApplicantDocument.objects.create(
        application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x',
        vision_fields={'fields': {'candidate_name': prof.name, 'candidate_nric': prof.nric.replace('-', ''),
                                  **fields},
                       'authenticity': {'status': 'genuine'}, 'student_verdict': 'ok', 'warnings': [],
                       'error': ''},
        vision_run_at=timezone.now())


class TheJoinTest(TestCase):
    def test_a_campus_is_joined_on_once(self):
        self.assertEqual(letter_institution('KOLEJ KOMUNITI', 'KANGAR'), 'KOLEJ KOMUNITI, KANGAR')
        self.assertEqual(letter_institution('UNIVERSITI TEKNOLOGI MARA', 'CAWANGAN SABAH, KAMPUS KOTA KINABALU'),
                         'UNIVERSITI TEKNOLOGI MARA, CAWANGAN SABAH, KAMPUS KOTA KINABALU')

    def test_nothing_is_repeated(self):
        self.assertEqual(letter_institution('Kolej Komuniti Kangar', 'Kangar'), 'Kolej Komuniti Kangar')
        self.assertEqual(letter_institution('Kolej Komuniti', 'KOLEJ KOMUNITI KANGAR'), 'KOLEJ KOMUNITI KANGAR')
        # A campus word that is only PART of a word of the name is not "inside" it.
        self.assertEqual(letter_institution('Politeknik Arau', 'Ara'), 'Politeknik Arau, Ara')

    def test_a_pre_s4_read_is_unchanged(self):
        for campus in (None, '', '   '):
            with self.subTest(campus=campus):
                self.assertEqual(letter_institution('  KOLEJ  KOMUNITI KANGAR ', campus), 'KOLEJ KOMUNITI KANGAR')
        self.assertEqual(letter_institution('', 'KANGAR'), 'KANGAR')
        self.assertEqual(letter_institution(None, None), '')


class MultiCampusPinsSurviveTheSplitTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()

    def test_the_name_alone_pins_no_campus_and_the_join_pins_one(self):
        alone = match_offer_course('DIPLOMA PELANCONGAN', 'KOLEJ KOMUNITI')
        self.assertEqual((alone or {}).get('institution', ''), '')
        joined = match_offer_course('DIPLOMA PELANCONGAN', letter_institution('KOLEJ KOMUNITI', 'KANGAR'))
        self.assertEqual((joined['course_id'], joined['institution']), ('RA-KK-DPL', 'Kolej Komuniti Kangar'))
        self.assertEqual(pinned_match('DIPLOMA PELANCONGAN', letter_institution('KOLEJ KOMUNITI', 'ARAU'))[1]
                         ['institution'], 'Kolej Komuniti Arau')

    def test_an_ikm_campus(self):
        line = letter_institution('INSTITUT KEMAHIRAN MARA', 'LUMUT')
        m = match_offer_course('DIPLOMA TEKNOLOGI KEJURUTERAAN MEKANIKAL', line)
        self.assertEqual((m['course_id'], m['institution']), ('RA-IKM-DTKM', 'Institut Kemahiran MARA Lumut'))
        self.assertEqual(letter_place('RA-IKM-DTKM', line), line)

    def test_the_old_refusals_still_hold_on_split_reads(self):
        degree = 'SARJANA MUDA KEJURUTERAAN KOMPUTER'
        line = letter_institution('UiTM', 'CAWANGAN PERLIS, KAMPUS ARAU')   # never UniMAP
        self.assertIsNone(match_offer_course(degree, line))
        uitm = letter_institution('UNIVERSITI TEKNOLOGI MARA', 'KAMPUS SHAH ALAM')
        self.assertEqual(match_offer_course('SARJANA MUDA PERNIAGAAN KEWANGAN (KEPUJIAN)', uitm)['course_id'],
                         'UE6343001')


class TheOfferCheckFeedsTheJoinTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()

    def test_student_offer_check_reads_the_campus(self):
        app = make_application('profile_complete', chosen_pathway='kkom')
        chk = student_offer_check(_offer(app, {
            'programme': 'DIPLOMA PELANCONGAN', 'institution': 'KOLEJ KOMUNITI', 'campus': 'KANGAR',
            'issuer': 'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI'}))
        self.assertEqual(chk['institution'], 'KOLEJ KOMUNITI, KANGAR')
        reason, match = pinned_match(chk['programme'], chk['institution'], chk['issuer'])
        self.assertEqual((reason, match['institution']), ('', 'Kolej Komuniti Kangar'))

    def test_a_stored_pre_s4_read_reads_as_before(self):
        app = make_application('profile_complete', chosen_pathway='kkom')
        chk = student_offer_check(_offer(app, {'programme': 'DIPLOMA PELANCONGAN',
                                               'institution': 'KOLEJ KOMUNITI KANGAR', 'issuer': ''}))
        self.assertEqual(chk['institution'], 'KOLEJ KOMUNITI KANGAR')
