"""Multi-gift reviewer tagging (owner design, 2026-11-06).

A reviewer covers a LIST of gifts, held as `ReviewerGift` rows; NO rows means EVERY gift (the
owner's default). The old one-gift column `PartnerAdmin.programme` is no longer read; `set_gifts`
keeps it as a write-only rollback mirror until TD-540 drops it.

Covered here: the data migration's copy, `reviewer_gifts` / `gift_allows` with 0, 1 and 2 gifts,
assignment refused for a wrong gift and allowed for a covered or every-gift reviewer, the set-gifts
endpoint's permissions and its own-organisation rule, and an invite naming several gifts.

No real student data: every name and address here is synthetic.
"""
from unittest.mock import MagicMock, patch

from django.apps import apps as django_apps
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_gift
from apps.courses.models import PartnerAdmin, PartnerOrganisation, ReviewerGift
from apps.scholarship import services
from apps.scholarship.services.assignment import case_gifts, gift_allows, reviewer_gifts
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme,
)

READY = 'apps.scholarship.services.assignment.is_ready_for_assignment'
SET = '/api/v1/admin/reviewers/{}/programme/'
INVITE = '/api/v1/admin/invite/'
CREATE = 'apps.courses.views_admin.http_requests.post'
WELCOME = 'apps.courses.views_staff.send_partner_welcome_email'


def _ids(admin):
    return [g.id for g in staff_gift.gifts_of(admin)]


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   SUPABASE_URL='https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY='k')
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bp = PartnerOrganisation.objects.get(code='brightpath')
        cls.gift_a = make_programme(organisation=cls.bp, code='mg-a', name_en='Gift A')
        cls.gift_b = make_programme(organisation=cls.bp, code='mg-b', name_en='Gift B')
        cls.gift_c = make_programme(organisation=cls.bp, code='mg-c', name_en='Gift C')
        cls.other_org = make_org()
        cls.foreign_gift = make_programme(organisation=cls.other_org, code='mg-x',
                                          name_en='Another tenant gift')
        cls.oa = make_admin('org_admin', owning_org=cls.bp, uid='mg-oa')
        cls.other_oa = make_admin('org_admin', owning_org=cls.other_org, uid='mg-oa2')
        cls.boss = make_admin('super', super_admin=True, uid='mg-su')
        cls.plain = make_admin('admin', owning_org=cls.bp, uid='mg-ad')
        cls.reviewer = make_admin('reviewer', first_seen_at=timezone.now(), owning_org=cls.bp, uid='mg-r1')

    def _case(self, programme):
        return make_application('profile_complete', cohort=make_cohort(programme=programme))


class TestTheDataMigrationCopiesTheOneGift(_Base):
    def test_a_gift_gives_one_row_and_null_gives_none(self):
        from importlib import import_module
        copy = import_module('apps.courses.migrations.0092_reviewergift').copy_one_gift_into_rows
        one = make_admin('reviewer', owning_org=self.bp)
        every = make_admin('reviewer', owning_org=self.bp)
        ReviewerGift.objects.all().delete()
        PartnerAdmin.objects.filter(pk=one.pk).update(programme=self.gift_b)

        copy(django_apps, None)

        self.assertEqual(list(ReviewerGift.objects.filter(partner_admin=one)
                              .values_list('programme_id', flat=True)), [self.gift_b.id])
        self.assertFalse(ReviewerGift.objects.filter(partner_admin=every).exists())
        self.assertEqual(ReviewerGift.objects.count(),
                         PartnerAdmin.objects.filter(programme__isnull=False).count())

    def test_one_row_per_pair(self):
        from django.db import IntegrityError, transaction
        ReviewerGift.objects.create(partner_admin=self.reviewer, programme=self.gift_a)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReviewerGift.objects.create(partner_admin=self.reviewer, programme=self.gift_a)


class TestGiftAllowsWithZeroOneAndTwoGifts(_Base):
    def test_no_gifts_is_every_gift(self):
        self.assertIsNone(reviewer_gifts(self.reviewer))
        for gift in (self.gift_a, self.gift_b, self.gift_c):
            self.assertTrue(gift_allows(self.reviewer, self._case(gift)))

    def test_one_gift(self):
        staff_gift.set_gifts(self.reviewer, [self.gift_a])
        self.assertEqual(reviewer_gifts(self.reviewer), frozenset({self.gift_a.id}))
        self.assertTrue(gift_allows(self.reviewer, self._case(self.gift_a)))
        self.assertFalse(gift_allows(self.reviewer, self._case(self.gift_b)))

    def test_two_gifts(self):
        staff_gift.set_gifts(self.reviewer, [self.gift_a, self.gift_b])
        self.assertEqual(reviewer_gifts(self.reviewer), frozenset({self.gift_a.id, self.gift_b.id}))
        self.assertTrue(gift_allows(self.reviewer, self._case(self.gift_a)))
        self.assertTrue(gift_allows(self.reviewer, self._case(self.gift_b)))
        self.assertFalse(gift_allows(self.reviewer, self._case(self.gift_c)))

    def test_a_case_of_unknown_gift_is_allowed(self):
        staff_gift.set_gifts(self.reviewer, [self.gift_a])
        self.assertTrue(gift_allows(self.reviewer, self._case(None)))

    def test_TD531b_a_case_moved_between_gifts_matches_either_gift(self):
        """TD-531(b): the lists filter a case by its own gift OR its cohort's. The assignment
        check now reads both, so a case whose cohort moved gift is offered under either."""
        app = self._case(self.gift_b)
        app.__class__.objects.filter(pk=app.pk).update(programme=self.gift_a)
        app.refresh_from_db()
        self.assertEqual(case_gifts(app), frozenset({self.gift_a.id, self.gift_b.id}))
        staff_gift.set_gifts(self.reviewer, [self.gift_b])
        self.assertTrue(gift_allows(self.reviewer, app))
        staff_gift.set_gifts(self.reviewer, [self.gift_c])
        self.assertFalse(gift_allows(self.reviewer, app))


class TestAssignmentReadsTheRows(_Base):
    def _assign(self, app, reviewer):
        with patch(READY, return_value=True):
            return services.assign_reviewer(app, reviewer=reviewer, by_admin=self.oa)

    def test_refused_for_a_gift_not_covered(self):
        staff_gift.set_gifts(self.reviewer, [self.gift_a, self.gift_b])
        app = self._case(self.gift_c)
        with self.assertRaises(services.AssignmentError) as ctx:
            self._assign(app, self.reviewer)
        self.assertEqual(str(ctx.exception), 'gift_mismatch')

    def test_allowed_for_the_second_covered_gift(self):
        staff_gift.set_gifts(self.reviewer, [self.gift_a, self.gift_b])
        app = self._case(self.gift_b)
        self._assign(app, self.reviewer)
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.reviewer.id)

    def test_allowed_for_an_every_gift_reviewer(self):
        app = self._case(self.gift_c)
        self._assign(app, self.reviewer)
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.reviewer.id)


class TestSetGifts(_Base):
    def test_it_replaces_the_rows_and_keeps_the_mirror(self):
        staff_gift.set_gifts(self.reviewer, [self.gift_a])
        self.reviewer.refresh_from_db()
        self.assertEqual(self.reviewer.programme_id, self.gift_a.id)   # one gift -> the mirror
        staff_gift.set_gifts(self.reviewer, [self.gift_b, self.gift_c])
        self.assertEqual(_ids(self.reviewer), [self.gift_b.id, self.gift_c.id])
        self.reviewer.refresh_from_db()
        self.assertIsNone(self.reviewer.programme_id)                  # several -> NULL (every)
        staff_gift.set_gifts(self.reviewer, [])
        self.assertEqual(_ids(self.reviewer), [])
        self.assertFalse(ReviewerGift.objects.filter(partner_admin=self.reviewer).exists())


class TestTheSetGiftsEndpoint(_Base):
    def _set(self, caller, target, ids):
        return authed_client(caller).post(SET.format(target.id), {'programme_ids': ids},
                                          format='json')

    def test_an_org_admin_tags_their_own_reviewer_with_several_gifts(self):
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            r = self._set(self.oa, self.reviewer, [self.gift_b.id, self.gift_a.id])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([g['code'] for g in r.json()['gifts']], ['mg-a', 'mg-b'])
        self.assertEqual(_ids(self.reviewer), [self.gift_a.id, self.gift_b.id])
        self.assertTrue(any('AUDIT reviewer_programme_set' in line and 'new=mg-a,mg-b' in line
                            and 'old=(every gift)' in line for line in logs.output), logs.output)

    def test_an_empty_list_is_every_gift(self):
        staff_gift.set_gifts(self.reviewer, [self.gift_a])
        r = self._set(self.oa, self.reviewer, [])
        self.assertEqual((r.status_code, r.json()['gifts']), (200, []))
        self.assertEqual(_ids(self.reviewer), [])

    def test_another_organisations_admin_gets_404(self):
        r = self._set(self.other_oa, self.reviewer, [self.gift_a.id])
        self.assertEqual(r.status_code, 404)
        self.assertEqual(_ids(self.reviewer), [])

    def test_an_org_admin_with_no_organisation_gets_404_and_nothing_changes(self):
        orphan = make_admin('org_admin', uid='mg-oa-none')
        self.assertIsNone(orphan.owning_organisation_id)
        r = self._set(orphan, self.reviewer, [self.gift_a.id])
        self.assertEqual(r.status_code, 404)
        self.assertEqual(_ids(self.reviewer), [])

    def test_a_super_may_tag(self):
        r = self._set(self.boss, self.reviewer, [self.gift_c.id])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(_ids(self.reviewer), [self.gift_c.id])

    def test_a_gift_from_another_organisation_is_404_and_nothing_changes(self):
        staff_gift.set_gifts(self.reviewer, [self.gift_a])
        for caller in (self.oa, self.boss):
            with self.subTest(caller=caller.role):
                r = self._set(caller, self.reviewer, [self.gift_b.id, self.foreign_gift.id])
                self.assertEqual(r.status_code, 404)
                self.assertEqual(_ids(self.reviewer), [self.gift_a.id])

    def test_a_plain_admin_is_refused(self):
        self.assertEqual(self._set(self.plain, self.reviewer, [self.gift_a.id]).status_code, 403)

    def test_not_a_list_is_400(self):
        r = self._set(self.oa, self.reviewer, self.gift_a.id)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'gift_required'))

    def test_the_reviewers_list_serves_the_gifts(self):
        staff_gift.set_gifts(self.reviewer, [self.gift_b, self.gift_a])
        rows = authed_client(self.oa).get('/api/v1/admin/reviewers/').json()['reviewers']
        row = next(x for x in rows if x['id'] == self.reviewer.id)
        self.assertEqual(row['gifts'], [
            {'id': self.gift_a.id, 'code': 'mg-a', 'name': 'Gift A'},
            {'id': self.gift_b.id, 'code': 'mg-b', 'name': 'Gift B'}])


class TestAnInviteNamesSeveralGifts(_Base):
    def _invite(self, body, email='multi.reviewer@example.org'):
        payload = {'email': email, 'name': 'Multi Reviewer', 'role': 'reviewer', **body}
        with patch(CREATE) as create, patch(WELCOME, return_value=True):
            create.return_value = MagicMock(status_code=200, text='ok',
                                            json=lambda: {'id': 'mg-new-uid'})
            return authed_client(self.oa).post(INVITE, payload, format='json')

    def test_several_gifts_are_stored(self):
        r = self._invite({'programme_ids': [self.gift_a.id, self.gift_c.id]})
        self.assertEqual(r.status_code, 201, r.content)
        row = PartnerAdmin.objects.get(email='multi.reviewer@example.org')
        self.assertEqual(_ids(row), [self.gift_a.id, self.gift_c.id])

    def test_an_empty_list_is_every_gift(self):
        r = self._invite({'programme_ids': []})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(_ids(PartnerAdmin.objects.get(email='multi.reviewer@example.org')), [])

    def test_a_foreign_gift_in_the_list_is_404_and_nothing_is_written(self):
        r = self._invite({'programme_ids': [self.gift_a.id, self.foreign_gift.id]})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(PartnerAdmin.objects.filter(email='multi.reviewer@example.org').exists())

    def test_a_reinvite_replaces_the_gifts(self):
        old = PartnerAdmin.objects.create(
            email='back.reviewer@gmail.com', name='Old', role='reviewer', is_active=False,
            owning_organisation=self.bp)
        staff_gift.set_gifts(old, [self.gift_c])
        r = self._invite({'programme_ids': [self.gift_a.id, self.gift_b.id]},
                         email='back.reviewer@gmail.com')
        self.assertEqual(r.status_code, 201, r.content)
        old.refresh_from_db()
        self.assertTrue(old.is_active)
        self.assertEqual(_ids(old), [self.gift_a.id, self.gift_b.id])
