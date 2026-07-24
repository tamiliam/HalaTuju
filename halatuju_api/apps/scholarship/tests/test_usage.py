"""Billing & usage v1 — the meter (Sprint 13a).

Proves the three hard promises of ``apps.scholarship.usage`` + the seam wrappers:

1. UNCONDITIONAL — metering runs with the UI flag OFF (it gates only the endpoint).
2. BEST-EFFORT — a failing usage-log write can NEVER break the user-facing call
   (the fault-injection tests: a send/AI call succeeds while UsageEvent.create raises).
3. ATTRIBUTION — org/application/source thread from the call site via usage_context;
   AI token counts come from the provider response's usage metadata.

Plus the dual-shape aggregation (super sees all orgs + platform; org_admin sees only
its own org, never platform) and the live document-storage snapshot.
"""
from types import SimpleNamespace
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import emails, usage, vision, whatsapp
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort, UsageEvent,
)


def _make_app(org):
    cohort = ScholarshipCohort.objects.create(
        code=f'c-{org.code}', name=org.code, year=2026, owning_organisation=org)
    prof = StudentProfile.objects.create(
        supabase_user_id=f'u-{org.code}', nric=f'0101{org.id:02d}-14-0001', name='Stud')
    return ScholarshipApplication.objects.create(cohort=cohort, profile=prof, status='submitted')


class TestRecordUsage(TestCase):
    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='rec', name='Rec Org')
        self.app = _make_app(self.org)

    def test_record_creates_a_row_with_all_fields(self):
        usage.record_usage(usage.GEMINI, model='gemini-2.5-flash', source='doc_extract',
                           input_tokens=11, output_tokens=7,
                           organisation_id=self.org.id, application_id=self.app.id)
        ev = UsageEvent.objects.get()
        self.assertEqual(ev.service, 'gemini')
        self.assertEqual(ev.model, 'gemini-2.5-flash')
        self.assertEqual(ev.source, 'doc_extract')
        self.assertEqual(ev.quantity, 1)
        self.assertEqual((ev.input_tokens, ev.output_tokens), (11, 7))
        self.assertEqual(ev.organisation_id, self.org.id)
        self.assertEqual(ev.application_id, self.app.id)

    def test_context_supplies_org_application_and_source(self):
        with usage.usage_context(application=self.app, source='profile_draft'):
            usage.record_usage(usage.GEMINI)
        ev = UsageEvent.objects.get()
        self.assertEqual(ev.organisation_id, self.org.id)
        self.assertEqual(ev.application_id, self.app.id)
        self.assertEqual(ev.source, 'profile_draft')

    def test_nested_context_overrides_source_keeps_org_app(self):
        with usage.usage_context(application=self.app, source='doc_extract'):
            with usage.usage_context(source='ic_fallback'):   # inherits org/app
                usage.record_usage(usage.GEMINI)
        ev = UsageEvent.objects.get()
        self.assertEqual(ev.source, 'ic_fallback')
        self.assertEqual(ev.organisation_id, self.org.id)
        self.assertEqual(ev.application_id, self.app.id)

    def test_non_int_tokens_become_null(self):
        usage.record_usage(usage.GEMINI, input_tokens=mock.Mock(), output_tokens='7')
        ev = UsageEvent.objects.get()
        self.assertIsNone(ev.input_tokens)
        self.assertIsNone(ev.output_tokens)

    @override_settings(BILLING_USAGE_ENABLED=False)
    def test_meter_runs_even_when_ui_flag_is_off(self):
        usage.record_usage(usage.EMAIL, source='x')
        self.assertEqual(UsageEvent.objects.count(), 1)

    def test_record_is_best_effort_swallows_db_failure(self):
        with mock.patch('apps.scholarship.models.UsageEvent.objects.create',
                        side_effect=RuntimeError('db down')):
            usage.record_usage(usage.GEMINI, source='x')   # must NOT raise
        self.assertEqual(UsageEvent.objects.count(), 0)


class TestSeamMetering(TestCase):
    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='seam', name='Seam Org')
        self.app = _make_app(self.org)

    @override_settings(GEMINI_API_KEY='test-key')
    def test_gemini_json_seam_meters_with_tokens(self):
        resp = SimpleNamespace(
            text='{"ok": 1}',
            usage_metadata=SimpleNamespace(prompt_token_count=42, candidates_token_count=13))
        client = mock.MagicMock()
        client.models.generate_content.return_value = resp
        with mock.patch('google.genai.Client', return_value=client):
            with usage.usage_context(application=self.app, source='doc_extract'):
                out = vision._call_gemini_json('prompt', {'type': 'object'})
        self.assertEqual(out, {'ok': 1})
        ev = UsageEvent.objects.get()
        self.assertEqual(ev.service, 'gemini')
        self.assertEqual((ev.input_tokens, ev.output_tokens), (42, 13))
        self.assertEqual(ev.source, 'doc_extract')
        self.assertEqual(ev.organisation_id, self.org.id)

    def test_email_seam_meters_one_row_per_send(self):
        emails.send_acknowledgement_email('stu@example.com', 'Aisha', 'BrightPath', lang='en')
        self.assertEqual(len(mail.outbox), 1)
        ev = UsageEvent.objects.get()
        self.assertEqual(ev.service, 'email')
        self.assertEqual(ev.quantity, 1)
        self.assertEqual(ev.source, 'send_acknowledgement_email')

    @override_settings(WHATSAPP_ENABLED=True, TWILIO_ACCOUNT_SID='AC', TWILIO_AUTH_TOKEN='tok',
                       TWILIO_WHATSAPP_FROM='whatsapp:+1000')
    def test_whatsapp_seam_meters_with_org(self):
        with mock.patch('apps.scholarship.whatsapp._post_to_twilio',
                        return_value=('SID', 'sent', '')):
            whatsapp.send_whatsapp('0123456789', body='hi', application=self.app, kind='reminder')
        ev = UsageEvent.objects.get(service='whatsapp')
        self.assertEqual(ev.source, 'reminder')
        self.assertEqual(ev.organisation_id, self.org.id)
        self.assertEqual(ev.application_id, self.app.id)


class TestFaultInjection(TestCase):
    """The load-bearing guarantee: a metering failure never breaks the user-facing call."""

    def test_email_still_sends_when_metering_raises(self):
        with mock.patch('apps.scholarship.models.UsageEvent.objects.create',
                        side_effect=RuntimeError('meter exploded')):
            ok = emails.send_acknowledgement_email('stu@example.com', 'Aisha', 'BrightPath', lang='en')
        self.assertTrue(ok)                 # the send succeeded
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(UsageEvent.objects.count(), 0)

    @override_settings(GEMINI_API_KEY='test-key')
    def test_gemini_call_returns_normally_when_metering_raises(self):
        resp = SimpleNamespace(text='{"ok": 1}', usage_metadata=None)
        client = mock.MagicMock()
        client.models.generate_content.return_value = resp
        with mock.patch('google.genai.Client', return_value=client), \
             mock.patch('apps.scholarship.models.UsageEvent.objects.create',
                        side_effect=RuntimeError('meter exploded')):
            out = vision._call_gemini_json('prompt', {'type': 'object'})
        self.assertEqual(out, {'ok': 1})    # the AI read is unharmed
        self.assertEqual(UsageEvent.objects.count(), 0)


class TestAggregation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.month = timezone.now().strftime('%Y-%m')
        cls.a = PartnerOrganisation.objects.create(code='aa', name='Alpha Org')
        cls.b = PartnerOrganisation.objects.create(code='bb', name='Beta Org')
        cls.app_a = _make_app(cls.a)
        # Org A: 2 gemini calls (tokens) + 1 email
        UsageEvent.objects.create(organisation=cls.a, application=cls.app_a, service='gemini',
                                  source='doc_extract', input_tokens=100, output_tokens=40)
        UsageEvent.objects.create(organisation=cls.a, service='gemini', source='profile_draft',
                                  input_tokens=50, output_tokens=20)
        UsageEvent.objects.create(organisation=cls.a, service='email', source='send_ack')
        # Org B: 1 whatsapp
        UsageEvent.objects.create(organisation=cls.b, service='whatsapp', source='reminder')
        # Platform (NULL org): 1 report
        UsageEvent.objects.create(organisation=None, service='gemini', source='report',
                                  input_tokens=200, output_tokens=80)
        # A document to prove the storage snapshot
        ApplicantDocument.objects.create(application=cls.app_a, doc_type='ic',
                                         storage_path=f'{cls.app_a.id}/ic/x', size=1024)

    def test_super_view_has_all_orgs_plus_platform(self):
        payload = usage.monthly_usage(self.month, include_platform=True)
        self.assertTrue(payload['can_see_platform'])
        by_id = {o['organisation_id']: o for o in payload['organisations']}
        self.assertIn(None, by_id)                       # platform block present
        self.assertTrue(by_id[None]['is_platform'])
        self.assertIn(self.a.id, by_id)
        self.assertIn(self.b.id, by_id)
        # Org A gemini row aggregates both calls
        a_gemini = next(s for s in by_id[self.a.id]['services'] if s['service'] == 'gemini')
        self.assertEqual(a_gemini['events'], 2)
        self.assertEqual(a_gemini['input_tokens'], 150)
        self.assertEqual(a_gemini['output_tokens'], 60)
        self.assertEqual(by_id[self.a.id]['storage_bytes'], 1024)

    def test_org_admin_view_is_fenced_no_platform_no_other_org(self):
        payload = usage.monthly_usage(self.month, restrict_org_id=self.a.id)
        self.assertFalse(payload['can_see_platform'])
        self.assertEqual(len(payload['organisations']), 1)
        block = payload['organisations'][0]
        self.assertEqual(block['organisation_id'], self.a.id)
        self.assertFalse(block['is_platform'])
        # No platform, no Beta anywhere in the payload.
        ids = {o['organisation_id'] for o in payload['organisations']}
        self.assertNotIn(None, ids)
        self.assertNotIn(self.b.id, ids)

    def test_org_admin_with_zero_usage_still_renders_own_block(self):
        empty = PartnerOrganisation.objects.create(code='zz', name='Zed Org')
        payload = usage.monthly_usage(self.month, restrict_org_id=empty.id)
        self.assertEqual(len(payload['organisations']), 1)
        self.assertEqual(payload['organisations'][0]['organisation_id'], empty.id)
        self.assertEqual(payload['organisations'][0]['totals']['events'], 0)

    def test_available_months_lists_the_month(self):
        self.assertIn(self.month, usage.available_months())

    def test_payload_and_block_key_shape(self):
        payload = usage.monthly_usage(self.month, include_platform=True)
        self.assertEqual(set(payload), {'month', 'months', 'can_see_platform', 'organisations'})
        block = payload['organisations'][0]
        self.assertEqual(set(block), {'organisation_id', 'organisation', 'is_platform',
                                      'services', 'totals', 'storage_bytes'})
        self.assertEqual(set(block['services'][0]),
                         {'service', 'events', 'quantity', 'input_tokens', 'output_tokens'})
        self.assertEqual(set(block['totals']),
                         {'events', 'quantity', 'input_tokens', 'output_tokens'})
