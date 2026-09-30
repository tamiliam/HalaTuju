"""TD-309 — the Documents page OFFERS the IC that settles whose STR it is (owner: option 1).

**What changed.** The STR document's served ``str_check`` gains ``ic_slots`` —
``{'missing': [...], 'unreadable': [...]}``, the roster members whose IC would settle a
cannot-judge STR — so the income wizard can offer a ``parent_ic`` card tagged to each of them
BEFORE submission. The submission gate is untouched.

**One rule, two readers.** ``str_ic_slots(sc, application)`` is the body ``str_owner_ic_asks`` used
to hold; the Check-2 ASK (``str_owner_ic_asks``) and the Documents-page OFFER
(``student_str_payload``) both read it (TD-262 F2 lesson: a demand and an offer that read the same
fact must be one reading). These tests pin that they agree, that the offer costs no query, and that
the server-only ``ic_read_members`` still never reaches the student.

Personal data is obviously fake.
"""
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.scholarship import income_engine
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.income_str_ownership import (
    _latest_str_check, str_ic_slots, str_owner_ic_asks, student_str_payload)
from apps.scholarship.tests.factories import make_application, make_cohort, make_student
from apps.scholarship.tests.test_documents import TEST_JWT_SECRET, _token
from apps.scholarship.tests.test_income_evidence_homes import (
    FATHER_NAME, FATHER_NRIC, STUDENT_NAME, _doc, _str_doc)

MOTHER_NAME = 'Kamala A/P Suppiah'
MOTHER_NRIC = '750808-14-5002'
STRANGER_NAME = 'Roslan Bin Ahmad'
STRANGER_NRIC = '880808-10-5533'

_MOTHERS_STR = dict(recipient_name=MOTHER_NAME, recipient_nric=MOTHER_NRIC)
_FATHERS_STR = dict(recipient_name=FATHER_NAME, recipient_nric=FATHER_NRIC)
_STRANGERS_STR = dict(recipient_name=STRANGER_NAME, recipient_nric=STRANGER_NRIC)
_NONE = {'missing': [], 'unreadable': []}

#: The Check-2 ask codes (``check2_queries._STR_IC_CODE``), spelt out so a rename is noticed.
_ASK_CODES = frozenset(f'{m}_ic_for_str_{k}'
                       for m in ('father', 'mother', 'guardian', 'brother', 'sister')
                       for k in ('missing', 'unreadable'))

#: ``shape -> (the STR's recipient, the ICs on file as (member, name read, nric read))``.
SHAPES = {
    # (a) the owner's own example: the mother's STR, only the father's IC on file
    'mother_missing': (_MOTHERS_STR, (('father', FATHER_NAME, FATHER_NRIC),)),
    # (b) the same, the mother's IC IS on file but nothing on it read
    'mother_unreadable': (_MOTHERS_STR, (('father', FATHER_NAME, FATHER_NRIC),
                                         ('mother', '', ''))),
    # (c) the family's own STR — it matches the father's IC
    'own': (_FATHERS_STR, (('father', FATHER_NAME, FATHER_NRIC),)),
    # (d) a TRUE stranger — every roster member's IC is on file and read, none matches
    'true_stranger': (_STRANGERS_STR, (('father', FATHER_NAME, FATHER_NRIC),
                                       ('mother', MOTHER_NAME, MOTHER_NRIC))),
}
EXPECTED = {
    'mother_missing': {'missing': ['mother'], 'unreadable': []},
    'mother_unreadable': {'missing': [], 'unreadable': ['mother']},
    'own': _NONE,
    'true_stranger': _NONE,
}


class StrIcSlotsBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(year=2026)

    def build(self, shape, *, route='str', state='submitted', student=None):
        """A household whose roster is {father, mother}: a private-sector father and a homemaker
        mother, the STR route's declared earner the father (or the father ticked, salary)."""
        str_kw, ics = SHAPES[shape] if shape else (None, (('father', FATHER_NAME, FATHER_NRIC),))
        app = make_application(
            state, cohort=self.cohort, student=student or make_student(name=STUDENT_NAME),
            income_route=route,
            income_earner='father' if route == 'str' else '',
            income_working_members=['father'] if route == 'salary' else [],
            father_name=FATHER_NAME, father_occupation='private',
            mother_name=MOTHER_NAME, mother_occupation='homemaker',
            other_family_members=[], siblings_in_school=0, siblings_in_tertiary=0)
        for member, name, nric in ics:
            _doc(app, 'parent_ic', member, name=name, nric=nric)
        if str_kw is not None:
            _str_doc(app, **str_kw)
        return app


class TestServedSlots(StrIcSlotsBase):
    """(a)–(f): what the student payload carries."""

    def test_each_shape_serves_the_members_whose_ic_would_settle_it(self):
        for shape, want in EXPECTED.items():
            for route in ('str', 'salary'):
                with self.subTest(shape=shape, route=route):
                    app = self.build(shape, route=route)
                    payload = student_str_payload(app.documents.get(doc_type='str'))
                    self.assertEqual(payload['ic_slots'], want)

    def test_mothers_str_with_only_fathers_ic_offers_her_ic_as_missing(self):
        """(a) the owner's own example."""
        app = self.build('mother_missing')
        payload = student_str_payload(app.documents.get(doc_type='str'))
        self.assertEqual(payload['ic_slots'], {'missing': ['mother'], 'unreadable': []})

    def test_her_ic_on_file_but_unread_is_offered_as_unreadable(self):
        """(b) never tell a student an IC she uploaded is "not on file" (review F-C)."""
        app = self.build('mother_unreadable')
        payload = student_str_payload(app.documents.get(doc_type='str'))
        self.assertEqual(payload['ic_slots'], {'missing': [], 'unreadable': ['mother']})

    def test_no_str_and_a_non_str_doc_serve_no_str_check(self):
        """(e)"""
        app = self.build(None)
        ic = app.documents.get(doc_type='parent_ic')
        self.assertIsNone(student_str_payload(ic))
        self.assertIsNone(_latest_str_check(app))
        self.assertEqual(str_ic_slots(None, app), _NONE)
        self.assertEqual(str_owner_ic_asks(app), _NONE)

    def test_the_payload_is_the_str_check_minus_the_server_only_field_plus_the_slots(self):
        """(f) ``ic_read_members`` is server-side only; everything else is the reading as it was."""
        app = self.build('mother_missing')
        doc = app.documents.get(doc_type='str')
        payload = student_str_payload(doc)
        self.assertNotIn('ic_read_members', payload)
        sc = income_engine.student_str_check(doc)
        del sc['ic_read_members']
        self.assertEqual({k: v for k, v in payload.items() if k != 'ic_slots'}, sc)


class TestOneRuleTwoReaders(StrIcSlotsBase):
    """(g) the Check-2 ASK and the Documents-page OFFER are the same function."""

    def test_the_ask_is_the_offer_on_every_shape(self):
        for shape in SHAPES:
            with self.subTest(shape=shape):
                app = self.build(shape)
                self.assertEqual(str_owner_ic_asks(app),
                                 str_ic_slots(_latest_str_check(app), app))
                self.assertEqual(
                    str_owner_ic_asks(app),
                    student_str_payload(app.documents.get(doc_type='str'))['ic_slots'])

    def test_check2_raises_exactly_the_offered_members(self):
        from apps.scholarship.check2_queries import _gap_sets
        for shape in ('mother_missing', 'mother_unreadable', 'own'):
            with self.subTest(shape=shape):
                app = self.build(shape, state='profile_complete')
                slots = student_str_payload(app.documents.get(doc_type='str'))['ic_slots']
                gaps, proof = _gap_sets(app)
                raised = (gaps | proof) & _ASK_CODES
                self.assertEqual(raised, {f'{m}_ic_for_str_{k}'
                                          for k, members in slots.items() for m in members})


class TestNoExtraQuery(StrIcSlotsBase):
    """(h) the offer is PURE: serving it costs exactly what the reading already cost (TD-285: a
    shared predicate needs its own budget)."""

    def _count(self, fn, doc_id):
        from apps.scholarship.models import ApplicantDocument
        doc = ApplicantDocument.objects.select_related('application').get(pk=doc_id)
        with CaptureQueriesContext(connection) as ctx:
            fn(doc)
        return len(ctx.captured_queries)

    def test_the_payload_costs_the_same_queries_as_the_reading(self):
        for shape in SHAPES:
            with self.subTest(shape=shape):
                app = self.build(shape)
                doc_id = app.documents.get(doc_type='str').id
                self.assertEqual(self._count(student_str_payload, doc_id),
                                 self._count(income_engine.student_str_check, doc_id))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestDocumentsEndpoint(StrIcSlotsBase):
    """(i) the student's own ``GET /documents/`` carries the slots on the STR row."""

    def test_the_students_documents_payload_carries_ic_slots(self):
        uid = 'td309-student'
        student = make_student(name=STUDENT_NAME, supabase_user_id=uid, nric='030101-14-7777')
        self.build('mother_missing', state='shortlisted', student=student)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        resp = client.get('/api/v1/scholarship/documents/')
        self.assertEqual(resp.status_code, 200)
        rows = {d['doc_type']: d for d in resp.json()['documents']}
        self.assertEqual(rows['str']['str_check']['ic_slots'],
                         {'missing': ['mother'], 'unreadable': []})
        self.assertNotIn('ic_read_members', rows['str']['str_check'])
        self.assertIsNone(rows['parent_ic']['str_check'])

    def test_a_superseded_str_never_reaches_the_student_so_the_webs_latest_is_the_live_one(self):
        """Review F5. The web picks "the latest STR" from the student GET by `uploaded_at`, which
        mirrors `latest_doc` only because that payload is LIVE-ONLY. Pin it: a superseded STR newer
        than the live one — with DIFFERENT slots — is not served, so the web cannot pick it."""
        from datetime import timedelta
        from django.utils import timezone
        uid = 'td309-f5'
        student = make_student(name=STUDENT_NAME, supabase_user_id=uid, nric='030101-14-5555')
        app = self.build('own', state='shortlisted', student=student)          # live STR: settled
        live = app.documents.get(doc_type='str')
        old = _str_doc(app, **_MOTHERS_STR)                        # would name the mother
        ApplicantDocument.objects.filter(id=old.id).update(
            superseded_at=timezone.now(), uploaded_at=live.uploaded_at + timedelta(hours=1))
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        rows = [d for d in client.get('/api/v1/scholarship/documents/').json()['documents']
                if d['doc_type'] == 'str']
        self.assertEqual([d['id'] for d in rows], [live.id])
        self.assertEqual(rows[0]['str_check']['ic_slots'], _NONE)

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.vision.run_field_extraction_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_only_an_ic_escapes_the_pre_consent_force_tag(self, *_):
        """Review F2: the exemption is for the IC card TD-309 offers, and nothing else. Pre-consent
        on the STR route, an `str`, `salary_slip` or `epf` POSTed with a non-earner tag is still
        force-tagged to the earner — else a mother-tagged STR could become THE STR for the gate and
        Check 2 while the page has no card for it. A `parent_ic` keeps the tag it was sent."""
        uid = 'td309-f2'
        student = make_student(name=STUDENT_NAME, supabase_user_id=uid, nric='030101-14-6666')
        app = self.build('mother_missing', state='shortlisted', student=student)
        self.assertIsNone(app.profile_completed_at)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        for doc_type, want in (('parent_ic', 'mother'), ('str', 'father'),
                               ('salary_slip', 'father'), ('epf', 'father')):
            with self.subTest(doc_type=doc_type):
                resp = client.post('/api/v1/scholarship/documents/', {
                    'doc_type': doc_type, 'household_member': 'mother',
                    'storage_path': f'{app.id}/{doc_type}/m', 'original_filename': 'm.pdf',
                    'size': 1000,
                }, format='json')
                self.assertEqual(resp.status_code, 201, resp.content)
                self.assertEqual(
                    ApplicantDocument.objects.get(id=resp.json()['id']).household_member, want)

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.vision.run_field_extraction_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_the_offered_ic_card_uploads_under_her_name_without_touching_the_earners_ic(self, *_):
        """The card the page now offers must actually TAKE her IC. Before consent the STR route
        force-tags its income documents to the declared earner (TD-115), which — applied to an IC
        the student explicitly tagged to the mother — would file it as the FATHER's and supersede
        his IC. An explicit non-earner tag on a `parent_ic` (and only a `parent_ic` — see
        `test_only_an_ic_escapes_the_pre_consent_force_tag`) is honoured instead."""
        uid = 'td309-uploader'
        student = make_student(name=STUDENT_NAME, supabase_user_id=uid, nric='030101-14-8888')
        app = self.build('mother_missing', state='shortlisted', student=student)
        self.assertIsNone(app.profile_completed_at)                  # PRE-consent: the force-tag window
        fathers_ic = app.documents.get(doc_type='parent_ic', household_member='father')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        resp = client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'parent_ic', 'household_member': 'mother',
            'storage_path': f'{app.id}/parent_ic/mother', 'original_filename': 'm.pdf', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(ApplicantDocument.objects.get(id=resp.json()['id']).household_member, 'mother')
        fathers_ic.refresh_from_db()
        self.assertIsNone(fathers_ic.superseded_at)                   # his IC is untouched
        # ...and the earner's own card still force-tags as before (a blank tag lands on him)
        resp = client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'parent_ic', 'storage_path': f'{app.id}/parent_ic/blank',
            'original_filename': 'f.pdf', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(ApplicantDocument.objects.get(id=resp.json()['id']).household_member, 'father')
