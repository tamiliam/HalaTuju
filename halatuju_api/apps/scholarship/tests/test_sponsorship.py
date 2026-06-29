"""Phase E3 — wallet + match/consent (Sponsorship).

Covers the money ledger (donations − holding allocations), fund-in-full, award
accept/decline (+ minor guardian gate), lapse → balance freed, the pool excluding
sponsored students, and — load-bearing — anonymity BOTH ways (sponsor never sees
the student's identity; student never sees the sponsor's). All on dummy data; the
pool flag is forced on where the sponsor endpoints are exercised.
"""
import json
from decimal import Decimal

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import sponsorship as svc
from apps.scholarship import services
from apps.scholarship import pool
from apps.scholarship.models import (
    Consent, Donation, OnboardingResponse, ScholarshipApplication, ScholarshipCohort,
    Sponsor, Sponsorship, SponsorProfile,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADULT_NRIC = '000101-10-1233'   # born 2000 → adult
MINOR_NRIC = '100101-10-1234'   # born 2010 → minor


def _token(uid, email='', anon=False):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated', 'email': email, 'is_anonymous': anon},
        TEST_JWT_SECRET, algorithm='HS256')


def _fundable_app(cohort, *, suffix='1', nric=ADULT_NRIC, award=Decimal('3000')):
    profile = StudentProfile.objects.create(
        supabase_user_id=f'stu-{suffix}', name='Zxq Student', nric=nric,
        preferred_state='Kedah', exam_type='spm', grades={'bm': 'A'},
        contact_email='student@secret.example', contact_phone='012-7776666',
    )
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, status='recommended', award_amount=award,
        notify_email='student@secret.example')
    SponsorProfile.objects.create(application=app, anon_markdown='The student is determined.', anon_published=True)
    Consent.objects.create(application=app, consent_type='share_with_sponsors', version='e', is_active=True)
    return app


def _sponsor(uid='spon-1', status='approved'):
    return Sponsor.objects.create(
        supabase_user_id=uid, name='Jane Sponsor', email='jane@sponsor.example',
        phone='0123', source='friend', consent_at=timezone.now(), status=status)


# ─── service layer ───────────────────────────────────────────────────────────

class TestSponsorshipService(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_balance_donations_minus_holding(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('1000'))
        Donation.objects.create(sponsor=s, amount=Decimal('2000'))
        self.assertEqual(svc.sponsor_balance(s), Decimal('3000'))
        app = _fundable_app(self.cohort)
        svc.fund_student(s, app)                       # allocates 3000
        self.assertEqual(svc.sponsor_balance(s), Decimal('0'))

    def test_fund_insufficient_balance(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('1000'))
        app = _fundable_app(self.cohort)               # award 3000
        with self.assertRaises(svc.SponsorshipError) as e:
            svc.fund_student(s, app)
        self.assertEqual(e.exception.code, 'insufficient_balance')

    def test_not_fundable_without_award_amount(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('5000'))
        app = _fundable_app(self.cohort, award=None)
        ScholarshipApplication.objects.filter(id=app.id).update(award_amount=None)
        app.refresh_from_db()
        with self.assertRaises(svc.SponsorshipError) as e:
            svc.fund_student(s, app)
        self.assertEqual(e.exception.code, 'not_fundable')

    def test_accept_adult_activates_and_sponsors(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        app = _fundable_app(self.cohort)
        svc.fund_student(s, app)
        sp = svc.respond_to_award(app, action='accept')
        self.assertEqual(sp.status, 'active')
        self.assertIsNotNone(sp.consent)
        app.refresh_from_db()
        self.assertEqual(app.status, 'active')
        self.assertTrue(app.consents.filter(consent_type='consent_to_sponsorship', is_active=True).exists())
        # …and a funded student is out of the pool.
        self.assertFalse(pool.is_pool_eligible(app))

    def test_accept_minor_requires_guardian(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        app = _fundable_app(self.cohort, suffix='m', nric=MINOR_NRIC)
        svc.fund_student(s, app)
        with self.assertRaises(svc.SponsorshipError) as e:
            svc.respond_to_award(app, action='accept')   # no guardian → blocked
        self.assertEqual(e.exception.code, 'guardian_required')
        sp = svc.respond_to_award(app, action='accept', granted_by='guardian',
                                  guardian_name='Mum', guardian_relationship='mother', guardian_nric=ADULT_NRIC)
        self.assertEqual(sp.status, 'active')

    def test_decline_frees_balance(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        app = _fundable_app(self.cohort)
        svc.fund_student(s, app)
        self.assertEqual(svc.sponsor_balance(s), Decimal('0'))
        svc.respond_to_award(app, action='decline')
        self.assertEqual(svc.sponsor_balance(s), Decimal('3000'))  # returned to balance

    def test_lapse_expired_offer(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        app = _fundable_app(self.cohort)
        sp = svc.fund_student(s, app)
        Sponsorship.objects.filter(id=sp.id).update(accept_deadline=timezone.now() - timezone.timedelta(days=1))
        self.assertEqual(svc.lapse_expired_offers(), 1)
        sp.refresh_from_db()
        self.assertEqual(sp.status, 'lapsed')
        self.assertEqual(svc.sponsor_balance(s), Decimal('3000'))

    # ─── F8a: award-confirmed email + onboarding ─────────────────────────────
    def test_accept_emails_award_confirmed_without_sponsor_identity(self):
        from django.core import mail
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        app = _fundable_app(self.cohort)
        svc.fund_student(s, app)
        mail.outbox = []
        svc.respond_to_award(app, action='accept')
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        blob = f'{msg.subject}\n{msg.body}'
        # B4: the sponsor is NEVER named to the student.
        self.assertNotIn('Jane Sponsor', blob)
        self.assertNotIn('jane@sponsor.example', blob)

    def test_complete_onboarding_records_consent_and_stamps(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        app = _fundable_app(self.cohort)
        svc.fund_student(s, app)
        svc.respond_to_award(app, action='accept')          # → status 'sponsored'
        resp = services.complete_onboarding(app, answers={'commitment': 'yes'})
        app.refresh_from_db()
        self.assertIsNotNone(app.onboarded_at)
        self.assertEqual(resp.answers, {'commitment': 'yes'})
        c = app.consents.filter(consent_type='student_onboarding_ack', is_active=True).first()
        self.assertIsNotNone(c)
        self.assertEqual(c.version, services.CONSENT_VERSION)
        self.assertEqual(c.granted_by, 'self')
        # re-running updates in place (no duplicate row, latest answers win)
        services.complete_onboarding(app, answers={'commitment': 'absolutely'})
        app.refresh_from_db()
        self.assertEqual(app.onboarding_response.answers, {'commitment': 'absolutely'})
        self.assertEqual(OnboardingResponse.objects.filter(application=app).count(), 1)

    def test_onboarding_blocked_before_award_accepted(self):
        app = _fundable_app(self.cohort)   # status 'recommended', not yet 'sponsored'
        with self.assertRaises(services.OnboardingError) as e:
            services.complete_onboarding(app)
        self.assertEqual(e.exception.code, 'not_awarded')


# ─── sponsor endpoints (flag + approval gated; anonymous student) ────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSponsorEndpoints(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.app = _fundable_app(cls.cohort)
        _sponsor('spon-ok')
        _sponsor('spon-pending', status='pending')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid, "x@x.com")}')

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_donate_then_fund_then_my_sponsorships(self):
        self._auth('spon-ok')
        d = self.client.post('/api/v1/sponsor/wallet/donate/', {'amount': '5000'}, format='json')
        self.assertEqual(d.status_code, 201, d.content)
        self.assertEqual(Decimal(d.json()['balance']), Decimal('5000'))
        f = self.client.post(f'/api/v1/sponsor/pool/{self.app.id}/fund/', {}, format='json')
        self.assertEqual(f.status_code, 201, f.content)
        self.assertEqual(f.json()['status'], 'offered')
        # wallet balance reflects the held allocation
        w = self.client.get('/api/v1/sponsor/wallet/')
        self.assertEqual(Decimal(w.json()['balance']), Decimal('2000'))
        mine = self.client.get('/api/v1/sponsor/sponsorships/')
        self.assertEqual(mine.status_code, 200)
        self._assert_no_student_identity(mine.json())

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_fund_insufficient_400(self):
        self._auth('spon-ok')
        r = self.client.post(f'/api/v1/sponsor/pool/{self.app.id}/fund/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'insufficient_balance')

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_pending_sponsor_forbidden(self):
        self._auth('spon-pending')
        self.assertEqual(self.client.get('/api/v1/sponsor/wallet/').status_code, 403)

    @override_settings(SPONSOR_POOL_ENABLED=False)
    def test_404_when_flag_off(self):
        self._auth('spon-ok')
        self.assertEqual(self.client.get('/api/v1/sponsor/wallet/').status_code, 404)

    # ─── F8a: the student onboarding-complete endpoint ───────────────────────
    def _onboard_url(self):
        return f'/api/v1/scholarship/applications/{self.app.id}/onboarding-complete/'

    def test_onboarding_complete_endpoint(self):
        s = Sponsor.objects.get(supabase_user_id='spon-ok')
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        svc.fund_student(s, self.app)
        svc.respond_to_award(self.app, action='accept')   # → 'sponsored'
        self._auth('stu-1')                               # the student owns the app (profile pk == uid)
        r = self.client.post(self._onboard_url(), {'answers': {'q': 'a'}}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertIsNotNone(self.app.onboarded_at)
        self.assertTrue(self.app.consents.filter(
            consent_type='student_onboarding_ack', is_active=True).exists())

    def test_onboarding_complete_blocked_before_award(self):
        self._auth('stu-1')                               # award not accepted yet
        r = self.client.post(self._onboard_url(), {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'not_awarded')

    def _assert_no_student_identity(self, payload):
        blob = json.dumps(payload)
        for v in ('Zxq Student', ADULT_NRIC, 'student@secret.example', '012-7776666'):
            self.assertNotIn(v, blob, 'student identity leaked to sponsor')


# ─── student award (anonymous sponsor) ───────────────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestStudentAward(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()
        self.app = _fundable_app(self.cohort)
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        svc.fund_student(s, self.app)
        self.uid = self.app.profile.supabase_user_id

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(self.uid, "x@x.com")}')

    def test_get_offer_hides_sponsor_identity(self):
        self._auth()
        r = self.client.get('/api/v1/scholarship/award/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNotNone(r.json()['offer'])
        blob = json.dumps(r.json())
        for v in ('Jane Sponsor', 'jane@sponsor.example'):
            self.assertNotIn(v, blob, 'sponsor identity leaked to student')

    def test_accept_activates(self):
        self._auth()
        r = self.client.post('/api/v1/scholarship/award/', {'action': 'accept'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['status'], 'active')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'active')

    def test_decline_lapses(self):
        self._auth()
        r = self.client.post('/api/v1/scholarship/award/', {'action': 'decline'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'lapsed')


# ─── admin: set award amount + match oversight ───────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAdminSponsorship(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        PartnerAdmin.objects.create(supabase_user_id='rev', role='reviewer', is_active=True, name='Rev', email='r@x.com')
        PartnerAdmin.objects.create(supabase_user_id='vie', role='admin', is_active=True, name='Vie', email='v@x.com')
        PartnerAdmin.objects.create(supabase_user_id='sup', role='super', is_active=True, name='Sup', email='s@x.com', is_super_admin=True)

    def setUp(self):
        self.client = APIClient()
        self.app = _fundable_app(self.cohort, award=None)
        ScholarshipApplication.objects.filter(id=self.app.id).update(award_amount=None)
        self.app.assigned_to = PartnerAdmin.objects.get(supabase_user_id='rev')
        self.app.save(update_fields=['assigned_to'])

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid, "x@x.com")}')

    def test_super_sets_award_amount(self):
        # Override is SUPER-ONLY (2026-06-29) and must land on an allowed slider stop.
        self._auth('sup')
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/award-amount/',
                             {'amount': '2500'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertEqual(self.app.award_amount, Decimal('2500'))

    def test_super_rejects_off_step_amount(self):
        self._auth('sup')
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/award-amount/',
                             {'amount': '2300'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_reviewer_cannot_set_amount(self):
        # Reviewers may no longer set the amount — it's pathway-standard + super-overridable.
        self._auth('rev')
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/award-amount/',
                             {'amount': '2500'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_viewer_cannot_set_amount(self):
        self._auth('vie')
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/award-amount/',
                             {'amount': '2500'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_oversight_sees_both_sides(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        ScholarshipApplication.objects.filter(id=self.app.id).update(award_amount=Decimal('3000'))
        self.app.refresh_from_db()
        svc.fund_student(s, self.app)
        self._auth('rev')
        r = self.client.get('/api/v1/admin/sponsorships/')
        self.assertEqual(r.status_code, 200)
        row = r.json()['sponsorships'][0]
        self.assertEqual(row['sponsor']['name'], 'Jane Sponsor')   # admin sees the sponsor
        self.assertEqual(row['application']['name'], 'Zxq Student')  # …and the student


# ─── award good-news email (sent when a student becomes 'awarded') ────────────

from django.core import mail  # noqa: E402


class TestAwardOfferEmail(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_award_and_notify_funds_without_inline_email(self):
        # Cool-off model: awarding never emails inline — the release cron sends it later.
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        app = _fundable_app(self.cohort)
        mail.outbox = []
        sp = svc.award_and_notify(s, app)
        app.refresh_from_db()
        self.assertEqual(sp.status, 'offered')
        self.assertEqual(app.status, 'awarded')
        self.assertIsNone(sp.offer_emailed_at)   # nothing emailed yet
        self.assertEqual(len(mail.outbox), 0)

    def test_award_offer_email_bm_has_no_amount(self):
        from apps.scholarship.emails import send_award_offer_email
        mail.outbox = []
        ok = send_award_offer_email('x@y.example', 'Aisyah', lang='ms')
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Berita baik', mail.outbox[0].subject)
        self.assertNotIn('RM', mail.outbox[0].body)

    def test_award_offer_email_no_recipient_noop(self):
        from apps.scholarship.emails import send_award_offer_email
        mail.outbox = []
        self.assertFalse(send_award_offer_email('', 'Nobody'))
        self.assertEqual(len(mail.outbox), 0)

    def test_award_offer_email_html_has_button_and_bold(self):
        from apps.scholarship.emails import send_award_offer_email
        mail.outbox = []
        send_award_offer_email('x@y.example', 'Aisyah', lang='en')
        html = mail.outbox[0].alternatives[0][0]   # (html_body, 'text/html')
        self.assertIn('<strong>your bank account details</strong>', html)      # bolded phrase
        self.assertIn('Add your bank details', html)                           # button label
        self.assertIn('/scholarship/application"', html)                       # button href
        self.assertIn('<a href=', html)                                        # rendered as a button/link
        # plain-text fallback still carries the raw link
        self.assertIn('/scholarship/application', mail.outbox[0].body)


from django.core.management import call_command  # noqa: E402


class TestAwardStudentsBatch(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_batch_awards_listed_apps_without_email(self):
        # Default (flag OFF): the batch funds + awards but sends NO email (owner sends later).
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('100000'))
        a1 = _fundable_app(self.cohort, suffix='b1', award=Decimal('2000'))
        a2 = _fundable_app(self.cohort, suffix='b2', award=Decimal('3000'))
        mail.outbox = []
        with override_settings(SEED_SPONSOR_ID=str(s.id),
                               SEED_AWARD_APP_IDS=f'{a1.id}, {a2.id}'):
            call_command('award_students_batch')
        a1.refresh_from_db(); a2.refresh_from_db()
        self.assertEqual(a1.status, 'awarded')
        self.assertEqual(a2.status, 'awarded')
        self.assertEqual(Sponsorship.objects.filter(sponsor=s, status='offered').count(), 2)
        self.assertEqual(svc.sponsor_balance(s), Decimal('95000'))   # 100000 - 2000 - 3000
        self.assertEqual(len(mail.outbox), 0)                        # decoupled — no emails

    def test_batch_noop_without_env(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('100000'))
        a1 = _fundable_app(self.cohort, suffix='n1')
        mail.outbox = []
        call_command('award_students_batch')   # no SEED_* set
        a1.refresh_from_db()
        self.assertEqual(a1.status, 'recommended')
        self.assertEqual(len(mail.outbox), 0)

    def test_batch_skips_not_fundable(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('100000'))
        a1 = _fundable_app(self.cohort, suffix='s1', award=Decimal('2000'))
        a2 = _fundable_app(self.cohort, suffix='s2', award=None)   # not fundable (no amount)
        ScholarshipApplication.objects.filter(id=a2.id).update(award_amount=None)
        mail.outbox = []
        with override_settings(SEED_SPONSOR_ID=str(s.id),
                               SEED_AWARD_APP_IDS=f'{a1.id},{a2.id}'):
            call_command('award_students_batch')
        a1.refresh_from_db(); a2.refresh_from_db()
        self.assertEqual(a1.status, 'awarded')          # the fundable one went through
        self.assertEqual(a2.status, 'recommended')      # the other skipped, untouched
        self.assertEqual(len(mail.outbox), 0)           # flag OFF — no emails


class TestSendAwardOfferEmails(TestCase):
    """The TEMPORARY owner-controlled award-email send (decoupled from awarding)."""
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _awarded(self, suffix):
        s = _sponsor(uid=f'sp-{suffix}')
        Donation.objects.create(sponsor=s, amount=Decimal('5000'))
        app = _fundable_app(self.cohort, suffix=suffix, award=Decimal('2000'))
        svc.fund_student(s, app)   # → offered Sponsorship + 'awarded', no email (default)
        return app

    def test_sends_to_listed_awarded_apps(self):
        a1 = self._awarded('e1')
        a2 = self._awarded('e2')
        mail.outbox = []
        with override_settings(AWARD_EMAIL_APP_IDS=f'{a1.id},{a2.id}'):
            call_command('send_award_offer_emails')
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('Good news', mail.outbox[0].subject)

    def test_noop_without_env(self):
        self._awarded('e3')
        mail.outbox = []
        call_command('send_award_offer_emails')
        self.assertEqual(len(mail.outbox), 0)

    def test_skips_app_without_award(self):
        # A recommended (not-yet-awarded) app in the list is skipped — no stray email.
        not_awarded = _fundable_app(self.cohort, suffix='e4', award=Decimal('2000'))
        mail.outbox = []
        with override_settings(AWARD_EMAIL_APP_IDS=str(not_awarded.id)):
            call_command('send_award_offer_emails')
        self.assertEqual(len(mail.outbox), 0)


from datetime import timedelta  # noqa: E402


class TestReleaseAwardOfferEmails(TestCase):
    """Cool-off auto-release: award → email sent once it's COOLOFF hours old, idempotent,
    and skipped if the award was cancelled within the window."""
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _award(self, suffix, *, age_hours=0):
        s = _sponsor(uid=f'rl-{suffix}')
        Donation.objects.create(sponsor=s, amount=Decimal('5000'))
        app = _fundable_app(self.cohort, suffix=suffix, award=Decimal('2000'))
        sp = svc.fund_student(s, app)          # offered + 'awarded', no email
        if age_hours:
            Sponsorship.objects.filter(id=sp.id).update(
                offered_at=timezone.now() - timedelta(hours=age_hours))
        return sp

    def test_sends_once_past_cooloff_and_is_idempotent(self):
        sp = self._award('a', age_hours=25)    # older than the default 24h
        mail.outbox = []
        self.assertEqual(svc.release_award_offer_emails(), 1)
        sp.refresh_from_db()
        self.assertIsNotNone(sp.offer_emailed_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Good news', mail.outbox[0].subject)
        # second run: already emailed → nothing
        mail.outbox = []
        self.assertEqual(svc.release_award_offer_emails(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_skips_within_cooloff(self):
        self._award('b', age_hours=1)          # only 1h old, default cool-off 24h
        mail.outbox = []
        self.assertEqual(svc.release_award_offer_emails(), 0)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(AWARD_OFFER_EMAIL_COOLOFF_HOURS=0)
    def test_cooloff_zero_sends_on_next_run(self):
        self._award('c', age_hours=0)          # no cool-off → eligible immediately
        mail.outbox = []
        self.assertEqual(svc.release_award_offer_emails(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_skips_cancelled_award(self):
        sp = self._award('d', age_hours=25)
        Sponsorship.objects.filter(id=sp.id).update(status='cancelled')   # reconsidered in-window
        mail.outbox = []
        self.assertEqual(svc.release_award_offer_emails(), 0)
        self.assertEqual(len(mail.outbox), 0)
