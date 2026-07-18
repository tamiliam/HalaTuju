"""Contract module Sprint 2 — the engine cutover.

Proves: a template-driven payment run is item-for-item identical to the legacy
constants run for Jul–Nov (the guard for the 30 live students); the STPM Dec gap
month greys only under a template; bursary.sign_agreement raises no_active_template
(flag on, no template) and comprehension_stale (signed after a redeploy without
re-taking the quiz); particulars + render read the template; and the student quiz
GET is served from the template.
"""
import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship import bursary, contracts, payments
from apps.scholarship.bursary import BursaryError
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort

from apps.scholarship.tests.contract_helpers import brightpath_org, make_deployable
from apps.scholarship.tests.test_sponsorship import _token, TEST_JWT_SECRET

GUAR_NAME, GUAR_NRIC, GUAR_PHONE = 'Rahmah Binti Ahmad', '700101-10-5555', '013-1112222'


def _deploy(version='2026-v1'):
    """A deployed (active) BrightPath template."""
    t = make_deployable(version)
    contracts.submit_for_deployment(t)
    return contracts.deploy(t, is_super=True)


def _cohort(year=2026):
    return ScholarshipCohort.objects.create(
        code='cut', name='B40', year=year, owning_organisation=brightpath_org())


def _app(cohort, *, pathway, suffix, award='3000', vircle='8000400175001',
         reporting=datetime.date(2026, 1, 1), status='awarded'):
    p = StudentProfile.objects.create(
        supabase_user_id=f'cut-{suffix}', name='Cut Student', nric='000101-10-1233',
        exam_type='spm', grades={'bm': 'A'}, contact_email='s@e.test',
        guardians=[{'name': GUAR_NAME, 'phone': GUAR_PHONE}])
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=p, status=status, chosen_pathway=pathway,
        award_amount=Decimal(award), vircle_id=vircle, reporting_date=reporting)
    return app


class TestPaymentRunParity(TestCase):
    """Jul–Nov: the template-driven run == the legacy-constants run, item for item."""

    def setUp(self):
        self.org = brightpath_org()
        self.cohort = _cohort(2026)
        # A spread of pathways (different start floors, all RM200).
        self.apps = [
            _app(self.cohort, pathway='stpm', suffix='sf'),
            _app(self.cohort, pathway='matric', suffix='m'),
            _app(self.cohort, pathway='poly', suffix='p'),
            _app(self.cohort, pathway='pismp', suffix='pi'),
        ]

    def _amount_map(self, pay_date, period):
        out = {}
        for r in payments.eligible_rows(self.org, pay_date, period_month=period):
            if r['eligible']:
                app = r['application']
                out[app.id] = payments.default_amount(app, payments._schedule_row(app))
        return out

    def test_jul_to_nov_identical_legacy_vs_template(self):
        months = [(7, datetime.date(2026, 7, 1)), (8, datetime.date(2026, 8, 1)),
                  (9, datetime.date(2026, 9, 1)), (10, datetime.date(2026, 10, 1)),
                  (11, datetime.date(2026, 11, 1))]
        legacy = {m: self._amount_map(d, d) for m, d in months}
        # No active template yet → legacy flat behaviour.
        self.assertIsNone(contracts.active_template_for(self.org))
        _deploy()
        self.assertIsNotNone(contracts.active_template_for(self.org))
        templated = {m: self._amount_map(d, d) for m, d in months}
        self.assertEqual(legacy, templated)
        # And every eligible amount is exactly RM200 (sanity — not an empty match).
        self.assertTrue(any(legacy.values()))
        for month_map in legacy.values():
            for amt in month_map.values():
                self.assertEqual(amt, Decimal('200.00'))


class TestGapMonthGreying(TestCase):
    def setUp(self):
        self.cohort = _cohort(2026)
        self.app = _app(self.cohort, pathway='stpm', suffix='g')

    def test_stpm_december_greys_only_under_template(self):
        dec = datetime.date(2026, 12, 1)
        legacy = payments.eligibility(self.app, dec, period_month=dec)
        self.assertNotIn('gap_month', legacy['reasons'])
        self.assertTrue(legacy['eligible'])
        _deploy()
        templated = payments.eligibility(self.app, dec, period_month=dec)
        self.assertIn('gap_month', templated['reasons'])
        self.assertFalse(templated['eligible'])

    def test_stpm_july_paid_under_template(self):
        _deploy()
        jul = datetime.date(2026, 7, 1)
        elig = payments.eligibility(self.app, jul, period_month=jul)
        self.assertNotIn('gap_month', elig['reasons'])
        self.assertTrue(elig['eligible'])

    def test_schedule_complete_past_end(self):
        _deploy()
        # STPM last paid offset is 16 (Nov of the 2nd year, 2027) → Dec 2027 is past the end.
        dec27 = datetime.date(2027, 12, 1)
        elig = payments.eligibility(self.app, dec27, period_month=dec27)
        self.assertIn('schedule_complete', elig['reasons'])


def _make_signable(app, *, comprehension_template=None):
    """Give an app everything sign_agreement needs to reach the template check:
    a matching parent_ic + a fresh guarantor-phone verification."""
    ApplicantDocument.objects.create(
        application=app, doc_type='parent_ic', storage_path=f'{app.id}/parent_ic.jpg',
        vision_run_at=timezone.now(), vision_name=GUAR_NAME, vision_nric=GUAR_NRIC,
        vision_error='')
    app.guarantor_phone = GUAR_PHONE
    app.guarantor_phone_verified_at = timezone.now()
    if comprehension_template is not None:
        app.comprehension_template = comprehension_template
    app.save(update_fields=['guarantor_phone', 'guarantor_phone_verified_at',
                            'comprehension_template'])


class TestSignAgreementGuards(TestCase):
    def setUp(self):
        self.cohort = _cohort(2026)

    def _sign(self, app):
        return bursary.sign_agreement(
            app, student_signed_name='Cut Student', student_signed_nric='000101-10-1233',
            guarantor_name=GUAR_NAME, guarantor_nric=GUAR_NRIC,
            guarantor_relationship='mother')

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_no_active_template_raises_with_flag_on(self):
        app = _app(self.cohort, pathway='matric', suffix='nat')
        _make_signable(app)
        self.assertIsNone(contracts.active_template_for(brightpath_org()))
        with self.assertRaises(BursaryError) as cm:
            self._sign(app)
        self.assertEqual(cm.exception.code, 'no_active_template')

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_comprehension_stale_after_redeploy(self):
        v1 = _deploy('2026-v1')
        app = _app(self.cohort, pathway='matric', suffix='stale')
        _make_signable(app, comprehension_template=v1)   # passed the quiz on v1
        v2 = _deploy('2026-v2')                           # redeploy → v1 archived, v2 active
        self.assertEqual(contracts.active_template_for(brightpath_org()), v2)
        with self.assertRaises(BursaryError) as cm:
            self._sign(app)
        self.assertEqual(cm.exception.code, 'comprehension_stale')

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    @patch('apps.scholarship.storage.upload_object', return_value=True)
    @patch('apps.scholarship.bursary.generate_pdf', return_value=b'%PDF-local')
    def test_happy_path_stores_template_and_version(self, _pdf, _up):
        tmpl = _deploy('2026-v1')
        app = _app(self.cohort, pathway='stpm', suffix='ok')
        _make_signable(app, comprehension_template=tmpl)
        agreement = self._sign(app)
        self.assertEqual(agreement.template_id, tmpl.id)
        self.assertEqual(agreement.version, tmpl.version)
        # Rendered from the template: English-authoritative notice, no DRAFT banner,
        # the counterparty name, the co-signer wording, and the STPM Schedule-1 gap.
        html = agreement.rendered_html
        self.assertIn('authoritative', html)
        self.assertNotIn('DRAFT', html)
        self.assertIn('Test Signatory', html)      # template counterparty_name
        self.assertIn('Co-signer', html)           # parent_role = co_signer_all
        self.assertIn('Exam month', html)          # STPM Dec/Jun gap in Schedule 1


class TestParticularsAndRender(TestCase):
    def setUp(self):
        self.cohort = _cohort(2026)
        self.app = _app(self.cohort, pathway='stpm', suffix='pr')
        self.tmpl = _deploy()

    def test_particulars_schedule_from_template(self):
        p = bursary.particulars_for(self.app, self.tmpl, 'en')
        self.assertIn('RM200', p['payment_schedule'])   # from the template's schedule row
        self.assertEqual(p['foundation_signatory_name'], 'Test Signatory')



class TestBursaryE2ECommand(TestCase):
    """Lock the seed→deploy→sign→countersign→execute driver green in CI (it seeds
    a template, so a cutover regression would break it). Runs both chain paths."""

    def test_e2e_runs_with_and_without_partner_org(self):
        from django.core.management import call_command
        call_command('bursary_e2e', verbosity=0)          # with referring partner
        call_command('bursary_e2e', no_org=True, verbosity=0)   # graceful Foundation-direct


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestComprehensionQuizApi(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.cohort = _cohort(2026)
        self.app = _app(self.cohort, pathway='stpm', suffix='api')
        self.tmpl = _deploy()

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(self.app.profile_id)}')

    def test_quiz_get_serves_template_checkpoints(self):
        self._auth()
        resp = self.client.get('/api/v1/scholarship/award/comprehension-quiz/?locale=en')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['template_version'], self.tmpl.version)
        self.assertEqual(resp.data['locale_used'], 'en')
        self.assertEqual(len(resp.data['checkpoints']), 8)
        self.assertTrue(all('question' in c for c in resp.data['checkpoints']))

    def test_pass_pins_comprehension_template(self):
        self._auth()
        resp = self.client.post('/api/v1/scholarship/award/comprehension/',
                                {'template_version': self.tmpl.version}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.comprehension_template_id, self.tmpl.id)
        self.assertIsNotNone(self.app.comprehension_passed_at)

    def test_pass_with_stale_version_409(self):
        self._auth()
        resp = self.client.post('/api/v1/scholarship/award/comprehension/',
                                {'template_version': '1999-old'}, format='json')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data['code'], 'version_changed')
        self.assertEqual(resp.data['template_version'], self.tmpl.version)
