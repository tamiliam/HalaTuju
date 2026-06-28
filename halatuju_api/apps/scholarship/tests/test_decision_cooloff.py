"""Decision cool-off (#13 decline, #14 award): the comm is held SILENTLY for a window, an
admin can cancel/hold within it, and the release cron reveals/finalises once due. Default is
OFF (0 days) — these force it on with override_settings."""
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import services
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Consent, Donation, ScholarshipApplication, ScholarshipCohort, Sponsor, SponsorProfile,
)


def _cohort():
    return ScholarshipCohort.objects.create(code='c', name='B40 Programme', year=2026)


@override_settings(DECLINE_COOLOFF_DAYS=7)
class TestDeclineCooloff(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = _cohort()
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='cd-admin', role='reviewer', is_active=True, name='A', email='admin@x.com')

    def _app(self, status='interviewed'):
        p = StudentProfile.objects.create(supabase_user_id=f'u{StudentProfile.objects.count()}')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status=status, notify_email='stu@x.com')

    def test_decline_is_immediate_but_email_embargoed(self):
        app = self._app()
        n = len(mail.outbox)
        services.admin_reject(app, self.admin, 'interview')
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')                # decision is IMMEDIATE
        self.assertEqual(app.rejection_category, 'interview')
        self.assertEqual(app.rejected_by, 'admin@x.com')
        self.assertIsNotNone(app.rejected_at)
        self.assertEqual(app.pending_rejection_category, 'interview')  # email still pending
        self.assertIsNotNone(app.decline_due_at)
        self.assertEqual(app.pending_decline_by, 'admin@x.com')
        self.assertIsNone(app.decision_email_sent_at)
        self.assertEqual(len(mail.outbox), n)                   # email EMBARGOED — not sent yet

    def test_student_sees_in_review_while_email_embargoed(self):
        from apps.scholarship.serializers import ApplicationReadSerializer
        app = self._app()
        services.admin_reject(app, self.admin, 'interview')
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')                # real (admin) status
        self.assertEqual(ApplicationReadSerializer(app).data['status'], 'interviewed')  # masked for student

    def test_student_does_not_see_accepted_status(self):
        # 'accepted' is an internal verification decision a super-admin can still reverse
        # (reopen -> interviewed -> possibly declined), so the student must keep seeing the
        # in-review state. The admin cockpit uses a different serializer and sees the real
        # 'accepted'. Good news reaches the student only via a concrete award offer.
        from apps.scholarship.serializers import ApplicationReadSerializer
        app = self._app(status='accepted')
        self.assertEqual(app.status, 'accepted')                # real (admin) status
        self.assertEqual(ApplicationReadSerializer(app).data['status'], 'interviewed')  # masked for student

    def test_cancel_pending_decline(self):
        app = self._app()
        services.admin_reject(app, self.admin, 'interview')
        self.assertTrue(services.cancel_pending_decline(app))
        app.refresh_from_db()
        self.assertIsNone(app.decline_due_at)
        self.assertEqual(app.pending_rejection_category, '')
        self.assertEqual(app.status, 'interviewed')             # student never knew

    def test_release_after_due_rejects_and_emails(self):
        app = self._app()
        services.admin_reject(app, self.admin, 'interview')
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            decline_due_at=timezone.now() - timedelta(minutes=1))   # backdate past due
        n = len(mail.outbox)
        self.assertEqual(services.release_pending_declines(), 1)
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')
        self.assertEqual(app.rejection_category, 'interview')
        self.assertEqual(app.rejected_by, 'admin@x.com')
        self.assertIsNone(app.decline_due_at)
        self.assertEqual(app.pending_rejection_category, '')
        self.assertEqual(len(mail.outbox), n + 1)               # decline email sent
        self.assertIn('documents', mail.outbox[-1].body.lower())

    def test_not_yet_due_email_not_sent(self):
        app = self._app()
        services.admin_reject(app, self.admin, 'interview')      # email due in 7 days
        self.assertEqual(services.release_pending_declines(), 0)
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')                # already rejected (immediate)
        self.assertIsNone(app.decision_email_sent_at)           # but the email is still embargoed

    def test_cancelled_decline_never_releases(self):
        app = self._app()
        services.admin_reject(app, self.admin, 'interview')
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            decline_due_at=timezone.now() - timedelta(minutes=1))
        services.cancel_pending_decline(app)
        self.assertEqual(services.release_pending_declines(), 0)


@override_settings(DECLINE_COOLOFF_DAYS=0)
class TestDeclineCooloffDisabled(TestCase):
    def test_immediate_reject_when_disabled(self):
        cohort = _cohort()
        admin = PartnerAdmin.objects.create(
            supabase_user_id='cd0-admin', role='reviewer', is_active=True, name='A', email='a@x.com')
        p = StudentProfile.objects.create(supabase_user_id='u0')
        app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=p, status='interviewed', notify_email='stu@x.com')
        services.admin_reject(app, admin, 'interview')
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')                # immediate (old behaviour)
        self.assertIsNone(app.decline_due_at)


@override_settings(AWARD_COOLOFF_DAYS=2)
class TestAwardCooloff(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = _cohort()

    def _offered_app(self):
        n = StudentProfile.objects.count()
        p = StudentProfile.objects.create(
            supabase_user_id=f'a{n}', name='Zxq', nric='000101-10-1233',
            grades={'bm': 'A'}, contact_email='s@x.com')
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='accepted', award_amount=Decimal('3000'),
            notify_email='s@x.com')
        SponsorProfile.objects.create(application=app, anon_markdown='x', anon_published=True)
        Consent.objects.create(application=app, consent_type='share_with_sponsors', version='e', is_active=True)
        s = Sponsor.objects.create(
            supabase_user_id=f'sp{n}', name='Jane', email=f'j{n}@x.com',
            phone='0123', source='friend', consent_at=timezone.now(), status='approved')
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        svc.fund_student(s, app)            # → 'offered'
        return app, s

    def test_accept_is_held_not_confirmed(self):
        app, s = self._offered_app()
        n = len(mail.outbox)
        sp = svc.respond_to_award(app, action='accept')
        app.refresh_from_db()
        self.assertEqual(sp.status, 'active')                   # money committed
        self.assertEqual(app.status, 'accepted')                # NOT 'sponsored' yet
        self.assertIsNotNone(app.award_due_at)
        self.assertEqual(len(mail.outbox), n)                   # no confirmed email yet
        self.assertEqual(svc.sponsor_balance(s), Decimal('0'))  # held

    def test_hold_reverts_acceptance_and_frees_money(self):
        app, s = self._offered_app()
        svc.respond_to_award(app, action='accept')
        self.assertTrue(svc.hold_pending_award(app))
        app.refresh_from_db()
        self.assertIsNone(app.award_due_at)
        self.assertEqual(app.status, 'accepted')
        self.assertEqual(svc.sponsor_balance(s), Decimal('3000'))   # returned to sponsor
        self.assertFalse(app.sponsorships.filter(status='active').exists())

    def test_release_after_due_confirms_and_emails(self):
        app, _s = self._offered_app()
        svc.respond_to_award(app, action='accept')
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            award_due_at=timezone.now() - timedelta(minutes=1))
        n = len(mail.outbox)
        self.assertEqual(svc.release_pending_awards(), 1)
        app.refresh_from_db()
        self.assertEqual(app.status, 'sponsored')
        self.assertIsNone(app.award_due_at)
        self.assertEqual(len(mail.outbox), n + 1)
        self.assertIn('confirmed', mail.outbox[-1].subject.lower())

    def test_held_award_does_not_release(self):
        app, _s = self._offered_app()
        svc.respond_to_award(app, action='accept')
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            award_due_at=timezone.now() - timedelta(minutes=1))
        svc.hold_pending_award(app)
        self.assertEqual(svc.release_pending_awards(), 0)
