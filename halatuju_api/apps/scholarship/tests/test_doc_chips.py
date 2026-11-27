"""Document chip standard S0: the server chips reproduce today's officer-drawer colours exactly.

The parity fixture is shared with the web (``halatuju-web/src/lib/__tests__/doc-chip-parity.test.ts``
runs today's web functions over the SAME cases), so the two sides can only agree or both go red.
"""
import datetime
import json
import pathlib

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship import doc_chips
from apps.scholarship.serializers import ApplicantDocumentSerializer
from apps.scholarship.sgd_conversion import AdminApplicantDocumentSerializer
from apps.scholarship.tests.factories import create_document, make_application

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
                self.assertEqual(doc_chips.pill_for(got), case['pill'])

    def test_every_chip_has_the_standard_shape(self):
        for case in _cases():
            for chip in doc_chips.chips_for(case['doc']):
                with self.subTest(case['name'], key=chip['key']):
                    want = CHIP_KEYS | ({'value'} if chip['kind'] == 'year' else set())
                    self.assertEqual(set(chip), want)
                    self.assertEqual(chip['student_action'], 'none')          # Sprint 0: nothing asked yet
                    self.assertIn(chip['student_action'], doc_chips.STUDENT_ACTIONS)
                    self.assertEqual(chip['state'], doc_chips.STATES[chip['status']])
                    self.assertIn(chip['kind'], ('fact', 'year'))
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
        self.assertEqual(doc_chips.pill_for([self.chip('red')]), 'check')


class ServedPayloadTests(TestCase):
    def setUp(self):
        self.app = make_application()

    def doc(self, doc_type, **kw):
        return create_document(self.app, doc_type, storage_path='s', **kw)

    def test_student_and_admin_payloads_carry_the_three_keys(self):
        d = self.doc('ic')
        for serializer in (ApplicantDocumentSerializer, AdminApplicantDocumentSerializer):
            with self.subTest(serializer.__name__):
                data = serializer(d).data
                for key in ('chips', 'chip_pill', 'read_at'):
                    self.assertIn(key, data)
                self.assertEqual(data['chips'], doc_chips.chips_for(data))
                self.assertEqual(data['chip_pill'], doc_chips.pill_for(data['chips']))

    def test_an_unread_ic_serves_two_grey_chips_and_unread(self):
        data = ApplicantDocumentSerializer(self.doc('ic')).data
        self.assertEqual([(c['key'], c['state']) for c in data['chips']], [('name', 'grey'), ('ic_no', 'grey')])
        self.assertEqual(data['chip_pill'], 'unread')
        self.assertIsNone(data['read_at'])

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

    def test_figure_refused_is_officer_only_so_the_amount_chip_may_differ(self):
        """Kept on purpose (S0 changes nothing): the student payload has no ``figure_refused``."""
        doc = {'doc_type': 'salary_slip', 'income_proof_check': {
            'name_status': 'match', 'nric': '', 'points': [{'key': 'amount', 'value': '900'}]}}
        student = {c['key']: c['state'] for c in doc_chips.chips_for(doc)}
        officer = {c['key']: c['state'] for c in doc_chips.chips_for({**doc, 'figure_refused': True})}
        self.assertEqual(student.get('amount'), 'green')
        self.assertEqual(officer.get('amount_unusable'), 'amber')
