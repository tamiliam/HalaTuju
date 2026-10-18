"""Sources and referral partners, Sprint B (2026-10-18) — a source is its own record, owned by an
organisation (decisions.md "Sources become their own table, owned by an organisation").

1. **The copy** (scholarship 0173) on a production-shaped fixture: every non-tenant, non-fixed-code
   `partner_organisations` row is copied KEEPING ITS ID, owned by THE tenant; nothing else moves —
   CUMIG's referral-partner row, its logins and its students are untouched, and the partner-email
   recipients are the same before and after. It refuses two tenants, and any reference that would
   dangle.
2. **Every repointed foreign key** names `ReferralSource`; `referred_by_org` and
   `Invitation.organisation` still name `PartnerOrganisation`.
3. **The fence** — Sources list / POST / PATCH, the partner emails' milestone matching, and the
   witness choice — with a SECOND organisation in every case. A super's conventions.
4. **Invites** — a `partner` login only onto an active referral partner; a new organisation it
   creates is marked; never onto a tenant or a source's old row; an `org_admin` never onto a
   referral partner. `GET /admin/orgs/` lists referral partners only.
"""
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.apps import apps as live_apps
from django.core import mail
from django.db import connection
from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import partner_comms, partner_notify
from apps.scholarship.models import (
    BursaryAgreement, Invitation, PartnerEmailLog, PartnerEmailTemplate, ProgrammeReferralSource,
    ReferralSource, ScholarshipApplication,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_source, make_student,
)

COPY = import_module('apps.scholarship.migrations.0173_referral_sources')
SOURCES = '/api/v1/admin/scholarship/sources/'
EMAILS = '/api/v1/admin/scholarship/partner-emails/'
INVITE = '/api/v1/admin/invite/'
ORGS = '/api/v1/admin/orgs/'
PARTNER_LIST = '/api/v1/admin/students/'

#: What `copy_sources` reads from its `schema_editor`: only the connection's vendor.
EDITOR = SimpleNamespace(connection=connection)


def _house():
    """The seeded house organisation — the one tenant (it runs the seeded flagship gift)."""
    return PartnerOrganisation.objects.get(code=partner_comms.HOUSE_ORG_CODE)


def _row(code, **kw):
    """A `partner_organisations` row as production has them BEFORE the copy."""
    kw.setdefault('name', code.upper())
    kw.setdefault('show_in_apply', True)
    return PartnerOrganisation.objects.create(code=code, **kw)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheCopyOnAProductionShapedFixture(TestCase):
    """Production on 2026-10-18, shrunk: one tenant (BrightPath); sources cumig (also THE referral
    partner, two `partner` logins, its course-selector students), smc, ewrf, and the switched-off
    sathya_sai and tara; a row carrying a fixed code; students with a source, a witness on an
    application, a partner-email log row."""

    @classmethod
    def setUpTestData(cls):
        cls.house = _house()
        cls.cumig = _row('cumig', is_referral_partner=True, contact_email='CUMIG@Example.org ',
                         contact_person='Cik Partner', phone='011')
        cls.smc = _row('smc', contact_email='smc@example.org')
        cls.ewrf = _row('ewrf')
        cls.sathya = _row('sathya_sai', show_in_apply=False)
        cls.tara = _row('tara', show_in_apply=False, contact_email='tara@example.org')
        cls.fixed = _row('other', show_in_apply=False)          # a fixed form code: never a source
        cls.logins = [make_admin('partner', org=cls.cumig) for _ in range(2)]
        StudentProfile.objects.bulk_create([
            StudentProfile(supabase_user_id=f'sb-cs-{i}', referral_source='cumig',
                           referred_by_org=cls.cumig) for i in range(25)])
        cls.cohort = make_cohort(owning_organisation=cls.house)
        cls.picker = make_student(referral_source='smc')
        cls.app = make_application(cohort=cls.cohort, student=cls.picker)
        cls.copied = (cls.cumig, cls.smc, cls.ewrf, cls.sathya, cls.tara)

    def setUp(self):
        # Production's state before the copy: these columns name `partner_organisations` ids. The
        # FKs now name the new table, so the values go in as raw ids and the copy makes them valid
        # (the test transaction checks every constraint at its end).
        StudentProfile.objects.filter(pk=self.picker.pk).update(source_id=self.smc.pk)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(witness_org_id=self.ewrf.pk)
        PartnerEmailLog.objects.create(organisation_id=self.cumig.pk, kind='weekly_summary',
                                       ok=True, recipients=['cumig@example.org'])

    def _recipients_before(self):
        """`partner_comms.qualifying_partners` as it was BEFORE Sprint B, on this table."""
        rows = (PartnerOrganisation.objects.filter(is_active=True)
                .exclude(code=partner_comms.HOUSE_ORG_CODE).exclude(contact_email='')
                .order_by('name'))
        return [(o.code, partner_comms.recipient_for(o)) for o in rows]

    def _partner_list_count(self):
        resp = authed_client(self.logins[0]).get(PARTNER_LIST)
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()['count']

    def test_every_source_is_copied_with_its_id_owned_by_the_tenant(self):
        COPY.copy_sources(live_apps, EDITOR)
        for row in self.copied:
            with self.subTest(code=row.code):
                src = ReferralSource.objects.get(pk=row.pk)
                self.assertEqual(
                    (src.code, src.name, src.contact_person, src.contact_email, src.phone,
                     src.show_in_apply, src.is_active, src.created_at, src.organisation_id),
                    (row.code, row.name, row.contact_person, row.contact_email, row.phone,
                     row.show_in_apply, row.is_active, row.created_at, self.house.pk))
        for row in (self.house, self.fixed):
            self.assertFalse(ReferralSource.objects.filter(pk=row.pk, code=row.code).exists())

    def test_nothing_else_moves_and_the_referral_partner_is_untouched(self):
        before = (self._partner_list_count(),
                  list(PartnerOrganisation.objects.order_by('pk').values_list(
                      'pk', 'code', 'is_referral_partner', 'is_active', 'contact_email')),
                  list(PartnerAdmin.objects.order_by('pk').values_list('pk', 'org_id', 'role')),
                  StudentProfile.objects.filter(referred_by_org=self.cumig).count())
        COPY.copy_sources(live_apps, EDITOR)
        COPY.refuse_dangling_references(live_apps, EDITOR)        # nothing dangles: no raise
        after = (self._partner_list_count(),
                 list(PartnerOrganisation.objects.order_by('pk').values_list(
                     'pk', 'code', 'is_referral_partner', 'is_active', 'contact_email')),
                 list(PartnerAdmin.objects.order_by('pk').values_list('pk', 'org_id', 'role')),
                 StudentProfile.objects.filter(referred_by_org=self.cumig).count())
        self.assertEqual(before, after)
        self.assertEqual(after[0], 25)
        # The three swapped values now name the copies — the same organisations, by the same ids.
        self.picker.refresh_from_db()
        self.assertEqual(self.picker.source.code, 'smc')
        self.assertEqual(ScholarshipApplication.objects.get(pk=self.app.pk).witness_org.code, 'ewrf')
        self.assertEqual(PartnerEmailLog.objects.get().organisation.code, 'cumig')

    def test_the_partner_email_recipients_are_identical_before_and_after(self):
        before = self._recipients_before()
        # The fixture's own floor: three rows have an address (a switched-off source still
        # qualifies — the email follows `is_active`, not `show_in_apply`).
        self.assertEqual([code for code, _ in before], ['cumig', 'smc', 'tara'])
        COPY.copy_sources(live_apps, EDITOR)
        after = [(s.code, partner_comms.recipient_for(s)) for s in partner_comms.qualifying_partners()]
        self.assertEqual(after, before)

    def test_the_copy_is_idempotent(self):
        COPY.copy_sources(live_apps, EDITOR)
        once = list(ReferralSource.objects.order_by('pk').values())
        COPY.copy_sources(live_apps, EDITOR)
        self.assertEqual(list(ReferralSource.objects.order_by('pk').values()), once)

    def test_two_tenants_copy_nothing(self):
        second = make_org('sb-second')
        make_admin('org_admin', owning_org=second)
        with self.assertRaises(RuntimeError):
            COPY.copy_sources(live_apps, EDITOR)
        self.assertFalse(ReferralSource.objects.filter(pk=self.smc.pk, code='smc').exists())
        # Put the raw ids back to NULL: no copy was made for them to name.
        self._unset_raw_ids()

    def test_a_witness_on_the_house_row_refuses_the_migration(self):
        """The house is a tenant, so it is never copied: a witness naming it would dangle."""
        COPY.copy_sources(live_apps, EDITOR)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(witness_org_id=self.house.pk)
        try:
            with self.assertRaisesRegex(RuntimeError, 'scholarship_applications.witness_org_id'):
                COPY.refuse_dangling_references(live_apps, EDITOR)
        finally:
            ScholarshipApplication.objects.filter(pk=self.app.pk).update(witness_org_id=None)

    def _unset_raw_ids(self):
        StudentProfile.objects.filter(pk=self.picker.pk).update(source_id=None)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(witness_org_id=None)
        PartnerEmailLog.objects.all().delete()


class TestEveryRepointedKey(TestCase):
    def test_the_five_source_columns_name_the_sources_table_and_the_rest_do_not(self):
        cases = (
            (ProgrammeReferralSource, 'source', ReferralSource),
            (StudentProfile, 'source', ReferralSource),
            (ScholarshipApplication, 'witness_org', ReferralSource),
            (BursaryAgreement, 'witness_org', ReferralSource),
            (PartnerEmailLog, 'organisation', ReferralSource),
            # The referral partner's column, and the tenant of a staff invitation, stay put.
            (StudentProfile, 'referred_by_org', PartnerOrganisation),
            (Invitation, 'organisation', PartnerOrganisation),
            (ReferralSource, 'organisation', PartnerOrganisation),
        )
        for model, field, target in cases:
            with self.subTest(field=f'{model.__name__}.{field}'):
                self.assertIs(model._meta.get_field(field).related_model, target)
        # The audit trail can no longer be taken by deleting its source.
        from django.db.models import PROTECT
        self.assertIs(PartnerEmailLog._meta.get_field('organisation').remote_field.on_delete,
                      PROTECT)
        self.assertNotIn('programme', {f.name for f in PartnerOrganisation._meta.fields})


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _TwoOrganisations(TestCase):
    """Organisation A and organisation B, each with a gift, an org_admin and sources — A and B
    BOTH own an `smc`. Plus THE referral partner (CUMIG) on `partner_organisations`."""

    @classmethod
    def setUpTestData(cls):
        cls.a = make_org('sb-a')
        cls.b = make_org('sb-b')
        cls.gift_a = make_programme(organisation=cls.a, code='sb-a-gift', is_active=True)
        cls.gift_b = make_programme(organisation=cls.b, code='sb-b-gift', is_active=True)
        cls.oa_a = make_admin('org_admin', owning_org=cls.a)
        cls.oa_b = make_admin('org_admin', owning_org=cls.b)
        cls.smc_a = make_source(cls.a, 'smc', name='SMC of A', contact_email='a@smc.test')
        cls.only_a = make_source(cls.a, 'only-a', contact_email='only@a.test')
        cls.smc_b = make_source(cls.b, 'smc', name='SMC of B', contact_email='b@smc.test')
        cls.only_b = make_source(cls.b, 'only-b')
        cls.cumig = PartnerOrganisation.objects.create(code='cumig', name='CUMIG',
                                                       is_referral_partner=True)
        cls.super = make_admin('super', super_admin=True)

    def _codes(self, client, query=''):
        resp = client.get(SOURCES + query)
        self.assertEqual(resp.status_code, 200, resp.content)
        return sorted((s['organisation'], s['code']) for s in resp.json()['sources'])


class TestTheSourcesFence(_TwoOrganisations):
    def test_an_organisation_sees_only_its_own_sources(self):
        self.assertEqual(self._codes(authed_client(self.oa_a)),
                         [('sb-a', 'only-a'), ('sb-a', 'smc')])
        self.assertEqual(self._codes(authed_client(self.oa_b)),
                         [('sb-b', 'only-b'), ('sb-b', 'smc')])

    def test_never_the_house_a_tenant_or_a_referral_partner(self):
        codes = {code for _, code in self._codes(authed_client(self.super))}
        for code in ('brightpath', 'sb-a', 'sb-b', 'cumig'):
            self.assertNotIn(code, codes)

    def test_a_new_source_belongs_to_the_callers_organisation(self):
        resp = authed_client(self.oa_a).post(SOURCES, {'code': 'fresh', 'name': 'Fresh'},
                                             format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['organisation'], 'sb-a')
        self.assertEqual(ReferralSource.objects.get(code='fresh').organisation, self.a)
        self.assertFalse(PartnerOrganisation.objects.filter(code='fresh').exists())

    def test_another_organisations_code_is_not_taken_and_ours_is(self):
        resp = authed_client(self.oa_a).post(SOURCES, {'code': 'only-b', 'name': 'Mine'},
                                             format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        resp = authed_client(self.oa_a).post(SOURCES, {'code': 'smc', 'name': 'Again'},
                                             format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (400, 'code_taken'))

    def test_another_organisations_source_is_a_404_and_untouched(self):
        resp = authed_client(self.oa_a).patch(f'{SOURCES}{self.only_b.pk}/',
                                              {'is_active': False, 'name': 'Hijacked'},
                                              format='json')
        self.assertEqual(resp.status_code, 404)
        self.only_b.refresh_from_db()
        self.assertEqual((self.only_b.is_active, self.only_b.name), (True, 'ONLY-B'))

    def test_an_organisation_less_admin_sees_none_and_cannot_add(self):
        loose = make_admin('admin')
        self.assertEqual(self._codes(authed_client(loose)), [])
        resp = authed_client(loose).post(SOURCES, {'code': 'x', 'name': 'X'}, format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (400, 'organisation_required'))
        self.assertFalse(ReferralSource.objects.filter(code='x').exists())

    def test_a_super_sees_every_organisation_and_narrows_with_the_crumb(self):
        client = authed_client(self.super)
        self.assertEqual(self._codes(client), [('sb-a', 'only-a'), ('sb-a', 'smc'),
                                               ('sb-b', 'only-b'), ('sb-b', 'smc')])
        self.assertEqual(self._codes(client, '?org=sb-b'), [('sb-b', 'only-b'), ('sb-b', 'smc')])
        self.assertEqual(client.get(SOURCES + '?org=nope').status_code, 404)

    def test_a_super_must_name_a_tenant_to_create_one(self):
        client = authed_client(self.super)
        resp = client.post(SOURCES, {'code': 'sup', 'name': 'Sup'}, format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (400, 'organisation_required'))
        # A referral partner is not an owner of sources (it is platform data, owned by nobody).
        resp = client.post(SOURCES + '?org=cumig', {'code': 'sup', 'name': 'Sup'}, format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (400, 'organisation_required'))
        resp = client.post(SOURCES + '?org=sb-b', {'code': 'sup', 'name': 'Sup'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(ReferralSource.objects.get(code='sup').organisation, self.b)

    def test_the_gift_count_is_the_sources_own_organisations(self):
        ProgrammeReferralSource.objects.create(programme=self.gift_a, source=self.smc_a)
        rows = {(s['organisation'], s['code']): s
                for s in authed_client(self.super).get(SOURCES).json()['sources']}
        self.assertEqual((rows[('sb-a', 'smc')]['gift_count'], rows[('sb-a', 'smc')]['gift_total']),
                         (1, 1))
        self.assertEqual((rows[('sb-b', 'smc')]['gift_count'], rows[('sb-b', 'smc')]['gift_total']),
                         (0, 1))


class TestThePartnerEmailsScreenIsFenced(_TwoOrganisations):
    """`GET /partner-emails/`: organisation B's admin never sees A's sources, A's counts or A's
    send log — and A's admin sees exactly A's (review fix: the fence had no test)."""

    def setUp(self):
        from django.core.management import call_command
        call_command('seed_partner_email_templates', verbosity=0)
        # Two of A's students named `smc`; B's `smc` has none of its own.
        for _ in range(2):
            make_application('submitted', cohort=make_cohort(programme=self.gift_a),
                             student=make_student(referral_source='smc'))
        PartnerEmailLog.objects.create(organisation=self.smc_a, kind='weekly_summary', ok=True,
                                       recipients=['a@smc.test'], students=2)

    def _screen(self, admin):
        resp = authed_client(admin).get(EMAILS)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        weekly = next(t for t in body['templates'] if t['kind'] == 'weekly_summary')
        return ({o['code']: (o['id'], o['students']) for o in body['organisations']},
                body['qualifying_count'], weekly['last_sent_at'], weekly['last_sent_orgs'])

    def test_b_sees_none_of_as_sources_counts_or_sends(self):
        orgs, qualifying, last_sent, last_orgs = self._screen(self.oa_b)
        self.assertEqual(orgs, {'smc': (self.smc_b.pk, 0), 'only-b': (self.only_b.pk, 0)})
        self.assertEqual(qualifying, 1)                    # B's smc has an address; only-b not
        self.assertEqual((last_sent, last_orgs), (None, 0))

    def test_a_sees_its_own(self):
        orgs, qualifying, last_sent, last_orgs = self._screen(self.oa_a)
        self.assertEqual(orgs, {'smc': (self.smc_a.pk, 2), 'only-a': (self.only_a.pk, 0)})
        self.assertEqual(qualifying, 2)
        self.assertIsNotNone(last_sent)
        self.assertEqual(last_orgs, 1)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestASuperOnAOneTenantPlatform(TestCase):
    """Production today: one tenant. An organisation-less super adding a source from the Sources
    page (which sends no `?org=`) gets the SOLE tenant — evidence, not a guess."""

    def test_the_sole_tenant_owns_it_and_a_second_tenant_makes_it_a_question(self):
        sup = make_admin('super', super_admin=True)
        self.assertEqual(list(PartnerOrganisation.objects.tenants().values_list('code', flat=True)),
                         [partner_comms.HOUSE_ORG_CODE])
        resp = authed_client(sup).post(SOURCES, {'code': 'one', 'name': 'One'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(ReferralSource.objects.get(code='one').organisation, _house())
        make_programme(organisation=make_org('sb-two'), is_active=True)       # a second tenant
        resp = authed_client(sup).post(SOURCES, {'code': 'two', 'name': 'Two'}, format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (400, 'organisation_required'))
        self.assertFalse(ReferralSource.objects.filter(code='two').exists())


@override_settings(PARTNER_COMMS_ENABLED=True,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestMilestonesMatchTheApplicationsOwnOrganisation(_TwoOrganisations):
    def test_a_shared_code_reaches_only_the_source_of_her_own_organisation(self):
        from django.core.management import call_command
        call_command('seed_partner_email_templates', verbosity=0)
        PartnerEmailTemplate.objects.update(enabled=True)
        for gift, code in ((self.gift_a, 'a'), (self.gift_b, 'b')):
            cohort = make_cohort(programme=gift)
            student = make_student(referral_source='smc', name=f'Student {code.upper()}')
            make_application('profile_complete', cohort=cohort, student=student)
        mail.outbox = []
        partner_notify.send_partner_milestones()
        by_recipient = {m.to[0]: m.body for m in mail.outbox}
        self.assertEqual(set(by_recipient), {'a@smc.test', 'b@smc.test'})
        self.assertIn('STUDENT A', by_recipient['a@smc.test'])
        self.assertNotIn('STUDENT B', by_recipient['a@smc.test'])
        self.assertIn('STUDENT B', by_recipient['b@smc.test'])
        self.assertNotIn('STUDENT A', by_recipient['b@smc.test'])


@override_settings(PARTNER_COMMS_ENABLED=False)
class TestTheWitnessChoiceIsFenced(_TwoOrganisations):
    def setUp(self):
        self.app_a = make_application('profile_complete', cohort=make_cohort(programme=self.gift_a))

    def _assign(self, admin, app, value):
        return authed_client(admin).patch(
            f'/api/v1/admin/scholarship/applications/{app.id}/witness/',
            {'witness_org': value}, format='json')

    def test_a_shared_code_names_the_applications_own_organisations_source(self):
        resp = self._assign(self.oa_a, self.app_a, 'smc')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.app_a.refresh_from_db()
        self.assertEqual(self.app_a.witness_org_id, self.smc_a.pk)

    def test_another_organisations_source_a_tenant_or_the_house_is_refused(self):
        for value in ('only-b', self.only_b.pk, 'sb-a', 'brightpath', 'cumig'):
            with self.subTest(value=str(value)):
                resp = self._assign(self.super, self.app_a, value)
                self.assertEqual((resp.status_code, resp.json()['code']),
                                 (400, 'unknown_organisation'))
        self.app_a.refresh_from_db()
        self.assertIsNone(self.app_a.witness_org_id)

    def test_another_organisations_application_is_a_404(self):
        resp = self._assign(self.oa_b, self.app_a, 'smc')
        self.assertEqual(resp.status_code, 404)
        self.app_a.refresh_from_db()
        self.assertIsNone(self.app_a.witness_org_id)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   SUPABASE_URL='https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY='k',
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestInvitesNeverBlurTheCategories(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.super = make_admin('super', super_admin=True)
        cls.cumig = PartnerOrganisation.objects.create(code='cumig', name='CUMIG',
                                                       is_referral_partner=True)
        cls.old_source_row = PartnerOrganisation.objects.create(code='smc', name='SMC')
        cls.tenant = make_org('sb-tenant')
        make_admin('org_admin', owning_org=cls.tenant)
        # As production after the copy: the old row's SOURCE twin (same id and code), owned by
        # the tenant.
        make_source(cls.tenant, 'smc', pk=cls.old_source_row.pk)

    def _invite(self, **payload):
        payload = {'email': f'{payload.get("role", "x")}{len(PartnerAdmin.objects.all())}@i.test',
                   'name': 'Invitee', **payload}
        with patch('apps.courses.views_admin.http_requests.post') as mp:
            uid = f'uid-{payload["email"]}'             # one login per invitee
            mp.return_value = MagicMock(status_code=200, text='ok', json=lambda: {'id': uid})
            return authed_client(self.super).post(INVITE, payload, format='json')

    def test_a_partner_login_onto_the_referral_partner_is_accepted(self):
        resp = self._invite(role='partner', org_id=self.cumig.pk)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(PartnerAdmin.objects.get(role='partner').org, self.cumig)

    def test_never_onto_a_source_row_a_tenant_or_a_switched_off_partner(self):
        sleepy = PartnerOrganisation.objects.create(code='sleepy', name='S', is_active=False,
                                                    is_referral_partner=True)
        for org, code in ((self.old_source_row, 'not_a_referral_partner'),
                          (self.tenant, 'org_is_tenant'),
                          (sleepy, 'not_a_referral_partner')):
            with self.subTest(org=org.code):
                before = PartnerAdmin.objects.count()
                resp = self._invite(role='partner', org_id=org.pk)
                self.assertEqual((resp.status_code, resp.json()['code']), (400, code))
                self.assertTrue(resp.json()['error'])          # a sentence the screen shows
                self.assertEqual(PartnerAdmin.objects.count(), before)
                org.refresh_from_db()
                self.assertEqual(org.is_referral_partner, org.code == 'sleepy')   # never marked

    def test_a_new_organisation_made_by_the_invite_is_a_referral_partner(self):
        resp = self._invite(role='partner', new_org_name='Roadshow', new_org_code='roadshow')
        self.assertEqual(resp.status_code, 201, resp.content)
        made = PartnerOrganisation.objects.get(code='roadshow')
        self.assertTrue(made.is_referral_partner)
        self.assertFalse(ReferralSource.objects.filter(code='roadshow').exists())

    def test_a_new_code_that_exists_follows_the_existing_rows_rule(self):
        for code, refusal in (('smc', 'not_a_referral_partner'), ('sb-tenant', 'org_is_tenant'),
                              ('other', 'code_reserved'), ('brightpath', 'code_reserved'),
                              ('bad code', 'bad_code')):
            with self.subTest(code=code):
                resp = self._invite(role='partner', new_org_name='X', new_org_code=code)
                self.assertEqual((resp.status_code, resp.json()['code']), (400, refusal))
        self.assertFalse(PartnerOrganisation.objects.get(code='smc').is_referral_partner)

    def test_an_org_admin_is_never_installed_on_a_referral_partner(self):
        for payload in ({'org_id': self.cumig.pk},
                        {'new_org_name': 'CUMIG', 'new_org_code': 'cumig'}):
            with self.subTest(payload=sorted(payload)):
                resp = self._invite(role='org_admin', **payload)
                self.assertEqual((resp.status_code, resp.json()['code']),
                                 (400, 'org_is_referral_partner'))
        self.cumig.refresh_from_db()
        self.assertFalse(self.cumig.module_scholarship)
        self.assertNotIn(self.cumig.pk, set(PartnerOrganisation.objects.tenants()
                                            .values_list('pk', flat=True)))

    def test_an_org_admin_never_turns_a_sources_old_row_into_a_tenant(self):
        """Review fix: `get_or_create(code='smc')` used to REUSE the old source row, switch its
        scholarship module on and bind the org_admin — a second tenant, in every tenant picker and
        on the monthly invoices, and the end of the sole-tenant fallback."""
        for payload, code in (({'new_org_name': 'SMC', 'new_org_code': 'smc'}, 'code_taken'),
                              ({'org_id': self.old_source_row.pk}, 'not_a_tenant')):
            with self.subTest(code=code):
                before = PartnerAdmin.objects.count()
                resp = self._invite(role='org_admin', **payload)
                self.assertEqual((resp.status_code, resp.json()['code']), (400, code))
                self.assertTrue(resp.json()['error'])
                self.assertEqual(PartnerAdmin.objects.count(), before)
        self.old_source_row.refresh_from_db()
        self.assertFalse(self.old_source_row.module_scholarship)
        self.assertNotIn(self.old_source_row.pk, set(PartnerOrganisation.objects.tenants()
                                                     .values_list('pk', flat=True)))

    def test_an_org_admin_onto_an_existing_tenant_or_a_new_organisation_still_works(self):
        for payload in ({'org_id': self.tenant.pk},
                        {'new_org_name': 'Inspire', 'new_org_code': 'inspire'}):
            with self.subTest(payload=sorted(payload)):
                resp = self._invite(role='org_admin', **payload)
                self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(PartnerOrganisation.objects.get(code='inspire').module_scholarship)

    def test_the_invite_dropdown_lists_referral_partners_only(self):
        resp = authed_client(self.super).get(ORGS)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual([o['code'] for o in resp.json()['orgs']], ['cumig'])
