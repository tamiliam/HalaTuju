"""Case 1048 (owner 2026-11-27): a near-miss name on a handwritten income declaration reads 'close'.

All names here are made up. The shape is case 1048's: a father's "Surat Akuan Pengesahan Pendapatan"
in the salary-slip slot, read as a declaration, whose handwritten name the AI misread by one or two
letters in one part. A typed payslip with the same misread still says 'mismatch'.
"""
import json
import re
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship.doc_red_keys import person_red
from apps.scholarship.income_engine import declaration_name, identity_checks
from apps.scholarship.income_engine.declaration_name import (
    CLOSE, for_decisions, near_miss, payslip_only_warning, shown_warnings, soften)

#: The tests of what 'close' WOULD show run with the switch on (NRIC chip Sprint 3's setting).
show_close_on = mock.patch.object(declaration_name, 'SHOW_CLOSE', True)

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

    # Review round 1, should-fix 4: a son's connector is never 'close' to a daughter's.
    def test_guard_a_l_against_a_p_is_never_close(self):
        self.assertFalse(near_miss('KAVITHA A/L KANDASAMY', 'KAVITHA A/P KANDASAMY'))
        self.assertFalse(near_miss('KAVITHA A/P KANDASAMY', 'KAVITHA A/L KANDASAMY'))
        self.assertFalse(near_miss('KAVITHA A / L KANDASANI', 'KAVITHA A/P KANDASAMY'))
        self.assertFalse(near_miss('KAVITHAA/L KANDASAMY', 'KAVITHA A/P KANDASAMY'))   # glued marker

    def test_guard_s_o_against_d_o_is_never_close(self):
        self.assertFalse(near_miss('KAVITHA S/O KANDASAMY', 'KAVITHA D/O KANDASAMY'))
        self.assertFalse(near_miss('KAVITHA D/O KANDASAMY', 'KAVITHA S/O KANDASAMY'))
        self.assertFalse(near_miss('KAVITHA S/O KANDASAMY', 'KAVITHA A/P KANDASAMY'))

    def test_guard_bin_against_binti_is_never_close(self):
        self.assertFalse(near_miss('NURUL BIN OSMAN', 'NURUL BINTI OSMAN'))
        self.assertFalse(near_miss('NURUL BN OSMAN', 'NURUL BT OSMAN'))

    def test_guard_a_misread_a_l_against_a_printed_a_p(self):
        self.assertFalse(near_miss('KAVITHA ALE KANDASAMY', 'KAVITHA A/P KANDASAMY'))
        self.assertFalse(near_miss('KAVITHA A/P KANDASAMY', 'KAVITHA NL KANDASAMY'))

    def test_same_sex_connectors_stay_close(self):
        self.assertTrue(near_miss('MURUGAPPAN S/O KANDASANI', IC_NAME))
        self.assertTrue(near_miss('MURUGAPPAN ALE KANDASANI', IC_NAME))
        self.assertTrue(near_miss('KAVITHA D/O KANDASANI', 'KAVITHA A/P KANDASAMY'))
        self.assertTrue(near_miss('NURUL BTE OSMAN', 'NURUL BINTI OSMAN'))

    # Review round 2: the slash-less exact forms carry their sex before any misread logic.
    def test_guard_d_o_against_a_slashless_so(self):
        self.assertFalse(near_miss('KUMARAN D/O RAJAN', 'KUMARAN SO RAJAN'))
        self.assertFalse(near_miss('KUMARAN SO RAJAN', 'KUMARAN D/O RAJAN'))

    def test_guard_a_slashless_do_against_s_o(self):
        self.assertFalse(near_miss('KUMARAN DO RAJAN', 'KUMARAN S/O RAJAN'))
        self.assertFalse(near_miss('KUMARAN DO RAJAN', 'KUMARAN SO RAJAN'))

    def test_guard_bnt_against_bin(self):
        self.assertFalse(near_miss('AMINAH BNT YUSOF', 'AMINAH BIN YUSOF'))
        self.assertFalse(near_miss('AMINAH BNT YUSOF', 'AMINAH BN YUSOF'))

    def test_guard_a_connector_glued_on_both_sides(self):
        self.assertFalse(near_miss('KUMARANA/PRAJAN', 'KUMARAN A/L RAJAN'))
        self.assertFalse(near_miss('KUMARAN A/L RAJAN', 'KUMARANA / PRAJAN'))
        self.assertFalse(near_miss('KUMARAND/ORAJAN', 'KUMARAN S/O RAJAN'))

    def test_guard_a_misread_word_near_both_sexes_against_a_clear_sex(self):
        for word in ('ALP', 'APL', 'BO'):
            self.assertFalse(near_miss(f'KUMARAN {word} RAJAN', 'KUMARAN A/L RAJAN'), word)
            self.assertFalse(near_miss(f'KUMARAN {word} RAJAN', 'KUMARAN A/P RAJAN'), word)
            self.assertFalse(near_miss('KUMARAN S/O RAJAN', f'KUMARAN {word} RAJAN'), word)

    def test_guard_ah_is_a_name_part_not_a_misread_connector(self):
        self.assertFalse(near_miss('TAN AH SENG', 'TAN SENG'))
        self.assertFalse(near_miss('TAN SENG', 'TAN AH SENG'))

    def test_same_sex_slashless_forms_stay_close(self):
        self.assertTrue(near_miss('KUMARAN SO RAJAN', 'KUMARAN S/O RAJAN'))
        self.assertTrue(near_miss('KUMARAN DO RAJAN', 'KUMARAN D/O RAJAN'))
        self.assertTrue(near_miss('AMINAH BNT YUSOF', 'AMINAH BINTI YUSOF'))
        self.assertTrue(near_miss('KUMARANA/LRAJAN', 'KUMARAN A/L RAJAN'))

    @show_close_on
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

    # Review round 1, blocker 3: the filter is an ALLOWLIST of pure absence notes.
    MUST_KEEP = ('Company chop missing', 'Majikan tidak menandatangani', 'Employer did not sign',
                 'Company letterhead looks forged', 'Majikan palsu', 'Pay period looks altered / tampered',
                 'Tempoh gaji telah diubah', 'Employer is the applicant themselves',
                 'Employer: none; amount written over (correction fluid)',
                 'No penghulu endorsement; employer missing',
                 'Employer not stated; IC number not visible', 'Tiada cop majikan',
                 'No KP shown; pay period missing', 'Employer not stated; the form is handwritten',
                 'Employer stamp not visible', 'Pay period not stated but the amount was overwritten',
                 'Employer missing; name of the earner differs')
    MUST_HIDE = ('Employer not stated', 'No employer name', 'Pay period missing', 'Tiada majikan',
                 'Tempoh gaji tidak dinyatakan', "Employer's name is not provided",
                 'Employer: none', 'Pay period not specified', 'Pay period not indicated',
                 'No employer; no pay period', 'Employer not stated; pay period missing',
                 'Nama majikan tidak dicatat', 'Pay period: N/A')

    def test_substantive_warnings_are_kept(self):
        for w in self.MUST_KEEP:
            self.assertFalse(payslip_only_warning(w), w)

    def test_pure_absence_warnings_are_hidden(self):
        for w in self.MUST_HIDE:
            self.assertTrue(payslip_only_warning(w), w)

    def test_an_employer_or_period_note_that_is_not_an_absence_is_kept(self):
        for w in ('Employer is a relative', 'Pay period is March to April', 'Majikan ialah syarikat sendiri',
                  'Company details look inconsistent'):
            self.assertFalse(payslip_only_warning(w), w)

    def test_a_declaration_shows_every_substantive_warning(self):
        ws = list(self.MUST_KEEP + self.R2_KEEP) + list(self.MUST_HIDE + self.R2_HIDE)
        self.assertEqual(shown_warnings(_doc(), ws), list(self.MUST_KEEP + self.R2_KEEP))

    # Review round 2: "nothing left over" — split on ; , . and/dan; every part must be pure absence.
    R2_KEEP = ('Employer not stated.  Figure crossed out', 'Employer not stated (whited out area)',
               'employer not stated, I.C. no unclear', 'employer not stated, k/p unreadable',
               'Tiada majikan dan tiada tarikh', 'No employer stated and the date is missing')
    R2_HIDE = ('Month of income not stated', 'Pay slip period absent')

    def test_r2_a_left_over_word_keeps_the_warning(self):
        for w in self.R2_KEEP:
            self.assertFalse(payslip_only_warning(w), w)

    def test_r2_month_of_income_and_pay_slip_period_are_hidden(self):
        for w in self.R2_HIDE:
            self.assertTrue(payslip_only_warning(w), w)

    def test_r2_the_ic_forms_keep_the_warning(self):
        for ic in ('I.C.', 'K/P', 'k.p.', 'i/c', 'IC', 'KP', 'I / C', 'K.P'):
            self.assertFalse(payslip_only_warning(f'Employer not stated; {ic} missing'), ic)
            self.assertFalse(payslip_only_warning(f'No {ic}'), ic)

    def test_r2_a_missing_date_is_not_payslip_only(self):
        for w in ('Date missing', 'Pay date not stated', 'Tiada tarikh', 'Employer not stated, no date',
                  'Tarikh tidak dinyatakan'):
            self.assertFalse(payslip_only_warning(w), w)

    def test_r2_and_dan_split_only_as_whole_words(self):
        # "and"/"dan" inside a word ("standard", "pendapatan") is not a split, and not a filler either.
        self.assertTrue(payslip_only_warning('No employer and no pay period'))
        self.assertTrue(payslip_only_warning('Tiada majikan dan tempoh gaji tidak dinyatakan'))
        self.assertFalse(payslip_only_warning('Employer not stated, standard form'))
        self.assertFalse(payslip_only_warning('Employer is not a company'))   # a bare "not" is no absence
        self.assertFalse(payslip_only_warning('Employer stated'))             # no absence at all
        self.assertFalse(payslip_only_warning('Salary not stated'))           # the amount is not a topic

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


class StoredVerdictUnchangedTests(SimpleTestCase):
    """Review round 1: the STORED student verdict is not softened. A declaration near miss still stores
    'name_mismatch', exactly as a typed payslip does, so no consumer of the stored verdict can read it
    as clean (and the verdict cannot depend on the order of the read's steps)."""

    NAMES = ['ANITHA A/P MURUGAPPAN', IC_NAME]          # the student, then a guardian

    def _verdict(self, name, doc_type='salary_slip'):
        from apps.scholarship.vision.judge import doc_student_verdict
        return doc_student_verdict(doc_type, {'name': name, 'gross_income': '1200'}, names=self.NAMES)

    def test_a_near_miss_stores_name_mismatch(self):
        self.assertEqual(self._verdict(MISREAD_2), 'name_mismatch')
        self.assertEqual(self._verdict('MURUGAPPAN ALE KANDASANI'), 'name_mismatch')

    def test_the_judge_takes_no_doc_seen(self):
        import inspect
        from apps.scholarship.vision.judge import doc_student_verdict
        self.assertNotIn('doc_seen', inspect.signature(doc_student_verdict).parameters)

    def _read_and_store(self, name, seen, show_close):
        """The REAL read/store path (run_field_extraction_for_document -> _read_labelled_doc -> the
        approval read -> _build_read_result -> add_read_authenticity -> _store_field_read) on a made-up
        declaration; only the OCR, the Gemini read, the approval call and the save are stand-ins."""
        from contextlib import nullcontext
        from django.test import override_settings
        from apps.scholarship import vision as v
        from apps.scholarship.vision import authenticity, field_extraction
        saved = []
        doc = SimpleNamespace(id=1, doc_type='salary_slip', application=None, application_id=None,
                              storage_path='made/up.jpg', content_type='image/jpeg', vision_fields={},
                              vision_fields_run_at=None, save=lambda **kw: saved.append(kw))
        ex = {'fields': {'name': name, 'gross_income': '1200'}, 'warnings': ['Employer not stated'], 'error': ''}
        with override_settings(DOC_GENUINENESS_CHECK_ENABLED=True), \
                mock.patch.object(declaration_name, 'SHOW_CLOSE', show_close), \
                mock.patch.object(field_extraction, '_doc_usage_ctx', lambda d: nullcontext()), \
                mock.patch.object(v, 'ocr_document', return_value={'text': 'SURAT AKUAN PENDAPATAN', 'error': ''}), \
                mock.patch('apps.scholarship.doc_parse.parse_by_labels', return_value=None), \
                mock.patch.object(v, 'extract_document_fields', return_value=ex), \
                mock.patch.object(field_extraction, '_read_approval', side_effect=lambda d, e, t, f: e), \
                mock.patch.object(authenticity, '_auth_income_doc',
                                  return_value={'doc_seen': seen, 'status': 'suspect'}):
            field_extraction.run_field_extraction_for_document(doc, names=self.NAMES)
        self.assertTrue(saved)
        return doc.vision_fields

    def test_the_real_read_stores_name_mismatch_for_a_declaration_near_miss(self):
        for show_close in (False, True):
            for name in (MISREAD_2, 'MURUGAPPAN ALE KANDASANI'):
                stored = self._read_and_store(name, 'declaration', show_close)
                self.assertEqual(stored['authenticity']['doc_seen'], 'declaration')
                self.assertEqual(stored['student_verdict'], 'name_mismatch', (name, show_close))
                self.assertEqual(stored['warnings'], ['Employer not stated'])   # the stored read is never filtered
                self.assertNotIn('close', json.dumps(stored).lower())

    def test_the_stored_verdict_is_the_typed_payslip_twin(self):
        decl = self._read_and_store(MISREAD_2, 'declaration', True)
        typed = self._read_and_store(MISREAD_2, 'private', True)
        self.assertEqual(decl['student_verdict'], typed['student_verdict'])


@show_close_on
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
        for st in ('match', 'no_ref', 'unreadable', 'not_read'):
            self.assertEqual(soften(_doc(), st, MISREAD_2, IC_NAME), st)

    def test_for_decisions_maps_close_to_mismatch_only(self):
        self.assertEqual(for_decisions(CLOSE), 'mismatch')
        for st in ('match', 'mismatch', 'no_ref', 'unreadable', 'not_read', ''):
            self.assertEqual(for_decisions(st), st)


# ── Review round 1, blockers 1 and 2: 'close' behaves EXACTLY like 'mismatch' for every decision ──

TYPED = 'private'        # a printed payslip with the same misread: the 'mismatch' twin


def _ic():
    return SimpleNamespace(vision_name=IC_NAME, vision_nric='', vision_run_at=None)


def _proof_patches(ic):
    return [mock.patch.object(identity_checks, '_proof_member', return_value='father'),
            mock.patch.object(identity_checks, '_member_ic_doc', return_value=ic),
            mock.patch.object(identity_checks, 'ic_second_opinion_deferred', return_value=False),
            mock.patch.object(identity_checks, 'chain_verified_earner', return_value=False),
            mock.patch('apps.scholarship.income_declaration.approval_missing', return_value=())]


class _Patched:
    """Runs the real decision code with its database lookups replaced by a made-up father's IC."""

    def __init__(self, extra=()):
        self.patches = _proof_patches(_ic()) + list(extra)

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()


@show_close_on
class DecisionEquivalenceTests(SimpleTestCase):
    """A declaration whose name SHOWS 'close' gets every decision a 'mismatch' gets: the same check,
    person-red, Action Centre state, cluster gate (so the income gate, the verdict band and the route
    switch, which all read it), coach and consent blocker. Only display_name_status differs."""

    def _both(self, fn):
        out = []
        for seen in ('declaration', TYPED):
            out.append(fn(_doc(seen=seen)))
        return out

    def test_the_decision_check_says_mismatch_for_both(self):
        with _Patched():
            decl, typed = self._both(identity_checks.student_income_proof_check)
        self.assertEqual(decl['name_status'], 'mismatch')
        self.assertEqual(decl, typed)
        self.assertNotIn(CLOSE, decl.values())

    def test_person_red_is_the_same(self):
        with _Patched():
            decl, typed = self._both(lambda d: person_red('salary_slip',
                                                          identity_checks.student_income_proof_check(d)))
        self.assertTrue(decl)
        self.assertEqual(decl, typed)

    def test_the_action_centre_holds_it_as_a_mismatch(self):
        # resolution.doc_match_verdict -> _income_proof: never 'ok' (None), so the request is not
        # closed (resolution.py), the file is not "usable" (promotion.py), and upload_read sends
        # match_verdict 'mismatch'.
        from apps.scholarship.resolution_doc_match import _income_proof
        with _Patched():
            decl, typed = self._both(lambda d: _income_proof(d, 'salary_slip'))
        self.assertEqual(decl, 'mismatch')
        self.assertEqual(decl, typed)

    def test_the_cluster_gate_refuses_both(self):
        # member_cluster_complete feeds salary_income_satisfied -> the verdict band (verdict_engine),
        # the route switch (assignment) and the submit gate. 'close' must not clear it.
        from apps.scholarship.income_engine import evidence
        out = []
        for seen in ('declaration', TYPED):
            doc = _doc(seen=seen)
            extra = [mock.patch.object(evidence, '_member_ic_doc', return_value=_ic()),
                     mock.patch.object(evidence, 'student_income_ic_check',
                                       return_value={'readable': True, 'name_status': 'match'}),
                     mock.patch.object(evidence, 'member_income_evidenced', return_value=True),
                     mock.patch.object(evidence, '_cluster_docs', return_value=[doc]),
                     mock.patch.object(evidence, 'relationship_doc_for', return_value=None)]
            with _Patched(extra):
                out.append(evidence.member_cluster_complete(object(), 'father'))
        self.assertEqual(out, [False, False])

    def test_the_coach_is_the_person_mismatch_coach_for_both(self):
        from apps.scholarship.income_engine import advice
        out = []
        for seen in ('declaration', TYPED):
            doc = _doc(seen=seen)
            extra = [mock.patch.object(advice, '_cluster_docs',
                                       side_effect=lambda a, m, dt, d=doc: [d] if dt == 'salary_slip' else []),
                     mock.patch.object(advice, '_member_ic_doc', return_value=_ic()),
                     mock.patch.object(advice, 'student_income_ic_check',
                                       return_value={'readable': True, 'name_status': 'match'})]
            with _Patched(extra):
                out.append(advice.income_cluster_advice(SimpleNamespace(income_route='salary'), 'father'))
        self.assertEqual(out, ['income_proof_person_mismatch'] * 2)

    def test_only_the_shown_status_says_close(self):
        from apps.scholarship import link_display
        shown = []
        for seen in ('declaration', TYPED):
            doc = _doc(seen=seen)
            extra = [mock.patch.object(link_display, '_member_ic_doc', return_value=_ic()),
                     mock.patch.object(link_display, 'ic_second_opinion_deferred', return_value=False),
                     mock.patch.object(link_display, '_anchor', return_value=None)]
            with _Patched(extra):
                chk = identity_checks.student_income_proof_check(doc)
                shown.append({**chk, **link_display.income_proof_display(doc, chk)})
        decl, typed = shown
        self.assertEqual((decl['name_status'], decl['display_name_status']), ('mismatch', CLOSE))
        self.assertEqual((typed['name_status'], typed['display_name_status']), ('mismatch', 'mismatch'))

    def test_a_deferred_card_shows_no_ref_not_close(self):
        # TD-390 turns a 'mismatch' into 'no_ref' when the card is half-read; 'close' must follow the
        # same rule, so the softening runs only on what is STILL a mismatch at the end.
        from apps.scholarship import link_display
        doc = _doc()
        extra = [mock.patch.object(link_display, '_member_ic_doc', return_value=_ic()),
                 mock.patch.object(link_display, 'ic_second_opinion_deferred', return_value=True),
                 mock.patch.object(link_display, '_anchor', return_value=None)]
        with _Patched(extra):
            chk = identity_checks.student_income_proof_check(doc)
            shown = link_display.income_proof_display(doc, chk)
        self.assertNotEqual(shown['display_name_status'], CLOSE)


class NoDecisionCallerTests(SimpleTestCase):
    """Review round 2: soften, near_miss and SHOW_CLOSE live in income_engine (the verdict fingerprint
    covers them) but only the display module may use them. A grep over apps/scholarship of every import
    and call form; the test files are allowed."""

    ALLOWED = {'link_display.py', 'income_engine/declaration_name.py'}
    #: The one other module that may import from declaration_name, and the one name it may take.
    WARNINGS_ONLY = {'serializers/documents.py'}

    def _sources(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1]
        for p in sorted(root.rglob('*.py')):
            rel = p.relative_to(root).as_posix()
            if 'tests' in p.relative_to(root).parts:
                continue
            yield rel, p.read_text(encoding='utf-8')

    def test_no_module_but_the_display_names_soften_near_miss_or_show_close(self):
        # Code only: comments and strings are blanked first (English prose says "do not soften").
        import io
        import tokenize
        users = []
        for rel, src in self._sources():
            if rel in self.ALLOWED:
                continue
            names = {t.string for t in tokenize.generate_tokens(io.StringIO(src).readline)
                     if t.type == tokenize.NAME}
            if names & {'soften', 'SHOW_CLOSE'} or (
                    'near_miss' in names and 'declaration_name' in src):
                users.append(rel)
        self.assertEqual(users, [])

    def test_only_the_allowed_modules_import_declaration_name(self):
        importers = {}
        # A bracketed import captures "(" and so fails the name check below: the safe direction.
        pattern = re.compile(r'(?:from\s+[.\w]*declaration_name\s+import\s+([^\n#]+)'
                             r'|from\s+[.\w]*income_engine\s+import\s+[^\n]*\bdeclaration_name\b'
                             r'|import\s+[.\w]*declaration_name\b'
                             r'|import_module\([^)]*declaration_name'
                             r'|__import__\([^)]*declaration_name)', re.M)
        for rel, src in self._sources():
            if rel in self.ALLOWED:
                continue
            for m in pattern.finditer(src):
                importers.setdefault(rel, []).append((m.group(1) or m.group(0)).strip())
        self.assertEqual(set(importers), self.WARNINGS_ONLY)
        for rel in self.WARNINGS_ONLY:
            self.assertEqual(importers[rel], ['shown_warnings'], rel)

    def test_the_grep_would_catch_each_import_form(self):
        # The guard itself: each way to reach soften would be seen.
        import io
        import tokenize
        for src in ('from .income_engine.declaration_name import soften\n',
                    'from .income_engine import declaration_name as dn\nx = dn.soften(1, 2, 3, 4)\n',
                    'import apps.scholarship.income_engine.declaration_name as dn\ny = dn.SHOW_CLOSE\n',
                    'from ..income_engine.declaration_name import (\n    near_miss,\n)\n'):
            names = {t.string for t in tokenize.generate_tokens(io.StringIO(src).readline)
                     if t.type == tokenize.NAME}
            self.assertTrue(names & {'soften', 'SHOW_CLOSE'} or 'near_miss' in names, src)


class ShowCloseSwitchTests(SimpleTestCase):
    """Review round 2: the API must not SERVE 'close' until the web can draw it (NRIC chip Sprint 3)."""

    def _payload(self, seen):
        from apps.scholarship import link_display
        doc = _doc(seen=seen)
        extra = [mock.patch.object(link_display, '_member_ic_doc', return_value=_ic()),
                 mock.patch.object(link_display, 'ic_second_opinion_deferred', return_value=False),
                 mock.patch.object(link_display, '_anchor', return_value=None)]
        with _Patched(extra):
            chk = identity_checks.student_income_proof_check(doc)
            return json.dumps({**chk, **link_display.income_proof_display(doc, chk)}, sort_keys=True,
                              default=str).encode('utf-8')

    def test_the_switch_is_off_in_code(self):
        self.assertIs(declaration_name.SHOW_CLOSE, False)
        import inspect
        src = inspect.getsource(declaration_name)
        self.assertNotIn('environ', src)
        self.assertNotIn('getenv', src)
        self.assertNotIn('settings', src)

    def test_switch_off_the_payload_is_byte_identical_to_base(self):
        # Base cb6a81b33 had no soften step at all: the display was the chain/deferral/not-read result,
        # which is the typed-payslip twin's payload and the payload with soften taken out.
        with mock.patch.object(declaration_name, 'SHOW_CLOSE', False):
            decl = self._payload('declaration')
            typed = self._payload(TYPED)
        with mock.patch.object(declaration_name, 'soften', lambda doc, status, *a: status):
            base = self._payload('declaration')
        self.assertEqual(decl, base)
        self.assertEqual(decl, typed)
        self.assertEqual(json.loads(decl)['display_name_status'], 'mismatch')
        self.assertNotIn(b'close', decl)

    def test_switch_off_soften_changes_nothing(self):
        with mock.patch.object(declaration_name, 'SHOW_CLOSE', False):
            self.assertEqual(soften(_doc(), 'mismatch', MISREAD_2, IC_NAME), 'mismatch')

    def test_switch_on_the_payload_shows_close(self):
        with show_close_on:
            decl = json.loads(self._payload('declaration'))
            typed = json.loads(self._payload(TYPED))
        self.assertEqual((decl['name_status'], decl['display_name_status']), ('mismatch', CLOSE))
        self.assertEqual(typed['display_name_status'], 'mismatch')

    def test_the_warning_filter_does_not_read_the_switch(self):
        ws = ['Employer not stated', 'The document is handwritten']
        for on in (False, True):
            with mock.patch.object(declaration_name, 'SHOW_CLOSE', on):
                self.assertEqual(shown_warnings(_doc(), ws), ['The document is handwritten'])
