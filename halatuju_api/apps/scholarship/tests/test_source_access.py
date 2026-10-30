"""Source sign-in S1 (2026-10-30): the `source_partner` role, its `source` binding and what it may
reach (`apps/scholarship/source_access.py`). The deny-by-default sweep is
`test_source_user_denied_everywhere.py`; the staff lists are `test_source_user_is_not_staff.py`.
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from apps.courses import staff_permissions
from apps.courses.models import PartnerAdmin
from apps.scholarship import source_access
from apps.scholarship.models import ProgrammeReferralSource, ScholarshipCohort
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_source,
)


class TestTheSourceBinding(TestCase):
    """role `source_partner` ⇔ `source` set; never a super; the source's organisation is the
    user's `owning_organisation`."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.source = make_source(organisation=cls.org)

    def test_a_source_user_with_its_source_saves(self):
        user = make_admin('source_partner', owning_org=self.org, source=self.source)
        self.assertEqual(list(self.source.users.all()), [user])

    def test_a_source_user_without_a_source_is_refused(self):
        # By hand: the factory gives a source user its source, as the product would.
        with self.assertRaises(ValidationError):
            PartnerAdmin.objects.create(role='source_partner', name='x', email='nosrc@example.test',
                                        owning_organisation=self.org)

    def test_the_factory_builds_a_source_user_with_its_source(self):
        user = make_admin('source_partner', owning_org=self.org)
        self.assertEqual(user.source.organisation_id, self.org.pk)
        self.assertEqual(make_admin('source_partner').source_binding_problem(), None)

    def test_a_staff_row_with_a_source_is_refused(self):
        with self.assertRaises(ValidationError):
            make_admin('reviewer', owning_org=self.org, source=self.source)

    def test_a_source_user_in_another_organisation_is_refused(self):
        with self.assertRaises(ValidationError):
            make_admin('source_partner', owning_org=make_org(), source=self.source)
        with self.assertRaises(ValidationError):
            make_admin('source_partner', owning_org=None, source=self.source)

    def test_a_source_user_is_never_a_super(self):
        with self.assertRaises(ValidationError):
            make_admin('source_partner', owning_org=self.org, source=self.source,
                       super_admin=True)

    def test_clean_says_the_same(self):
        row = PartnerAdmin(role='source_partner', name='x', email='x@example.test',
                           owning_organisation=self.org)
        with self.assertRaises(ValidationError):
            row.clean()

    def test_the_database_refuses_what_save_would_have_refused(self):
        """`.update()` skips `save()`, so the CHECK constraint is the backstop for both halves."""
        reviewer = make_admin('reviewer', owning_org=self.org)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PartnerAdmin.objects.filter(pk=reviewer.pk).update(role='source_partner')
        with self.assertRaises(IntegrityError), transaction.atomic():
            PartnerAdmin.objects.filter(pk=reviewer.pk).update(source=self.source)
        user = make_admin('source_partner', owning_org=self.org, source=self.source)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PartnerAdmin.objects.filter(pk=user.pk).update(role='reviewer')
        with self.assertRaises(IntegrityError), transaction.atomic():
            PartnerAdmin.objects.filter(pk=user.pk).update(is_super_admin=True)

    def test_an_unrelated_save_on_staff_reads_no_source(self):
        """The guard costs a source user one look-up and a staff save nothing."""
        reviewer = make_admin('reviewer', owning_org=self.org)
        with self.assertNumQueries(1):
            reviewer.save(update_fields=['name'])


class TestASourceUserHoldsNoPermission(TestCase):
    def test_resolve_is_empty_and_every_key_is_refused(self):
        org = make_org()
        user = make_admin('source_partner', owning_org=org, source=make_source(organisation=org))
        self.assertEqual(staff_permissions.resolve(user), ())
        self.assertEqual(staff_permissions.preset_for('source_partner'), ())
        self.assertFalse(staff_permissions.is_custom(user))
        for key in staff_permissions.CATALOGUE:
            self.assertFalse(user.has_perm(key), key)
            self.assertNotIn(user, staff_permissions.holders(org, key))
        # A stored list on the row changes nothing: the role is outside TEAM_ROLES.
        user.permissions = list(staff_permissions.CATALOGUE)
        self.assertEqual(staff_permissions.resolve(user), ())


class TestWhatASourceUserMayReach(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.source = make_source(organisation=cls.org)
        cls.other_source = make_source(organisation=cls.org)
        cls.linked_gift = make_programme(organisation=cls.org)
        cls.held_gift = make_programme(organisation=cls.org)
        cls.unrelated_gift = make_programme(organisation=cls.org)
        ProgrammeReferralSource.objects.create(programme=cls.linked_gift, source=cls.source)
        cls.own = make_application('submitted', cohort=make_cohort(programme=cls.held_gift),
                                   source=cls.source)
        cls.witnessed = make_application(
            'submitted', cohort=make_cohort(programme=cls.unrelated_gift),
            source=cls.other_source, witness_org=cls.source)
        cls.others = make_application('submitted', cohort=make_cohort(programme=cls.unrelated_gift),
                                      source=cls.other_source)
        # Another organisation's gift and application, wrongly pointing at this source: the fence
        # must keep both out even though the source id matches.
        cls.other_org = make_org()
        cls.foreign_gift = make_programme(organisation=cls.other_org)
        ProgrammeReferralSource.objects.create(programme=cls.foreign_gift, source=cls.source)
        cls.foreign = make_application('submitted', cohort=make_cohort(programme=cls.foreign_gift),
                                       source=cls.source)
        cls.user = make_admin('source_partner', owning_org=cls.org, source=cls.source)

    def ids(self, qs):
        return sorted(qs.values_list('pk', flat=True))

    def test_applications_are_its_own_plus_the_ones_it_witnesses(self):
        self.assertEqual(self.ids(source_access.applications_for(self.user)),
                         sorted([self.own.pk, self.witnessed.pk]))

    def test_the_list_is_its_own_only_never_a_witness_only_case(self):
        self.assertEqual(self.ids(source_access.listed_applications_for(self.user)), [self.own.pk])

    def test_gifts_are_the_linked_and_the_held_never_another_organisations(self):
        self.assertEqual(self.ids(source_access.programmes_for(self.user)),
                         sorted([self.linked_gift.pk, self.held_gift.pk]))

    def test_a_cohort_moved_to_another_gift_brings_that_gift(self):
        ScholarshipCohort.objects.filter(pk=self.own.cohort_id).update(
            programme=self.unrelated_gift)
        self.assertEqual(self.ids(source_access.programmes_for(self.user)),
                         sorted([self.linked_gift.pk, self.held_gift.pk, self.unrelated_gift.pk]))

    def assertSeesNothing(self, admin):
        self.assertEqual(self.ids(source_access.applications_for(admin)), [])
        self.assertEqual(self.ids(source_access.listed_applications_for(admin)), [])
        self.assertEqual(self.ids(source_access.programmes_for(admin)), [])

    def test_a_switched_off_source_sees_nothing(self):
        self.source.is_active = False
        self.source.save(update_fields=['is_active'])
        self.user.refresh_from_db()
        self.assertSeesNothing(self.user)

    def test_hidden_from_the_apply_form_still_signs_in(self):
        """`show_in_apply=False` is the apply form's switch, not the sign-in's."""
        self.source.show_in_apply = False
        self.source.save(update_fields=['show_in_apply'])
        self.user.refresh_from_db()
        self.assertEqual(self.ids(source_access.listed_applications_for(self.user)), [self.own.pk])

    def test_a_revoked_source_user_sees_nothing(self):
        self.user.is_active = False
        self.assertSeesNothing(self.user)

    def test_anybody_else_sees_nothing(self):
        self.assertSeesNothing(None)
        self.assertSeesNothing(make_admin('org_admin', owning_org=self.org))
        self.assertSeesNothing(make_admin('reviewer', owning_org=self.org))
        self.assertSeesNothing(make_admin('super', super_admin=True))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheRoleAndScopeEndpoints(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.source = make_source(organisation=cls.org, name='Kampung Trust')
        cls.gift = make_programme(organisation=cls.org)
        cls.other_gift = make_programme(organisation=cls.org)
        ProgrammeReferralSource.objects.create(programme=cls.gift, source=cls.source)
        cls.user = make_admin('source_partner', owning_org=cls.org, source=cls.source)

    def test_role_names_the_source_for_a_source_user(self):
        body = authed_client(self.user).get('/api/v1/admin/role/').json()
        self.assertEqual((body['role'], body['source_id'], body['source_name']),
                         ('source_partner', self.source.pk, 'Kampung Trust'))
        self.assertEqual((body['permissions'], body['owning_org_id']), ([], self.org.pk))

    def test_role_names_no_source_for_staff(self):
        body = authed_client(make_admin('reviewer', owning_org=self.org)).get(
            '/api/v1/admin/role/').json()
        self.assertEqual((body['source_id'], body['source_name']), (None, None))

    def test_scopes_are_the_sources_organisation_and_gifts(self):
        body = authed_client(self.user).get('/api/v1/admin/scholarship/scopes/').json()
        self.assertEqual([o['id'] for o in body['organisations']], [self.org.pk])
        self.assertEqual([(p['id'], p['is_active'], p['organisation_id']) for p in body['programmes']],
                         [(self.gift.pk, self.gift.is_active, self.org.pk)])

    def test_a_switched_off_source_gets_empty_scopes(self):
        self.source.is_active = False
        self.source.save(update_fields=['is_active'])
        body = authed_client(self.user).get('/api/v1/admin/scholarship/scopes/').json()
        self.assertEqual(body, {'organisations': [], 'programmes': []})

    def test_staff_scopes_are_unchanged(self):
        body = authed_client(make_admin('org_admin', owning_org=self.org)).get(
            '/api/v1/admin/scholarship/scopes/').json()
        self.assertEqual(sorted(p['id'] for p in body['programmes']),
                         sorted([self.gift.pk, self.other_gift.pk]))
