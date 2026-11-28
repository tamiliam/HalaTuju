"""Owner ruling 28 Nov 2026 ("1"): the reviewer -> QC hand-off re-checks only what can still be fixed.

A SUBMITTED application (``profile_completed_at`` set) at ``interviewing`` or ``interviewed`` is past the
wizard: the student sees only the Action Centre. So the hand-off (verify-accept, and the cockpit's
clear-accept decision through the served ``handoff``) counts ONLY documents, consent and guardian docs
there, and ignores the quiz, the story, the address, the family roster and the funding answers. Every
other status — and an application never submitted — keeps the full ``application_completeness`` check.

Case 513 is the shape: submitted, interviewing, quiz wiped to {} by sign-in bug #81.
"""
import hashlib
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.services import (
    HANDOFF_LATE_STATUSES, HANDOFF_PARTS_LATE, application_completeness, handoff_parts,
    handoff_payload, handoff_ready,
)
from apps.scholarship.services.handoff import HANDOFF_PARTS_FULL
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_phase_c import SUPER, PhaseCBase

IGNORED_LATE = ('quiz_done', 'details_done', 'funding_done', 'address_done', 'family_done')
KEPT_LATE = ('documents_done', 'consent_done', 'guardian_docs_done')
ALL_DONE = {p: True for p in HANDOFF_PARTS_FULL}


def _completeness(**gaps):
    """A completeness answer with the named parts False and ``complete`` computed the way the real one is."""
    c = {**ALL_DONE, **gaps}
    c['complete'] = all(c[p] for p in HANDOFF_PARTS_FULL)
    return c


def _app(status, submitted=True):
    return SimpleNamespace(status=status, profile_completed_at=timezone.now() if submitted else None)


class TestTheRule(SimpleTestCase):
    """The rule on its own, part by part, status by status."""

    def test_the_parts_lists_are_the_ruling(self):
        self.assertEqual(set(HANDOFF_PARTS_LATE), set(KEPT_LATE))
        self.assertEqual(set(HANDOFF_PARTS_FULL), set(KEPT_LATE) | set(IGNORED_LATE))
        self.assertEqual(set(HANDOFF_LATE_STATUSES), {'interviewing', 'interviewed'})

    def test_late_and_submitted_ignores_each_unfixable_part(self):
        for status in ('interviewing', 'interviewed'):
            for part in IGNORED_LATE:
                with self.subTest(status=status, part=part):
                    c = _completeness(**{part: False})
                    self.assertFalse(c['complete'])              # the full answer still says no
                    self.assertEqual(handoff_ready(_app(status), c), (True, []))

    def test_late_and_submitted_ignores_all_five_at_once(self):
        c = _completeness(**{p: False for p in IGNORED_LATE})
        for status in ('interviewing', 'interviewed'):
            with self.subTest(status=status):
                self.assertEqual(handoff_ready(_app(status), c), (True, []))

    def test_late_and_submitted_keeps_each_fixable_part(self):
        for status in ('interviewing', 'interviewed'):
            for part in KEPT_LATE:
                with self.subTest(status=status, part=part):
                    self.assertEqual(handoff_ready(_app(status), _completeness(**{part: False})),
                                     (False, [part]))

    def test_early_statuses_keep_the_full_check(self):
        for status in ('shortlisted', 'profile_complete'):
            for part in HANDOFF_PARTS_FULL:
                with self.subTest(status=status, part=part):
                    self.assertEqual(handoff_ready(_app(status), _completeness(**{part: False})),
                                     (False, [part]))

    def test_not_submitted_keeps_the_full_check_even_late(self):
        for status in ('interviewing', 'interviewed', 'shortlisted', 'profile_complete'):
            for part in HANDOFF_PARTS_FULL:
                with self.subTest(status=status, part=part):
                    self.assertEqual(
                        handoff_ready(_app(status, submitted=False), _completeness(**{part: False})),
                        (False, [part]))

    def test_the_full_check_is_exactly_complete(self):
        """Outside the late arm, `ready` is `completeness['complete']` for every one-gap answer and none."""
        answers = [_completeness()] + [_completeness(**{p: False}) for p in HANDOFF_PARTS_FULL]
        for status in ('shortlisted', 'profile_complete'):
            for c in answers:
                self.assertEqual(handoff_ready(_app(status), c)[0], c['complete'])
        for c in answers:
            self.assertEqual(handoff_ready(_app('interviewing', submitted=False), c)[0], c['complete'])

    def test_parts_and_payload_shape(self):
        self.assertEqual(handoff_parts(_app('interviewing')), HANDOFF_PARTS_LATE)
        self.assertEqual(handoff_parts(_app('interviewing', submitted=False)), HANDOFF_PARTS_FULL)
        self.assertEqual(handoff_parts(_app('profile_complete')), HANDOFF_PARTS_FULL)
        self.assertEqual(handoff_payload(_app('interviewing'), _completeness(quiz_done=False)),
                         {'ready': True, 'missing': []})
        self.assertEqual(handoff_payload(_app('shortlisted'), _completeness(quiz_done=False)),
                         {'ready': False, 'missing': ['quiz_done']})


class TestCompletenessUntouched(SimpleTestCase):
    """⛔ `services/completeness.py` is DO NOT CHANGE; the hand-off rule lives beside it, not in it.
    If this fails you edited it: that needs the owner (H8 ruling), never a re-pin to make this pass."""

    PINNED = 'a48c906196f91517c55e804f2603fd949e4959e11d44300305bd96fe9ccfd519'

    def test_completeness_py_is_byte_for_byte_unchanged(self):
        path = Path(__file__).resolve().parents[1] / 'services' / 'completeness.py'
        digest = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        self.assertEqual(digest, self.PINNED)


class TestHandoffEndToEnd(PhaseCBase):
    """verify-accept and the served `handoff` on real applications."""

    VA = '/api/v1/admin/scholarship/applications/{}/verify-accept/'
    DETAIL = '/api/v1/admin/scholarship/applications/{}/'

    def _late(self, **overrides):
        """A submitted case at interviewing with the verdict recorded (the Recommend road), every part done."""
        app = make_application('verdict_recorded', outcome='recommend', cohort=self.cohort,
                               student=self.profile, bucket='A', aspirations='Be an auditor',
                               plans='Study hard', daily_life='Help at home', fears='Fees', **overrides)
        return self._complete(app)

    def _accept(self, app):
        self._auth(SUPER)
        return self.client.post(self.VA.format(app.id))

    def test_case_513_shape_passes_the_handoff(self):
        app = self._late()
        self.profile.student_signals = {}
        self.profile.save(update_fields=['student_signals'])
        self.assertIsNotNone(app.profile_completed_at)
        self.assertEqual(app.status, 'interviewing')
        self.assertFalse(application_completeness(app)['complete'])     # the full answer is unchanged
        self._auth(SUPER)
        d = self.client.get(self.DETAIL.format(app.id)).json()
        self.assertFalse(d['completeness']['complete'])
        self.assertFalse(d['completeness']['quiz_done'])
        self.assertEqual(d['handoff'], {'ready': True, 'missing': []})
        r = self._accept(app)
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')                      # AWAITING QC

    def test_story_family_and_funding_gaps_do_not_block_late(self):
        app = self._late()
        app.funding_need.delete()
        ScholarshipApplication.objects.filter(pk=app.id).update(aspirations='', father_occupation='')
        app.refresh_from_db()
        self.assertEqual(self._accept(app).status_code, 200)

    def test_consent_missing_still_refuses(self):
        app = self._late()
        app.consents.update(is_active=False)
        r = self._accept(app)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'incomplete_profile')
        self.assertEqual(r.json()['handoff_missing'], ['consent_done'])
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')

    def test_documents_not_done_still_refuses(self):
        app = self._late()
        ApplicantDocument.objects.filter(application=app, doc_type='ic').delete()
        r = self._accept(app)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['handoff_missing'], ['documents_done'])
        self._auth(SUPER)
        self.assertEqual(self.client.get(self.DETAIL.format(app.id)).json()['handoff'],
                         {'ready': False, 'missing': ['documents_done']})

    def test_not_submitted_late_case_keeps_the_full_check(self):
        app = self._late()
        ScholarshipApplication.objects.filter(pk=app.id).update(profile_completed_at=None)
        self.profile.student_signals = {}
        self.profile.save(update_fields=['student_signals'])
        app.refresh_from_db()
        r = self._accept(app)
        self.assertEqual(r.status_code, 400)
        self.assertIn('quiz_done', r.json()['handoff_missing'])

    def test_profile_complete_keeps_the_full_check(self):
        app = self._complete(self._assigned_app(status='profile_complete'))
        ScholarshipApplication.objects.filter(pk=app.id).update(verdict_decided_at=timezone.now())
        self.profile.student_signals = {}
        self.profile.save(update_fields=['student_signals'])
        app.refresh_from_db()
        r = self._accept(app)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['handoff_missing'], ['quiz_done'])
        self._auth(SUPER)
        self.assertEqual(self.client.get(self.DETAIL.format(app.id)).json()['handoff'],
                         {'ready': False, 'missing': ['quiz_done']})

    def test_shortlisted_keeps_the_full_check(self):
        app = self._complete(self._assigned_app(status='shortlisted'))
        ScholarshipApplication.objects.filter(pk=app.id).update(verdict_decided_at=timezone.now())
        self.profile.student_signals = {}
        self.profile.save(update_fields=['student_signals'])
        app.refresh_from_db()
        r = self._accept(app)
        self.assertEqual(r.status_code, 400)
        self.assertIn('quiz_done', r.json()['handoff_missing'])
