"""Document chip standard S0: the server chips reproduce today's officer-drawer colours exactly.

The parity fixture is shared with the web (``halatuju-web/src/lib/__tests__/doc-chip-parity.test.ts``
runs today's web functions over the SAME cases), so the two sides can only agree or both go red.
"""
import datetime
import json
import pathlib
from unittest import mock

from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.scholarship import doc_chips, doc_chips_student
from apps.scholarship.serializers import documents as documents_ser
from apps.scholarship.serializers import ApplicantDocumentSerializer
from apps.scholarship.sgd_conversion import AdminApplicantDocumentSerializer
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, create_document, make_admin, make_application, make_cohort,
)

FIXTURE = pathlib.Path(__file__).resolve().parent / 'fixtures' / 'doc_chip_parity.json'
CHIP_KEYS = {'key', 'status', 'state', 'student_action', 'reason', 'kind'}


def _cases():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))['cases']


class ParityFixtureTests(SimpleTestCase):
    def test_the_fixture_is_big_enough_and_covers_every_scored_type(self):
        cases = _cases()
        self.assertGreaterEqual(len(cases), 70)
        types = {c['doc']['doc_type'] for c in cases}
        for dt in ('ic', 'parent_ic', 'results_slip', 'higher_results', 'offer_letter', 'str', 'salary_slip',
                   'epf', 'birth_certificate', 'guardianship_letter', 'semester_result', 'school_leaving_cert',
                   'income_support_doc', 'water_bill', 'electricity_bill'):
            self.assertIn(dt, types)
        self.assertEqual(len({c['name'] for c in cases}), len(cases), 'case names must be unique')

    def test_chips_for_matches_every_case(self):
        for case in _cases():
            with self.subTest(case['name']):
                got = doc_chips.chips_for(case['doc'])
                trimmed = [{k: c[k] for k in ('key', 'status', 'state', 'kind', 'value') if k in c} for c in got]
                self.assertEqual(trimmed, case['chips'])
                # The fixture pill is TODAY's web (no Problem). The one change: a red fact chip is 'problem'.
                red = any(c['state'] == 'red' and c['kind'] == 'fact' for c in case['chips'])
                want = 'problem' if case['pill'] == 'check' and red else case['pill']
                self.assertEqual(doc_chips.pill_for(got), want)

    def test_every_chip_has_the_standard_shape(self):
        for case in _cases():
            for chip in doc_chips.chips_for(case['doc']):
                with self.subTest(case['name'], key=chip['key']):
                    want = CHIP_KEYS | ({'value'} if chip['kind'] in ('year', 'plain') else set())
                    self.assertEqual(set(chip), want)
                    self.assertEqual(chip['student_action'], 'none')          # Sprint 0: nothing asked yet
                    self.assertIn(chip['student_action'], doc_chips.STUDENT_ACTIONS)
                    self.assertEqual(chip['state'], doc_chips.STATES[chip['status']])
                    self.assertIn(chip['kind'], ('fact', 'year', 'plain'))
                    self.assertIsInstance(chip['reason'], str)


class PillTests(SimpleTestCase):
    def chip(self, state, kind='fact'):
        return {'key': 'k', 'state': state, 'kind': kind}

    def test_no_chips_or_only_grey_is_unread(self):
        self.assertEqual(doc_chips.pill_for([]), 'unread')
        self.assertEqual(doc_chips.pill_for([self.chip('grey'), self.chip('grey')]), 'unread')

    def test_year_chips_never_count(self):
        self.assertEqual(doc_chips.pill_for([self.chip('amber', 'year')]), 'unread')
        self.assertEqual(doc_chips.pill_for([self.chip('green'), self.chip('amber', 'year')]), 'verified')

    def test_all_green_is_verified_and_any_amber_or_red_is_check(self):
        self.assertEqual(doc_chips.pill_for([self.chip('green'), self.chip('grey')]), 'verified')
        self.assertEqual(doc_chips.pill_for([self.chip('green'), self.chip('amber')]), 'check')
        self.assertEqual(doc_chips.pill_for([self.chip('red')]), 'problem')
        self.assertEqual(doc_chips.pill_for([self.chip('red'), self.chip('amber')]), 'problem')
        self.assertEqual(doc_chips.pill_for([self.chip('green'), self.chip('red')]), 'problem')

    def test_a_red_year_chip_alone_is_not_a_problem(self):
        self.assertEqual(doc_chips.pill_for([self.chip('green'), self.chip('red', 'year')]), 'verified')
        self.assertEqual(doc_chips.pill_for([self.chip('red', 'year')]), 'unread')


_JUNK = (['match'], {'status': 'match'}, 5, 3.5, True, 'x', None, [], {}, [{'key': 'amount'}])
_CHECK_KEYS = {
    'parent_ic': 'income_ic_check', 'results_slip': 'academic_check', 'higher_results': 'higher_check',
    'offer_letter': 'pathway_check', 'str': 'str_check', 'salary_slip': 'income_proof_check',
    'epf': 'income_proof_check', 'birth_certificate': 'bc_check', 'guardianship_letter': 'guardianship_check',
    'semester_result': 'semester_check', 'school_leaving_cert': 'school_leaving_check',
    'income_support_doc': 'support_doc_check', 'water_bill': 'utility_check', 'electricity_bill': 'utility_check',
}
_FIELDS = (
    'name', 'ic', 'nric', 'name_status', 'nric_status', 'display_name_status', 'display_nric_status',
    'current_status', 'readable', 'wrong_card', 'display_wrong_card', 'member', 'higher_kind', 'subjects',
    'results', 'kind_status', 'cgpa', 'cgpa_status', 'grades_status', 'pathway', 'pathway_set_by_offer',
    'reporting_date', 'switched_from', 'points', 'unreadable', 'child_status', 'mother_status',
    'display_mother_status', 'father_status', 'guardian_status', 'ward_status', 'kelakuan_status',
    'school_status', 'read_status', 'amount', 'address_status', 'reasonable_status', 'outstanding_status',
    'exam_year', 'exam_year_status', 'intake_year', 'intake_year_status',
)


class JunkPayloadTests(SimpleTestCase):
    """Review finding 1: a junk value (a list or dict where a status word should be) never raises."""

    def test_no_junk_value_anywhere_raises(self):
        for dt in ('ic', 'photo', *_CHECK_KEYS):
            for junk in _JUNK:
                docs = [
                    {'doc_type': dt, _CHECK_KEYS.get(dt, 'x_check'): junk, 'authenticity': junk},
                    {'doc_type': dt, 'vision_name_verdict': junk, 'vision_nric_verdict': junk,
                     'authenticity': {'status': junk}, 'vision_fields': {'student_verdict': junk},
                     'figure_refused': junk, _CHECK_KEYS.get(dt, 'x_check'): {
                         **{k: junk for k in _FIELDS}, 'points': [{'key': junk, 'value': junk}, junk]}},
                ]
                for doc in docs:
                    with self.subTest(dt, junk=repr(junk)):
                        chips = doc_chips.chips_for(doc)
                        self.assertIn(doc_chips.pill_for(chips), doc_chips.PILLS)
                        for chip in chips:
                            self.assertEqual(chip['state'], doc_chips.STATES[chip['status']])

    def test_a_payload_that_is_not_a_dict_has_no_chips(self):
        for junk in _JUNK:
            with self.subTest(junk=repr(junk)):
                self.assertEqual(doc_chips.chips_for(junk), [])


class WhereTheWebThrowsTests(SimpleTestCase):
    """Finding 4: where today's web would THROW, the server picks a quiet answer. These stay out of the
    shared parity fixture (the jest half cannot run them)."""

    def keys(self, doc):
        return [(c['key'], c['state']) for c in doc_chips.chips_for(doc)]

    def test_a_check_that_is_not_a_dict_is_no_check(self):
        self.assertEqual(self.keys({'doc_type': 'semester_result', 'semester_check': ['x']}), [])
        self.assertEqual(self.keys({'doc_type': 'str', 'str_check': 'x'}), [])

    def test_only_strings_are_trimmed(self):          # the web: (500 || '').trim() throws
        self.assertEqual(self.keys({'doc_type': 'income_support_doc',
                                    'support_doc_check': {'read_status': 'read', 'amount': 500}}),
                         [('evidence', 'green')])
        self.assertEqual(self.keys({'doc_type': 'semester_result', 'semester_check': {
            'name_status': 'match', 'nric_status': 'match', 'cgpa': 3.5}})[-1], ('cgpa', 'grey'))

    def test_points_that_are_not_a_list_read_as_none(self):   # the web: {}.some throws
        doc = {'doc_type': 'salary_slip', 'income_proof_check': {'name_status': 'match',
                                                                 'points': {'key': 'amount', 'value': '9'}}}
        self.assertEqual(self.keys(doc), [('name', 'green'), ('amount', 'grey'), ('period', 'grey')])

    def test_n5_a_year_counts_only_when_it_is_a_str_or_an_int(self):
        """The web would draw a junk year as text ("true"); the server serves a str or an int only."""
        for year, want in (('2025', '2025'), (2025, '2025'), (True, None), (2025.0, None),
                           ({'y': 2025}, None), (['2025'], None), ('', None), (0, None)):
            with self.subTest(year=repr(year)):
                yc = doc_chips.year_chip({'doc_type': 'results_slip',
                                          'academic_check': {'exam_year': year, 'exam_year_status': 'current'}})
                self.assertEqual(yc and yc['value'], want)

    def test_a_genuineness_word_that_is_not_a_string_is_amber(self):   # the web: [].startsWith throws
        doc = {'doc_type': 'ic', 'vision_name_verdict': 'match', 'vision_nric_verdict': 'match',
               'authenticity': {'status': ['not_ic']}}
        self.assertEqual(self.keys(doc), [('name', 'green'), ('ic_no', 'green'), ('genuine', 'amber')])


class ServedPayloadTests(TestCase):
    def setUp(self):
        self.app = make_application()
        documents_ser._CHIP_FALLBACK_LOGGED.clear()      # the log-once memory is per process

    def doc(self, doc_type, **kw):
        return create_document(self.app, doc_type, storage_path='s', **kw)

    def test_student_and_admin_payloads_carry_the_three_keys(self):
        """S1 audience split: the student's payload serves the STUDENT chips, the officer's the
        OFFICER chips, under the same three keys."""
        d = self.doc('ic', vision_run_at=timezone.now())
        for serializer, module in ((ApplicantDocumentSerializer, doc_chips_student),
                                   (AdminApplicantDocumentSerializer, doc_chips)):
            with self.subTest(serializer.__name__):
                data = serializer(d).data
                for key in ('chips', 'chip_pill', 'read_at'):
                    self.assertIn(key, data)
                self.assertEqual(data['chips'], module.chips_for(data))
                self.assertEqual(data['chip_pill'], module.pill_for(data['chips']))
                self.assertTrue(data['chips'])

    def test_the_student_payload_carries_no_officer_chip_word(self):
        """The S0 exposure note, closed: no officer-only key reaches the student's chips."""
        d = self.doc('ic', vision_run_at=timezone.now())
        student = ApplicantDocumentSerializer(d).data['chips']
        officer = AdminApplicantDocumentSerializer(d).data['chips']
        self.assertEqual([c['key'] for c in student], ['icNo', 'name'])
        self.assertEqual([c['key'] for c in officer], ['name', 'ic_no'])
        self.assertTrue(all('label' in c for c in student))
        self.assertFalse(any('label' in c for c in officer))

    def test_an_unread_ic_serves_two_grey_chips_and_unread(self):
        d = self.doc('ic')
        data = AdminApplicantDocumentSerializer(d).data
        self.assertEqual([(c['key'], c['state']) for c in data['chips']], [('name', 'grey'), ('ic_no', 'grey')])
        self.assertEqual(data['chip_pill'], 'unread')
        self.assertIsNone(data['read_at'])
        student = ApplicantDocumentSerializer(d).data                 # the student sees no checklist yet
        self.assertEqual((student['chips'], student['chip_pill']), ([], 'unread'))

    def test_read_at_is_the_later_of_the_two_read_stamps(self):
        early = timezone.make_aware(datetime.datetime(2026, 11, 1, 9, 0))
        late = timezone.make_aware(datetime.datetime(2026, 11, 2, 9, 0))
        field = ApplicantDocumentSerializer().fields['vision_run_at']
        for label, run_at, fields_run_at, want in (('fields later', early, late, late),
                                                   ('vision later', late, early, late),
                                                   ('vision only', early, None, early),
                                                   ('fields only', None, late, late)):
            with self.subTest(label):                       # a str label: xdist cannot ship a datetime
                d = self.doc('photo', vision_run_at=run_at, vision_fields_run_at=fields_run_at)
                self.assertEqual(ApplicantDocumentSerializer(d).data['read_at'], field.to_representation(want))
                d.delete()

    def test_a_junk_check_through_the_serializer_never_raises(self):
        junk = {'name': ['match'], 'subjects': {'k': 'match'}, 'results': 5, 'higher_kind': [],
                'exam_year': ['2025'], 'exam_year_status': {'a': 1}}
        with mock.patch.object(ApplicantDocumentSerializer, 'get_academic_check', lambda self, obj: junk), \
                mock.patch.object(ApplicantDocumentSerializer, 'get_authenticity',
                                  lambda self, obj: {'status': {'x': 1}}):
            data = ApplicantDocumentSerializer(self.doc('results_slip')).data
        self.assertIn(data['chip_pill'], doc_chips.PILLS)
        self.assertTrue(all(isinstance(c, dict) for c in data['chips']))

    def test_a_raise_in_the_chips_falls_back_and_logs_no_value(self):
        d = self.doc('ic')
        for serializer, module in ((ApplicantDocumentSerializer, doc_chips_student),
                                   (AdminApplicantDocumentSerializer, doc_chips)):
            for target in ('chips_for', 'pill_for'):
                documents_ser._CHIP_FALLBACK_LOGGED.clear()

                def boom(*_a, **_k):
                    raise ValueError('SECRET NAME 900101-01-1234')
                with self.subTest(serializer.__name__, target=target), mock.patch.object(module, target, boom), \
                        self.assertLogs('apps.scholarship.serializers.documents', 'ERROR') as logs:
                    data = serializer(d).data
                    self.assertEqual((data['chips'], data['chip_pill']), ([], 'unread'))
                    self.assertIn('read_at', data)
                    line = '\n'.join(logs.output)
                    self.assertIn(str(d.pk), line)
                    self.assertIn('ValueError', line)
                    self.assertNotIn('SECRET', line)
                    self.assertNotIn('900101', line)

    def test_n6_the_fallback_logs_once_per_exception_type_and_always_counts(self):
        d = self.doc('ic')
        before = documents_ser.CHIP_FALLBACKS['count']
        with mock.patch.object(doc_chips_student, 'chips_for', lambda *_a: 1 / 0), \
                mock.patch.object(documents_ser.logger, 'error') as error:
            for _ in range(3):
                self.assertEqual(ApplicantDocumentSerializer(d).data['chips'], [])
        self.assertEqual(error.call_count, 1)                           # once, not three times
        self.assertEqual(error.call_args.args[1:], (d.pk, 'ZeroDivisionError'))
        with mock.patch.object(doc_chips_student, 'chips_for', lambda *_a: [][1]), \
                mock.patch.object(documents_ser.logger, 'error') as error:
            ApplicantDocumentSerializer(d).data
            ApplicantDocumentSerializer(d).data
        self.assertEqual(error.call_count, 1)                           # a new type logs once more
        self.assertEqual(error.call_args.args[2], 'IndexError')
        self.assertEqual(documents_ser.CHIP_FALLBACKS['count'], before + 5)

    def test_a_raise_in_the_chips_never_breaks_the_admin_payload_either(self):
        with mock.patch.object(doc_chips, 'chips_for', lambda *_a: 1 / 0), \
                self.assertLogs('apps.scholarship.serializers.documents', 'ERROR'):
            data = AdminApplicantDocumentSerializer(self.doc('ic')).data
        self.assertEqual((data['chips'], data['chip_pill']), ([], 'unread'))

    def test_read_at_never_raises(self):
        d = self.doc('photo')
        d.vision_run_at = 'junk'                           # in memory only: max() of a str and a datetime
        d.vision_fields_run_at = timezone.now()
        with self.assertLogs('apps.scholarship.serializers.documents', 'WARNING') as logs:
            data = ApplicantDocumentSerializer(d).data
        self.assertIsNone(data['read_at'])
        self.assertIn('TypeError', '\n'.join(logs.output))

    def test_figure_refused_is_officer_only_so_the_amount_chip_may_differ(self):
        """Kept on purpose (S0 changes nothing): the student payload has no ``figure_refused``."""
        doc = {'doc_type': 'salary_slip', 'income_proof_check': {
            'name_status': 'match', 'nric': '', 'points': [{'key': 'amount', 'value': '900'}]}}
        student = {c['key']: c['state'] for c in doc_chips.chips_for(doc)}
        officer = {c['key']: c['state'] for c in doc_chips.chips_for({**doc, 'figure_refused': True})}
        self.assertEqual(student.get('amount'), 'green')
        self.assertEqual(officer.get('amount_unusable'), 'amber')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   DOC_GENUINENESS_CHECK_ENABLED=False)
class OfficerRerunPayloadTests(TestCase):
    """S1 review round 1: the officer's Re-run answers with the OFFICER's payload (officer chips),
    not the student's, at no extra query."""

    def setUp(self):
        cohort = make_cohort()
        self.reviewer = make_admin('reviewer', owning_org=cohort.owning_organisation)
        self.app = make_application('assigned', cohort=cohort, reviewer=self.reviewer)
        self.ic = create_document(self.app, 'ic', storage_path='s', vision_run_at=timezone.now())

    def test_the_rerun_response_serves_the_officer_chips(self):
        with mock.patch('apps.scholarship.reextract.reextract_document', return_value=True):
            resp = authed_client(self.reviewer).post(
                f'/api/v1/admin/scholarship/applications/{self.app.id}/documents/{self.ic.id}/re-run-vision/',
                {}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual([c['key'] for c in data['chips']], ['name', 'ic_no'])     # officer keys
        self.assertEqual(data['chips'], doc_chips.chips_for(data))
        self.assertIn('figure_refused', data)
        self.assertIn('sgd_conversion', data)

    def test_the_officer_payload_costs_no_more_queries_than_the_student_one(self):
        # The conversion path must really run: gross_income (not net_pay) and an in-review status.
        type(self.app).objects.filter(pk=self.app.pk).update(status='submitted')
        slip = create_document(self.app, 'salary_slip', storage_path='p', vision_run_at=timezone.now(),
                               vision_fields={'fields': {'gross_income': '1000', 'currency': 'SGD'}})
        fresh = ApplicantDocument.objects.get(pk=slip.pk)
        self.assertIsNotNone(AdminApplicantDocumentSerializer(fresh).data['sgd_conversion'])
        for doc_id in ApplicantDocument.objects.filter(application=self.app).values_list('pk', flat=True):
            counts = []
            for serializer in (ApplicantDocumentSerializer, AdminApplicantDocumentSerializer):
                doc = ApplicantDocument.objects.get(pk=doc_id)           # fresh: nothing cached
                with CaptureQueriesContext(connection) as ctx:
                    serializer(doc).data
                counts.append(len(ctx.captured_queries))
            with self.subTest(doc_id=doc_id):
                self.assertEqual(counts[0], counts[1])
