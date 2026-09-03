"""Sabah S2b — creating a gift programme and its intake years (2026-09-02).

Until now neither could be created anywhere: no endpoint, no screen, and `scholarship` registers
no models in Django admin. Standing up a second gift meant an engineer writing SQL — which is the
one thing the owner's acceptance test forbids: *"Suresh, as org admin, can do everything on his own
without any work from me."*

Fence tests follow the house rule: cross-org is **404, never 403**.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.models import Programme, ScholarshipCohort
from apps.scholarship.tests.test_api import TEST_JWT_SECRET, _make_token

PROGRAMMES = '/api/v1/admin/scholarship/programmes/'


def _org(code):
    return PartnerOrganisation.objects.create(code=code, name=code.title(), is_active=True)


def _admin(uid, org=None, role='org_admin', super_=False):
    return PartnerAdmin.objects.create(
        supabase_user_id=uid, email=f'{uid}@example.com', name=uid,
        role=role, is_super_admin=super_, is_active=True, owning_organisation=org)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Case(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a, cls.org_b = _org('sab-a'), _org('sab-b')
        cls.prog_a = Programme.objects.create(
            organisation=cls.org_a, code='sab-a-flagship', name_en='A Flagship', is_active=True)
        cls.prog_b = Programme.objects.create(
            organisation=cls.org_b, code='sab-b-flagship', name_en='B Flagship', is_active=True)
        cls.admin_a = _admin('sab-admin-a', cls.org_a)
        cls.admin_b = _admin('sab-admin-b', cls.org_b)
        cls.reviewer_a = _admin('sab-rev-a', cls.org_a, role='reviewer')

    def setUp(self):
        self.client = APIClient()

    def _as(self, admin):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_make_token(admin.supabase_user_id)}')

    def _post(self, admin, url, body):
        self._as(admin)
        return self.client.post(url, body, format='json')

    def _patch(self, admin, url, body):
        self._as(admin)
        return self.client.patch(url, body, format='json')

    def _get(self, admin, url):
        self._as(admin)
        return self.client.get(url)


class TestProgrammes(_Case):
    def test_an_org_admin_sees_only_their_own_organisations_gifts(self):
        r = self._get(self.admin_a, PROGRAMMES)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p['code'] for p in r.data['programmes']], ['sab-a-flagship'])

    def test_a_reviewer_may_not_look_at_all(self):
        # Deciding what a programme IS belongs to the organisation's administrator, the same rule
        # and the same roles as the Layer 0 configuration screen.
        self.assertEqual(self._get(self.reviewer_a, PROGRAMMES).status_code, 403)

    def test_creating_a_gift_leaves_it_INACTIVE(self):
        # ⚠ The property, not a preference. An active second programme changes live behaviour the
        # moment it exists: the payment-run picker appears (S1) and the configuration screen starts
        # asking which programme. Switching on is a separate press.
        r = self._post(self.admin_a, PROGRAMMES, {'code': 'sab-a-sabah', 'name_en': 'A Sabah'})
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data['is_active'])
        self.assertFalse(Programme.objects.get(code='sab-a-sabah').is_active)

    def test_it_refuses_a_client_that_asks_for_active(self):
        r = self._post(self.admin_a, PROGRAMMES,
                       {'code': 'sab-a-two', 'name_en': 'Two', 'is_active': True})
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data['is_active'])

    def test_the_code_must_be_a_url_safe_slug(self):
        for bad in ('Has Caps', 'has space', 'x', '-leading', 'trailing_underscore!'):
            r = self._post(self.admin_a, PROGRAMMES, {'code': bad, 'name_en': 'X'})
            self.assertEqual(r.status_code, 400, bad)
            self.assertEqual(r.data['code'], 'bad_code')

    def test_a_code_already_taken_by_ANOTHER_TENANT_is_refused_without_saying_whose(self):
        # `Programme.code` is unique platform-wide because it is what an apply link carries (PF-1),
        # so the clash may be with a tenant this caller must not learn exists.
        r = self._post(self.admin_a, PROGRAMMES, {'code': 'sab-b-flagship', 'name_en': 'X'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'code_taken')
        self.assertNotIn('sab-b', str(r.data.get('error', '')) + str(r.data.get('organisation', '')))

    def test_another_tenants_gift_is_404_never_403(self):
        r = self._patch(self.admin_a, f'{PROGRAMMES}{self.prog_b.id}/', {'name_en': 'Renamed'})
        self.assertEqual(r.status_code, 404)
        self.prog_b.refresh_from_db()
        self.assertEqual(self.prog_b.name_en, 'B Flagship')

    def test_a_gift_taking_applications_cannot_be_switched_off(self):
        # Switching it off would stop the apply link resolving while a half-finished application
        # still points at it — `resolve_open_cohort` filters on `programme__is_active`.
        ScholarshipCohort.objects.create(
            programme=self.prog_a, owning_organisation=self.org_a,
            code='sab-a-2026', name='A 2026', year=2026, is_active=True, is_open=True)
        r = self._patch(self.admin_a, f'{PROGRAMMES}{self.prog_a.id}/', {'is_active': False})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'has_open_year')


class TestAnInactiveGiftIsReachable(_Case):
    """⚠ A GIFT IS CREATED INACTIVE AND MUST BE CONFIGURED BEFORE IT IS SWITCHED ON.

    That is the whole shape of the create flow (S2: an active second programme changes live
    behaviour the instant it exists), and TWO endpoints filtered `is_active=True` and so refused
    the state an org_admin spends the most time in. The owner hit it on first use: they created a
    second gift, pressed into it, and the console showed them the FIRST gift's settings — the
    breadcrumb list did not contain the new one, so the selection was discarded and fell back.

    The FENCE is the organisation and it is untouched; the cross-org 404s below prove it.
    """

    def setUp(self):
        super().setUp()
        self.draft = Programme.objects.create(
            organisation=self.org_a, code='sab-a-draft-gift', name_en='A Draft Gift',
            is_active=False)

    def test_the_scope_switcher_offers_a_gift_that_is_not_switched_on_yet(self):
        r = self._get(self.admin_a, '/api/v1/admin/scholarship/scopes/')
        self.assertEqual(r.status_code, 200)
        codes = [p['code'] for p in r.data['programmes']]
        self.assertIn('sab-a-draft-gift', codes)
        self.assertIn('sab-a-flagship', codes)

    def test_it_says_which_are_switched_on(self):
        # So a switcher can mark one rather than leaving the reader to find out from the screen.
        r = self._get(self.admin_a, '/api/v1/admin/scholarship/scopes/')
        by_code = {p['code']: p['is_active'] for p in r.data['programmes']}
        self.assertFalse(by_code['sab-a-draft-gift'])
        self.assertTrue(by_code['sab-a-flagship'])

    def test_ANOTHER_TENANTS_inactive_gift_is_still_invisible(self):
        # Widening on `is_active` must not widen on the ORGANISATION. This is the assertion that
        # says the fence did not move.
        Programme.objects.create(
            organisation=self.org_b, code='sab-b-draft', name_en='B Draft', is_active=False)
        r = self._get(self.admin_a, '/api/v1/admin/scholarship/scopes/')
        self.assertNotIn('sab-b-draft', [p['code'] for p in r.data['programmes']])

    def test_its_configuration_can_be_opened_before_it_is_switched_on(self):
        r = self._get(self.admin_a,
                      '/api/v1/admin/scholarship/programme/configuration/?programme=sab-a-draft-gift')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['programme']['code'], 'sab-a-draft-gift')

    def test_configuration_still_404s_across_the_fence(self):
        Programme.objects.create(
            organisation=self.org_b, code='sab-b-draft-2', name_en='B Draft 2', is_active=False)
        r = self._get(self.admin_a,
                      '/api/v1/admin/scholarship/programme/configuration/?programme=sab-b-draft-2')
        self.assertEqual(r.status_code, 404)

    def test_two_gifts_still_refuse_to_be_guessed_between(self):
        # The inactive gift now COUNTS towards ambiguity, which is correct: an unnamed request has
        # two honest answers, so it must ask rather than resolve to the active one.
        r = self._get(self.admin_a, '/api/v1/admin/scholarship/programme/configuration/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'programme_required')
        self.assertEqual(sorted(r.data['programmes']), ['sab-a-draft-gift', 'sab-a-flagship'])


class TestIntakeYears(_Case):
    def _years(self, prog):
        return f'{PROGRAMMES}{prog.id}/years/'

    def test_creating_a_year_does_NOT_open_it(self):
        # `is_open` defaults to True on the model, so creating a year would otherwise let real
        # students in with the same press. Opening is its own deliberate action.
        r = self._post(self.admin_a, self._years(self.prog_a),
                       {'code': 'sab-a-2027', 'name': 'A 2027', 'year': 2027})
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data['is_open'])

    def test_it_sets_BOTH_the_programme_and_the_organisation(self):
        # An application denormalises `owning_organisation` from its cohort, so a cohort carrying
        # one and not the other files students under the wrong fence. It is DERIVED, never asked.
        self._post(self.admin_a, self._years(self.prog_a),
                   {'code': 'sab-a-2028', 'name': 'A 2028', 'year': 2028})
        c = ScholarshipCohort.objects.get(code='sab-a-2028')
        self.assertEqual(c.programme_id, self.prog_a.id)
        self.assertEqual(c.owning_organisation_id, self.org_a.id)

    def test_requirements_are_stored_and_a_missing_one_is_NOT_APPLIED(self):
        r = self._post(self.admin_a, self._years(self.prog_a), {
            'code': 'sab-a-2029', 'name': 'A 2029', 'year': 2029,
            'min_spm_a_count': 4, 'min_spm_bplus_count': 5,
            'income_ceiling': 5860, 'per_capita_ceiling': 1584,
            'min_stpm_pngk': None, 'min_merit_score': None,
        })
        self.assertEqual(r.status_code, 201)
        reqs = r.data['requirements']
        self.assertEqual(reqs['min_spm_a_count'], 4)
        self.assertIsNone(reqs['min_stpm_pngk'])
        self.assertIsNone(reqs['min_merit_score'])

    def test_clearing_a_requirement_unticks_it(self):
        c = ScholarshipCohort.objects.create(
            programme=self.prog_a, owning_organisation=self.org_a, code='sab-a-2030',
            name='A 2030', year=2030, is_active=True, is_open=False, min_stpm_pngk=2.9)
        r = self._patch(self.admin_a, f'/api/v1/admin/scholarship/intake-years/{c.id}/',
                        {'min_stpm_pngk': None})
        self.assertEqual(r.status_code, 200)
        c.refresh_from_db()
        self.assertIsNone(c.min_stpm_pngk)

    def test_a_requirement_NOT_MENTIONED_is_left_alone(self):
        # A PATCH sends only what changed. Absent must not read as "untick" — that would clear
        # every requirement the screen did not happen to send.
        c = ScholarshipCohort.objects.create(
            programme=self.prog_a, owning_organisation=self.org_a, code='sab-a-2031',
            name='A 2031', year=2031, is_active=True, is_open=False, min_spm_a_count=4)
        self._patch(self.admin_a, f'/api/v1/admin/scholarship/intake-years/{c.id}/',
                    {'name': 'Renamed'})
        c.refresh_from_db()
        self.assertEqual(c.min_spm_a_count, 4)

    def test_only_one_round_per_organisation_may_be_open(self):
        # `resolve_open_cohort` RAISES on two open rounds, because picking one files a student
        # under the wrong fence (PF-1). That refusal reaches the STUDENT at the moment they press
        # Apply; this one reaches the ADMIN at the moment they create the ambiguity.
        open_one = ScholarshipCohort.objects.create(
            programme=self.prog_a, owning_organisation=self.org_a, code='sab-a-open',
            name='Open', year=2026, is_active=True, is_open=True)
        other = ScholarshipCohort.objects.create(
            programme=self.prog_a, owning_organisation=self.org_a, code='sab-a-second',
            name='Second', year=2027, is_active=True, is_open=False)
        r = self._patch(self.admin_a, f'/api/v1/admin/scholarship/intake-years/{other.id}/',
                        {'is_open': True})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'another_year_open')
        self.assertEqual(r.data['open_code'], open_one.code)
        other.refresh_from_db()
        self.assertFalse(other.is_open)

    def test_a_year_under_an_INACTIVE_gift_cannot_be_opened(self):
        prog = Programme.objects.create(
            organisation=self.org_a, code='sab-a-draft', name_en='Draft', is_active=False)
        c = ScholarshipCohort.objects.create(
            programme=prog, owning_organisation=self.org_a, code='sab-a-draft-2026',
            name='Draft 2026', year=2026, is_active=True, is_open=False)
        r = self._patch(self.admin_a, f'/api/v1/admin/scholarship/intake-years/{c.id}/',
                        {'is_open': True})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'programme_not_active')

    def test_moving_a_threshold_is_audited_with_the_OLD_and_NEW_value(self):
        # ⚠ THE VALUES, NOT JUST THE FIELD NAMES. A threshold decides who is shortlisted, and
        # `shortlisting.evaluate()` reads it LIVE — so the only question anybody asks afterwards is
        # "from what, to what". TD-203 is the same gap on `award_amount`: three production rows had
        # to be corrected with no system record of who set them, on the owner's memory alone.
        c = ScholarshipCohort.objects.create(
            programme=self.prog_a, owning_organisation=self.org_a, code='sab-a-2032',
            name='A 2032', year=2032, is_active=True, is_open=False, min_spm_a_count=4)
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            r = self._patch(self.admin_a, f'/api/v1/admin/scholarship/intake-years/{c.id}/',
                            {'min_spm_a_count': 3})
        self.assertEqual(r.status_code, 200)
        line = [m for m in logs.output if 'intake_year_requirements_set' in m]
        self.assertEqual(len(line), 1)
        self.assertIn('min_spm_a_count:4->3', line[0])
        self.assertIn(self.admin_a.email, line[0])

    def test_a_threshold_that_did_NOT_move_writes_no_change_line(self):
        # A PATCH restating the same value is not a change, and a log that says otherwise makes the
        # trail useless for the one job it has — a reader cannot tell a real edit from a re-save.
        c = ScholarshipCohort.objects.create(
            programme=self.prog_a, owning_organisation=self.org_a, code='sab-a-2033',
            name='A 2033', year=2033, is_active=True, is_open=False, min_spm_a_count=4)
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            self._patch(self.admin_a, f'/api/v1/admin/scholarship/intake-years/{c.id}/',
                        {'min_spm_a_count': 4, 'name': 'Renamed'})
        self.assertEqual([m for m in logs.output if 'intake_year_requirements_set' in m], [])

    def test_another_tenants_intake_year_is_404(self):
        c = ScholarshipCohort.objects.create(
            programme=self.prog_b, owning_organisation=self.org_b, code='sab-b-2026',
            name='B 2026', year=2026, is_active=True, is_open=False)
        r = self._patch(self.admin_a, f'/api/v1/admin/scholarship/intake-years/{c.id}/',
                        {'name': 'Stolen'})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self._get(self.admin_a, self._years(self.prog_b)).status_code, 404)
