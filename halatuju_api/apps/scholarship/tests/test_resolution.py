"""Tests for the resolution-ticket engine (Sprint 3).

Real-ORM fixtures (lesson #55). Covers generation, the mapping exclusions (the
three codes deliberately NOT ticketed), idempotency, auto-resolve on gap-clear,
the no-re-nag rule, student resolve, and officer-raised items.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.resolution import (
    add_officer_item, resolve_item, sync_resolution_items,
)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'res-{self.id()}', name='THERESA ARUL MARY A/P A.PHILIPS',
            nric='080115-05-0132', preferred_state='Melaka',
            household_income=1800, household_size=4, receives_str=False, receives_jkm=False,
        )
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            chosen_pathway='Matriculation',
        )

    def _codes(self, items):
        return sorted(i.code for i in items)


def _add_ic(app, *, nric='', name='', address='', error='', run=True):
    return ApplicantDocument.objects.create(
        application=app, doc_type='ic', storage_path=f'{app.id}/ic/x',
        vision_nric=nric, vision_name=name, vision_address=address,
        vision_run_at=timezone.now() if run else None, vision_error=error,
    )


def _add_doc(app, doc_type, *, student_verdict='', fields=None, name_match=''):
    vf = {}
    if student_verdict or fields is not None:
        vf = {'fields': fields or {}, 'warnings': [], 'student_verdict': student_verdict, 'error': ''}
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, storage_path=f'{app.id}/{doc_type}/x',
        vision_fields=vf, vision_name_match=name_match, vision_run_at=timezone.now(),
    )


class TestGeneration(_Base):
    def test_bare_application_generates_doc_tickets(self):
        # No documents → ic/results/income gaps; pathway declared (no ticket).
        items = sync_resolution_items(self.app)
        self.assertEqual(self._codes(items),
                         ['ic_missing', 'income_proof_missing', 'results_slip_missing'])
        self.assertTrue(all(i.kind == 'doc' and i.source == 'system' for i in items))

    def test_doc_ticket_carries_doc_type(self):
        items = {i.code: i for i in sync_resolution_items(self.app)}
        self.assertEqual(items['ic_missing'].doc_type, 'ic')
        self.assertEqual(items['results_slip_missing'].doc_type, 'results_slip')

    def test_confirm_ticket_for_address_mismatch(self):
        _add_ic(self.app, nric=self.profile.nric, name=self.profile.name,
                address='NO 1 JALAN X, 08000 SUNGAI PETANI, KEDAH')
        _add_doc(self.app, 'results_slip', student_verdict='ok', name_match='found')
        _add_doc(self.app, 'str', name_match='found')  # income verified
        codes = {i.code: i for i in sync_resolution_items(self.app)}
        self.assertIn('address_state_mismatch', codes)
        self.assertEqual(codes['address_state_mismatch'].kind, 'confirm')


class TestMappingExclusions(_Base):
    def test_nonticketable_codes_make_no_tickets(self):
        # ic_service_down + grades_unverified + str_present_unverified are the
        # three deliberately-excluded codes.
        self.profile.receives_str = True
        self.profile.save()
        _add_ic(self.app, error='Vision API down')                       # ic_service_down
        _add_doc(self.app, 'results_slip', student_verdict='ok', name_match='found')  # grades_unverified
        _add_doc(self.app, 'str', name_match='not_found')                # str_present_unverified
        self.assertEqual(sync_resolution_items(self.app), [])


class TestIdempotencyAndLifecycle(_Base):
    def test_sync_is_idempotent(self):
        sync_resolution_items(self.app)
        sync_resolution_items(self.app)
        self.assertEqual(self.app.resolution_items.filter(source='system').count(), 3)

    def test_auto_resolve_when_gap_clears(self):
        self.profile.receives_str = True
        self.profile.save()
        # str_claimed_no_doc ticket appears.
        codes = self._codes(sync_resolution_items(self.app))
        self.assertIn('str_claimed_no_doc', codes)
        # Upload an STR doc → the income gap clears.
        _add_doc(self.app, 'str', name_match='found')
        sync_resolution_items(self.app)
        t = self.app.resolution_items.get(code='str_claimed_no_doc')
        self.assertEqual(t.status, 'resolved')
        self.assertEqual(t.resolved_by, 'system')

    def test_no_renag_after_resolved_confirm(self):
        _add_ic(self.app, nric=self.profile.nric, name=self.profile.name,
                address='NO 1 JALAN X, 08000 SUNGAI PETANI, KEDAH')
        _add_doc(self.app, 'results_slip', student_verdict='ok', name_match='found')
        _add_doc(self.app, 'str', name_match='found')
        sync_resolution_items(self.app)
        t = self.app.resolution_items.get(code='address_state_mismatch')
        resolve_item(t, text='I live in Melaka now', by='student')
        # The verdict still flags the state mismatch, but sync must NOT re-create.
        sync_resolution_items(self.app)
        self.assertEqual(self.app.resolution_items.filter(code='address_state_mismatch').count(), 1)
        self.assertEqual(self.app.resolution_items.get(code='address_state_mismatch').status, 'resolved')


class TestResolveAndOfficer(_Base):
    def test_resolve_item_records_response(self):
        items = sync_resolution_items(self.app)
        ic = next(i for i in items if i.code == 'ic_missing')
        resolve_item(ic, text='done', by='student')
        ic.refresh_from_db()
        self.assertEqual(ic.status, 'resolved')
        self.assertEqual(ic.resolution_text, 'done')
        self.assertEqual(ic.resolved_by, 'student')

    def test_add_officer_item(self):
        t = add_officer_item(self.app, kind='explanation',
                             prompt='Please explain the gap in your income.',
                             admin_email='reviewer@x.org')
        self.assertEqual(t.source, 'officer')
        self.assertEqual(t.code, 'officer_1')
        self.assertEqual(t.created_by, 'reviewer@x.org')
        # Officer items are returned in the open queue alongside system items.
        self.assertIn('officer_1', self._codes(sync_resolution_items(self.app)))
