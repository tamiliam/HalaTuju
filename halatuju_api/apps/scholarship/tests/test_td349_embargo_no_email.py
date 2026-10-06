"""TD-349 (2026-10-06): every way out of a decline's email embargo sends before it unmasks.

A decline is recorded at once (`status='rejected'`) but its email waits out the cool-off, and
until it goes the student is shown the stage she was declined FROM (`student_status.py`). Two
exits lifted that mask with no email at all:

D1 — a REOPEN. `reopen.reopen_decision` cleared the pending marker but left `status='rejected'`,
     so she was shown the raw decline at once and the cron never sent the email. Round 1 made the
     reopen REVERSE the decline; the adversarial review showed that reopens INTO the funnel (a
     funded student reopened at active, a failed reinstatement only logged, the cancel's audit
     line inside a reopen, AWAITING QC reached without the verify step). So (lead decision) a
     reopen of an embargoed decline is REFUSED — `decline_pending` — before any write, and the
     existing "cancel the pending decline" is the way to re-decide it.
D2 — a FAILED SEND. `release_pending_declines` cleared the markers and saved BEFORE the send,
     and the send swallows a mail failure. Now each due decline is CLAIMED (a row lock, then a
     re-check that it is still pending, still due and still rejected), sent, and only then cleared.
     A failure is logged at ERROR, leaves the decline masked, and the next run retries.
And one "told" rule (`_told_of_this_decline`) for the cancel and the cron.

Every case is built with `factories.make_application` — this file hand-builds no application.
⚠ SQLite (the test database) ignores `select_for_update`, so the LOCK is PostgreSQL's and is not
exercised here; the re-check under it is.
"""
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import reopen, services
from apps.scholarship.models import DecisionReopen, ScholarshipApplication, SponsorProfile
from apps.scholarship.services import decline as decline_service
from apps.scholarship.student_status import student_facing_status
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application,
)

#: The logger `services/decline.py` writes to (the package name, written out — see that file).
SERVICES_LOG = 'apps.scholarship.services'

#: Everything a refused reopen must leave exactly as it was.
ROW_FIELDS = ('status', 'pending_rejection_category', 'decline_due_at', 'pending_decline_by',
              'pre_decline_status', 'award_amount', 'pre_decline_award_amount',
              'rejection_category', 'rejected_at', 'rejected_by', 'decision_reopened_at',
              'decline_email_sent_at')


def _shown(app):
    """What the student's own screens show, read fresh from the database."""
    app.refresh_from_db()
    return student_facing_status(app)


def _row(app):
    return ScholarshipApplication.objects.filter(pk=app.pk).values(*ROW_FIELDS).get()


def _make_due(app):
    ScholarshipApplication.objects.filter(pk=app.pk).update(
        decline_due_at=timezone.now() - timedelta(minutes=1))
    app.refresh_from_db()


def _still_embargoed(test, app):
    app.refresh_from_db()
    test.assertEqual(app.status, 'rejected')
    test.assertTrue(app.pending_rejection_category)
    test.assertIsNotNone(app.decline_due_at)
    test.assertIsNone(app.decline_email_sent_at)


# ── D1: a reopen of an embargoed decline is refused ─────────────────────────────────────────
#: (stage built, factory kwargs, decline bucket) — every status a decline path can snapshot
#: into `pre_decline_status` while embargoing the email: the four `INTERVIEW_REJECT_FROM`
#: stages and the three `contractual` ones. `org_admin_reject` embargoes nothing.
DECLINED_FROM = (
    ('shortlisted', {}, 'interview'),
    ('profile_complete', {}, 'interview'),
    ('interviewing', {}, 'interview'),
    ('awaiting_qc', {'outcome': 'decline'}, 'interview'),     # status 'interviewed'
    ('recommended', {}, 'contractual'),
    ('active', {}, 'contractual'),
    ('maintenance', {}, 'contractual'),
)


@override_settings(DECLINE_COOLOFF_DAYS=7, ROOT_URLCONF='halatuju.urls',
                   SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ReopenRefusesAnEmbargoedDeclineTest(TestCase):
    def setUp(self):
        self.reviewer = make_admin('reviewer', email='td349-reviewer@example.test')
        self.superadmin = make_admin('super', super_admin=True, email='td349-super@example.test')

    def _declined(self, stage, kw, category):
        # A reopen needs a recorded decision; stages before the verdict are given one, so the
        # refusal under test is the ONLY reason the reopen can fail.
        kw = dict(kw)
        kw.setdefault('verdict_decided_at', timezone.now())
        app = make_application(stage, **kw)
        services.admin_reject(app, self.reviewer, category)
        app.refresh_from_db()
        _still_embargoed(self, app)
        return app

    def _refused(self, app, reason='The reviewer misread it.'):
        with self.assertRaises(reopen.ReopenError) as caught:
            reopen.reopen_decision(app, by_admin=self.superadmin, reason=reason)
        self.assertEqual(caught.exception.code, 'decline_pending')

    def test_every_embargoed_snapshot_is_refused_and_nothing_is_written(self):
        for stage, kw, category in DECLINED_FROM:
            with self.subTest(stage=stage):
                app = self._declined(stage, kw, category)
                before, shown = _row(app), _shown(app)
                sponsorships = list(app.sponsorships.values_list('id', 'status'))
                published = list(SponsorProfile.objects.filter(application=app)
                                 .values_list('anon_published', flat=True))
                sent = len(mail.outbox)
                self._refused(app)
                self.assertEqual(_row(app), before)                     # status, markers, award
                self.assertEqual(_shown(app), shown)                    # her view does not move
                self.assertNotEqual(_shown(app), 'rejected')
                self.assertFalse(DecisionReopen.objects.filter(application=app).exists())
                self.assertEqual(list(app.sponsorships.values_list('id', 'status')), sponsorships)
                self.assertEqual(list(SponsorProfile.objects.filter(application=app)
                                      .values_list('anon_published', flat=True)), published)
                self.assertEqual(len(mail.outbox), sent)

    def test_a_pending_decline_is_named_before_a_missing_reason(self):
        app = self._declined('awaiting_qc', {'outcome': 'decline'}, 'interview')
        self._refused(app, reason='   ')

    def test_the_view_answers_400_with_a_code_and_a_sentence(self):
        app = self._declined('awaiting_qc', {'outcome': 'decline'}, 'interview')
        r = authed_client(self.superadmin).post(
            f'/api/v1/admin/scholarship/applications/{app.id}/reopen-decision/',
            {'reason': 'The reviewer misread it.'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'decline_pending')
        self.assertIn('Cancel the pending decline', r.json()['error'])
        _still_embargoed(self, app)

    def test_cancel_is_the_way_and_a_reopen_is_allowed_after_it(self):
        app = self._declined('recommended', {}, 'contractual')
        shown = _shown(app)
        self._refused(app)
        self.assertTrue(services.cancel_pending_decline(app, by_email='td349-super@example.test'))
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')
        self.assertEqual(_shown(app), shown)
        self.assertIsNone(app.decision_reopened_at)                 # no reopen flag left behind
        reopen.reopen_decision(app, by_admin=self.superadmin, reason='Now re-decide it.')
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')                 # the ordinary reopen step

    def test_a_decline_whose_email_has_gone_is_reopened_as_before(self):
        app = self._declined('awaiting_qc', {'outcome': 'decline'}, 'interview')
        _make_due(app)
        self.assertEqual(services.release_pending_declines(), 1)
        app.refresh_from_db()
        reopen.reopen_decision(app, by_admin=self.superadmin, reason='The reviewer misread it.')
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')                    # stays, reopened
        self.assertIsNotNone(app.decision_reopened_at)
        self.assertEqual(_shown(app), 'rejected')


# ── One "told" rule for the cancel and the cron ─────────────────────────────────────────────
@override_settings(DECLINE_COOLOFF_DAYS=7)
class ToldOfThisDeclineTest(TestCase):
    def setUp(self):
        self.reviewer = make_admin('reviewer', email='td349-told@example.test')

    def test_an_older_stamp_does_not_stop_a_cancel_restoring(self):
        # Declined once and told; reopened, re-decided, declined again. Cancelling THIS decline
        # must reverse it: she has not been told of this one.
        app = make_application('awaiting_qc', outcome='decline',
                               decline_email_sent_at=timezone.now() - timedelta(days=30))
        services.admin_reject(app, self.reviewer, 'interview')
        app.refresh_from_db()
        self.assertEqual(_shown(app), 'interviewed')
        self.assertTrue(services.cancel_pending_decline(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')

    def test_a_cancel_after_this_decline_was_emailed_does_not_reverse_it(self):
        app = make_application('rejected')
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            decline_email_sent_at=app.rejected_at + timedelta(seconds=5))
        app.refresh_from_db()
        self.assertTrue(services.cancel_pending_decline(app))       # clears the markers only
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')

    def test_a_cancel_holding_a_stale_row_cannot_reverse_what_the_cron_just_sent(self):
        app = make_application('rejected')                          # the view loaded this
        _make_due(app)
        self.assertEqual(services.release_pending_declines(), 1)    # meanwhile, sent
        self.assertTrue(app.pending_rejection_category)             # the stale copy
        self.assertFalse(services.cancel_pending_decline(app))      # re-read: nothing pending
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')

    def test_the_rule_itself(self):
        app = make_application('rejected')
        told = decline_service._told_of_this_decline
        self.assertFalse(told(app))                                       # no stamp
        app.decline_email_sent_at = app.rejected_at - timedelta(seconds=1)
        self.assertFalse(told(app))                                       # an earlier decline's
        app.decline_email_sent_at = app.rejected_at
        self.assertTrue(told(app))                                        # this one's
        app.rejected_at = None
        self.assertTrue(told(app))         # legacy: no rejected_at to compare, any stamp is told


# ── D2: the release cron ──────────────────────────────────────────────────────────────────
@override_settings(DECLINE_COOLOFF_DAYS=7)
class ReleaseSendsBeforeItUnmasksTest(TestCase):
    def _due(self, **kw):
        app = make_application('rejected', **kw)               # declined at QC, email embargoed
        _make_due(app)
        self.assertEqual(_shown(app), 'interviewed')            # masked
        return app

    def test_a_normal_release_sends_once_then_unmasks(self):
        app = self._due()
        sent = len(mail.outbox)
        self.assertEqual(services.release_pending_declines(), 1)
        app.refresh_from_db()
        self.assertEqual(len(mail.outbox), sent + 1)
        self.assertEqual(mail.outbox[-1].to, [app.notify_email])
        self.assertIsNotNone(app.decline_email_sent_at)
        self.assertEqual(app.pending_rejection_category, '')
        self.assertIsNone(app.decline_due_at)
        self.assertEqual(_shown(app), 'rejected')
        self.assertEqual(services.release_pending_declines(), 0)   # nothing left to send
        self.assertEqual(len(mail.outbox), sent + 1)

    def test_a_send_that_raises_keeps_the_decline_masked_and_the_next_run_sends_it(self):
        app = self._due()
        with patch('apps.scholarship.services.decline.send_decline_email',
                   side_effect=RuntimeError('template exploded')):
            with self.assertLogs(SERVICES_LOG, level='ERROR') as logs:
                self.assertEqual(services.release_pending_declines(), 0)   # not counted
        self.assertTrue(any(str(app.id) in line for line in logs.output))
        _still_embargoed(self, app)
        self.assertEqual(_shown(app), 'interviewed')            # still masked
        sent = len(mail.outbox)
        self.assertEqual(services.release_pending_declines(), 1)           # the retry
        self.assertEqual(len(mail.outbox), sent + 1)
        self.assertEqual(_shown(app), 'rejected')

    def test_a_swallowed_mail_failure_is_a_failure_too(self):
        # The real road: Brevo refuses, `_send_html` logs and returns False, nothing raises.
        app = self._due()
        with patch('django.core.mail.EmailMultiAlternatives.send',
                   side_effect=OSError('smtp down')):
            with self.assertLogs(SERVICES_LOG, level='ERROR') as logs:
                self.assertEqual(services.release_pending_declines(), 0)
        self.assertTrue(any(str(app.id) in line for line in logs.output))
        _still_embargoed(self, app)
        self.assertEqual(_shown(app), 'interviewed')
        self.assertEqual(services.release_pending_declines(), 1)
        self.assertEqual(_shown(app), 'rejected')

    def test_one_failure_does_not_stop_the_batch(self):
        bad, good = self._due(), self._due()
        real = decline_service.send_decline_email

        def flaky(**kw):
            if kw['to_email'] == bad.notify_email:
                raise RuntimeError('this one fails')
            return real(**kw)

        with patch('apps.scholarship.services.decline.send_decline_email', side_effect=flaky):
            with self.assertLogs(SERVICES_LOG, level='ERROR'):
                self.assertEqual(services.release_pending_declines(), 1)
        _still_embargoed(self, bad)
        self.assertEqual(_shown(good), 'rejected')
        self.assertIsNotNone(good.decline_email_sent_at)
        self.assertEqual(mail.outbox[-1].to, [good.notify_email])

    def test_an_email_already_sent_for_this_decline_is_not_sent_again(self):
        # A stamp for THIS decline with the markers still set (e.g. an older half-failure). The
        # run only clears them.
        app = self._due()
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            decline_email_sent_at=app.rejected_at + timedelta(seconds=5))
        sent = len(mail.outbox)
        self.assertEqual(services.release_pending_declines(), 1)
        self.assertEqual(len(mail.outbox), sent)
        self.assertEqual(_shown(app), 'rejected')

    def test_a_stamp_from_an_earlier_decline_does_not_stop_this_email(self):
        app = self._due()
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            decline_email_sent_at=app.rejected_at - timedelta(days=30))
        sent = len(mail.outbox)
        self.assertEqual(services.release_pending_declines(), 1)
        self.assertEqual(len(mail.outbox), sent + 1)

    def test_with_no_address_at_all_the_decline_is_released_without_an_email(self):
        # Nothing to retry: there is nobody to send to. Kept masked, she would be shown her old
        # stage for ever. Released, and logged so an officer can reach her another way.
        app = self._due(notify_email='')
        sent = len(mail.outbox)
        with self.assertLogs(SERVICES_LOG, level='WARNING') as logs:
            self.assertEqual(services.release_pending_declines(), 1)
        self.assertTrue(any(str(app.id) in line for line in logs.output))
        self.assertEqual(len(mail.outbox), sent)
        self.assertEqual(_shown(app), 'rejected')


@override_settings(DECLINE_COOLOFF_DAYS=7)
class ReleaseClaimsBeforeItSendsTest(TestCase):
    """The cron reads its list, then CLAIMS each row right before the send: re-selected under a
    row lock (PostgreSQL; a no-op on SQLite) and re-checked. Anything that got there first wins,
    silently. The hook below runs between the list being read and the claim."""

    def setUp(self):
        self.reviewer = make_admin('reviewer', email='td349-claim@example.test')

    def _hooked(self, before_claim):
        real = decline_service._claim_due_decline

        def hook(pk, now):
            before_claim(pk)
            return real(pk, now)
        return patch('apps.scholarship.services.decline._claim_due_decline', side_effect=hook)

    def _due(self):
        app = make_application('rejected')
        _make_due(app)
        return app

    def test_a_cancel_after_the_list_was_read_is_not_sent(self):
        app = self._due()

        def cancel(pk):
            services.cancel_pending_decline(ScholarshipApplication.objects.get(pk=pk))

        sent = len(mail.outbox)
        with self._hooked(cancel), self.assertNoLogs(SERVICES_LOG, level='ERROR'):
            self.assertEqual(services.release_pending_declines(), 0)
        self.assertEqual(len(mail.outbox), sent)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')                 # the cancel's restore stands
        self.assertIsNone(app.decline_email_sent_at)

    def test_a_case_cancelled_and_declined_again_waits_for_its_new_window(self):
        app = self._due()

        def cancel_and_redecline(pk):
            row = ScholarshipApplication.objects.get(pk=pk)
            services.cancel_pending_decline(row)
            row.refresh_from_db()
            services.admin_reject(row, self.reviewer, 'interview')   # a fresh 7-day window

        sent = len(mail.outbox)
        with self._hooked(cancel_and_redecline):
            self.assertEqual(services.release_pending_declines(), 0)
        self.assertEqual(len(mail.outbox), sent)
        _still_embargoed(self, app)

    def test_markers_on_a_case_that_is_not_rejected_are_never_guessed_into_a_decline(self):
        # No writer leaves markers on a live case any more (the reopen refuses); the old "legacy"
        # arm recorded a decline here at send time. Now: skipped, not counted, said aloud.
        app = make_application('interviewing', pending_rejection_category='interview',
                               decline_due_at=timezone.now() - timedelta(minutes=1))
        sent = len(mail.outbox)
        with self.assertLogs(SERVICES_LOG, level='WARNING') as logs:
            self.assertEqual(services.release_pending_declines(), 0)
        self.assertTrue(any(str(app.id) in line for line in logs.output))
        self.assertEqual(len(mail.outbox), sent)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')
