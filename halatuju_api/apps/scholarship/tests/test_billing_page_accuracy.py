"""Usage & Billing, read by the organisation it describes (2026-09-15).

The owner put the organisation's page beside Supabase's own usage page and found two things wrong:

* **Storage read 1.1 GB; Supabase read 1.347 GB.** We summed the sizes on our own document rows —
  which miss files whose row was replaced but whose object is still stored and billed — and divided
  by 1024³ while printing "GB". Now the figure comes from `storage.objects`, Supabase's own file
  table, and the screen prints decimal units.
* **The shared services were invisible.** Google Workspace (mailboxes, Drive, Meet) is a standing
  paid cost and was not named anywhere; Cloudflare and GitHub sat in a footnote.
"""
from unittest import mock

from django.test import TestCase

from apps.courses.models import PartnerOrganisation
from apps.scholarship import platform_cost, usage
from apps.scholarship.models import (
    ApplicantDocument, PlatformCost, ScholarshipApplication, ScholarshipCohort,
)
from apps.courses.models import StudentProfile


class TestEveryLedgerSourceIsADecision(TestCase):
    """A supplier added to the cost ledger must be shown to tenants or excluded WITH A REASON."""

    def test_every_source_is_listed_or_excluded_and_never_both(self):
        sources = {k for k, _ in PlatformCost.SOURCE_CHOICES}
        listed = {s['key'] for s in platform_cost.PLATFORM_SERVICES}
        excluded = set(platform_cost.NOT_A_PLATFORM_SERVICE)
        self.assertEqual(sources - listed - excluded, set(),
                         'A ledger source nobody decided about: list it in PLATFORM_SERVICES or '
                         'give a reason in NOT_A_PLATFORM_SERVICE.')
        self.assertEqual(listed & excluded, set())
        self.assertEqual((listed | excluded) - sources, set(), 'A decision about a source that is gone.')
        for reason in platform_cost.NOT_A_PLATFORM_SERVICE.values():
            self.assertGreater(len(reason.strip()), 20)

    def test_the_services_the_owner_named_are_on_the_page(self):
        by_key = {s['key']: s['plan'] for s in platform_cost.PLATFORM_SERVICES}
        self.assertEqual(by_key['workspace'], 'paid')
        self.assertEqual(by_key['cloudflare'], 'free')
        self.assertEqual(by_key['github'], 'free')
        self.assertTrue(set(by_key.values()) <= {'paid', 'free'})

    def test_the_tenant_list_carries_names_and_plans_and_nothing_that_costs(self):
        payload = usage.monthly_usage('2026-09', restrict_org_id=None)
        for service in payload['platform_services']:
            self.assertEqual(set(service), {'key', 'plan'})
        # A copy: mutating the payload must never reach the module constant.
        payload['platform_services'][0]['plan'] = 'tampered'
        self.assertNotEqual(platform_cost.PLATFORM_SERVICES[0]['plan'], 'tampered')


class TestStorageIsMeasuredFromSupabasesFiles(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='acc-org', name='Acc Org')
        cohort = ScholarshipCohort.objects.create(code='acc-c', name='c', year=2026,
                                                  owning_organisation=cls.org)
        prof = StudentProfile.objects.create(supabase_user_id='acc-s', nric='010101-14-0009', name='S')
        app = ScholarshipApplication.objects.create(cohort=cohort, profile=prof)
        ApplicantDocument.objects.create(application=app, doc_type='ic',
                                         storage_path=f'{app.id}/ic/x', size=1000)

    def test_without_the_storage_table_it_falls_back_to_our_records(self):
        """SQLite has no `storage` schema; the fallback is the recorded size."""
        self.assertEqual(usage.org_storage_bytes(self.org.id), 1000)
        self.assertEqual(usage.bucket_storage_bytes(), 1000)

    def _postgres(self, value=None, boom=False):
        cursor = mock.MagicMock()
        if boom:
            cursor.execute.side_effect = RuntimeError('permission denied for schema storage')
        cursor.fetchone.return_value = (value,)
        conn = mock.MagicMock(vendor='postgresql')
        conn.cursor.return_value.__enter__.return_value = cursor
        return conn, cursor

    def test_on_postgres_the_organisation_figure_is_the_stored_files_and_names_the_org_twice(self):
        conn, cursor = self._postgres(1_218_528_263)
        with mock.patch('django.db.connection', conn):
            self.assertEqual(usage.org_storage_bytes(self.org.id), 1_218_528_263)
        sql, params = cursor.execute.call_args[0]
        self.assertIn('storage.objects', sql)
        # Documents by application id, request files by the organisation id in the path.
        self.assertEqual(params, ['b40-documents', self.org.id, str(self.org.id)])

    def test_on_postgres_the_platform_figure_is_every_file_in_every_bucket(self):
        conn, cursor = self._postgres(1_351_877_763)
        with mock.patch('django.db.connection', conn):
            self.assertEqual(usage.bucket_storage_bytes(), 1_351_877_763)
        sql = cursor.execute.call_args[0][0]
        self.assertIn('storage.objects', sql)
        self.assertNotIn('bucket_id', sql)   # all buckets, as Supabase counts

    def test_a_storage_read_that_fails_logs_and_falls_back_rather_than_breaking_the_page(self):
        conn, _ = self._postgres(boom=True)
        with mock.patch('django.db.connection', conn), \
                self.assertLogs('apps.scholarship.usage', level='WARNING'):
            self.assertEqual(usage.org_storage_bytes(self.org.id), 1000)

    def test_an_empty_bucket_is_a_real_zero_not_a_fallback(self):
        conn, _ = self._postgres(0)
        with mock.patch('django.db.connection', conn):
            self.assertEqual(usage.org_storage_bytes(self.org.id), 0)
