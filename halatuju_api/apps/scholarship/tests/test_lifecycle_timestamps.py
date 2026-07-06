"""Lifecycle transition stamps — recommended_at / awarded_at / active_at / maintenance_at.

These record the DATE an application FIRST reached each post-shortlist milestone and drive the
officer-cockpit header timeline. The invariant is *set-if-null*: a reopen / unfund-then-refund
revisits a state but must NOT overwrite the original date.

Field-name wiring at each call site is already guarded by that transition's own suite (a typo'd
field makes ``stamp_first`` raise). Here we assert the stamp VALUE is set and never clobbered.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship import disbursement
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Consent, Donation, ScholarshipApplication, ScholarshipCohort, Sponsor, SponsorProfile,
)


def _cohort():
    return ScholarshipCohort.objects.create(code='lc', name='B40', year=2026)


def _app(cohort, status='recommended', suffix='1'):
    p = StudentProfile.objects.create(
        supabase_user_id=f'lc-{suffix}', name='Zxq Student', exam_type='spm', grades={'bm': 'A'},
        contact_email='s@secret.example')
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=p, status=status, award_amount=Decimal('3000'),
        notify_email='s@secret.example')
    SponsorProfile.objects.create(application=app, anon_markdown='determined', anon_published=True)
    Consent.objects.create(application=app, consent_type='share_with_sponsors', version='e', is_active=True)
    return app


def _sponsor(uid='lc-spon', balance=Decimal('3000')):
    s = Sponsor.objects.create(
        supabase_user_id=uid, name='Jane', email='jane@sponsor.example', phone='0123',
        source='friend', consent_at=timezone.now(), status='approved')
    if balance:
        Donation.objects.create(sponsor=s, amount=balance)
    return s


class TestStampFirst(TestCase):
    """The model helper — set-if-null, and it reports whether it stamped."""

    def setUp(self):
        self.app = _app(_cohort())

    def test_sets_when_null_and_reports_the_field(self):
        self.assertIsNone(self.app.awarded_at)
        self.assertEqual(self.app.stamp_first('awarded_at'), 'awarded_at')
        self.assertIsNotNone(self.app.awarded_at)

    def test_does_not_overwrite_when_already_set(self):
        first = timezone.now() - timezone.timedelta(days=10)
        self.app.awarded_at = first
        self.assertIsNone(self.app.stamp_first('awarded_at'))  # no stamp → returns None
        self.assertEqual(self.app.awarded_at, first)           # original preserved


class TestTransitionStamps(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def test_fund_stamps_awarded_at(self):
        app = _app(self.cohort, status='recommended', suffix='fund')
        svc.fund_student(_sponsor(), app)
        app.refresh_from_db()
        self.assertEqual(app.status, 'awarded')
        self.assertIsNotNone(app.awarded_at)

    def test_fund_does_not_overwrite_an_existing_awarded_at(self):
        # A re-award (after an earlier award was reverted) must keep the ORIGINAL date.
        earlier = timezone.now() - timezone.timedelta(days=30)
        app = _app(self.cohort, status='recommended', suffix='reaward')
        app.awarded_at = earlier
        app.save(update_fields=['awarded_at'])
        svc.fund_student(_sponsor(uid='lc-spon2'), app)
        app.refresh_from_db()
        self.assertEqual(app.status, 'awarded')
        self.assertEqual(app.awarded_at, earlier)

    def test_finalise_award_stamps_active_at(self):
        app = _app(self.cohort, status='awarded', suffix='act')
        svc._finalise_award(app)
        app.refresh_from_db()
        self.assertEqual(app.status, 'active')
        self.assertIsNotNone(app.active_at)

    def test_first_payout_stamps_maintenance_at(self):
        app = _app(self.cohort, status='active', suffix='maint')
        disbursement._flip_to_maintenance(app)
        app.refresh_from_db()
        self.assertEqual(app.status, 'maintenance')
        self.assertIsNotNone(app.maintenance_at)
        stamped = app.maintenance_at
        # Idempotent: a second flip (already in maintenance) is a no-op and never re-stamps.
        disbursement._flip_to_maintenance(app)
        app.refresh_from_db()
        self.assertEqual(app.maintenance_at, stamped)
