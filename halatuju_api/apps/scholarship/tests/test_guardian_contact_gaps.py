"""Request #26 follow-up — the two gaps the build itself reported, closed (2026-10-05).

GAP A — the back door through a SECOND application. `services.create_application` writes the apply
form's `guardians` onto the profile, and the only guard in front of it was "one live application
per student PER ROUND". So a student holding an offered award could apply to another open round,
type their OWN number as the parent's, and — with signing on — receive the guarantor PIN
themselves. Pre-existing (the 2026-07-01 "locked phone" decision had the same hole), but a freeze
with a back door is decorative. Closed: while frozen, the form's guardians are dropped and the
stored one stands; the application is still created and every other field still syncs.

GAP B — defence at the point of use. `sign_agreement` trusted that the number the PIN was checked
against (`application.guarantor_phone`) is still the number on file. An admin correction during the
window (owner ruling R3) breaks that — the old check vouched for the wrong phone. Now signing
refuses `guarantor_phone_changed` until the guarantor re-verifies on the current number.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship import bursary
from apps.scholarship.bursary import BursaryError
from apps.scholarship.models import BursaryAgreement, ScholarshipApplication
from apps.scholarship.tests.contract_helpers import flagship
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_cohort
from apps.scholarship.tests.test_guardian_contact import PARENT, _award, _state
from apps.scholarship.tests.test_td229_contract_per_gift import (
    GUAR_PHONE, _deployed, _sign, _signable,
)

APPLY = '/api/v1/scholarship/applications/'
MY_OWN = '019-000 1111'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestGapA_ASecondApplicationCannotMoveAFrozenPhone(TestCase):

    def _apply_elsewhere(self):
        profile, offered_app = _state('awarded_offer_open')
        second = make_cohort(is_open=True)
        resp = authed_client(profile).post(APPLY, {
            'cohort_code': second.code, 'consent_to_contact': True, 'intends_tertiary_2026': True,
            'guardians': [{'name': 'Me Myself', 'phone': MY_OWN}],
            'school': 'SMK Baru', 'household_income': 1234,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        # The application IS created — a student holding an offer may apply elsewhere.
        self.assertTrue(ScholarshipApplication.objects.filter(profile=profile, cohort=second).exists())
        profile.refresh_from_db()
        offered_app.refresh_from_db()
        return profile, offered_app

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_flag_on_and_frozen_the_parent_phone_does_not_move_but_the_rest_syncs(self):
        profile, offered_app = self._apply_elsewhere()
        self.assertEqual(profile.guardians, [PARENT])
        self.assertEqual(bursary.guarantor_phone_for(offered_app), PARENT['phone'])
        # …and every other field on the form still reached the profile.
        self.assertEqual((profile.school, profile.household_income), ('SMK Baru', 1234))

    @override_settings(BURSARY_AGREEMENT_ENABLED=False)
    def test_flag_off_nobody_is_frozen_so_the_same_submission_updates_it(self):
        profile, offered_app = self._apply_elsewhere()
        self.assertEqual(profile.guardians, [{'name': 'Me Myself', 'phone': MY_OWN}])
        self.assertEqual(bursary.guarantor_phone_for(offered_app), MY_OWN)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True, PHONE_VERIFY_CHANNEL='sms',
                   TWILIO_ACCOUNT_SID='sid', TWILIO_AUTH_TOKEN='tok',
                   TWILIO_VERIFY_SERVICE_SID='VA-test')
class TestGapB_SigningRefusesAPhoneChangedAfterThePin(TestCase):
    """verify → an admin corrects the number → sign is refused → re-verify → signs."""

    def setUp(self):
        self.template = _deployed('2026-r26', flagship(), 'Flagship Signatory')
        self.app = _signable(flagship(), comprehension_template=self.template)  # verified on GUAR_PHONE
        _award(self.app, 'offered')                    # the signing window: the PIN views serve it
        self.boss = make_admin('super', super_admin=True)

    def _admin_correct(self, phone):
        resp = authed_client(self.boss).post(
            f'/api/v1/admin/scholarship/applications/{self.app.pk}/guardian-contact/',
            {'name': self.app.profile.guardians[0]['name'], 'phone': phone}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.app.refresh_from_db()
        self.app.profile.refresh_from_db()

    @patch('apps.scholarship.whatsapp._post_to_verify', return_value={'status': 'approved'})
    @patch('apps.scholarship.storage.upload_object', return_value=True)
    @patch('apps.scholarship.bursary.generate_pdf', return_value=b'%PDF-local')
    def test_a_changed_number_is_refused_until_the_guarantor_re_verifies(self, _pdf, _up, _verify):
        self._admin_correct('013-999 8888')
        with self.assertRaises(BursaryError) as cm:
            _sign(self.app)
        self.assertEqual(cm.exception.code, 'guarantor_phone_changed')
        self.assertFalse(BursaryAgreement.objects.filter(application=self.app).exists())

        # Re-verify through the REAL check view: it stamps the number now on file.
        resp = authed_client(self.app.profile).post(
            '/api/v1/scholarship/award/guarantor/verify-phone/check/', {'code': '123456'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.app.refresh_from_db()
        self.assertEqual(self.app.guarantor_phone, '013-999 8888')
        self.assertIsNotNone(_sign(self.app).pk)

    @patch('apps.scholarship.storage.upload_object', return_value=True)
    @patch('apps.scholarship.bursary.generate_pdf', return_value=b'%PDF-local')
    def test_the_same_number_written_differently_is_not_a_change(self, _pdf, _up):
        # The PIN goes to the E.164 form, so a reformatted copy of the SAME number still vouches.
        self._admin_correct(GUAR_PHONE.replace('-', ' '))
        self.assertNotEqual(self.app.profile.guardians[0]['phone'], GUAR_PHONE)
        self.assertIsNotNone(_sign(self.app).pk)

    def test_same_phone_reads_the_number_not_the_spelling(self):
        self.assertTrue(bursary.same_phone('013-111 2222', '+60131112222'))
        self.assertFalse(bursary.same_phone('013-111 2222', '013-999 8888'))
        self.assertFalse(bursary.same_phone('', '013-111 2222'))
