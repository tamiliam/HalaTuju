"""TD-119 (Sprint A2.8b) - a NON-earner parent's card was checked against the earner's STR.

On the STR route the STR is the declared earner's own document (architecture doc section 4: cross-check
ONLY the earner's IC against the route's proof; "a non-earner parent's IC has no proof to match, so it
is not flagged"). ``student_income_ic_check`` compared EVERY tagged parent card with the STR, so a
father's genuine card on a mother-STR application read as a name + number mismatch, and the Action
Centre held the task (corpus case a12, a genuine document wrongly flagged). ``parent_ic_reference``
(request #59) already kept this rule; the check now keeps it too. The earner's own card is unchanged.
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship import income_engine
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.resolution import doc_match_verdict
from apps.scholarship.tests.factories import create_document, make_application, make_student

STUDENT_NRIC = '050101-14-1234'
MOTHER_NRIC = '750721-04-5130'
FATHER_NRIC = '700101-14-5677'


def _doc(application, doc_type, member='', **kw):
    kw.setdefault('storage_path', f'test/{doc_type}/{ApplicantDocument.objects.count()}')
    kw.setdefault('content_type', 'image/jpeg')
    return create_document(application=application, doc_type=doc_type, household_member=member, **kw)


def _card(application, member, name, nric):
    return _doc(application, 'parent_ic', member, vision_name=name, vision_nric=nric,
                vision_run_at=timezone.now(), vision_error='', vision_fields={'student_verdict': 'ok'})


class TestANonEarnerCardOnTheStrRoute(TestCase):

    def setUp(self):
        self.app = make_application('profile_complete', income_route='str', income_earner='mother',
                                    father_name='Kumar A/L Raju', mother_name='Saraswathy A/P Muthu',
                                    other_family_members=[],
                                    student=make_student(nric=STUDENT_NRIC, name='Arun A/L Kumar'))
        _doc(self.app, 'str', vision_fields={
            'fields': {'recipient_name': 'Saraswathy A/P Muthu', 'recipient_nric': MOTHER_NRIC},
            'student_verdict': 'ok', 'error': ''})

    def test_the_fathers_card_is_not_checked_against_the_mothers_str(self):
        check = income_engine.student_income_ic_check(
            _card(self.app, 'father', 'Kumar A/L Raju', FATHER_NRIC))
        self.assertEqual((check['proof_kind'], check['proof_name_status'], check['proof_nric_status']),
                         ('', 'no_ref', 'no_ref'))
        self.assertEqual(check['name_status'], 'match')          # the patronymic still links him

    def test_the_fathers_card_no_longer_holds_its_task(self):
        doc = _card(self.app, 'father', 'Kumar A/L Raju', FATHER_NRIC)
        self.assertNotEqual(doc_match_verdict(doc), 'mismatch')

    def test_the_earners_own_card_is_still_checked_against_her_str(self):
        """The control: the earner's card keeps the cross-check, so a wrong card still reds."""
        good = income_engine.student_income_ic_check(
            _card(self.app, 'mother', 'Saraswathy A/P Muthu', MOTHER_NRIC))
        self.assertEqual((good['proof_kind'], good['proof_name_status'], good['proof_nric_status']),
                         ('str', 'match', 'match'))
        wrong = income_engine.student_income_ic_check(
            _card(self.app, 'mother', 'Kumar A/L Raju', FATHER_NRIC))
        self.assertEqual((wrong['proof_name_status'], wrong['proof_nric_status']), ('mismatch', 'mismatch'))

    def test_one_number_two_names_stays_red(self):
        """G7 review: the skip is for a DIFFERENT person only (both fields differ). A non-earner card
        that carries the STR's number under another name, or the STR's name over another number, is
        the old red mismatch."""
        same_number = _card(self.app, 'father', 'Kumar A/L Raju', MOTHER_NRIC)
        check = income_engine.student_income_ic_check(same_number)
        self.assertEqual((check['proof_kind'], check['proof_name_status'], check['proof_nric_status']),
                         ('str', 'mismatch', 'match'))
        self.assertEqual(doc_match_verdict(same_number), 'mismatch')
        same_name = _card(self.app, 'father', 'Saraswathy A/P Muthu', FATHER_NRIC)
        check = income_engine.student_income_ic_check(same_name)
        self.assertEqual((check['proof_kind'], check['proof_name_status'], check['proof_nric_status']),
                         ('str', 'match', 'mismatch'))
        self.assertEqual(doc_match_verdict(same_name), 'mismatch')

    def test_a_fully_different_non_earner_card_is_no_ref(self):
        check = income_engine.student_income_ic_check(
            _card(self.app, 'father', 'Lim Ah Kow', '680202-10-1111'))
        self.assertEqual((check['proof_kind'], check['proof_name_status'], check['proof_nric_status']),
                         ('', 'no_ref', 'no_ref'))

    def test_a_blank_tagged_card_is_read_as_the_earners_and_checked(self):
        """No household tag: the card is the declared earner's, so the STR cross-check still runs."""
        doc = _card(self.app, '', 'Kumar A/L Raju', FATHER_NRIC)
        check = income_engine.student_income_ic_check(doc)
        self.assertEqual(check['member'], 'mother')
        self.assertEqual((check['proof_kind'], check['proof_name_status'], check['proof_nric_status']),
                         ('str', 'mismatch', 'mismatch'))
        self.assertEqual(doc_match_verdict(doc), 'mismatch')

    def test_a_guardian_earner_on_the_str_route(self):
        """A guardian earner's own card is checked against the STR; a parent's different card is not."""
        guardian_nric = '690303-08-2222'
        app = make_application('profile_complete', income_route='str', income_earner='guardian',
                               father_name='Kumar A/L Raju', mother_name='Saraswathy A/P Muthu',
                               other_family_members=[],
                               student=make_student(nric='050202-14-4321', name='Arun A/L Kumar'))
        _doc(app, 'str', vision_fields={
            'fields': {'recipient_name': 'Devi A/P Rama', 'recipient_nric': guardian_nric},
            'student_verdict': 'ok', 'error': ''})
        own = income_engine.student_income_ic_check(_card(app, 'guardian', 'Devi A/P Rama', guardian_nric))
        self.assertEqual((own['proof_kind'], own['proof_name_status'], own['proof_nric_status']),
                         ('str', 'match', 'match'))
        wrong = income_engine.student_income_ic_check(_card(app, 'guardian', 'Kumar A/L Raju', FATHER_NRIC))
        self.assertEqual((wrong['proof_kind'], wrong['proof_name_status'], wrong['proof_nric_status']),
                         ('str', 'mismatch', 'mismatch'))
        mother = income_engine.student_income_ic_check(_card(app, 'mother', 'Saraswathy A/P Muthu', MOTHER_NRIC))
        self.assertEqual((mother['proof_kind'], mother['proof_name_status'], mother['proof_nric_status']),
                         ('', 'no_ref', 'no_ref'))

    def test_the_salary_route_is_unchanged(self):
        """Salary route: each member's card is checked against THAT member's own slip, as before."""
        self.app.income_route, self.app.income_earner = 'salary', 'mother'
        self.app.save(update_fields=['income_route', 'income_earner'])
        _doc(self.app, 'salary_slip', 'father', vision_fields={
            'fields': {'name': 'Kumar A/L Raju', 'nric': FATHER_NRIC, 'gross_income': '1800.00'},
            'student_verdict': 'ok', 'error': ''})
        check = income_engine.student_income_ic_check(
            _card(self.app, 'father', 'Kumar A/L Raju', FATHER_NRIC))
        self.assertEqual((check['proof_kind'], check['proof_name_status'], check['proof_nric_status']),
                         ('salary_slip', 'match', 'match'))
