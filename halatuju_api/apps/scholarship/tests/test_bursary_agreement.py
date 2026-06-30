"""Conditional Bursary Award Agreement — the binding bursary contract signed when a
student accepts an award.

All external seams are MOCKED (no network / billable calls):
  - ``apps.scholarship.bursary.generate_pdf`` → returns dummy PDF bytes;
  - ``apps.scholarship.storage.upload_object`` / ``create_signed_download_url``.
The test application carries a ``parent_ic`` ApplicantDocument whose OCR'd NRIC/name
match the guarantor we pass, so the identity gate passes deterministically (no live
Vision). The flag is forced ON where the agreement is exercised; the OFF path asserts
the old behaviour is untouched.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import bursary
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    ApplicantDocument, BursaryAgreement, Consent, Donation,
    ScholarshipApplication, ScholarshipCohort, Sponsor, SponsorProfile,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADULT_NRIC = '000101-10-1233'   # born 2000 → adult
MINOR_NRIC = '100101-10-1234'   # born 2010 → minor
GUARANTOR_NRIC = '700101-10-5555'
GUARANTOR_NAME = 'Rahmah Binti Ahmad'
GUARANTOR_PHONE = '013-1112222'


def _token(uid, email='x@x.com'):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated', 'email': email,
         'email_verified': True, 'is_anonymous': False},
        TEST_JWT_SECRET, algorithm='HS256')


def _fundable_app(cohort, *, suffix='1', nric=ADULT_NRIC, award=Decimal('3000'), org=None):
    profile = StudentProfile.objects.create(
        supabase_user_id=f'stu-{suffix}', name='Zxq Student', nric=nric,
        preferred_state='Kedah', exam_type='spm', grades={'bm': 'A'},
        contact_email='student@secret.example', contact_phone='012-7776666',
        guardians=[{'name': GUARANTOR_NAME, 'phone': GUARANTOR_PHONE}],
        referred_by_org=org,
    )
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, status='recommended', award_amount=award,
        notify_email='student@secret.example',
        chosen_programme={'course_name': 'Diploma in Nursing', 'institution': 'Politeknik KL'})
    SponsorProfile.objects.create(application=app, anon_markdown='Determined.', anon_published=True)
    Consent.objects.create(application=app, consent_type='share_with_sponsors', version='e', is_active=True)
    return app


def _add_parent_ic(app, *, name=GUARANTOR_NAME, nric=GUARANTOR_NRIC):
    """A parent_ic doc whose OCR fields make guarantor_identity_check pass."""
    return ApplicantDocument.objects.create(
        application=app, doc_type='parent_ic', storage_path=f'{app.id}/parent_ic.jpg',
        vision_run_at=timezone.now(), vision_name=name, vision_nric=nric, vision_error='')


def _verify_guarantor_phone(app, *, when=None):
    """Stamp a (by default FRESH) guarantor phone-PIN verification — the same-session
    parent gate sign_agreement requires before recording the surety signature."""
    app.guarantor_phone = GUARANTOR_PHONE
    app.guarantor_phone_verified_at = when or timezone.now()
    app.save(update_fields=['guarantor_phone', 'guarantor_phone_verified_at'])


def _sponsor(uid='spon-1'):
    return Sponsor.objects.create(
        supabase_user_id=uid, name='Jane Sponsor', email='jane@sponsor.example',
        phone='0123', source='friend', consent_at=timezone.now(), status='approved')


def _fund(app):
    s = _sponsor()
    Donation.objects.create(sponsor=s, amount=Decimal('3000'))
    return svc.fund_student(s, app)


# Patch the PDF + storage seams for every test in this module.
def _mock_seams():
    pdf = patch('apps.scholarship.bursary.generate_pdf', return_value=b'%PDF-1.4 test')
    upload = patch('apps.scholarship.storage.upload_object', return_value=True)
    dl = patch('apps.scholarship.storage.create_signed_download_url',
               return_value='https://signed.example/agreement.pdf')
    return pdf, upload, dl


@override_settings(BURSARY_AGREEMENT_ENABLED=True)
class TestBursaryService(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.pdf, self.upload, self.dl = _mock_seams()
        self.mock_pdf = self.pdf.start()
        self.mock_upload = self.upload.start()
        self.mock_dl = self.dl.start()
        self.addCleanup(self.pdf.stop)
        self.addCleanup(self.upload.stop)
        self.addCleanup(self.dl.stop)

    def test_adult_accept_creates_binding_agreement(self):
        app = _fundable_app(self.cohort)
        _add_parent_ic(app)
        _fund(app)
        _verify_guarantor_phone(app)
        sp = svc.respond_to_award(
            app, action='accept', student_signed_name='Zxq Student',
            guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
            guarantor_relationship='mother')
        self.assertEqual(sp.status, 'active')
        app.refresh_from_db()
        self.assertEqual(app.status, 'awarded')   # student + guarantor signed; Foundation counter-sign pending
        ag = app.bursary_agreement
        self.assertEqual(ag.status, 'binds')
        self.assertTrue(ag.binds)
        self.assertTrue(ag.rendered_html)
        self.assertEqual(len(ag.agreement_sha256), 64)
        self.assertTrue(ag.pdf_storage_path)
        self.assertEqual(ag.award_amount, Decimal('3000'))
        self.mock_upload.assert_called_once()

    def test_nric_mismatch_rolls_back(self):
        app = _fundable_app(self.cohort, suffix='nric')
        _add_parent_ic(app, nric='999999-99-9999')   # IC NRIC differs from typed
        _fund(app)
        with self.assertRaises(svc.SponsorshipError) as e:
            svc.respond_to_award(
                app, action='accept', student_signed_name='Zxq Student',
                guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
                guarantor_relationship='mother')
        self.assertEqual(e.exception.code, 'parent_ic_nric_mismatch')
        app.refresh_from_db()
        self.assertEqual(app.status, 'awarded')   # accept rolled back; the offer (fund → 'awarded') still stands
        self.assertFalse(BursaryAgreement.objects.filter(application=app).exists())
        self.assertFalse(app.sponsorships.filter(status='active').exists())

    def test_name_mismatch(self):
        app = _fundable_app(self.cohort, suffix='name')
        _add_parent_ic(app, name='Totally Different Person')
        _fund(app)
        with self.assertRaises(svc.SponsorshipError) as e:
            svc.respond_to_award(
                app, action='accept', student_signed_name='Zxq Student',
                guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
                guarantor_relationship='mother')
        self.assertEqual(e.exception.code, 'parent_ic_name_mismatch')
        self.assertFalse(BursaryAgreement.objects.filter(application=app).exists())

    def test_parent_ic_missing(self):
        app = _fundable_app(self.cohort, suffix='noic')   # no parent_ic uploaded
        _fund(app)
        with self.assertRaises(svc.SponsorshipError) as e:
            svc.respond_to_award(
                app, action='accept', student_signed_name='Zxq Student',
                guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
                guarantor_relationship='mother')
        self.assertEqual(e.exception.code, 'parent_ic_missing')
        self.assertFalse(BursaryAgreement.objects.filter(application=app).exists())

    def test_adult_missing_student_signature(self):
        app = _fundable_app(self.cohort, suffix='nosig')
        _add_parent_ic(app)
        _fund(app)
        with self.assertRaises(svc.SponsorshipError) as e:
            svc.respond_to_award(
                app, action='accept',   # no student_signed_name
                guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
                guarantor_relationship='mother')
        self.assertEqual(e.exception.code, 'student_signature_required')

    def test_minor_guardian_is_guarantor(self):
        app = _fundable_app(self.cohort, suffix='m', nric=MINOR_NRIC)
        _add_parent_ic(app)
        _fund(app)
        _verify_guarantor_phone(app)
        sp = svc.respond_to_award(
            app, action='accept', granted_by='guardian',
            guardian_name=GUARANTOR_NAME, guardian_relationship='mother',
            guardian_nric=GUARANTOR_NRIC)
        self.assertEqual(sp.status, 'active')
        ag = app.bursary_agreement
        self.assertTrue(ag.binds)
        self.assertEqual(ag.guarantor_name, GUARANTOR_NAME)

    def test_decline_creates_no_agreement(self):
        app = _fundable_app(self.cohort, suffix='dec')
        _add_parent_ic(app)
        _fund(app)
        svc.respond_to_award(app, action='decline')
        self.assertFalse(BursaryAgreement.objects.filter(application=app).exists())

    def test_countersign_and_witness(self):
        org = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        app = _fundable_app(self.cohort, suffix='cw', org=org)
        _add_parent_ic(app)
        _fund(app)
        _verify_guarantor_phone(app)
        svc.respond_to_award(
            app, action='accept', student_signed_name='Zxq Student',
            guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
            guarantor_relationship='mother')
        ag = app.bursary_agreement
        bursary.countersign_foundation(ag, by_name='The Super')
        ag.refresh_from_db()
        self.assertEqual(ag.foundation_signed_by, 'The Super')
        self.assertEqual(ag.status, 'countersigned')
        bursary.record_witness(ag, org=org, by_name='Partner Admin', witness_name='CUMIG')
        ag.refresh_from_db()
        self.assertEqual(ag.status, 'executed')
        self.assertTrue(ag.is_executed)

    def test_anonymity_no_donor_in_html_or_serializer(self):
        from apps.scholarship.serializers import BursaryAgreementSerializer
        app = _fundable_app(self.cohort, suffix='anon')
        _add_parent_ic(app)
        _fund(app)
        _verify_guarantor_phone(app)
        svc.respond_to_award(
            app, action='accept', student_signed_name='Zxq Student',
            guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
            guarantor_relationship='mother')
        ag = app.bursary_agreement
        # The Foundation signatory IS named…
        self.assertIn('Suresh', ag.rendered_html)
        data = BursaryAgreementSerializer(ag).data
        self.assertEqual(data['foundation_signatory_name'], 'Suresh')
        # …but the donor is NEVER named anywhere.
        blob = ag.rendered_html + str(data)
        self.assertNotIn('Jane Sponsor', blob)
        self.assertNotIn('jane@sponsor.example', blob)


class TestBursaryFlagOff(TestCase):
    """Flag OFF (default): acceptance works with NO signature fields and creates no agreement."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_accept_without_signature_fields_no_agreement(self):
        app = _fundable_app(self.cohort, suffix='off')
        # No parent_ic, no signature fields — exactly the old call shape.
        _fund(app)
        sp = svc.respond_to_award(app, action='accept')
        self.assertEqual(sp.status, 'active')
        app.refresh_from_db()
        self.assertEqual(app.status, 'active')   # flag OFF: no signing step → cool-off (0) finalises to 'active'
        self.assertFalse(BursaryAgreement.objects.filter(application=app).exists())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestBursaryEndpoints(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()
        self.pdf, self.upload, self.dl = _mock_seams()
        self.pdf.start(); self.upload.start(); self.dl.start()
        self.addCleanup(self.pdf.stop)
        self.addCleanup(self.upload.stop)
        self.addCleanup(self.dl.stop)

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _signed_app(self, *, suffix, org=None):
        app = _fundable_app(self.cohort, suffix=suffix, org=org)
        _add_parent_ic(app)
        _fund(app)
        _verify_guarantor_phone(app)
        svc.respond_to_award(
            app, action='accept', student_signed_name='Zxq Student',
            guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
            guarantor_relationship='mother')
        return app

    def test_student_bursary_agreement_endpoint(self):
        app = self._signed_app(suffix='ep')
        self._auth('stu-ep')
        resp = self.client.get('/api/v1/scholarship/bursary-agreement/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'binds')
        self.assertEqual(resp.data['pdf_url'], 'https://signed.example/agreement.pdf')

    def test_super_can_countersign(self):
        app = self._signed_app(suffix='cs')
        PartnerAdmin.objects.create(
            supabase_user_id='super-1', name='Boss', email='boss@h.org',
            is_super_admin=True, role='super', is_active=True)
        self._auth('super-1')
        resp = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/bursary-agreement/countersign/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'countersigned')
        app.bursary_agreement.refresh_from_db()
        self.assertEqual(app.bursary_agreement.foundation_signed_by, 'Boss')

    def test_referring_partner_can_witness(self):
        org = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        app = self._signed_app(suffix='wok', org=org)
        PartnerAdmin.objects.create(
            supabase_user_id='partner-1', name='Cik Partner', email='p@cumig.org',
            org=org, role='partner', is_active=True)
        self._auth('partner-1')
        resp = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/bursary-agreement/witness/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(app.bursary_agreement.__class__.objects.get(id=app.bursary_agreement.id).witness_signed_at)

    def test_non_referring_partner_cannot_witness(self):
        org = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        other = PartnerOrganisation.objects.create(code='other', name='OTHER')
        app = self._signed_app(suffix='w403', org=org)
        PartnerAdmin.objects.create(
            supabase_user_id='partner-2', name='Wrong Org', email='p@other.org',
            org=other, role='partner', is_active=True)
        self._auth('partner-2')
        resp = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/bursary-agreement/witness/')
        self.assertEqual(resp.status_code, 403)

    def test_missing_witness_does_not_block_activation(self):
        # The witness is non-blocking: student + guarantor + Foundation is enough to execute the
        # agreement → the application reaches 'active' even with no witness recorded.
        app = self._signed_app(suffix='nowit')   # student + guarantor signed → 'awarded'
        app.refresh_from_db()
        self.assertEqual(app.status, 'awarded')   # not active yet — Foundation hasn't counter-signed
        bursary.countersign_foundation(app.bursary_agreement, by_name='The Foundation')
        app.refresh_from_db()
        self.assertEqual(app.status, 'active')     # executed without a witness
        self.assertIsNone(app.bursary_agreement.witness_signed_at)


@override_settings(BURSARY_AGREEMENT_ENABLED=True)
class TestGuarantorPhoneGate(TestCase):
    """Same-session parent gate: sign_agreement requires a FRESH guarantor phone-PIN
    verification AND a phone on file — neither a stale stamp nor a missing number passes."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.pdf, self.upload, self.dl = _mock_seams()
        self.pdf.start(); self.upload.start(); self.dl.start()
        self.addCleanup(self.pdf.stop)
        self.addCleanup(self.upload.stop)
        self.addCleanup(self.dl.stop)

    def _accept(self, app):
        return svc.respond_to_award(
            app, action='accept', student_signed_name='Zxq Student',
            guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
            guarantor_relationship='mother')

    def test_unverified_phone_blocks_signing(self):
        app = _fundable_app(self.cohort, suffix='gp1')   # phone on file, no PIN stamp
        _add_parent_ic(app)
        _fund(app)
        with self.assertRaises(svc.SponsorshipError) as e:
            self._accept(app)
        self.assertEqual(e.exception.code, 'guarantor_phone_unverified')
        self.assertFalse(BursaryAgreement.objects.filter(application=app).exists())

    def test_no_guardian_phone_blocks_signing(self):
        app = _fundable_app(self.cohort, suffix='gp2')
        app.profile.guardians = []
        app.profile.save(update_fields=['guardians'])
        _add_parent_ic(app)
        _fund(app)
        _verify_guarantor_phone(app)   # stamp present but no number on file → still blocked
        with self.assertRaises(svc.SponsorshipError) as e:
            self._accept(app)
        self.assertEqual(e.exception.code, 'guarantor_phone_missing')

    def test_stale_verification_refused(self):
        app = _fundable_app(self.cohort, suffix='gp3')
        _add_parent_ic(app)
        _fund(app)
        _verify_guarantor_phone(app, when=timezone.now() - timedelta(hours=2))
        with self.assertRaises(svc.SponsorshipError) as e:
            self._accept(app)
        self.assertEqual(e.exception.code, 'guarantor_phone_unverified')

    def test_fresh_verification_allows_signing(self):
        app = _fundable_app(self.cohort, suffix='gp4')
        _add_parent_ic(app)
        _fund(app)
        _verify_guarantor_phone(app)
        sp = self._accept(app)
        self.assertEqual(sp.status, 'active')
        self.assertTrue(BursaryAgreement.objects.filter(application=app).exists())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True, PHONE_VERIFY_CHANNEL='sms',
                   TWILIO_ACCOUNT_SID='sid', TWILIO_AUTH_TOKEN='tok',
                   TWILIO_VERIFY_SERVICE_SID='VA-test')
class TestGuarantorPhoneEndpoints(TestCase):
    """The send/check verify endpoints. The Twilio HTTP seam (``_post_to_verify``) is
    mocked — never a live call."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _offered_app(self, suffix):
        app = _fundable_app(self.cohort, suffix=suffix)
        _add_parent_ic(app)
        _fund(app)   # offered sponsorship → app 'awarded'; _award_application finds it
        return app

    @patch('apps.scholarship.whatsapp._post_to_verify', return_value={'status': 'pending'})
    def test_send_pin_to_locked_phone(self, mock_post):
        self._offered_app('e1')
        self._auth('stu-e1')
        resp = self.client.post('/api/v1/scholarship/award/guarantor/verify-phone/send/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'sent')
        self.assertTrue(resp.data['phone_hint'].endswith('2222'))
        # The number handed to Twilio is the LOCKED guardian phone, normalised to E.164.
        self.assertIn('+60131112222', str(mock_post.call_args))

    @patch('apps.scholarship.whatsapp._post_to_verify', return_value={'status': 'approved'})
    def test_check_pin_stamps_verification(self, mock_post):
        app = self._offered_app('e2')
        self._auth('stu-e2')
        resp = self.client.post('/api/v1/scholarship/award/guarantor/verify-phone/check/',
                                {'code': '123456'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['verified'])
        app.refresh_from_db()
        self.assertIsNotNone(app.guarantor_phone_verified_at)
        self.assertEqual(app.guarantor_phone, GUARANTOR_PHONE)

    @patch('apps.scholarship.whatsapp._post_to_verify', return_value={'status': 'pending'})
    def test_wrong_pin_rejected_no_stamp(self, mock_post):
        app = self._offered_app('e3')
        self._auth('stu-e3')
        resp = self.client.post('/api/v1/scholarship/award/guarantor/verify-phone/check/',
                                {'code': '000000'}, format='json')
        self.assertEqual(resp.status_code, 400)
        app.refresh_from_db()
        self.assertIsNone(app.guarantor_phone_verified_at)

    def test_send_requires_an_offer(self):
        self._auth('nobody')   # authenticated but no offered award
        resp = self.client.post('/api/v1/scholarship/award/guarantor/verify-phone/send/')
        self.assertEqual(resp.status_code, 403)

    @override_settings(BURSARY_AGREEMENT_ENABLED=False)
    def test_send_blocked_while_bursary_dark(self):
        self._offered_app('e5')
        self._auth('stu-e5')
        resp = self.client.post('/api/v1/scholarship/award/guarantor/verify-phone/send/')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data['code'], 'bursary_disabled')


@override_settings(BURSARY_AGREEMENT_ENABLED=True)
class TestSigningChainNotifications(TestCase):
    """S4: after each signature the right party is emailed, in order — partner witness →
    Foundation countersign → student executed. The no-org path skips straight to the
    Foundation; emails are best-effort and never break signing."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        from django.core import mail
        self.mail = mail
        self.pdf, self.upload, self.dl = _mock_seams()
        self.pdf.start(); self.upload.start(); self.dl.start()
        self.addCleanup(self.pdf.stop)
        self.addCleanup(self.upload.stop)
        self.addCleanup(self.dl.stop)

    def _super(self, email='foundation@h.org'):
        return PartnerAdmin.objects.create(
            supabase_user_id=f'sup-{email}', name='The Foundation', email=email,
            is_super_admin=True, role='super', is_active=True)

    def _accept(self, app):
        _verify_guarantor_phone(app)
        return svc.respond_to_award(
            app, action='accept', student_signed_name='Zxq Student',
            guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
            guarantor_relationship='mother')

    def test_no_org_guarantor_signed_emails_foundation(self):
        self._super('foundation@h.org')
        app = _fundable_app(self.cohort, suffix='n1')   # no referring org
        _add_parent_ic(app)
        _fund(app)
        self.mail.outbox = []
        self._accept(app)
        bodies = [m.to[0] for m in self.mail.outbox]
        self.assertIn('foundation@h.org', bodies)
        self.assertTrue(any('countersignature' in m.subject.lower() for m in self.mail.outbox))

    def test_org_guarantor_signed_emails_partner_witness(self):
        org = PartnerOrganisation.objects.create(
            code='cumig', name='CUMIG', contact_email='partner@cumig.org',
            contact_person='Cik Partner')
        self._super('foundation@h.org')
        app = _fundable_app(self.cohort, suffix='o1', org=org)
        _add_parent_ic(app)
        _fund(app)
        self.mail.outbox = []
        self._accept(app)
        # Partner is emailed (witness pending); the Foundation is NOT yet (sequenced).
        recipients = [m.to[0] for m in self.mail.outbox]
        self.assertIn('partner@cumig.org', recipients)
        self.assertNotIn('foundation@h.org', recipients)
        self.assertTrue(any('witness' in m.subject.lower() for m in self.mail.outbox))

    def test_witness_then_foundation_then_executed_chain(self):
        org = PartnerOrganisation.objects.create(
            code='cumig', name='CUMIG', contact_email='partner@cumig.org')
        self._super('foundation@h.org')
        app = _fundable_app(self.cohort, suffix='ch', org=org)
        _add_parent_ic(app)
        _fund(app)
        ag = app.bursary_agreement if hasattr(app, 'bursary_agreement') else None
        self._accept(app)
        ag = app.bursary_agreement

        # Partner witnesses → Foundation is nudged to countersign.
        self.mail.outbox = []
        bursary.record_witness(ag, org=org, by_name='Partner Admin', witness_name='CUMIG')
        self.assertIn('foundation@h.org', [m.to[0] for m in self.mail.outbox])

        # Foundation countersigns → executes → student emailed; app 'active'.
        self.mail.outbox = []
        bursary.countersign_foundation(ag, by_name='The Foundation')
        app.refresh_from_db()
        self.assertEqual(app.status, 'active')
        student_mail = [m for m in self.mail.outbox if m.to[0] == 'student@secret.example']
        self.assertTrue(student_mail)
        self.assertTrue(any('in effect' in m.subject.lower() or 'effect' in m.subject.lower()
                            for m in student_mail))

    def test_foundation_notify_emails_prefers_env_override(self):
        from django.test import override_settings as _os
        self._super('super@h.org')
        with _os(FOUNDATION_NOTIFY_EMAIL='a@x.org, b@x.org'):
            self.assertEqual(bursary.foundation_notify_emails(), ['a@x.org', 'b@x.org'])
        # No override → falls back to active super admins.
        self.assertIn('super@h.org', bursary.foundation_notify_emails())

    def test_sign_invitation_command(self):
        from django.core.management import call_command
        app = _fundable_app(self.cohort, suffix='inv')
        _fund(app)
        self.mail.outbox = []
        with override_settings(SIGN_INVITE_APP_IDS=str(app.id)):
            call_command('send_sign_invitation_emails')
        sent = [m for m in self.mail.outbox if m.to[0] == 'student@secret.example']
        self.assertTrue(sent)
        self.assertTrue(any('sign' in m.subject.lower() for m in sent))


@override_settings(BURSARY_AGREEMENT_ENABLED=True)
class TestCockpitAgreementSurfacing(TestCase):
    """TD-144: the admin detail serializer carries the REAL agreement so the cockpit shows
    accurate four-party ticks (no optimistic default)."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.pdf, self.upload, self.dl = _mock_seams()
        self.pdf.start(); self.upload.start(); self.dl.start()
        self.addCleanup(self.pdf.stop)
        self.addCleanup(self.upload.stop)
        self.addCleanup(self.dl.stop)

    def _detail(self, app):
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        return AdminApplicationDetailSerializer(app).data

    def test_no_agreement_is_none(self):
        app = _fundable_app(self.cohort, suffix='td1')
        _fund(app)   # awarded, but not signed yet
        data = self._detail(app)
        self.assertTrue(data['bursary_agreement_enabled'])
        self.assertIsNone(data['bursary_agreement'])   # ticks render as "–", not a false ✓

    def test_signed_agreement_surfaced_with_accurate_ticks(self):
        app = _fundable_app(self.cohort, suffix='td2')
        _add_parent_ic(app)
        _fund(app)
        _verify_guarantor_phone(app)
        svc.respond_to_award(
            app, action='accept', student_signed_name='Zxq Student',
            guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
            guarantor_relationship='mother')
        data = self._detail(app)
        ag = data['bursary_agreement']
        self.assertIsNotNone(ag)
        self.assertIsNotNone(ag['student_signed_at'])     # student ✓
        self.assertIsNotNone(ag['guarantor_signed_at'])   # guarantor ✓
        self.assertIsNone(ag['foundation_signed_at'])     # Foundation – (not yet)
        self.assertIsNone(ag['witness_signed_at'])        # witness –

    @override_settings(BURSARY_AGREEMENT_ENABLED=False)
    def test_dark_flag_hides_agreement(self):
        app = _fundable_app(self.cohort, suffix='td3')
        _fund(app)
        data = self._detail(app)
        self.assertFalse(data['bursary_agreement_enabled'])
        self.assertIsNone(data['bursary_agreement'])


@override_settings(BURSARY_AGREEMENT_ENABLED=True, BURSARY_SIGN_REMINDER_DAYS=3,
                   FOUNDATION_NOTIFY_EMAIL='foundation@h.org')
class TestSigningReminders(TestCase):
    """S6 SLA cron: a pending witness/countersignature is re-nudged after the interval, and
    not before (the *_reminded_at stamps prevent daily spam)."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        from django.core import mail
        self.mail = mail
        self.pdf, self.upload, self.dl = _mock_seams()
        self.pdf.start(); self.upload.start(); self.dl.start()
        self.addCleanup(self.pdf.stop)
        self.addCleanup(self.upload.stop)
        self.addCleanup(self.dl.stop)

    def _signed(self, *, suffix, org=None):
        app = _fundable_app(self.cohort, suffix=suffix, org=org)
        _add_parent_ic(app)
        _fund(app)
        _verify_guarantor_phone(app)
        svc.respond_to_award(
            app, action='accept', student_signed_name='Zxq Student',
            guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
            guarantor_relationship='mother')
        return app

    def test_no_reminder_before_interval(self):
        self._signed(suffix='r1')   # just signed → within the interval
        self.mail.outbox = []
        out = bursary.send_signing_reminders()
        self.assertEqual(out, {'witness': 0, 'countersign': 0})
        self.assertEqual(len(self.mail.outbox), 0)

    def test_countersign_reminder_after_interval_no_org(self):
        app = self._signed(suffix='r2')   # no org → Foundation is the pending party
        ag = app.bursary_agreement
        ag.guarantor_signed_at = timezone.now() - timedelta(days=5)
        ag.save(update_fields=['guarantor_signed_at'])
        self.mail.outbox = []
        out = bursary.send_signing_reminders()
        self.assertEqual(out['countersign'], 1)
        self.assertIn('foundation@h.org', [m.to[0] for m in self.mail.outbox])
        ag.refresh_from_db()
        self.assertIsNotNone(ag.countersign_reminded_at)
        # A second run the same day does not re-send (stamp is fresh).
        self.mail.outbox = []
        self.assertEqual(bursary.send_signing_reminders()['countersign'], 0)

    def test_witness_reminder_after_interval_with_org(self):
        org = PartnerOrganisation.objects.create(
            code='cumig', name='CUMIG', contact_email='partner@cumig.org')
        app = self._signed(suffix='r3', org=org)
        ag = app.bursary_agreement
        ag.guarantor_signed_at = timezone.now() - timedelta(days=5)
        ag.save(update_fields=['guarantor_signed_at'])
        self.mail.outbox = []
        out = bursary.send_signing_reminders()
        self.assertEqual(out['witness'], 1)
        self.assertIn('partner@cumig.org', [m.to[0] for m in self.mail.outbox])
