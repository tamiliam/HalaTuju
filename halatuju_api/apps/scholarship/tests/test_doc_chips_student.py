"""Document chip standard S1: the STUDENT's chips (``doc_chips_student``).

The parity fixture ``student_cases`` is shared with the web
(``halatuju-web/src/components/ScholarshipDocuments/__tests__/student-chip-parity.test.tsx``), which
renders today's student checklists on the same cases and reads the badges off the screen. SYNTHETIC
data only.
"""
import json
import pathlib

from django.test import SimpleTestCase

from apps.scholarship import doc_chips, doc_chips_student as S
from apps.scholarship.tests.test_doc_chips import _CHECK_KEYS, _FIELDS, _JUNK

FIXTURE = pathlib.Path(__file__).resolve().parent / 'fixtures' / 'doc_chip_parity.json'
_PROJECTED = ('key', 'status', 'state', 'kind', 'label')
_STUDENT_FIELDS = _FIELDS + (
    'current_status', 'proof_kind', 'proof_name_status', 'proof_nric_status', 'display_proof_name_status',
    'display_proof_nric_status', 'display_wrong_card', 'display_name_status', 'guardian_name', 'ward_name',
    'child_name', 'mother_name', 'father_name', 'candidate_name', 'candidate_nric', 'monthly_bill',
    'unpaid_balance', 'missing', 'extra', 'mismatched', 'uncertain', 'declared_programme',
    'declared_institution', 'issuer', 'offer_date', 'intake', 'pathway', 'programme', 'institution',
)


def _cases():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))['student_cases']


class StudentParityFixtureTests(SimpleTestCase):
    def test_the_fixture_is_big_enough_and_covers_every_student_checklist(self):
        cases = _cases()
        self.assertGreaterEqual(len(cases), 50)
        types = {c['doc']['doc_type'] for c in cases}
        for dt in ('ic', 'parent_ic', 'salary_slip', 'epf', 'str', 'water_bill', 'electricity_bill',
                   'birth_certificate', 'guardianship_letter', 'results_slip', 'offer_letter',
                   'higher_results', 'photo', 'semester_result'):
            self.assertIn(dt, types)
        self.assertEqual(len({c['doc']['id'] for c in cases}), len(cases))

    def test_chips_for_matches_every_case(self):
        for case in _cases():
            with self.subTest(case['name']):
                got = [{k: c[k] for k in _PROJECTED} for c in S.chips_for(case['doc'])]
                self.assertEqual(got, case['chips'])

    def test_every_chip_has_the_standard_shape(self):
        seen_kinds = set()
        for case in _cases():
            for chip in S.chips_for(case['doc']):
                with self.subTest(case['name'], key=chip['key']):
                    self.assertEqual(set(chip), {'key', 'status', 'state', 'student_action', 'reason',
                                                 'kind', 'label'})
                    self.assertEqual(chip['student_action'], 'none')
                    self.assertEqual(chip['state'], S.STATES[chip['status']])
                    self.assertIn(chip['kind'], ('fact', 'plain', 'note'))
                    self.assertIsInstance(chip['label'], str)
                    seen_kinds.add(chip['kind'])
        self.assertEqual(seen_kinds, {'fact', 'plain', 'note'})

    def test_the_states_are_the_officer_states(self):
        self.assertIs(S.STATES, doc_chips.STATES)


class StudentPillTests(SimpleTestCase):
    def _c(self, state, kind='fact'):
        status = {v: k for k, v in S.STATES.items()}[state]
        return {'key': 'x', 'status': status, 'state': state, 'kind': kind}

    def test_no_chips_or_only_grey_is_unread(self):
        self.assertEqual(S.pill_for([]), 'unread')
        self.assertEqual(S.pill_for([self._c('grey')]), 'unread')

    def test_plain_tags_and_notes_never_count(self):
        self.assertEqual(S.pill_for([self._c('green'), self._c('amber', 'note'), self._c('grey', 'plain')]),
                         'verified')
        self.assertEqual(S.pill_for([self._c('amber', 'note')]), 'unread')

    def test_all_green_is_verified_and_any_amber_is_check(self):
        self.assertEqual(S.pill_for([self._c('green'), self._c('green')]), 'verified')
        self.assertEqual(S.pill_for([self._c('green'), self._c('amber')]), 'check')

    def test_any_red_fact_chip_is_problem_like_the_officer_rule(self):
        self.assertEqual(S.pill_for([self._c('red')]), 'problem')
        self.assertEqual(S.pill_for([self._c('green'), self._c('amber'), self._c('red')]), 'problem')
        self.assertEqual(S.pill_for([self._c('red', 'note')]), 'unread')      # a note never counts
        for chips in ([self._c('red')], [self._c('amber')], [self._c('green')], [self._c('grey')]):
            self.assertEqual(S.pill_for(chips), doc_chips.pill_for(chips))

    def test_every_fixture_pill_is_an_officer_pill_word(self):
        for case in _cases():
            with self.subTest(case['name']):
                self.assertIn(S.pill_for(S.chips_for(case['doc'])), doc_chips.PILLS)


class StudentJunkPayloadTests(SimpleTestCase):
    """A junk value (a list, a dict, a number where a word should be) never raises."""

    def test_no_junk_value_anywhere_raises(self):
        for dt in ('ic', 'photo', 'semester_result', 'higher_results', *_CHECK_KEYS):
            for junk in _JUNK:
                check = _CHECK_KEYS.get(dt, 'x_check')
                docs = [
                    {'doc_type': dt, check: junk, 'authenticity': junk, 'vision_run_at': junk},
                    {'doc_type': dt, 'vision_run_at': '2026-11-01', 'vision_name_verdict': junk,
                     'vision_nric_verdict': junk, 'vision_name': junk, 'vision_nric': junk,
                     'vision_address': junk, 'vision_name_match': junk, 'vision_address_match': junk,
                     'authenticity': {'status': junk, 'doc_seen': junk, 'reason': junk},
                     'vision_fields': {'student_verdict': junk},
                     check: {**{k: junk for k in _STUDENT_FIELDS},
                             'points': [{'key': junk, 'value': junk}, junk]}},
                ]
                for doc in docs:
                    with self.subTest(dt, junk=repr(junk)):
                        chips = S.chips_for(doc)
                        self.assertIn(S.pill_for(chips), doc_chips.PILLS)
                        for chip in chips:
                            self.assertEqual(chip['state'], S.STATES[chip['status']])
                            self.assertIsInstance(chip['label'], str)

    def test_a_payload_that_is_not_a_dict_has_no_chips(self):
        for junk in _JUNK:
            with self.subTest(junk=repr(junk)):
                self.assertEqual(S.chips_for(junk), [])

    def test_an_unread_ic_has_no_checklist(self):
        """Today's card draws no checklist until the card is read; only the genuineness note, if any."""
        self.assertEqual(S.chips_for({'doc_type': 'ic', 'vision_run_at': None}), [])
