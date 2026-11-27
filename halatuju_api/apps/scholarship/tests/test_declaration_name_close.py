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
    CLOSE, for_decisions, near_miss, payslip_only_warning, shown_warnings, soften)

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

    def test_the_read_has_no_second_judging_step(self):
        from apps.scholarship.vision import field_extraction
        self.assertFalse(hasattr(field_extraction, '_soften_declaration_name'))

    def test_no_stored_close_word_exists(self):
        from apps.scholarship.income_engine import declaration_name
        self.assertFalse(hasattr(declaration_name, 'NAME_CLOSE_VERDICT'))
        self.assertFalse(hasattr(declaration_name, 'stored_verdict_close'))


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

    def test_no_decision_module_calls_soften(self):
        # soften lives in income_engine (the verdict fingerprint covers it) but only the display
        # module may call it.
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1]
        callers = sorted(p.relative_to(root).as_posix() for p in root.rglob('*.py')
                         if 'tests' not in p.parts and p.name != 'declaration_name.py'
                         and 'declaration_name import soften' in p.read_text(encoding='utf-8'))
        self.assertEqual(callers, ['link_display.py'])
