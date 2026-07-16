"""Tests for in-app interview scheduling (propose → book → reschedule → cancel),
the reminder cron, the booking emails, and endpoint permissions.

Google Meet is mocked everywhere (``apps.scholarship.meeting.create_event`` etc.) —
never a live Google call in CI.
"""
from datetime import timedelta
from unittest.mock import patch

import jwt
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import scheduling
from apps.scholarship.models import InterviewSlot, ReviewerProfile, ScholarshipApplication, ScholarshipCohort, WhatsAppMessage

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(INTERVIEW_SCHEDULING_ENABLED=True)
class SchedulingServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Rohini', email='rohini@example.com')
        cls.other_reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev2-uid', role='reviewer', is_active=True,
            name='Bala', email='bala@example.com')
        cls.viewer = PartnerAdmin.objects.create(
            supabase_user_id='view-uid', role='admin', is_active=True,
            name='Viewer', email='viewer@example.com')
        # A senior 'qc' reviewer — assignable + reviews its assigned cases (2026-07). Must be
        # able to propose interview times on a case assigned to it (regression: a stale role
        # tuple in scheduling._can_review blocked this with 'not_reviewer' — 2026-07-10).
        cls.qc = PartnerAdmin.objects.create(
            supabase_user_id='qc-uid', role='qc', is_active=True,
            name='Suresh', email='qc@example.com')
        # A 'partner' (org rep) is never a review target — the genuine not_reviewer case.
        cls.partner = PartnerAdmin.objects.create(
            supabase_user_id='partner-uid', role='partner', is_active=True,
            name='Partner', email='partner@example.com')
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='stud', nric='030101-14-1234', name='Priya')

    def setUp(self):
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='interviewing',
            notify_email='priya@example.com', assigned_to=self.reviewer)

    def _future(self, **kw):
        return timezone.now() + timedelta(**kw)

    # ── propose ──────────────────────────────────────────────────────────────
    def test_propose_creates_active_slots(self):
        slots = scheduling.propose_slots(
            self.app, reviewer=self.reviewer,
            starts=[self._future(days=3), self._future(days=4)])
        self.assertEqual(len(slots), 2)
        self.assertEqual(InterviewSlot.objects.filter(application=self.app, is_active=True).count(), 2)

    def test_propose_emails_student_to_pick_a_time(self):
        # Proposing times must notify the student to come book — otherwise the in-app
        # scheduler is invisible to them (runs parallel to the assignment email).
        mail.outbox.clear()
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=3)])
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['priya@example.com'])
        self.assertIn('Pick a time slot', msg.subject)
        self.assertIn('/scholarship/application', msg.body)            # link in the text fallback
        self.assertEqual(msg.reply_to, ['interview@halatuju.xyz'])     # replies route to interview@
        # HTML primary + plain-text fallback.
        self.assertEqual(len(msg.alternatives), 1)
        html, mime = msg.alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('Choose your interview time', html)             # the button label
        self.assertIn('/scholarship/application"', html)              # button href

    # ── status advances when the interview process starts ─────────────────────
    def _pc_app(self, uid='stud-pc'):
        p = StudentProfile.objects.create(
            supabase_user_id=uid, nric='990101-14-9999', name='Devi')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='profile_complete',
            notify_email=f'{uid}@example.com', assigned_to=self.reviewer)

    def test_propose_advances_profile_complete_to_interviewing(self):
        # The interview process begins at propose (the first interview@ email) — the status
        # must follow, not wait for the reviewer to open the capture form.
        app = self._pc_app()
        scheduling.propose_slots(app, reviewer=self.reviewer, starts=[self._future(days=3)])
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')

    def test_propose_never_pulls_a_decided_case_back(self):
        # Re-proposing (e.g. a reschedule) on a recommended case must NOT revert it to interviewing.
        app = self._pc_app(uid='stud-acc')
        app.status = 'recommended'
        app.save(update_fields=['status'])
        scheduling.propose_slots(app, reviewer=self.reviewer, starts=[self._future(days=3)])
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')

    # ── proposing requires an assignment (hotfix 2026-07-03; closes the super bypass) ─────────
    def _unassigned_pc_app(self, uid='stud-unassigned'):
        p = StudentProfile.objects.create(supabase_user_id=uid, nric='990202-14-8888', name='Nita')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='profile_complete',
            notify_email=f'{uid}@example.com')   # NO assigned_to

    def test_propose_refused_on_unassigned_application(self):
        # Slots are the assigned reviewer's calendar — an UNASSIGNED app can't have times
        # proposed, and (being the forward trigger) must not flip it into the funnel with no
        # accountable owner. Refused for EVERYONE, including a super (closes the bypass).
        superadmin = PartnerAdmin.objects.create(
            supabase_user_id='super-sched', is_super_admin=True, is_active=True,
            name='Boss', email='boss-sched@example.com')
        app = self._unassigned_pc_app()
        for who in (superadmin, self.reviewer):
            with self.assertRaises(scheduling.SchedulingError) as ctx:
                scheduling.propose_slots(app, reviewer=who, starts=[self._future(days=3)])
            self.assertEqual(str(ctx.exception), 'not_assigned')
        app.refresh_from_db()
        self.assertEqual(app.status, 'profile_complete')                 # never advanced
        self.assertFalse(InterviewSlot.objects.filter(application=app).exists())

    @override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_propose_endpoint_returns_400_not_assigned_for_super(self):
        # End-to-end: the super's propose POST on an unassigned app → 400 not_assigned, no change.
        PartnerAdmin.objects.create(
            supabase_user_id='super-ep', is_super_admin=True, is_active=True,
            name='Boss', email='boss-ep@example.com')
        app = self._unassigned_pc_app(uid='stud-ep')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("super-ep")}')
        # A VALID slot (10:00 MYT, 30-min boundary, >24h out) so the endpoint's slot-window
        # checks pass and we actually reach the assignment guard.
        from datetime import timezone as _dtz
        myt = _dtz(timedelta(hours=8))
        slot = (timezone.now() + timedelta(days=3)).astimezone(myt).replace(
            hour=10, minute=0, second=0, microsecond=0)
        r = client.post(f'/api/v1/admin/scholarship/applications/{app.id}/interview-slots/',
                        {'slots': [slot.isoformat()]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'not_assigned')
        app.refresh_from_db()
        self.assertEqual(app.status, 'profile_complete')

    def test_interviewing_invariant_holds_for_both_legit_paths(self):
        # INVARIANT: status=='interviewing' ⇒ assigned_to set AND (active slots OR a submitted
        # session). The two legit entry paths (propose; offline submit) must each satisfy it.
        from apps.scholarship.models import InterviewSession
        from apps.scholarship.services import submit_interview
        # propose path
        a1 = self._pc_app(uid='inv-propose')
        scheduling.propose_slots(a1, reviewer=self.reviewer, starts=[self._future(days=3)])
        a1.refresh_from_db()
        self.assertEqual(a1.status, 'interviewing')
        self.assertIsNotNone(a1.assigned_to_id)
        self.assertTrue(InterviewSlot.objects.filter(application=a1, is_active=True).exists())
        # offline-submit path
        a2 = self._pc_app(uid='inv-submit')
        submit_interview(InterviewSession.objects.create(application=a2, status='draft'))
        a2.refresh_from_db()
        self.assertEqual(a2.status, 'interviewing')
        self.assertIsNotNone(a2.assigned_to_id)
        self.assertTrue(a2.interview_sessions.filter(status='submitted').exists())

    # ── WhatsApp "times proposed — please pick one" nudge (roadmap S2 / TD-138) ──
    _SANDBOX = 'whatsapp:+14155238886'
    _REAL = 'whatsapp:+19162597009'

    def _opt_in(self):
        self.profile.contact_phone = '012-345 6789'
        self.profile.whatsapp_opt_in = True
        self.profile.save(update_fields=['contact_phone', 'whatsapp_opt_in'])

    @override_settings(WHATSAPP_ENABLED=True, TWILIO_ACCOUNT_SID='AC', TWILIO_AUTH_TOKEN='t',
                       TWILIO_WHATSAPP_FROM=_SANDBOX)
    @patch('apps.scholarship.whatsapp._post_to_twilio', return_value=('SM1', 'queued', ''))
    def test_proposed_nudge_freetexts_in_sandbox(self, _post):
        self._opt_in()
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=3)])
        msgs = WhatsAppMessage.objects.filter(application=self.app, kind='interview_proposed')
        self.assertEqual(msgs.count(), 1)
        self.assertIn('/scholarship/application', msgs.first().body)

    @override_settings(WHATSAPP_ENABLED=True, TWILIO_ACCOUNT_SID='AC', TWILIO_AUTH_TOKEN='t',
                       TWILIO_WHATSAPP_FROM=_REAL)  # real sender, NO proposed-template SID set
    @patch('apps.scholarship.whatsapp._post_to_twilio', return_value=('SM1', 'queued', ''))
    def test_proposed_nudge_dark_on_real_sender_without_template(self, _post):
        self._opt_in()
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=3)])
        self.assertEqual(
            WhatsAppMessage.objects.filter(application=self.app, kind='interview_proposed').count(), 0)
        _post.assert_not_called()   # never attempts a forbidden free-text on a real sender

    @override_settings(WHATSAPP_ENABLED=True, TWILIO_ACCOUNT_SID='AC', TWILIO_AUTH_TOKEN='t',
                       TWILIO_WHATSAPP_FROM=_REAL, TWILIO_WHATSAPP_PROPOSED_CONTENT_SID='HXproposed')
    @patch('apps.scholarship.whatsapp._post_to_twilio', return_value=('SM1', 'queued', ''))
    def test_proposed_nudge_uses_template_in_prod(self, _post):
        self._opt_in()
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=3)])
        self.assertEqual(
            WhatsAppMessage.objects.filter(application=self.app, kind='interview_proposed').count(), 1)
        _post.assert_called_once()

    @override_settings(WHATSAPP_ENABLED=True, TWILIO_ACCOUNT_SID='AC', TWILIO_AUTH_TOKEN='t',
                       TWILIO_WHATSAPP_FROM=_SANDBOX)
    @patch('apps.scholarship.whatsapp._post_to_twilio', return_value=('SM1', 'queued', ''))
    def test_proposed_nudge_skipped_when_opted_out(self, _post):
        self.profile.contact_phone = '012-345 6789'
        self.profile.whatsapp_opt_in = False
        self.profile.save(update_fields=['contact_phone', 'whatsapp_opt_in'])
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=3)])
        self.assertEqual(
            WhatsAppMessage.objects.filter(application=self.app, kind='interview_proposed').count(), 0)

    @override_settings(WHATSAPP_ENABLED=True, TWILIO_ACCOUNT_SID='AC', TWILIO_AUTH_TOKEN='t',
                       TWILIO_WHATSAPP_FROM=_REAL,
                       TWILIO_WHATSAPP_PROPOSED_CONTENT_SID_EN='HXpen',
                       TWILIO_WHATSAPP_PROPOSED_CONTENT_SID_BM='HXpbm')
    @patch('apps.scholarship.emails.english_only_email', return_value=True)
    @patch('apps.scholarship.whatsapp._post_to_twilio', return_value=('SM1', 'queued', ''))
    def test_proposed_nudge_picks_EN_variant_for_english_only(self, post, _eo):
        self._opt_in()
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=3)])
        self.assertEqual(post.call_args[0][5], 'HXpen')   # content_sid

    @override_settings(WHATSAPP_ENABLED=True, TWILIO_ACCOUNT_SID='AC', TWILIO_AUTH_TOKEN='t',
                       TWILIO_WHATSAPP_FROM=_REAL,
                       TWILIO_WHATSAPP_PROPOSED_CONTENT_SID_EN='HXpen',
                       TWILIO_WHATSAPP_PROPOSED_CONTENT_SID_BM='HXpbm')
    @patch('apps.scholarship.emails.english_only_email', return_value=False)
    @patch('apps.scholarship.whatsapp._post_to_twilio', return_value=('SM1', 'queued', ''))
    def test_proposed_nudge_picks_BM_variant_otherwise(self, post, _eo):
        self._opt_in()
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=3)])
        self.assertEqual(post.call_args[0][5], 'HXpbm')   # content_sid

    def test_propose_rejects_unassigned_reviewer(self):
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.propose_slots(self.app, reviewer=self.other_reviewer,
                                     starts=[self._future(days=3)])
        self.assertEqual(str(cm.exception), 'not_assigned')

    def test_propose_rejects_non_reviewer(self):
        # A 'partner' is not a review target → not_reviewer (an 'admin'/'qc' IS one, and is only
        # scoped out by the assignment check, so they'd raise not_assigned instead — see below).
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.propose_slots(self.app, reviewer=self.partner,
                                     starts=[self._future(days=3)])
        self.assertEqual(str(cm.exception), 'not_reviewer')

    def test_propose_allowed_for_assigned_qc(self):
        # Regression (2026-07-10): a 'qc' reviewer assigned to the case could not propose times —
        # scheduling._can_review omitted 'qc'. An assigned qc must be able to propose.
        self.app.assigned_to = self.qc
        self.app.save(update_fields=['assigned_to'])
        slots = scheduling.propose_slots(self.app, reviewer=self.qc,
                                         starts=[self._future(days=3)])
        self.assertEqual(len(slots), 1)

    def test_scheduling_review_roles_match_services(self):
        # Guard against the two _can_review copies drifting again: the interview surface must accept
        # exactly the same review roles as the rest of the review/assignment surface.
        from apps.scholarship import services
        for role in ('reviewer', 'super', 'admin', 'qc', 'org_admin', 'partner', ''):
            a = PartnerAdmin(role=role, is_active=True)
            self.assertEqual(scheduling._can_review(a), services._can_review(a),
                             f'role {role!r} disagrees between scheduling and services')

    def test_propose_drops_past_times_and_needs_one_future(self):
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                     starts=[self._future(days=-1)])
        self.assertEqual(str(cm.exception), 'no_future_slots')

    def test_slot_in_window_rule(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        myt = ZoneInfo('Asia/Kuala_Lumpur')
        def at(h, m):
            return datetime(2026, 6, 22, h, m, tzinfo=myt)
        # in-window, on 30-min boundary
        self.assertTrue(scheduling.slot_in_window(at(8, 0)))
        self.assertTrue(scheduling.slot_in_window(at(9, 30)))
        self.assertTrue(scheduling.slot_in_window(at(21, 30)))
        # off-boundary minutes
        self.assertFalse(scheduling.slot_in_window(at(9, 15)))
        # outside the 08:00–21:30 window
        self.assertFalse(scheduling.slot_in_window(at(7, 30)))
        self.assertFalse(scheduling.slot_in_window(at(22, 0)))

    def _other_app(self, uid='stud2'):
        p = StudentProfile.objects.create(
            supabase_user_id=uid, nric='800101-14-5678', name='Bala Jr')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='interviewing',
            notify_email=f'{uid}@example.com', assigned_to=self.reviewer)

    # ── email-skip (re-propose the same menu) ──────────────────────────────────
    def test_propose_skips_email_when_menu_unchanged(self):
        t = [self._future(days=3), self._future(days=4), self._future(days=5)]
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=t)
        mail.outbox.clear()
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=t)  # same 3
        self.assertEqual(len(mail.outbox), 0)

    def test_propose_emails_when_menu_changes(self):
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=3)])
        mail.outbox.clear()
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=6)])
        self.assertEqual(len(mail.outbox), 1)

    # ── reviewer-wide conflict ─────────────────────────────────────────────────
    def test_propose_rejects_reviewer_conflict_across_students(self):
        other = self._other_app()
        t = self._future(days=3)
        scheduling.propose_slots(other, reviewer=self.reviewer, starts=[t])
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[t])
        self.assertEqual(str(cm.exception), 'reviewer_conflict')

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_book_rejects_reviewer_conflict(self, _mock):
        other = self._other_app()
        t = self._future(days=3)
        s1 = InterviewSlot.objects.create(application=self.app, reviewer=self.reviewer, start=t)
        s2 = InterviewSlot.objects.create(application=other, reviewer=self.reviewer, start=t)
        scheduling.book_slot(self.app, slot_id=s1.id)  # books t for app1
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.book_slot(other, slot_id=s2.id)
        self.assertEqual(str(cm.exception), 'reviewer_conflict')

    def test_payload_reviewer_busy_admin_only(self):
        from apps.scholarship.serializers_admin import interview_schedule_payload
        other = self._other_app()
        InterviewSlot.objects.create(
            application=other, reviewer=self.reviewer, start=self._future(days=3))
        admin_p = interview_schedule_payload(self.app, include_reviewer_busy=True)
        self.assertEqual(len(admin_p['reviewer_busy']), 1)        # the other student's slot
        student_p = interview_schedule_payload(self.app)
        self.assertNotIn('reviewer_busy', student_p)              # never leaked to students

    # ── request alternatives ("none of these work") ────────────────────────────
    def test_request_alternatives_records_and_notifies_reviewer(self):
        mail.outbox.clear()
        scheduling.request_alternatives(self.app, note='only back after 22 June')
        self.app.refresh_from_db()
        self.assertIsNotNone(self.app.interview_alternatives_requested_at)
        self.assertEqual(self.app.interview_alternatives_note, 'only back after 22 June')
        self.assertEqual(len(mail.outbox), 1)                      # the assigned reviewer
        self.assertEqual(mail.outbox[0].to, ['rohini@example.com'])
        self.assertIn('different interview times', mail.outbox[0].subject)
        self.assertIn('only back after 22 June', mail.outbox[0].body)

    def test_request_alternatives_rejected_once_booked(self):
        self.app.interview_status = 'booked'
        self.app.save(update_fields=['interview_status'])
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.request_alternatives(self.app)
        self.assertEqual(str(cm.exception), 'already_booked')

    def test_proposing_clears_the_alternatives_request(self):
        scheduling.request_alternatives(self.app, note='x')
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=4)])
        self.app.refresh_from_db()
        self.assertIsNone(self.app.interview_alternatives_requested_at)
        self.assertEqual(self.app.interview_alternatives_note, '')

    def test_payload_surfaces_alternatives_request(self):
        from apps.scholarship.serializers_admin import interview_schedule_payload
        scheduling.request_alternatives(self.app, note='after exams')
        p = interview_schedule_payload(self.app)
        self.assertTrue(p['alternatives_requested'])
        self.assertEqual(p['alternatives_note'], 'after exams')

    # ── email language gate (English-only ⇔ chose English AND A/A+ in English) ──
    def test_english_only_email_rule(self):
        from apps.scholarship.emails import english_only_email
        def mk(locale, call, eng):
            p = StudentProfile.objects.create(
                supabase_user_id=f'eo-{locale}-{call}-{eng}', nric='030101-14-1234',
                name='X', grades=({'eng': eng} if eng else {}), preferred_call_language=call)
            return ScholarshipApplication.objects.create(
                cohort=self.cohort, profile=p, status='interviewing', locale=locale)
        self.assertTrue(english_only_email(mk('en', 'en', 'A+')))
        self.assertTrue(english_only_email(mk('en', '', 'A')))
        self.assertFalse(english_only_email(mk('en', 'en', 'B')))   # English grade too low
        self.assertFalse(english_only_email(mk('ms', 'en', 'A+')))  # used the app in Malay
        self.assertFalse(english_only_email(mk('en', 'ms', 'A+')))  # wants Malay calls
        self.assertFalse(english_only_email(mk('en', 'ta', 'A+')))  # wants Tamil calls

    def test_propose_email_drops_bm_for_english_only_student(self):
        p = StudentProfile.objects.create(
            supabase_user_id='eo-prop', nric='030101-14-9999', name='Anya Rao',
            grades={'eng': 'A+'}, preferred_call_language='en')
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='interviewing', notify_email='anya@example.com',
            assigned_to=self.reviewer, locale='en')
        mail.outbox.clear()
        scheduling.propose_slots(app, reviewer=self.reviewer, starts=[self._future(days=3)])
        body = mail.outbox[-1].body
        self.assertIn('Hi ANYA,', body)   # profile.name is CAPS-normalised on save
        self.assertNotIn('Salam', body)   # BM mirror dropped for a confident English reader

    def test_reproposing_withdraws_old_unbooked_slots(self):
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=3)])
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=5)])
        active = InterviewSlot.objects.filter(application=self.app, is_active=True)
        self.assertEqual(active.count(), 1)

    # ── book ─────────────────────────────────────────────────────────────────
    @patch('apps.scholarship.meeting.create_event',
           return_value={'url': 'https://meet.google.com/abc-defg-hij', 'event_id': 'evt-1'})
    def test_book_sets_state_meet_and_emails(self, _mock):
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[self._future(days=3)])[0]
        mail.outbox.clear()
        scheduling.book_slot(self.app, slot_id=slot.id)
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, 'booked')
        self.assertEqual(self.app.interview_slot_id, slot.id)
        self.assertEqual(self.app.interview_meeting_url, 'https://meet.google.com/abc-defg-hij')
        self.assertEqual(self.app.interview_meeting_provider, 'google_meet')
        self.assertEqual(self.app.interview_calendar_event_id, 'evt-1')
        self.assertIsNotNone(self.app.interview_confirmation_sent_at)
        # student + reviewer confirmations
        self.assertEqual(len(mail.outbox), 2)

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_book_without_meet_still_succeeds(self, _mock):
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[self._future(days=3)])[0]
        scheduling.book_slot(self.app, slot_id=slot.id)
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, 'booked')
        self.assertEqual(self.app.interview_meeting_url, '')

    def test_book_bad_slot(self):
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.book_slot(self.app, slot_id=999999)
        self.assertEqual(str(cm.exception), 'bad_slot')

    def test_book_past_slot(self):
        slot = InterviewSlot.objects.create(
            application=self.app, reviewer=self.reviewer, start=self._future(days=-1))
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.book_slot(self.app, slot_id=slot.id)
        self.assertEqual(str(cm.exception), 'past_slot')

    # ── reschedule ───────────────────────────────────────────────────────────
    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_reschedule_within_cutoff_ok(self, _mock):
        slots = scheduling.propose_slots(
            self.app, reviewer=self.reviewer,
            starts=[self._future(days=5), self._future(days=6)])
        scheduling.book_slot(self.app, slot_id=slots[0].id)
        scheduling.book_slot(self.app, slot_id=slots[1].id)  # reschedule
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_slot_id, slots[1].id)

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_reschedule_too_late(self, _mock):
        slots = scheduling.propose_slots(
            self.app, reviewer=self.reviewer,
            starts=[self._future(hours=2), self._future(days=6)])
        scheduling.book_slot(self.app, slot_id=slots[0].id)  # booked 2h out (inside 12h cutoff)
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.book_slot(self.app, slot_id=slots[1].id)
        self.assertEqual(str(cm.exception), 'too_late')

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_reschedule_resets_reminder_stamps(self, _mock):
        slots = scheduling.propose_slots(
            self.app, reviewer=self.reviewer,
            starts=[self._future(days=5), self._future(days=6)])
        scheduling.book_slot(self.app, slot_id=slots[0].id)
        self.app.interview_reminded_1d_at = timezone.now()
        self.app.save(update_fields=['interview_reminded_1d_at'])
        scheduling.book_slot(self.app, slot_id=slots[1].id)
        self.app.refresh_from_db()
        self.assertIsNone(self.app.interview_reminded_1d_at)

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_rebook_refreshes_booked_at(self, _mock):
        # interview_booked_at must track the CURRENT booking so reminder-notice re-gates on reschedule.
        slots = scheduling.propose_slots(
            self.app, reviewer=self.reviewer,
            starts=[self._future(days=5), self._future(days=6)])
        scheduling.book_slot(self.app, slot_id=slots[0].id)
        old = timezone.now() - timedelta(hours=10)
        self.app.interview_booked_at = old
        self.app.save(update_fields=['interview_booked_at'])
        scheduling.book_slot(self.app, slot_id=slots[1].id)
        self.app.refresh_from_db()
        self.assertGreater(self.app.interview_booked_at, old)  # rebook refreshed it

    # ── cancel ───────────────────────────────────────────────────────────────
    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_cancel_ok_and_notifies(self, _mock):
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[self._future(days=5)])[0]
        scheduling.book_slot(self.app, slot_id=slot.id)
        mail.outbox.clear()
        scheduling.cancel(self.app, by='student')
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, 'cancelled')
        self.assertEqual(self.app.interview_meeting_url, '')
        self.assertEqual(len(mail.outbox), 2)  # student + reviewer

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_cancel_stores_reason_and_emails_it(self, _mock):
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[self._future(days=5)])[0]
        scheduling.book_slot(self.app, slot_id=slot.id)
        mail.outbox.clear()
        scheduling.cancel(self.app, by='student', reason='Clashes with my exam')
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_cancel_reason, 'Clashes with my exam')
        self.assertTrue(any('Clashes with my exam' in m.body for m in mail.outbox))  # reviewer notice

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_proposing_after_cancel_clears_reason(self, _mock):
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[self._future(days=5)])[0]
        scheduling.book_slot(self.app, slot_id=slot.id)
        scheduling.cancel(self.app, by='student', reason='Clashes with my exam')
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=6)])
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_cancel_reason, '')

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_cancel_too_late_for_student(self, _mock):
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[self._future(hours=2)])[0]
        scheduling.book_slot(self.app, slot_id=slot.id)
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.cancel(self.app, by='student')
        self.assertEqual(str(cm.exception), 'too_late')

    def test_cancel_when_not_booked(self):
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.cancel(self.app, by='student')
        self.assertEqual(str(cm.exception), 'not_booked')

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_cancel_voids_the_menu(self, _mock):
        slots = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                         starts=[self._future(days=3), self._future(days=4)])
        scheduling.book_slot(self.app, slot_id=slots[0].id)
        scheduling.cancel(self.app, by='student')
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, 'cancelled')
        self.assertIsNone(self.app.interview_slot_id)         # booking pointers cleared
        self.assertIsNone(self.app.interview_start)
        self.assertEqual(                                     # the whole menu withdrawn
            InterviewSlot.objects.filter(application=self.app, is_active=True).count(), 0)

    # ── reviewer reschedule (release the booking + re-offer) ───────────────────
    @patch('apps.scholarship.meeting.cancel_event', return_value=True)
    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_reviewer_reschedule_releases_booking_and_reoffers(self, _create, _cancel):
        slots = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                         starts=[self._future(days=5), self._future(days=6)])
        scheduling.book_slot(self.app, slot_id=slots[0].id)
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, 'booked')
        mail.outbox.clear()
        # Reviewer MOVES it: release the booking + offer a fresh menu.
        scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                 starts=[self._future(days=8)], release_booking=True)
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, '')          # back to awaiting-a-pick
        self.assertIsNone(self.app.interview_slot_id)            # old booking released
        self.assertIsNone(self.app.interview_start)
        self.assertEqual(self.app.interview_meeting_url, '')
        self.assertEqual(                                        # only the new slot is live
            InterviewSlot.objects.filter(application=self.app, is_active=True).count(), 1)
        # Student is told to re-pick, with the moved-the-time copy.
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[-1]
        self.assertIn('time has changed', msg.subject)
        self.assertIn('had to move', msg.body)

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_reschedule_noop_when_not_booked_just_proposes(self, _create):
        # release_booking on a not-yet-booked interview is a normal proposal (no error).
        scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                 starts=[self._future(days=4)], release_booking=True)
        self.app.refresh_from_db()
        self.assertEqual(
            InterviewSlot.objects.filter(application=self.app, is_active=True).count(), 1)

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_proposing_after_cancel_clears_cancelled_state(self, _mock):
        slots = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                         starts=[self._future(days=3)])
        scheduling.book_slot(self.app, slot_id=slots[0].id)
        scheduling.cancel(self.app, by='student')
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=5)])
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, '')       # back to awaiting-a-pick
        self.assertIsNone(self.app.interview_cancelled_at)
        self.assertEqual(                                     # the fresh menu is live
            InterviewSlot.objects.filter(application=self.app, is_active=True).count(), 1)


@override_settings(INTERVIEW_SCHEDULING_ENABLED=True)
class ReminderCronTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Rohini', email='rohini@example.com')
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='stud', nric='030101-14-1234', name='Priya')

    def _booked_app(self, start):
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='interviewing',
            notify_email='priya@example.com', assigned_to=self.reviewer,
            interview_status='booked', interview_start=start)

    @override_settings(WHATSAPP_ENABLED=True, TWILIO_ACCOUNT_SID='AC',
                       TWILIO_AUTH_TOKEN='t', TWILIO_WHATSAPP_FROM='whatsapp:+14155238886')
    @patch('apps.scholarship.whatsapp._post_to_twilio', return_value=('SM1', 'queued', ''))
    def test_whatsapp_reminder_sent_when_opted_in(self, _post):
        self.profile.contact_phone = '012-345 6789'
        self.profile.whatsapp_opt_in = True
        self.profile.save(update_fields=['contact_phone', 'whatsapp_opt_in'])
        app = self._booked_app(timezone.now() + timedelta(hours=20))
        call_command('send_interview_reminders')
        self.assertEqual(
            WhatsAppMessage.objects.filter(application=app, kind='interview_reminder_1day').count(), 1)

    @override_settings(WHATSAPP_ENABLED=True, TWILIO_ACCOUNT_SID='AC',
                       TWILIO_AUTH_TOKEN='t', TWILIO_WHATSAPP_FROM='whatsapp:+14155238886')
    @patch('apps.scholarship.whatsapp._post_to_twilio', return_value=('SM1', 'queued', ''))
    def test_whatsapp_reminder_skipped_when_opted_out(self, _post):
        self.profile.contact_phone = '012-345 6789'
        self.profile.whatsapp_opt_in = False
        self.profile.save(update_fields=['contact_phone', 'whatsapp_opt_in'])
        app = self._booked_app(timezone.now() + timedelta(hours=20))
        mail.outbox.clear()
        call_command('send_interview_reminders')
        self.assertEqual(WhatsAppMessage.objects.filter(application=app).count(), 0)
        # email is channel-independent — it still goes out to the opted-out student
        self.assertTrue(any('priya@example.com' in m.to for m in mail.outbox))

    # ── reminder v2: EN / EN+BM template variants picked by english_only (S3) ──
    @override_settings(WHATSAPP_ENABLED=True, TWILIO_ACCOUNT_SID='AC', TWILIO_AUTH_TOKEN='t',
                       TWILIO_WHATSAPP_FROM='whatsapp:+19162597009',
                       TWILIO_WHATSAPP_REMINDER_CONTENT_SID_EN='HXen',
                       TWILIO_WHATSAPP_REMINDER_CONTENT_SID_BM='HXbm')
    @patch('apps.scholarship.emails.english_only_email', return_value=True)
    @patch('apps.scholarship.whatsapp._post_to_twilio', return_value=('SM1', 'queued', ''))
    def test_reminder_uses_EN_variant_for_english_only(self, post, _eo):
        self.profile.contact_phone = '012-345 6789'; self.profile.whatsapp_opt_in = True
        self.profile.save(update_fields=['contact_phone', 'whatsapp_opt_in'])
        self._booked_app(timezone.now() + timedelta(hours=20))
        call_command('send_interview_reminders')
        # _post_to_twilio args: (sid, token, sender, to, body, content_sid, content_variables)
        self.assertEqual(post.call_count, 1)
        content_sid, cv = post.call_args[0][5], post.call_args[0][6]
        self.assertEqual(content_sid, 'HXen')
        self.assertNotIn('5', cv)                       # EN template → no Malay 'when'
        self.assertEqual(cv['2'], 'Rohini')             # interviewer named
        self.assertIn('tomorrow', cv['3'])              # 24h 'when' phrase

    @override_settings(WHATSAPP_ENABLED=True, TWILIO_ACCOUNT_SID='AC', TWILIO_AUTH_TOKEN='t',
                       TWILIO_WHATSAPP_FROM='whatsapp:+19162597009',
                       TWILIO_WHATSAPP_REMINDER_CONTENT_SID_EN='HXen',
                       TWILIO_WHATSAPP_REMINDER_CONTENT_SID_BM='HXbm')
    @patch('apps.scholarship.emails.english_only_email', return_value=False)
    @patch('apps.scholarship.whatsapp._post_to_twilio', return_value=('SM1', 'queued', ''))
    def test_reminder_uses_BM_variant_otherwise(self, post, _eo):
        self.profile.contact_phone = '012-345 6789'; self.profile.whatsapp_opt_in = True
        self.profile.save(update_fields=['contact_phone', 'whatsapp_opt_in'])
        self._booked_app(timezone.now() + timedelta(hours=20))
        call_command('send_interview_reminders')
        content_sid, cv = post.call_args[0][5], post.call_args[0][6]
        self.assertEqual(content_sid, 'HXbm')
        self.assertIn('esok', cv['5'])                  # bilingual template carries the BM 'when'

    def test_one_day_reminder_fires_once(self):
        app = self._booked_app(timezone.now() + timedelta(hours=20))
        mail.outbox.clear()
        call_command('send_interview_reminders')
        app.refresh_from_db()
        self.assertIsNotNone(app.interview_reminded_1d_at)
        self.assertEqual(len(mail.outbox), 2)  # student + reviewer
        # idempotent: a second run sends nothing new
        mail.outbox.clear()
        call_command('send_interview_reminders')
        self.assertEqual(len(mail.outbox), 0)

    def test_one_hour_reminder_fires(self):
        app = self._booked_app(timezone.now() + timedelta(minutes=30))
        call_command('send_interview_reminders')
        app.refresh_from_db()
        self.assertIsNotNone(app.interview_reminded_1h_at)
        self.assertIsNotNone(app.interview_reminded_1d_at)  # also within 24h

    def test_no_reminder_far_out(self):
        app = self._booked_app(timezone.now() + timedelta(days=3))
        call_command('send_interview_reminders')
        app.refresh_from_db()
        self.assertIsNone(app.interview_reminded_1d_at)

    # ── booking-notice gating (skip a reminder the booking gave too little notice for) ──
    def test_one_day_skipped_when_booked_within_24h(self):
        # Same-day booking (10h notice): no "24h reminder", and not yet inside the 1h window → nothing.
        start = timezone.now() + timedelta(hours=10)
        app = self._booked_app(start)
        app.interview_booked_at = timezone.now()
        app.save(update_fields=['interview_booked_at'])
        mail.outbox.clear()
        call_command('send_interview_reminders')
        app.refresh_from_db()
        self.assertIsNone(app.interview_reminded_1d_at)   # 24h reminder skipped
        self.assertEqual(len(mail.outbox), 0)

    def test_one_day_fires_when_booked_with_24h_notice(self):
        # Interview 20h away but booked 25h before it → ≥24h notice → 24h reminder fires.
        start = timezone.now() + timedelta(hours=20)
        app = self._booked_app(start)
        app.interview_booked_at = start - timedelta(hours=25)
        app.save(update_fields=['interview_booked_at'])
        call_command('send_interview_reminders')
        app.refresh_from_db()
        self.assertIsNotNone(app.interview_reminded_1d_at)

    def test_one_hour_skipped_when_booked_within_1h(self):
        # Last-minute booking (30 min notice): neither reminder fires (confirmation already sent at booking).
        start = timezone.now() + timedelta(minutes=30)
        app = self._booked_app(start)
        app.interview_booked_at = timezone.now()
        app.save(update_fields=['interview_booked_at'])
        call_command('send_interview_reminders')
        app.refresh_from_db()
        self.assertIsNone(app.interview_reminded_1h_at)
        self.assertIsNone(app.interview_reminded_1d_at)

    def test_one_hour_fires_when_booked_with_1h_notice(self):
        # Interview 30 min away but booked 3h before → ≥1h notice → 1h reminder fires; 24h still skipped.
        start = timezone.now() + timedelta(minutes=30)
        app = self._booked_app(start)
        app.interview_booked_at = start - timedelta(hours=3)
        app.save(update_fields=['interview_booked_at'])
        call_command('send_interview_reminders')
        app.refresh_from_db()
        self.assertIsNotNone(app.interview_reminded_1h_at)
        self.assertIsNone(app.interview_reminded_1d_at)   # only 3h notice → no 24h reminder

    @override_settings(INTERVIEW_SCHEDULING_ENABLED=False)
    def test_inert_when_flag_off(self):
        app = self._booked_app(timezone.now() + timedelta(hours=20))
        call_command('send_interview_reminders')
        app.refresh_from_db()
        self.assertIsNone(app.interview_reminded_1d_at)


class BookingEmailTests(TestCase):
    def test_booked_email_html_ics_and_interviewer_name(self):
        start = timezone.now() + timedelta(days=2)
        from apps.scholarship.emails import send_interview_booked_email
        self.assertTrue(send_interview_booked_email(
            's@example.com', student_name='Priya Devi', reviewer_name='Rohini',
            start=start, meeting_url='https://meet.google.com/abc', duration_min=45))
        msg = mail.outbox[-1]
        self.assertEqual(msg.subject, 'Your BrightPath Bursary Programme interview is booked')
        self.assertEqual(msg.reply_to, ['interview@halatuju.xyz'])
        self.assertEqual(msg.from_email, 'interview@halatuju.xyz')   # #2: sends FROM interview@
        # Harmless List-Unsubscribe (mailto to support, no one-click) so a mistaken click
        # can't trigger the ESP's auto-suppression of service mail.
        self.assertIn('mailto:help@halatuju.xyz', msg.extra_headers.get('List-Unsubscribe', ''))
        self.assertNotIn('List-Unsubscribe-Post', msg.extra_headers)
        body = msg.body
        self.assertIn('Hi Priya,', body)                    # first name
        self.assertIn('Interviewer: Rohini', body)          # interviewer NAME (no phone)
        self.assertIn('Penemu duga: Rohini', body)          # BM mirror
        self.assertIn('https://meet.google.com/abc', body)
        self.assertNotIn('+60', body)                       # phone no longer included
        # HTML alternative + .ics calendar attachment
        html, mime = msg.alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('Add to calendar', html)
        self.assertIn('calendar.google.com/calendar/render', html)
        self.assertIn('/scholarship/application"', html)      # "application page" is linked
        ics = [a for a in msg.attachments if a[0] == 'interview.ics']
        self.assertEqual(len(ics), 1)
        self.assertIn('BEGIN:VEVENT', ics[0][1])

    def test_booked_email_english_only_drops_bm(self):
        from apps.scholarship.emails import send_interview_booked_email
        send_interview_booked_email(
            's@example.com', student_name='Priya', reviewer_name='Rohini',
            start=timezone.now() + timedelta(days=2), meeting_url='', english_only=True)
        body = mail.outbox[-1].body
        self.assertIn('BrightPath Bursary Programme', body)
        self.assertNotIn('Program Bursari BrightPath', body)

    def test_reminder_email_when_labels(self):
        from apps.scholarship.emails import send_interview_reminder_email
        start = timezone.now() + timedelta(days=1)
        send_interview_reminder_email('s@example.com', student_name='Priya', start=start, when='1day')
        self.assertIn('tomorrow', mail.outbox[-1].body)
        send_interview_reminder_email('s@example.com', student_name='Priya', start=start, when='1hour')
        self.assertIn('about an hour', mail.outbox[-1].body)

    def test_reminder_email_is_html_bilingual(self):
        from apps.scholarship.emails import send_interview_reminder_email
        start = timezone.now() + timedelta(days=1)
        send_interview_reminder_email('s@example.com', student_name='Priya', start=start, when='1day')
        msg = mail.outbox[-1]
        self.assertEqual(len(msg.alternatives), 1)
        html, mime = msg.alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('<', html)
        self.assertIn('Peringatan', msg.body)  # BM mirror present in the text part

    def test_reminder_email_english_only_drops_bm(self):
        from apps.scholarship.emails import send_interview_reminder_email
        start = timezone.now() + timedelta(days=1)
        send_interview_reminder_email('s@example.com', student_name='Priya', start=start,
                                      when='1day', english_only=True)
        self.assertNotIn('Peringatan', mail.outbox[-1].body)

    def test_cancelled_email_is_html_bilingual(self):
        from apps.scholarship.emails import send_interview_cancelled_email
        send_interview_cancelled_email('s@example.com', student_name='Priya Devi')
        msg = mail.outbox[-1]
        self.assertEqual(len(msg.alternatives), 1)
        self.assertEqual(msg.alternatives[0][1], 'text/html')
        self.assertIn('Hi Priya,', msg.body)            # first-name greeting
        self.assertIn('still active', msg.body)          # application-still-active reassurance
        self.assertIn('Permohonan anda masih aktif', msg.body)  # BM mirror


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   INTERVIEW_SCHEDULING_ENABLED=True)
class SchedulingEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@example.com')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Rohini', email='rohini@example.com')
        cls.other_reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev2-uid', role='reviewer', is_active=True,
            name='Bala', email='bala@example.com')
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='stud', nric='030101-14-1234', name='Priya')

    def setUp(self):
        self.client = APIClient()
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='interviewing',
            notify_email='priya@example.com', assigned_to=self.reviewer)

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _iso(self, **kw):
        # A valid interview slot: 10:00 MYT on a future day (on-boundary, in-window).
        from zoneinfo import ZoneInfo
        base = (timezone.now() + timedelta(**kw)).astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
        return base.replace(hour=10, minute=0, second=0, microsecond=0).isoformat()

    def _propose_url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/interview-slots/'

    def test_assigned_reviewer_can_propose(self):
        self._auth('rev-uid')
        r = self.client.post(self._propose_url(), {'slots': [self._iso(days=3)]}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['slots']), 1)

    def test_propose_rejects_out_of_window_time(self):
        # 03:00 MYT — outside 08:00–21:30 → 400, no slots created.
        from zoneinfo import ZoneInfo
        self._auth('rev-uid')
        bad = ((timezone.now() + timedelta(days=3)).astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
               .replace(hour=3, minute=0, second=0, microsecond=0).isoformat())
        r = self.client.post(self._propose_url(), {'slots': [bad]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'invalid_slot_time')

    def test_propose_rejects_too_soon_time(self):
        # A valid 10:00 MYT slot but only ~3 hours out — inside the 24h lead → 400.
        from zoneinfo import ZoneInfo
        self._auth('rev-uid')
        soon = ((timezone.now() + timedelta(hours=3)).astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
                .replace(minute=0, second=0, microsecond=0).isoformat())
        r = self.client.post(self._propose_url(), {'slots': [soon]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'too_soon')

    def test_propose_rejects_off_boundary_time(self):
        # 10:15 MYT — not on a 30-minute boundary → 400.
        from zoneinfo import ZoneInfo
        self._auth('rev-uid')
        bad = ((timezone.now() + timedelta(days=3)).astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
               .replace(hour=10, minute=15, second=0, microsecond=0).isoformat())
        r = self.client.post(self._propose_url(), {'slots': [bad]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'invalid_slot_time')

    def test_unassigned_reviewer_cannot_propose(self):
        self._auth('rev2-uid')
        r = self.client.post(self._propose_url(), {'slots': [self._iso(days=3)]}, format='json')
        self.assertEqual(r.status_code, 403)

    @patch('apps.scholarship.meeting.cancel_event', return_value=True)
    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_reviewer_reschedule_via_endpoint(self, _create, _cancel):
        # Reviewer proposes + the student books, then the reviewer MOVES it with reschedule=true.
        self._auth('rev-uid')
        r = self.client.post(self._propose_url(), {'slots': [self._iso(days=4)]}, format='json')
        slot_id = r.json()['slots'][0]['id']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("stud")}')
        self.client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/interview/book/',
            {'slot_id': slot_id}, format='json')
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, 'booked')
        # Reviewer moves the time.
        self._auth('rev-uid')
        r = self.client.post(self._propose_url(),
                             {'slots': [self._iso(days=6)], 'reschedule': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, '')        # booking released
        self.assertIsNone(self.app.interview_slot_id)

    @override_settings(INTERVIEW_SCHEDULING_ENABLED=False)
    def test_propose_404_when_flag_off(self):
        self._auth('rev-uid')
        r = self.client.post(self._propose_url(), {'slots': [self._iso(days=3)]}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_student_requests_alternatives_endpoint(self):
        self._auth('stud')
        r = self.client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/interview/request-alternatives/',
            {'note': 'none of these work for me'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['alternatives_requested'])
        self.assertEqual(r.json()['alternatives_note'], 'none of these work for me')

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_student_books_and_cancels_own(self, _mock):
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[timezone.now() + timedelta(days=5)])[0]
        self._auth('stud')
        r = self.client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/interview/book/',
            {'slot_id': slot.id}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'booked')
        r2 = self.client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/interview/cancel/', {}, format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['status'], 'cancelled')

    def test_student_cannot_book_others_application(self):
        other_profile = StudentProfile.objects.create(
            supabase_user_id='other', nric='040101-14-9999', name='Other')
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[timezone.now() + timedelta(days=5)])[0]
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("other")}')
        r = self.client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/interview/book/',
            {'slot_id': slot.id}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_student_get_interview_state(self):
        scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                 starts=[timezone.now() + timedelta(days=5)])
        self._auth('stud')
        r = self.client.get(f'/api/v1/scholarship/applications/{self.app.id}/interview/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['slots']), 1)
