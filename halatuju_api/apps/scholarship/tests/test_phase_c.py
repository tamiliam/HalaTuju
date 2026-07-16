"""Phase C: handoff hardening (confirm + accept-gate) + roles + assignment +
interview capture + request-info."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, Consent, FundingNeed, InterviewSession,
    ScholarshipApplication, ScholarshipCohort,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
SUPER = 'super-uid'
REVIEWER = 'reviewer-uid'
VIEWER = 'viewer-uid'
STUDENT = 'student-uid'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class PhaseCBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id=SUPER, is_super_admin=True, is_active=True,
            name='Super', email='super@example.com',
        )
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id=REVIEWER, role='reviewer', is_active=True,
            name='Reviewer', email='reviewer@example.com',
        )
        cls.viewer = PartnerAdmin.objects.create(
            supabase_user_id=VIEWER, role='admin', is_active=True,
            name='Viewer', email='viewer@example.com',
        )
        # Adult profile (2003-born NRIC) so guardian_docs are trivially satisfied.
        cls.profile = StudentProfile.objects.create(
            supabase_user_id=STUDENT, nric='030101-14-1234', name='Priya', school='SMK X',
            grades={f'sub{i}': 'A' for i in range(10)},
            household_income=2500, receives_str=True,
            student_signals={'field_interest': {'it': 5}},
            address='No. 1 Jalan ABC', postal_code='62100', city='Putrajaya',
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _make_app(self, status='shortlisted'):
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status=status, bucket='A',
            aspirations='Be an auditor', plans='Study hard',
            daily_life='Help at home each evening', fears='Worried about fees',
        )

    def _assigned_app(self, status='shortlisted'):
        """An application assigned to the reviewer — the realistic 'reviewing my own
        assigned case' scenario now that reviewers are assignment-scoped."""
        app = self._make_app(status=status)
        app.assigned_to = self.reviewer
        app.save(update_fields=['assigned_to'])
        return app

    def _complete(self, app):
        """Satisfy all 7 completeness parts for ``app`` (gate v2: STR route + father
        earner, with a compulsory offer letter + the route's income docs)."""
        FundingNeed.objects.create(application=app, categories=['living'], programme_months=36)
        for dt in ('ic', 'results_slip', 'offer_letter', 'parent_ic', 'str'):
            ApplicantDocument.objects.create(application=app, doc_type=dt, storage_path=f'x/{dt}')
        Consent.objects.create(application=app, version='t', is_active=True)
        ScholarshipApplication.objects.filter(pk=app.id).update(
            income_route='str', income_earner='father',
            # 2026-06 redesign: the structured family roster is compulsory.
            father_name='AROON', father_occupation='driver',
            mother_name='KOMATHI', mother_occupation='homemaker',
            siblings_in_school=1, siblings_in_tertiary=0)
        app.refresh_from_db()
        return app


class TestConfirm(PhaseCBase):
    def test_confirm_incomplete_returns_400_with_completeness(self):
        app = self._make_app()
        self._auth(STUDENT)
        r = self.client.post(f'/api/v1/scholarship/applications/{app.id}/confirm/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'incomplete_profile')
        self.assertIn('completeness', r.json())
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')

    @patch('apps.scholarship.services.send_profile_complete_admin_email')
    def test_confirm_complete_flips_status_and_emails(self, mock_email):
        app = self._complete(self._make_app())
        self._auth(STUDENT)
        r = self.client.post(f'/api/v1/scholarship/applications/{app.id}/confirm/')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'profile_complete')
        self.assertIsNotNone(app.profile_completed_at)
        mock_email.assert_called_once()

    @override_settings(PROFILE_COMPLETE_EMAIL_ENABLED=True)
    @patch('apps.scholarship.emails.send_profile_complete_student_email')
    @patch('apps.scholarship.services.send_submission_received_email')
    @patch('apps.scholarship.services.send_profile_complete_admin_email')
    def test_confirm_sends_profile_complete_email_when_flag_on(self, _admin, mock_ack, mock_new):
        app = self._complete(self._make_app())
        self._auth(STUDENT)
        r = self.client.post(f'/api/v1/scholarship/applications/{app.id}/confirm/')
        self.assertEqual(r.status_code, 200)
        mock_new.assert_called_once()            # richer email sent
        mock_ack.assert_not_called()             # basic ack superseded (no double-email)

    @patch('apps.scholarship.emails.send_profile_complete_student_email')
    @patch('apps.scholarship.services.send_submission_received_email')
    @patch('apps.scholarship.services.send_profile_complete_admin_email')
    def test_confirm_sends_basic_ack_when_flag_off(self, _admin, mock_ack, mock_new):
        app = self._complete(self._make_app())
        self._auth(STUDENT)
        r = self.client.post(f'/api/v1/scholarship/applications/{app.id}/confirm/')
        self.assertEqual(r.status_code, 200)
        mock_ack.assert_called_once()            # default: basic ack
        mock_new.assert_not_called()

    @patch('apps.scholarship.services.send_profile_complete_admin_email')
    def test_confirm_is_idempotent(self, _mock):
        app = self._complete(self._assigned_app(status='profile_complete'))
        self._auth(STUDENT)
        r = self.client.post(f'/api/v1/scholarship/applications/{app.id}/confirm/')
        self.assertEqual(r.status_code, 200)  # no-op, not an error

    def test_student_can_still_edit_after_confirm(self):
        """Completion is not a freeze — PATCH details still works at profile_complete."""
        app = self._complete(self._assigned_app(status='profile_complete'))
        self._auth(STUDENT)
        r = self.client.patch(
            f'/api/v1/scholarship/applications/{app.id}/',
            {'aspirations': 'Updated'}, format='json',
        )
        self.assertEqual(r.status_code, 200)


class TestAcceptGate(PhaseCBase):
    def test_accept_incomplete_hard_blocked(self):
        app = self._make_app()
        self._auth(SUPER)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{app.id}/verify-accept/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'incomplete_profile')
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')  # not accepted

    def test_accept_complete_succeeds(self):
        from django.utils import timezone
        app = self._complete(self._assigned_app(status='profile_complete'))
        # Check-3 audit gate: the reviewer must have recorded their verdict before close.
        ScholarshipApplication.objects.filter(pk=app.id).update(verdict_decided_at=timezone.now())
        self._auth(SUPER)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{app.id}/verify-accept/')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        # QC (2026-07): the reviewer's verify-accept lands in 'interviewed' (awaiting QC), not
        # 'recommended' — QC then clears it to recommended via qc-decision.
        self.assertEqual(app.status, 'interviewed')

    def test_viewer_cannot_accept(self):
        app = self._complete(self._assigned_app(status='profile_complete'))
        self._auth(VIEWER)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{app.id}/verify-accept/')
        self.assertEqual(r.status_code, 403)


class TestListFilters(PhaseCBase):
    def _second_app(self, status='shortlisted'):
        """A second application needs a distinct cohort (one app per cohort+profile)."""
        cohort2 = ScholarshipCohort.objects.create(code='c2', name='B40-2', year=2025)
        return ScholarshipApplication.objects.create(
            cohort=cohort2, profile=self.profile, status=status, bucket='A',
        )

    def test_status_profile_complete_filter(self):
        self._complete(self._assigned_app(status='profile_complete'))
        self._second_app(status='shortlisted')
        self._auth(SUPER)
        r = self.client.get('/api/v1/admin/scholarship/applications/?status=profile_complete')
        self.assertEqual(r.json()['total_count'], 1)

    def test_assigned_me_and_none(self):
        a = self._make_app()
        a.assigned_to = self.reviewer
        a.save(update_fields=['assigned_to'])
        self._second_app()  # unassigned
        # A reviewer is scoped to their assigned applicants only.
        self._auth(REVIEWER)
        r_me = self.client.get('/api/v1/admin/scholarship/applications/?assigned=me')
        self.assertEqual(r_me.json()['total_count'], 1)
        r_none = self.client.get('/api/v1/admin/scholarship/applications/?assigned=none')
        self.assertEqual(r_none.json()['total_count'], 0)   # can't see unassigned ones
        # A super sees the unassigned one.
        self._auth(SUPER)
        r_none_super = self.client.get('/api/v1/admin/scholarship/applications/?assigned=none')
        self.assertEqual(r_none_super.json()['total_count'], 1)


class TestRoleScoping(PhaseCBase):
    """Role realignment (2026-06-09): reviewer is ASSIGNMENT-scoped, partner has NO
    B40 access, super/admin see all. Security-critical leak coverage."""

    def test_reviewer_cannot_open_unassigned_application(self):
        app = self._make_app()  # assigned to nobody
        self._auth(REVIEWER)
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{app.id}/')
        self.assertEqual(r.status_code, 403)   # not theirs → blocked

    def test_reviewer_can_open_assigned_application(self):
        app = self._make_app()
        app.assigned_to = self.reviewer
        app.save(update_fields=['assigned_to'])
        self._auth(REVIEWER)
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{app.id}/')
        self.assertEqual(r.status_code, 200)

    def test_super_opens_any_application(self):
        app = self._make_app()
        self._auth(SUPER)
        self.assertEqual(
            self.client.get(f'/api/v1/admin/scholarship/applications/{app.id}/').status_code, 200)

    def test_partner_has_no_b40_access(self):
        org = PartnerOrganisation.objects.create(code='p1', name='Org One')
        PartnerAdmin.objects.create(supabase_user_id='partner-uid', role='partner',
                                    org=org, is_active=True, name='Partner', email='p@x.org')
        self._make_app()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("partner-uid")}')
        self.assertEqual(
            self.client.get('/api/v1/admin/scholarship/applications/').status_code, 403)

    def test_partner_sees_only_own_org_students(self):
        org_a = PartnerOrganisation.objects.create(code='a', name='Org A')
        org_b = PartnerOrganisation.objects.create(code='b', name='Org B')
        StudentProfile.objects.create(supabase_user_id='sa', name='Anita',
                                      referred_by_org=org_a, exam_type='spm')
        StudentProfile.objects.create(supabase_user_id='sb', name='Bala',
                                      referred_by_org=org_b, exam_type='spm')
        PartnerAdmin.objects.create(supabase_user_id='pa-uid', role='partner', org=org_a,
                                    is_active=True, name='PA', email='pa@x.org')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("pa-uid")}')
        names = [s['name'] for s in self.client.get('/api/v1/admin/students/').json()['students']]
        self.assertIn('ANITA', names)        # own org (names CAPS-normalised on save)
        self.assertNotIn('BALA', names)      # NEVER another org's student

    def test_reviewer_has_no_students_access(self):
        # Reviewers are individuals — the Students page is not theirs (even though the
        # 2 prod reviewers historically carry an org tag).
        self.reviewer.org = PartnerOrganisation.objects.create(code='r', name='Rev Org')
        self.reviewer.save(update_fields=['org'])
        self._auth(REVIEWER)
        self.assertEqual(self.client.get('/api/v1/admin/students/').status_code, 403)


class TestAssignment(PhaseCBase):
    # Assignment moved to the super-only audited endpoint (F7); see
    # test_assignment.py for the full coverage. These keep the Phase-C path green.
    def _ready_app(self):
        from django.utils import timezone
        app = self._make_app()
        ScholarshipApplication.objects.filter(pk=app.id).update(
            profile_completed_at=timezone.now(),   # no open queries -> ready
            status='profile_complete')             # ...and Completed: the assignable stage
        app.refresh_from_db()
        return app

    def test_super_can_assign(self):
        app = self._ready_app()
        self._auth(SUPER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/assign/',
            {'reviewer_id': self.reviewer.id}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.reviewer.id)

    def test_assign_unknown_admin_400(self):
        app = self._ready_app()
        self._auth(SUPER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/assign/',
            {'reviewer_id': 99999}, format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_non_super_cannot_assign(self):
        app = self._ready_app()
        self._auth(REVIEWER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/assign/',
            {'reviewer_id': self.reviewer.id}, format='json',
        )
        self.assertEqual(r.status_code, 403)


class TestInterview(PhaseCBase):
    def test_draft_does_not_advance_but_submit_does(self):
        app = self._complete(self._assigned_app(status='profile_complete'))
        self._auth(REVIEWER)
        # Saving a DRAFT must NOT advance the funnel (hotfix 2026-07-03: the Phase-C draft-save
        # advance was removed — it mis-fired on agenda edits/deletes once V3 folded the agenda in).
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/interview/',
            {'findings': {'household_size_one': {'verdict': 'resolved', 'rationale': 'ok'}},
             'rubric': {'financial_need': 5}, 'overall_note': 'Solid.'}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'profile_complete')     # draft save leaves status untouched
        # SUBMIT is the offline-interview fallback trigger → interviewing (the case is assigned).
        # (Findings-submit stops at 'interviewing'; 'interviewed' needs the full verify-accept.)
        r2 = self.client.post(f'/api/v1/admin/scholarship/applications/{app.id}/interview/submit/')
        self.assertEqual(r2.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')
        self.assertEqual(InterviewSession.objects.filter(application=app, status='submitted').count(), 1)

    def test_draft_save_on_unassigned_never_advances(self):
        # The exact hotfix bug (2026-07-03): a super saving/editing an interview draft during
        # early triage (before assignment) previously flipped profile_complete → interviewing
        # with no accountable owner. A draft save must now never move the status.
        app = self._complete(self._make_app(status='profile_complete'))   # UNASSIGNED
        self._auth(SUPER)
        url = f'/api/v1/admin/scholarship/applications/{app.id}/interview/'
        r = self.client.post(
            url, {'findings': {'household_size_one': {'verdict': 'resolved', 'rationale': 'ok'}}},
            format='json')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'profile_complete')
        # An "agenda edit/delete" is the SAME endpoint (re-save the draft) — still no advance.
        r2 = self.client.post(
            url, {'findings': {'household_size_one': {'verdict': 'resolved', 'rationale': 'revised'}}},
            format='json')
        self.assertEqual(r2.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'profile_complete')

    def test_reviewer_reopens_submitted_interview(self):
        # Submit, then the reviewer reopens to add a forgotten finding → un-submits +
        # reverts interviewed → interviewing (so Check 2 + the decision gate reopen too).
        app = self._complete(self._assigned_app(status='profile_complete'))
        self._auth(REVIEWER)
        self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/interview/',
            {'findings': {'household_size_one': {'verdict': 'resolved', 'rationale': 'ok'}}}, format='json')
        self.client.post(f'/api/v1/admin/scholarship/applications/{app.id}/interview/submit/')
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{app.id}/interview/reopen/')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')
        self.assertEqual(InterviewSession.objects.filter(application=app, status='submitted').count(), 0)
        self.assertEqual(InterviewSession.objects.filter(application=app, status='draft').count(), 1)

    def test_interview_reopen_blocked_after_decision(self):
        app = self._complete(self._assigned_app(status='interviewed'))
        app.verdict_decided_at = timezone.now()
        app.save(update_fields=['verdict_decided_at'])
        InterviewSession.objects.create(application=app, status='submitted', submitted_at=timezone.now())
        self._auth(REVIEWER)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{app.id}/interview/reopen/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'decision_recorded')

    def test_bad_verdict_rejected(self):
        app = self._complete(self._assigned_app(status='profile_complete'))
        self._auth(REVIEWER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/interview/',
            {'findings': {'x': {'verdict': 'nonsense', 'rationale': 'y'}}}, format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bad_findings')

    def test_rationale_too_long_rejected(self):
        app = self._complete(self._assigned_app(status='profile_complete'))
        self._auth(REVIEWER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/interview/',
            {'findings': {'x': {'verdict': 'resolved', 'rationale': 'z' * 200}}}, format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_viewer_cannot_write_interview(self):
        app = self._complete(self._assigned_app(status='profile_complete'))
        self._auth(VIEWER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/interview/',
            {'findings': {}}, format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_viewer_can_read_interview(self):
        app = self._make_app()
        self._auth(VIEWER)
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{app.id}/interview/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('agenda', r.json())

    def test_interview_agenda_surfaces_anomaly_codes(self):
        """TD audit 2026-06-14: the agenda is a projection of the anomaly codes, but the only
        test asserted the key exists. Seed a known anomaly and assert its code is surfaced — so
        a regression that drops/filters agenda codes is caught."""
        self.profile.household_size = 1     # → triggers the 'household_size_one' anomaly
        self.profile.save()
        app = self._make_app()
        self._auth(VIEWER)
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{app.id}/interview/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('household_size_one', r.json()['agenda'])

    def test_interview_agenda_full_does_not_echo_open_check2_items(self):
        """Owner 2026-07-06: open Check-2 queries / doc-requests are NOT echoed onto the interview
        agenda as 'carried-over' items (they live in Check-2 Outstanding). Motivation still stands."""
        from apps.scholarship.views_admin import interview_agenda_full
        from apps.scholarship.models import ResolutionItem
        app = self._make_app()
        ResolutionItem.objects.create(application=app, source='officer', code='officer_1',
                                      kind='doc', doc_type='salary_slip', status='open')
        agenda = interview_agenda_full(app)
        kinds = {(e['kind'], e['code']) for e in agenda}
        self.assertNotIn(('open_query', 'officer_1'), kinds)          # no carried-over echo
        self.assertFalse(any(e['kind'] == 'open_query' for e in agenda))
        self.assertTrue(any(e['kind'] == 'motivation' for e in agenda))  # standing motivation section
        # every entry is a well-formed {code, kind, params}
        for e in agenda:
            self.assertEqual(set(e), {'code', 'kind', 'params'})


class TestRequestInfo(PhaseCBase):
    @patch('apps.scholarship.views_admin.send_request_info_email')
    def test_request_info_stores_note_and_emails(self, mock_email):
        app = self._complete(self._assigned_app(status='profile_complete'))
        self._auth(REVIEWER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/request-info/',
            {'note': 'Please upload your latest payslip.'}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.info_request_note, 'Please upload your latest payslip.')
        self.assertIsNotNone(app.info_requested_at)
        self.assertEqual(app.status, 'profile_complete')  # unchanged
        mock_email.assert_called_once()

    def test_request_info_requires_note(self):
        app = self._assigned_app()
        self._auth(REVIEWER)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/request-info/',
            {'note': '  '}, format='json',
        )
        self.assertEqual(r.status_code, 400)


class TestRoleEndpoint(PhaseCBase):
    def test_role_returned(self):
        self._auth(REVIEWER)
        r = self.client.get('/api/v1/admin/role/')
        self.assertEqual(r.json()['role'], 'reviewer')

    def test_legacy_super_reported_as_super(self):
        self._auth(SUPER)
        r = self.client.get('/api/v1/admin/role/')
        self.assertEqual(r.json()['role'], 'super')


class TestStickyProfileCompleteRevert(PhaseCBase):
    """A profile_complete application that's edited back to incomplete (e.g. a
    compulsory doc removed) must roll back to 'shortlisted' — honest funnel."""

    def _confirmed(self):
        from django.utils import timezone
        app = self._complete(self._assigned_app(status='profile_complete'))
        app.profile_completed_at = timezone.now()
        app.save(update_fields=['profile_completed_at'])
        return app

    def test_helper_reverts_when_incomplete(self):
        from apps.scholarship.services import revert_if_profile_incomplete
        app = self._confirmed()
        ApplicantDocument.objects.filter(application=app, doc_type='results_slip').delete()
        self.assertTrue(revert_if_profile_incomplete(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')
        self.assertIsNone(app.profile_completed_at)

    def test_helper_noop_when_still_complete(self):
        from apps.scholarship.services import revert_if_profile_incomplete
        app = self._confirmed()
        self.assertFalse(revert_if_profile_incomplete(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'profile_complete')

    def test_helper_does_not_touch_interviewing(self):
        from apps.scholarship.services import revert_if_profile_incomplete
        app = self._make_app(status='interviewing')  # incomplete + past confirm
        self.assertFalse(revert_if_profile_incomplete(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')

    def test_deleting_compulsory_doc_reverts_via_api(self):
        app = self._confirmed()
        ic = ApplicantDocument.objects.get(application=app, doc_type='ic')
        self._auth(STUDENT)
        r = self.client.delete(f'/api/v1/scholarship/documents/{ic.id}/')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')
        self.assertIsNone(app.profile_completed_at)
