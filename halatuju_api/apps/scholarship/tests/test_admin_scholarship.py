"""Tests for the MyNadi admin API + AI profile drafting (Sprint 6a)."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, Referee, ScholarshipApplication, ScholarshipCohort, SponsorProfile,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADMIN = 'admin-uid'
STUDENT = 'student-uid'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAdminScholarship(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id=ADMIN, is_super_admin=True, is_active=True,
            name='Admin', email='admin@example.com',
        )
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='stud-prof', nric='030101-14-1234', name='Priya', school='SMK X',
            # academic + financial data is canonical on the profile
            grades={f'sub{i}': 'A' for i in range(10)},
            household_income=2500, receives_str=True,
        )
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted', bucket='A',
            aspirations='Become an auditor', justification='Low income family',
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_non_admin_forbidden(self):
        self._auth(STUDENT)
        r = self.client.get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(r.status_code, 403)

    def test_requires_auth(self):
        r = self.client.get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(r.status_code, 401)

    def test_list_sort_by_name_and_merit(self):
        # A second applicant with a weaker record (lower merit) + an earlier name.
        prof2 = StudentProfile.objects.create(
            supabase_user_id='stud2', nric='040202-14-2222', name='Aaron',
            grades={'sub0': 'C', 'sub1': 'C'}, household_income=3000)
        ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=prof2, status='shortlisted')
        self._auth(ADMIN)

        def names(params):
            r = self.client.get('/api/v1/admin/scholarship/applications/' + params)
            self.assertEqual(r.status_code, 200)
            return [a['name'] for a in r.json()['applications']]

        self.assertIn('AARON', names('?sort=name&dir=asc')[0])     # A before P
        self.assertIn('PRIYA', names('?sort=name&dir=desc')[0])    # reversed
        self.assertIn('PRIYA', names('?sort=merit&dir=desc')[0])   # all-A → highest merit
        self.assertIn('AARON', names('?sort=merit&dir=asc')[0])    # weakest → lowest merit

    def test_contact_submission_email(self):
        from django.core import mail
        from apps.scholarship.emails import send_contact_submission_admin_email
        self.assertTrue(send_contact_submission_admin_email(
            to_email='contact@halatuju.xyz', name='Asha', contact='asha@example.com',
            category='general', message='A question about B40.', created_at='2026-06-17 10:00'))
        m = mail.outbox[-1]
        self.assertEqual(m.to, ['contact@halatuju.xyz'])
        self.assertEqual(m.reply_to, ['asha@example.com'])     # email contact → reply-to
        self.assertIn('A question about B40.', m.body)
        self.assertIn('general', m.subject)
        # a phone (non-email) contact → no reply-to
        send_contact_submission_admin_email(
            to_email='contact@halatuju.xyz', name='Ben', contact='012-345 6789',
            category='bug', message='broken', created_at='2026-06-17')
        self.assertEqual(mail.outbox[-1].reply_to, [])

    def test_findings_accepts_deleted_verdict(self):
        # S4 review: a 'Deleted' interview talking point persists as a finding (then filters
        # off the agenda); validation must accept it. 'resolved' valid; bogus rejected.
        from apps.scholarship.views_admin import _validate_findings
        self.assertIsNone(_validate_findings({'device_in_funding': {'verdict': 'deleted', 'rationale': ''}}))
        self.assertIsNone(_validate_findings({'x': {'verdict': 'resolved', 'rationale': 'asked, fine'}}))
        self.assertIsNotNone(_validate_findings({'x': {'verdict': 'bogus'}}))

    def test_findings_accepts_empty_verdict_draft(self):
        # Regression: typing a one-line finding WITHOUT clicking a verdict button sends
        # verdict='' (the cockpit's natural action). Rejecting it 400'd the whole Save-draft
        # and LOST the reviewer's notes. An in-progress finding (just a rationale) must validate.
        from apps.scholarship.views_admin import _validate_findings
        self.assertIsNone(_validate_findings({'father_accident': {'verdict': '', 'rationale': 'in April, fine'}}))
        self.assertIsNone(_validate_findings({'x': {'verdict': '', 'rationale': ''}}))   # untouched entry, harmless
        self.assertIsNotNone(_validate_findings({'x': {'verdict': 'bogus'}}))            # still rejects nonsense

    # ── Check-2/Check-3 redesign S2: officer reviews student-answered caveats ──
    def _make_answered_caveat(self):
        from apps.scholarship.resolution import add_officer_item, resolve_item
        item = add_officer_item(
            self.app, kind='explanation', prompt="Please clarify your father's job.",
            admin_email='admin@example.com', fact='income',
        )
        resolve_item(item, text='He drives an e-hailing car part-time.', by='student')
        return item

    def test_cockpit_surfaces_student_answered_caveat(self):
        """A caveat the student has answered (resolved, by student) still surfaces in the
        admin Outstanding queue WITH its answer, so the officer can review it."""
        item = self._make_answered_caveat()
        self._auth(ADMIN)
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200)
        rows = {i['id']: i for i in r.json()['resolution_items']}
        self.assertIn(item.id, rows)
        self.assertEqual(rows[item.id]['status'], 'resolved')
        self.assertEqual(rows[item.id]['resolution_text'], 'He drives an e-hailing car part-time.')

    def test_accept_answer_restamps_officer_and_drops_from_queue(self):
        """Officer 'Accept' (resolve action) re-stamps resolved_by to the officer, so the
        answered item leaves the cockpit queue."""
        item = self._make_answered_caveat()
        self._auth(ADMIN)
        r = self.client.post(f'/api/v1/admin/scholarship/resolution-items/{item.id}/resolve/')
        self.assertEqual(r.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')
        self.assertNotEqual(item.resolved_by, 'student')
        self.assertNotIn(item.id, [i['id'] for i in r.json()['resolution_items']])

    def test_reopen_returns_answered_item_to_student(self):
        """Officer 'Ask again' (reopen) sends the query back to the student's to-do; the
        typed answer is preserved for the audit trail."""
        item = self._make_answered_caveat()
        self._auth(ADMIN)
        r = self.client.post(f'/api/v1/admin/scholarship/resolution-items/{item.id}/reopen/')
        self.assertEqual(r.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')
        self.assertEqual(item.resolved_by, '')
        self.assertIsNone(item.resolved_at)
        self.assertEqual(item.resolution_text, 'He drives an e-hailing car part-time.')

    def test_officer_doc_request_tags_member_in_params(self):
        """A per-person document request (e.g. the father's salary slip) stores the target
        member in params so the student's upload tags the right (doc_type, member) slot."""
        self._auth(ADMIN)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/resolution-items/',
            {'kind': 'doc', 'prompt': "Please upload father's salary slip.",
             'doc_type': 'salary_slip', 'fact': 'income', 'household_member': 'father'},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        from apps.scholarship.models import ResolutionItem
        item = ResolutionItem.objects.filter(
            application=self.app, kind='doc', doc_type='salary_slip').first()
        self.assertIsNotNone(item)
        self.assertEqual(item.params.get('household_member'), 'father')

    def test_officer_doc_request_rejects_bad_member(self):
        self._auth(ADMIN)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/resolution-items/',
            {'kind': 'doc', 'prompt': 'x', 'doc_type': 'salary_slip', 'household_member': 'cousin'},
            format='json',
        )
        self.assertEqual(r.status_code, 400)

    @override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
    def test_officer_request_resets_notify_stamp(self):
        """Raising a reviewer item re-notifies the student — but via the batched sweep,
        not a per-item email (a reviewer raises several in one sitting). The endpoint
        just resets the one-time notify stamp so `send_due_query_emails` re-sends ONE
        summary; a re-request after the student cleared everything re-notifies them."""
        from django.utils import timezone
        self.app.query_raised_notified_at = timezone.now()
        self.app.save(update_fields=['query_raised_notified_at'])
        self._auth(ADMIN)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/resolution-items/',
            {'kind': 'doc', 'prompt': 'Please upload your offer letter.',
             'doc_type': 'offer_letter', 'fact': 'pathway'},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertIsNone(self.app.query_raised_notified_at)

    @override_settings(CHECK2_STUDENT_QUERIES_ENABLED=False)
    def test_officer_request_keeps_stamp_when_flag_off(self):
        from django.utils import timezone
        stamp = timezone.now()
        self.app.query_raised_notified_at = stamp
        self.app.save(update_fields=['query_raised_notified_at'])
        self._auth(ADMIN)
        self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/resolution-items/',
            {'kind': 'doc', 'prompt': 'x', 'doc_type': 'offer_letter'}, format='json')
        self.app.refresh_from_db()
        self.assertEqual(self.app.query_raised_notified_at, stamp)

    # ── Check-2/Check-3 redesign S3: auto-draft the profile at the reviewer handoff ──
    @override_settings(CHECK2_AUTO_GENERATE=True)
    @patch('apps.scholarship.services.is_ready_for_assignment', return_value=True)
    @patch('apps.scholarship.profile_engine.generate_sponsor_profile',
           return_value={'markdown': 'Draft profile.', 'model_used': 'test'})
    def test_handoff_autodrafts_profile_when_flag_on(self, _gen, _ready):
        from apps.scholarship.services import assign_reviewer
        from apps.scholarship.models import SponsorProfile
        assign_reviewer(self.app, reviewer=self.admin, by_admin=self.admin)
        sp = SponsorProfile.objects.filter(application=self.app).first()
        self.assertIsNotNone(sp)
        self.assertEqual(sp.draft_markdown, 'Draft profile.')

    @override_settings(CHECK2_AUTO_GENERATE=False)
    @patch('apps.scholarship.services.is_ready_for_assignment', return_value=True)
    @patch('apps.scholarship.profile_engine.generate_sponsor_profile',
           return_value={'markdown': 'Draft profile.', 'model_used': 'test'})
    def test_handoff_no_autodraft_when_flag_off(self, _gen, _ready):
        from apps.scholarship.services import assign_reviewer
        from apps.scholarship.models import SponsorProfile
        assign_reviewer(self.app, reviewer=self.admin, by_admin=self.admin)
        self.assertFalse(SponsorProfile.objects.filter(application=self.app).exists())

    @override_settings(CHECK2_AUTO_GENERATE=True)
    @patch('apps.scholarship.services.is_ready_for_assignment', return_value=True)
    @patch('apps.scholarship.profile_engine.generate_sponsor_profile')
    def test_handoff_never_redrafts_existing_profile(self, gen, _ready):
        from apps.scholarship.services import assign_reviewer
        from apps.scholarship.models import SponsorProfile
        SponsorProfile.objects.create(
            application=self.app, draft_markdown='Existing.', generated_at=timezone.now())
        assign_reviewer(self.app, reviewer=self.admin, by_admin=self.admin)
        gen.assert_not_called()
        self.assertEqual(SponsorProfile.objects.get(application=self.app).draft_markdown, 'Existing.')

    # ── Check-2/Check-3 redesign S4: querying locks once the interview is concluded ──
    def test_raise_query_blocked_after_interview_concluded(self):
        from apps.scholarship.models import InterviewSession
        InterviewSession.objects.create(application=self.app, status='submitted')
        self._auth(ADMIN)
        r = self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/resolution-items/',
            {'kind': 'explanation', 'prompt': 'a late question'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json().get('error'), 'querying_closed')

    def test_reopen_blocked_after_interview_concluded(self):
        from apps.scholarship.models import InterviewSession
        item = self._make_answered_caveat()
        InterviewSession.objects.create(application=self.app, status='submitted')
        self._auth(ADMIN)
        r = self.client.post(f'/api/v1/admin/scholarship/resolution-items/{item.id}/reopen/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json().get('error'), 'querying_closed')

    @override_settings(CHECK2_AUTO_GENERATE=True)
    @patch('apps.scholarship.profile_engine.refine_sponsor_profile',
           return_value={'markdown': 'Final polished.', 'model_used': 'pro'})
    def test_submit_interview_autofinalises_when_flag_on(self, _refine):
        from apps.scholarship.models import SponsorProfile, InterviewSession
        from apps.scholarship.services import submit_interview
        SponsorProfile.objects.create(
            application=self.app, draft_markdown='Draft.', generated_at=timezone.now())
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='interviewing')
        self.app.refresh_from_db()
        sess = InterviewSession.objects.create(application=self.app, status='draft')
        submit_interview(sess)
        self.assertEqual(SponsorProfile.objects.get(application=self.app).final_markdown, 'Final polished.')

    @override_settings(CHECK2_AUTO_GENERATE=False)
    @patch('apps.scholarship.profile_engine.refine_sponsor_profile')
    def test_submit_interview_no_autofinalise_when_flag_off(self, refine):
        from apps.scholarship.models import SponsorProfile, InterviewSession
        from apps.scholarship.services import submit_interview
        SponsorProfile.objects.create(
            application=self.app, draft_markdown='Draft.', generated_at=timezone.now())
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='interviewing')
        self.app.refresh_from_db()
        sess = InterviewSession.objects.create(application=self.app, status='draft')
        submit_interview(sess)
        refine.assert_not_called()

    # TD audit 2026-06-14: the bare except in _maybe_autofinalise exists so a Gemini failure
    # NEVER breaks interview submission — but that guarantee was untested. These two cover it.
    @override_settings(CHECK2_AUTO_GENERATE=True)
    @patch('apps.scholarship.profile_engine.refine_sponsor_profile',
           return_value={'error': 'engine down'})
    def test_submit_interview_survives_autofinalise_engine_error(self, _refine):
        from apps.scholarship.models import SponsorProfile, InterviewSession
        from apps.scholarship.services import submit_interview
        SponsorProfile.objects.create(
            application=self.app, draft_markdown='Draft.', generated_at=timezone.now())
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='interviewing')
        self.app.refresh_from_db()
        sess = InterviewSession.objects.create(application=self.app, status='draft')
        advanced = submit_interview(sess)            # must still complete the submit
        self.assertTrue(advanced)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'interviewed')
        self.assertFalse(SponsorProfile.objects.get(application=self.app).final_markdown.strip())

    @override_settings(CHECK2_AUTO_GENERATE=True)
    @patch('apps.scholarship.profile_engine.refine_sponsor_profile',
           side_effect=RuntimeError('boom'))
    def test_submit_interview_survives_autofinalise_exception(self, _refine):
        from apps.scholarship.models import SponsorProfile, InterviewSession
        from apps.scholarship.services import submit_interview
        SponsorProfile.objects.create(
            application=self.app, draft_markdown='Draft.', generated_at=timezone.now())
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='interviewing')
        self.app.refresh_from_db()
        sess = InterviewSession.objects.create(application=self.app, status='draft')
        advanced = submit_interview(sess)            # must NOT raise
        self.assertTrue(advanced)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'interviewed')
        self.assertFalse(SponsorProfile.objects.get(application=self.app).final_markdown.strip())

    def test_admin_list(self):
        self._auth(ADMIN)
        r = self.client.get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['total_count'], 1)
        self.assertEqual(r.json()['applications'][0]['name'], 'PRIYA')  # names upper-cased for admin

    def test_admin_list_has_source_and_merit(self):
        """The list table's Source (referring org) + Merit columns. Merit is computed live
        per row via the same helper the detail card uses (no stored column)."""
        StudentProfile.objects.filter(pk=self.profile.pk).update(
            referral_source='smc', coq_score=7, stream_subjects=[],
            grades={'bm': 'A', 'eng': 'A', 'math': 'A', 'hist': 'A',
                    'phy': 'A', 'chem': 'A', 'bio': 'A', 'addmath': 'A'},
        )
        self._auth(ADMIN)
        item = self.client.get('/api/v1/admin/scholarship/applications/').json()['applications'][0]
        self.assertEqual(item['referral_source'], 'smc')
        self.assertGreater(item['merit_score'], 85)

    def test_admin_list_filter_bucket(self):
        self._auth(ADMIN)
        r = self.client.get('/api/v1/admin/scholarship/applications/?bucket=B')
        self.assertEqual(r.json()['total_count'], 0)

    def test_admin_list_filter_source(self):
        StudentProfile.objects.filter(pk=self.profile.pk).update(referral_source='smc')
        self._auth(ADMIN)
        self.assertEqual(
            self.client.get('/api/v1/admin/scholarship/applications/?source=smc').json()['total_count'], 1)
        self.assertEqual(
            self.client.get('/api/v1/admin/scholarship/applications/?source=pptm').json()['total_count'], 0)

    def test_admin_detail(self):
        self._auth(ADMIN)
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['aspirations'], 'Become an auditor')
        self.assertEqual(body['name'], 'PRIYA')  # names upper-cased for admin
        self.assertIn('documents', body)
        self.assertIn('referees', body)
        self.assertIsNone(body['sponsor_profile'])

    def test_admin_detail_name_email_and_merit_history(self):
        """Full name from the declaration signature (not the Google handle); email
        falls back to the login/notify email; merit counts History ('hist' key)."""
        StudentProfile.objects.filter(pk=self.profile.pk).update(
            name='krisha1204', contact_email='', coq_score=7, stream_subjects=[],
            grades={'bm': 'A', 'eng': 'A', 'math': 'A', 'hist': 'A',
                    'phy': 'A', 'chem': 'A', 'bio': 'A', 'addmath': 'A'},
        )
        ScholarshipApplication.objects.filter(pk=self.app.id).update(
            declaration_name='SHARMILA A/P SANGGAR', notify_email='login@example.com',
        )
        self._auth(ADMIN)
        body = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/').json()
        # declaration signature wins over the profile handle
        self.assertEqual(body['name'], 'SHARMILA A/P SANGGAR')
        # email falls back to the captured login email when contact_email is blank
        self.assertEqual(body['notify_email'], 'login@example.com')
        # all-A core (incl. History via the hist->history rename) → high merit
        self.assertGreater(body['merit_score'], 85)

    def test_admin_detail_verified_email(self):
        """The admin card shows only a VERIFIED email: a verified contact_email when
        set, else the verified Google login email — never an unverified typed one."""
        self._auth(ADMIN)
        # 1) A verified contact email is shown directly.
        StudentProfile.objects.filter(pk=self.profile.pk).update(
            contact_email='me@verified.com', contact_email_verified=True)
        body = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/').json()
        self.assertEqual(body['verified_email'], 'me@verified.com')
        # 2) An unverified typed contact email is NOT shown — it falls back to the
        #    verified login email looked up from Supabase auth.users.
        StudentProfile.objects.filter(pk=self.profile.pk).update(
            contact_email='typed@unverified.com', contact_email_verified=False)
        with patch('apps.courses.views_admin._fetch_auth_data',
                   return_value={'stud-prof': {'email': 'login@gmail.com', 'last_sign_in': ''}}):
            body = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/').json()
        self.assertEqual(body['verified_email'], 'login@gmail.com')
        self.assertNotEqual(body['verified_email'], 'typed@unverified.com')

    def test_admin_detail_complete_profile_fields(self):
        """Complete-profile view: every /apply field the student entered is in the
        admin detail response (contact/family/academic/plans/support/story)."""
        # Populate the full set on the profile + application.
        StudentProfile.objects.filter(pk=self.profile.pk).update(
            contact_phone='012-3456789', contact_email='priya@example.com',
            preferred_state='Melaka', preferred_call_language='ta',
            referral_source='cumig', household_size=5,
            guardians=[{'name': 'Mr Priya Sr', 'phone': '013-1112222'}],
            muet_band=4, coq_score=8.0, stpm_grades={}, spm_prereq_grades={},
        )
        ScholarshipApplication.objects.filter(pk=self.app.id).update(
            help_university='yes', help_scholarship='unsure', anything_else='Please help.',
            consent_to_contact=True, declaration_name='Priya', intends_tertiary_2026=True,
            pathway_certainty='sure', field_of_study='accounting',
            first_in_family=True, parents_occupation='Lorry driver',
            siblings_studying_count=2, family_context='Father ill', daily_life='Help at home',
        )
        self._auth(ADMIN)
        body = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/').json()
        # Class-B fields now exposed:
        for key in ('contact_phone', 'contact_email', 'preferred_state', 'preferred_call_language',
                    'referral_source', 'guardians', 'household_size', 'receives_jkm',
                    'muet_band', 'coq_score', 'grades', 'stpm_grades',
                    'consent_to_contact', 'declaration_name', 'declared_at',
                    'first_in_family', 'parents_occupation', 'siblings_studying_count',
                    'family_context', 'daily_life',
                    'help_university', 'help_scholarship', 'anything_else',
                    'pathway_certainty', 'field_of_study', 'intends_tertiary_2026'):
            self.assertIn(key, body, f'{key} missing from admin detail')
        self.assertEqual(body['contact_phone'], '012-3456789')
        self.assertEqual(body['preferred_state'], 'Melaka')
        self.assertEqual(body['guardians'][0]['name'], 'Mr Priya Sr')
        self.assertEqual(body['siblings_studying_count'], 2)
        self.assertTrue(body['consent_to_contact'])
        self.assertEqual(body['help_university'], 'yes')

    @patch('apps.scholarship.profile_engine.generate_sponsor_profile',
           return_value={'markdown': '# Priya\nA strong candidate.', 'model_used': 'gemini-2.5-flash'})
    def test_generate_profile(self, _mock):
        self._auth(ADMIN)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/generate-profile/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['status'], 'draft')
        self.assertIn('strong candidate', body['draft_markdown'])
        self.assertEqual(body['model_used'], 'gemini-2.5-flash')

    @patch('apps.scholarship.profile_engine.generate_sponsor_profile', return_value={'error': 'AI down'})
    def test_generate_profile_ai_error(self, _mock):
        self._auth(ADMIN)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/generate-profile/')
        self.assertEqual(r.status_code, 503)

    def test_edit_and_publish(self):
        SponsorProfile.objects.create(application=self.app, draft_markdown='draft text')
        self._auth(ADMIN)
        r = self.client.put(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/profile/',
            {'edited_markdown': 'edited text', 'status': 'approved'}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['edited_markdown'], 'edited text')
        self.assertEqual(r.json()['status'], 'approved')
        self.assertEqual(r.json()['current_markdown'], 'edited text')
        r2 = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/publish/')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['status'], 'published')

    def test_publish_nothing_400(self):
        SponsorProfile.objects.create(application=self.app)  # empty draft + edited
        self._auth(ADMIN)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/publish/')
        self.assertEqual(r.status_code, 400)

    # ── S11a: verify & accept ──────────────────────────────────────────────
    def _verify_url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/verify-accept/'

    def _complete_app(self):
        """Phase C: the accept-gate now hard-requires a complete profile.
        Satisfy all 7 completeness parts on self.app."""
        from apps.scholarship.models import Consent, FundingNeed
        self.profile.student_signals = {'field_interest': {'it': 5}}
        self.profile.address = 'No. 1 Jalan ABC'
        self.profile.postal_code = '62100'
        self.profile.city = 'Putrajaya'
        self.profile.save()
        # Check-3 audit gate: a case is only closeable once the reviewer has RECORDED
        # their verdict (audited the AI). A complete, accept-ready fixture sets it.
        ScholarshipApplication.objects.filter(pk=self.app.id).update(
            plans='Study hard', daily_life='Help at home', fears='Worried about fees',
            income_route='str', income_earner='father',   # gate v2: STR route, father earner
            # 2026-06 redesign: the structured family roster is compulsory.
            father_name='AROON', father_occupation='driver',
            mother_name='KOMATHI', mother_occupation='homemaker',
            siblings_in_school=1, siblings_in_tertiary=0,
            verdict_decided_at=timezone.now())
        FundingNeed.objects.create(application=self.app, categories=['living'], programme_months=36)
        for dt in ('ic', 'results_slip', 'offer_letter', 'parent_ic', 'str'):
            ApplicantDocument.objects.create(application=self.app, doc_type=dt, storage_path=f'x/{dt}')
        Consent.objects.create(application=self.app, version='t', is_active=True)

    def test_verify_accept_locks_nric_and_advances(self):
        self._complete_app()
        self._auth(ADMIN)
        r = self.client.post(
            self._verify_url(),
            {'checklist': {'nric': True, 'name': True, 'results': True, 'document': True}},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['status'], 'accepted')
        self.assertTrue(body['nric_verified'])
        self.assertEqual(body['verified_by'], 'admin@example.com')
        self.assertIsNotNone(body['verified_at'])
        self.assertTrue(body['verify_checklist']['document'])
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.nric_verified)  # NRIC is now locked

    def test_verify_accept_requires_recorded_verdict(self):
        # Check-3 audit gate: complete profile but the reviewer never recorded their
        # verdict → 400 verdict_not_recorded (hard, no override). NRIC stays unlocked.
        self._complete_app()
        ScholarshipApplication.objects.filter(pk=self.app.id).update(verdict_decided_at=None)
        self._auth(ADMIN)
        r = self.client.post(self._verify_url())
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json().get('code'), 'verdict_not_recorded')
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.nric_verified)

    def test_verify_accept_only_shortlisted(self):
        ScholarshipApplication.objects.filter(pk=self.app.id).update(status='submitted')
        self._auth(ADMIN)
        r = self.client.post(self._verify_url())
        self.assertEqual(r.status_code, 400)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.nric_verified)

    def test_verify_accept_nric_conflict(self):
        # Soft-NRIC: another profile already has this NRIC verified → 409 (TD-054).
        # Must be complete to pass the Phase C accept-gate and reach the NRIC check.
        self._complete_app()
        StudentProfile.objects.create(
            supabase_user_id='other-uid', nric='030101-14-1234', nric_verified=True,
        )
        self._auth(ADMIN)
        r = self.client.post(self._verify_url())
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json().get('code'), 'nric_conflict')
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.nric_verified)

    def test_verify_accept_requires_admin(self):
        self._auth(STUDENT)
        r = self.client.post(self._verify_url())
        self.assertEqual(r.status_code, 403)

    def test_mentoring_toggle(self):
        self._auth(ADMIN)
        r = self.client.patch(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/',
            {'mentoring_candidate': True}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['mentoring_candidate'])
        self.app.refresh_from_db()
        self.assertTrue(self.app.mentoring_candidate)

    # ── S5b: admin records the referee at verify-&-accept ───────────────────
    def _referees_url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/referees/'

    def test_admin_list_referees_empty(self):
        self._auth(ADMIN)
        r = self.client.get(self._referees_url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['referees'], [])

    def test_admin_add_referee(self):
        self._auth(ADMIN)
        r = self.client.post(
            self._referees_url(),
            {'name': 'Cikgu Devi', 'role': 'teacher', 'relationship': 'class teacher',
             'phone': '0123456789', 'email': 'devi@smkx.edu.my'},
            format='json',
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['name'], 'Cikgu Devi')
        self.assertEqual(Referee.objects.filter(application=self.app).count(), 1)

    def test_admin_add_referee_requires_name(self):
        self._auth(ADMIN)
        r = self.client.post(self._referees_url(), {'role': 'teacher'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_admin_list_after_add(self):
        Referee.objects.create(application=self.app, name='Mr Tan', role='counsellor')
        self._auth(ADMIN)
        r = self.client.get(self._referees_url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['referees']), 1)
        self.assertEqual(r.json()['referees'][0]['name'], 'Mr Tan')

    def test_admin_delete_referee(self):
        ref = Referee.objects.create(application=self.app, name='Mr Tan')
        self._auth(ADMIN)
        r = self.client.delete(f'{self._referees_url()}{ref.id}/')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Referee.objects.filter(pk=ref.id).exists())

    def test_admin_delete_referee_wrong_application_404(self):
        """A referee id that belongs to a different application is not deletable here."""
        other_cohort = ScholarshipCohort.objects.create(code='c2', name='B40-2', year=2027)
        other_app = ScholarshipApplication.objects.create(
            cohort=other_cohort, profile=self.profile, status='shortlisted',
        )
        ref = Referee.objects.create(application=other_app, name='Someone Else')
        self._auth(ADMIN)
        r = self.client.delete(f'{self._referees_url()}{ref.id}/')
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Referee.objects.filter(pk=ref.id).exists())

    def test_referee_endpoints_require_admin(self):
        self._auth(STUDENT)
        self.assertEqual(self.client.get(self._referees_url()).status_code, 403)
        self.assertEqual(
            self.client.post(self._referees_url(), {'name': 'X'}, format='json').status_code, 403,
        )

    # ── S13: admin re-runs Vision OCR on an existing IC document ────────────
    def _rerun_vision_url(self, doc_id):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/documents/{doc_id}/re-run-vision/'

    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_admin_rerun_vision_on_ic(self, mock_vision):
        from django.utils import timezone as _tz

        def update_doc(doc):
            doc.vision_nric = '030101-14-1234'
            doc.vision_name = 'PRIYA D/O KRISHNAN'
            doc.vision_run_at = _tz.now()
            doc.vision_error = ''
            doc.save(update_fields=['vision_nric', 'vision_name', 'vision_run_at', 'vision_error'])
            return {'nric': '030101-14-1234', 'name': 'PRIYA D/O KRISHNAN', 'error': None}
        mock_vision.side_effect = update_doc
        ic = ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='ic/abc')
        self._auth(ADMIN)
        r = self.client.post(self._rerun_vision_url(ic.id))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(mock_vision.called)
        body = r.json()
        self.assertEqual(body['vision_nric'], '030101-14-1234')
        self.assertEqual(body['vision_name'], 'PRIYA D/O KRISHNAN')

    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_admin_rerun_vision_on_parent_ic(self, mock_vision):
        # Regression: parent-IC re-run used to 400 ("Could not re-run Vision").
        mock_vision.return_value = {'nric': '', 'name': '', 'error': None}
        pic = ApplicantDocument.objects.create(application=self.app, doc_type='parent_ic', storage_path='pic/abc')
        self._auth(ADMIN)
        r = self.client.post(self._rerun_vision_url(pic.id))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(mock_vision.called)

    @patch('apps.scholarship.vision.run_field_extraction_for_document')
    @patch('apps.scholarship.vision.run_vision_match_for_document')
    @patch('apps.scholarship.vision.ocr_document')
    def test_admin_rerun_vision_on_results_slip(self, mock_ocr, mock_match, mock_extract):
        # Now SUPPORTED: re-run extracts the GRADES off the results slip (S2), forced
        # past the throttle. (Previously this 400'd — re-run was IC-only.)
        mock_ocr.return_value = {}
        mock_match.return_value = {'name_match': 'found', 'address_match': ''}
        results = ApplicantDocument.objects.create(application=self.app, doc_type='results_slip', storage_path='r/abc')
        self._auth(ADMIN)
        r = self.client.post(self._rerun_vision_url(results.id))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(mock_match.called)
        self.assertTrue(mock_extract.called)   # the grade read

    @patch('apps.scholarship.vision.ocr_document')
    def test_admin_rerun_vision_on_statement_of_intent(self, mock_ocr):
        # P1 (Check 2): the letter of intent re-reads to plain text in vision_fields['text'].
        mock_ocr.return_value = {'text': 'I want to become a teacher because...', 'error': ''}
        loi = ApplicantDocument.objects.create(
            application=self.app, doc_type='statement_of_intent', storage_path='loi/abc')
        self._auth(ADMIN)
        r = self.client.post(self._rerun_vision_url(loi.id))
        self.assertEqual(r.status_code, 200)
        loi.refresh_from_db()
        self.assertEqual(loi.vision_fields.get('text'), 'I want to become a teacher because...')
        self.assertEqual(loi.vision_fields.get('student_verdict'), 'read')

    def test_admin_rerun_vision_rejects_unsupported_type(self):
        # A type with no automatic check (e.g. guardianship_letter) still 400s.
        doc = ApplicantDocument.objects.create(application=self.app, doc_type='guardianship_letter', storage_path='g/abc')
        self._auth(ADMIN)
        r = self.client.post(self._rerun_vision_url(doc.id))
        self.assertEqual(r.status_code, 400)

    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_rerun_vision_forbidden_for_non_reviewer(self, mock_vision):
        """TD audit 2026-06-14: re-running a (billable) document read is a reviewer-gated WRITE.
        A read-only 'admin' role has full B40 scope but is NOT a reviewer, so it must be refused —
        this endpoint previously only scope-checked, leaving the role gate off."""
        PartnerAdmin.objects.create(
            supabase_user_id='ro-admin-uid', role='admin', is_active=True,
            name='ReadOnly', email='ro@example.com')
        ic = ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='ic/ro')
        self._auth('ro-admin-uid')
        r = self.client.post(self._rerun_vision_url(ic.id))
        self.assertEqual(r.status_code, 403)
        self.assertFalse(mock_vision.called)

    def test_admin_rerun_vision_404_for_wrong_application(self):
        other_cohort = ScholarshipCohort.objects.create(code='c3', name='B40-3', year=2028)
        other_app = ScholarshipApplication.objects.create(cohort=other_cohort, profile=self.profile, status='shortlisted')
        ic = ApplicantDocument.objects.create(application=other_app, doc_type='ic', storage_path='ic/zzz')
        self._auth(ADMIN)
        r = self.client.post(self._rerun_vision_url(ic.id))
        self.assertEqual(r.status_code, 404)

    def test_admin_rerun_vision_requires_admin(self):
        ic = ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='ic/abc')
        self._auth(STUDENT)
        r = self.client.post(self._rerun_vision_url(ic.id))
        self.assertEqual(r.status_code, 403)
