"""Team tables T5b (2026-11-03) — QC is self-sufficient, and QC never decides their own.

Roadmap `docs/plans/2026-11-01-team-tables-roadmap.md` T5 (owner "approve all"): *"QC implicitly sees ALL students
and may decide on any except those they reviewed / interviewed / were assigned (QC self-sufficient, no `see_all`
dependency)."* decisions.md "Team tables T5b".

- `QcAloneReads`   — a person holding `qc` WITHOUT a stored `see_all` reads the Applications list and a file
                     exactly as `see_all + qc` does; another organisation stays 404 / unseen. Since sprint S1 both
                     are refused Scholars (its own key, `scholars`, which `qc` does not bring). (The
                     access matrix asks every other admin door: `test_team_tables_matrix.T5bQcAlone`.)
- `SeparationGuard` — the QC decision refuses whoever was ever assigned, interviewed (a draft counts), proposed
                     interview times, verify-accepted, recorded or once recorded the verdict, or is assigned now;
                     an unrelated QC passes; a super passes whatever they did.
- `ThroughTheDoors` — a QC working an UNASSIGNED case through the real review endpoints (org-wide write, kept) is
                     then refused the QC decision on it, on every outcome (accept / reopen / reject).
"""
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import qc_separation
from apps.scholarship.models import (
    AssignmentEvent, InterviewSession, InterviewSlot, ScholarshipApplication, StaffActivity,
)
from apps.scholarship.services import assign_reviewer
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, answered_findings, authed_client, make_admin, make_application, make_cohort,
)

API = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
APPS = '/api/v1/admin/scholarship/applications/'
SCHOLARS = '/api/v1/admin/scholarship/scholars/'
METRICS = '/api/v1/admin/scholarship/verdict-metrics/'


def _qc_url(app):
    return f'{APPS}{app.pk}/qc-decision/'


def _ids(body):
    """Every `id` in a JSON body, at any depth (the lists' row shapes are not this file's business)."""
    if isinstance(body, dict):
        return {*([body['id']] if 'id' in body else []), *(i for v in body.values() for i in _ids(v))}
    if isinstance(body, list):
        return {i for v in body for i in _ids(v)}
    return set()


def _set(admin, keys):
    PartnerAdmin.objects.filter(pk=admin.pk).update(permissions=keys)
    admin.refresh_from_db()
    return admin


@override_settings(**API)
class QcAloneReads(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.org = cls.cohort.owning_organisation
        cls.other_cohort = make_cohort()
        cls.mine = make_application('awaiting_qc', outcome='recommend', cohort=cls.cohort)
        cls.scholar = make_application('active', cohort=cls.cohort)
        cls.theirs = make_application('awaiting_qc', outcome='recommend', cohort=cls.other_cohort)
        cls.their_scholar = make_application('active', cohort=cls.other_cohort)
        # Three people holding `qc` with NO stored `see_all`, each beside a TWIN of the same role
        # holding `see_all + qc` (the qc twin is the live QC preset, NULL). Role labels still add
        # their own extras (an `admin` sees the mentoring summary), so each is asked of its own twin.
        cls.preset = make_admin('qc', owning_org=cls.org)
        cls.qc_only = _set(make_admin('qc', owning_org=cls.org), ['qc'])
        cls.admin_qc = _set(make_admin('admin', owning_org=cls.org), ['qc'])
        cls.reviewer_qc = _set(make_admin('reviewer', first_seen_at=timezone.now(), owning_org=cls.org), ['review', 'qc'])
        cls.twins = (
            (cls.qc_only, cls.preset),
            (cls.admin_qc, _set(make_admin('admin', owning_org=cls.org), ['see_all', 'qc'])),
            (cls.reviewer_qc, _set(make_admin('reviewer', first_seen_at=timezone.now(), owning_org=cls.org), ['review', 'see_all', 'qc'])),
        )

    def test_qc_alone_resolves_to_the_preset(self):
        for who in (self.qc_only, self.admin_qc):
            self.assertEqual(who.permission_set, ('see_all', 'qc'))
        self.assertEqual(self.reviewer_qc.permission_set, ('review', 'see_all', 'qc'))

    def test_the_applications_list_detail_and_metrics_read_as_see_all_plus_qc(self):
        urls = (APPS, f'{APPS}{self.mine.pk}/', METRICS)
        for who, twin in self.twins:
            for url in urls:
                with self.subTest(who=who.role, url=url):
                    want, got = authed_client(twin).get(url), authed_client(who).get(url)
                    self.assertEqual(want.status_code, 200, want.content[:200])
                    self.assertEqual(got.status_code, 200, got.content[:200])
                    if url in (APPS, METRICS):
                        self.assertEqual(got.json(), want.json())

    def test_neither_qc_nor_its_twin_opens_scholars(self):
        # Sprint S1 (owner 2026-11-09): `qc` brings `see_all`, never `scholars`.
        for pair in self.twins:
            for who in pair:
                for url in (SCHOLARS, f'{SCHOLARS}{self.scholar.pk}/'):
                    with self.subTest(who=who.role, url=url):
                        self.assertEqual(authed_client(who).get(url).status_code, 403)

    def test_the_lists_hold_only_their_own_organisation(self):
        apps = _ids(authed_client(self.qc_only).get(APPS).json())
        self.assertIn(self.mine.pk, apps)
        self.assertNotIn(self.theirs.pk, apps)

    def test_another_organisation_is_still_404(self):
        c = authed_client(self.qc_only)
        self.assertEqual(c.get(f'{APPS}{self.theirs.pk}/').status_code, 404)
        self.assertEqual(c.get(f'{SCHOLARS}{self.their_scholar.pk}/').status_code, 403)   # S1: no door
        with mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[]):
            self.assertEqual(c.post(_qc_url(self.theirs), {'decision': 'accept'}, format='json').status_code,
                             404)

    def test_qc_alone_may_qc_a_case_it_never_touched(self):
        with mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[]):
            r = authed_client(self.qc_only).post(_qc_url(self.mine), {'decision': 'accept'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.status, 'recommended')


@override_settings(**API)
class SeparationGuard(TestCase):
    """Each kind of work on the case, by the person who then asks to QC it, through the real endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.org = cls.cohort.owning_organisation
        cls.super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.reviewer = make_admin('reviewer', first_seen_at=timezone.now(), owning_org=cls.org)
        cls.qc = make_admin('qc', owning_org=cls.org)            # the one who did the work
        cls.other_qc = make_admin('qc', owning_org=cls.org)      # unrelated

    def setUp(self):
        self.app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort,
                                    reviewer=self.reviewer)
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _ask(self, who, decision='accept'):
        body = {'decision': decision, 'comments': 'Recheck the payslips.'}
        r = authed_client(who).post(_qc_url(self.app), body, format='json')
        return r.status_code, (r.json().get('code') if r.status_code != 200 else None)

    def _refused(self, who, code):
        for decision in ('accept', 'reopen', 'reject'):
            with self.subTest(decision=decision):
                self.assertEqual(self._ask(who, decision), (403, code))
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'interviewed')          # nothing moved

    def test_an_unrelated_qc_passes(self):
        self.assertEqual(self._ask(self.other_qc), (200, None))

    def test_the_current_assignee_is_refused(self):
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(assigned_to=self.qc)
        self._refused(self.qc, 'self_qc_forbidden')

    def test_the_verdict_recorder_is_refused(self):
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(verdict_decided_by=self.qc.email.upper())
        self._refused(self.qc, 'self_verdict_qc_forbidden')

    def test_a_reassign_does_not_launder_self_qc(self):
        # Assigned to the QC while in interview, handed to the reviewer by the service the assign
        # endpoint calls (a case changes hands only at profile_complete / interviewing), then sent to QC.
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(assigned_to=self.qc,
                                                                    status='interviewing')
        self.app.refresh_from_db()
        assign_reviewer(self.app, reviewer=self.reviewer, by_admin=self.super)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='interviewed')
        self.app.refresh_from_db()
        self.assertEqual(self.app.assigned_to_id, self.reviewer.pk)
        self.assertTrue(AssignmentEvent.objects.filter(application=self.app, from_admin=self.qc).exists())
        self._refused(self.qc, 'self_assigned_qc_forbidden')

    def test_an_earlier_assignment_counts_by_its_to_side_too(self):
        AssignmentEvent.objects.create(application=self.app, from_admin=None, to_admin=self.qc)
        self._refused(self.qc, 'self_assigned_qc_forbidden')

    def test_the_interviewer_is_refused_submitted_or_draft(self):
        for state in ('submitted', 'draft'):
            with self.subTest(state=state):
                InterviewSession.objects.filter(application=self.app).delete()
                InterviewSession.objects.create(application=self.app, interviewer=self.qc, status=state)
                self._refused(self.qc, 'self_interview_qc_forbidden')

    def test_proposing_interview_times_counts_as_interviewing(self):
        from django.utils import timezone
        InterviewSlot.objects.create(application=self.app, reviewer=self.qc, start=timezone.now())
        self._refused(self.qc, 'self_interview_qc_forbidden')

    def test_the_verify_accept_counts_as_review_work(self):
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(verified_by=self.qc.email)
        self._refused(self.qc, 'self_review_qc_forbidden')

    def test_a_verdict_once_recorded_counts_after_somebody_re_records_it(self):
        # `verdict_decided_by` now names the reviewer; the QC's own activity row still says they recorded one.
        for verb in qc_separation.REVIEW_VERBS:
            with self.subTest(verb=verb):
                StaffActivity.objects.filter(actor=self.qc).delete()
                StaffActivity.objects.create(actor=self.qc, verb=verb, subject_type='application',
                                             subject_id=self.app.pk)
                self._refused(self.qc, 'self_review_qc_forbidden')

    def test_a_query_to_the_student_does_not_count(self):
        StaffActivity.objects.create(actor=self.qc, verb='query_raised', subject_type='application',
                                     subject_id=self.app.pk)
        self.assertEqual(self._ask(self.qc), (200, None))

    def test_work_on_ANOTHER_case_does_not_count(self):
        elsewhere = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort)
        AssignmentEvent.objects.create(application=elsewhere, to_admin=self.qc)
        InterviewSession.objects.create(application=elsewhere, interviewer=self.qc)
        StaffActivity.objects.create(actor=self.qc, verb='verdict_recorded', subject_type='application',
                                     subject_id=elsewhere.pk)
        self.assertEqual(self._ask(self.qc), (200, None))

    def test_the_organisation_admin_is_held_to_it_too(self):
        AssignmentEvent.objects.create(application=self.app, to_admin=self.lead)
        self._refused(self.lead, 'self_assigned_qc_forbidden')

    def test_a_super_who_did_all_of_it_is_the_owner_override(self):
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(
            assigned_to=self.super, verdict_decided_by=self.super.email, verified_by=self.super.email)
        AssignmentEvent.objects.create(application=self.app, to_admin=self.super)
        InterviewSession.objects.create(application=self.app, interviewer=self.super, status='submitted')
        self.assertEqual(self._ask(self.super), (200, None))


@override_settings(**API)
class ThroughTheDoors(TestCase):
    """`qc` writes org-wide (`_can_review_app`, kept): a QC may record an interview or a verdict on a case
    not assigned to them. The guard must then hold at the QC decision — that is why it widened."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', first_seen_at=timezone.now(), owning_org=cls.org)
        cls.qc = _set(make_admin('qc', owning_org=cls.org), ['qc'])     # qc alone, no stored see_all
        cls.other_qc = make_admin('qc', owning_org=cls.org)

    def setUp(self):
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _to_qc(self, app):
        ScholarshipApplication.objects.filter(pk=app.pk).update(status='interviewed')

    def test_an_interview_draft_saved_on_an_unassigned_case_blocks_the_qc(self):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        r = authed_client(self.qc).post(f'{APPS}{app.pk}/interview/',
                                        {'findings': answered_findings(app), 'overall_note': 'Met her.'},
                                        format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(InterviewSession.objects.get(application=app).interviewer_id, self.qc.pk)
        self._to_qc(app)
        r = authed_client(self.qc).post(_qc_url(app), {'decision': 'accept'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (403, 'self_interview_qc_forbidden'))
        r = authed_client(self.other_qc).post(_qc_url(app), {'decision': 'accept'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_a_draft_author_whose_credit_a_colleague_took_is_still_refused(self):
        # T5b review round 1: the draft's credit moves to its LAST author (owner 2026-08-13), so QC A
        # drafts, reviewer B rewrites a finding and submits — the session names B only. A's own
        # `interview_drafted` row is what still refuses A.
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        url = f'{APPS}{app.pk}/interview/'
        r = authed_client(self.qc).post(url, {'findings': answered_findings(app), 'overall_note': 'A met her.'},
                                        format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        rewritten = {k: {**v, 'rationale': 'B checked this again.'} for k, v in answered_findings(app).items()}
        r = authed_client(self.reviewer).post(url, {'findings': rewritten, 'overall_note': 'B rewrote it.'},
                                              format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        r = authed_client(self.reviewer).post(f'{url}submit/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        session = InterviewSession.objects.get(application=app)
        self.assertEqual((session.status, session.interviewer_id), ('submitted', self.reviewer.pk))
        drafted = StaffActivity.objects.filter(verb='interview_drafted', subject_type='application',
                                               subject_id=app.pk)
        self.assertEqual(sorted(drafted.values_list('actor_id', flat=True)),
                         sorted([self.qc.pk, self.reviewer.pk]))
        self._to_qc(app)
        r = authed_client(self.qc).post(_qc_url(app), {'decision': 'accept'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (403, 'self_review_qc_forbidden'))
        r = authed_client(self.other_qc).post(_qc_url(app), {'decision': 'accept'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_re_saving_ones_own_draft_writes_one_row_not_one_per_save(self):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        url = f'{APPS}{app.pk}/interview/'
        for note in ('first', 'second', 'third'):
            r = authed_client(self.reviewer).post(url, {'findings': answered_findings(app), 'overall_note': note},
                                                  format='json')
            self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(StaffActivity.objects.filter(verb='interview_drafted', actor=self.reviewer).count(), 1)

    def test_a_verdict_recorded_on_an_unassigned_case_blocks_the_qc(self):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        verdict = {'officer_verdict': {'identity': 'pass', 'academic': 'pass', 'pathway': 'pass',
                                       'income': 'pass', 'overall': 'hold'}}
        with mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[]):
            r = authed_client(self.qc).post(f'{APPS}{app.pk}/record-verdict/', verdict, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.verdict_decided_by, self.qc.email)
        # The reviewer then re-records it (the stamp now names them); the QC's own row still counts.
        with mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[]):
            r = authed_client(self.reviewer).post(f'{APPS}{app.pk}/record-verdict/', verdict, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self._to_qc(app)
        r = authed_client(self.qc).post(_qc_url(app), {'decision': 'accept'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (403, 'self_review_qc_forbidden'))
