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
from apps.scholarship.income_engine.declaration_name import (
    CLOSE, NAME_CLOSE_VERDICT, near_miss, payslip_only_warning, shown_warnings, soften)

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


class ConnectorDropTests(SimpleTestCase):
    """The patronymic connector drops out; a misread connector (one short inner word) drops once."""

    IC_NO_AL = 'MURUGAPPAN KANDASAMY'          # an IC that prints no A/L

    def test_misread_connector_between_given_and_father_name_is_close(self):
        # The shape of the case: given name, a misread "A/L", the father's name misread too;
        # the IC prints the given name and the father's name with no A/L.
        self.assertTrue(near_miss('MURUGAPPAN ALE KANDASANI', self.IC_NO_AL))
        self.assertTrue(near_miss('MURUGAPPAN AIL KANDASAMY', self.IC_NO_AL))
        self.assertTrue(near_miss('MURUGAPPAN NL KANDASAMY', IC_NAME))

    def test_exact_once_the_connectors_are_gone_is_close(self):
        self.assertTrue(near_miss('MURUGAPPAN A/L KANDASAMY', self.IC_NO_AL))
        self.assertTrue(near_miss('MURUGAPPAN ALE KANDASAMY', self.IC_NO_AL))

    def test_bn_is_a_connector(self):
        self.assertTrue(near_miss('HARIZAL BN OSMAN', 'HARIZAL BIN OSMAN'))
        self.assertTrue(near_miss('HARIZAL BN OSMAN', 'HARIZAL OSMAN'))

    def test_the_extra_word_may_be_on_the_ic_side(self):
        self.assertTrue(near_miss(self.IC_NO_AL, 'MURUGAPPAN ALE KANDASANI'))

    def test_guard_a_whole_different_word(self):
        self.assertFalse(near_miss('SELVAM ALE KANDASAMY', IC_NAME))

    def test_guard_two_parts_off(self):
        self.assertFalse(near_miss('MURUGESAN ALE KANDASANI', IC_NAME))

    def test_guard_a_different_father_name(self):
        self.assertFalse(near_miss('MURUGAPPAN ALE RAMASAMY', IC_NAME))

    def test_guard_an_extra_word_that_is_not_connector_like(self):
        self.assertFalse(near_miss('MURUGAPPAN RAJ KANDASAMY', IC_NAME))
        self.assertFalse(near_miss('MURUGAPPAN ANBU KANDASAMY', IC_NAME))   # four letters: not short

    def test_guard_two_extra_words(self):
        self.assertFalse(near_miss('MURUGAPPAN ALE NL KANDASAMY', IC_NAME))
        self.assertFalse(near_miss('MURUGAPPAN ALE KANDASAMY NL', self.IC_NO_AL))

    def test_guard_a_connector_like_word_at_either_end_does_not_drop(self):
        self.assertFalse(near_miss('ALE MURUGAPPAN KANDASAMY', self.IC_NO_AL))
        self.assertFalse(near_miss('MURUGAPPAN KANDASAMY ALE', self.IC_NO_AL))

    def test_guard_father_and_son_reversed_is_never_close(self):
        self.assertFalse(near_miss('KANDASAMY A/L MURUGAPPAN', IC_NAME))
        # With a misread connector the reversal is not visible to the patronymic check, so the
        # rest must agree in printed order.
        self.assertFalse(near_miss('KANDASAMY ALE MURUGAPPAN', IC_NAME))
        self.assertFalse(near_miss('KANDASAMY ALE MURUGAPPAN', self.IC_NO_AL))

    def test_declaration_with_a_misread_connector_softens_and_a_typed_payslip_does_not(self):
        read = 'MURUGAPPAN ALE KANDASANI'
        self.assertEqual(soften(_doc(name=read), 'mismatch', read, self.IC_NO_AL), CLOSE)
        self.assertEqual(soften(_doc(seen='private', name=read), 'mismatch', read, self.IC_NO_AL), 'mismatch')


class PayslipOnlyWarningTests(SimpleTestCase):
    EMPLOYER = 'No employer name shown on the document'
    PERIOD = 'Pay period is not stated'
    PERIOD_MS = 'Tempoh gaji tidak dinyatakan'
    HANDWRITTEN = 'The document is handwritten'
    NAME = 'Name on the form differs from the employer record'
    SIGN = 'Employer signature is missing'
    STAMP = 'Company stamp is not visible'

    def test_employer_and_period_warnings_are_payslip_only(self):
        for w in (self.EMPLOYER, self.PERIOD, self.PERIOD_MS, 'Company name missing',
                  'Month and year of salary not shown'):
            self.assertTrue(payslip_only_warning(w), w)

    def test_identity_approval_and_other_warnings_are_kept(self):
        for w in (self.HANDWRITTEN, self.NAME, self.SIGN, self.STAMP, 'NRIC not visible', '', None):
            self.assertFalse(payslip_only_warning(w), w)

    def test_a_declaration_loses_only_the_payslip_only_warnings(self):
        ws = [self.EMPLOYER, self.HANDWRITTEN, self.PERIOD, self.SIGN]
        self.assertEqual(shown_warnings(_doc(), ws), [self.HANDWRITTEN, self.SIGN])
        self.assertEqual(ws, [self.EMPLOYER, self.HANDWRITTEN, self.PERIOD, self.SIGN])   # not edited

    def test_a_typed_payslip_and_other_types_keep_every_warning(self):
        ws = [self.EMPLOYER, self.PERIOD]
        self.assertIs(shown_warnings(_doc(seen='private'), ws), ws)
        self.assertIs(shown_warnings(_doc(seen=''), ws), ws)
        self.assertIs(shown_warnings(_doc(doc_type='epf'), ws), ws)
        self.assertIsNone(shown_warnings(_doc(), None))

    def test_the_serializer_shows_a_filtered_copy_and_never_edits_the_stored_read(self):
        from rest_framework import serializers as drf
        from apps.scholarship.serializers.documents import ApplicantDocumentSerializer
        doc = _doc()
        doc.vision_fields['warnings'] = [self.EMPLOYER, self.HANDWRITTEN]
        with mock.patch.object(drf.ModelSerializer, 'to_representation',
                               lambda self, inst: {'id': 1, 'vision_fields': inst.vision_fields}):
            data = ApplicantDocumentSerializer().to_representation(doc)
        self.assertEqual(data['vision_fields']['warnings'], [self.HANDWRITTEN])
        self.assertEqual(data['vision_fields']['fields'], doc.vision_fields['fields'])
        self.assertEqual(doc.vision_fields['warnings'], [self.EMPLOYER, self.HANDWRITTEN])

    def test_the_serializer_leaves_a_typed_payslip_alone(self):
        from rest_framework import serializers as drf
        from apps.scholarship.serializers.documents import ApplicantDocumentSerializer
        doc = _doc(seen='private')
        doc.vision_fields['warnings'] = [self.EMPLOYER]
        with mock.patch.object(drf.ModelSerializer, 'to_representation',
                               lambda self, inst: {'id': 1, 'vision_fields': inst.vision_fields}):
            data = ApplicantDocumentSerializer().to_representation(doc)
        self.assertIs(data['vision_fields'], doc.vision_fields)


class StoredVerdictTests(SimpleTestCase):
    """Task 3: the stored student verdict says 'name_close', not 'name_mismatch', on the same rule."""

    NAMES = ['ANITHA A/P MURUGAPPAN', IC_NAME]          # the student, then a guardian

    def _verdict(self, name, seen, doc_type='salary_slip'):
        from apps.scholarship.vision.judge import doc_student_verdict
        return doc_student_verdict(doc_type, {'name': name, 'gross_income': '1200'},
                                   names=self.NAMES, doc_seen=seen)

    def test_declaration_near_miss_stores_name_close(self):
        self.assertEqual(self._verdict(MISREAD_2, 'declaration'), NAME_CLOSE_VERDICT)
        self.assertEqual(self._verdict('MURUGAPPAN ALE KANDASANI', 'declaration'), NAME_CLOSE_VERDICT)

    def test_typed_payslip_or_unknown_kind_stays_name_mismatch(self):
        self.assertEqual(self._verdict(MISREAD_2, 'private'), 'name_mismatch')
        self.assertEqual(self._verdict(MISREAD_2, ''), 'name_mismatch')

    def test_a_stranger_or_another_doc_type_stays_name_mismatch(self):
        self.assertEqual(self._verdict(STRANGER, 'declaration'), 'name_mismatch')
        self.assertEqual(self._verdict(MISREAD_2, 'declaration', doc_type='epf'), 'name_mismatch')

    def test_a_matching_name_is_still_ok(self):
        self.assertEqual(self._verdict(IC_NAME, 'declaration'), 'ok')

    def test_the_read_judges_again_once_it_knows_the_form_is_a_declaration(self):
        from apps.scholarship.vision.field_extraction import _soften_declaration_name
        doc = SimpleNamespace(doc_type='salary_slip')
        result = {'fields': {'name': MISREAD_2, 'gross_income': '1200'}, 'student_verdict': 'name_mismatch',
                  'authenticity': {'doc_seen': 'declaration'}}
        _soften_declaration_name(doc, result, names=self.NAMES)
        self.assertEqual(result['student_verdict'], NAME_CLOSE_VERDICT)
        typed = {**result, 'student_verdict': 'name_mismatch', 'authenticity': {'doc_seen': 'private'}}
        _soften_declaration_name(doc, typed, names=self.NAMES)
        self.assertEqual(typed['student_verdict'], 'name_mismatch')
        no_auth = {'fields': result['fields'], 'student_verdict': 'name_mismatch'}
        _soften_declaration_name(doc, no_auth, names=self.NAMES)
        self.assertEqual(no_auth['student_verdict'], 'name_mismatch')

    def test_name_close_is_quiet_in_the_help_coach_and_never_ok(self):
        from apps.scholarship.help_engine import VERDICT_GUIDANCE
        from apps.scholarship.help_verdict import _help_other_document
        self.assertNotIn(NAME_CLOSE_VERDICT, VERDICT_GUIDANCE)
        doc = SimpleNamespace(vision_fields={'student_verdict': NAME_CLOSE_VERDICT},
                              vision_name_match='', vision_address_match='')
        self.assertEqual(_help_other_document(doc), '')


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
