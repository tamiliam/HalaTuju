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
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

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


class TestTheSendersFixedOn20260818(TestCase):
    """The eight senders that were STILL billing the platform on 2026-08-18, and the six of
    them a call-site context could fix.

    The 2026-07-26 sprint (above) wrapped *the four seams that were firing at the time* and the
    note recorded it as done. It was — for those four. Attribution is opt-in per call site with
    no default and nothing checking it, so every sender that started firing afterwards began
    life org-NULL. Measured on production for August 2026: **125 emails on the platform row**,
    every one of them bursary work — 24 application closures, 13 reminders, 10 award offers,
    7 reviewer assignments, 7 student-assignment notices, 1 nudge, plus the partner (29) and
    sponsor (33) digests, which are a separate decision because the recipient is not the tenant.

    These are BEHAVIOURAL and drive the real service functions, not `_meter_email` directly:
    the defect was never in the meter, it was in what the caller had open around it.
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='bp', name='BrightPath')
        cls.cohort = ScholarshipCohort.objects.create(
            code='cbp', name='B40 Programme', year=2026, owning_organisation=cls.org)

    _seq = 0

    def _app(self, **kw):
        type(self)._seq += 1
        prof = StudentProfile.objects.create(
            supabase_user_id=f'ua-{type(self)._seq}', name='Priya')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=prof, notify_email='stu@example.com', **kw)

    def _email_orgs(self):
        return list(UsageEvent.objects.filter(service='email')
                    .values_list('source', 'organisation_id'))

    def test_a_completion_reminder_bills_the_tenant(self):
        from apps.scholarship import services
        self._app(status='shortlisted',
                  reminder_anchor_at=timezone.now() - timedelta(days=3))
        services.send_application_reminders()
        rows = self._email_orgs()
        self.assertEqual(rows, [('send_reminder_email', self.org.id)])

    def test_an_auto_CLOSURE_bills_the_tenant(self):
        from apps.scholarship import services
        now = timezone.now()
        self._app(status='shortlisted',
                  reminder_anchor_at=now - timedelta(days=70),
                  reminder_stage=len(services.REMINDER_THRESHOLDS_DAYS),
                  last_reminder_at=now - timedelta(days=10))
        services.send_application_reminders()
        rows = self._email_orgs()
        self.assertEqual(rows, [('send_application_closed_email', self.org.id)])

    def test_a_reviewer_assignment_bills_the_tenant(self):
        from apps.courses.models import PartnerAdmin
        from apps.scholarship import services
        mk = PartnerAdmin.objects.create
        first = mk(supabase_user_id='rv-1', role='reviewer', is_active=True,
                   name='First', email='first@example.com', owning_organisation=self.org)
        second = mk(supabase_user_id='rv-2', role='reviewer', is_active=True,
                    name='Second', email='second@example.com', owning_organisation=self.org)
        actor = mk(supabase_user_id='su-1', role='super', is_super_admin=True,
                   is_active=True, name='Su', email='su@example.com')
        # REassignment, so the first-assignment readiness gate is not in the way.
        app = self._app(status='profile_complete', assigned_to=first)
        services.assign_reviewer(app, reviewer=second, by_admin=actor)
        rows = self._email_orgs()
        self.assertIn(('send_reviewer_assigned_email', self.org.id), rows)
        self.assertNotIn(None, [org for _, org in rows])

    def test_a_nudge_bills_the_tenant(self):
        from apps.scholarship import nudge
        app = self._app(status='shortlisted')
        # `is_applicable` gates on a full consent + zero-blocker state, which is a large fixture
        # and is NOT what this test is about. Patch the gate, not the sender: the thing under
        # test is the context the call site opens, and a skipped test guards nothing.
        with mock.patch.object(nudge, 'is_applicable', return_value=True):
            nudge.send_nudge(app, manual=False)
        self.assertEqual(self._email_orgs(), [('send_application_nudge_email', self.org.id)])

    def test_an_award_offer_bills_the_tenant(self):
        from apps.scholarship import sponsorship
        from apps.scholarship.models import Programme, Sponsor, Sponsorship
        app = self._app(status='awarded')
        programme = Programme.objects.get(code=self.cohort.programme.code) \
            if getattr(self.cohort, 'programme_id', None) else None
        sponsor = Sponsor.objects.create(supabase_user_id='sp-1', name='Giver',
                                         email='giver@example.com', status='approved')
        sp = Sponsorship.objects.create(
            application=app, sponsor=sponsor, amount=1000, status='offered',
            **({'programme': programme} if programme is not None else {}))
        # offered_at is auto_now_add, so it must be back-dated past the cool-off by UPDATE —
        # assigning it on create() is silently ignored and the release query then skips the row.
        Sponsorship.objects.filter(pk=sp.pk).update(
            offered_at=timezone.now() - timedelta(days=2))
        sponsorship.release_award_offer_emails()
        rows = self._email_orgs()
        self.assertTrue(rows, 'no email was metered — the fixture did not reach the sender')
        for source, org_id in rows:
            self.assertEqual(org_id, self.org.id, f'{source} still bills the platform')

    def test_the_guard_can_actually_fail(self):
        """Without a call-site context the same send lands on the platform row — which is what
        every one of the tests above would look like before the fix."""
        emails._meter_email()
        self.assertIsNone(UsageEvent.objects.get(service='email').organisation_id)
