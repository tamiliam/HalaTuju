"""Sprint S1 (TD-664 a-c, the activity box): every served flag equals what its door does.

Serve, never derive: the cockpit and the scholar file read flags the server computes with the same
function the door asks. Pinned per stage and per viewer through the real endpoints:
  * `can_qc` — the QC door (`qc-decision/`) answers 403 to the role exactly when `can_qc` is false;
  * `can_close_pre_award` — the close door refuses a pre-award close exactly when it is false;
  * `case_stage` — the verdict door answers `case_closed` exactly when the stage is not `open`;
  * `controls.can_write_activity` — the activity POST is let through exactly when it is true
    (a `scholars` holder on an open file; never a closed file, a mentor, or a staff mentor without the key).
"""
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import mentoring
from apps.scholarship.models import Mentor
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)
from apps.scholarship.tests.test_mentoring import _scholar, make_mentor

APPS = '/api/v1/admin/scholarship/applications/'
FILES = '/api/v1/admin/scholarship/scholars/'
LOCMEM = override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@LOCMEM
class _World(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', owning_org=org)
        cls.qc = make_admin('qc', owning_org=org)
        cls.org_admin = make_admin('org_admin', owning_org=org)
        cls.super = make_admin(super_admin=True)

    def case(self, stage, outcome=None, **kw):
        return make_application(stage, outcome=outcome, cohort=self.cohort, reviewer=self.reviewer, **kw)

    def flags(self, who, app):
        r = authed_client(who).get(f'{APPS}{app.id}/')
        self.assertEqual(r.status_code, 200, r.content[:200])
        return r.json()


class TheQcFlagIsTheQcDoor(_World):
    def test_can_qc_is_false_exactly_where_the_door_refuses_the_role(self):
        for who, expected in ((self.reviewer, False), (self.qc, True), (self.org_admin, True),
                              (self.super, True)):
            with self.subTest(who=who.role):
                app = self.case('awaiting_qc', 'recommend')
                self.assertIs(self.flags(who, app)['can_qc'], expected)
                r = authed_client(who).post(f'{APPS}{app.id}/qc-decision/', {}, format='json')
                self.assertEqual(r.status_code == 403, not expected, r.content[:200])

    def test_can_qc_is_the_key_not_the_stage(self):
        # The panel shows by stage on the web; the key is served at every stage.
        for stage in ('submitted', 'interviewing', 'active'):
            with self.subTest(stage=stage):
                self.assertIs(self.flags(self.qc, self.case(stage))['can_qc'], True)
                self.assertIs(self.flags(self.reviewer, self.case(stage))['can_qc'], False)


class TheCloseFlagIsTheCloseDoor(_World):
    def test_a_pre_award_close_is_offered_exactly_where_the_door_allows_it(self):
        for who in (self.reviewer, self.qc, self.org_admin, self.super):
            with self.subTest(who=who.role):
                app = self.case('submitted')
                offered = self.flags(who, app)['can_close_pre_award']
                r = authed_client(who).post(f'{APPS}{app.id}/close/', {'closure_reason': 'stalled'},
                                            format='json')
                self.assertEqual(r.status_code == 200, offered, r.content[:200])
                if offered:
                    self.assertEqual(r.json()['status'], 'closed')
                    self.assertEqual(r.json()['case_stage'], 'pre_award_end')   # the reply serves it too
                mail.outbox.clear()

    def test_the_assigned_reviewer_is_not_offered_it(self):
        self.assertIs(self.flags(self.reviewer, self.case('submitted'))['can_close_pre_award'], False)
        self.assertIs(self.flags(self.org_admin, self.case('submitted'))['can_close_pre_award'], True)


class TheStageIsTheVerdictDoor(_World):
    def test_case_closed_is_answered_exactly_where_the_stage_is_not_open(self):
        cases = {'open': self.case('interviewing'),
                 'past_award': self.case('active'),
                 'pre_award_end': self.case('rejected'),
                 'reopened': self.case('rejected', decision_reopened_at=timezone.now())}
        expected = {'open': 'open', 'past_award': 'past_award', 'pre_award_end': 'pre_award_end',
                    'reopened': 'open'}
        for name, app in cases.items():
            with self.subTest(name):
                stage = self.flags(self.super, app)['case_stage']
                self.assertEqual(stage, expected[name])
                r = authed_client(self.super).post(f'{APPS}{app.id}/record-verdict/', {}, format='json')
                self.assertEqual(r.json().get('code') == 'case_closed', stage != 'open', r.content[:200])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@LOCMEM
class TheActivityFlagIsTheActivityDoor(TestCase):
    def setUp(self):
        self.app = _scholar()                                      # maintenance: the file is open
        self.org = self.app.owning_organisation
        self.lead = make_admin('org_admin', owning_org=self.org)
        self.holder = make_admin('admin', owning_org=self.org, permissions=['scholars'])

    def served(self, who, app=None):
        r = authed_client(who).get(f'{FILES}{(app or self.app).id}/')
        self.assertEqual(r.status_code, 200, r.content[:200])
        return r.json()['controls']['can_write_activity']

    def door(self, who, app=None):
        r = authed_client(who).post(f'{FILES}{(app or self.app).id}/activity/',
                                    {'kind': 'note', 'body': 'A note.'}, format='json')
        return r.status_code

    def test_a_scholars_holder_on_an_open_file(self):
        for who in (self.holder, self.lead):
            with self.subTest(who=who.role):
                self.assertIs(self.served(who), True)
                self.assertEqual(self.door(who), 201)

    def test_a_closed_file(self):
        closed = make_application('closed', cohort=self.app.cohort)
        self.assertIs(self.served(self.holder, closed), False)
        self.assertEqual(self.door(self.holder, closed), 409)

    def test_a_mentor(self):
        mentor = make_mentor(self.org, email='mentor.s1@example.invalid')
        mentoring.assign(self.lead, self.app, mentor, email_student=False)
        login = mentoring._login(mentor)
        self.assertIs(self.served(login), False)
        self.assertEqual(self.door(login), 403)

    def test_a_staff_mentor_without_the_key(self):
        person = make_admin('reviewer', owning_org=self.org)
        person.mentor = Mentor.objects.create(organisation=self.org)
        person.save(update_fields=['mentor'])
        mentoring.assign(self.lead, self.app, person.mentor, email_student=False)
        self.assertIs(self.served(person), False)
        self.assertEqual(self.door(person), 403)
