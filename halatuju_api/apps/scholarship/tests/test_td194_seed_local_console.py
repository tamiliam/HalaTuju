"""TD-194 (2026-10-05): the officer console can be reviewed on a developer's machine.

`seed_local_console` makes a super admin and one made-up application per main stage on the local
SQLite database, through the test factory. Pinned: it runs clean, it is safe to run twice, the
seeded admin really can open the console's first call and a list, and it REFUSES any database
that is not SQLite before writing a row.
"""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.management.commands import seed_local_console as cmd
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client


def seed(*args):
    out = StringIO()
    call_command('seed_local_console', *args, stdout=out)
    return out.getvalue()


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSeedLocalConsole(TestCase):
    def test_it_runs_clean_and_builds_one_application_per_stage(self):
        out = seed('--email', 'Me@Example.com', '--uid', 'td194-uid')
        self.assertIn('Seeded', out)
        org = PartnerOrganisation.objects.get(code=cmd.ORG_CODE)
        apps_ = ScholarshipApplication.objects.filter(owning_organisation=org)
        self.assertEqual(apps_.count(), len(cmd.DEMO_STAGES))
        self.assertEqual(set(apps_.values_list('programme__code', flat=True)), {cmd.GIFT_CODE})
        admin = PartnerAdmin.objects.get(email='me@example.com')
        self.assertTrue(admin.is_super and admin.is_active)
        self.assertEqual(admin.owning_organisation, org)

    def test_running_it_twice_makes_nothing_twice(self):
        seed('--email', 'me@example.com')
        out = seed('--email', 'me@example.com')
        self.assertIn('Already seeded', out)
        self.assertEqual(PartnerOrganisation.objects.filter(code=cmd.ORG_CODE).count(), 1)
        self.assertEqual(PartnerAdmin.objects.filter(email='me@example.com').count(), 1)
        self.assertEqual(ScholarshipApplication.objects.count(), len(cmd.DEMO_STAGES))

    def test_without_a_uid_it_waits_for_the_first_sign_in_to_link(self):
        seed('--email', 'me@example.com')
        self.assertIsNone(PartnerAdmin.objects.get(email='me@example.com').supabase_user_id)

    def test_the_seeded_admin_can_open_the_console(self):
        seed('--email', 'me@example.com', '--uid', 'td194-uid')
        client = authed_client('td194-uid')
        self.assertEqual(client.get('/api/v1/admin/role/').status_code, 200)
        r = client.get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(r.status_code, 200, r.content[:200])

    def test_it_refuses_a_database_that_is_not_sqlite(self):
        with mock.patch.object(cmd, 'connection') as conn:
            conn.vendor = 'postgresql'
            with self.assertRaises(CommandError):
                seed('--email', 'me@example.com')
        self.assertFalse(PartnerOrganisation.objects.filter(code=cmd.ORG_CODE).exists())
        self.assertFalse(PartnerAdmin.objects.filter(email='me@example.com').exists())
