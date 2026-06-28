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
        sp = svc.respond_to_award(
            app, action='accept', student_signed_name='Zxq Student',
            guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
            guarantor_relationship='mother')
        self.assertEqual(sp.status, 'active')
        app.refresh_from_db()
        self.assertEqual(app.status, 'sponsored')
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
        self.assertEqual(app.status, 'recommended')   # rolled back, NOT sponsored
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
        self.assertEqual(app.status, 'sponsored')
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

    def test_missing_witness_does_not_block_sponsored(self):
        # No witness recorded — the application still reached 'sponsored' on acceptance.
        app = self._signed_app(suffix='nowit')
        app.refresh_from_db()
        self.assertEqual(app.status, 'sponsored')
        self.assertIsNone(app.bursary_agreement.witness_signed_at)
