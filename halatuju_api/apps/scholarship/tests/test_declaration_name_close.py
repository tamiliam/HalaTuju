"""Case 1048 (owner 2026-11-27): a near-miss name on a handwritten income declaration reads 'close'.

All names here are made up. The shape is case 1048's: a father's "Surat Akuan Pengesahan Pendapatan"
in the salary-slip slot, read as a declaration, whose handwritten name the AI misread by one or two
letters in one part. A typed payslip with the same misread still says 'mismatch'.
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship.doc_red_keys import person_red
from apps.scholarship.income_engine import identity_checks
from apps.scholarship.income_engine.declaration_name import CLOSE, near_miss, soften

IC_NAME = 'MURUGAPPAN A/L KANDASAMY'
MISREAD_1 = 'MURUGAPAN A/L KANDASAMY'      # one letter dropped in a long part
MISREAD_2 = 'MURUGAPPAN A/L KANDASANI'     # two letters misread in one part
STRANGER = 'MURUGAPPAN A/L RAMASAMY'       # a different father's name: not a misread


def _doc(seen='declaration', doc_type='salary_slip', name=MISREAD_2):
    return SimpleNamespace(doc_type=doc_type, application=object(), id=1, application_id=1,
                           vision_fields={'authenticity': {'doc_seen': seen},
                                          'fields': {'name': name, 'nric': '', 'gross_income': '1200'}})


class NearMissRuleTests(SimpleTestCase):
    def test_one_or_two_letters_in_one_part_is_a_near_miss(self):
        self.assertTrue(near_miss(MISREAD_2, IC_NAME))
        self.assertTrue(near_miss('MURUGAPPAN A/L KANDASAMY RAJU', 'MURUGAPPAN A/L KANDASAMY RAJA'))

    def test_a_different_name_part_is_not(self):
        self.assertFalse(near_miss(STRANGER, IC_NAME))

    def test_two_parts_off_is_not(self):
        self.assertFalse(near_miss('MURUGESAN A/L KANDASANI', IC_NAME))

    def test_three_edits_or_a_different_first_letter_is_not(self):
        self.assertFalse(near_miss('MURUGAPPAN A/L KANDAXXXX', IC_NAME))
        self.assertFalse(near_miss('MURUGAPPAN A/L RANDASANY', IC_NAME))

    def test_a_different_number_of_parts_or_one_word_is_not(self):
        self.assertFalse(near_miss('MURUGAPPAN', 'MURUGAPAN'))
        self.assertFalse(near_miss('MURUGAPPAN A/L KANDASANI RAJ', IC_NAME))


class SoftenScopeTests(SimpleTestCase):
    def test_declaration_near_miss_is_close(self):
        self.assertEqual(soften(_doc(), 'mismatch', MISREAD_2, IC_NAME), CLOSE)

    def test_typed_payslip_with_the_same_misread_stays_mismatch(self):
        # A printed payslip is seen as private/govt, never 'declaration': the matcher is not loosened.
        self.assertEqual(soften(_doc(seen='private'), 'mismatch', MISREAD_2, IC_NAME), 'mismatch')
        self.assertEqual(soften(_doc(seen=''), 'mismatch', MISREAD_2, IC_NAME), 'mismatch')

    def test_epf_is_never_softened(self):
        self.assertEqual(soften(_doc(doc_type='epf'), 'mismatch', MISREAD_2, IC_NAME), 'mismatch')

    def test_a_stranger_on_a_declaration_stays_mismatch(self):
        self.assertEqual(soften(_doc(), 'mismatch', STRANGER, IC_NAME), 'mismatch')

    def test_other_statuses_pass_through(self):
        for st in ('match', 'no_ref', 'unreadable'):
            self.assertEqual(soften(_doc(), st, MISREAD_2, IC_NAME), st)


class IncomeProofCheckTests(SimpleTestCase):
    """The real check, with its database lookups replaced by a made-up father's IC."""

    def _check(self, doc):
        ic = SimpleNamespace(vision_name=IC_NAME, vision_nric='')
        with mock.patch.object(identity_checks, '_proof_member', return_value='father'), \
                mock.patch.object(identity_checks, '_member_ic_doc', return_value=ic), \
                mock.patch.object(identity_checks, 'ic_second_opinion_deferred', return_value=False), \
                mock.patch.object(identity_checks, 'chain_verified_earner', return_value=False), \
                mock.patch('apps.scholarship.income_declaration.approval_missing', return_value=()):
            return identity_checks.student_income_proof_check(doc)

    def test_case_1048_shape_reads_close_and_is_not_red(self):
        chk = self._check(_doc())
        self.assertEqual(chk['name_status'], CLOSE)
        self.assertFalse(person_red('salary_slip', chk))

    def test_typed_payslip_one_edit_still_reads_mismatch_and_red(self):
        # 'KANDASAMI' vs 'KANDASAMY' passes the tolerant matcher (9 letters, 1 edit); a short part
        # one letter off does not — and on a typed payslip it stays red.
        doc = _doc(seen='private', name='MURUGAPPAN A/L KANDASAMY RAJU')
        ic = SimpleNamespace(vision_name='MURUGAPPAN A/L KANDASAMY RAJA', vision_nric='')
        with mock.patch.object(identity_checks, '_proof_member', return_value='father'), \
                mock.patch.object(identity_checks, '_member_ic_doc', return_value=ic), \
                mock.patch.object(identity_checks, 'ic_second_opinion_deferred', return_value=False), \
                mock.patch.object(identity_checks, 'chain_verified_earner', return_value=False), \
                mock.patch('apps.scholarship.income_declaration.approval_missing', return_value=()):
            chk = identity_checks.student_income_proof_check(doc)
        self.assertEqual(chk['name_status'], 'mismatch')
        self.assertTrue(person_red('salary_slip', chk))

    def test_close_is_never_a_match_for_the_consumers(self):
        chk = self._check(_doc())
        self.assertNotIn('match', (chk['name_status'], chk['nric_status']))
        self.assertNotIn('mismatch', (chk['name_status'], chk['nric_status']))
