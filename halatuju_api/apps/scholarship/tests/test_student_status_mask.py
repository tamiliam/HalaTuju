"""TD-164 (2026-10-03): what the STUDENT is shown while her decline email is embargoed.

The decision is immediate (`status='rejected'`) but the email waits out the cool-off
(`DECLINE_COOLOFF_DAYS`, 7 in production). Until it goes, `ApplicationReadSerializer.get_status`
hides the rejection. It used to hide it behind a hard-coded `'interviewed'` — a stage a declined
SHORTLISTED student never reached, shown for a week while every write path 403'd her. It now
shows the stage she was declined FROM: `pre_decline_status`, the same snapshot
`cancel_pending_decline` restores. `'recommended'` stays masked as `'interviewed'` (rule 2 of
the same method), and a legacy row with no snapshot falls back to `'interviewed'`.

ONE EXCEPTION (adversarial review F1, the lead's ruling, 2026-10-03): a pre-decline
`'shortlisted'` is shown as `'profile_complete'`. Shortlisted is the only snapshot that puts the
student back on a WRITE surface — the editable five-step form, where every Save / Confirm / upload
403s and the documents list reads empty — so she would write to help and a person would reveal the
decline before the email does. `'profile_complete'` is the locked, passive Action Centre.

The web reads every value `pre_decline_status` can hold — `LIVE_APPLICATION_STATES` in
`halatuju-web/src/lib/scholarship.ts` lists all of them except `recommended`, which never reaches
it.
"""
from django.test import TestCase, override_settings

from apps.scholarship import services
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.serializers import ApplicationReadSerializer
from apps.scholarship.tests.factories import make_admin, make_application


def _shown(app):
    app.refresh_from_db()
    return ApplicationReadSerializer(app).data['status']


@override_settings(DECLINE_COOLOFF_DAYS=7)
class EmbargoedDeclineMaskTest(TestCase):
    def setUp(self):
        self.admin = make_admin('reviewer', email='mask-admin@example.test')

    def _declined(self, stage, category='interview', **kw):
        app = make_application(stage, **kw)
        before = app.status
        services.admin_reject(app, self.admin, category)
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')                 # the real status
        self.assertEqual(app.pre_decline_status, before)         # the snapshot the mask reads
        self.assertTrue(app.pending_rejection_category)          # email still embargoed
        return app

    def test_shortlisted_decline_shows_the_locked_profile_complete(self):
        # The defect: this read 'interviewed' (a stage she never reached) for the whole cool-off.
        # Not 'shortlisted' either — that re-opens the editable form (review F1).
        self.assertEqual(_shown(self._declined('shortlisted')), 'profile_complete')

    def test_contractual_decline_of_an_active_student_shows_active(self):
        # It used to read 'interviewed' — a funded student shown back in review for a week.
        app = self._declined('active', category='contractual')
        self.assertEqual(_shown(app), 'active')

    def test_each_interview_reject_from_status_shows_itself(self):
        for stage, expected in (('profile_complete', 'profile_complete'),
                                ('interviewing', 'interviewing'),
                                ('awaiting_qc', 'interviewed')):
            with self.subTest(stage=stage):
                kw = {'outcome': 'decline'} if stage == 'awaiting_qc' else {}
                self.assertEqual(_shown(self._declined(stage, **kw)), expected)

    def test_contractual_decline_of_recommended_stays_masked_as_interviewed(self):
        # 'recommended' is internal and reversible — the student never sees it, rejected or not.
        app = self._declined('recommended', category='contractual')
        self.assertEqual(_shown(app), 'interviewed')

    def test_legacy_pending_row_without_snapshot_falls_back_to_interviewed(self):
        app = self._declined('shortlisted')
        ScholarshipApplication.objects.filter(pk=app.pk).update(pre_decline_status='')
        self.assertEqual(_shown(app), 'interviewed')

    def test_mask_lifts_once_the_email_has_gone(self):
        app = self._declined('shortlisted')
        ScholarshipApplication.objects.filter(pk=app.pk).update(pending_rejection_category='')
        self.assertEqual(_shown(app), 'rejected')

    def test_org_admin_reject_is_immediate_and_never_masked(self):
        # The org-admin drop sets no pending marker: the student is told at once.
        app = make_application('shortlisted')
        org_admin = make_admin('org_admin', email='mask-org@example.test')
        services.org_admin_reject(app, org_admin, 'Stuck for a month')
        self.assertEqual(_shown(app), 'rejected')
