"""Tests for the resolution-ticket engine (Sprint 3).

Real-ORM fixtures (lesson #55). Covers generation, the mapping exclusions (the
three codes deliberately NOT ticketed), idempotency, auto-resolve on gap-clear,
the no-re-nag rule, student resolve, and officer-raised items.
"""
import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ResolutionItem, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.resolution import (
    add_officer_item, resolve_item, sync_resolution_items,
)

_TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      _TEST_JWT_SECRET, algorithm='HS256')


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
        # Check-2 gate: queries only exist AFTER the student submits their /application
        # (consent). These generation tests assume a submitted Step-4, so stamp it.
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='profile_complete',
            chosen_pathway='Matriculation', profile_completed_at=timezone.now(),
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
        # No documents → ic + results gaps (doc); the income wizard isn't walked →
        # income_earner_undeclared (confirm); pathway declared (no ticket).
        items = sync_resolution_items(self.app)
        self.assertEqual(self._codes(items),
                         ['ic_missing', 'income_earner_undeclared', 'results_slip_missing'])
        self.assertTrue(all(i.source == 'system' for i in items))

    def test_no_queries_before_consent(self):
        # Check-2 gate: a shortlisted-but-not-yet-submitted /application (no
        # profile_completed_at) has the SAME gaps, but produces NO student queries —
        # they appear only after consent. (Apply → Shortlist → Consent → Check 2 → Query.)
        self.app.status = 'shortlisted'
        self.app.profile_completed_at = None
        self.app.save(update_fields=['status', 'profile_completed_at'])
        self.assertEqual(list(sync_resolution_items(self.app)), [])
        # …and nothing was written to the table prematurely.
        self.assertEqual(self.app.resolution_items.count(), 0)

    def test_doc_ticket_carries_doc_type(self):
        items = {i.code: i for i in sync_resolution_items(self.app)}
        self.assertEqual(items['ic_missing'].doc_type, 'ic')
        self.assertEqual(items['results_slip_missing'].doc_type, 'results_slip')

    def test_address_state_divergence_makes_no_caveat_ticket(self):
        # A different-STATE IC address is NOT an identity caveat — it's a pre-interview
        # flag ("ask which is current"), so it must generate no resolution ticket.
        _add_ic(self.app, nric=self.profile.nric, name=self.profile.name,
                address='NO 1 JALAN X, 08000 SUNGAI PETANI, KEDAH')
        _add_doc(self.app, 'results_slip', student_verdict='ok', name_match='found')
        _add_doc(self.app, 'str', name_match='found')  # income verified
        codes = {i.code: i for i in sync_resolution_items(self.app)}
        self.assertNotIn('address_state_mismatch', codes)


class TestMappingExclusions(_Base):
    def test_nonticketable_codes_make_no_tickets(self):
        # ic_service_down + grades_unverified + str_present_unverified are the
        # three deliberately-excluded codes. Walk the income wizard (str/father +
        # earner IC) so income produces str_present_unverified, not the ticketable
        # income_earner_undeclared.
        self.profile.name = 'DIVASHINI A/P MURUGAN'
        self.profile.save()
        self.app.income_route = 'str'
        self.app.income_earner = 'father'
        self.app.save()
        ApplicantDocument.objects.create(
            application=self.app, doc_type='parent_ic',
            storage_path=f'{self.app.id}/parent_ic/x', vision_name='MURUGAN A/L KESAVAN',
            vision_run_at=timezone.now())
        _add_ic(self.app, error='Vision API down')                       # ic_service_down
        _add_doc(self.app, 'results_slip', student_verdict='ok', name_match='found')  # grades_unverified
        # An APPROVED + current STR (so it's NOT str_not_current) whose recipient we couldn't
        # read → the non-ticketable 'str_present_unverified'. A bare STR with no status now
        # correctly yields the ticketable 'str_not_current', so give it Lulus + year here.
        _add_doc(self.app, 'str', name_match='not_found',
                 fields={'status': 'diluluskan', 'year': '2026'})        # str_present_unverified
        self.assertEqual(sync_resolution_items(self.app), [])


class TestIdempotencyAndLifecycle(_Base):
    def test_sync_is_idempotent(self):
        sync_resolution_items(self.app)
        sync_resolution_items(self.app)
        self.assertEqual(self.app.resolution_items.filter(source='system').count(), 3)

    def test_auto_resolve_when_gap_clears(self):
        # Walk the income wizard (str/father + earner IC) → an income_proof_missing
        # gap appears until the STR is uploaded.
        self.profile.name = 'DIVASHINI A/P MURUGAN'
        self.profile.save()
        self.app.income_route = 'str'
        self.app.income_earner = 'father'
        self.app.save()
        ApplicantDocument.objects.create(
            application=self.app, doc_type='parent_ic',
            storage_path=f'{self.app.id}/parent_ic/x', vision_name='MURUGAN A/L KESAVAN',
            vision_run_at=timezone.now())
        codes = self._codes(sync_resolution_items(self.app))
        self.assertIn('income_proof_missing', codes)
        # Upload a verified STR doc → the income gap clears.
        _add_doc(self.app, 'str', name_match='found')
        sync_resolution_items(self.app)
        t = self.app.resolution_items.get(code='income_proof_missing')
        self.assertEqual(t.status, 'resolved')
        self.assertEqual(t.resolved_by, 'system')

    def test_no_renag_after_resolved_confirm(self):
        # A 'confirm' ticket whose underlying condition PERSISTS (here an NRIC mismatch —
        # the IC's number differs from the typed one) must not be re-created once the
        # student resolves it: confirm = acknowledge/explain, not fix-the-data.
        _add_ic(self.app, nric='710829-02-5709', name=self.profile.name)  # != profile.nric
        _add_doc(self.app, 'results_slip', student_verdict='ok', name_match='found')
        _add_doc(self.app, 'str', name_match='found')
        sync_resolution_items(self.app)
        t = self.app.resolution_items.get(code='nric_mismatch')
        resolve_item(t, text='The IC photo had glare; the number is correct', by='student')
        # The verdict still flags the mismatch, but sync must NOT re-create.
        sync_resolution_items(self.app)
        self.assertEqual(self.app.resolution_items.filter(code='nric_mismatch').count(), 1)
        self.assertEqual(self.app.resolution_items.get(code='nric_mismatch').status, 'resolved')


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


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=_TEST_JWT_SECRET)
class TestStudentQueueViewGate(TestCase):
    """The STUDENT /scholarship/resolution-items endpoint must show NOTHING until the
    /application is submitted (consent) — even for tickets already in the DB. This is
    the regression test for the Deploy-3 miss (the engine was gated but the VIEW queried
    items directly). Either/or: form before submit, queries after."""
    URL = '/api/v1/scholarship/resolution-items/'

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()
        self.profile = StudentProfile.objects.create(supabase_user_id='res-view-stu', nric='030101-14-1234', name='Stu')
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted')
        # Two tickets already in the DB (as if generated prematurely under old behaviour).
        for code, fact in (('ic_missing', 'identity'), ('results_slip_missing', 'academic')):
            ResolutionItem.objects.create(application=self.app, source='system', code=code,
                                          fact=fact, kind='doc', status='open')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("res-view-stu")}')

    def test_no_queries_before_submission_even_with_existing_tickets(self):
        # profile_completed_at is None → the queue is hidden (form-only state).
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['open'], [])
        self.assertEqual(r.json()['resolved'], [])

    def test_queries_appear_after_submission(self):
        self.app.profile_completed_at = timezone.now()
        self.app.status = 'profile_complete'
        self.app.save(update_fields=['profile_completed_at', 'status'])
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200)
        codes = sorted(i['code'] for i in r.json()['open'])
        self.assertIn('ic_missing', codes)
        self.assertIn('results_slip_missing', codes)
