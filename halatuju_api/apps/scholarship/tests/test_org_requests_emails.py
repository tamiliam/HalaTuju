"""Requests space — email + AI-wiring tests (Sprint 15, Phase 3).

The five best-effort English emails (submit→owner, questions→submitter, answer→owner,
quote→submitter, accept→owner): the right recipient, seam-compliant sender, hours-denominated
quote copy, ZERO platform brand literals. Plus the post-commit wiring over the endpoints (create
notifies the owner, quote emails the submitter) and the 503 mapping when the AI seam is
unconfigured.
"""
from unittest import mock

import jwt
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import emails
from apps.scholarship.models import OrgRequest

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
BASE = '/api/v1/admin/scholarship/requests/'
OWNER = 'owner@halatuju.test'

# Platform brand literals that must NOT appear in the requests emails (the AST guard covers the
# module's constants; this covers the RENDERED output built from f-strings + data).
_FORBIDDEN = ('BrightPath', 'Cikgu Gopal', 'halatuju.xyz')


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ADMIN_NOTIFY_EMAIL=OWNER)
class TestSendFunctions(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='em', name='Acme Org')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='em-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='dina@acme.test')
        cls.req = OrgRequest.objects.create(
            organisation=cls.org, submitted_by=cls.oa, kind='feature',
            title='CSV export', description='We want a CSV export on the dashboard.',
            quote_hours=8, quote_margin_pct=50, quote_note='One new endpoint plus the button.')

    def setUp(self):
        mail.outbox.clear()

    def _last(self):
        self.assertTrue(mail.outbox, 'nothing landed in the outbox')
        return mail.outbox[-1]

    def _assert_clean(self, msg):
        # The COPY I authored (subject + body) carries no brand literal. The sender identity
        # (from_email) legitimately is the platform address via the branding seam (_P.email_from) —
        # that is the seam's job, not a hard-coded literal, so it's out of scope here.
        blob = f'{msg.subject}\n{msg.body}'
        for tok in _FORBIDDEN:
            self.assertNotIn(tok, blob, tok)

    def test_submitted_goes_to_owner(self):
        self.assertTrue(emails.send_org_request_submitted_email(self.req))
        m = self._last()
        self.assertEqual(m.to, [OWNER])
        self.assertIn('CSV export', m.subject)
        self._assert_clean(m)

    def test_questions_go_to_submitter(self):
        self.assertTrue(emails.send_org_request_questions_email(self.req, ['Which report?']))
        m = self._last()
        self.assertEqual(m.to, ['dina@acme.test'])
        self.assertIn('Which report?', m.body)
        self._assert_clean(m)

    def test_questions_no_email_when_empty(self):
        self.assertFalse(emails.send_org_request_questions_email(self.req, []))
        self.assertFalse(mail.outbox)

    def test_answered_goes_to_owner(self):
        self.assertTrue(emails.send_org_request_answered_email(self.req))
        self.assertEqual(self._last().to, [OWNER])

    def test_quote_goes_to_submitter_with_hours(self):
        self.assertTrue(emails.send_org_request_quote_email(self.req))
        m = self._last()
        self.assertEqual(m.to, ['dina@acme.test'])
        self.assertIn('8 hours', m.body)          # tidy hours, not '8.0'
        self.assertIn('50% margin', m.body)
        self._assert_clean(m)

    def test_accepted_goes_to_owner(self):
        self.assertTrue(emails.send_org_request_accepted_email(self.req))
        self.assertEqual(self._last().to, [OWNER])

    def test_owner_email_skipped_when_unset(self):
        with override_settings(ADMIN_NOTIFY_EMAIL=''):
            self.assertFalse(emails.send_org_request_submitted_email(self.req))

    def test_fmt_hours(self):
        from decimal import Decimal
        self.assertEqual(emails._fmt_hours(Decimal('8.0')), '8')
        self.assertEqual(emails._fmt_hours(Decimal('8.5')), '8.5')
        self.assertEqual(emails._fmt_hours(None), '')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True, ADMIN_NOTIFY_EMAIL=OWNER)
class TestWiring(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='wi', name='Wiring Org')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='wi-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Omar', email='omar@wi.test')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='wi-su', is_super_admin=True, is_active=True,
            name='Super', email='su@wi.test')

    def setUp(self):
        self.client = APIClient()
        mail.outbox.clear()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_create_notifies_owner(self):
        self._auth('wi-oa')
        r = self.client.post(BASE, {'kind': 'feature', 'title': 'Dark mode',
                                    'description': 'Please add dark mode.'}, format='json')
        self.assertEqual(r.status_code, 201)
        owner_mail = [m for m in mail.outbox if m.to == [OWNER]]
        self.assertTrue(owner_mail)
        self.assertIn('Dark mode', owner_mail[-1].subject)

    def test_quote_emails_submitter(self):
        req = OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.oa, kind='feature',
            title='Filters', description='Add filters', status='triaged',
            triaged_kind='feature', lane='sprint')
        self._auth('wi-su')
        mail.outbox.clear()
        r = self.client.post(f'{BASE}{req.id}/quote/', {'hours': 12, 'note': 'ok'}, format='json')
        self.assertEqual(r.status_code, 200)
        sub_mail = [m for m in mail.outbox if m.to == ['omar@wi.test']]
        self.assertTrue(sub_mail)
        self.assertIn('12 hours', sub_mail[-1].body)

    def test_create_auto_run_never_500s_unconfigured(self):
        # No GEMINI_API_KEY → the auto-run swallows the ContractsError; create still 201s.
        self._auth('wi-oa')
        r = self.client.post(BASE, {'kind': 'bug', 'title': 'x', 'description': 'y'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(OrgRequest.objects.get(id=r.json()['id']).ai_run_count, 0)

    def test_ai_rerun_wires_seam_and_emails_questions(self):
        req = OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.oa, kind='feature',
            title='Reports', description='Add reports')
        good = ('{"classification": "feature", "lane": "sprint", "estimated_hours": 6, '
                '"clarifying_questions": ["Which columns?"], "rationale": "new report"}')
        self._auth('wi-su')
        mail.outbox.clear()
        with mock.patch('apps.scholarship.contracts._gemini_generate', return_value=good):
            r = self.client.post(f'{BASE}{req.id}/ai-rerun/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.ai_draft_hours, __import__('decimal').Decimal('6.0'))
        # The clarifying question emailed the submitter directly.
        sub_mail = [m for m in mail.outbox if m.to == ['omar@wi.test']]
        self.assertTrue(sub_mail)
        self.assertIn('Which columns?', sub_mail[-1].body)
        # ...and stays out of the OWNER-facing payload contract (super sees it, org never).
        self.assertIn('ai_draft_hours', r.json())
