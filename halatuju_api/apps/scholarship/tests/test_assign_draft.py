"""A2.3b / TD-586 — the first-assign profile draft is written in the BACKGROUND, not inside the assign.

The one home of the handoff auto-draft rule (Check-2/Check-3 redesign S3): fires only on the FIRST
assignment, only with ``CHECK2_AUTO_GENERATE`` on, never re-drafts. Since A2.3b ``assign_reviewer``
only queues it (``assign_draft.queue_first_draft``) and the ``finalise-profiles`` cron writes it
(``assign_draft.draft_pending``). The generator is mocked throughout: no paid call runs.
"""
import io
import time
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import assign_draft
from apps.scholarship.models import ScholarshipApplication, SponsorProfile
from apps.scholarship.services import assignment
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application,
)

GENERATE = 'apps.scholarship.profile_engine.generate_sponsor_profile'
DOWN = 'apps.scholarship.services.outage.gemini_reads_down'
DRAFT = {'markdown': 'Draft profile.', 'model_used': 'test', 'prompt_version': 'v-test'}


@override_settings(CHECK2_AUTO_GENERATE=True)
@patch(DOWN, return_value=False)
class TestFirstAssignDraft(TestCase):
    def setUp(self):
        self.app = make_application('profile_complete')
        self.super = make_admin(super_admin=True)
        self.reviewer = make_admin('reviewer', first_seen_at=timezone.now(), owning_org=self.app.owning_organisation, name='Rohini')
        self.reviewer2 = make_admin('reviewer', first_seen_at=timezone.now(), owning_org=self.app.owning_organisation, name='Kavin')

    def _assign(self, reviewer):
        assignment.assign_reviewer(self.app, reviewer=reviewer, by_admin=self.super)
        self.app.refresh_from_db()

    def _sp(self):
        return SponsorProfile.objects.get(application=self.app)

    @override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_the_first_assign_replies_without_calling_the_generator(self, _down):
        client = authed_client(self.super)
        with patch(GENERATE) as gen:
            r = client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/assign/',
                            {'reviewer_id': self.reviewer.id}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertEqual(r.json()['assigned_to_id'], self.reviewer.id)     # the reply is unchanged
        gen.assert_not_called()
        sp = self._sp()
        self.assertEqual((sp.finalise_state, sp.finalise_attempts, sp.draft_markdown),
                         ('drafting', 0, ''))
        self.assertIsNone(sp.generated_at)

    def test_the_cron_writes_the_draft_the_inline_code_wrote(self, _down):
        self._assign(self.reviewer)
        with patch(GENERATE, return_value=DRAFT) as gen:
            out = io.StringIO()
            call_command('run_pending_finalise', stdout=out)
            assign_draft.draft_pending(time.monotonic())                   # a second run: nothing
        gen.assert_called_once()
        self.assertIn('Drafted: done=1', out.getvalue())
        sp = self._sp()
        self.assertEqual((sp.draft_markdown, sp.model_used, sp.prompt_version), ('Draft profile.', 'test', 'v-test'))
        self.assertIsNotNone(sp.generated_at)
        self.assertEqual((sp.finalise_state, sp.status), ('', 'draft'))

    def test_a_reassign_does_not_queue_again(self, _down):
        self._assign(self.reviewer)
        token = self._sp().finalise_requested_at
        self._assign(self.reviewer2)                                          # a reassign
        self._assign(None)                                                    # unassign...
        self._assign(self.reviewer)                                           # ...and a first assign again
        self.assertEqual(SponsorProfile.objects.filter(application=self.app).count(), 1)
        sp = self._sp()
        self.assertEqual((sp.finalise_state, sp.finalise_requested_at), ('drafting', token))
        with patch(GENERATE, return_value=DRAFT) as gen:
            assign_draft.draft_pending(time.monotonic())
        gen.assert_called_once()

    def test_an_engine_error_retries_then_gives_up_to_no_draft(self, _down):
        self._assign(self.reviewer)
        with patch(GENERATE, return_value={'error': 'engine down'}) as gen:
            outcomes = [assign_draft.run_draft(self._sp().pk) for _ in range(assign_draft.MAX_ATTEMPTS + 1)]
        self.assertEqual(outcomes, ['retry', 'retry', 'failed', 'not_claimed'])
        self.assertEqual(gen.call_count, assign_draft.MAX_ATTEMPTS)          # the retry cap
        sp = self._sp()
        self.assertEqual((sp.finalise_state, sp.draft_markdown), ('', ''))   # as a failed inline draft left it

    def test_a_raising_engine_counts_as_one_failed_attempt(self, _down):
        self._assign(self.reviewer)
        with patch(GENERATE, side_effect=RuntimeError('boom')):
            self.assertEqual(assign_draft.draft_pending(time.monotonic())['retry'], 1)
        self.assertEqual((self._sp().finalise_state, self._sp().finalise_attempts), ('drafting', 1))

    def test_a_draft_written_meanwhile_is_never_paid_for_twice(self, _down):
        self._assign(self.reviewer)
        SponsorProfile.objects.filter(application=self.app).update(
            draft_markdown='By hand.', generated_at=timezone.now())         # the Generate button
        with patch(GENERATE) as gen:
            self.assertEqual(assign_draft.draft_pending(time.monotonic())['superseded'], 1)
        gen.assert_not_called()
        self.assertEqual((self._sp().draft_markdown, self._sp().finalise_state), ('By hand.', ''))

    def test_never_redrafts_an_existing_profile(self, _down):
        SponsorProfile.objects.create(application=self.app, draft_markdown='Existing.',
                                      generated_at=timezone.now())
        self._assign(self.reviewer)
        self.assertEqual((self._sp().finalise_state, self._sp().draft_markdown), ('', 'Existing.'))

    def test_a_stale_claim_is_claimable_and_a_spent_one_is_let_go(self, _down):
        self._assign(self.reviewer)
        old = timezone.now() - assign_draft.STALE_CLAIM - timedelta(minutes=1)
        SponsorProfile.objects.filter(application=self.app).update(finalise_claimed_at=old, finalise_attempts=1)
        with patch(GENERATE, return_value=DRAFT):
            self.assertEqual(assign_draft.draft_pending(time.monotonic())['done'], 1)
        other = make_application('profile_complete')
        assignment.assign_reviewer(other, reviewer=make_admin(
            'reviewer', owning_org=other.owning_organisation, first_seen_at=timezone.now()), by_admin=self.super)
        SponsorProfile.objects.filter(application=other).update(
            finalise_claimed_at=old, finalise_attempts=assign_draft.MAX_ATTEMPTS)
        with patch(GENERATE) as gen:
            self.assertEqual(assign_draft.draft_pending(time.monotonic())['failed'], 1)
        gen.assert_not_called()
        self.assertEqual(SponsorProfile.objects.get(application=other).finalise_state, '')

    def test_a_fresh_claim_blocks_a_second_worker(self, _down):
        self._assign(self.reviewer)
        sp_id = self._sp().pk
        second = []

        def first_worker_call(*_a, **_k):         # a second worker arrives mid-call
            second.append(assign_draft.run_draft(sp_id))
            return DRAFT
        with patch(GENERATE, side_effect=first_worker_call) as gen:
            self.assertEqual(assign_draft.run_draft(sp_id), 'done')
        self.assertEqual(second, ['not_claimed'])
        gen.assert_called_once()
        # A claim older than STALE_CLAIM (a worker killed mid-call) can be taken again.
        SponsorProfile.objects.filter(pk=sp_id).update(
            finalise_state='drafting', generated_at=None, finalise_attempts=1,
            finalise_claimed_at=timezone.now() - assign_draft.STALE_CLAIM - timedelta(minutes=1))
        with patch(GENERATE, return_value=DRAFT) as gen:
            self.assertEqual(assign_draft.run_draft(sp_id), 'done')
        gen.assert_called_once()

    def test_the_backfill_and_the_ready_sweep_leave_a_queued_draft_to_the_cron(self, _down):
        from apps.scholarship.services import autogenerate_ready_profiles
        self._assign(self.reviewer)
        with patch(GENERATE) as gen:
            out = io.StringIO()
            call_command('backfill_assigned_profiles', stdout=out)
            gen.assert_not_called()
            self.assertIn(f'skipped_queued=[{self.app.id}]', out.getvalue())
            ScholarshipApplication.objects.filter(pk=self.app.pk).update(
                assigned_to=None, status='profile_complete', profile_completed_at=timezone.now())
            self.assertEqual(autogenerate_ready_profiles()['generated'], 0)
            gen.assert_not_called()
        self.assertEqual(self._sp().finalise_state, 'drafting')
        SponsorProfile.objects.filter(application=self.app).update(finalise_state='')
        with patch(GENERATE, return_value=DRAFT) as gen:                       # the control
            self.assertEqual(autogenerate_ready_profiles()['generated'], 1)

    def test_skipped_while_gemini_reads_are_down(self, down):
        self._assign(self.reviewer)
        down.return_value = True
        with patch(GENERATE) as gen:
            self.assertTrue(assign_draft.draft_pending(time.monotonic())['skipped_outage'])
        gen.assert_not_called()
        self.assertEqual((self._sp().finalise_state, self._sp().finalise_attempts), ('drafting', 0))

    def test_no_row_is_claimed_once_the_run_is_past_its_deadline(self, _down):
        self._assign(self.reviewer)
        with patch(GENERATE) as gen:
            counts = assign_draft.draft_pending(0, clock=lambda: assign_draft.DEADLINE_SECONDS)
        self.assertEqual(counts['deferred'], 1)
        gen.assert_not_called()

    def test_the_flag_off_drops_the_queue_with_no_call(self, _down):
        self._assign(self.reviewer)
        with override_settings(CHECK2_AUTO_GENERATE=False), patch(GENERATE) as gen:
            self.assertEqual(assign_draft.draft_pending(time.monotonic())['dropped_flag_off'], 1)
        gen.assert_not_called()
        self.assertEqual(self._sp().finalise_state, '')

    def test_a_queued_draft_is_left_alone_by_the_finalise_worker(self, _down):
        from apps.scholarship import profile_finalise
        self._assign(self.reviewer)
        with patch('apps.scholarship.profile_finalise.refine_sponsor_profile') as refine:
            profile_finalise.run_pending()
        refine.assert_not_called()
        self.assertEqual(self._sp().finalise_state, 'drafting')


@override_settings(CHECK2_AUTO_GENERATE=False)
class TestFlagOff(TestCase):
    def test_no_queue_and_no_row_when_the_flag_is_off(self):
        app = make_application('profile_complete')
        sup = make_admin(super_admin=True)
        with patch(GENERATE) as gen:
            assignment.assign_reviewer(app, reviewer=make_admin(
                'reviewer', owning_org=app.owning_organisation, first_seen_at=timezone.now()), by_admin=sup)
        gen.assert_not_called()
        self.assertFalse(SponsorProfile.objects.filter(application=app).exists())
