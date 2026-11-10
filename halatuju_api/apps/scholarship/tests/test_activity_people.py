"""Sprint P1 (2026-11-09) — who wrote each line of the activity log, and the log's filter.

Pinned through the real endpoint (`admin/scholarship/scholars/<pk>/activity/`):
  * THE ACTOR BLOCK — a staff member's name and photo (or none), the scholar's own rows, an email
    that matches nobody (shown as written), and a fully automatic row (``actor: None``);
  * THE COST — ONE signing call per request with each photo once, and a query count that does not
    grow with the rows or the people on the page;
  * ``?show=all|notes|system`` and ``counts`` (filtered on the server, so paging stays right);
  * THE MENTOR RULE — a viewer without the Mentoring tab never receives a mentoring row under any
    filter, nor the name, photo or email of a mentor on a row they do receive;
  * (P1 review) ``actor_email`` only for an unknown writer; a failed photo signing never fails the
    read (initials instead); ``?counts=0`` for the side panel.
"""
import http.client
from unittest import mock

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.scholarship import activity, mentoring, storage
from apps.scholarship.models import ReviewerProfile, StudentActivity
from apps.scholarship.models.activity import (
    EVENT_LETTER_ACKNOWLEDGED, EVENT_RESULT_SUBMITTED, EVENT_SESSION_LOGGED, EVENT_SUBSTATE_CHANGED,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_student,
)

API = '/api/v1/admin/scholarship/scholars/'
SIGN = 'apps.scholarship.storage.create_signed_download_urls'
#: The activity GET for a signed-in officer with rows from three writers (see `test_the_query_count_is_pinned`).
PINNED_QUERIES = 6


def _signed(paths, expires_in=3600):
    return {p: f'https://signed.example.org/{p}?t={expires_in}' for p in paths}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Log(TestCase):
    @classmethod
    def setUpTestData(cls):
        cohort = make_cohort()
        org = cohort.owning_organisation
        cls.org_admin = make_admin('org_admin', owning_org=org, name='Farah Officer')
        cls.officer = make_admin('admin', owning_org=org, name='Gopal Officer')
        # Sprint S1: QC alone no longer reads Scholars; a QC given `scholars` is the reader outside
        # the Mentoring tab.
        cls.qc = make_admin('qc', owning_org=org, name='Hana Checker',
                            permissions=['see_all', 'qc', 'scholars'])
        cls.mentor = make_admin('mentor', owning_org=org, name='Imran Mentor')
        ReviewerProfile.objects.create(partner_admin=cls.org_admin, phone='012-000 0001',
                                       photo_path='staff-photos/1/farah.webp')
        ReviewerProfile.objects.create(partner_admin=cls.mentor, phone='012-000 0002',
                                       photo_path='staff-photos/2/imran.webp')
        cls.app = make_application('maintenance', cohort=cohort,
                                   student=make_student(name='JULIA SCHOLAR'),
                                   notify_email='julia.scholar@example.org')

    def _url(self):
        return f'{API}{self.app.id}/activity/'

    def _read(self, admin, **params):
        with mock.patch(SIGN, side_effect=_signed) as sign:
            r = authed_client(admin).get(self._url(), params)
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.json(), sign

    def _note(self, by, body='A note.', kind='note'):
        return activity.add_entry(self.app, kind, body, actor_email=by)

    def _actor(self, payload, row):
        return next(r['actor'] for r in payload['results'] if r['id'] == row.id)


class TestTheActorBlock(_Log):
    def test_a_staff_member_shows_their_name_and_photo(self):
        row = self._note(self.org_admin.email)
        payload, _ = self._read(self.officer)
        self.assertEqual(self._actor(payload, row), {
            'name': 'Farah Officer', 'kind': 'staff',
            'photo_url': 'https://signed.example.org/staff-photos/1/farah.webp?t=3600'})

    def test_a_staff_member_without_a_photo_has_none(self):
        row = self._note(self.officer.email)
        payload, sign = self._read(self.officer)
        self.assertEqual(self._actor(payload, row),
                         {'name': 'Gopal Officer', 'photo_url': None, 'kind': 'staff'})
        sign.assert_not_called()                  # nothing to sign: no call at all

    def test_the_email_is_matched_whatever_its_case(self):
        row = self._note(self.org_admin.email.upper())
        payload, _ = self._read(self.officer)
        self.assertEqual(self._actor(payload, row)['name'], 'Farah Officer')

    def test_a_system_row_with_a_person_names_that_person(self):
        row = activity.log_event(self.app, EVENT_SUBSTATE_CHANGED, actor_email=self.officer.email,
                                 meta={'from': 'on_track', 'to': 'probation'})
        payload, _ = self._read(self.officer)
        self.assertEqual(self._actor(payload, row)['name'], 'Gopal Officer')

    def test_a_fully_automatic_row_has_no_actor(self):
        row = activity.log_event(self.app, EVENT_SUBSTATE_CHANGED, meta={'to': 'probation'})
        payload, _ = self._read(self.officer)
        self.assertIsNone(self._actor(payload, row))

    def test_the_scholars_own_rows_without_an_email_are_the_scholar(self):
        letter = activity.log_event(self.app, EVENT_LETTER_ACKNOWLEDGED)
        result = activity.log_event(self.app, EVENT_RESULT_SUBMITTED, meta={'by': 'student'})
        staff_result = activity.log_event(self.app, EVENT_RESULT_SUBMITTED, meta={'by': 'staff'})
        payload, _ = self._read(self.officer)
        scholar = {'name': 'JULIA SCHOLAR', 'photo_url': None, 'kind': 'scholar'}
        self.assertEqual(self._actor(payload, letter), scholar)
        self.assertEqual(self._actor(payload, result), scholar)
        self.assertIsNone(self._actor(payload, staff_result))

    def test_the_scholars_own_email_is_the_scholar(self):
        row = self._note('Julia.Scholar@example.org')
        payload, _ = self._read(self.officer)
        self.assertEqual(self._actor(payload, row)['kind'], 'scholar')

    def test_an_email_that_matches_nobody_is_shown_as_written(self):
        row = self._note('former.officer@example.org')
        payload, _ = self._read(self.officer)
        self.assertEqual(self._actor(payload, row),
                         {'name': 'former.officer@example.org', 'photo_url': None, 'kind': 'unknown'})

    def test_a_new_entry_comes_back_with_its_actor(self):
        with mock.patch(SIGN, side_effect=_signed):
            r = authed_client(self.org_admin).post(self._url(), {'kind': 'note', 'body': 'Hello.'},
                                                   format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()['actor']['name'], r.json()['actor']['kind']),
                         ('Farah Officer', 'staff'))
        self.assertTrue(r.json()['actor']['photo_url'].startswith('https://signed.example.org/'))


class TestTheCost(_Log):
    def test_each_photo_is_signed_once_in_one_call(self):
        for _ in range(3):
            self._note(self.org_admin.email)
            self._note(self.mentor.email)
        _, sign = self._read(self.org_admin)
        self.assertEqual(sign.call_count, 1)
        self.assertEqual(sorted(sign.call_args.args[0]),
                         ['staff-photos/1/farah.webp', 'staff-photos/2/imran.webp'])

    def _queries(self, admin):
        with CaptureQueriesContext(connection) as ctx:
            self._read(admin)
        return len(ctx.captured_queries)

    def test_the_query_count_does_not_grow_with_rows_or_people(self):
        self._note(self.org_admin.email)
        small = self._queries(self.officer)
        for who in (self.officer.email, self.mentor.email, 'nobody@example.org',
                    'julia.scholar@example.org', ''):
            for _ in range(3):
                if who:
                    self._note(who)
                else:
                    activity.log_event(self.app, EVENT_SUBSTATE_CHANGED)
        self.assertEqual(self._queries(self.officer), small)

    def test_the_query_count_is_pinned(self):
        """Absolute pin beside the relative check above: the auth and fence reads, the grouped
        counts, the page of rows and ONE login lookup. A new query per request fails here."""
        for who in (self.org_admin.email, self.officer.email, 'nobody@example.org'):
            self._note(who)
        with mock.patch(SIGN, side_effect=_signed):
            client = authed_client(self.officer)
            with self.assertNumQueries(PINNED_QUERIES):
                r = client.get(self._url())
        self.assertEqual(r.status_code, 200)

    def test_the_side_panel_skips_the_grouped_counts(self):
        self._note(self.officer.email)
        activity.log_event(self.app, EVENT_SUBSTATE_CHANGED)
        payload, _ = self._read(self.officer, counts='0')
        self.assertNotIn('counts', payload)
        self.assertEqual(payload['count'], 2)
        with_counts, _ = self._read(self.officer)
        self.assertEqual(with_counts['counts'], {'all': 2, 'notes': 1, 'system': 1})
        self.assertEqual((self._grouped(counts='0'), self._grouped()), (0, 1))

    def _grouped(self, **params):
        """How many grouped queries over the log one read runs."""
        with CaptureQueriesContext(connection) as ctx:
            self._read(self.officer, **params)
        return sum('GROUP BY' in q['sql'] and '"student_activity"' in q['sql'] for q in ctx.captured_queries)


class TestTheFilter(_Log):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for kind in ('note', 'call', 'meeting', 'email'):
            activity.add_entry(cls.app, kind, f'A {kind}.', actor_email=cls.officer.email)
        for _ in range(2):
            activity.log_event(cls.app, EVENT_SUBSTATE_CHANGED)

    def test_counts_and_each_filter(self):
        for show, kinds in (('all', {'note', 'call', 'meeting', 'email', 'system'}),
                            ('notes', {'note', 'call', 'meeting', 'email'}),
                            ('system', {'system'}),
                            ('nonsense', {'note', 'call', 'meeting', 'email', 'system'})):
            with self.subTest(show=show):
                payload, _ = self._read(self.officer, show=show)
                self.assertEqual(payload['counts'], {'all': 6, 'notes': 4, 'system': 2})
                self.assertEqual({r['kind'] for r in payload['results']}, kinds)
                self.assertEqual(payload['count'], len(payload['results']))

    def test_a_filter_pages(self):
        first, _ = self._read(self.officer, show='notes', page_size=3)
        second, _ = self._read(self.officer, show='notes', page_size=3, page=2)
        self.assertEqual((first['count'], len(first['results']), len(second['results'])), (4, 3, 1))
        ids = [r['id'] for r in first['results'] + second['results']]
        self.assertEqual(len(set(ids)), 4)
        self.assertEqual(ids, sorted(ids, reverse=True))          # still newest first


class TestTheMentorRule(_Log):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.session = activity.log_event(cls.app, EVENT_SESSION_LOGGED, actor_email=cls.mentor.email)
        cls.mentor_note = activity.add_entry(cls.app, 'note', 'From the mentor.',
                                             actor_email=cls.mentor.email)

    def test_the_viewer_is_outside_the_mentoring_tab(self):
        self.assertFalse(mentoring.may_read_mentoring(self.qc))
        self.assertTrue(mentoring.may_read_mentoring(self.org_admin))

    def test_no_mentoring_row_under_any_filter(self):
        for show in ('all', 'notes', 'system'):
            with self.subTest(show=show):
                payload, _ = self._read(self.qc, show=show)
                self.assertNotIn(self.session.id, [r['id'] for r in payload['results']])
                self.assertEqual(payload['counts'], {'all': 1, 'notes': 1, 'system': 0})

    def test_a_mentor_is_never_named_to_them(self):
        payload, sign = self._read(self.qc)
        row = next(r for r in payload['results'] if r['id'] == self.mentor_note.id)
        self.assertEqual(row['actor'], {'name': '', 'photo_url': None, 'kind': 'mentor'})
        self.assertEqual(row['actor_email'], '')
        self.assertNotIn(self.mentor.email, str(payload))
        self.assertNotIn('Imran', str(payload))
        sign.assert_not_called()                  # their photo is never even signed

    def test_the_mentoring_tab_reader_sees_the_mentor(self):
        payload, _ = self._read(self.org_admin)
        self.assertEqual(self._actor(payload, self.mentor_note)['name'], 'Imran Mentor')
        self.assertEqual(self._actor(payload, self.session)['kind'], 'mentor')
        self.assertEqual(StudentActivity.objects.filter(application=self.app).count(),
                         payload['counts']['all'])


class TestTheEmailIsServedOnlyForAnUnknownWriter(_Log):
    def test_a_known_person_has_no_email_in_the_payload(self):
        staff = self._note(self.org_admin.email)
        scholar = self._note('julia.scholar@example.org')
        unknown = self._note('former.officer@example.org')
        payload, _ = self._read(self.officer)
        by_id = {r['id']: r for r in payload['results']}
        self.assertEqual(by_id[staff.id]['actor_email'], '')
        self.assertEqual(by_id[scholar.id]['actor_email'], '')
        self.assertEqual(by_id[unknown.id]['actor_email'], 'former.officer@example.org')
        self.assertNotIn(self.org_admin.email, str(payload))
        self.assertNotIn('julia.scholar@example.org', str(payload))


class TestAFailedSigningNeverFailsTheRead(_Log):
    """The photo is a nicety: the signer raising, or answering with nothing, gives initials."""

    def _both(self, **patch):
        self._note(self.org_admin.email)
        with mock.patch(SIGN, **patch):
            got = authed_client(self.officer).get(self._url())
            made = authed_client(self.org_admin).post(self._url(), {'kind': 'note', 'body': 'Hi.'},
                                                      format='json')
        self.assertEqual((got.status_code, made.status_code), (200, 201), (got.content, made.content))
        self.assertEqual([r['actor']['photo_url'] for r in got.json()['results']], [None])
        self.assertEqual(made.json()['actor'], {'name': 'Farah Officer', 'photo_url': None, 'kind': 'staff'})

    def test_the_signer_raises(self):
        with self.assertLogs('apps.scholarship.activity_people', 'WARNING') as logs:
            self._both(side_effect=RuntimeError('storage down'))
        self.assertTrue(all('farah' not in line.lower() and '@' not in line for line in logs.output),
                        logs.output)

    def test_the_signer_returns_nothing(self):
        self._both(return_value={})


@override_settings(SUPABASE_URL='https://storage.example.org', SUPABASE_SERVICE_ROLE_KEY='not-a-key')
class TestStorageCatchesAConnectionFailure(TestCase):
    """`storage._post` answers None (never raises) on a reset connection or a malformed reply."""

    def test_each_failure_is_none(self):
        for exc in (ConnectionResetError('reset'), http.client.RemoteDisconnected('gone'),
                    http.client.IncompleteRead(b''), TimeoutError('slow')):
            with self.subTest(exc=type(exc).__name__):
                with mock.patch('urllib.request.urlopen', side_effect=exc):
                    self.assertEqual(storage.create_signed_download_urls(['staff-photos/1/a.webp']), {})
