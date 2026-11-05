"""Org request #56 (2026-11-05) — a results document whose name is ONE letter off the student's.

A matriculation transcript read by the AI fallback came back with one letter of the given name as
"Q" for "O"; the strict name check stored 'name_mismatch' and the Documents step blocked the student.
The fix (`apps/scholarship/name_misread.py`): exactly one SUBSTITUTED letter, in exactly one part of
at least 4 letters, every other part identical and in order -> 'partial' (amber, never a block, a
reviewer note). Anything else blocks exactly as before. All names here are invented.
"""
from django.test import SimpleTestCase, TestCase

from apps.scholarship.academic_engine import _slip_name_status
from apps.scholarship.help_engine import verdict_for_document
from apps.scholarship.higher_results import match_verdict, student_higher_check
from apps.scholarship.models import ApplicantDocument, Consent, FundingNeed, ScholarshipApplication
from apps.scholarship.name_misread import MIN_PART_LETTERS, one_letter_misread
from apps.scholarship.resolution import doc_match_verdict
from apps.scholarship.services.blockers import document_red_blockers
from apps.scholarship.services.completeness import application_completeness
from apps.scholarship.tests.factories import make_application, make_student, matched_str_pair
from apps.scholarship.tests.test_third_route_s3 import (
    DEGREE, MATRIC_PATHWAY, SPM_HELD, STPM_HELD, STPM_READ, _degree_course,
)
from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION, build_verdict
from apps.scholarship.verdict_ladder import _academic_red_chips

OWN = 'ROHANA A/P GOPAL'
MISREAD = 'RQHANA A/P GOPAL'          # the #56 shape: one O read as Q, in one part


class TestTheRule(SimpleTestCase):
    def test_one_substituted_letter_in_one_part_is_a_misread(self):
        self.assertTrue(one_letter_misread(MISREAD, OWN))
        self.assertTrue(one_letter_misread('rohana a/p gopql', OWN))      # any part, any case

    def test_a_leaked_label_is_ignored(self):
        self.assertTrue(one_letter_misread('NAMA : ' + MISREAD, OWN))

    def test_two_letters_in_one_part_is_another_name(self):
        self.assertFalse(one_letter_misread('RQHQNA A/P GOPAL', OWN))

    def test_one_letter_in_each_of_two_parts_is_another_name(self):
        self.assertFalse(one_letter_misread('RQHANA A/P GQPAL', OWN))

    def test_a_short_part_gets_no_tolerance(self):
        self.assertEqual(MIN_PART_LETTERS, 4)
        self.assertFalse(one_letter_misread('TAN AH KOW', 'TAN AH KOK'))   # 3 letters
        self.assertFalse(one_letter_misread('LIN MEI LING', 'LIM MEI LING'))
        self.assertTrue(one_letter_misread('RAJV A/L MUTHU', 'RAJU A/L MUTHU'))   # 4 letters: the floor

    def test_an_added_or_dropped_letter_is_not_a_misread(self):
        self.assertFalse(one_letter_misread('ROHANNA A/P GOPAL', OWN))
        self.assertFalse(one_letter_misread('ROHAN A/P GOPAL', OWN))

    def test_a_missing_extra_or_reordered_part_is_not_a_misread(self):
        self.assertFalse(one_letter_misread('RQHANA', OWN))
        self.assertFalse(one_letter_misread('RQHANA A/P GOPAL KUMAR', OWN))
        self.assertFalse(one_letter_misread('GOPAL RQHANA', OWN))

    def test_an_exact_or_empty_name_is_not_a_misread(self):
        self.assertFalse(one_letter_misread(OWN, OWN))     # exact is a match upstream, not a misread
        self.assertFalse(one_letter_misread('', OWN))
        self.assertFalse(one_letter_misread(MISREAD, ''))


def _app(held, plan, name=OWN):
    _degree_course()
    student = make_student(name=name, nric='030101-14-1234', school='SMK X',
                           student_signals={'field_interest': {'it': 5}}, address='No. 1 Jalan ABC',
                           postal_code='62100', city='Putrajaya', household_income=2500,
                           receives_str=True, **held)
    app = make_application('shortlisted', student=student, **plan)
    FundingNeed.objects.create(application=app, categories=['living'], programme_months=36)
    for dt in ('ic', 'offer_letter'):
        _doc(app, dt)
    matched_str_pair(app)
    Consent.objects.create(application=app, version='t', is_active=True)
    ScholarshipApplication.objects.filter(pk=app.id).update(
        income_route='str', income_earner='father', father_name='AROON', father_occupation='driver',
        mother_name='KOMATHI', mother_occupation='homemaker', siblings_in_school=1,
        siblings_in_tertiary=0)
    return ScholarshipApplication.objects.get(pk=app.pk)


def _doc(app, doc_type, fields=None, verdict='ok'):
    vf = {'fields': fields, 'student_verdict': verdict, 'error': ''} if fields is not None else {}
    return ApplicantDocument.objects.create(application=app, doc_type=doc_type,
                                            storage_path=f'test/{doc_type}', vision_fields=vf)


def _academic(app):
    return next(f for f in build_verdict(ScholarshipApplication.objects.get(pk=app.pk))
                if f['fact'] == 'academic')


class TestTheHigherResults(TestCase):
    """The matriculation / STPM / diploma upload (the #56 document)."""

    def _upload(self, name, verdict='name_mismatch'):
        app = _app(STPM_HELD, DEGREE)
        doc = _doc(app, 'higher_results', {**STPM_READ, 'candidate_name': name}, verdict=verdict)
        return app, doc

    def test_a_one_letter_misread_passes_with_a_reviewer_note(self):
        app, doc = self._upload(MISREAD)
        self.assertEqual(_slip_name_status(doc), 'partial')
        self.assertEqual(student_higher_check(doc)['name'], 'partial')
        self.assertEqual(match_verdict(doc), 'ok')
        self.assertEqual(doc_match_verdict(doc), 'ok')
        self.assertNotIn('higher_results_name_mismatch', document_red_blockers(app))
        self.assertTrue(application_completeness(app)['documents_done'])
        self.assertEqual(_academic_red_chips(app), 0)
        f = _academic(app)
        codes = {i['code'] for i in f['unresolved']}
        self.assertIn('higher_results_name_near', codes)
        self.assertNotIn('higher_results_name_mismatch', codes)
        self.assertNotIn('higher_results_name_ok', {i['code'] for i in f['evidence']})
        self.assertNotEqual(f['status'], 'verified')

    def test_a_two_letter_difference_still_blocks(self):
        app, doc = self._upload('RQHQNA A/P GOPAL')
        self.assertEqual(_slip_name_status(doc), 'mismatch')
        self.assertIn('higher_results_name_mismatch', document_red_blockers(app))
        self.assertFalse(application_completeness(app)['documents_done'])
        self.assertIn('higher_results_name_mismatch', {i['code'] for i in _academic(app)['unresolved']})

    def test_one_letter_in_each_of_two_parts_still_blocks(self):
        app, doc = self._upload('RQHANA A/P GQPAL')
        self.assertIn('higher_results_name_mismatch', document_red_blockers(app))
        self.assertFalse(application_completeness(app)['documents_done'])

    def test_a_short_part_still_blocks(self):
        app = _app(STPM_HELD, DEGREE, name='TAN AH KOK')
        _doc(app, 'higher_results', {**STPM_READ, 'candidate_name': 'TAN AH KOW'}, verdict='name_mismatch')
        self.assertIn('higher_results_name_mismatch', document_red_blockers(app))
        self.assertFalse(application_completeness(app)['documents_done'])

    def test_a_near_miss_of_a_parents_name_is_not_the_students_document(self):
        app, doc = self._upload('KQMATHI')     # one letter off the MOTHER'S name, not the student's
        self.assertEqual(_slip_name_status(doc), 'mismatch')

    def test_an_exact_match_is_unchanged(self):
        app, doc = self._upload(OWN, verdict='ok')
        self.assertEqual(_slip_name_status(doc), 'match')
        self.assertNotIn('higher_results_name_mismatch', document_red_blockers(app))
        f = _academic(app)
        self.assertIn('higher_results_name_ok', {i['code'] for i in f['evidence']})
        self.assertNotIn('higher_results_name_near', {i['code'] for i in f['unresolved']})


class TestTheSpmSlip(TestCase):
    """The same shared compare on the SPM results slip."""

    def _upload(self, name, verdict='name_mismatch'):
        app = _app(SPM_HELD, MATRIC_PATHWAY)
        doc = _doc(app, 'results_slip', {'candidate_name': name, 'results': []}, verdict=verdict)
        return app, doc

    def test_a_one_letter_misread_passes_with_a_reviewer_note(self):
        app, doc = self._upload(MISREAD)
        self.assertEqual(_slip_name_status(doc), 'partial')
        self.assertNotIn('results_slip_name_mismatch', document_red_blockers(app))
        self.assertTrue(application_completeness(app)['documents_done'])
        self.assertNotEqual(doc_match_verdict(doc), 'mismatch')
        self.assertNotEqual(verdict_for_document(doc), 'slip_name_mismatch')
        self.assertEqual(_academic_red_chips(app), 0)
        f = _academic(app)
        self.assertIn('results_slip_name_near', {i['code'] for i in f['unresolved']})
        self.assertNotIn('results_slip_name_mismatch', {i['code'] for i in f['unresolved']})
        self.assertNotEqual(f['status'], 'verified')

    def test_another_name_still_blocks(self):
        app, doc = self._upload('RQHQNA A/P GOPAL')
        self.assertEqual(_slip_name_status(doc), 'mismatch')
        self.assertIn('results_slip_name_mismatch', document_red_blockers(app))
        self.assertFalse(application_completeness(app)['documents_done'])
        self.assertEqual(verdict_for_document(doc), 'slip_name_mismatch')
        self.assertEqual(_academic_red_chips(app), 1)

    def test_an_exact_match_is_unchanged(self):
        app, doc = self._upload(OWN, verdict='ok')
        self.assertEqual(_slip_name_status(doc), 'match')
        self.assertIn('results_slip_name_ok', {i['code'] for i in _academic(app)['evidence']})


class TestTheVersion(SimpleTestCase):
    def test_the_engine_version_moved(self):
        self.assertGreaterEqual(VERDICT_ENGINE_VERSION, '2026-11-05.1')
