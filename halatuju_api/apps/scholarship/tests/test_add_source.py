"""Add source is back on the Sources page (owner, 2026-11-19).

`POST admin/scholarship/sources/` creates a source WITHOUT inviting anybody. It reverses the
source sign-in S2 part that moved Add into the invite (decisions.md, 2026-11-19); the invite with a
new source stays as it is. Pinned here:

- WHO: the permission alone — Sources "View and change" (`sources.edit`, the `sources` door). View
  only, no access, and the source / reviewer / qc roles are 403. No role name decides.
- THE FENCE: an org_admin's new source is their own organisation's; a super names one with `?org=`;
  an organisation-less super with several tenants is 400 `organisation_required`.
- THE RULES, the same copy the invite uses: `code_and_name_required`, `code_reserved`, `code_taken`
  (per organisation — the same code in another organisation is fine).
- THE NEW SOURCE: joins no gift, `show_in_apply` False unless asked, no person (`sign_in` 'none'),
  and every reader of a person-less source behaves (Sources list, source names, the apply form's
  choices, partner emails).
"""
from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin
from apps.scholarship.models import ProgrammeReferralSource, ReferralSource
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org, make_programme, make_source,
)

SOURCES = '/api/v1/admin/scholarship/sources/'


def _without(admin, *keys):
    """``admin`` with the v2 permission ``keys`` taken off its stored list (a lead unticking them
    on Team tables)."""
    admin.permissions = [k for k in (admin.permissions or []) if k not in keys]
    admin.save(update_fields=['permissions'])
    return PartnerAdmin.objects.get(pk=admin.pk)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org(name='Add Source Org')
        cls.other_org = make_org(name='Another Tenant')
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        # An active org_admin makes the second organisation a TENANT too (`tenants()`).
        cls.other_lead = make_admin('org_admin', owning_org=cls.other_org)
        cls.admin = make_admin('admin', owning_org=cls.org)
        cls.super = make_admin('super', super_admin=True)

    def add(self, caller, query='', **body):
        body.setdefault('code', 'fresh')
        body.setdefault('name', 'Fresh Centre')
        return authed_client(caller).post(SOURCES + query, body, format='json')


class TestWhoMayAdd(_Base):
    def test_sources_view_and_change_may_add(self):
        for caller, code in ((self.lead, 'by-lead'), (self.admin, 'by-admin')):
            with self.subTest(role=caller.role):
                r = self.add(caller, code=code)
                self.assertEqual(r.status_code, 201, r.content)
                self.assertTrue(ReferralSource.objects.filter(organisation=self.org,
                                                              code=code).exists())

    def test_view_only_may_read_but_not_add(self):
        viewer = _without(make_admin('admin', owning_org=self.org), 'sources.edit')
        self.assertIn('sources.view', viewer.permissions)
        self.assertEqual(authed_client(viewer).get(SOURCES).status_code, 200)
        r = self.add(viewer)
        self.assertEqual(r.status_code, 403, r.content)
        self.assertFalse(ReferralSource.objects.filter(code='fresh').exists())

    def test_no_sources_access_may_not_add(self):
        nobody = _without(make_admin('admin', owning_org=self.org), 'sources.edit', 'sources.view')
        self.assertEqual(authed_client(nobody).get(SOURCES).status_code, 403)
        self.assertEqual(self.add(nobody).status_code, 403)
        self.assertFalse(ReferralSource.objects.filter(code='fresh').exists())

    def test_source_reviewer_and_qc_may_not_add(self):
        own = make_source(organisation=self.org, code='mine')
        callers = [make_admin('reviewer', owning_org=self.org), make_admin('qc', owning_org=self.org),
                   make_admin('source_partner', owning_org=self.org, source=own)]
        for caller in callers:
            with self.subTest(role=caller.role):
                self.assertEqual(self.add(caller).status_code, 403)
        self.assertFalse(ReferralSource.objects.filter(code='fresh').exists())


class TestTheFence(_Base):
    def test_an_org_admins_source_is_their_own_organisations(self):
        r = self.add(self.lead, query=f'?org={self.other_org.code}')    # ?org= is a super's only
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(ReferralSource.objects.get(code='fresh').organisation_id, self.org.pk)

    def test_a_super_names_the_organisation(self):
        r = self.add(self.super, query=f'?org={self.other_org.code}')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(ReferralSource.objects.get(code='fresh').organisation_id, self.other_org.pk)

    def test_an_organisation_less_super_among_several_tenants_must_name_one(self):
        r = self.add(self.super)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'organisation_required'))
        self.assertFalse(ReferralSource.objects.filter(code='fresh').exists())


class TestTheRules(_Base):
    def test_code_and_name_are_required(self):
        for body in ({'code': ''}, {'name': '  '}):
            with self.subTest(body=body):
                r = self.add(self.lead, **body)
                self.assertEqual((r.status_code, r.json()['code']),
                                 (400, 'code_and_name_required'))

    def test_reserved_codes_are_refused(self):
        for code in ('other', 'Brightpath'):
            with self.subTest(code=code):
                r = self.add(self.lead, code=code)
                self.assertEqual((r.status_code, r.json()['code']), (400, 'code_reserved'))

    def test_a_code_is_taken_within_its_organisation_only(self):
        make_source(organisation=self.org, code='smc')
        r = self.add(self.lead, code='SMC')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'code_taken'))
        r = self.add(self.other_lead, code='smc')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(ReferralSource.objects.filter(code='smc').count(), 2)

    def test_a_value_that_is_not_text_is_a_400_not_a_500(self):
        r = self.add(self.lead, name=['x'])
        self.assertEqual(r.status_code, 400)


class TestTheNewSource(_Base):
    def test_it_has_no_person_no_gift_and_is_off_the_apply_form_by_default(self):
        gift = make_programme(organisation=self.org)
        r = self.add(self.lead, code='Quiet', contact_person='Mala', phone='0123')
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertEqual((body['code'], body['sign_in'], body['person'], body['show_in_apply']),
                         ('quiet', 'none', None, False))
        made = ReferralSource.objects.get(code='quiet')
        self.assertEqual((made.contact_person, made.phone), ('Mala', '0123'))
        self.assertFalse(ProgrammeReferralSource.objects.filter(source=made).exists())
        self.assertFalse(ProgrammeReferralSource.objects.filter(programme=gift).exists())
        self.assertFalse(PartnerAdmin.objects.filter(source=made).exists())

    def test_show_in_apply_when_asked(self):
        r = self.add(self.lead, show_in_apply=True)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(ReferralSource.objects.get(code='fresh').show_in_apply)

    def test_the_list_shows_it_with_no_person(self):
        self.add(self.lead)
        rows = {s['code']: s for s in authed_client(self.lead).get(SOURCES).json()['sources']}
        self.assertEqual((rows['fresh']['sign_in'], rows['fresh']['user_count'],
                          rows['fresh']['person']), ('none', 0, None))

    def test_every_reader_takes_a_source_with_no_person(self):
        """Source names (Applications filter), the gift's Configuration list, the apply form's
        choices and the partner digest's applications all read a person-less source as a plain
        source: listed by name, offered only once a gift switches it on, no applications."""
        from apps.scholarship import gift_sources, partner_comms
        gift = make_programme(organisation=self.org, is_active=True)
        made = ReferralSource.objects.get(pk=self.add(self.lead, show_in_apply=True).json()['id'])
        names = authed_client(self.lead).get('/api/v1/admin/scholarship/source-names/').json()
        self.assertIn({'code': 'fresh', 'name': 'Fresh Centre'}, names['sources'])
        self.assertIn({'code': 'fresh', 'name': 'Fresh Centre', 'on': False},
                      gift_sources.sources_for(gift))
        self.assertNotIn(made, gift_sources.offered_sources(gift))     # joins no gift
        ProgrammeReferralSource.objects.create(programme=gift, source=made)
        self.assertIn(made, gift_sources.offered_sources(gift))        # once the gift switches it on
        self.assertEqual(partner_comms.partner_applications(made).count(), 0)

    def test_its_details_stay_editable_with_no_person(self):
        made_id = self.add(self.lead).json()['id']
        r = authed_client(self.lead).patch(f'{SOURCES}{made_id}/', {'name': 'Renamed'},
                                           format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(ReferralSource.objects.get(pk=made_id).name, 'Renamed')
