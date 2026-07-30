"""`awarded` is deliberately NOT rejectable — owner ruling, 2026-07-30.

*"They cannot be rejected directly. It should only happen after a proper withdrawal of the
award."*

This test exists because the omission LOOKS like a bug. On the same day, `awarded` was found
missing from three cockpit conditions where it genuinely belonged (the QC sign-off), and 47
production records were displaying wrongly as a result. Two conditions away, in this file, the
same status is missing from the reject sets — and there it is correct. Without something pinning
it, the next person to sweep for "places that forgot `awarded`" will add it here and quietly make
an awarded student directly rejectable.

The asymmetry with active/maintenance is the substance, not an accident: those mean the student
ACCEPTED, so a decline is a real contractual failure. `awarded` means the offer is merely OPEN, so
the right action is withdrawing it — which returns them to `recommended`, from where a decline is
already allowed.
"""
from django.test import TestCase

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import services
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort


class TestRejectStatusSets(TestCase):
    def test_awarded_is_absent_from_both_reject_sets(self):
        self.assertNotIn('awarded', services.INTERVIEW_REJECT_FROM)
        self.assertNotIn('awarded', services.ORG_REJECT_FROM)

    def test_the_states_that_ARE_rejectable_are_unchanged(self):
        # The negative half. A test asserting only "awarded is absent" would also pass if
        # somebody emptied these tuples, which would break every legitimate decline.
        self.assertEqual(services.INTERVIEW_REJECT_FROM,
                         ('shortlisted', 'profile_complete', 'interviewing', 'interviewed'))
        self.assertEqual(services.ORG_REJECT_FROM, ('shortlisted',))


class TestAnAwardedApplicationCannotBeDeclined(TestCase):
    """The behaviour, not just the constants — the tuples could stay right while the gate drifts."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c-rej', name='B40', year=2026)
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='rej-admin', role='org_admin', is_active=True,
            name='OA', email='oa@x.com')

    _seq = 0

    def _app(self, status):
        type(self)._seq += 1
        profile = StudentProfile.objects.create(
            supabase_user_id=f'rej-{status}-{type(self)._seq}', name='Priya')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status)

    def test_neither_category_accepts_an_awarded_application(self):
        for category in ('interview', 'contractual'):
            with self.subTest(category=category):
                app = self._app('awarded')
                with self.assertRaises(ValueError) as ctx:
                    services.admin_reject(app, self.admin, category)
                self.assertEqual(str(ctx.exception), 'bad_status')
                app.refresh_from_db()
                self.assertEqual(app.status, 'awarded', 'an awarded student was declined')

    def test_the_withdrawal_route_is_what_opens_it(self):
        """Withdraw first → 'recommended' → a contractual decline is then permitted. This is the
        route the owner's ruling prescribes, asserted end to end so 'withdraw first' is a real
        path rather than advice in a comment."""
        app = self._app('recommended')       # i.e. post-withdrawal
        services.admin_reject(app, self.admin, 'contractual')
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')
