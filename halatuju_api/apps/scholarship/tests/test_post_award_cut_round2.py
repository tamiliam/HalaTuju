"""POST-AWARD-CUT review round 2 (18 Nov): the write rule asks for a READ, the review track ends at
the award, and a case that ended past the award is classified on the award's own stamps.

  H1 — "a caller writes only to a case they can READ": past the award by either page (the
       Applications read, or the Scholars key with a file); a case that ended before it by the
       Applications read. No read is widened.
  P1 — owner R5, the review track ends at the award: record-verdict, suggest-gaps (and the
       interview doors, which share the prologue) and generate-profile answer 400 `case_closed`
       past it, a reopen notwithstanding. re-run-vision stays on the case rule.
  R3 — finalise-profile (a queued, billable cron pass) is refused past the award too.
  M1 — a terminal case is past the award on `active_at`, its decline snapshot, or `awarded_at`;
       a reopen never makes it OPEN.
"""
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import closure, reopen
from apps.scholarship.models import ApplicantDocument, SponsorProfile
from apps.scholarship.models.interviews import InterviewSession
from apps.scholarship.staff_lifecycle import OPEN, PAST_AWARD, PRE_AWARD_END, case_stage
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)

APPS = '/api/v1/admin/scholarship/applications/'
VERDICT = {'officer_verdict': {'identity': 'pass', 'academic': 'pass', 'pathway': 'pass',
                               'income': 'pass', 'overall': 'decline'}, 'reason': 'test'}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _World(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', owning_org=org)
        cls.qc = make_admin('qc', owning_org=org)
        cls.admin = make_admin('admin', owning_org=org)        # the preset: see_all + scholars + ...
        cls.scholars_only = make_admin('admin', owning_org=org, permissions=['scholars'])
        cls.approve_only = make_admin('admin', owning_org=org, permissions=['students.approve'])
        cls.super = make_admin(super_admin=True)

    def case(self, stage, **kw):
        return make_application(stage, cohort=self.cohort, reviewer=self.reviewer, **kw)

    def patch(self, who, app):
        return authed_client(who).patch(f'{APPS}{app.id}/', {'mentoring_candidate': True}, format='json')

    def generate(self, who, app):
        with mock.patch('apps.scholarship.services.generate_ready_profile',
                        return_value=(None, 'not reached')) as gen:
            r = authed_client(who).post(f'{APPS}{app.id}/generate-profile/', {}, format='json')
        return r, gen.called

    def vision(self, who, app):
        doc = ApplicantDocument.objects.create(application=app, doc_type='ic')
        with mock.patch('apps.scholarship.reextract.reextract_document', return_value=False) as rx:
            r = authed_client(who).post(f'{APPS}{app.id}/documents/{doc.id}/re-run-vision/', {}, format='json')
        return r, rx.called


class AWriterMustReadTheCase(_World):
    def test_a_scholars_holder_with_no_read_of_the_case_writes_nothing(self):
        app = self.case('awarded')                     # no wallet: no file, and no Applications read
        self.assertEqual(authed_client(self.scholars_only).get(f'{APPS}{app.id}/').status_code, 403)
        self.assertEqual(self.patch(self.scholars_only, app).status_code, 403)
        for door in (self.generate, self.vision):
            with self.subTest(door=door.__name__):
                r, called = door(self.scholars_only, app)
                self.assertEqual((r.status_code, called), (403, False))

    def test_a_scholars_holder_who_reads_the_file_keeps_the_file_writes(self):
        app = self.case('active')                      # read on the Scholars page (`_file_for`)
        self.assertEqual(authed_client(self.scholars_only).get(f'/api/v1/admin/scholarship/scholars/{app.id}/')
                         .status_code, 200)
        self.assertEqual(self.patch(self.scholars_only, app).status_code, 200)
        r, called = self.vision(self.scholars_only, app)
        self.assertEqual((r.status_code, called), (400, True))   # ran; the mock says "no automatic check"

    def test_an_approver_with_no_applications_read_writes_nothing_on_a_pre_award_end(self):
        for stage in ('expired', 'rejected'):
            app = self.case(stage)
            self.assertEqual(case_stage(app), PRE_AWARD_END)
            c = authed_client(self.approve_only)
            referee = c.post(f'{APPS}{app.id}/referees/', {'name': 'X', 'phone': '0123456789',
                                                           'relationship': 'teacher'}, format='json')
            (gen, gen_called), (vis, vis_called) = self.generate(self.approve_only, app), \
                self.vision(self.approve_only, app)
            with self.subTest(stage=stage):
                self.assertEqual(c.get(f'{APPS}{app.id}/').status_code, 403)
                self.assertEqual((self.patch(self.approve_only, app).status_code, referee.status_code,
                                  gen.status_code, vis.status_code), (403, 403, 403, 403))
                self.assertEqual((gen_called, vis_called), (False, False))

    def test_the_served_flag_follows_the_same_rule(self):
        reader = make_admin('admin', owning_org=self.cohort.owning_organisation, permissions=['see_all'])
        body = authed_client(reader).get(f'{APPS}{self.case("expired").id}/').json()
        self.assertEqual((body['can_write'], body['can_cancel_decline'], body['can_tranche']), (False, False, False))


class TheReviewTrackEndsAtTheAward(_World):
    def test_record_verdict_and_suggest_gaps_refuse_a_funded_case(self):
        for who, kw in ((self.admin, {}), (self.super, {'decision_reopened_at': timezone.now()})):
            app = self.case('active', **kw)
            before = app.award_amount
            c = authed_client(who)
            verdict = c.post(f'{APPS}{app.id}/record-verdict/', VERDICT, format='json')
            with mock.patch('apps.scholarship.gap_engine.generate_interview_gaps',
                            return_value={'gaps': []}) as gaps:
                suggest = c.post(f'{APPS}{app.id}/suggest-gaps/', {}, format='json')
            app.refresh_from_db()
            with self.subTest(who=who.email):
                self.assertEqual((verdict.status_code, verdict.json()['code']), (400, 'case_closed'))
                self.assertEqual((suggest.status_code, suggest.json()['code']), (400, 'case_closed'))
                self.assertFalse(gaps.called)
                self.assertEqual((app.status, app.award_amount), ('active', before))

    def test_generate_profile_refuses_past_the_award_and_works_before_it(self):
        r, called = self.generate(self.admin, self.case('active'))
        self.assertEqual((r.status_code, r.json()['code'], called), (400, 'case_closed', False))
        r, called = self.generate(self.reviewer, self.case('interviewing'))
        self.assertEqual((r.status_code, called), (503, True))   # reached the generator (mocked to fail)


class APastAwardEndingIsNeverOpen(_World):
    def test_closed_from_awarded_then_reopened_is_never_open(self):
        app = self.case('awarded', verdict_decided_at=timezone.now())
        closure.close_application(app, closure_reason='stalled', by_email='lead@example.test')
        self.assertEqual((app.status, app.active_at, case_stage(app)), ('closed', None, PAST_AWARD))
        reopen.reopen_decision(app, by_admin=self.super, reason='test')
        app.refresh_from_db()
        self.assertEqual(case_stage(app), PAST_AWARD)
        for who, code in ((self.reviewer, 403), (self.qc, 403), (self.admin, 200)):
            with self.subTest(who=who.role):
                self.assertEqual(self.patch(who, app).status_code, code)

    def test_a_legacy_withdrawn_row_of_a_funded_student(self):
        now = timezone.now()
        app = self.case('active')
        type(app).objects.filter(pk=app.pk).update(status='withdrawn', decision_reopened_at=now)
        app.refresh_from_db()
        self.assertEqual(case_stage(app), PAST_AWARD)
        self.assertEqual(self.patch(self.reviewer, app).status_code, 403)

    def test_a_reopened_decline_of_a_funded_student(self):
        app = self.case('rejected', pre_decline_status='active', decision_reopened_at=timezone.now())
        self.assertEqual(case_stage(app), PAST_AWARD)
        self.assertEqual(self.patch(self.reviewer, app).status_code, 403)

    def test_a_fallen_through_award(self):
        # `awarded_at` outlives `revert_to_pool`: the open status decides first, the decline snapshot next.
        back = self.case('recommended', awarded_at=timezone.now())
        self.assertEqual(case_stage(back), OPEN)
        declined = self.case('rejected', awarded_at=timezone.now(), pre_decline_status='recommended',
                             decision_reopened_at=timezone.now())
        self.assertEqual(case_stage(declined), OPEN)
        self.assertEqual(self.patch(self.reviewer, declined).status_code, 200)
        # Closed with no snapshot of where from: fails closed, to the lead keys.
        closure.close_application(back, closure_reason='stalled', by_email='lead@example.test')
        self.assertEqual(case_stage(back), PAST_AWARD)


class TheWriteRepliesServeTheFlags(_World):
    """L4: the two replies that answered with the bare serializer now serve the write flags, so the
    cockpit is not left with the flags of a case that has moved on."""
    def test_an_org_reject_serves_the_reviewer_losing_the_case(self):
        app = self.case('shortlisted')
        body = authed_client(self.super).post(f'{APPS}{app.id}/org-reject/', {'comments': 'test'},
                                              format='json').json()
        self.assertEqual((body['status'], body['can_write']), ('rejected', True))
        self.assertFalse(authed_client(self.reviewer).get(f'{APPS}{app.id}/').json()['can_write'])

    def test_a_reporting_date_reply_serves_the_flags(self):
        r = authed_client(self.reviewer).post(f'{APPS}{self.case("interviewing").id}/reporting-date/',
                                              {'date': '2027-01-04'}, format='json')
        self.assertEqual((r.status_code, r.json()['can_write'], r.json()['can_tranche']), (200, True, True))


class FinaliseProfileEndsAtTheAward(_World):
    """Review round 3: finalise-profile queues a billable cron pass (refine + anon blurb), so it is
    refused past the award as generate-profile is, a reopen notwithstanding."""
    def ready(self, stage, **kw):
        app = self.case(stage, **kw)
        sp, _ = SponsorProfile.objects.get_or_create(application=app)
        draft = [f.name for f in SponsorProfile._meta.fields if f.name in ('draft_markdown', 'markdown')]
        SponsorProfile.objects.filter(pk=sp.pk).update(**{f: 'draft text' for f in draft})
        InterviewSession.objects.create(application=app, interviewer=self.reviewer, status='submitted',
                                        submitted_at=timezone.now())
        return app

    def finalise(self, who, app):
        before = SponsorProfile.objects.get(application=app).finalise_state
        with mock.patch('apps.scholarship.profile_finalise.queue_finalise') as queue:
            r = authed_client(who).post(f'{APPS}{app.id}/finalise-profile/', {}, format='json')
        after = SponsorProfile.objects.get(application=app).finalise_state
        return r, queue.called, before == after

    def test_refused_past_the_award_a_reopen_notwithstanding(self):
        for name, who, app in (('admin', self.admin, self.ready('active')),
                               ('scholars_only', self.scholars_only, self.ready('active')),
                               ('super, reopened', self.super,
                                self.ready('active', decision_reopened_at=timezone.now()))):
            with self.subTest(who=name):
                self.assertEqual(case_stage(app), PAST_AWARD)
                r, queued, unchanged = self.finalise(who, app)
                self.assertEqual((r.status_code, r.json()['code'], queued, unchanged),
                                 (400, 'case_closed', False, True))

    def test_an_open_case_still_queues(self):
        app = self.ready('interviewing')
        r = authed_client(self.reviewer).post(f'{APPS}{app.id}/finalise-profile/', {}, format='json')
        self.assertEqual((r.status_code, SponsorProfile.objects.get(application=app).finalise_state),
                         (200, 'pending'))
