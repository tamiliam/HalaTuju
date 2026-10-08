"""TD-376 and TD-377 (2026-10-08, the owner: "yes to both") — the last two roads past the "Born in"
floor that request #31's reviews found.

  * TD-376 — an award that falls through (`sponsorship._revert_to_pool`, now
    `award_revert.revert_to_pool`) put the case back at `recommended` whatever its IC said. A case
    whose CURRENT IC fails the intake's CURRENT rule now lands at `interviewed` (AWAITING QC),
    where the floor and its recorded override apply. Never a refusal: every one of the five callers
    — the sponsor's withdrawal, the student's decline, the hold, the release cron's fall-through
    and the lapse — still goes through.
  * TD-377 — QC accept never re-locks an IC, so a `recommended` case could carry an unlocked one
    and the student could change it before funding. Her own IC change is now refused, exactly as a
    locked IC is (same code, same words), while any application on the profile is `recommended` on
    a ruled intake, and `/profile` serves the padlock.
"""
import re
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.profile_claim import NRIC_LOCKED, handle_claim
from apps.scholarship import birth_state
from apps.scholarship import pool
from apps.scholarship import reopen as reopen_service
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Consent, Donation, ScholarshipApplication, Sponsor, SponsorProfile, Sponsorship,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_student,
    unique_suffix,
)

#: Every other requirement cleared, so a verdict can only turn on the birth-state rule.
ONLY_BIRTH = dict(min_spm_a_count=None, min_spm_bplus_count=None, min_spm_credit_count=None,
                  min_stpm_pngk=None, min_merit_score=None, income_ceiling=None,
                  per_capita_ceiling=None)

SABAH_IC = '080505-12-1234'
SABAH_47_IC = '080505-47-1234'
SELANGOR_IC = '080505-10-1234'
REVERT_LOG = 'apps.scholarship.award_revert'


def _sponsor():
    return Sponsor.objects.create(
        supabase_user_id=unique_suffix('td376-sp-'), name='J',
        email=f'{unique_suffix("td376")}@x.test', phone='0', source='friend',
        consent_at=timezone.now(), status='approved')


def _awarded(states=('sabah',), nric=SABAH_IC, **sponsorship):
    """An `awarded` case and the sponsorship that holds it. The IC QC saw is Sabah's."""
    app = make_application('awarded', student=make_student(nric=nric),
                           cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=list(states)),
                           award_amount=Decimal('3000'))
    sp = Sponsorship.objects.create(application=app, sponsor=_sponsor(), amount=Decimal('3000'),
                                    **{'status': 'offered', **sponsorship})
    return app, sp


def _swap_ic(app, nric):
    """What a super's lock release at `awarded` (TD-371 allows it) lets the student do."""
    app.profile.nric, app.profile.nric_verified = nric, False
    app.profile.save(update_fields=['nric', 'nric_verified'])


def _reverify(app, admin=None):
    """The reviewer verify-accepts the IC again — which re-locks it and runs the duplicate
    verified-IC check. The completeness gate is not what these tests are about, so it is held
    open."""
    admin = admin or make_admin('super', super_admin=True)
    with override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET), \
            mock.patch('apps.scholarship.views_admin.applications.application_completeness',
                       return_value={'complete': True}):
        r = authed_client(admin).post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/verify-accept/', {}, format='json')
    assert r.status_code == 200, r.content
    app.refresh_from_db()
    app.profile.refresh_from_db()
    assert app.profile.nric_verified and app.status == 'interviewed'


# ── TD-376 ────────────────────────────────────────────────────────────────────────────────────
class TestAFailingRevertLandsAtQc(TestCase):
    def test_the_sponsors_withdrawal_lands_a_failing_case_at_awaiting_qc(self):
        app, sp = _awarded()
        _swap_ic(app, SELANGOR_IC)
        with self.assertLogs(REVERT_LOG, level='INFO') as logs:
            svc.cancel_offer(sp.sponsor, sp.id)                 # never refused
        app.refresh_from_db()
        sp.refresh_from_db()
        self.assertEqual((app.status, sp.status), ('interviewed', 'cancelled'))
        line = [m for m in logs.output if 'AUDIT revert_to_qc_birth_state' in m]
        self.assertEqual(len(line), 1)
        self.assertIn(f'app_id={app.id} from=awarded to=interviewed reason=ic_unlocked,rule_fails',
                      line[0])
        self.assertIsNone(re.search(r'\d{6}-?\d{2}-?\d{4}', line[0]))
        for name in ('sabah', 'selangor', 'Sabah', 'Selangor'):
            self.assertNotIn(name, line[0])

    def test_it_is_neither_visible_nor_fundable_and_qc_can_find_it(self):
        app, sp = _awarded()
        _swap_ic(app, SELANGOR_IC)
        svc.cancel_offer(sp.sponsor, sp.id)
        app.refresh_from_db()
        self.assertTrue(app.sponsor_profile.anon_published)      # unchanged, and held back by status
        self.assertFalse(pool.is_pool_eligible(app))
        self.assertFalse(svc.is_fundable(app))
        for qs in (pool.eligible_pool_queryset(ScholarshipApplication),
                   pool.display_pool_queryset(ScholarshipApplication)):
            self.assertFalse(qs.filter(pk=app.pk).exists())
        with override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET):
            r = authed_client(make_admin('super', super_admin=True)).get(
                '/api/v1/admin/scholarship/applications/?status=interviewed')
        self.assertEqual(r.status_code, 200)
        self.assertIn(app.id, [row['id'] for row in r.json()['applications']])

    def test_a_locked_passing_ic_and_an_unruled_intake_revert_exactly_as_before(self):
        # Ruled + the IC QC saw, still LOCKED (the awarded factory took the lock at verify-accept);
        # unruled + an IC changed after a release (unlocked, and failing a rule nobody set).
        # A locked IC is unique, so each subtest's student holds her own number.
        for states, nric, swap in ((('sabah',), '080501-12-1234', None),
                                   ((), '080502-12-1234', SELANGOR_IC)):
            with self.subTest(states=states, swap=swap):
                app, sp = _awarded(states=states, nric=nric)
                if swap:
                    _swap_ic(app, swap)
                else:
                    self.assertTrue(app.profile.nric_verified)
                with self.assertNoLogs(REVERT_LOG, level='INFO'):
                    svc.cancel_offer(sp.sponsor, sp.id)
                app.refresh_from_db()
                self.assertEqual(app.status, 'recommended')
                self.assertTrue(svc.is_fundable(app))

    def test_an_unlocked_ic_that_still_passes_is_diverted_too(self):
        # Review round 7: a lock released at `awarded`, the IC unchanged (or changed to another
        # Sabah code) — it passes, but it is UNLOCKED, and every other door into `recommended` on
        # a ruled intake needs a locked IC. So it goes to QC; the reviewer re-locks it there.
        for day, code in ((1, '12'), (2, '47')):
            with self.subTest(code=code):
                # A locked IC is unique, so each subtest's student holds her own number.
                app, sp = _awarded(nric=f'08050{day}-12-1234')
                _swap_ic(app, f'08050{day}-{code}-1234')
                with self.assertLogs(REVERT_LOG, level='INFO') as logs:
                    svc.cancel_offer(sp.sponsor, sp.id)
                app.refresh_from_db()
                self.assertEqual(app.status, 'interviewed')
                self.assertFalse(svc.is_fundable(app))
                self.assertTrue(any(f'app_id={app.id} from=awarded to=interviewed '
                                    f'reason=ic_unlocked' in m and 'rule_fails' not in m
                                    for m in logs.output), logs.output)
                _reverify(app)                                  # the way back: re-lock, then QC


class TestEveryCallerStillWorks(TestCase):
    """Each of `_revert_to_pool`'s five callers, with a failing IC: it goes through, and the case
    lands at AWAITING QC."""

    def _lands_at_qc(self, app):
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertIsNone(app.award_due_at)

    def test_the_students_decline(self):
        app, sp = _awarded()
        _swap_ic(app, SELANGOR_IC)
        svc.respond_to_award(app, action='decline')
        sp.refresh_from_db()
        self.assertEqual(sp.status, 'lapsed')
        self._lands_at_qc(app)

    def test_the_hold(self):
        app, sp = _awarded(status='active')
        app.award_due_at = timezone.now() + timedelta(days=3)
        app.save(update_fields=['award_due_at'])
        _swap_ic(app, SELANGOR_IC)
        self.assertTrue(svc.hold_pending_award(app))
        sp.refresh_from_db()
        self.assertEqual(sp.status, 'lapsed')
        self._lands_at_qc(app)

    def test_the_release_crons_fall_through(self):
        app, sp = _awarded(status='lapsed')                     # the acceptance did not hold
        app.award_due_at = timezone.now() - timedelta(hours=1)
        app.save(update_fields=['award_due_at'])
        _swap_ic(app, SELANGOR_IC)
        self.assertEqual(svc.release_pending_awards(), 0)
        self._lands_at_qc(app)

    def test_the_lapse(self):
        app, sp = _awarded(accept_deadline=timezone.now() - timedelta(days=2))
        _swap_ic(app, SELANGOR_IC)
        self.assertEqual(svc.lapse_expired_offers()['lapsed'], 1)
        sp.refresh_from_db()
        self.assertEqual(sp.status, 'lapsed')
        self._lands_at_qc(app)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestQcThenAppliesTheFloor(TestCase):
    def setUp(self):
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_refused_without_a_reason_and_accepted_with_one(self):
        app, sp = _awarded()
        _swap_ic(app, SELANGOR_IC)
        svc.cancel_offer(sp.sponsor, sp.id)
        qc = make_admin('qc', owning_org=app.cohort.owning_organisation)
        url = f'/api/v1/admin/scholarship/applications/{app.pk}/qc-decision/'
        # The changed IC is UNLOCKED (that is how it changed), so QC cannot accept it at all —
        # a reason or not — until the reviewer verify-accepts it again and it is locked.
        r = authed_client(qc).post(url, {'decision': 'accept', 'override_reason': 'Seen.'},
                                   format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'birth_state_ic_unlocked'))
        _reverify(app)
        r = authed_client(qc).post(url, {'decision': 'accept'}, format='json')
        self.assertEqual((r.status_code, r.json()['code'], r.json()['facts']),
                         (400, 'verdict_gap_floor', ['birth_state']))
        r = authed_client(qc).post(url, {'decision': 'accept',
                                         'override_reason': 'Birth certificate shows Tawau.'},
                                   format='json')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual((app.status, app.qc_override_reason),
                         ('recommended', 'Birth certificate shows Tawau.'))
        self.assertTrue(svc.is_fundable(app))


# ── TD-377 ────────────────────────────────────────────────────────────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestHerOwnIcIsHeldAtRecommended(TestCase):
    """Since the TD-376/377 review no door lets a ruled case INTO `recommended` with an unlocked
    IC (`TestTd377sTwoRoutesAreClosedAtTheDoor`), so this hold is the second line: it covers a case
    that was already `recommended` unlocked before that stop shipped, and any future door."""

    def _unlocked(self, stage='recommended', states=('sabah',), nric=SABAH_IC):
        student = make_student(nric=nric)
        app = make_application(stage, student=student,
                               cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=list(states)))
        student.refresh_from_db()
        student.nric_verified = False                           # a pre-existing unlocked row
        student.save(update_fields=['nric_verified'])
        return app, student

    def _change(self, student, nric=SELANGOR_IC):
        uid = student.supabase_user_id
        return handle_claim(uid, uid, {'nric': nric})

    def test_refused_exactly_as_a_locked_ic_is(self):
        app, student = self._unlocked()
        self.assertEqual(self._change(student), (NRIC_LOCKED, 403))
        self.assertEqual(NRIC_LOCKED, {
            'error': 'Your NRIC is verified and locked. Contact support to change it.',
            'code': 'nric_locked'})
        student.refresh_from_db()
        self.assertEqual(student.nric, SABAH_IC)
        # The very payload a locked IC gets.
        locked = make_student(nric='080606-12-1234', nric_verified=True)
        self.assertEqual(self._change(locked, '080606-10-1234'), (NRIC_LOCKED, 403))

    def test_the_profile_shows_the_padlock(self):
        app, student = self._unlocked()
        body = authed_client(student.supabase_user_id).get('/api/v1/profile/').json()
        self.assertEqual((body['nric_locked'], body['nric_verified']), (True, False))

    def test_allowed_when_the_intake_has_no_rule(self):
        app, student = self._unlocked(states=())
        self.assertEqual(self._change(student), ({'status': 'created'}, 200))
        body = authed_client(student.supabase_user_id).get('/api/v1/profile/').json()
        self.assertIs(body['nric_locked'], False)

    def test_allowed_at_every_other_status(self):
        for day, stage in enumerate(('shortlisted', 'interviewing', 'awarded', 'active'), 1):
            with self.subTest(stage=stage):
                # One pair of ICs per student: a number another profile holds is a claim instead.
                app, student = self._unlocked(stage=stage, nric=f'08050{day}-12-1234')
                self.assertEqual(self._change(student, f'08050{day}-10-1234'),
                                 ({'status': 'created'}, 200))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTd377sTwoRoutesAreClosedAtTheDoor(TestCase):
    """TD-377's two routes left a `recommended` case with an UNLOCKED IC. The TD-376/377 review
    closed both at the door into `recommended`: on a ruled intake QC accept and a
    reopen-cancel that restores `recommended` need a LOCKED IC (`birth_state_ic_unlocked`, no
    override). Verify-accept re-locks it. So a ruled `recommended` case now always carries a
    locked IC, and from there to `awarded` only a super's deliberate release can unlock it."""

    def setUp(self):
        self.super = _super = make_admin('super', super_admin=True)
        self.client = authed_client(_super)
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, app, action, body=None):
        return self.client.post(f'/api/v1/admin/scholarship/applications/{app.pk}/{action}/',
                                body or {}, format='json')

    def _release(self, app):
        r = self._post(app, 'release-nric-lock', {'reason': 'Typed wrong.'})
        self.assertEqual(r.status_code, 200, r.content)

    def _refused_unlocked(self, r):
        self.assertEqual((r.status_code, r.json()['code'], r.json()['error']),
                         (400, 'birth_state_ic_unlocked', birth_state.IC_UNLOCKED_MESSAGE))

    def test_the_reviewers_scenario_end_to_end(self):
        app = make_application('awaiting_qc', outcome='recommend', student=make_student(nric=SABAH_IC),
                               cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah']))
        self._release(app)                                     # allowed: not yet recommended
        for body in ({'decision': 'accept'},
                     {'decision': 'accept', 'override_reason': 'Birth certificate seen.'}):
            with self.subTest(body=body):
                self._refused_unlocked(self._post(app, 'qc-decision', body))
                app.refresh_from_db()
                self.assertEqual(app.status, 'interviewed')    # nothing moved
        _reverify(app, self.super)                             # re-locks the IC
        self.assertEqual(self._post(app, 'qc-decision', {'decision': 'accept'}).status_code, 200)
        app.refresh_from_db()
        app.profile.refresh_from_db()
        self.assertEqual((app.status, app.profile.nric_verified), ('recommended', True))
        # A sponsor funds it: `awarded`, still locked — her own change is the locked refusal.
        SponsorProfile.objects.create(application=app, anon_markdown='Determined.',
                                      anon_published=True, anon_published_at=timezone.now())
        Consent.objects.create(application=app, consent_type='share_with_sponsors', version='t',
                               is_active=True)
        sponsor = _sponsor()
        Donation.objects.create(sponsor=sponsor, amount=Decimal('5000'),
                                programme=app.cohort.programme)
        svc.fund_student(sponsor, app)
        app.refresh_from_db()
        self.assertEqual(app.status, 'awarded')
        uid = app.profile.supabase_user_id
        self.assertEqual(handle_claim(uid, uid, {'nric': SELANGOR_IC}), (NRIC_LOCKED, 403))
        app.profile.refresh_from_db()
        self.assertEqual((app.profile.nric, app.profile.nric_verified), (SABAH_IC, True))

    def test_reopen_release_then_cancel_needs_the_ic_locked_again(self):
        app = make_application('recommended', student=make_student(nric=SABAH_IC),
                               cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah']))
        reopen_service.reopen_decision(app, by_admin=self.super, reason='Re-check the income.')
        self._release(app)                                     # allowed at `interviewed`
        self._refused_unlocked(self._post(app, 'cancel-reopen'))
        app.refresh_from_db()
        self.assertEqual((app.status, app.decision_reopened_at is not None), ('interviewed', True))
        _reverify(app, self.super)                             # verify-accept DURING the reopen
        self.assertEqual(self._post(app, 'cancel-reopen').status_code, 200)
        app.refresh_from_db()
        app.profile.refresh_from_db()
        self.assertEqual((app.status, app.profile.nric_verified), ('recommended', True))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheLockedIcStopIsNarrow(TestCase):
    """The stop binds QC ACCEPT to `recommended` and a cancel restoring `recommended`, on a ruled
    intake only. The decline-confirm path, unruled intakes and every other cancel are unchanged."""

    def setUp(self):
        self.super = make_admin('super', super_admin=True)
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _awaiting_qc_unlocked(self, states, outcome='recommend', nric=SABAH_IC):
        app = make_application('awaiting_qc', outcome=outcome, student=make_student(nric=nric),
                               cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=list(states)))
        app.profile.nric_verified = False
        app.profile.save(update_fields=['nric_verified'])
        return app

    def _qc(self, app, **body):
        return authed_client(self.super).post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/qc-decision/',
            {'decision': 'accept', **body}, format='json')

    def test_accept_allowed_unlocked_on_an_unruled_intake(self):
        app = self._awaiting_qc_unlocked([])
        self.assertEqual(self._qc(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')

    @override_settings(DECLINE_QC_COOLOFF_HOURS=24)
    def test_confirming_a_decline_is_unaffected(self):
        app = self._awaiting_qc_unlocked(['sabah'], outcome='decline')   # the decline road: no lock
        self.assertFalse(app.profile.nric_verified)
        self.assertEqual(self._qc(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual((app.status, app.rejection_category), ('rejected', 'interview'))

    def test_a_cancel_not_restoring_recommended_is_unaffected(self):
        # A QC reopen (interviewed -> interviewing) cancels back to AWAITING QC.
        app = make_application('awaiting_qc', outcome='recommend', student=make_student(nric=SABAH_IC),
                               cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah']))
        reopen_service.reopen_decision(app, by_admin=self.super, reason='Missing a payslip.')
        app.profile.nric_verified = False
        app.profile.save(update_fields=['nric_verified'])
        r = authed_client(self.super).post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/cancel-reopen/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
