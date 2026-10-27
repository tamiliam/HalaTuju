"""TD-410 — owner ruling 2026-10-27, "Suspect shouldn't count", narrowed the same day (option A):
only an income proof flagged as possibly FAKE stops counting.

`income_shown.proof_flagged` is read at every door (the per-earner answer, the gate, the cluster,
Check 2's proof ask, the verdict band, TD-409's hold). Flagged: a `not_<type>` wrong-type score, a
`suspect` payslip that names a family OTHER than `informal` (the model emits none today; a legacy or
future formal-family score), a suspect support letter. NOT flagged: an INFORMAL payslip (the model's
only `suspect` — "not a standard payslip"), no genuineness signal at all, and any EPF until TD-411.
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student

STUDENT, STUDENT_NRIC = 'DIVASHINI A/P MURUGAN', '080115-05-0132'
FATHER, FATHER_NRIC = 'MURUGAN A/L SUBRAMANIAM', '700707-05-5671'
FAKE = 'private'          # a suspect payslip naming a formal family = flagged as possibly fake


def _doc(app, doc_type, *, member='', status=None, seen=None, fields=None, verdict='ok'):
    vf = {'fields': fields or {}, 'student_verdict': verdict, 'error': ''}
    if status is not None:
        vf['authenticity'] = {'status': status, 'probability': 0.5}
        if seen is not None:
            vf['authenticity']['doc_seen'] = seen
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, household_member=member, vision_fields=vf,
        storage_path=f'test/{doc_type}/{ApplicantDocument.objects.count()}', vision_run_at=timezone.now())


class _Case(TestCase):

    def _app(self, stage='profile_complete', **kw):
        kw.setdefault('income_route', 'salary')
        kw.setdefault('income_working_members', ['father'])
        kw.setdefault('mother_occupation', 'homemaker')
        return make_application(
            stage, income_earner='', father_name='Murugan', father_occupation='private',
            other_family_members=[], student=make_student(name=STUDENT, nric=STUDENT_NRIC), **kw)

    def _father_ic(self, app):
        return ApplicantDocument.objects.create(
            application=app, doc_type='parent_ic', household_member='father', vision_name=FATHER,
            vision_nric=FATHER_NRIC, storage_path=f'test/pic/{app.id}', vision_run_at=timezone.now())

    def _slip(self, app, status, seen=None, member='father'):
        return _doc(app, 'salary_slip', member=member, status=status, seen=seen,
                    fields={'gross_income': '1,450.00'})


class ThePerEarnerAnswer(_Case):

    def test_a_payslip_flagged_as_possibly_fake_shows_no_income_and_says_why(self):
        from apps.scholarship.income_shown import income_shown
        app = self._app()
        slip = self._slip(app, 'suspect', FAKE)
        a = income_shown(app, 'father')
        self.assertIs(a.shown, False)
        self.assertEqual([u.as_dict() for u in a.unusable],
                         [{'doc_id': slip.id, 'doc_type': 'salary_slip', 'reason': 'suspect'}])

    def test_an_informal_payslip_still_counts(self):
        """Owner option A: every live suspect slip is the informal family — an employer's letter-slip."""
        from apps.scholarship.income_shown import income_shown
        for seen in ('informal', 'INFORMAL', None):
            with self.subTest(seen):
                app = self._app()
                self._slip(app, 'suspect', seen)
                self.assertIs(income_shown(app, 'father').shown, True)

    def test_a_wrong_type_payslip_keeps_its_own_reason(self):
        from apps.scholarship.income_shown import income_shown
        app = self._app()
        self._slip(app, 'not_salary')            # no doc_seen: never read as the informal family
        a = income_shown(app, 'father')
        self.assertIs(a.shown, False)
        self.assertEqual([u.reason for u in a.unusable], ['not_salary'])

    def test_no_genuineness_signal_still_counts(self):
        from apps.scholarship.income_shown import income_shown
        for status in (None, '', 'unchecked', 'genuine', 'likely_genuine'):
            with self.subTest(status):
                app = self._app()
                self._slip(app, status)
                self.assertIs(income_shown(app, 'father').shown, True)

    def test_an_epf_still_counts_whatever_its_score_until_td_411(self):
        """The EPF scorer reads `not_epf` p=0.00 on statements it names `epf` — not trusted yet."""
        from apps.scholarship.income_engine import _member_has_epf_value
        from apps.scholarship.income_shown import income_shown
        for status in ('suspect', 'not_epf', None):
            with self.subTest(status):
                app = self._app()
                _doc(app, 'epf', member='father', status=status, seen='epf',
                     fields={'monthly_contribution': '300.00'})
                self.assertIs(income_shown(app, 'father').shown, True)
                self.assertIs(_member_has_epf_value(app, 'father'), True)

    def test_a_flagged_support_letter_backs_no_declared_amount(self):
        from apps.scholarship.income_engine import has_income_support_doc
        from apps.scholarship.income_shown import income_shown
        for status, shown in (('suspect', False), ('not_income_support_doc', False), (None, True)):
            with self.subTest(status):
                app = self._app(income_declared={'father': 1200})
                _doc(app, 'income_support_doc', member='father', status=status, fields={'issuer': 'Penghulu'})
                self.assertIs(income_shown(app, 'father').shown, shown)
                self.assertIs(has_income_support_doc(app, 'father'), shown)


class TheGate(_Case):

    def test_a_payslip_flagged_as_possibly_fake_does_not_clear_the_salary_route(self):
        from apps.scholarship.income_engine import income_established, member_income_evidenced
        from apps.scholarship.services import income_doc_blockers
        app = self._app()
        self._father_ic(app)
        self._slip(app, 'suspect', FAKE)
        self.assertIs(member_income_evidenced(app, 'father'), False)
        self.assertIs(income_established(app), False)
        self.assertIn('income_evidence_missing:father', income_doc_blockers(app))

    def test_an_informal_genuine_or_unscored_payslip_still_does(self):
        from apps.scholarship.services import income_doc_blockers
        for status, seen in (('suspect', 'informal'), ('genuine', 'private'), (None, None)):
            with self.subTest(status):
                app = self._app()
                self._father_ic(app)
                self._slip(app, status, seen)
                self.assertEqual(income_doc_blockers(app), [])


class CheckTwoAndTheHold(_Case):

    def test_a_flagged_payslip_is_asked_for_again_after_submission(self):
        """The per-member proof ask: the mother works and her only payslip is flagged."""
        from apps.scholarship.check2_queries import sync_check2_queries
        app = self._app(income_working_members=['father', 'mother'], mother_occupation='private',
                        mother_name='Lakshmi')
        self._father_ic(app)
        self._slip(app, 'genuine', 'private')
        self._slip(app, 'suspect', FAKE, member='mother')
        sync_check2_queries(app)
        self.assertTrue(app.resolution_items.filter(code='mother_income_proof_missing', status='open').exists())

    def test_a_flagged_payslip_no_longer_clears_an_str_request(self):
        """TD-409's hold: with only a flagged payslip beside an unmatched STR, the request stays held."""
        from apps.scholarship.models import ResolutionItem
        from apps.scholarship.resolution import sync_resolution_items
        app = self._app(income_route='str', income_working_members=[])
        app.income_earner = 'father'
        app.save(update_fields=['income_earner'])
        item = ResolutionItem.objects.create(application=app, source='system', code='income_proof_missing',
                                             fact='income', kind='doc', doc_type='str')
        self._slip(app, 'suspect', FAKE)
        _doc(app, 'str', fields={'recipient_name': 'MURUGAN A/L SUBRAMANIAM', 'status': 'Lulus',
                                 'year': '2026', 'source_type': 'semakan_status'})   # no card on file
        sync_resolution_items(app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')
        self.assertIs(item.params.get('needs_officer_eye'), True)


class TheVerdict(_Case):

    def test_a_salary_route_payslip_flagged_as_possibly_fake_is_not_verified_income(self):
        from apps.scholarship.verdict_engine import build_verdict
        app = self._app(stage='shortlisted')
        self._father_ic(app)
        self._slip(app, 'suspect', FAKE)
        income = next(f for f in build_verdict(app) if f['fact'] == 'income')
        self.assertNotEqual(income['status'], 'verified')
