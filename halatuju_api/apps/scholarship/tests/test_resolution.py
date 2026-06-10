"""Tests for the resolution-ticket engine (Sprint 3).

Real-ORM fixtures (lesson #55). Covers generation, the mapping exclusions (the
three codes deliberately NOT ticketed), idempotency, auto-resolve on gap-clear,
the no-re-nag rule, student resolve, and officer-raised items.
"""
import jwt
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ResolutionItem, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.resolution import (
    add_officer_item, resolve_item, sync_resolution_items,
    doc_match_verdict, resolve_doc_items_for_upload,
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
        # No documents → ic + results + offer gaps (doc); the income wizard isn't walked
        # → income_earner_undeclared (confirm). The offer letter is now compulsory, so a
        # bare app also raises offer_letter_missing.
        items = sync_resolution_items(self.app)
        self.assertEqual(self._codes(items),
                         ['ic_missing', 'income_earner_undeclared', 'offer_letter_missing',
                          'results_slip_missing'])
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
        # The three excluded codes raise NO tickets (the compulsory-offer gap is its own
        # separate, ticketable matter — assert the exclusions specifically, not emptiness).
        codes = self._codes(sync_resolution_items(self.app))
        for excluded in ('ic_service_down', 'grades_unverified', 'str_present_unverified'):
            self.assertNotIn(excluded, codes)


class TestIdempotencyAndLifecycle(_Base):
    def test_sync_is_idempotent(self):
        sync_resolution_items(self.app)
        sync_resolution_items(self.app)
        # ic_missing + results_slip_missing + offer_letter_missing + income_earner_undeclared.
        self.assertEqual(self.app.resolution_items.filter(source='system').count(), 4)

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

    def test_system_verdict_items_not_shown_to_student(self):
        # The student's queue shows ONLY deliberately-raised items (officer/AI) —
        # never the system's own verdict gaps (those live on the officer cockpit, so a
        # mismatched upload can't spawn a duplicate system ticket beside the reviewer
        # task + Gopal's coach).
        self.app.profile_completed_at = timezone.now()
        self.app.status = 'profile_complete'
        self.app.save(update_fields=['profile_completed_at', 'status'])
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200)
        codes = [i['code'] for i in r.json()['open']]
        self.assertNotIn('ic_missing', codes)
        self.assertNotIn('results_slip_missing', codes)
        # …but an officer-raised request DOES show.
        add_officer_item(self.app, kind='doc', prompt='Upload your IC',
                         admin_email='o@x', doc_type='ic')
        codes2 = [i['code'] for i in self.client.get(self.URL).json()['open']]
        self.assertIn('officer_1', codes2)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=_TEST_JWT_SECRET,
                   CHECK2_STUDENT_QUERIES_ENABLED=True)
class TestCheck2QueriesInStudentQueue(TestCase):
    """Check 2 STEP 2: AI clarify queries surface in the student Action Centre;
    reviewer-only 'human' items never do; the student can answer a clarify by text."""
    URL = '/api/v1/scholarship/resolution-items/'

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()
        self.profile = StudentProfile.objects.create(
            supabase_user_id='c2-stu', nric='030101-14-1234', name='Stu',
            household_income=1200, household_size=5)
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='profile_complete',
            profile_completed_at=timezone.now(),
            aspirations='I want to teach.', field_of_study='Education',
            siblings_in_tertiary=0,
            chosen_pathway='stpm', pathway_certainty='sure')  # STPM → transport asked
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("c2-stu")}')

    def test_clarify_query_shows_but_human_hidden(self):
        ResolutionItem.objects.create(
            application=self.app, source='check2', code='human_award_sizing',
            fact='income', kind='human', status='open')
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200)
        codes = {i['code'] for i in r.json()['open']}
        # device + transport clarify queries are generated; the human item is hidden.
        self.assertIn('transport_cost_unknown', codes)
        self.assertNotIn('human_award_sizing', codes)

    def test_student_can_answer_a_clarify(self):
        self.client.get(self.URL)  # generates the clarify queries
        item = self.app.resolution_items.get(code='transport_cost_unknown')
        r = self.client.post(f'{self.URL}{item.id}/resolve/', {'text': 'Bus, ~RM80/month.'},
                             format='json')
        self.assertEqual(r.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')
        self.assertEqual(item.resolution_text, 'Bus, ~RM80/month.')
        self.assertEqual(item.resolved_by, 'student')

    def test_clarify_requires_text(self):
        self.client.get(self.URL)
        item = self.app.resolution_items.get(code='transport_cost_unknown')
        r = self.client.post(f'{self.URL}{item.id}/resolve/', {'text': ''}, format='json')
        self.assertEqual(r.status_code, 400)

    @override_settings(CHECK2_STUDENT_QUERIES_ENABLED=False)
    def test_clarify_hidden_from_student_when_flag_off(self):
        # Held: no clarify queries shown to the student, and none are even created.
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200)
        codes = {i['code'] for i in r.json()['open']}
        self.assertNotIn('transport_cost_unknown', codes)
        self.assertNotIn('sibling_level_unknown', codes)
        self.assertFalse(
            self.app.resolution_items.filter(source='check2', kind='clarify').exists())


class TestDocMatchVerdict(_Base):
    """The Action Centre's per-document accept/keep-open verdict (Phase 1). Only a
    CONFIRMED mismatch or an UNREADABLE scan keeps a task open; uncertain / soft /
    pending are accepted (D1). Engines are patched — the reduction logic is what's tested."""

    def _doc(self, doc_type, **kw):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type=doc_type, storage_path=f'{self.app.id}/{doc_type}/x', **kw)

    def test_results_slip_name_mismatch(self):
        doc = self._doc('results_slip')
        with patch('apps.scholarship.academic_engine.student_slip_check',
                   return_value={'name': 'mismatch'}):
            self.assertEqual(doc_match_verdict(doc), 'mismatch')

    def test_results_slip_grades_mismatch(self):
        doc = self._doc('results_slip')
        with patch('apps.scholarship.academic_engine.student_slip_check',
                   return_value={'name': 'match', 'subjects': 'match', 'results': 'mismatch'}):
            self.assertEqual(doc_match_verdict(doc), 'mismatch')

    def test_results_slip_unreadable(self):
        doc = self._doc('results_slip')
        with patch('apps.scholarship.academic_engine.student_slip_check',
                   return_value={'name': 'unreadable'}):
            self.assertEqual(doc_match_verdict(doc), 'unreadable')

    def test_results_slip_clean_ok(self):
        doc = self._doc('results_slip')
        with patch('apps.scholarship.academic_engine.student_slip_check',
                   return_value={'name': 'match', 'subjects': 'match', 'results': 'match'}):
            self.assertEqual(doc_match_verdict(doc), 'ok')

    def test_results_slip_uncertain_is_accepted(self):
        # An uncertain grade goes to the reviewer — we accept the upload (D1).
        doc = self._doc('results_slip')
        with patch('apps.scholarship.academic_engine.student_slip_check',
                   return_value={'name': 'match', 'subjects': 'match', 'results': 'uncertain'}):
            self.assertEqual(doc_match_verdict(doc), 'ok')

    def test_str_rejected_is_mismatch(self):
        doc = self._doc('str')
        with patch('apps.scholarship.income_engine.student_str_check',
                   return_value={'name_status': 'match', 'nric_status': 'match', 'current_status': 'rejected'}):
            self.assertEqual(doc_match_verdict(doc), 'mismatch')

    def test_str_current_ok(self):
        doc = self._doc('str')
        with patch('apps.scholarship.income_engine.student_str_check',
                   return_value={'name_status': 'match', 'nric_status': 'match', 'current_status': 'current'}):
            self.assertEqual(doc_match_verdict(doc), 'ok')

    def test_birth_certificate_mother_mismatch(self):
        doc = self._doc('birth_certificate')
        with patch('apps.scholarship.income_engine.student_bc_check',
                   return_value={'child_status': 'match', 'mother_status': 'mismatch', 'father_status': 'match'}):
            self.assertEqual(doc_match_verdict(doc), 'mismatch')

    def test_birth_certificate_clean_ok(self):
        doc = self._doc('birth_certificate')
        with patch('apps.scholarship.income_engine.student_bc_check',
                   return_value={'child_status': 'match', 'mother_status': 'match', 'father_status': 'match'}):
            self.assertEqual(doc_match_verdict(doc), 'ok')

    def test_parent_ic_name_mismatch(self):
        doc = self._doc('parent_ic', vision_run_at=timezone.now())
        with patch('apps.scholarship.income_engine.student_income_ic_check',
                   return_value={'name_status': 'mismatch', 'readable': True}):
            self.assertEqual(doc_match_verdict(doc), 'mismatch')

    def test_utility_always_ok(self):
        self.assertEqual(doc_match_verdict(self._doc('water_bill')), 'ok')

    def test_unknown_doc_type_ok(self):
        self.assertEqual(doc_match_verdict(self._doc('photo')), 'ok')


class TestResolveDocItemsForUpload(_Base):
    """A clean upload resolves the matching OPEN doc task (the officer-doc bug fix);
    a mismatch leaves it open; it never touches other doc types or non-doc items."""

    def _doc(self, doc_type):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type=doc_type, storage_path=f'{self.app.id}/{doc_type}/x')

    def test_clean_upload_resolves_officer_doc_item(self):
        item = add_officer_item(self.app, kind='doc', prompt='Upload your BC',
                                admin_email='o@x', doc_type='birth_certificate')
        doc = self._doc('birth_certificate')
        with patch('apps.scholarship.resolution.doc_match_verdict', return_value='ok'):
            self.assertEqual(resolve_doc_items_for_upload(self.app, doc), 'ok')
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')
        self.assertEqual(item.resolution_doc_id, doc.id)

    def test_mismatch_keeps_officer_doc_item_open(self):
        item = add_officer_item(self.app, kind='doc', prompt='Upload your BC',
                                admin_email='o@x', doc_type='birth_certificate')
        doc = self._doc('birth_certificate')
        with patch('apps.scholarship.resolution.doc_match_verdict', return_value='mismatch'):
            self.assertEqual(resolve_doc_items_for_upload(self.app, doc), 'mismatch')
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')

    def test_only_matching_doc_type_resolves(self):
        bc = add_officer_item(self.app, kind='doc', prompt='BC', admin_email='o@x',
                              doc_type='birth_certificate')
        slip = add_officer_item(self.app, kind='doc', prompt='Slip', admin_email='o@x',
                                doc_type='salary_slip')
        doc = self._doc('birth_certificate')
        with patch('apps.scholarship.resolution.doc_match_verdict', return_value='ok'):
            resolve_doc_items_for_upload(self.app, doc)
        bc.refresh_from_db(); slip.refresh_from_db()
        self.assertEqual(bc.status, 'resolved')
        self.assertEqual(slip.status, 'open')

    def test_does_not_touch_explanation_items(self):
        q = add_officer_item(self.app, kind='explanation', prompt='How do you travel?',
                             admin_email='o@x')
        doc = self._doc('birth_certificate')
        with patch('apps.scholarship.resolution.doc_match_verdict', return_value='ok'):
            resolve_doc_items_for_upload(self.app, doc)
        q.refresh_from_db()
        self.assertEqual(q.status, 'open')
