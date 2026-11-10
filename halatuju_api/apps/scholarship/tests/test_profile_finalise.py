"""A2.1 / TD-517: the final sponsor profile is written in the BACKGROUND, not inside record-verdict.

`profile_finalise.queue_finalise` (called by the view) only queues; `run_pending` (the
`finalise-profiles` cron) runs the refine and the card blurb, with retry. Gemini is mocked
throughout: no paid call runs, and no real student document is used.
"""
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import profile_finalise as pf
from apps.scholarship.models import InterviewSession, SponsorProfile
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, answered_findings, authed_client, make_admin, make_application, make_cohort,
)

REFINE = 'apps.scholarship.profile_finalise.refine_sponsor_profile'
BLURB = 'apps.scholarship.profile_finalise.generate_anon_blurb'
DOWN = 'apps.scholarship.services.outage.gemini_reads_down'
SEAM = 'apps.scholarship.profile_engine._call_gemini_text'
# No token of the factory's 'Test Student N' name, so the PII scan reads it as clean.
FINAL = {'markdown': '## Determined, and wants to study engineering',
         'model_used': 'gemini-3.8-flash', 'prompt_version': 'v-test'}


def _queued(app, **kw):
    """A profile queued exactly as the view queues it, plus the submitted interview it needs."""
    InterviewSession.objects.create(application=app, status='submitted', submitted_at=timezone.now(),
                                    findings=answered_findings(app))
    # The 'recommended' factory stage already made a profile row.
    SponsorProfile.objects.update_or_create(application=app, defaults={'draft_markdown': '## Draft', **kw})
    result, sp = pf.queue_finalise(app, 'en')
    sp.save(update_fields=pf.QUEUE_FIELDS)
    return result, sp


@patch(DOWN, return_value=False)
class TestQueue(TestCase):
    def test_queue_sets_pending_and_calls_nothing(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        with patch(REFINE) as refine, patch(BLURB) as blurb:
            result, sp = _queued(app)
        self.assertEqual(result, {'ok': True, 'pending': True, 'published': False})
        refine.assert_not_called()
        blurb.assert_not_called()
        sp.refresh_from_db()
        self.assertEqual((sp.finalise_state, sp.finalise_language, sp.finalise_attempts), ('pending', 'en', 0))
        self.assertIsNotNone(sp.finalise_requested_at)

    def test_preconditions_unchanged(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        self.assertEqual(pf.queue_finalise(app, None), ({'ok': False, 'code': 'no_draft'}, None))
        SponsorProfile.objects.create(application=app, draft_markdown='## Draft')
        self.assertEqual(pf.queue_finalise(app, None), ({'ok': False, 'code': 'no_interview'}, None))

    def test_a_non_text_language_is_dropped(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        _, sp = _queued(app)
        self.assertEqual(pf.queue_finalise(app, 42)[1].finalise_language, '')


@patch(DOWN, return_value=False)
class TestWorker(TestCase):
    def test_success_writes_what_the_inline_finalise_wrote(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        _, sp = _queued(app)
        with patch(REFINE, return_value=FINAL) as refine, patch(BLURB, return_value='Wants to study.'):
            counts = pf.run_pending()
        self.assertEqual(counts['done'], 1)
        self.assertEqual(refine.call_args.kwargs['language'], 'en')
        sp.refresh_from_db()
        self.assertEqual(sp.final_markdown, FINAL['markdown'])
        self.assertEqual(sp.anon_markdown, FINAL['markdown'])
        self.assertEqual((sp.final_model_used, sp.prompt_version), ('gemini-3.8-flash', 'v-test'))
        self.assertEqual(sp.anon_blurb, 'Wants to study.')
        self.assertEqual((sp.finalise_state, sp.anon_published), ('', False))   # never publishes pre-QC
        self.assertIsNotNone(sp.finalised_at)

    def test_a_decline_builds_no_blurb(self, _down):
        app = make_application('verdict_recorded', outcome='decline')
        _queued(app)
        with patch(REFINE, return_value=FINAL), patch(BLURB) as blurb:
            pf.run_pending()
        blurb.assert_not_called()

    def test_retry_then_success(self, _down):
        # THE background retry: an engine error stays pending, the next run succeeds.
        app = make_application('verdict_recorded', outcome='recommend')
        _, sp = _queued(app)
        with patch(REFINE, return_value={'error': 'boom'}), patch(BLURB, return_value=''):
            self.assertEqual(pf.run_pending()['retry'], 1)
        sp.refresh_from_db()
        self.assertEqual((sp.finalise_state, sp.finalise_attempts, sp.final_markdown), ('pending', 1, ''))
        self.assertIsNone(sp.finalise_claimed_at)
        with patch(REFINE, return_value=FINAL), patch(BLURB, return_value=''):
            self.assertEqual(pf.run_pending()['done'], 1)
        sp.refresh_from_db()
        self.assertEqual((sp.finalise_state, sp.final_markdown), ('', FINAL['markdown']))

    def test_an_exception_counts_as_an_attempt_and_never_raises(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        _, sp = _queued(app)
        with patch(REFINE, side_effect=RuntimeError('network')):
            self.assertEqual(pf.run_pending()['retry'], 1)
        sp.refresh_from_db()
        self.assertEqual((sp.finalise_state, sp.finalise_attempts), ('pending', 1))

    def test_attempts_spent_is_failed(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        _, sp = _queued(app)
        with patch(REFINE, return_value={'error': 'boom'}) as refine:
            for _ in range(pf.MAX_ATTEMPTS + 1):
                pf.run_pending()
        self.assertEqual(refine.call_count, pf.MAX_ATTEMPTS)    # no fourth paid call
        sp.refresh_from_db()
        self.assertEqual((sp.finalise_state, sp.finalise_attempts), ('failed', pf.MAX_ATTEMPTS))

    def test_a_claimed_row_is_not_run_twice(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        _, sp = _queued(app)
        SponsorProfile.objects.filter(pk=sp.pk).update(finalise_claimed_at=timezone.now())
        with patch(REFINE) as refine:
            self.assertEqual(pf.run_finalise(sp.pk), 'not_claimed')
            pf.run_pending()
        refine.assert_not_called()

    def test_a_stale_claim_is_taken_again(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        _, sp = _queued(app)
        SponsorProfile.objects.filter(pk=sp.pk).update(
            finalise_claimed_at=timezone.now() - pf.STALE_CLAIM - timedelta(minutes=1), finalise_attempts=1)
        with patch(REFINE, return_value=FINAL), patch(BLURB, return_value=''):
            self.assertEqual(pf.run_pending()['done'], 1)

    def test_a_stale_claim_on_the_last_attempt_is_closed_as_failed(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        _, sp = _queued(app)
        SponsorProfile.objects.filter(pk=sp.pk).update(
            finalise_claimed_at=timezone.now() - pf.STALE_CLAIM - timedelta(minutes=1),
            finalise_attempts=pf.MAX_ATTEMPTS)
        with patch(REFINE) as refine:
            self.assertEqual(pf.run_pending()['failed'], 1)
        refine.assert_not_called()
        sp.refresh_from_db()
        self.assertEqual(sp.finalise_state, 'failed')

    def test_a_re_record_during_the_run_drops_the_old_result(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        _, sp = _queued(app)

        def rerecord_then_answer(*a, **kw):
            # The reviewer re-records while Gemini is still answering: the token moves on.
            again, row = pf.queue_finalise(app, 'ms')
            row.save(update_fields=pf.QUEUE_FIELDS)
            return FINAL
        with patch(REFINE, side_effect=rerecord_then_answer), patch(BLURB, return_value=''):
            self.assertEqual(pf.run_finalise(sp.pk), 'superseded')
        sp.refresh_from_db()
        self.assertEqual((sp.final_markdown, sp.finalise_state, sp.finalise_language), ('', 'pending', 'ms'))

    def test_skipped_while_gemini_is_down(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        _, sp = _queued(app)
        with patch(DOWN, return_value=True), patch(REFINE) as refine:
            self.assertTrue(pf.run_pending()['skipped_outage'])
        refine.assert_not_called()
        sp.refresh_from_db()
        self.assertEqual((sp.finalise_state, sp.finalise_attempts), ('pending', 0))

    def test_the_worker_never_publishes(self, _down):
        # A2.1 review (M1): even on a 'recommended' case with nothing published, publishing stays
        # with QC-Accept (which refuses while the profile is pending, so QC reads the final text).
        app = make_application('recommended')
        _, sp = _queued(app, anon_markdown='', anon_blurb='', anon_published=False, anon_published_at=None)
        with patch(REFINE, return_value=FINAL), patch(BLURB, return_value='Wants to study.'), \
                patch('apps.scholarship.pool.publish_profile_to_pool') as publish:
            self.assertEqual(pf.run_pending()['done'], 1)
        publish.assert_not_called()
        sp.refresh_from_db()
        self.assertFalse(sp.anon_published)
        self.assertEqual((sp.anon_markdown, sp.anon_blurb), (FINAL['markdown'], 'Wants to study.'))

    def test_a_published_profile_keeps_its_sponsor_text(self, _down):
        # A2.1 review (M1): a CLEAN new text is not swapped in either; only final_markdown moves.
        app = make_application('recommended')
        _, sp = _queued(app, anon_markdown='## Old clean', anon_blurb='Old blurb', anon_published=True,
                        anon_model_used='old-model')
        with patch(REFINE, return_value=FINAL), patch(BLURB, return_value='New blurb'):
            self.assertEqual(pf.run_pending()['done'], 1)
        sp.refresh_from_db()
        self.assertEqual(sp.final_markdown, FINAL['markdown'])
        self.assertEqual((sp.anon_markdown, sp.anon_blurb, sp.anon_model_used, sp.anon_published),
                         ('## Old clean', 'Old blurb', 'old-model', True))

    def test_qc_accept_refuses_while_pending(self, _down):
        from apps.scholarship.views_admin.qc_checks import _accept_absolute_stop
        app = make_application('verdict_recorded', outcome='recommend')
        app.reporting_date = timezone.localdate()
        app.award_amount = 1000
        _queued(app)
        refusal = _accept_absolute_stop(app)
        self.assertEqual((refusal.status_code, refusal.data['code']), (400, 'profile_pending'))
        with patch(REFINE, return_value=FINAL), patch(BLURB, return_value=''):
            pf.run_pending()
        self.assertNotEqual(getattr(_accept_absolute_stop(app), 'data', {}).get('code'), 'profile_pending')

    def test_qc_accept_refuses_a_failed_profile(self, _down):
        # A2.1 re-review (Med): a profile the cron gave up on must not be accepted either; an
        # empty one would reach 'recommended' with nothing published, a reopened one its old text.
        from apps.scholarship.views_admin.qc_checks import _accept_absolute_stop
        app = make_application('verdict_recorded', outcome='recommend')
        app.reporting_date = timezone.localdate()
        app.award_amount = 1000
        _queued(app)
        with patch(REFINE, return_value={'error': 'boom'}):
            for _ in range(pf.MAX_ATTEMPTS + 1):
                pf.run_pending()
        self.assertEqual(SponsorProfile.objects.get(application=app).finalise_state, 'failed')
        refusal = _accept_absolute_stop(app)
        self.assertEqual((refusal.status_code, refusal.data['code']), (400, 'profile_failed'))
        # Running finalise again (re-queue) and a good run clear it.
        _queued(app)
        with patch(REFINE, return_value=FINAL), patch(BLURB, return_value=''):
            pf.run_pending()
        self.assertNotIn(getattr(_accept_absolute_stop(app), 'data', {}).get('code'),
                         ('profile_pending', 'profile_failed'))

    def test_a_run_stops_claiming_after_its_time_budget(self, _down):
        # A2.1 review (L4): no new row is claimed once the budget is spent; the rest wait.
        apps = [make_application('verdict_recorded', outcome='recommend') for _ in range(3)]
        for app in apps:
            _queued(app)
        ticks = iter([0, 0, pf.TIME_BUDGET_SECONDS, pf.TIME_BUDGET_SECONDS])
        with patch(REFINE, return_value=FINAL) as refine, patch(BLURB, return_value=''):
            counts = pf.run_pending(clock=lambda: next(ticks))
        self.assertEqual((counts['done'], counts['deferred'], refine.call_count), (1, 2, 1))
        self.assertEqual(SponsorProfile.objects.filter(finalise_state='pending').count(), 2)

    def test_the_batch_is_small(self, _down):
        self.assertEqual((pf.BATCH, pf.TIME_BUDGET_SECONDS), (3, 150))

    def test_the_command_runs_the_batch(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        _queued(app)
        with patch(REFINE, return_value=FINAL), patch(BLURB, return_value=''):
            call_command('run_pending_finalise')
        self.assertEqual(SponsorProfile.objects.get(application=app).final_markdown, FINAL['markdown'])

    def test_the_cron_job_is_registered(self, _down):
        from apps.scholarship.cron_health import EVERY_5_MIN, EXPECTED_CADENCE
        from apps.scholarship.services.system_health import cadence_word
        from apps.scholarship.views import CronRunView
        self.assertEqual(CronRunView.JOBS['finalise-profiles'], 'run_pending_finalise')
        self.assertEqual(EXPECTED_CADENCE['finalise-profiles'], EVERY_5_MIN)
        self.assertEqual(cadence_word(EVERY_5_MIN), 'every5')

    def test_system_health_counts_failed_profiles(self, _down):
        # A2.1 review (L2): a profile the cron gave up on is no longer silent.
        from apps.scholarship.services.system_health import profiles_row
        self.assertEqual((profiles_row()['status'], profiles_row()['code']), ('green', 'ok'))
        app = make_application('verdict_recorded', outcome='recommend')
        _, sp = _queued(app)
        SponsorProfile.objects.filter(pk=sp.pk).update(finalise_state='failed')
        row = profiles_row()
        self.assertEqual((row['status'], row['code'], row['params']), ('amber', 'failed', {'count': '1'}))

    def test_system_health_ignores_failed_profiles_on_closed_cases(self, _down):
        # A2.1 re-review (Low): a closed case's failed row needs no one; the light goes green.
        from apps.scholarship.models import ScholarshipApplication
        from apps.scholarship.services.system_health import profiles_row
        app = make_application('verdict_recorded', outcome='recommend')
        _, sp = _queued(app)
        SponsorProfile.objects.filter(pk=sp.pk).update(finalise_state='failed')
        self.assertEqual(profiles_row()['status'], 'amber')
        ScholarshipApplication.objects.filter(pk=app.pk).update(status='withdrawn')
        self.assertEqual((profiles_row()['status'], profiles_row()['code']), ('green', 'ok'))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@patch(DOWN, return_value=False)
class TestRecordVerdictMakesNoGeminiCall(TestCase):
    def test_the_view_queues_and_never_reaches_gemini(self, _down):
        cohort = make_cohort()
        admin = make_admin('reviewer', owning_org=cohort.owning_organisation)
        app = make_application('interviewing', cohort=cohort, reviewer=admin)
        InterviewSession.objects.create(application=app, status='submitted', submitted_at=timezone.now(),
                                        findings=answered_findings(app))
        SponsorProfile.objects.create(application=app, draft_markdown='## Draft')
        client = authed_client(admin)
        with patch(SEAM) as seam, patch(REFINE) as refine, patch(BLURB) as blurb:
            r = client.post(f'/api/v1/admin/scholarship/applications/{app.id}/record-verdict/', {
                'officer_verdict': {'identity': 'pass', 'academic': 'pass', 'income': 'pass',
                                    'pathway': 'pass', 'overall': 'accept'},
                'finalise': True, 'language': 'en'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r.json()['finalise_result'], {'ok': True, 'pending': True, 'published': False})
        seam.assert_not_called()
        refine.assert_not_called()
        blurb.assert_not_called()
        sp = SponsorProfile.objects.get(application=app)
        self.assertEqual(sp.finalise_state, 'pending')
        self.assertEqual(r.json()['sponsor_profile']['finalise_state'], 'pending')
