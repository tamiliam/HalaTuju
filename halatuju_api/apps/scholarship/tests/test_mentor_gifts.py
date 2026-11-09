"""Invitations I4 (2026-11-08; owner ruling 2, open points C and D): a mentor has gifts, and a gift LIMITS who
they mentor.

Every door, driven through the real endpoints:

- THE INVITE: `programme_ids` become the mentor's gifts (`[]` or absent = every gift); not a list 400
  `gift_required`; an unknown, ended or another organisation's gift 404 `not_found` (nothing is made); a
  resend keeps the gifts; a re-invite of a switched-off mentor takes the new ones.
- THE RULE (C): no gifts = every gift, including a gift started later. `mentoring.assign` refuses
  `mentor_not_in_gift`; `assignable_mentors` (the picker) leaves such a mentor out.
- THE EDIT (D): narrowing past a CURRENT scholar is 409 `mentor_has_scholars_outside` with the count and
  writes nothing; narrowing with no conflict works; an ENDED assignment never blocks. Fenced: super and the
  mentor's own org_admin; an admin 403; another organisation's mentor or gift 404.
- THE READERS: the Mentors list and detail carry `gifts` / `every_gift` (and the detail the organisation's
  gift choices); the Invitations Mentor tab names each waiting mentor's gifts and offers only the invite's
  own organisation's active gifts.
- EXISTING MENTORS (no rows) are unaffected.
- DELETING A GIFT (I4 review) never widens a mentor: refused `gift_limits_mentors` with the count while it is
  some mentor's ONLY gift; a mentor holding other gifts just loses that row.
"""
import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.models import Invitation, Mentor, MentorAssignment, MentorGift
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org, make_programme,
)

INVITE = '/api/v1/admin/invitations/'
MENTORS = '/api/v1/admin/mentors/'
SCHOLARS = '/api/v1/admin/scholarship/scholars/'
NEW_LOGIN = 'apps.courses.staff_reinvite._new_login'
ISSUE = 'apps.courses.supabase_admin.issue_temp_password'
KILL = 'apps.courses.supabase_admin.kill_temp_password'
READ = 'apps.courses.supabase_admin.read_auth_user'
UNTOUCHED = {'id': 'x', 'last_sign_in_at': None, 'app_metadata': {}}
SUPABASE = dict(SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', **SUPABASE)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org(name='Gift Test Tenant')
        cls.flagship = make_programme(organisation=cls.org, code='flagship', name_en='Flagship Bursary')
        cls.sabah = make_programme(organisation=cls.org, code='sabah', name_en='Sabah Bursary')
        cls.ended = make_programme(organisation=cls.org, code='zz-ended', name_en='Ended Bursary', is_active=False)
        cls.other_org = make_org(name='Other Tenant')
        cls.foreign = make_programme(organisation=cls.other_org, code='foreign', name_en='Foreign Bursary')
        cls.super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.viewer = make_admin('admin', owning_org=cls.org)
        cls.other_lead = make_admin('org_admin', owning_org=cls.other_org)
        cls.flag_cohort = make_cohort(programme=cls.flagship)
        cls.sabah_cohort = make_cohort(programme=cls.sabah)

    # ── helpers ──
    def scholar(self, cohort):
        return make_application('maintenance', cohort=cohort, active_at=timezone.now() - datetime.timedelta(days=60))

    def mentor(self, *gifts):
        m = make_admin('mentor', owning_org=self.org).mentor
        MentorGift.objects.bulk_create([MentorGift(mentor=m, programme=g) for g in gifts])
        return m

    def gift_codes(self, mentor):
        return sorted(MentorGift.objects.filter(mentor=mentor).values_list('programme__code', flat=True))

    def invite(self, caller=None, query='', **body):
        body.setdefault('audience', 'mentor')
        body.setdefault('name', 'Priya Devi')
        body.setdefault('email', 'priya@example.org')
        uid = 'uid-' + body['email'].split('@')[0]          # one sign-in per address
        with patch(NEW_LOGIN, return_value=(uid, False, None)):
            return authed_client(caller or self.lead).post(INVITE + query, body, format='json')

    def set_gifts(self, mentor, ids, caller=None):
        body = {} if ids is None else {'programme_ids': ids}
        return authed_client(caller or self.lead).post(f'{MENTORS}{mentor.pk}/gifts/', body, format='json')

    def assign(self, app, mentor, caller=None):
        return authed_client(caller or self.lead).post(
            f'{SCHOLARS}{app.pk}/mentoring/assign/', {'mentor_id': mentor.pk, 'email_student': False},
            format='json')

    def offered(self, app):
        r = authed_client(self.lead).get(f'{SCHOLARS}{app.pk}/mentoring/')
        self.assertEqual(r.status_code, 200, r.content)
        return {m['id'] for m in r.json()['assignable']}

    def open_for(self, mentor, app):
        return MentorAssignment.objects.create(application=app, mentor=mentor, started_by_email='t@example.org')


class TestTheInvite(_Base):
    def test_an_invite_with_gifts_gives_the_mentor_those_gifts(self):
        r = self.invite(programme_ids=[self.sabah.pk, self.flagship.pk])
        self.assertEqual(r.status_code, 201, r.content)
        mentor = Mentor.objects.get(pk=r.json()['mentor']['id'])
        self.assertEqual(self.gift_codes(mentor), ['flagship', 'sabah'])
        row = r.json()['mentor']
        self.assertEqual(([g['code'] for g in row['gifts']], row['every_gift']), (['flagship', 'sabah'], False))
        self.assertEqual(row['gifts'][0], {'id': self.flagship.pk, 'code': 'flagship', 'name': 'Flagship Bursary'})

    def test_an_empty_list_or_no_list_is_every_gift(self):
        for i, body in enumerate(({'programme_ids': []}, {})):
            r = self.invite(email=f'every{i}@example.org', **body)
            self.assertEqual(r.status_code, 201, r.content)
            self.assertEqual((r.json()['mentor']['gifts'], r.json()['mentor']['every_gift']), ([], True))
            self.assertFalse(MentorGift.objects.filter(mentor_id=r.json()['mentor']['id']).exists())

    def test_a_bad_gift_choice_is_refused_and_nothing_is_made(self):
        cases = [('x', 400, 'gift_required'), ({'id': 1}, 400, 'gift_required'),
                 ([self.foreign.pk], 404, 'not_found'), ([self.ended.pk], 404, 'not_found'),
                 ([999999], 404, 'not_found'), ([self.sabah.pk, 'abc'], 404, 'not_found'),
                 ([True], 404, 'not_found')]
        for raw, code, word in cases:
            r = self.invite(programme_ids=raw)
            self.assertEqual((r.status_code, r.json().get('code')), (code, word), raw)
        self.assertFalse(Mentor.objects.filter(organisation=self.org).exists())
        self.assertFalse(Invitation.objects.filter(audience='mentor').exists())

    def test_a_super_naming_the_organisation_may_name_its_gifts_but_not_another_ones(self):
        r = self.invite(caller=self.super, query=f'?org={self.org.code}', programme_ids=[self.sabah.pk])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.gift_codes(Mentor.objects.get(pk=r.json()['mentor']['id'])), ['sabah'])
        r = self.invite(caller=self.super, query=f'?org={self.org.code}', email='x2@example.org',
                        programme_ids=[self.foreign.pk])
        self.assertEqual(r.status_code, 404)

    def test_a_resend_keeps_the_gifts(self):
        r = self.invite(programme_ids=[self.sabah.pk])
        mentor = Mentor.objects.get(pk=r.json()['mentor']['id'])
        with patch(ISSUE, return_value=True), patch(KILL, return_value='killed'), patch(READ, return_value=UNTOUCHED):
            r = authed_client(self.lead).post(f'{MENTORS}{mentor.pk}/resend/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.gift_codes(mentor), ['sabah'])
        self.assertEqual([g['code'] for g in r.json()['gifts']], ['sabah'])

    def test_a_reinvite_of_a_switched_off_mentor_takes_the_new_gifts(self):
        r = self.invite(programme_ids=[self.sabah.pk])
        mentor = Mentor.objects.get(pk=r.json()['mentor']['id'])
        with patch(ISSUE, return_value=True), patch(KILL, return_value='killed'), \
                patch('apps.scholarship.staff_lifecycle.login_used_elsewhere', return_value=False):
            self.assertEqual(authed_client(self.lead).post(f'{MENTORS}{mentor.pk}/revoke/', {},
                                                           format='json').status_code, 200)
        with patch(ISSUE, return_value=True), patch(READ, return_value=UNTOUCHED):
            r = self.invite(programme_ids=[self.flagship.pk])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['mentor']['id'], mentor.pk)
        self.assertEqual(self.gift_codes(mentor), ['flagship'])


class TestTheRule(_Base):
    def test_a_mentor_limited_to_sabah_is_not_offered_and_is_refused_for_a_flagship_scholar(self):
        sabah_only = self.mentor(self.sabah)
        flag_app, sabah_app = self.scholar(self.flag_cohort), self.scholar(self.sabah_cohort)
        self.assertNotIn(sabah_only.pk, self.offered(flag_app))
        r = self.assign(flag_app, sabah_only)
        self.assertEqual((r.status_code, r.json().get('code')), (400, 'mentor_not_in_gift'))
        self.assertFalse(MentorAssignment.objects.filter(application=flag_app).exists())
        self.assertIn(sabah_only.pk, self.offered(sabah_app))
        self.assertEqual(self.assign(sabah_app, sabah_only).status_code, 200)

    def test_no_gifts_is_every_gift_including_a_gift_started_later(self):
        everyone = self.mentor()
        later = make_programme(organisation=self.org, code='later', name_en='Later Bursary')
        app = self.scholar(make_cohort(programme=later))
        self.assertIn(everyone.pk, self.offered(app))
        self.assertEqual(self.assign(app, everyone).status_code, 200)

    def test_several_gifts_allow_a_scholar_in_any_of_them(self):
        both = self.mentor(self.sabah, self.flagship)
        for cohort in (self.flag_cohort, self.sabah_cohort):
            app = self.scholar(cohort)
            self.assertIn(both.pk, self.offered(app))
            self.assertEqual(self.assign(app, both).status_code, 200)

    def test_the_rule_is_asked_again_under_the_lock(self):
        """A gift narrowed between the first check and the lock is still refused (the second ask)."""
        from apps.scholarship import mentor_gift, mentoring
        mentor, app = self.mentor(), self.scholar(self.flag_cohort)
        real = mentor_gift.allows
        calls = []

        def narrowed_after_first(m, a):
            calls.append(1)
            if len(calls) == 2:
                MentorGift.objects.create(mentor=m, programme=self.sabah)
            return real(m, a)
        with patch('apps.scholarship.mentor_gift.allows', side_effect=narrowed_after_first):
            with self.assertRaises(mentoring.MentoringError) as e:
                mentoring.assign(self.lead, app, mentor, email_student=False)
        self.assertEqual((e.exception.code, len(calls)), ('mentor_not_in_gift', 2))


class TestTheEdit(_Base):
    def test_narrowing_past_current_scholars_is_refused_with_how_many_and_writes_nothing(self):
        mentor = self.mentor()
        self.open_for(mentor, self.scholar(self.flag_cohort))
        self.open_for(mentor, self.scholar(self.flag_cohort))
        self.open_for(mentor, self.scholar(self.sabah_cohort))
        r = self.set_gifts(mentor, [self.sabah.pk])
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual((r.json()['code'], r.json()['count']), ('mentor_has_scholars_outside', 2))
        self.assertEqual(self.gift_codes(mentor), [])
        self.assertEqual(MentorAssignment.objects.filter(mentor=mentor, ended_at__isnull=True).count(), 3)

    def test_narrowing_with_no_conflict_works_and_widening_back_to_every_gift_works(self):
        mentor = self.mentor()
        self.open_for(mentor, self.scholar(self.sabah_cohort))
        r = self.set_gifts(mentor, [self.sabah.pk, self.ended.pk])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json(), {'id': mentor.pk, 'every_gift': False, 'gifts': [
            {'id': self.sabah.pk, 'code': 'sabah', 'name': 'Sabah Bursary'},
            {'id': self.ended.pk, 'code': 'zz-ended', 'name': 'Ended Bursary'}]})
        self.assertEqual(self.gift_codes(mentor), ['sabah', 'zz-ended'])
        r = self.set_gifts(mentor, [])
        self.assertEqual((r.status_code, r.json()['gifts'], r.json()['every_gift']), (200, [], True))
        self.assertEqual(self.gift_codes(mentor), [])

    def test_an_ended_assignment_does_not_block(self):
        mentor = self.mentor()
        row = self.open_for(mentor, self.scholar(self.flag_cohort))
        MentorAssignment.objects.filter(pk=row.pk).update(ended_at=timezone.now())
        r = self.set_gifts(mentor, [self.sabah.pk])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.gift_codes(mentor), ['sabah'])

    def test_a_missing_or_bad_list_is_refused(self):
        mentor = self.mentor(self.sabah)
        for ids, code, word in ((None, 400, 'gift_required'), ('sabah', 400, 'gift_required'),
                                ([self.foreign.pk], 404, 'not_found'), ([0], 404, 'not_found')):
            r = self.set_gifts(mentor, ids)
            self.assertEqual((r.status_code, r.json().get('code')), (code, word), ids)
        self.assertEqual(self.gift_codes(mentor), ['sabah'])

    def test_the_fence_and_the_roles(self):
        mentor = self.mentor()
        self.assertEqual(self.set_gifts(mentor, [self.sabah.pk], caller=self.viewer).status_code, 403)
        self.assertEqual(self.set_gifts(mentor, [], caller=self.other_lead).status_code, 404)
        reviewer = make_admin('reviewer', owning_org=self.org)
        self.assertEqual(self.set_gifts(mentor, [], caller=reviewer).status_code, 403)
        self.assertEqual(self.set_gifts(mentor, [], caller=mentor.users.first()).status_code, 403)
        self.assertEqual(self.gift_codes(mentor), [])
        # A super may set any organisation's mentor — but only to that organisation's gifts.
        self.assertEqual(self.set_gifts(mentor, [self.foreign.pk], caller=self.super).status_code, 404)
        self.assertEqual(self.set_gifts(mentor, [self.flagship.pk], caller=self.super).status_code, 200)
        self.assertEqual(self.gift_codes(mentor), ['flagship'])
        # Another organisation's lead cannot tag a mentor of theirs with this organisation's gift.
        theirs = make_admin('mentor', owning_org=self.other_org).mentor
        self.assertEqual(self.set_gifts(theirs, [self.sabah.pk], caller=self.other_lead).status_code, 404)
        self.assertEqual(self.set_gifts(theirs, [self.foreign.pk], caller=self.other_lead).status_code, 200)


class TestTheReaders(_Base):
    def test_existing_mentors_are_unaffected(self):
        """A mentor from before I4 has no rows: Every gift on every reader, offered and assignable as before."""
        old = self.mentor()
        rows = authed_client(self.lead).get(MENTORS).json()['mentors']
        [row] = [r for r in rows if r['id'] == old.pk]
        self.assertEqual((row['gifts'], row['every_gift']), ([], True))
        for cohort in (self.flag_cohort, self.sabah_cohort):
            app = self.scholar(cohort)
            self.assertIn(old.pk, self.offered(app))
            self.assertEqual(self.assign(app, old).status_code, 200)

    def test_the_detail_carries_the_gifts_and_the_organisations_choices_only(self):
        mentor = self.mentor(self.sabah)
        for caller in (self.lead, self.viewer):
            body = authed_client(caller).get(f'{MENTORS}{mentor.pk}/').json()
            self.assertEqual([g['code'] for g in body['mentor']['gifts']], ['sabah'])
            self.assertFalse(body['mentor']['every_gift'])
            self.assertEqual([(p['code'], p['is_active']) for p in body['programmes']],
                             [('flagship', True), ('sabah', True), ('zz-ended', False)])

    def test_the_mentor_tab_names_each_waiting_mentors_gifts_and_offers_own_active_gifts(self):
        self.invite(programme_ids=[self.sabah.pk])
        self.invite(email='every@example.org', name='Every Gift')
        body = authed_client(self.lead).get(INVITE + '?kind=mentor').json()
        by_email = {r['email']: r for r in body['invitations']}
        sabah_row, every_row = by_email['priya@example.org'], by_email['every@example.org']
        self.assertEqual(([g['code'] for g in sabah_row['gifts']], sabah_row['every_gift'],
                          sabah_row['programme_name']), (['sabah'], False, 'Sabah Bursary'))
        self.assertEqual((every_row['gifts'], every_row['every_gift'], every_row['programme']), ([], True, ''))
        self.assertEqual([p['code'] for p in body['mentor_programmes']], ['flagship', 'sabah'])
        # A super naming the organisation is offered THAT organisation's gifts only.
        body = authed_client(self.super).get(INVITE + f'?kind=mentor&org={self.other_org.code}').json()
        self.assertEqual([p['code'] for p in body['mentor_programmes']], ['foreign'])


class TestTheGiftDelete(_Base):
    """I4 review: deleting a gift must never silently WIDEN a mentor to every gift. A gift that is some
    mentor's ONLY gift is refused `gift_limits_mentors` with the count (the list row says so too); a mentor
    who holds other gifts just loses that row; a gift no mentor holds deletes as before."""
    GIFTS = '/api/v1/admin/scholarship/programmes/'

    def spare(self):
        return make_programme(organisation=self.org, code='spare-27', name_en='Sabah 2027', is_active=False)

    def delete(self, gift):
        return authed_client(self.lead).delete(f'{self.GIFTS}{gift.pk}/', {'confirm': f'delete {gift.code}'},
                                               format='json')

    def test_refused_while_it_is_a_mentors_only_gift_with_the_count(self):
        spare = self.spare()
        only_a, only_b = self.mentor(spare), self.mentor(spare)
        self.mentor(spare, self.sabah)                      # holds another gift: not counted
        r = self.delete(spare)
        self.assertEqual((r.status_code, r.json()['code'], r.json()['count']), (400, 'gift_limits_mentors', 2))
        self.assertEqual((self.gift_codes(only_a), self.gift_codes(only_b)), (['spare-27'], ['spare-27']))
        row = next(p for p in authed_client(self.lead).get(self.GIFTS).json()['programmes'] if p['id'] == spare.pk)
        self.assertEqual((row['delete_blocked_by'], row['delete_blocked_count']), ('gift_limits_mentors', 2))

    def test_allowed_when_the_mentor_holds_other_gifts_and_those_rows_stay(self):
        spare = self.spare()
        m = self.mentor(spare, self.sabah, self.flagship)
        self.assertEqual(self.delete(spare).status_code, 204)
        self.assertEqual(self.gift_codes(m), ['flagship', 'sabah'])

    def test_allowed_when_no_mentor_holds_it(self):
        spare = self.spare()
        m = self.mentor(self.sabah)
        self.assertEqual(self.delete(spare).status_code, 204)
        self.assertEqual(self.gift_codes(m), ['sabah'])
