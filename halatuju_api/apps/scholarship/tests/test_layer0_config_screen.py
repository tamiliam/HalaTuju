"""Layer 0 Sprint 5 — the programme configuration endpoint (2026-08-30).

What an `org_admin` can set, what they cannot, and — the one that matters — that a write here is
read by the SAME seam the gates enforce. The fence tests follow the house rule: cross-org is 404,
never 403.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import requirements
from apps.scholarship.models import (
    ApplicationItem, Programme, ProgrammeApplicationItem, ScholarshipApplication,
    ScholarshipCohort,
)
from apps.scholarship.tests.test_api import TEST_JWT_SECRET, _make_token

URL = '/api/v1/admin/scholarship/programme/configuration/'


def _org(code):
    return PartnerOrganisation.objects.create(code=code, name=code.title(), is_active=True)


def _programme(org, code):
    return Programme.objects.create(organisation=org, code=code, name_en=code.title(), is_active=True)


def _admin(uid, org=None, role='org_admin', super_=False):
    return PartnerAdmin.objects.create(
        supabase_user_id=uid, email=f'{uid}@example.com', name=uid,
        role=role, is_super_admin=super_, is_active=True, owning_organisation=org)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _ConfigCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_application_catalogue', verbosity=0)
        cls.org_a = _org('cfg-a')
        cls.org_b = _org('cfg-b')
        cls.prog_a = _programme(cls.org_a, 'cfg-a-bursary')
        cls.prog_b = _programme(cls.org_b, 'cfg-b-bursary')

    def setUp(self):
        self.client = APIClient()

    def _as(self, admin):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_make_token(admin.supabase_user_id)}')

    def _get(self, admin, query=''):
        self._as(admin)
        return self.client.get(URL + query)

    def _put(self, admin, items, query=''):
        self._as(admin)
        return self.client.put(URL + query, {'items': items}, format='json')


class TestReading(_ConfigCase):

    def test_an_org_admin_reads_their_own_programme_without_naming_it(self):
        resp = self._get(_admin('oa-1', org=self.org_a))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['programme']['code'], 'cfg-a-bursary')
        codes = {(i['kind'], i['code']): i for i in body['items']}
        self.assertEqual(codes[('document', 'ic')]['state'], 'required')
        self.assertTrue(codes[('document', 'ic')]['is_core'])
        self.assertEqual(codes[('document', 'water_bill')]['state'], 'optional')
        self.assertEqual(codes[('question', 'justification')]['state'], 'optional')
        self.assertEqual(len(body['items']), 19)   # 9 documents + 10 questions

    def test_a_cross_org_programme_is_404_not_403(self):
        resp = self._get(_admin('oa-2', org=self.org_a), '?programme=cfg-b-bursary')
        self.assertEqual(resp.status_code, 404)

    def test_a_plain_admin_is_refused(self):
        resp = self._get(_admin('ad-1', org=self.org_a, role='admin'))
        self.assertEqual(resp.status_code, 403)

    def test_a_super_must_name_the_programme_when_there_are_several(self):
        resp = self._get(_admin('su-1', role='super', super_=True))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['code'], 'programme_required')
        self.assertIn('cfg-b-bursary', resp.json()['programmes'])
        resp = self._get(_admin('su-1b', role='super', super_=True), '?programme=cfg-b-bursary')
        self.assertEqual(resp.status_code, 200)

    def test_live_applicants_counts_only_students_still_inside_the_gate(self):
        cohort = ScholarshipCohort.objects.create(code='cfg-c', name='C', year=2026, programme=self.prog_a)
        for i, st in enumerate(['shortlisted', 'shortlisted', 'profile_complete', 'rejected']):
            prof = StudentProfile.objects.create(supabase_user_id=f'cfg-s{i}', nric=f'08010{i}-14-000{i}')
            ScholarshipApplication.objects.create(cohort=cohort, profile=prof, status=st)
        resp = self._get(_admin('oa-3', org=self.org_a))
        self.assertEqual(resp.json()['live_applicants'], 2)


class TestWriting(_ConfigCase):

    def test_a_write_reaches_the_gate_seam_and_leaves_the_neighbour_alone(self):
        admin = _admin('oa-4', org=self.org_a)
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            resp = self._put(admin, [{'kind': 'document', 'code': 'water_bill', 'state': 'required'}])
        self.assertEqual(resp.status_code, 200)
        # The screen re-reads what it wrote…
        states = {(i['kind'], i['code']): i['state'] for i in resp.json()['items']}
        self.assertEqual(states[('document', 'water_bill')], 'required')
        self.assertEqual(states[('document', 'electricity_bill')], 'optional')   # neighbour untouched
        # …and the SEAM the gates read agrees — this is the sprint's whole point.
        self.assertEqual(requirements.programme_states(self.prog_a, 'document')['water_bill'], 'required')
        self.assertEqual(requirements.programme_states(self.prog_b, 'document')['water_bill'], 'optional')
        # Audited: who, which programme, which item, old → new.
        line = [l for l in logs.output if 'AUDIT programme_item_set' in l]
        self.assertEqual(len(line), 1)
        self.assertIn('programme=cfg-a-bursary', line[0])
        self.assertIn('item=document:water_bill', line[0])
        self.assertIn('was=optional now=required', line[0])
        self.assertIn('by=oa-4@example.com', line[0])

    def test_a_core_item_cannot_be_switched_off_and_nothing_is_written(self):
        admin = _admin('oa-5', org=self.org_a)
        resp = self._put(admin, [
            {'kind': 'document', 'code': 'water_bill', 'state': 'required'},   # valid…
            {'kind': 'question', 'code': 'consent', 'state': 'off'},           # …then a core → off
        ])
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['code'], 'core_item')
        self.assertEqual(resp.json()['item'], 'question:consent')
        # All-or-nothing: the valid first entry was NOT applied either.
        self.assertFalse(ProgrammeApplicationItem.objects.filter(programme=self.prog_a).exists())

    def test_a_write_at_the_current_state_is_not_audited(self):
        admin = _admin('oa-6', org=self.org_a)
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            # assertLogs needs at least one line; the read path logs nothing, so emit one ourselves.
            import logging
            logging.getLogger('apps.scholarship.views_admin').info('sentinel')
            resp = self._put(admin, [{'kind': 'document', 'code': 'water_bill', 'state': 'optional'}])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([l for l in logs.output if 'AUDIT' in l], [])

    def test_cross_org_write_is_404_and_writes_nothing(self):
        admin = _admin('oa-7', org=self.org_a)
        resp = self._put(admin, [{'kind': 'document', 'code': 'water_bill', 'state': 'off'}],
                         '?programme=cfg-b-bursary')
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(ProgrammeApplicationItem.objects.filter(programme=self.prog_b).exists())

    def test_unknown_item_and_bad_state_are_refused(self):
        admin = _admin('oa-8', org=self.org_a)
        self.assertEqual(self._put(admin, [{'kind': 'document', 'code': 'passport', 'state': 'off'}]).status_code, 404)
        self.assertEqual(self._put(admin, [{'kind': 'document', 'code': 'photo', 'state': 'maybe'}]).status_code, 400)

    def test_a_switched_off_question_stops_gating_a_NEW_application(self):
        # End to end: the screen's write governs a student who applies afterwards.
        admin = _admin('oa-9', org=self.org_a)
        self._put(admin, [{'kind': 'question', 'code': 'fears', 'state': 'off'}])
        cohort = ScholarshipCohort.objects.create(code='cfg-c2', name='C2', year=2026, programme=self.prog_a)
        prof = StudentProfile.objects.create(supabase_user_id='cfg-new', nric='080909-14-9999')
        app = ScholarshipApplication.objects.create(cohort=cohort, profile=prof, status='shortlisted',
                                                    aspirations='a', plans='p', daily_life='d', fears='')
        from apps.scholarship.services import application_completeness
        self.assertTrue(application_completeness(app)['details_done'])
        self.assertNotIn('fears', requirements.payload_for(app, 'question')['required'])
