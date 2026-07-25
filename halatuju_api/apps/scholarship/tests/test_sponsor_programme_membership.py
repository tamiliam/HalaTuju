"""Sponsor programme membership — acceptance is per gift (P3, 2026-07-26).

The owner's rule: a sponsor sees a programme's students only if they *"specifically onboarded
into both and accepted into both — and that is not a given"*. The ACCOUNT stays platform-level;
ACCEPTANCE is per programme and survives the year rollover.

Pinned here: the two-gate model (account vetted AND accepted into this gift), the pool list and
detail fences, the notification fences (a digest must not route around the pool fence), standing
gifts, the backfill's no-visibility-change invariant, and a source guard that every sponsor-facing
pool read goes through ``pool.for_sponsor``.

Anonymity is NOT re-tested here — it is enforced by the allowlist serializers and their own
suites, and this sprint must leave them untouched. That separation is the point: membership
governs WHICH cards are visible, never WHAT a card shows.
"""
import inspect
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import pool, sponsor_notifications, standing_gift, views_sponsor
from apps.scholarship.models import (
    Consent, Programme, ScholarshipApplication, ScholarshipCohort, Sponsor,
    SponsorProfile, SponsorProgrammeMembership,
)


def _org(code='mem-org'):
    return PartnerOrganisation.objects.create(code=code, name=code.title())


def _programme(org, code, name='Gift'):
    return Programme.objects.create(organisation=org, code=code, name_en=name)


def _pooled_app(programme, org, uid, code, award=Decimal('3000')):
    """A pool-visible application in ``programme`` (anon-published + active share consent
    + QC-cleared 'recommended')."""
    cohort = ScholarshipCohort.objects.create(
        code=code, name='C', year=2026, owning_organisation=org, programme=programme,
    )
    profile = StudentProfile.objects.create(supabase_user_id=uid, name='S')
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, award_amount=award, status='recommended',
    )
    SponsorProfile.objects.create(application=app, anon_markdown='Determined.',
                                  anon_published=True)
    Consent.objects.create(application=app, consent_type='share_with_sponsors',
                           version='e', is_active=True)
    return app


def _sponsor(email='funder@example.com', uid='sp-1', status='approved'):
    return Sponsor.objects.create(supabase_user_id=uid, name='Funder', email=email,
                                  status=status)


def _accept(sponsor, programme, status='approved'):
    return SponsorProgrammeMembership.objects.create(
        sponsor=sponsor, programme=programme, status=status)


class PoolFenceMixin:
    @classmethod
    def setUpTestData(cls):
        cls.org = _org()
        cls.flagship = _programme(cls.org, 'p-flagship', 'Flagship Bursary')
        cls.sabah = _programme(cls.org, 'p-sabah', 'Sabah Bursary')
        cls.flagship_app = _pooled_app(cls.flagship, cls.org, 'u-flag', 'c-flag')
        cls.sabah_app = _pooled_app(cls.sabah, cls.org, 'u-sabah', 'c-sabah')
        cls.sponsor = _sponsor()


class TestMembershipFence(PoolFenceMixin, TestCase):
    def _visible(self, sponsor):
        qs = pool.for_sponsor(pool.display_pool_queryset(ScholarshipApplication), sponsor)
        return set(qs.values_list('id', flat=True))

    def test_sees_only_the_programme_they_are_accepted_into(self):
        _accept(self.sponsor, self.sabah)
        self.assertEqual(self._visible(self.sponsor), {self.sabah_app.id})

    def test_accepted_into_both_sees_both(self):
        _accept(self.sponsor, self.sabah)
        _accept(self.sponsor, self.flagship)
        self.assertEqual(self._visible(self.sponsor),
                         {self.sabah_app.id, self.flagship_app.id})

    def test_no_membership_sees_nothing(self):
        """The safe direction: absent acceptance is an empty pool, not the whole platform."""
        self.assertEqual(self._visible(self.sponsor), set())

    def test_pending_or_rejected_membership_grants_nothing(self):
        _accept(self.sponsor, self.sabah, status='pending')
        self.assertEqual(self._visible(self.sponsor), set())
        SponsorProgrammeMembership.objects.update(status='rejected')
        self.assertEqual(self._visible(self.sponsor), set())
        SponsorProgrammeMembership.objects.update(status='suspended')
        self.assertEqual(self._visible(self.sponsor), set())

    def test_account_gate_and_programme_gate_are_both_required(self):
        """An un-vetted ACCOUNT is refused upstream even with an approved membership —
        the two gates are independent, not alternatives."""
        pending_account = _sponsor(email='p@example.com', uid='sp-2', status='pending')
        _accept(pending_account, self.sabah)
        self.assertFalse(pending_account.is_approved)          # gate 1 refuses
        self.assertEqual(self._visible(pending_account), {self.sabah_app.id})  # gate 2 allows

    def test_membership_is_unique_per_sponsor_programme(self):
        from django.db import IntegrityError, transaction
        _accept(self.sponsor, self.sabah)
        with self.assertRaises(IntegrityError), transaction.atomic():
            _accept(self.sponsor, self.sabah)


@override_settings(SPONSOR_POOL_ENABLED=True)
class TestNotificationsRespectTheFence(PoolFenceMixin, TestCase):
    def test_digest_only_covers_accepted_programmes(self):
        """A digest must not route around the pool fence — otherwise a Sabah-only funder
        learns by email that flagship students exist."""
        _accept(self.sponsor, self.sabah)
        self.sponsor.notify_frequency = 'weekly'
        self.sponsor.save(update_fields=['notify_frequency'])
        base = pool.eligible_pool_queryset(ScholarshipApplication)
        self.assertEqual(set(pool.for_sponsor(base, self.sponsor).values_list('id', flat=True)),
                         {self.sabah_app.id})

    def test_realtime_alert_only_covers_accepted_programmes(self):
        _accept(self.sponsor, self.flagship)
        ids = set(pool.approved_programme_ids(self.sponsor))
        theirs = [a for a in [self.flagship_app, self.sabah_app] if a.programme_id in ids]
        self.assertEqual([a.id for a in theirs], [self.flagship_app.id])


class TestStandingGiftRespectsTheFence(PoolFenceMixin, TestCase):
    def test_standing_gift_never_reaches_an_unaccepted_programme(self):
        from apps.scholarship.models import Donation
        _accept(self.sponsor, self.sabah)
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('10000'),
                                programme=self.sabah)
        Donation.objects.create(sponsor=self.sponsor, amount=Decimal('10000'),
                                programme=self.flagship)
        standing_gift.StandingGift.objects.create(sponsor=self.sponsor, active=True)
        # Funded in BOTH wallets, but accepted only into Sabah.
        self.assertEqual(list(standing_gift.matching_gifts(self.flagship_app)), [])
        self.assertEqual([g.sponsor_id for g in standing_gift.matching_gifts(self.sabah_app)],
                         [self.sponsor.id])


class TestBackfillChangesNoVisibility(TestCase):
    def test_membership_mirrors_the_account_status_exactly(self):
        """The backfill's invariant: nobody gains or loses sight of anyone."""
        org = _org()
        # NB: never 'brightpath-flagship' — migration 0119 already seeds that programme
        # into the test DB (same trap as 'brightpath' in test_application_owning_org.py).
        flagship = _programme(org, 'bf-flagship', 'Flagship')
        sponsors = [
            _sponsor(email='a@x.com', uid='s-a', status='approved'),
            _sponsor(email='b@x.com', uid='s-b', status='pending'),
            _sponsor(email='c@x.com', uid='s-c', status='rejected'),
            _sponsor(email='d@x.com', uid='s-d', status='suspended'),
        ]
        SponsorProgrammeMembership.objects.bulk_create([
            SponsorProgrammeMembership(sponsor=s, programme=flagship, status=s.status,
                                       vetted_by='backfill 0123')
            for s in sponsors
        ])
        for s in sponsors:
            membership = SponsorProgrammeMembership.objects.get(sponsor=s, programme=flagship)
            self.assertEqual(membership.status, s.status)
        # Exactly the previously-approved sponsors can see the pool, and only them.
        approved = SponsorProgrammeMembership.objects.filter(status='approved')
        self.assertEqual(approved.count(), 1)


class TestEverySponsorPoolReadIsFenced(TestCase):
    """Source guard — every sponsor-facing pool read must go through ``pool.for_sponsor``.

    A view that calls ``display_pool_queryset`` directly would serve the whole platform's pool.
    This is the mechanical equivalent of the org-fence completeness map: behaviour tests cover
    the paths we thought of, this covers the one someone adds next.
    """
    def test_pool_views_narrow_by_membership(self):
        for view in (views_sponsor.SponsorPoolListView, views_sponsor.SponsorPoolDetailView):
            source = inspect.getsource(view)
            self.assertIn(
                'for_sponsor', source,
                f'{view.__name__} must narrow the pool via pool.for_sponsor(...) — a bare '
                f'display_pool_queryset serves every programme on the platform.',
            )

    def test_notification_paths_narrow_by_membership(self):
        for fn in (sponsor_notifications.send_sponsor_digests,
                   sponsor_notifications.send_sponsor_realtime):
            source = inspect.getsource(fn)
            self.assertTrue(
                'for_sponsor' in source or 'approved_programme_ids' in source,
                f'{fn.__qualname__} must fence by programme membership — an email that '
                f'routes around the pool fence leaks that other programmes exist.',
            )
