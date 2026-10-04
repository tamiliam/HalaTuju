"""TD-229 (2026-10-03) — the bursary agreement template belongs to a GIFT, not the organisation.

The owner's ruling of 2026-09-04: "the template is PER GIFT". Until this change the rule was one
ACTIVE template per organisation, so the day an organisation ran a second gift its students
would have signed the first gift's wording. What these tests hold:

  * ONE ACTIVE PER GIFT — two gifts in one organisation may each have an active template; a
    second active in ONE gift is archived by `deploy` and refused by the database.
  * AN AGREEMENT RENDERS FROM ITS OWN GIFT'S TEMPLATE, never a neighbour's.
  * A GIFT WITH NO TEMPLATE REFUSES the sign path (`no_active_template`) — no agreement row.
  * THE BACK-FILL IS LOAD-BEARING — a template whose gift is NULL resolves for nobody.
  * THE ADMIN ENDPOINTS keep the organisation fence as the fence; `?programme=` narrows inside
    it, another tenant's gift is a 404 (never a 403), and create without a gift is refused when
    the organisation runs more than one.
"""
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import bursary, contract_scope, contracts
from apps.scholarship.bursary import BursaryError
from apps.scholarship.models import ApplicantDocument, BursaryAgreement, ContractTemplate
from apps.scholarship.tests.contract_helpers import brightpath_org, flagship, make_deployable
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_student,
)

GUAR_NAME, GUAR_NRIC, GUAR_PHONE = 'Rahmah Binti Ahmad', '700101-10-5555', '013-1112222'
BASE = '/api/v1/admin/scholarship/contract-templates/'


def _deployed(version, gift, signatory):
    """An ACTIVE template written for ``gift``, whose counterparty is ``signatory`` — a name
    that appears in the rendered agreement, so a test can tell whose document it is."""
    t = make_deployable(version, programme=gift.code)
    contracts.update_config(t, counterparty_name=signatory)
    contracts.submit_for_deployment(t)
    return contracts.deploy(t, is_super=True)


def _second_gift(code='td229-b'):
    """A second gift in the SAME organisation as the flagship — the case TD-229 is about."""
    return make_programme(organisation=brightpath_org(), code=code, name_en='Second Gift')


def _signable(gift, *, comprehension_template=None):
    """An awarded student of ``gift`` with everything `sign_agreement` checks before the
    template: a matching parent IC, a fresh guarantor-phone PIN, and (optionally) the quiz pass."""
    student = make_student(guardians=[{'name': GUAR_NAME, 'phone': GUAR_PHONE}])
    app = make_application('awarded', cohort=make_cohort(programme=gift), student=student)
    ApplicantDocument.objects.create(
        application=app, doc_type='parent_ic', storage_path=f'{app.id}/parent_ic.jpg',
        vision_run_at=timezone.now(), vision_name=GUAR_NAME, vision_nric=GUAR_NRIC,
        vision_error='')
    app.guarantor_phone = GUAR_PHONE
    app.guarantor_phone_verified_at = timezone.now()
    app.comprehension_template = comprehension_template
    app.save(update_fields=['guarantor_phone', 'guarantor_phone_verified_at',
                            'comprehension_template'])
    return app


def _sign(app):
    return bursary.sign_agreement(
        app, student_signed_name='Gift Student', student_signed_nric='000101-10-1233',
        guarantor_name=GUAR_NAME, guarantor_nric=GUAR_NRIC, guarantor_relationship='mother')


class TestOneActivePerGift(TestCase):
    def test_two_gifts_in_one_organisation_each_keep_an_active_template(self):
        a = _deployed('2026-a', flagship(), 'Flagship Signatory')
        b = _deployed('2026-b', _second_gift(), 'Second Signatory')
        a.refresh_from_db()
        # Deploying B archived NOTHING of A's — until TD-229 it archived the org's one active.
        self.assertEqual((a.status, b.status), ('active', 'active'))
        self.assertEqual(
            ContractTemplate.objects.filter(organisation=brightpath_org(), status='active').count(), 2)

    def test_a_second_deploy_in_one_gift_archives_the_first(self):
        first = _deployed('2026-v1', flagship(), 'One')
        second = _deployed('2026-v2', flagship(), 'Two')
        first.refresh_from_db()
        self.assertEqual((first.status, second.status), ('archived', 'active'))
        self.assertEqual(contract_scope.active_template_for(flagship()), second)

    def test_the_database_refuses_two_active_in_one_gift(self):
        _deployed('2026-v1', flagship(), 'One')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ContractTemplate.objects.create(
                organisation=brightpath_org(), programme=flagship(), version='sneak',
                status='active')

    def test_a_template_without_a_gift_cannot_be_deployed(self):
        # Since TD-327 (0164) the database refuses a NULL gift, so the orphan is built IN MEMORY:
        # `deploy`'s own `programme_required` guard still stands in front of the column.
        t = make_deployable('2026-orphan')
        contracts.submit_for_deployment(t)
        t.programme = None
        with self.assertRaises(contracts.ContractsError) as cm:
            contracts.deploy(t, is_super=True)
        self.assertEqual(cm.exception.code, 'programme_required')
        t.refresh_from_db()
        self.assertEqual(t.status, 'pending_deployment')

    def test_the_database_refuses_a_template_without_a_gift_td327(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ContractTemplate.objects.create(organisation=brightpath_org(), version='no-gift')
        t = make_deployable('2026-homed')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ContractTemplate.objects.filter(pk=t.pk).update(programme=None)
        t.refresh_from_db()
        self.assertEqual(t.programme_id, flagship().id)

    def test_create_refuses_no_gift_and_another_organisations_gift(self):
        with self.assertRaises(contracts.ContractsError) as cm:
            contracts.create_template(brightpath_org(), 'x1')
        self.assertEqual(cm.exception.code, 'programme_required')
        foreign = make_programme()   # in an organisation of its own
        with self.assertRaises(contracts.ContractsError) as cm:
            contracts.create_template(brightpath_org(), 'x2', programme=foreign)
        self.assertEqual(cm.exception.code, 'programme_required')


class TestRendersFromItsOwnGift(TestCase):
    def setUp(self):
        self.gift_b = _second_gift()
        # B FIRST, then A: the organisation's most recently deployed template is then the
        # FLAGSHIP's, so an org-level resolver would hand gift B's student the wrong document.
        self.tmpl_b = _deployed('2026-b', self.gift_b, 'Second Signatory')
        self.tmpl_a = _deployed('2026-a', flagship(), 'Flagship Signatory')

    def test_each_application_resolves_its_own_gifts_template(self):
        app_a = make_application('awarded', cohort=make_cohort(programme=flagship()))
        app_b = make_application('awarded', cohort=make_cohort(programme=self.gift_b))
        self.assertEqual(contract_scope.template_for_application(app_a), self.tmpl_a)
        self.assertEqual(contract_scope.template_for_application(app_b), self.tmpl_b)

    @patch('apps.scholarship.storage.upload_object', return_value=True)
    @patch('apps.scholarship.bursary.generate_pdf', return_value=b'%PDF-local')
    def test_the_signed_agreement_is_the_gifts_own_document(self, _pdf, _up):
        app = _signable(self.gift_b, comprehension_template=self.tmpl_b)
        agreement = _sign(app)
        self.assertEqual(agreement.template_id, self.tmpl_b.id)
        self.assertIn('Second Signatory', agreement.rendered_html)
        self.assertNotIn('Flagship Signatory', agreement.rendered_html)


class TestAGiftWithNoTemplateRefuses(TestCase):
    """`no_active_template` — and no agreement row — whether the flag is on or off: the flag-off
    fall-through could not render anyway (the constants it fell back to went in Sprint 5)."""

    def setUp(self):
        _deployed('2026-a', flagship(), 'Flagship Signatory')   # a NEIGHBOUR has one
        self.bare = _second_gift('td229-bare')

    def _assert_refused(self):
        app = _signable(self.bare)
        self.assertIsNone(contract_scope.template_for_application(app))
        with self.assertRaises(BursaryError) as cm:
            _sign(app)
        self.assertEqual(cm.exception.code, 'no_active_template')
        self.assertFalse(BursaryAgreement.objects.filter(application=app).exists())

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_refused_with_the_flag_on(self):
        self._assert_refused()

    @override_settings(BURSARY_AGREEMENT_ENABLED=False)
    def test_refused_with_the_flag_off(self):
        self._assert_refused()

    def test_an_application_with_no_gift_resolves_nothing(self):
        app = make_application('awarded', cohort=make_cohort(
            programme=None, owning_organisation=brightpath_org()))
        self.assertIsNone(app.programme)
        self.assertIsNone(contract_scope.template_for_application(app))


class _FakeApps:
    """Hands a migration function the REAL Programme models and a stand-in ContractTemplate.

    Since TD-327 (0164) a template with no gift cannot be stored, so the NULL rows 0163 back-filled
    (and 0164 refuses) can no longer be built in the test database. The two data functions are
    proved instead by what they ASK of the ContractTemplate manager."""

    def __init__(self, template_manager):
        from django.apps import apps as django_apps
        self._real = django_apps
        self._template = type('ContractTemplate', (), {'objects': template_manager})

    def get_model(self, app_label, name):
        if name == 'ContractTemplate':
            return self._template
        return self._real.get_model(app_label, name)


class TestTheBackfillIsLoadBearing(TestCase):
    def test_a_gift_less_template_can_no_longer_exist_td327(self):
        # Until TD-327 this test proved that a template whose 0163 UPDATE was skipped governs
        # nobody. The column is NOT NULL now, so that state is refused at the database instead.
        t = _deployed('2026-a', flagship(), 'Flagship Signatory')
        app = make_application('awarded', cohort=make_cohort(programme=flagship()))
        self.assertEqual(contract_scope.template_for_application(app), t)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ContractTemplate.objects.filter(pk=t.pk).update(programme=None)
        self.assertEqual(contract_scope.template_for_application(app), t)

    def test_the_migration_backfill_puts_the_flagships_organisation_on_the_flagship(self):
        from importlib import import_module
        from unittest.mock import MagicMock
        mig = import_module('apps.scholarship.migrations.0163_contracttemplate_programme')
        manager = MagicMock()
        mig.backfill_flagship_templates(_FakeApps(manager), None)
        # Only the flagship's OWN organisation, only rows not yet homed — another organisation's
        # template is never re-homed onto the flagship.
        manager.filter.assert_called_once_with(
            organisation_id=flagship().organisation_id, programme__isnull=True)
        manager.filter.return_value.update.assert_called_once_with(programme=flagship())

    def test_0164_refuses_a_database_still_holding_a_gift_less_template(self):
        from importlib import import_module
        from unittest.mock import MagicMock
        mig = import_module('apps.scholarship.migrations.0164_contracttemplate_programme_not_null')
        manager = MagicMock()
        manager.filter.return_value.count.return_value = 2
        with self.assertRaisesRegex(RuntimeError, 'TD-327: 2 contract template'):
            mig.refuse_null_templates(_FakeApps(manager), None)
        manager.filter.assert_called_once_with(programme__isnull=True)
        manager.filter.return_value.count.return_value = 0
        mig.refuse_null_templates(_FakeApps(manager), None)   # a clean database passes


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheEndpointsNarrowByGiftInsideTheFence(TestCase):
    def setUp(self):
        self.org = brightpath_org()
        self.gift_b = _second_gift()
        self.tmpl_a = _deployed('2026-a', flagship(), 'Flagship Signatory')
        self.tmpl_b = _deployed('2026-b', self.gift_b, 'Second Signatory')
        self.oa = make_admin('org_admin', owning_org=self.org)
        self.foreign_gift = make_programme(code='td229-foreign')
        self.super = make_admin('super', super_admin=True)

    def _ids(self, resp):
        self.assertEqual(resp.status_code, 200, resp.content)
        return {t['id'] for t in resp.json()['templates']}

    def test_omitted_gift_lists_every_template_the_fence_allows(self):
        ids = self._ids(authed_client(self.oa).get(BASE))
        self.assertEqual(ids, {self.tmpl_a.id, self.tmpl_b.id})

    def test_a_named_gift_narrows_to_its_templates_and_labels_them(self):
        resp = authed_client(self.oa).get(f'{BASE}?programme={self.gift_b.code}')
        self.assertEqual(self._ids(resp), {self.tmpl_b.id})
        self.assertEqual(resp.json()['templates'][0]['programme'],
                         {'code': self.gift_b.code, 'name': 'Second Gift'})

    def test_another_tenants_gift_is_404_never_403(self):
        client = authed_client(self.oa)
        self.assertEqual(client.get(f'{BASE}?programme={self.foreign_gift.code}').status_code, 404)
        r = client.post(f'{BASE}?programme={self.foreign_gift.code}', {'version': 'x'}, format='json')
        self.assertEqual(r.status_code, 404)
        self.assertFalse(ContractTemplate.objects.filter(version='x').exists())

    def test_create_takes_the_gift_from_the_scope(self):
        r = authed_client(self.oa).post(
            f'{BASE}?programme={self.gift_b.code}', {'version': '2027-b'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        made = ContractTemplate.objects.get(pk=r.json()['id'])
        self.assertEqual((made.programme_id, made.organisation_id), (self.gift_b.id, self.org.id))

    def test_create_without_a_gift_is_refused_when_the_organisation_runs_several(self):
        r = authed_client(self.oa).post(BASE, {'version': '2027-none'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'programme_required')
        self.assertFalse(ContractTemplate.objects.filter(version='2027-none').exists())

    def test_create_without_a_gift_uses_the_organisations_only_live_gift(self):
        solo = make_org()
        gift = make_programme(organisation=solo)
        oa = make_admin('org_admin', owning_org=solo)
        r = authed_client(oa).post(BASE, {'version': '2027-solo'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(ContractTemplate.objects.get(pk=r.json()['id']).programme_id, gift.id)

    def test_a_super_names_the_gift_and_the_organisation_follows(self):
        r = authed_client(self.super).post(
            f'{BASE}?programme={self.foreign_gift.code}', {'version': '2027-f'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        made = ContractTemplate.objects.get(pk=r.json()['id'])
        self.assertEqual(made.organisation_id, self.foreign_gift.organisation_id)

    def test_only_a_SIGNED_template_blocks_deleting_its_gift(self):
        """Owner ruling 2026-10-03: an unsigned template (draft, active or archived) goes WITH
        the gift; one a BursaryAgreement references holds it."""
        from apps.scholarship.views_admin.gifts import programme_delete_blocker
        bare = _second_gift('td229-empty')
        self.assertEqual(programme_delete_blocker(bare), (None, 0))
        self.assertEqual(programme_delete_blocker(self.gift_b), (None, 0))   # active, unsigned
        BursaryAgreement.objects.create(application=make_application('awarded'),
                                        version=self.tmpl_b.version, template=self.tmpl_b)
        self.assertEqual(programme_delete_blocker(self.gift_b), ('has_contract_templates', 1))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestDeletingAGiftTakesItsUnsignedTemplates(TestCase):
    """The gift-delete handler (owner ruling 2026-10-03, TD-229)."""

    def setUp(self):
        self.org = make_org()
        self.gift = make_programme(organisation=self.org, code='td229-del', is_active=False)
        self.draft = ContractTemplate.objects.create(
            organisation=self.org, programme=self.gift, version='d1')
        self.draft.clauses.create(order=1, heading_en='One', body_en='Body')
        self.archived = ContractTemplate.objects.create(
            organisation=self.org, programme=self.gift, version='a1', status='archived')
        self.client = authed_client(make_admin('org_admin', owning_org=self.org))

    def _delete(self):
        return self.client.delete(f'/api/v1/admin/scholarship/programmes/{self.gift.id}/',
                                  {'confirm': 'delete td229-del'}, format='json')

    def test_the_gift_and_its_unsigned_templates_go_together(self):
        from apps.scholarship.models import ContractClause, Programme
        r = self._delete()
        self.assertEqual(r.status_code, 204, getattr(r, 'data', r.content))
        self.assertFalse(Programme.objects.filter(pk=self.gift.pk).exists())
        self.assertFalse(ContractTemplate.objects.filter(pk__in=[self.draft.pk, self.archived.pk]).exists())
        self.assertFalse(ContractClause.objects.filter(template_id=self.draft.pk).exists())

    def test_a_signed_template_refuses_and_deletes_nothing(self):
        from apps.scholarship.models import Programme
        BursaryAgreement.objects.create(application=make_application('awarded'),
                                        version='a1', template=self.archived)
        r = self._delete()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'has_contract_templates')
        self.assertTrue(Programme.objects.filter(pk=self.gift.pk).exists())
        self.assertEqual(ContractTemplate.objects.filter(programme=self.gift).count(), 2)
        self.assertEqual(self.draft.clauses.count(), 1)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestTheStudentAwardPageIsHonest(TestCase):
    """The student's award GET (flag on, an offer waiting). It previews THEIR GIFT's agreement —
    and until TD-229 it could not preview at all: it called `particulars_for` and
    `render_agreement_html` without the template both have required since Contract Sprint 5,
    so every flag-on preview was a TypeError. With no active template for the gift it now says
    so (`bursary_unavailable`) instead of previewing anything."""

    def setUp(self):
        from apps.scholarship.models import ScholarshipCohort
        from apps.scholarship.tests.test_bursary_agreement import _fund, _fundable_app
        cohort = ScholarshipCohort.objects.create(code='td229-award', name='B40', year=2026)
        self.app = _fundable_app(cohort, suffix='td229')   # its gift gets an active template
        _fund(self.app)
        self.client = authed_client(self.app.profile_id)

    def test_the_gifts_agreement_is_previewed(self):
        r = self.client.get('/api/v1/scholarship/award/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('Suresh', r.json()['bursary_preview']['rendered_html'])
        self.assertNotIn('bursary_unavailable', r.json())

    def test_a_gift_with_no_active_template_previews_nothing_and_says_so(self):
        ContractTemplate.objects.filter(programme=self.app.programme).update(status='archived')
        r = self.client.get('/api/v1/scholarship/award/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn('bursary_preview', r.json())
        self.assertEqual(r.json()['bursary_unavailable'], 'no_active_template')
