"""Sprint S1 (TD-664 e): every write that answers with the case serves the same flags as the GET.

Twelve write replies used to answer with the bare serializer, so after a write the cockpit lost
`can_write` and the flags beside it and fell back to deriving them. Each now answers through
`_detail_payload`. Pinned two ways:
  * live — each of the twelve endpoints, called as a super with a body it accepts, answers 200 with
    every served key (`SERVED`);
  * source — no `AdminApplicationDetailSerializer(` is left in `views_admin/` outside `_detail_payload`.
Gemini and student emails are mocked; nothing here makes a paid call.
"""
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.models import Consent, Disbursement, ResolutionItem
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)

APPS = '/api/v1/admin/scholarship/applications/'
ADMIN = '/api/v1/admin/scholarship/'
SERVED = ('can_write', 'can_cancel_decline', 'can_tranche', 'can_qc', 'can_close_pre_award',
          'case_stage', 'qc_refusal')
VIEWS = Path(__file__).resolve().parents[1] / 'views_admin'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EachWriteReplyServesTheFlags(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.reviewer = make_admin('reviewer', owning_org=cls.cohort.owning_organisation)
        cls.super = make_admin(super_admin=True)

    def case(self, stage='interviewing', **kw):
        return make_application(stage, cohort=self.cohort, reviewer=self.reviewer, **kw)

    def post(self, url, body=None):
        return authed_client(self.super).post(url, body or {}, format='json')

    def assertServed(self, r):
        self.assertEqual(r.status_code, 200, r.content[:300])
        body = r.json()
        for key in SERVED:
            self.assertIn(key, body)
        self.assertIn(body['case_stage'], ('open', 'past_award', 'pre_award_end'))
        self.assertIs(body['can_qc'], True)                     # a super holds every key

    def test_patch(self):
        app = self.case()
        self.assertServed(authed_client(self.super).patch(
            f'{APPS}{app.id}/', {'mentoring_candidate': True}, format='json'))

    def test_verify_accept(self):
        app = self.case(verdict_decided_at=timezone.now())
        with patch('apps.scholarship.views_admin.applications.application_completeness',
                   return_value={'complete': True}):
            self.assertServed(self.post(f'{APPS}{app.id}/verify-accept/'))

    def test_nudge(self):
        app = self.case('shortlisted', notify_email='student@example.test',
                        nudge_sent_at=timezone.now() - timedelta(hours=25))
        Consent.objects.create(application=app, version='t', granted_by='guardian',
                               guardian_name='Parent', is_active=True)
        with patch('apps.scholarship.nudge._has_blockers', return_value=False):
            self.assertServed(self.post(f'{APPS}{app.id}/nudge/'))

    def test_schedule_a_tranche(self):
        app = self.case('maintenance')
        self.assertServed(self.post(f'{APPS}{app.id}/disbursements/', {'amount': '500'}))

    def test_a_tranche_action(self):
        app = self.case('maintenance')
        disb = Disbursement.objects.create(application=app, amount=Decimal('500'), status='scheduled',
                                           sequence=1)
        self.assertServed(self.post(f'{ADMIN}disbursements/{disb.id}/mark_due/'))

    def test_maintenance_substate(self):
        app = self.case('maintenance')
        self.assertServed(self.post(f'{APPS}{app.id}/maintenance/', {'substate': 'probation'}))

    def test_release_the_nric_lock(self):
        app = self.case('shortlisted')
        app.profile.nric_verified = True
        app.profile.save(update_fields=['nric_verified'])
        self.assertServed(self.post(f'{APPS}{app.id}/release-nric-lock/',
                                    {'reason': 'The card belongs to a sibling; freeing the number.'}))

    def test_set_the_award_amount(self):
        app = self.case()
        self.assertServed(self.post(f'{APPS}{app.id}/award-amount/', {'amount': '2500'}))

    def test_suggest_gaps(self):
        app = self.case('shortlisted')
        with patch('apps.scholarship.gap_engine.generate_interview_gaps',
                   return_value={'gaps': [{'code': 'g1', 'question': 'Q?', 'why': 'W'}]}):
            self.assertServed(self.post(f'{APPS}{app.id}/suggest-gaps/'))

    def test_request_info(self):
        app = self.case('profile_complete')
        with patch('apps.scholarship.views_admin.resolution.send_request_info_email'):
            self.assertServed(self.post(f'{APPS}{app.id}/request-info/',
                                        {'note': 'Please upload your latest payslip.'}))

    def test_add_a_resolution_item(self):
        app = self.case(profile_completed_at=timezone.now())
        self.assertServed(self.post(f'{APPS}{app.id}/resolution-items/',
                                    {'kind': 'explanation', 'prompt': 'Please explain'}))

    def test_a_resolution_item_action(self):
        app = self.case(profile_completed_at=timezone.now())
        self.assertEqual(self.post(f'{APPS}{app.id}/resolution-items/',
                                   {'kind': 'explanation', 'prompt': 'Please explain'}).status_code, 200)
        item = ResolutionItem.objects.filter(application=app).latest('pk')
        self.assertServed(self.post(f'{ADMIN}resolution-items/{item.id}/waive/'))


class NoBareSerializerReplyIsLeft(TestCase):
    def test_only_detail_payload_builds_the_case_reply(self):
        offenders = []
        for path in sorted(VIEWS.glob('*.py')):
            text = path.read_text()
            body = text
            if path.name == 'applications.py':
                # `_detail_payload` itself is the one home: cut its body out before scanning.
                body = re.sub(r'def _detail_payload\(.*?\n(?=\S)', '', text, flags=re.S)
            if 'AdminApplicationDetailSerializer(' in body:
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_the_scan_sees_the_one_home(self):
        # A control: the scan would see the serializer if `_detail_payload` were not cut out.
        self.assertIn('AdminApplicationDetailSerializer(', (VIEWS / 'applications.py').read_text())
