"""The one-off repair behind the mis-credited interviews (2026-08-18).

Pre-TD-216, whoever first touched an interview draft owned the credit for good, so the July
triage sweep left 24 submitted interviews reading "Interviewed by Ve. Elanjelian" over work
somebody else did.

What the repair must NOT do carries as much weight as what it must:

* it must credit the ASSIGNED REVIEWER, not the verdict-recorder, or application #13 — where the
  reviewer interviewed and the OWNER recorded the decision — gets re-credited to the owner, which
  is the defect wearing a different hat;
* it must leave alone an interview a reviewer is already credited with, even when somebody else
  recorded the verdict (applications 12 and 51), because that divergence is legitimate;
* it must leave alone an interview the owner genuinely did conduct;
* and it must do nothing at all on a second run.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import (
    InterviewSession, ScholarshipApplication, ScholarshipCohort,
)

OWNER = 'tamiliam@gmail.com'


class TestRepairInterviewCredit(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='ric', name='RIC Org')
        cls.owner = PartnerAdmin.objects.create(
            supabase_user_id='ric-super', is_super_admin=True, role='super', is_active=True,
            name='Ve. Elanjelian', email=OWNER)
        cls.owner_org_admin = PartnerAdmin.objects.create(
            supabase_user_id='ric-orgadmin', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Ve. Elanjelian', email='elanjelian@me.com')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='ric-rev', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Balan Sithamparam', email='balan@example.com')
        cls.other_admin = PartnerAdmin.objects.create(
            supabase_user_id='ric-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Suresh Thirugnanam', email='suresh@example.com')
        cls.cohort = ScholarshipCohort.objects.create(
            code='ric-c', name='B40', year=2026, owning_organisation=cls.org)

    _uid = 0

    def _app(self, **kwargs):
        type(self)._uid += 1
        profile = StudentProfile.objects.create(
            supabase_user_id=f'ric-stud-{self._uid}', name='A Student', grades={},
            household_income=1000)
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='interviewed', **kwargs)

    def _session(self, app, interviewer, status='submitted'):
        return InterviewSession.objects.create(
            application=app, interviewer=interviewer, status=status,
            overall_note='Min Qual is 5A\'s', submitted_at=timezone.now())

    def _run(self, *args):
        out = StringIO()
        call_command('repair_interview_credit', *args, stdout=out)
        return out.getvalue()

    # ── the shapes it must repair ────────────────────────────────────────────────────────────

    def test_credits_the_assigned_reviewer_not_the_verdict_recorder(self):
        """#13: the reviewer interviewed, the OWNER recorded the verdict.

        This is the bite test for the precedence. Key on `verdict_decided_by` and the owner is
        credited all over again — a repair that repairs nothing.
        """
        app = self._app(assigned_to=self.reviewer, verdict_decided_by=OWNER)
        session = self._session(app, self.owner)

        self._run('--apply')

        session.refresh_from_db()
        self.assertEqual(session.interviewer, self.reviewer)

    def test_falls_back_to_the_verdict_recorder_when_nobody_was_assigned(self):
        """#137: never assigned; an org_admin wrote, submitted and decided it in one sitting."""
        app = self._app(assigned_to=None, verdict_decided_by='suresh@example.com')
        session = self._session(app, self.owner)

        self._run('--apply')

        session.refresh_from_db()
        self.assertEqual(session.interviewer, self.other_admin)

    def test_repairs_the_org_admin_account_too(self):
        """Both of the owner's accounts ran the sweep — apps 28 and 101 carry the other one."""
        app = self._app(assigned_to=self.reviewer, verdict_decided_by='balan@example.com')
        session = self._session(app, self.owner_org_admin)

        self._run('--apply')

        session.refresh_from_db()
        self.assertEqual(session.interviewer, self.reviewer)

    def test_matches_the_verdict_email_case_insensitively(self):
        app = self._app(assigned_to=None, verdict_decided_by='Suresh@Example.COM')
        session = self._session(app, self.owner)

        self._run('--apply')

        session.refresh_from_db()
        self.assertEqual(session.interviewer, self.other_admin)

    # ── the shapes it must leave alone ───────────────────────────────────────────────────────

    def test_leaves_a_reviewers_own_credit_alone_when_the_owner_decided(self):
        """Applications 12 and 51: the reviewer interviewed, the owner recorded the decision.

        The divergence is legitimate. The fence is the current HOLDER, never the divergence —
        widen it and this reviewer loses an interview she really did conduct.
        """
        app = self._app(assigned_to=None, verdict_decided_by=OWNER)
        session = self._session(app, self.reviewer)

        self._run('--apply')

        session.refresh_from_db()
        self.assertEqual(session.interviewer, self.reviewer)

    def test_leaves_an_interview_the_owner_really_conducted(self):
        """#31/#67/#84/#87 — unassigned, owner-decided. Resolves to the owner, so: no change."""
        app = self._app(assigned_to=None, verdict_decided_by=OWNER)
        session = self._session(app, self.owner)

        out = self._run('--apply')

        session.refresh_from_db()
        self.assertEqual(session.interviewer, self.owner)
        self.assertIn('no change', out)

    def test_skips_a_row_with_nothing_to_go_on(self):
        app = self._app(assigned_to=None, verdict_decided_by='')
        session = self._session(app, self.owner)

        out = self._run('--apply')

        session.refresh_from_db()
        self.assertEqual(session.interviewer, self.owner)
        self.assertIn('SKIPPED', out)

    def test_leaves_a_draft_alone(self):
        """A draft still self-heals: TD-216 moves the credit on the next authoring save."""
        app = self._app(assigned_to=self.reviewer, verdict_decided_by='balan@example.com')
        session = self._session(app, self.owner, status='draft')

        self._run('--apply')

        session.refresh_from_db()
        self.assertEqual(session.interviewer, self.owner)

    # ── how it runs ──────────────────────────────────────────────────────────────────────────

    def test_reports_without_writing_by_default(self):
        app = self._app(assigned_to=self.reviewer, verdict_decided_by=OWNER)
        session = self._session(app, self.owner)

        out = self._run()

        session.refresh_from_db()
        self.assertEqual(session.interviewer, self.owner)
        self.assertIn('report only', out)
        self.assertIn('1 re-credited', out)

    def test_is_idempotent(self):
        app = self._app(assigned_to=self.reviewer, verdict_decided_by=OWNER)
        self._session(app, self.owner)

        self._run('--apply')
        out = self._run('--apply')

        self.assertIn('0 re-credited', out)

    def test_does_not_bump_updated_at(self):
        """A credit correction is not an edit of the interview — the timestamp must not move."""
        app = self._app(assigned_to=self.reviewer, verdict_decided_by=OWNER)
        session = self._session(app, self.owner)
        before = InterviewSession.objects.get(pk=session.pk).updated_at

        self._run('--apply')

        self.assertEqual(InterviewSession.objects.get(pk=session.pk).updated_at, before)

    def test_app_ids_scopes_the_run(self):
        target = self._app(assigned_to=self.reviewer, verdict_decided_by=OWNER)
        other = self._app(assigned_to=self.reviewer, verdict_decided_by=OWNER)
        target_session = self._session(target, self.owner)
        other_session = self._session(other, self.owner)

        self._run('--apply', '--app-ids', str(target.id))

        target_session.refresh_from_db()
        other_session.refresh_from_db()
        self.assertEqual(target_session.interviewer, self.reviewer)
        self.assertEqual(other_session.interviewer, self.owner)
