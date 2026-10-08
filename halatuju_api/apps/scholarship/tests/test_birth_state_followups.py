"""The request #31 follow-ups (2026-10-08): TD-371, TD-372, TD-373 and TD-375.

  * TD-371 — the "Born in" rule is re-checked at submit and at QC accept, and nowhere after. Two
    super doors could reach funding past it: releasing the IC lock on a `recommended` case (the IC
    can then change), and cancelling a reopen (which restores `recommended` without QC). The lock
    release is refused while ANY application on the profile is `recommended` on a ruled intake;
    the reopen-cancel is refused when it would restore `recommended` and the CURRENT IC fails the
    intake's CURRENT rule. Nothing else moves. Its review added: the route that refusal names
    (QC accept again, then cancel) works end to end, and the IC lock is also held while a HELD
    decline would restore `recommended` (closed at the lock, so the cancel stays a safe undo).
    `_revert_to_pool` was TD-376, and TD-377 holds the student's own IC at `recommended` — both in
    `test_birth_state_td376_377.py`.
  * TD-372 — a student who has an application and changes their own IC leaves one AUDIT log line,
    with no IC number and no state name in it.
  * TD-373 — the stored rule is read ONE way (`birth_state.stored_keys`) by the gate and by the
    intake-year row the Rules tab loads, so a hand-edited value cannot be enforced while the
    screen shows nothing.
  * TD-375 — a non-text QC override reason is no reason (400), never a 500; its review gave the
    QC reopen / reject comments, the reopen reason and the IC-lock release reason the same rule.
"""
import re
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from apps.courses.profile_claim import handle_claim
from apps.scholarship import birth_state as bs
from apps.scholarship import reopen as reopen_service
from apps.scholarship.models import ScholarshipCohort
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme,
    make_student,
)

#: Every other requirement cleared, so a verdict can only turn on the birth-state rule.
ONLY_BIRTH = dict(min_spm_a_count=None, min_spm_bplus_count=None, min_spm_credit_count=None,
                  min_stpm_pngk=None, min_merit_score=None, income_ceiling=None,
                  per_capita_ceiling=None)

SABAH_IC = '080505-12-1234'
SABAH_47_IC = '080505-47-1234'
SELANGOR_IC = '080505-10-1234'


def _super():
    return make_admin('super', super_admin=True)


# ── TD-371 (a): the IC-lock release ──────────────────────────────────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheLockReleaseWaitsForAReopen(TestCase):
    def setUp(self):
        self.client = authed_client(_super())

    def _release(self, app):
        return self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/release-nric-lock/',
            {'reason': 'The student says the IC was typed wrong.'}, format='json')

    def _locked(self, app):
        app.profile.refresh_from_db()
        return app.profile.nric_verified

    def test_refused_at_recommended_on_an_intake_with_the_rule(self):
        cohort = make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah'])
        app = make_application('recommended', cohort=cohort, student=make_student(nric=SABAH_IC))
        r = self._release(app)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'birth_state_rule_reopen_first')
        self.assertIn('Reopen the case first', r.json()['error'])
        self.assertTrue(self._locked(app))

    def test_refused_through_ANOTHER_application_of_the_same_profile(self):
        # The lock is the PROFILE's. Releasing it through an old declined application would free
        # the IC of the recommended one just the same.
        student = make_student(nric=SABAH_IC)
        make_application('recommended', student=student,
                         cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah']))
        old = make_application('rejected', student=student, cohort=make_cohort())
        r = self._release(old)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'birth_state_rule_reopen_first'))
        self.assertTrue(self._locked(old))

    def test_a_hand_stored_bare_string_rule_is_still_a_rule(self):
        cohort = make_cohort(**ONLY_BIRTH)
        ScholarshipCohort.objects.filter(pk=cohort.pk).update(allowed_birth_states='sabah')
        app = make_application('recommended', cohort=cohort, student=make_student(nric=SABAH_IC))
        self.assertEqual(self._release(app).status_code, 400)

    def test_allowed_at_recommended_when_the_intake_has_no_rule(self):
        app = make_application('recommended', cohort=make_cohort(**ONLY_BIRTH),
                               student=make_student(nric=SABAH_IC))
        self.assertEqual(self._release(app).status_code, 200)
        self.assertFalse(self._locked(app))

    def test_allowed_at_awarded_even_with_the_rule(self):
        # From `awarded` on a sponsor has committed the funding; a genuine IC correction must stay
        # possible there. (Its road back, `_revert_to_pool`, re-reads the rule since TD-376.)
        cohort = make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah'])
        app = make_application('awarded', cohort=cohort, student=make_student(nric=SABAH_IC))
        self.assertEqual(self._release(app).status_code, 200)
        self.assertFalse(self._locked(app))


# ── TD-371 (b): cancelling a reopen ──────────────────────────────────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestCancellingAReopenReReadsTheRule(TestCase):
    def setUp(self):
        self.admin = _super()
        self.client = authed_client(self.admin)

    def _reopened(self, states, stage='recommended', nric=SABAH_IC):
        cohort = make_cohort(**ONLY_BIRTH, allowed_birth_states=states)
        kw = {'outcome': 'recommend'} if stage == 'awaiting_qc' else {}
        app = make_application(stage, cohort=cohort, student=make_student(nric=nric), **kw)
        reopen_service.reopen_decision(app, by_admin=self.admin, reason='Checking the income.')
        return app

    def _swap_ic(self, app, nric):
        # What a lock release while reopened lets the student do.
        app.profile.nric, app.profile.nric_verified = nric, False
        app.profile.save(update_fields=['nric', 'nric_verified'])

    def _cancel(self, app):
        return self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/cancel-reopen/', {}, format='json')

    def _reverify(self, app):
        """The reviewer verify-accepts the (new) IC again, which re-locks it — since the TD-376/377
        review a ruled case cannot return to `recommended` on an unlocked IC at all. The
        completeness gate is not what these tests are about, so it is held open."""
        with mock.patch('apps.scholarship.views_admin.applications.application_completeness',
                        return_value={'complete': True}):
            r = self.client.post(
                f'/api/v1/admin/scholarship/applications/{app.pk}/verify-accept/', {},
                format='json')
        self.assertEqual(r.status_code, 200, r.content)
        app.profile.refresh_from_db()
        self.assertTrue(app.profile.nric_verified)

    def test_refused_when_it_would_restore_recommended_with_a_failing_ic(self):
        app = self._reopened(['sabah'])
        self.assertEqual(app.status, 'interviewed')
        self._swap_ic(app, SELANGOR_IC)
        self._reverify(app)                                     # locked again — on the NEW IC
        r = self._cancel(app)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'birth_state_rule_failed')
        self.assertEqual(r.json()['error'], reopen_service.BIRTH_STATE_RULE_FAILED)
        self.assertIn('Accept it through QC', r.json()['error'])
        self.assertIn('then cancel this reopen', r.json()['error'])
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertIsNotNone(app.decision_reopened_at)          # nothing was written
        self.assertIsNotNone(reopen_service.open_reopen(app))

    def test_allowed_when_the_current_ic_meets_the_rule(self):
        app = self._reopened(['sabah'])
        self._swap_ic(app, SABAH_47_IC)                         # another Sabah code
        self._reverify(app)
        self.assertEqual(self._cancel(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')

    def test_allowed_when_the_intake_has_no_rule(self):
        app = self._reopened([])
        self._swap_ic(app, SELANGOR_IC)
        self.assertEqual(self._cancel(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')

    def test_a_cancel_that_does_not_restore_recommended_is_untouched(self):
        # A QC reopen (interviewed -> interviewing) cancels back to AWAITING QC, where QC accept
        # will apply the floor anyway.
        app = self._reopened(['sabah'], stage='awaiting_qc')
        self.assertEqual(app.status, 'interviewing')
        self._swap_ic(app, SELANGOR_IC)
        self.assertEqual(self._cancel(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')

    def test_a_code_without_a_sentence_is_still_answered_with_the_code(self):
        app = make_application('recommended')
        r = self._cancel(app)
        self.assertEqual((r.status_code, r.json()), (400, {'error': 'not_reopened',
                                                           'code': 'not_reopened'}))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheRouteTheRefusalNames(TestCase):
    """Review of TD-371: the refusal is strict even for a case QC already accepted WITH a recorded
    override (a super then reopened it about income). Its message names the way through — QC
    accept again, recording the reason again, then cancel the reopen — and that way must work."""

    def setUp(self):
        self.cohort = make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah'])
        self.qc = make_admin('qc', owning_org=self.cohort.owning_organisation)
        self.super = _super()
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, who, app, action, body=None):
        return authed_client(who).post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/{action}/', body or {},
            format='json')

    def test_override_accept_reopen_refused_cancel_qc_reaccept_then_cancel(self):
        app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort,
                               student=make_student(nric=SELANGOR_IC))
        reason = 'Birth certificate shows Kota Kinabalu.'
        accept = {'decision': 'accept', 'override_reason': reason}
        self.assertEqual(self._post(self.qc, app, 'qc-decision', accept).status_code, 200)
        app.refresh_from_db()
        self.assertEqual((app.status, app.qc_override_reason), ('recommended', reason))

        # A super reopens it about something else entirely.
        r = self._post(self.super, app, 'reopen-decision', {'reason': 'Re-check the income.'})
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')

        # The cancel is refused — strictly, override or not — and says what to do instead.
        r = self._post(self.super, app, 'cancel-reopen')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'birth_state_rule_failed'))
        self.assertIn('recording the override reason again', r.json()['error'])
        self.assertIn('STRAIGHT AWAY', r.json()['error'])           # the double sponsor alert

        # QC accepts again with the reason recorded again …
        self.assertEqual(self._post(self.qc, app, 'qc-decision', accept).status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')
        self.assertIsNotNone(app.decision_reopened_at)        # the reopen is still open

        # … and THEN the cancel goes through and clears it, the case staying recommended.
        r = self._post(self.super, app, 'cancel-reopen')
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual((app.status, app.decision_reopened_at), ('recommended', None))
        self.assertIsNone(reopen_service.open_reopen(app))
        self.assertFalse(app.decision_reopens.get().resulted_in_change)


# ── TD-371, the review: a HELD decline holds the IC lock ──────────────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAHeldDeclineHoldsTheIcLock(TestCase):
    """A contractual decline of a `recommended` case is held; cancelling it restores `recommended`
    from the snapshot, skipping QC. The route past the floor was: release the IC lock during the
    hold, change the IC, cancel. It is closed at the LOCK RELEASE, not at the cancel — refusing the
    cancel also refused a genuine undo (the review's case: QC accepted the IC with a recorded
    override, a super declined by mistake, and the decline then went out). With the lock held, the
    IC cannot change during the hold, so the cancel is safe as it is."""

    def setUp(self):
        self.super = _super()
        self.client = authed_client(self.super)

    def _post(self, app, action, body=None):
        return self.client.post(f'/api/v1/admin/scholarship/applications/{app.pk}/{action}/',
                                body or {}, format='json')

    def _held(self, states, nric=SABAH_IC):
        app = make_application('recommended', student=make_student(nric=nric),
                               cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=states))
        self.assertEqual(self._post(app, 'reject', {'category': 'contractual'}).status_code, 200)
        app.refresh_from_db()
        self.assertEqual((app.status, app.pre_decline_status), ('rejected', 'recommended'))
        self.assertIsNotNone(app.decline_due_at)                     # held, the student not told
        self.assertTrue(app.profile.nric_verified)
        return app

    def _release(self, app):
        return self._post(app, 'release-nric-lock', {'reason': 'The IC was typed wrong.'})

    def test_the_restore_target_is_the_cancels_own(self):
        from apps.scholarship.services.decline import held_decline_restore_target
        held = self._held(['sabah'])
        self.assertEqual(held_decline_restore_target(held), 'recommended')
        qc_declined = make_application('rejected')                   # held, from AWAITING QC
        self.assertEqual(held_decline_restore_target(qc_declined), 'interviewed')
        self.assertIsNone(held_decline_restore_target(make_application('recommended')))

    def test_release_refused_while_the_hold_would_restore_recommended_on_a_ruled_intake(self):
        app = self._held(['sabah'])
        r = self._release(app)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'birth_state_rule_reopen_first'))
        self.assertIn('Let the decline go, or cancel it first', r.json()['error'])
        app.profile.refresh_from_db()
        self.assertTrue(app.profile.nric_verified)

    def test_release_allowed_when_the_hold_restores_to_something_else(self):
        # The QC-confirmed decline restores AWAITING QC, where QC accept applies the floor anyway.
        app = make_application('rejected', student=make_student(nric=SABAH_IC, nric_verified=True),
                               cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah']))
        self.assertEqual(self._release(app).status_code, 200)

    def test_release_allowed_once_the_student_has_been_told(self):
        from django.utils import timezone
        app = self._held(['sabah'])
        app.decline_email_sent_at = timezone.now()                   # nothing left to cancel
        app.save(update_fields=['decline_email_sent_at'])
        self.assertEqual(self._release(app).status_code, 200)

    def test_release_allowed_when_the_intake_has_no_rule(self):
        self.assertEqual(self._release(self._held([])).status_code, 200)

    def test_the_reviewers_case_an_override_accept_then_a_mistaken_decline_is_undone(self):
        cohort = make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah'])
        qc = make_admin('qc', owning_org=cohort.owning_organisation)
        app = make_application('awaiting_qc', outcome='recommend', cohort=cohort,
                               student=make_student(nric=SELANGOR_IC))
        with mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[]):
            r = authed_client(qc).post(
                f'/api/v1/admin/scholarship/applications/{app.pk}/qc-decision/',
                {'decision': 'accept', 'override_reason': 'Birth certificate shows Sandakan.'},
                format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._post(app, 'reject', {'category': 'contractual'}).status_code, 200)
        app.refresh_from_db()
        self.assertEqual((app.status, app.pre_decline_status), ('rejected', 'recommended'))
        self.assertEqual(self._release(app).status_code, 400)       # the IC cannot move …
        r = self._post(app, 'cancel-decline')                        # … so the undo is safe
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual((app.status, app.decline_due_at, app.qc_override_reason),
                         ('recommended', None, 'Birth certificate shows Sandakan.'))


# ── TD-372: an own-profile IC change leaves a trail ──────────────────────────────────────────
class TestAnOwnIcChangeIsAudited(TestCase):
    LOGGER = 'apps.courses.profile_claim'

    def _change(self, student, nric):
        uid = student.supabase_user_id
        with self.assertLogs(self.LOGGER, level='INFO') as logs:
            self.assertEqual(handle_claim(uid, uid, {'nric': nric}), ({'status': 'created'}, 200))
        lines = [m for m in logs.output if 'AUDIT nric_self_change' in m]
        self.assertEqual(len(lines), 1, logs.output)
        return lines[0]

    def _assert_no_identity(self, line, *nrics):
        for nric in nrics:
            self.assertNotIn(nric, line)
            self.assertNotIn(nric.replace('-', ''), line)
        self.assertIsNone(re.search(r'\d{6}-?\d{2}-?\d{4}', line))
        for name in ('sabah', 'selangor', 'Sabah', 'Selangor', 'IC code'):
            self.assertNotIn(name, line)

    def test_a_change_that_fails_a_rule_names_the_application_and_nothing_else(self):
        student = make_student(nric=SABAH_IC)
        ruled = make_application('shortlisted', student=student,
                                 cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah']))
        line = self._change(student, SELANGOR_IC)
        self.assertIn(f'profile_id={student.pk}', line)
        self.assertIn(f'app_ids={ruled.id}', line)
        self.assertIn('birth_state_changed=yes', line)
        self.assertIn(f'rule_fails={ruled.id}', line)
        self._assert_no_identity(line, SABAH_IC, SELANGOR_IC)

    def test_a_new_code_for_the_same_state_is_not_a_move(self):
        student = make_student(nric=SABAH_IC)
        app = make_application('shortlisted', student=student,
                               cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah']))
        line = self._change(student, SABAH_47_IC)
        self.assertIn(f'app_ids={app.id} birth_state_changed=no rule_fails=none', line)
        self._assert_no_identity(line, SABAH_IC, SABAH_47_IC)

    def test_every_application_is_listed_and_only_the_ruled_one_fails(self):
        student = make_student(nric=SABAH_IC)
        free = make_application('rejected', student=student, cohort=make_cohort())
        ruled = make_application('shortlisted', student=student,
                                 cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah']))
        line = self._change(student, SELANGOR_IC)
        self.assertIn(f'app_ids={free.id},{ruled.id}', line)
        self.assertIn(f'rule_fails={ruled.id}', line)

    def test_no_line_when_the_profile_has_no_application(self):
        student = make_student(nric=SABAH_IC)
        uid = student.supabase_user_id
        with self.assertNoLogs(self.LOGGER, level='INFO'):
            self.assertEqual(handle_claim(uid, uid, {'nric': SELANGOR_IC}),
                             ({'status': 'created'}, 200))
        student.refresh_from_db()
        self.assertEqual(student.nric, SELANGOR_IC)


# ── TD-373: one reader of the stored value ───────────────────────────────────────────────────
class TestTheStoredValueIsReadOneWay(SimpleTestCase):
    def test_stored_keys(self):
        cases = (
            (['sabah', 'sarawak'], ['sabah', 'sarawak']),
            (('sabah',), ['sabah']),
            (['Sabah'], ['Sabah']),            # wrong case KEPT as stored — shown, never dropped
            ('sabah', ['sabah']),              # a bare string is one key
            ('Sabah', ['Sabah']),
            (None, []), ('', []), ([], []),
            ([12], ['12']),
            ({'sabah': True}, ["{'sabah': True}"]),   # one entry: fails closed, no substring
        )
        for value, want in cases:
            with self.subTest(value=value):
                self.assertEqual(bs.stored_keys(value), want)

    def test_the_gate_reads_it_the_same_way(self):
        self.assertEqual(bs.check(SABAH_IC, 'sabah'), (True, ''))
        self.assertIs(bs.meets_rule(SABAH_IC, ['Sabah']), False)      # wrong case fails closed
        self.assertIs(bs.meets_rule(SABAH_IC, 'Sabah'), False)
        self.assertEqual(bs.check(SABAH_IC, ['Sabah']),
                         (False, 'born in Sabah (IC code 12); this intake accepts Sabah'))
        self.assertIsNone(bs.meets_rule(SELANGOR_IC, ''))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheRulesTabIsServedWhatTheGateEnforces(TestCase):
    def setUp(self):
        self.programme = make_programme()
        self.client = authed_client(make_admin('org_admin', owning_org=self.programme.organisation))

    def _served(self, stored):
        c = make_cohort(programme=self.programme, is_active=True, is_open=False)
        ScholarshipCohort.objects.filter(pk=c.pk).update(allowed_birth_states=stored)
        years = self.client.get(
            f'/api/v1/admin/scholarship/programmes/{self.programme.id}/years/').data['years']
        return next(y for y in years if y['id'] == c.id)['requirements']['allowed_birth_states']

    def test_a_bare_string_is_served_as_a_list(self):
        self.assertEqual(self._served('sabah'), ['sabah'])

    def test_a_wrong_case_key_is_served_as_stored(self):
        self.assertEqual(self._served(['Sabah']), ['Sabah'])

    def test_a_normal_list_and_the_empty_rule_are_unchanged(self):
        self.assertEqual(self._served(['sabah', 'sarawak']), ['sabah', 'sarawak'])
        self.assertEqual(self._served([]), [])


# ── TD-375: a non-text override reason ───────────────────────────────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestANonTextOverrideReasonIsNoReason(TestCase):
    def setUp(self):
        self.cohort = make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah'])
        self.qc = make_admin('qc', owning_org=self.cohort.owning_organisation)
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_number_or_a_list_is_a_400_not_a_500(self):
        for day, reason in enumerate((5, ['Birth certificate seen.'], {'why': 'x'}, True), 1):
            with self.subTest(reason=reason):
                # One Selangor IC per student: the recommend road locks it, and a locked IC is
                # unique.
                app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort,
                                       student=make_student(nric=f'08050{day}-10-1234'))
                r = authed_client(self.qc).post(
                    f'/api/v1/admin/scholarship/applications/{app.pk}/qc-decision/',
                    {'decision': 'accept', 'override_reason': reason}, format='json')
                self.assertEqual(r.status_code, 400)
                self.assertEqual((r.json()['code'], r.json()['facts']),
                                 ('verdict_gap_floor', ['birth_state']))
                app.refresh_from_db()
                self.assertEqual((app.status, app.qc_override_reason), ('interviewed', ''))


#: What a hand-made request can send where a reason or comment belongs.
NOT_TEXT = (5, ['A reason in a list.'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestEveryReasonOnTheseDoorsMustBeText(TestCase):
    """TD-375's review: the same 500 as the override reason, on the QC reopen and reject comments,
    the reopen reason and the IC-lock release reason. Each is read as missing, so the endpoint's
    own "required" 400 answers it, and nothing moves."""

    def setUp(self):
        self.super = _super()
        self.client = authed_client(self.super)

    def _post(self, app, action, body):
        return self.client.post(f'/api/v1/admin/scholarship/applications/{app.pk}/{action}/',
                                body, format='json')

    def test_qc_reopen_and_reject_comments(self):
        for decision in ('reopen', 'reject'):
            for comments in NOT_TEXT:
                with self.subTest(decision=decision, comments=comments):
                    app = make_application('awaiting_qc', outcome='recommend')
                    r = self._post(app, 'qc-decision',
                                   {'decision': decision, 'comments': comments})
                    self.assertEqual((r.status_code, r.json()['code']),
                                     (400, 'comments_required'))
                    app.refresh_from_db()
                    self.assertEqual((app.status, app.decision_reopened_at),
                                     ('interviewed', None))

    def test_the_reopen_reason(self):
        for reason in NOT_TEXT:
            with self.subTest(reason=reason):
                app = make_application('recommended')
                r = self._post(app, 'reopen-decision', {'reason': reason})
                self.assertEqual((r.status_code, r.json()['code']), (400, 'reason_required'))
                app.refresh_from_db()
                self.assertEqual((app.status, app.decision_reopened_at), ('recommended', None))

    def test_the_ic_lock_release_reason(self):
        for reason in NOT_TEXT:
            with self.subTest(reason=reason):
                app = make_application('awaiting_qc', outcome='recommend')   # the IC is locked
                r = self._post(app, 'release-nric-lock', {'reason': reason})
                self.assertEqual((r.status_code, r.json()['code']), (400, 'reason_required'))
                app.profile.refresh_from_db()
                self.assertTrue(app.profile.nric_verified)
