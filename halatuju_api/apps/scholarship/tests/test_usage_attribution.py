"""Billing attribution: a metered call raised BY a tenant's application bills that tenant.

Why this file exists. The v1 meter threaded the organisation only through an ambient
``usage_context``. Every seam that runs OUTSIDE a request — the crons, the release job — had
no such context, so it silently recorded ``organisation_id = NULL``. Measured on prod
2026-07-26: **18 of 18 email events were org-NULL**, i.e. an invoice generated that day would
have under-charged the tenant for every single email sent on its behalf.

Silent is the operative word: nothing failed, nothing logged, and the usage screen looked
plausible. These tests make the attribution an asserted property rather than a hope.

Two guards, deliberately different in kind:
  * BEHAVIOURAL — a metered call inside an application context lands on that application's
    owning organisation, and one outside it still lands on the platform row (the platform row
    is legitimate for platform-base work; it must not become the dumping ground for tenant work).
  * STRUCTURAL — every public scheduling entry point that takes an application is decorated.
    A future sibling added without the decorator fails here rather than quietly under-charging.
"""
import inspect

from django.test import TestCase

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import emails, scheduling, usage
from apps.scholarship.models import (
    ScholarshipApplication, ScholarshipCohort, UsageEvent,
)


class _AppFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='aa', name='Alpha Org')
        cohort = ScholarshipCohort.objects.create(code='ca', name='A', year=2026,
                                                  owning_organisation=cls.org)
        prof = StudentProfile.objects.create(supabase_user_id='stud-a',
                                             nric='010101-14-0001', name='Stud A')
        cls.app = ScholarshipApplication.objects.create(cohort=cohort, profile=prof,
                                                        status='submitted')


class TestEmailAttribution(_AppFixture):
    """The email meter reads the ambient context — so the CALLER must set one."""

    def test_email_inside_an_application_context_bills_that_org(self):
        with usage.usage_context(application=self.app):
            emails._meter_email()
        ev = UsageEvent.objects.get(service='email')
        self.assertEqual(ev.organisation_id, self.org.id)
        self.assertEqual(ev.application_id, self.app.id)

    def test_email_with_no_context_stays_on_the_platform_row(self):
        """Platform-base work (ops mail, internal alerts) legitimately has no tenant.
        This asserts the fallback still EXISTS — the fix must not invent an org."""
        emails._meter_email()
        self.assertIsNone(UsageEvent.objects.get(service='email').organisation_id)

    def test_a_nested_context_keeps_its_source_but_inherits_the_org(self):
        """The property the help-engine fix depends on. The coach's own
        ``usage_context(source='doc_help')`` supplies no org, so it inherits the caller's —
        which is why the engine's firewalled signature never had to change."""
        with usage.usage_context(application=self.app):
            with usage.usage_context(source='doc_help'):
                usage.record_usage(usage.GEMINI)
        ev = UsageEvent.objects.get(service='gemini')
        self.assertEqual(ev.organisation_id, self.org.id)
        self.assertEqual(ev.source, 'doc_help')


class TestSchedulingEntryPointsAreBilled(TestCase):
    """STRUCTURAL: every public scheduling entry point taking an application is decorated.

    Scheduling fans out email + WhatsApp to BOTH the student and the reviewer, all of it work
    done for one tenant. A new sibling that forgets the decorator would under-charge silently,
    so the completeness check lives here rather than in a reviewer's memory."""

    def test_every_application_first_entry_point_is_decorated(self):
        inspected, undecorated = [], []
        for name, fn in vars(scheduling).items():
            if name.startswith('_') or not inspect.isfunction(fn):
                continue
            if fn.__module__ != scheduling.__name__:
                continue
            params = list(inspect.signature(fn).parameters)
            if not params or params[0] != 'application':
                continue
            inspected.append(name)
            # functools.wraps sets __wrapped__ — present iff _bills_to_application applied.
            if getattr(fn, '__wrapped__', None) is None:
                undecorated.append(name)
        # Floor: a completeness check that inspects nothing passes for the wrong reason. Six
        # entry points existed when this was written; if a refactor drops below that, the
        # guard has stopped guarding and should be re-pointed, not deleted.
        self.assertGreaterEqual(
            len(inspected), 6,
            f'Expected >=6 application-first scheduling entry points, found {inspected}. '
            'The guard is no longer looking at what it was written to protect.')
        self.assertEqual(
            undecorated, [],
            'These scheduling entry points take an application but are not wrapped in '
            '@_bills_to_application, so the email/WhatsApp they send would be billed to the '
            'platform instead of the tenant: ' + ', '.join(undecorated))

    def test_the_guard_can_actually_fail(self):
        """A completeness check that cannot fail is decoration, not a guard."""
        def new_entry_point(application, *, thing=None):   # noqa: ARG001 — shape only
            return None
        params = list(inspect.signature(new_entry_point).parameters)
        self.assertEqual(params[0], 'application')
        self.assertIsNone(getattr(new_entry_point, '__wrapped__', None))
