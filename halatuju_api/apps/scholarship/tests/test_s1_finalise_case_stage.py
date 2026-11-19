"""Sprint S1, TD-664 (f): the background profile jobs make no paid call for a case that is not OPEN.

A profile queued while the case was open used to be refined (and paid for) after an award, a
decline, a withdrawal or a close. Now `profile_finalise.run_finalise` asks `staff_lifecycle.case_stage`
after the claim and drops the job ('case_closed') with no Gemini call. The first-assign draft
(`assign_draft.run_draft`) had the same shape and gets the same check. Gemini is mocked throughout.
"""
import time
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import assign_draft
from apps.scholarship import profile_finalise as pf
from apps.scholarship.models import InterviewSession, ScholarshipApplication, SponsorProfile
from apps.scholarship.services import assignment
from apps.scholarship.tests.factories import answered_findings, make_admin, make_application

REFINE = 'apps.scholarship.profile_finalise.refine_sponsor_profile'
BLURB = 'apps.scholarship.profile_finalise.generate_anon_blurb'
DOWN = 'apps.scholarship.services.outage.gemini_reads_down'
GENERATE = 'apps.scholarship.profile_engine.generate_sponsor_profile'
FINAL = {'markdown': '## Determined, and wants to study engineering',
         'model_used': 'gemini-3.8-flash', 'prompt_version': 'v-test'}
DRAFT = {'markdown': 'Draft profile.', 'model_used': 'test', 'prompt_version': 'v-test'}


def _queued(app):
    InterviewSession.objects.create(application=app, status='submitted', submitted_at=timezone.now(),
                                    findings=answered_findings(app))
    SponsorProfile.objects.update_or_create(application=app, defaults={'draft_markdown': '## Draft'})
    _, sp = pf.queue_finalise(app, 'en')
    sp.save(update_fields=pf.QUEUE_FIELDS)
    return sp


def _move(app, **fields):
    """The case moves on after the job was queued (an award, a decline, a withdrawal, a close)."""
    ScholarshipApplication.objects.filter(pk=app.pk).update(**fields)


#: Each not-OPEN case the cron may meet, as the fields that put it there.
CLOSED_CASES = {
    'awarded': {'status': 'awarded', 'awarded_at': timezone.now()},
    'rejected': {'status': 'rejected'},
    'withdrawn': {'status': 'withdrawn'},
    'closed_before_award': {'status': 'closed'},
}


@patch(DOWN, return_value=False)
class TestFinaliseAsksTheCaseStage(TestCase):
    def test_an_open_case_is_still_refined(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        sp = _queued(app)
        with patch(REFINE, return_value=FINAL) as refine, patch(BLURB, return_value=''):
            counts = pf.run_pending()
        self.assertEqual((counts['done'], counts['case_closed']), (1, 0))
        refine.assert_called_once()
        sp.refresh_from_db()
        self.assertEqual(sp.final_markdown, FINAL['markdown'])

    def test_each_closed_case_is_dropped_with_no_refine_call(self, _down):
        for name, fields in CLOSED_CASES.items():
            with self.subTest(name):
                app = make_application('verdict_recorded', outcome='recommend')
                sp = _queued(app)
                _move(app, **fields)
                with patch(REFINE) as refine, patch(BLURB) as blurb:
                    self.assertEqual(pf.run_finalise(sp.pk), 'case_closed')
                refine.assert_not_called()
                blurb.assert_not_called()
                sp.refresh_from_db()
                self.assertEqual((sp.finalise_state, sp.final_markdown), ('', ''))
                self.assertIsNone(sp.finalise_claimed_at)

    def test_a_reopened_pre_award_decline_is_open_again(self, _down):
        app = make_application('verdict_recorded', outcome='recommend')
        sp = _queued(app)
        _move(app, status='rejected', decision_reopened_at=timezone.now())
        with patch(REFINE, return_value=FINAL) as refine, patch(BLURB, return_value=''):
            self.assertEqual(pf.run_finalise(sp.pk), 'done')
        refine.assert_called_once()

    def test_a_stale_token_is_not_dropped(self, _down):
        # A re-record restamped the job after this run read it: the drop leaves the newer job alone.
        app = make_application('verdict_recorded', outcome='recommend')
        sp = _queued(app)
        _move(app, status='withdrawn')
        old = sp.finalise_requested_at
        newer = old + timedelta(seconds=5)
        SponsorProfile.objects.filter(pk=sp.pk).update(finalise_requested_at=newer)
        self.assertEqual(pf._drop_closed(sp.pk, app.pk, old), 'superseded')
        sp.refresh_from_db()
        self.assertEqual((sp.finalise_state, sp.finalise_requested_at), ('pending', newer))

    def test_run_pending_counts_case_closed(self, _down):
        open_app = make_application('verdict_recorded', outcome='recommend')
        _queued(open_app)
        shut = make_application('verdict_recorded', outcome='recommend')
        _queued(shut)
        _move(shut, status='withdrawn')
        with patch(REFINE, return_value=FINAL) as refine, patch(BLURB, return_value=''):
            counts = pf.run_pending()
        self.assertEqual((counts['done'], counts['case_closed'], counts['error']), (1, 1, 0))
        self.assertEqual(refine.call_count, 1)


@override_settings(CHECK2_AUTO_GENERATE=True)
@patch(DOWN, return_value=False)
class TestFirstAssignDraftAsksTheCaseStage(TestCase):
    def _assigned(self):
        app = make_application('profile_complete')
        boss = make_admin(super_admin=True)
        reviewer = make_admin('reviewer', first_seen_at=timezone.now(),
                              owning_org=app.owning_organisation, name='Rohini')
        assignment.assign_reviewer(app, reviewer=reviewer, by_admin=boss)
        return app, SponsorProfile.objects.get(application=app)

    def test_an_open_case_is_still_drafted(self, _down):
        _, sp = self._assigned()
        with patch(GENERATE, return_value=DRAFT) as gen:
            counts = assign_draft.draft_pending(time.monotonic())
        self.assertEqual((counts['done'], counts['case_closed']), (1, 0))
        gen.assert_called_once()

    def test_a_case_that_left_open_is_let_go_with_no_call(self, _down):
        app, sp = self._assigned()
        _move(app, status='withdrawn')
        with patch(GENERATE) as gen:
            counts = assign_draft.draft_pending(time.monotonic())
        self.assertEqual((counts['case_closed'], counts['error']), (1, 0))
        gen.assert_not_called()
        sp.refresh_from_db()
        self.assertEqual(sp.finalise_state, '')
        self.assertIsNone(sp.finalise_claimed_at)
