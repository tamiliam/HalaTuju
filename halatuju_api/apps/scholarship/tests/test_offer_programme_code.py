"""Offer reader S4's programme / programme_code split — the matcher puts the code back.

S4 moves a printed course code out of ``programme`` into ``programme_code``. The matcher reads a UPU
code from the programme text (``_printed_course``), so ``offer_course_match.programme_line`` returns
it in the pre-S4 shape and ``pathway_engine.student_offer_check`` feeds that line to every caller.
``promotion.is_pathway_switch`` compares the programme NAME, so a pre-S4 read and an S4 re-read of
the same letter are one programme. Catalogue rows are ``test_offer_course_match``'s.
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.offer_course_match import match_offer_course, programme_line
from apps.scholarship.pathway_engine import student_offer_check
from apps.scholarship.promotion import is_pathway_switch
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_offer_course_match import seed_realign_catalogue

UKUR = 'Sarjana Muda Ukur Bahan dengan Kepujian'


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
    def test_a_upu_code_goes_after_the_name(self):
        self.assertEqual(programme_line(UKUR, 'UW6526001'), f'{UKUR} - UW6526001')

    def test_a_uitm_local_code_goes_in_front(self):
        self.assertEqual(programme_line('SARJANA MUDA PERNIAGAAN KEWANGAN (KEPUJIAN)', 'BA272'),
                         'BA272 SARJANA MUDA PERNIAGAAN KEWANGAN (KEPUJIAN)')

    def test_any_other_code_is_left_out(self):
        self.assertEqual(programme_line('DIPLOMA PELANCONGAN REKREASI', 'DRT'), 'DIPLOMA PELANCONGAN REKREASI')
        self.assertEqual(programme_line('DIPLOMA X', 'AT06'), 'DIPLOMA X')

    def test_a_pre_s4_read_is_unchanged(self):
        self.assertEqual(programme_line(f'{UKUR} - UW6526001', ''), f'{UKUR} - UW6526001')
        self.assertEqual(programme_line(f'{UKUR} - UW6526001', 'UW6526001'), f'{UKUR} - UW6526001')


class TheMatcherSeesTheCodeTest(TestCase):
    def setUp(self):
        seed_realign_catalogue()

    def test_an_s4_read_resolves_through_its_code(self):
        app = make_application()
        chk = student_offer_check(_offer(app, {
            'programme': UKUR, 'programme_code': 'UW6526001', 'institution': 'Universiti Malaysia Sarawak',
            'issuer': 'Universiti Malaysia Sarawak'}))
        self.assertEqual(chk['programme'], f'{UKUR} - UW6526001')
        m = match_offer_course(chk['programme'], chk['institution'], chk['issuer'])
        self.assertEqual((m or {}).get('course_id'), 'UW6526001')


class SwitchReadsTheNameTest(TestCase):
    def test_a_pre_s4_and_an_s4_read_of_one_letter_are_no_switch(self):
        app = make_application()
        old = _offer(app, {'programme': 'FTV - ASASI TEKNOLOGI KEJURUTERAAN'})
        new = _offer(app, {'programme': 'ASASI TEKNOLOGI KEJURUTERAAN', 'programme_code': 'FTV'})
        self.assertFalse(is_pathway_switch(new, old))
        upu_old = _offer(app, {'programme': f'{UKUR} - UW6526001'})
        upu_new = _offer(app, {'programme': UKUR, 'programme_code': 'UW6526001'})
        self.assertFalse(is_pathway_switch(upu_new, upu_old))

    def test_a_real_switch_is_still_a_switch(self):
        app = make_application()
        old = _offer(app, {'programme': 'FTV - ASASI TEKNOLOGI KEJURUTERAAN'})
        new = _offer(app, {'programme': 'DIPLOMA SAINS KOMPUTER', 'programme_code': 'DSPD'})
        self.assertTrue(is_pathway_switch(new, old))
