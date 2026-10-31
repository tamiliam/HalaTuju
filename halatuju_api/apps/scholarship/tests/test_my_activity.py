"""Common profile S4 (2026-10-31): `GET admin/me/activity/` — a person's OWN activity list (D7, D8).

  * own rows only, for every role — a super included; a source user is opted in;
  * D8: a subject's name is decided NOW — a reviewer unassigned since reads "a student"; a staff
    member of another organisation reads "a team member"; a source sees only its own cases;
  * D7: a purged subject reads "(removed)";
  * paging (newest first, (created_at, id) cursor, ties broken by id), the filters, the 400s;
  * the query count does not grow with the page;
  * the ALLOWLIST: no NRIC, email, phone, income or free text ever reaches the payload.
"""
import json
from datetime import timedelta

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.scholarship import staff_activity
from apps.scholarship.models import (
    Invitation, OrgRequest, PaymentRun, ScholarshipApplication, StaffActivity,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_source,
)

URL = '/api/v1/admin/me/activity/'
V = staff_activity.V
ITEM_KEYS = {'id', 'verb', 'kind', 'created_at', 'backfilled', 'subject', 'meta'}
SUBJECT_KEYS = {'type', 'state', 'label', 'id'}


def _row(actor, verb, subject=None, *, ago=0, meta=None, backfilled=False):
    kind, pk = ('', None)
    if subject is not None:
        kind = staff_activity._SUBJECT_OF_MODEL[subject._meta.label_lower][0]
        pk = subject.pk
    return StaffActivity.objects.create(
        actor=actor, verb=verb, subject_type=kind, subject_id=pk, meta=meta or {},
        created_at=timezone.now() - timedelta(minutes=ago), backfilled=backfilled)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _World(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.other_org = make_org()
        cls.cohort = make_cohort(programme=make_programme(organisation=cls.org))
        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        cls.colleague = make_admin('qc', owning_org=cls.org, name='Kala Colleague')
        cls.stranger = make_admin('qc', owning_org=cls.other_org, name='Other Org Person')
        cls.superadmin = make_admin('super', super_admin=True)
        cls.student = make_application('assigned', cohort=cls.cohort, reviewer=cls.reviewer)
        cls.student.profile.name = 'Priya Ramasamy'
        cls.student.profile.nric = '050505-14-1234'
        cls.student.profile.contact_email = 'priya@example.test'
        cls.student.profile.contact_phone = '012-9998877'
        cls.student.profile.save()

    def get(self, who, **params):
        resp = authed_client(who).get(URL, params)
        return resp

    def results(self, who, **params):
        resp = self.get(who, **params)
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()


class TestOwnRowsOnly(_World):

    def test_a_person_reads_only_their_own_rows(self):
        mine = _row(self.reviewer, V.FIRST_SIGN_IN)
        _row(self.colleague, V.FIRST_SIGN_IN)
        self.assertEqual([i['id'] for i in self.results(self.reviewer)['results']], [mine.pk])

    def test_a_super_also_reads_only_their_own(self):
        _row(self.reviewer, V.FIRST_SIGN_IN)
        own = _row(self.superadmin, V.PROFILE_UPDATED, meta={'fields': ['name']})
        self.assertEqual([i['id'] for i in self.results(self.superadmin)['results']], [own.pk])

    def test_nobody_signed_in_is_refused(self):
        from rest_framework.test import APIClient
        self.assertIn(APIClient().get(URL).status_code, (401, 403))


class TestDecidedNow(_World):

    def test_the_assigned_reviewer_sees_the_students_name(self):
        _row(self.reviewer, V.VERDICT_RECORDED, self.student)
        subject = self.results(self.reviewer)['results'][0]['subject']
        self.assertEqual(subject, {'type': 'application', 'state': 'visible',
                                   'label': 'PRIYA RAMASAMY', 'id': self.student.pk})

    def test_d8_once_unassigned_it_is_a_student(self):
        _row(self.reviewer, V.VERDICT_RECORDED, self.student)
        ScholarshipApplication.objects.filter(pk=self.student.pk).update(assigned_to=None)
        subject = self.results(self.reviewer)['results'][0]['subject']
        self.assertEqual(subject, {'type': 'application', 'state': 'hidden', 'label': 'a student',
                                   'id': None})

    def test_d8_another_organisations_case_is_a_student_even_for_see_all(self):
        elsewhere = make_application('submitted', cohort=make_cohort(
            programme=make_programme(organisation=self.other_org)))
        _row(self.colleague, V.QUERY_RAISED, elsewhere)
        self.assertEqual(self.results(self.colleague)['results'][0]['subject']['state'], 'hidden')

    def test_d7_a_purged_student_is_removed(self):
        _row(self.reviewer, V.VERDICT_RECORDED, self.student)
        ScholarshipApplication.objects.filter(pk=self.student.pk).delete()
        subject = self.results(self.reviewer)['results'][0]['subject']
        self.assertEqual(subject, {'type': 'application', 'state': 'removed',
                                   'label': 'a student (removed)', 'id': None})

    def test_a_staff_subject_in_my_organisation_is_named_and_another_is_not(self):
        _row(self.superadmin, V.PERMISSIONS_CHANGED, self.colleague, ago=1)
        _row(self.reviewer, V.PERMISSIONS_CHANGED, self.colleague, ago=1)
        _row(self.reviewer, V.PERMISSIONS_CHANGED, self.stranger)
        labels = [i['subject']['label'] for i in self.results(self.reviewer)['results']]
        self.assertEqual(labels, ['a team member', 'Kala Colleague'])
        self.assertEqual(self.results(self.superadmin)['results'][0]['subject']['label'],
                         'Kala Colleague')

    @override_settings(REQUESTS_ENABLED=True)
    def test_references_never_typed_text(self):
        run = PaymentRun.objects.create(organisation=self.org, programme=self.cohort.programme,
                                        payment_date=timezone.localdate(),
                                        period_month=timezone.localdate().replace(day=1),
                                        reference='PR-2026-0001')
        req = OrgRequest.objects.create(organisation=self.org, submitted_by=self.reviewer, kind='bug',
                                        title='Secret title text', description='Secret body text')
        # An org_admin opens both Payments (the lead tier) and Requests: both references are named.
        lead = make_admin('org_admin', owning_org=self.org)
        _row(lead, V.PAYMENT_RUN_SIGNED, run, meta={'role': 'approver'}, ago=1)
        _row(lead, V.ORG_REQUEST_RAISED, req)
        body = self.results(lead)
        self.assertEqual([i['subject']['label'] for i in body['results']],
                         [f'#{req.pk}', 'PR-2026-0001'])
        self.assertNotIn('Secret', json.dumps(body))
        # A reviewer may not open Payments, so the run is a neutral word to them.
        _row(self.reviewer, V.PAYMENT_RUN_SIGNED, run)
        self.assertEqual(self.results(self.reviewer)['results'][0]['subject']['label'],
                         'a payment run')


class TestUnnamedVisibleSubject(_World):
    """TD-445: a subject the viewer may see but which has no name is served `label: None` (the web
    puts in its own translated word), still `visible` and with its id, so a student stays linked."""

    def test_an_invitation_with_a_blank_name_is_visible_with_no_label(self):
        inv = Invitation.objects.create(audience='staff', email='blank@example.test', code='td445',
                                        organisation=self.org, name='')
        lead = make_admin('org_admin', owning_org=self.org)
        _row(lead, V.INVITATION_SENT, inv)
        subject = self.results(lead)['results'][0]['subject']
        self.assertEqual(subject, {'type': 'invitation', 'state': 'visible', 'label': None, 'id': inv.pk})

    def test_a_student_with_no_name_is_visible_with_no_label_and_keeps_its_id(self):
        nameless = make_application('assigned', cohort=self.cohort, reviewer=self.reviewer)
        nameless.profile.name = ''
        nameless.profile.save()
        _row(self.reviewer, V.VERDICT_RECORDED, nameless)
        subject = self.results(self.reviewer)['results'][0]['subject']
        self.assertEqual(subject, {'type': 'application', 'state': 'visible', 'label': None,
                                   'id': nameless.pk})


class TestSourceUser(_World):

    def test_a_source_reads_its_own_list_and_only_its_own_cases_by_name(self):
        source = make_source(organisation=self.org)
        user = make_admin('source_partner', owning_org=self.org, source=source)
        witnessed = make_application('awarded', cohort=self.cohort, witness_org=source)
        _row(user, V.CONTRACT_WITNESSED, witnessed, ago=1)
        _row(user, V.CONTRACT_WITNESSED, self.student)
        _row(user, V.PERMISSIONS_CHANGED, self.colleague, ago=2)
        states = [i['subject']['state'] for i in self.results(user)['results']]
        self.assertEqual(states, ['hidden', 'visible', 'hidden'])


class TestMentor(_World):

    def test_a_mentor_reads_its_own_list_and_names_nobody_else(self):
        """S7a + S4: a mentor is opted in to its own list, and is an outsider like a source user — a
        colleague in the same organisation and a student both read as the neutral word."""
        mentor = make_admin('mentor', owning_org=self.org)
        _row(mentor, V.PROFILE_UPDATED, meta={'fields': ['about']}, ago=2)
        _row(mentor, V.PERMISSIONS_CHANGED, self.colleague, ago=1)
        _row(mentor, V.CONTRACT_WITNESSED, self.student)
        _row(self.reviewer, V.PROFILE_UPDATED)
        items = self.results(mentor)['results']
        self.assertEqual([i['verb'] for i in items],
                         [V.CONTRACT_WITNESSED, V.PERMISSIONS_CHANGED, V.PROFILE_UPDATED])
        self.assertEqual([(i['subject'] or {}).get('state') for i in items], ['hidden', 'hidden', None])
        self.assertNotIn('Kala Colleague', str(items))
        self.assertNotIn('Priya', str(items))


class TestPagingAndFilters(_World):

    def test_newest_first_in_pages_with_no_overlap_and_ties_broken_by_id(self):
        same = timezone.now() - timedelta(minutes=5)
        made = [_row(self.reviewer, V.FIRST_SIGN_IN, ago=10)]
        made += [StaffActivity.objects.create(actor=self.reviewer, verb=V.PROFILE_UPDATED,
                                              created_at=same) for _ in range(3)]
        made.append(_row(self.reviewer, V.FIRST_SIGN_IN, ago=1))
        seen, cursor = [], None
        while True:
            body = self.results(self.reviewer, limit=2, **({'cursor': cursor} if cursor else {}))
            seen += [i['id'] for i in body['results']]
            cursor = body['next']
            if not cursor:
                break
        expected = [made[4].pk, made[3].pk, made[2].pk, made[1].pk, made[0].pk]
        self.assertEqual(seen, expected)

    def test_the_filters(self):
        _row(self.reviewer, V.FIRST_SIGN_IN, ago=3)
        _row(self.reviewer, V.VERDICT_RECORDED, self.student, ago=2)
        _row(self.reviewer, V.TRANCHE_RELEASED, self.student, ago=1)
        _row(self.reviewer, V.INVITATION_SENT)
        verbs = {kind: [i['verb'] for i in self.results(self.reviewer, kind=kind)['results']]
                 for kind in ('all', 'students', 'money', 'profile')}
        self.assertEqual(verbs['all'], ['invitation_sent', 'tranche_released', 'verdict_recorded',
                                        'first_sign_in'])
        self.assertEqual(verbs['students'], ['verdict_recorded'])
        self.assertEqual(verbs['money'], ['tranche_released'])
        self.assertEqual(verbs['profile'], ['first_sign_in'])

    def test_bad_queries_are_400(self):
        for params, code in (({'kind': 'secret'}, 'bad_kind'), ({'cursor': '!!!'}, 'bad_cursor'),
                             ({'limit': '0'}, 'bad_limit'), ({'limit': '101'}, 'bad_limit'),
                             ({'limit': 'x'}, 'bad_limit')):
            with self.subTest(params):
                resp = self.get(self.reviewer, **params)
                self.assertEqual((resp.status_code, resp.json()['code']), (400, code))

    def test_the_backfilled_flag_is_served(self):
        _row(self.reviewer, V.FIRST_SIGN_IN, backfilled=True)
        self.assertIs(self.results(self.reviewer)['results'][0]['backfilled'], True)


class TestQueryCount(_World):

    def _mixed_rows(self, n):
        inv = Invitation.objects.create(audience='staff', email='x@example.test', code=f'c{n}',
                                        organisation=self.org)
        apps = [make_application('assigned', cohort=self.cohort, reviewer=self.reviewer)
                for _ in range(n)]
        for i, app in enumerate(apps):
            _row(self.reviewer, V.QUERY_RAISED, app, ago=i)
            _row(self.reviewer, V.PERMISSIONS_CHANGED, self.colleague, ago=i)
            _row(self.reviewer, V.INVITATION_SENT, inv, ago=i)

    def _count(self, limit):
        client = authed_client(self.reviewer)
        with CaptureQueriesContext(connection) as ctx:
            resp = client.get(URL, {'limit': limit})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['results']), limit)
        return len(ctx.captured_queries)

    def test_the_query_count_does_not_grow_with_the_page(self):
        self._mixed_rows(10)
        self.assertEqual(self._count(3), self._count(30))


class TestAllowlist(_World):

    def test_no_identity_contact_income_or_free_text_ever_reaches_the_payload(self):
        _row(self.reviewer, V.VERDICT_RECORDED, self.student, ago=2)
        _row(self.reviewer, V.PERMISSIONS_CHANGED, self.colleague, ago=1)
        # A row whose meta somebody wrote by hand, past the writer's check: re-filtered on the way out.
        _row(self.reviewer, V.QUERY_RAISED, self.student,
             meta={'note': 'He called me rude', 'kind': 'doc', 'reason': 'not a code at all'})
        body = self.results(self.reviewer)
        for item in body['results']:
            self.assertEqual(set(item), ITEM_KEYS)
            self.assertEqual(set(item['subject']), SUBJECT_KEYS)
        self.assertEqual(body['results'][0]['meta'], {'kind': 'doc'})
        text = json.dumps(body)
        for secret in ('050505-14-1234', 'priya@example.test', '012-9998877', self.reviewer.email,
                       self.colleague.email, 'rude', 'household_income', '@'):
            self.assertNotIn(secret, text)
