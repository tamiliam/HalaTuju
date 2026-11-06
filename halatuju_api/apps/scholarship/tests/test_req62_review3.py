"""Request #62 review 3 (2026-11-06): "We are checking what the student has declared with
documentary evidence." When nothing declared was compared, nothing is shown, asked or held; when a
hold happens, it names its reason. Chip, checklist, verdict and ladder agree."""
from django.test import TestCase

from apps.scholarship.academic_engine import student_slip_check
from apps.scholarship.help_engine import verdict_for_document
from apps.scholarship.resolution import doc_match_verdict
from apps.scholarship.tests.test_third_route_s4 import SPM_READ, _academic
from apps.scholarship.tests.test_three_exclusive_spm_routes import (
    CORE, CORE_TYPED, STPM, _codes, _slip_app,
)
from apps.scholarship.verdict_engine import _verdict_academic
from apps.scholarship.verdict_ladder import _academic_red_chips

NO_HIST = CORE[:3]   # Sejarah's row dropped by the reader: a SHORT read


def _higher_app(prereq):
    from apps.scholarship.tests import test_third_route_s3 as s3
    app = s3._app({**s3.STPM_FULL_HELD, 'spm_prereq_grades': prereq}, s3.DEGREE)
    s3._doc(app, 'higher_results', s3.STPM_FULL_READ)
    return app, s3


class NothingCheckedNothingShown(TestCase):
    """Fix 1: a declared subject the read never grade-checked, with nothing flagged, is NOT a tick
    (was: subjects/results 'match') and NOT a silent hold (was: review with no unresolved item)."""

    def _assert_quiet(self, app, doc):
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['results']), ('not_compared', 'not_compared'))
        fact = _verdict_academic(app, True)
        self.assertEqual(fact['unresolved'], [])
        self.assertNotIn('grades_verified', _codes(fact))
        self.assertEqual(_academic_red_chips(app), 0)
        self.assertEqual(doc_match_verdict(doc), 'ok')
        self.assertEqual(verdict_for_document(doc), '')

    def test_short_read_without_the_declared_subject(self):
        app, doc = _slip_app({**STPM, 'spm_prereq_grades': {'phy': 'A'}}, NO_HIST)
        self._assert_quiet(app, doc)

    def test_declared_subject_printed_but_ungraded(self):
        app, doc = _slip_app({**STPM, 'spm_prereq_grades': {'phy': 'A'}})
        doc.vision_fields['fields']['_debug_rows'] = ['1511 FIZIK A']
        doc.save()
        self._assert_quiet(app, doc)

    def test_the_higher_card_is_not_held_by_it(self):
        app, s3 = _higher_app({'phy': 'A'})
        s3._doc(app, 'results_slip', {**SPM_READ, 'results': NO_HIST})
        self.assertEqual(_academic(app)['status'], 'verified')


class SomeCheckedOthersNot(TestCase):
    """Fix 1: some declared subjects checked, others unreachable → results 'pending' and a named
    "please check by eye" item, so the hold has a reason."""

    def test_the_hold_names_the_unchecked_subject(self):
        app, doc = _slip_app({**STPM, 'spm_prereq_grades': CORE_TYPED}, NO_HIST)
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['results']), ('match', 'pending'))
        fact = _verdict_academic(app, True)
        self.assertEqual(fact['status'], 'review')
        items = [i for i in fact['unresolved'] if i['code'] == 'academic_grades_unchecked']
        self.assertEqual([i['params']['subjects'] for i in items], ['Sejarah'])
        self.assertEqual(_academic_red_chips(app), 0)          # please check, never a red chip

    def test_the_higher_card_hold_carries_the_reason(self):
        app, s3 = _higher_app(CORE_TYPED)
        s3._doc(app, 'results_slip', {**SPM_READ, 'results': NO_HIST})
        f = _academic(app)
        self.assertEqual(f['status'], 'review')
        self.assertIn('academic_grades_unchecked', _codes(f))


class NoPrereqUnreadableSlip(TestCase):
    """Fix 3: no prereq + a slip whose subject table did not read → only the name may speak: no
    re-upload ask, the officer's slip request closes."""

    def test_only_the_name_speaks(self):
        app, doc = _slip_app({**STPM, 'spm_prereq_grades': {}}, [])
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['results']), ('not_compared', 'not_compared'))
        self.assertEqual(verdict_for_document(doc), '')
        self.assertEqual(doc_match_verdict(doc), 'ok')

    def test_control_with_a_prereq_still_asks(self):
        app, doc = _slip_app({**STPM, 'spm_prereq_grades': CORE_TYPED}, [])
        self.assertEqual(student_slip_check(doc)['subjects'], 'unreadable')


class WhitespaceGrade(TestCase):
    """Fix 5: a whitespace grade is not entered (was: a mismatch "typed ' '")."""

    def test_whitespace_is_blank(self):
        app, doc = _slip_app({**STPM, 'spm_prereq_grades': {'bm': 'A', 'eng': ' '}})
        chk = student_slip_check(doc)
        self.assertEqual((chk['results'], chk['mismatched']), ('match', []))
        self.assertIn('grades_verified', _codes(_verdict_academic(app, True)))
