"""One application in play — the owner's ruling on TD-337 (2026-10-05), as BUILT.

The ruling is per organisation; what is built blocks an in-play application in ANY organisation
until the student side can carry two live applications (roadmap M2–M4; lead decision after the
adversarial review — see `services/apply_gate.py`). A FINISHED application never blocks.

`services/apply_gate.py` is the one home of the rule; the submit (`ApplicationListCreateView.post`)
and the apply page's question (`GET /api/v1/scholarship/apply-gate/`) both read it. These tests
build REAL rows for every status, because the rule's whole risk is a status nobody classified and
an embargo that leaks through the gate before the decline email goes.

The web half of the invariant is `studentScreenDrift.test.ts`: every list the rule can produce (at
most one in-play application beside any finished ones) must put the application screen on THAT
application. `TestTheServedListOfABlockedStudent` below is what makes the web half honest: it proves
that for such a list the student's own serialised list carries the gate's blocking application with
an in-play status, and every other application with a finished one.
"""
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.models import BursaryAgreement, ScholarshipApplication
from apps.scholarship.serializers import ApplicationReadSerializer
from apps.scholarship.services import apply_gate
from apps.scholarship.services.apply_gate import (
    ALREADY_APPLIED, FINISHED_STATUSES, IN_PLAY_STATUSES, IN_PROGRESS,
)
from apps.scholarship.student_status import student_facing_status
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_application, make_cohort, make_org, make_programme,
    make_student,
)

#: How to build an application whose RAW status is each of the thirteen, through the factory's
#: own stages (a status the product reaches without a stage of its own is an override on one).
#: `rejected` here is the decline whose email has GONE (embargo over); the embargoed one is below.
_BUILD = {
    'submitted': dict(stage='submitted'),
    'shortlisted': dict(stage='shortlisted'),
    'profile_complete': dict(stage='profile_complete'),
    'interviewing': dict(stage='interviewing'),
    'interviewed': dict(stage='awaiting_qc', outcome='recommend'),
    'recommended': dict(stage='recommended'),
    'awarded': dict(stage='awarded'),
    'active': dict(stage='active'),
    'maintenance': dict(stage='maintenance'),
    'closed': dict(stage='closed'),
    'rejected': dict(stage='rejected', pending_rejection_category='', decline_due_at=None,
                     pending_decline_by=''),
    'withdrawn': dict(stage='submitted', status='withdrawn'),
    'expired': dict(stage='expired'),
}

#: Declines whose email is still EMBARGOED, by the stage they were declined from — every stage
#: `admin_reject` / `org_admin_reject` accepts (`INTERVIEW_REJECT_FROM`, the contractual three),
#: and '' for a legacy row with no snapshot. She is shown that stage, so each must stay in play.
_EMBARGOED_FROM = ('shortlisted', 'profile_complete', 'interviewing', 'interviewed',
                   'recommended', 'active', 'maintenance', '')


def _build(status, cohort, student, **extra):
    spec = dict(_BUILD[status])
    spec.update(extra)
    return make_application(spec.pop('stage'), cohort=cohort, student=student, **spec)


def _embargoed(pre, cohort, student, **extra):
    return make_application('rejected', cohort=cohort, student=student, pre_decline_status=pre,
                            **extra)


def _round(org=None, **kw):
    return make_cohort(programme=make_programme(organisation=org or make_org()), **kw)


class TestEveryStatusIsClassified(TestCase):
    """A new status must be classified before it can ship — never guessed by the gate."""

    def test_in_play_and_finished_partition_STATUS_CHOICES_exactly(self):
        every = {code for code, _ in ScholarshipApplication.STATUS_CHOICES}
        self.assertEqual(IN_PLAY_STATUSES & FINISHED_STATUSES, frozenset())
        self.assertEqual(IN_PLAY_STATUSES | FINISHED_STATUSES, every)
        self.assertEqual(set(_BUILD), every)

    def test_finished_is_exactly_the_four_the_owner_named(self):
        self.assertEqual(FINISHED_STATUSES, {'rejected', 'withdrawn', 'closed', 'expired'})


class TestStudentFacingStatusHasOneHome(TestCase):
    """The serializer and the gate read ONE function, so the embargo is masked the same way."""

    def setUp(self):
        self.student = make_student()

    def test_the_serializer_answers_exactly_what_the_function_answers(self):
        for status in _BUILD:
            app = _build(status, make_cohort(), self.student)
            self.assertEqual(ApplicationReadSerializer(app).data['status'],
                             student_facing_status(app), status)
        for pre in _EMBARGOED_FROM:
            app = _embargoed(pre, make_cohort(), self.student)
            self.assertEqual(ApplicationReadSerializer(app).data['status'],
                             student_facing_status(app), pre)

    def test_an_embargoed_decline_reads_as_the_stage_it_left(self):
        cases = {'interviewed': 'interviewed', 'shortlisted': 'profile_complete',
                 'recommended': 'interviewed', '': 'interviewed', 'active': 'active'}
        for pre, shown in cases.items():
            self.assertEqual(student_facing_status(
                _embargoed(pre, make_cohort(), self.student)), shown, pre)

    def test_a_decline_whose_email_went_reads_rejected(self):
        self.assertEqual(student_facing_status(
            _build('rejected', make_cohort(), self.student)), 'rejected')


class TestTheRule(TestCase):
    """Real rows; the verdict for a NEW round (B) of the same organisation as her round (A)."""

    def setUp(self):
        self.org = make_org()
        self.round_a = _round(self.org, is_open=False)
        self.round_b = _round(self.org)
        self.student = make_student()

    def test_every_status_in_another_round_of_the_same_organisation(self):
        for status in _BUILD:
            with self.subTest(status=status):
                student = make_student()
                app = _build(status, self.round_a, student)
                v = apply_gate.apply_verdict(student, self.round_b)
                if status in FINISHED_STATUSES:
                    self.assertEqual((v.reason, v.application), ('', None))
                else:
                    self.assertEqual((v.reason, v.application), (IN_PROGRESS, app))

    def test_every_status_in_ANOTHER_organisation_blocks_or_not_exactly_alike(self):
        """Stricter than the per-organisation ruling, on purpose, until M2 (module docstring):
        an in-play application in organisation B blocks A; a finished one in B does not."""
        for status in _BUILD:
            with self.subTest(status=status):
                student = make_student()
                app = _build(status, _round(is_open=False), student)
                v = apply_gate.apply_verdict(student, self.round_b)
                expected = ('', None) if status in FINISHED_STATUSES else (IN_PROGRESS, app)
                self.assertEqual((v.reason, v.application), expected)

    def test_ruling_1_an_awarded_student_may_not_apply_to_another_programme_of_her_organisation(self):
        _build('active', self.round_a, self.student)
        self.assertEqual(apply_gate.apply_verdict(self.student, self.round_b).reason, IN_PROGRESS)

    def test_same_round_finished_is_already_applied_and_expired_is_not(self):
        for status in ('rejected', 'withdrawn', 'closed'):
            with self.subTest(status=status):
                student = make_student()
                app = _build(status, self.round_b, student)
                v = apply_gate.apply_verdict(student, self.round_b)
                self.assertEqual((v.reason, v.application), (ALREADY_APPLIED, app))
        student = make_student()
        _build('expired', self.round_b, student)
        self.assertTrue(apply_gate.apply_verdict(student, self.round_b).allowed)

    def test_in_play_beats_same_round(self):
        live = _build('shortlisted', self.round_a, self.student)
        _build('withdrawn', self.round_b, self.student)
        v = apply_gate.apply_verdict(self.student, self.round_b)
        self.assertEqual((v.reason, v.application), (IN_PROGRESS, live))

    def test_the_embargo_does_not_leak_both_ways(self):
        """Embargoed → still in play (blocked); email gone → finished (allowed)."""
        app = _embargoed('interviewed', self.round_a, self.student)
        self.assertEqual(apply_gate.apply_verdict(self.student, self.round_b).reason, IN_PROGRESS)
        app.pending_rejection_category = ''
        app.decline_due_at = None
        app.save(update_fields=['pending_rejection_category', 'decline_due_at'])
        self.assertTrue(apply_gate.apply_verdict(self.student, self.round_b).allowed)

    def test_every_embargoed_variant_is_in_play_in_any_organisation(self):
        for pre in _EMBARGOED_FROM:
            with self.subTest(pre=pre):
                student = make_student()
                _embargoed(pre, _round(is_open=False), student)
                self.assertEqual(apply_gate.apply_verdict(student, self.round_b).reason,
                                 IN_PROGRESS)

    def test_legacy_data_with_two_in_play_names_the_newest(self):
        older = _build('maintenance', self.round_a, self.student,
                       submitted_at=timezone.now() - timezone.timedelta(days=400))
        newer = _build('submitted', _round(is_open=False), self.student)
        self.assertNotEqual(older, newer)
        self.assertEqual(apply_gate.apply_verdict(self.student, self.round_b).application, newer)

    def test_no_profile_is_allowed_and_never_matches_orphaned_rows(self):
        _build('submitted', self.round_a, self.student)
        ScholarshipApplication.objects.update(profile=None)
        self.assertTrue(apply_gate.apply_verdict(None, self.round_b).allowed)
        self.assertIsNone(apply_gate.in_play_application(''))

    def test_over_rounds(self):
        other = _round()
        self.assertTrue(apply_gate.verdict_over_rounds(self.student, [self.round_b, other]).allowed)
        _build('rejected', other, self.student)
        self.assertTrue(apply_gate.verdict_over_rounds(self.student, [self.round_b, other]).allowed)
        _build('closed', self.round_b, self.student)
        self.assertEqual(apply_gate.verdict_over_rounds(self.student, [other, self.round_b]).reason,
                         ALREADY_APPLIED)
        _build('submitted', self.round_a, self.student)     # in play → refused for every round
        self.assertEqual(apply_gate.verdict_over_rounds(self.student, [other, self.round_b]).reason,
                         IN_PROGRESS)
        self.assertTrue(apply_gate.verdict_over_rounds(self.student, []).allowed)

    def test_in_play_application_is_the_current_one(self):
        _build('closed', self.round_a, self.student)
        self.assertIsNone(apply_gate.in_play_application(self.student.pk))
        live = _build('awarded', self.round_b, self.student)
        self.assertEqual(apply_gate.in_play_application(self.student.pk), live)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheServedListOfABlockedStudent(TestCase):
    """THE INVARIANT, api half. For every list the rule can produce — at most ONE in-play
    application (every in-play status and every embargoed shape) beside any number of finished or
    expired ones — when the gate says `application_in_progress`:
      * the application it names is that in-play application;
      * the student's OWN list serialises it with an in-play status, never 'recommended';
      * and every OTHER application in the list with a finished status.
    `studentScreenDrift.test.ts` then proves the application screen shows exactly that one."""

    COMPANIONS = ([], ['rejected'], ['withdrawn'], ['closed'], ['expired'],
                  ['rejected', 'withdrawn', 'closed', 'expired'])

    def test_every_in_play_shape_beside_every_set_of_finished_ones(self):
        served_seen = set()
        shapes = ([('status', s) for s in sorted(IN_PLAY_STATUSES)]
                  + [('embargoed', pre) for pre in _EMBARGOED_FROM])
        for kind, value in shapes:
            for companions in self.COMPANIONS:
                with self.subTest(shape=f'{kind}:{value}', companions=companions):
                    student = make_student()
                    for done in companions:
                        _build(done, _round(is_open=False), student)
                    old = _round(is_open=False)
                    live = (_build(value, old, student) if kind == 'status'
                            else _embargoed(value, old, student))
                    res = authed_client(student).get('/api/v1/scholarship/apply-gate/').json()
                    self.assertEqual((res['reason'], res['application_id']), (IN_PROGRESS, live.id))
                    served = {a['id']: a['status'] for a in authed_client(student).get(
                        '/api/v1/scholarship/applications/').json()['applications']}
                    self.assertIn(served.pop(live.id), IN_PLAY_STATUSES - {'recommended'})
                    self.assertTrue(set(served.values()) <= FINISHED_STATUSES, served)
                    served_seen.add(student_facing_status(live))
        self.assertEqual(served_seen, IN_PLAY_STATUSES - {'recommended'})


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheSubmitRefuses(TestCase):
    URL = '/api/v1/scholarship/applications/'

    def setUp(self):
        self.org = make_org()
        self.old = _round(self.org, is_open=False)
        self.gift = make_programme(organisation=self.org)
        self.new = make_cohort(programme=self.gift)
        self.student = make_student(contact_email='s@example.test')
        self.client = authed_client(self.student)

    def _post(self):
        return self.client.post(self.URL, {'programme_code': self.gift.code}, format='json')

    def test_in_play_in_the_same_organisation_is_a_409_with_its_code(self):
        _build('awarded', self.old, self.student)
        r = self._post()
        self.assertEqual((r.status_code, r.json()['code']), (409, IN_PROGRESS))
        self.assertIn('error', r.json())
        self.assertEqual(ScholarshipApplication.objects.filter(cohort=self.new).count(), 0)

    def test_in_play_in_ANOTHER_organisation_is_refused_too(self):
        _build('submitted', _round(is_open=False), self.student)
        self.assertEqual(self._post().json()['code'], IN_PROGRESS)

    def test_a_finished_student_may_apply_to_a_later_round_or_another_organisation(self):
        _build('rejected', self.old, self.student)
        _build('closed', _round(is_open=False), self.student)
        r = self._post()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(ScholarshipApplication.objects.get(cohort=self.new).profile, self.student)

    def test_the_same_round_twice_is_already_applied(self):
        _build('withdrawn', self.new, self.student)
        r = self._post()
        self.assertEqual((r.status_code, r.json()['code']), (409, ALREADY_APPLIED))
        self.assertEqual(r.json()['error'], 'You have already applied to this round.')

    def test_an_embargoed_decline_still_blocks_at_submit(self):
        _embargoed('interviewed', self.old, self.student)
        self.assertEqual(self._post().json()['code'], IN_PROGRESS)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestThePageCanAsk(TestCase):
    URL = '/api/v1/scholarship/apply-gate/'

    def setUp(self):
        self.org = make_org()
        self.old = _round(self.org, is_open=False)
        self.gift = make_programme(organisation=self.org)
        self.new = make_cohort(programme=self.gift)
        self.student = make_student()
        self.client = authed_client(self.student)

    def _ask(self, code=''):
        return self.client.get(self.URL + (f'?programme={code}' if code else '')).json()

    def test_signed_out_is_refused(self):
        from rest_framework.test import APIClient
        self.assertIn(APIClient().get(self.URL).status_code, (401, 403))

    def test_nothing_held_is_allowed(self):
        self.assertEqual(self._ask(self.gift.code),
                         {'allowed': True, 'reason': '', 'application_id': None})

    def test_in_play_names_her_own_application(self):
        app = _build('profile_complete', self.old, self.student)
        self.assertEqual(self._ask(self.gift.code),
                         {'allowed': False, 'reason': IN_PROGRESS, 'application_id': app.id})
        self.assertEqual(self._ask()['reason'], IN_PROGRESS)     # the one open round, bare

    def test_same_round_finished_is_already_applied(self):
        app = _build('rejected', self.new, self.student)
        self.assertEqual(self._ask(self.gift.code),
                         {'allowed': False, 'reason': ALREADY_APPLIED, 'application_id': app.id})

    def test_another_students_applications_are_not_hers(self):
        _build('active', self.old, make_student())
        self.assertTrue(self._ask(self.gift.code)['allowed'])

    def test_several_open_bare_refused_only_when_already_applied_to_every_one(self):
        other_gift = make_programme(organisation=make_org())
        other = make_cohort(programme=other_gift)
        _build('closed', self.new, self.student)
        self.assertTrue(self._ask()['allowed'])                 # the chooser will ask
        self.assertEqual(self._ask(self.gift.code)['reason'], ALREADY_APPLIED)
        self.assertTrue(self._ask(other_gift.code)['allowed'])
        _build('withdrawn', other, self.student)
        self.assertEqual(self._ask()['reason'], ALREADY_APPLIED)

    def test_one_programme_with_two_open_rounds_reads_like_the_bare_case(self):
        second = make_cohort(programme=self.gift)
        _build('withdrawn', self.new, self.student)
        self.assertTrue(self._ask(self.gift.code)['allowed'])
        _build('withdrawn', second, self.student)
        self.assertEqual(self._ask(self.gift.code)['reason'], ALREADY_APPLIED)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestEveryVisitOfAnInPlayStudent(TestCase):
    """Closed is the NORMAL state for most of the year, and an applicant keeps the link she applied
    through: on ANY visit an in-play student is answered `application_in_progress`. The answer does
    not depend on the code — known, unknown, closed, another organisation's — so it cannot be used
    to find out which codes exist or whose they are."""
    URL = '/api/v1/scholarship/apply-gate/'

    def setUp(self):
        self.org = make_org()
        self.gift = make_programme(organisation=self.org)
        self.round = make_cohort(programme=self.gift, is_open=False)     # her gift, now closed
        self.student = make_student()
        self.client = authed_client(self.student)

    def _ask(self, code=''):
        return self.client.get(self.URL + (f'?programme={code}' if code else '')).json()

    def _codes(self):
        """Every kind of visit: her closed gift, a retired alias of it, another programme of her
        organisation (closed), another organisation's (closed, and open), an unknown code, bare."""
        from apps.scholarship.models import ProgrammeCodeAlias
        ProgrammeCodeAlias.objects.get_or_create(programme=self.gift, code='old-code-for-her-gift')
        sibling = make_programme(organisation=self.org)
        make_cohort(programme=sibling, is_open=False)
        foreign_closed = make_programme(organisation=make_org())
        make_cohort(programme=foreign_closed, is_open=False)
        foreign_open = make_programme(organisation=make_org())
        make_cohort(programme=foreign_open)
        return [self.gift.code, 'old-code-for-her-gift', sibling.code, foreign_closed.code,
                foreign_open.code, 'no-such-gift', '']

    def test_in_play_every_visit_is_in_progress_naming_her_application(self):
        app = _build('interviewing', self.round, self.student)
        for code in self._codes():
            with self.subTest(code=code):
                self.assertEqual(self._ask(code), {
                    'allowed': False, 'reason': IN_PROGRESS, 'application_id': app.id})

    def test_every_in_play_status_on_her_closed_gift(self):
        for status in sorted(IN_PLAY_STATUSES):
            with self.subTest(status=status):
                student = make_student()
                _build(status, self.round, student)
                self.assertEqual(apply_gate.verdict_for_visit(student, self.gift.code).reason,
                                 IN_PROGRESS)

    def test_the_embargoed_decline_on_a_closed_gift_is_still_bounced(self):
        """No leak: the email has not gone, so she is shown the stage she left, and sent there."""
        _embargoed('interviewed', self.round, self.student)
        self.assertEqual(self._ask(self.gift.code)['reason'], IN_PROGRESS)
        self.assertEqual(self._ask()['reason'], IN_PROGRESS)

    def test_nothing_in_play_unknown_and_closed_codes_alike_are_allowed(self):
        _build('withdrawn', self.round, self.student)
        for code in self._codes():
            with self.subTest(code=code):
                self.assertTrue(self._ask(code)['allowed'])

    def test_a_finished_student_on_her_closed_gift_is_allowed_and_meets_the_closed_card(self):
        for status in sorted(FINISHED_STATUSES):
            with self.subTest(status=status):
                student = make_student()
                _build(status, self.round, student)
                self.assertTrue(apply_gate.verdict_for_visit(student, self.gift.code).allowed)

    def test_already_applied_still_needs_an_open_round(self):
        _build('rejected', self.round, self.student)
        self.assertEqual(self._ask(self.gift.code)['reason'], '')

    def test_the_submit_path_is_unchanged(self):
        _build('interviewing', self.round, self.student)
        later = make_cohort(programme=self.gift)
        self.assertEqual(apply_gate.apply_verdict(self.student, later).reason, IN_PROGRESS)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestTheAgreementFollowsHerCurrentApplication(TestCase):
    """`GET /scholarship/bursary-agreement/` answers for her CURRENT (in-play) application. A
    graduate with a signed agreement on a closed application, later awarded on a new one, was shown
    the OLD agreement ("awaiting countersignature") instead of her offer."""
    URL = '/api/v1/scholarship/bursary-agreement/'

    def setUp(self):
        self.org = make_org()
        self.student = make_student()
        self.client = authed_client(self.student)

    def _signed(self, app):
        now = timezone.now()
        return BursaryAgreement.objects.create(
            application=app, version='2026-v1', pdf_storage_path=f'{app.id}/agreement.pdf',
            student_signed_at=now, guarantor_signed_at=now, foundation_signed_at=now)

    def test_old_signed_and_closed_new_awarded_unsigned_answers_none(self):
        self._signed(_build('closed', _round(self.org, is_open=False), self.student))
        _build('awarded', _round(self.org), self.student)
        self.assertEqual(self.client.get(self.URL).status_code, 404)   # as for any unsigned student

    def test_old_signed_only_is_unchanged(self):
        ag = self._signed(_build('closed', _round(self.org, is_open=False), self.student))
        r = self.client.get(self.URL)
        self.assertEqual((r.status_code, r.json()['id']), (200, ag.id))

    def test_the_current_application_with_its_own_agreement(self):
        self._signed(_build('closed', _round(self.org, is_open=False), self.student))
        ag = self._signed(_build('active', _round(self.org), self.student))
        r = self.client.get(self.URL)
        self.assertEqual((r.status_code, r.json()['id']), (200, ag.id))

    def test_the_current_one_wins_even_when_the_older_id_is_higher(self):
        """Ordering by id alone would pick whichever row was created last; the current one wins."""
        current = _build('maintenance', _round(self.org), self.student,
                         submitted_at=timezone.now())
        ag = self._signed(current)
        self._signed(_build('closed', _round(self.org, is_open=False), self.student,
                            submitted_at=timezone.now() - timezone.timedelta(days=400)))
        self.assertEqual(self.client.get(self.URL).json()['id'], ag.id)
