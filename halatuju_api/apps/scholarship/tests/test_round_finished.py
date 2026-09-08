"""Closing an intake round FOR GOOD — the end of the grace period (owner, 2026-09-08).

⚠⚠ THE ONE THING EVERY TEST HERE EXISTS TO PROTECT: **CLOSED AND FINISHED ARE DIFFERENT THINGS.**

`is_open=False` stops NEW applications and nothing else. A student who had already started keeps
their right to submit, because the intake gate lives on the CREATE endpoint and a returning
applicant never reaches it again. That is stated at `views.ApplicationCreateView` and it is not an
oversight — it is how the 2026 intake actually ran. The switch went off on 1 July, the landing page
greyed out, and **thirty students who were already part-way through submitted between then and the
7th**. Nobody designed that grace period into a screen; it fell out of where the gate sits, and for
two months nothing said it existed. Reconstructing it needed a database query, because there was no
record of the close at all.

`finished_at` is where that grace period ENDS. It is **TERMINAL** (owner: *"when an application is
finished, can it be opened again? I don't think it should be"*) — nothing in the product clears it,
which is why finishing asks for the round's code to be typed.

`test_a_CLOSED_round_still_lets_a_started_student_submit` is the one that would fail if somebody
"tidied" the two states into one, and it would take those thirty students with it.
"""
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import Programme, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import RoundFinishedError, confirm_profile
from apps.scholarship.tests.test_api import TEST_JWT_SECRET, _make_token
from apps.scholarship.views_admin import round_state


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestFinishingARound(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(
            code='fin-org', name='Fin Org', is_active=True)
        cls.prog = Programme.objects.create(
            organisation=cls.org, code='fin-gift', name_en='Fin Gift', is_active=True)
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='fin-admin', email='fin-admin@example.com', name='Fin Admin',
            role='org_admin', is_super_admin=False, is_active=True, owning_organisation=cls.org)
        # A SECOND tenant, for the fence.
        cls.other_org = PartnerOrganisation.objects.create(
            code='fin-other', name='Other Org', is_active=True)
        cls.other_prog = Programme.objects.create(
            organisation=cls.other_org, code='fin-other-gift', name_en='Other', is_active=True)

    def setUp(self):
        self.client = APIClient()

    def _auth(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {_make_token(self.admin.supabase_user_id)}')

    def _year(self, **kw):
        defaults = dict(programme=self.prog, owning_organisation=self.org, code='fin-y',
                        name='Fin Y', year=2027, is_active=True, is_open=False)
        defaults.update(kw)
        return ScholarshipCohort.objects.create(**defaults)

    def _application(self, cohort, *, submitted, nric='900101010101'):
        """⚠ SUBMITTED IS A STATUS, NOT A TIMESTAMP. `submitted_at` is `auto_now_add`, so it is
        stamped when the row is CREATED and is never null — the first cut of this helper set it to
        None and the count it fed read zero for everybody. `shortlisted` means started-not-yet-
        submitted; `profile_complete` is what `confirm_profile` leaves behind."""
        profile = StudentProfile.objects.create(
            supabase_user_id=f'stu-{nric}', name='Test Student', nric=nric)
        return ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile,
            status='profile_complete' if submitted else 'shortlisted')

    def _finish(self, cohort, confirm=None):
        self._auth()
        body = {'confirm': cohort.code if confirm is None else confirm}
        return self.client.post(
            f'/api/v1/admin/scholarship/intake-years/{cohort.id}/finish/', body, format='json')

    # ── the four states ──────────────────────────────────────────────────────────────────────

    def test_round_state_reads_draft_open_closed_finished(self):
        y = self._year()
        # Never opened, nobody applied — a round on its first day, not one that has run and stopped.
        self.assertEqual(round_state(y), 'draft')

        y.is_open = True
        y.save(update_fields=['is_open'])
        self.assertEqual(round_state(y), 'open')

        y.is_open = False
        y.save(update_fields=['is_open'])
        self._application(y, submitted=True)
        self.assertEqual(round_state(y), 'closed')

        y.finished_at = timezone.now()
        y.save(update_fields=['finished_at'])
        self.assertEqual(round_state(y), 'finished')

    def test_finished_outranks_open(self):
        """A finished round can never read `open`, whatever the switch says — the endpoint refuses
        to reopen one, so a row in that shape is a database correction, and it must still render
        the terminal state rather than inviting applicants."""
        y = self._year(is_open=True, finished_at=timezone.now())
        self.assertEqual(round_state(y), 'finished')

    def test_the_row_serves_the_state_and_the_unsubmitted_count(self):
        """⚠ SERVED, NOT DERIVED. The badge and the "close for good" dialog both read these; a
        browser copy of the rule would eventually disagree with the control beside it."""
        y = self._year()
        self._application(y, submitted=True, nric='900101010102')
        self._application(y, submitted=False, nric='900101010103')
        self._auth()
        r = self.client.get(f'/api/v1/admin/scholarship/programmes/{self.prog.id}/years/')
        row = r.json()['years'][0]
        self.assertEqual(row['state'], 'closed')
        self.assertEqual(row['applications'], 2)
        # The people finishing would shut out — the one fact the dialog's reader cannot see.
        self.assertEqual(row['unsubmitted'], 1)
        self.assertIsNone(row['finished_at'])

    # ── finishing ────────────────────────────────────────────────────────────────────────────

    def test_finishing_records_when_and_who(self):
        """The gap this whole feature came from: opening and closing a round left NO record, so two
        months later "when did this close?" came down to the owner's memory."""
        y = self._year()
        r = self._finish(y)
        self.assertEqual(r.status_code, 200, r.content)
        y.refresh_from_db()
        self.assertIsNotNone(y.finished_at)
        self.assertEqual(y.finished_by, 'fin-admin@example.com')
        self.assertEqual(r.json()['state'], 'finished')

    def test_an_OPEN_round_must_be_closed_first(self):
        """Two deliberate steps, the same reasoning as "creating never opens". Stopping new
        applicants and ending the grace period are different decisions taken at different times —
        collapsing them would have shut out the thirty students of 1–7 July."""
        y = self._year(is_open=True)
        r = self._finish(y)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'still_open')
        y.refresh_from_db()
        self.assertIsNone(y.finished_at)

    def test_the_code_must_be_typed(self):
        y = self._year()
        r = self._finish(y, confirm='fin-wrong')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'confirm_mismatch')
        y.refresh_from_db()
        self.assertIsNone(y.finished_at)

    def test_the_typed_code_is_case_insensitive(self):
        """It is a confirmation, not a password. Refusing FIN-Y for fin-y would teach nothing."""
        y = self._year()
        self.assertEqual(self._finish(y, confirm='FIN-Y').status_code, 200)

    def test_finishing_twice_is_refused(self):
        y = self._year(finished_at=timezone.now())
        r = self._finish(y)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'already_finished')

    def test_another_tenants_round_is_a_404_not_a_403(self):
        other = ScholarshipCohort.objects.create(
            programme=self.other_prog, owning_organisation=self.other_org,
            code='other-y', name='Other Y', year=2027, is_active=True, is_open=False)
        self.assertEqual(self._finish(other).status_code, 404)
        other.refresh_from_db()
        self.assertIsNone(other.finished_at)

    # ── terminal ─────────────────────────────────────────────────────────────────────────────

    def test_a_FINISHED_round_cannot_BE_REOPENED(self):
        """⚠ THE OWNER'S RULING, AND THE REFUSAL IS ON THE SERVER. A screen that merely hides the
        control is a suggestion; this has to be a rule, because nothing in the product clears
        `finished_at` and reopening would silently restart an intake everyone believes is over."""
        y = self._year(finished_at=timezone.now())
        self._auth()
        r = self.client.patch(f'/api/v1/admin/scholarship/intake-years/{y.id}/',
                              {'is_open': True}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'round_finished')
        y.refresh_from_db()
        self.assertFalse(y.is_open)

    def test_a_finished_round_can_still_be_RENAMED(self):
        """Terminal means it cannot take applications again — not that its record is frozen. A typo
        in the name a student saw should still be correctable."""
        y = self._year(finished_at=timezone.now())
        self._auth()
        r = self.client.patch(f'/api/v1/admin/scholarship/intake-years/{y.id}/',
                              {'name': 'Fin Y (2027 intake)'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        y.refresh_from_db()
        self.assertEqual(y.name, 'Fin Y (2027 intake)')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheGracePeriod(TestCase):
    """⚠⚠ THE HALF THAT MUST NOT BE TIDIED AWAY.

    A CLOSED round still lets a student who had already started finish. A FINISHED one does not.
    Both directions are asserted, because a test that only pins the refusal would pass just as
    happily if closing had started refusing too — which is the change that would have cost thirty
    real students their applications.
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(
            code='grace-org', name='Grace Org', is_active=True)
        cls.prog = Programme.objects.create(
            organisation=cls.org, code='grace-gift', name_en='Grace Gift', is_active=True)

    def _round(self, **kw):
        defaults = dict(programme=self.prog, owning_organisation=self.org, code='grace-y',
                        name='Grace Y', year=2027, is_active=True, is_open=False)
        defaults.update(kw)
        return ScholarshipCohort.objects.create(**defaults)

    def _shortlisted(self, cohort, nric):
        profile = StudentProfile.objects.create(
            supabase_user_id=f'grace-{nric}', name='Grace Student', nric=nric)
        return ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='shortlisted')

    def test_a_CLOSED_round_still_lets_a_started_student_submit(self):
        """The 1–7 July 2026 behaviour, pinned. `confirm_profile` reaches the completeness check
        (it raises `IncompleteProfileError` on this bare fixture) rather than being stopped by the
        round — that is the proof the round did not refuse it."""
        app = self._shortlisted(self._round(), '900101010201')
        with self.assertRaises(Exception) as caught:
            confirm_profile(app)
        self.assertNotIsInstance(caught.exception, RoundFinishedError)

    def test_a_FINISHED_round_refuses_a_late_submission(self):
        app = self._shortlisted(self._round(finished_at=timezone.now()), '900101010202')
        with self.assertRaises(RoundFinishedError):
            confirm_profile(app)

    def test_the_refusal_comes_BEFORE_the_completeness_check(self):
        """Nothing the student uploads can fix a finished round, so pointing them at a missing
        document would be advice they cannot act on. The order is the message."""
        app = self._shortlisted(self._round(finished_at=timezone.now()), '900101010203')
        with self.assertRaises(RoundFinishedError):
            confirm_profile(app)
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')
        self.assertIsNone(app.profile_completed_at)
