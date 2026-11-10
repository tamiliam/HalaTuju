"""Audit sprint A3.4 — GOLDEN CASES, part 2: the two per-document verdicts, recorded BEFORE the split.

``resolution.doc_match_verdict`` (does an Action Centre upload close its task?) and
``help_engine.verdict_for_document`` (which Cikgu Gopal note does a document get?) are driven through
every branch on stand-in documents, and each answer is compared with
``fixtures/a34_golden_verdicts.json``. Part 1, the shared helpers and the rules for re-recording
(never, to make a refactor green) are in ``test_a34_golden_verdicts.py``.
"""
from contextlib import ExitStack

from apps.scholarship import help_engine, resolution
from apps.scholarship.tests.test_a34_golden_verdicts import (
    AE, IE, PE, STUDENT, STUDENT_NRIC, _Calls, _DEFERRED, _GoldenBase, _chk, _doc, _fake_app, _patched,
    _sc)


# ── 3. The Action Centre's per-document verdict (`resolution.doc_match_verdict`) ──────────────

def _slip(**over):
    base = {'name': 'match', 'subjects': 'match', 'results': 'match'}
    base.update(over)
    return base


def _sv(v):
    return {'student_verdict': v}


#: name → (document, {check-function: answer}, stranger-roster). Check functions are patched at
#: their source; ``unjudged`` drives the real STR stranger rule (``str_unjudged_members``).
def _dm_cases():
    no_ref = {'name_status': 'no_ref', 'nric_status': 'no_ref'}
    return {
        'd01_higher_results':          (_doc('higher_results'), {}, None),
        'd02_slip_name_mismatch':      (_doc('results_slip'), {'slip': _slip(name='mismatch')}, None),
        'd03_slip_grade_mismatch':     (_doc('results_slip'), {'slip': _slip(results='mismatch')}, None),
        'd04_slip_name_unreadable':    (_doc('results_slip'), {'slip': _slip(name='unreadable')}, None),
        'd05_slip_table_unreadable':   (_doc('results_slip'), {'slip': _slip(subjects='unreadable')}, None),
        'd06_slip_name_pending':       (_doc('results_slip'), {'slip': _slip(name='pending')}, None),
        'd07_slip_table_pending':      (_doc('results_slip'), {'slip': _slip(subjects='pending')}, None),
        'd08_slip_subject_soft':       (_doc('results_slip'), {'slip': _slip(subjects='mismatch')}, None),
        'd09_slip_results_pending_ok': (_doc('results_slip'), {'slip': _slip(results='pending')}, None),
        'd10_slip_no_check':           (_doc('results_slip'), {'slip': None}, None),
        'd11_offer_name_mismatch':     (_doc('offer_letter'), {'offer': {'name': 'mismatch'}}, None),
        'd12_offer_ic_mismatch':       (_doc('offer_letter'), {'offer': {'ic': 'mismatch'}}, None),
        'd13_offer_not_official':      (_doc('offer_letter'), {'offer': {'name': 'match'},
                                                               'official': 'not_genuine'}, None),
        'd14_offer_name_unreadable':   (_doc('offer_letter'), {'offer': {'name': 'unreadable'}}, None),
        'd15_offer_name_pending':      (_doc('offer_letter'), {'offer': {'name': 'pending'}}, None),
        'd16_offer_ok':                (_doc('offer_letter'), {'offer': {'name': 'match'}}, None),
        'd17_parent_ic_mismatch':      (_doc('parent_ic'), {'pic': {'name_status': 'mismatch',
                                                                    'readable': True}}, None),
        'd18_parent_ic_chain_rescues': (_doc('parent_ic'), {'pic': {'proof_nric_status': 'mismatch',
                                                                    'chain_verified': True,
                                                                    'readable': True}}, None),
        'd19_parent_ic_not_run':       (_doc('parent_ic', run=False), {'pic': {}}, None),
        'd20_parent_ic_deferred':      (_doc('parent_ic'), {'pic': {'deferred': True}}, None),
        'd21_parent_ic_decode_error':  (_doc('parent_ic', error='empty image'), {'pic': {}}, None),
        'd22_parent_ic_service_down':  (_doc('parent_ic', error='Vision API quota exceeded'), {'pic': {}}, None),
        'd23_parent_ic_blank':         (_doc('parent_ic'), {'pic': {}}, None),
        'd24_parent_ic_ok':            (_doc('parent_ic'), {'pic': {'readable': True}}, None),
        'd25_slip_mismatch':           (_doc('salary_slip', vf=_sv('ok')), {'proof': {'nric_status': 'mismatch'}},
                                        None),
        'd26_slip_unread':             (_doc('salary_slip', vf=_sv('')), {'proof': {}}, None),
        'd27_slip_deferred':           (_doc('salary_slip', vf=_sv('review_manually')), {'proof': {}}, None),
        'd28_slip_wrong_doc':          (_doc('salary_slip', vf=_sv('wrong_doc')), {'proof': {}}, None),
        'd29_slip_incomplete':         (_doc('salary_slip', vf=_sv('incomplete')), {'proof': {}}, None),
        'd30_slip_ok':                 (_doc('salary_slip', vf=_sv('ok')), {'proof': {}}, None),
        'd31_epf_unreadable':          (_doc('epf', vf=_sv('unreadable')), {'proof': None}, None),
        'd32_str_stale':               (_doc('str'), {'str': _sc('stale')}, None),
        'd33_str_rejected':            (_doc('str'), {'str': _sc('rejected')}, None),
        'd34_str_wrong_type':          (_doc('str'), {'str': _sc('wrong_type')}, None),
        'd35_str_matched_but_red':     (_doc('str'), {'str': _sc('current', 'mismatch', 'match')}, None),
        'd36_str_proven_stranger':     (_doc('str'), {'str': _sc('current', 'mismatch', 'no_ref')}, []),
        'd37_str_unjudged_stranger':   (_doc('str'), {'str': _sc('current', 'mismatch', 'no_ref')},
                                        ['father']),
        'd38_str_unknown':             (_doc('str'), {'str': _sc('unknown', 'no_ref', 'no_ref')}, None),
        'd39_str_future':              (_doc('str'), {'str': _sc('future')}, None),
        'd40_str_ok':                  (_doc('str'), {'str': _sc('current')}, None),
        'd41_str_unmatched':           (_doc('str'), {'str': {'current_status': 'current', **no_ref}}, None),
        'd41b_str_unconfirmed_matched': (_doc('str'), {'str': _sc('unconfirmed')}, None),
        'd41c_str_no_check':           (_doc('str'), {'str': None}, None),
        'd42_bc_child_mismatch':       (_doc('birth_certificate', vf=_sv('ok')), {'bc': {'child_status': 'mismatch'}},
                                        None),
        'd43_bc_father_only':          (_doc('birth_certificate', vf=_sv('ok')),
                                        {'bc': {'father_status': 'mismatch'}}, None),
        'd44_bc_unread':               (_doc('birth_certificate', vf=_sv('')), {'bc': {}}, None),
        'd45_bc_wrong_doc':            (_doc('birth_certificate', vf=_sv('wrong_doc')), {'bc': {}}, None),
        'd46_letter_mismatch':         (_doc('guardianship_letter', vf=_sv('ok')),
                                        {'gl': {'ward_status': 'mismatch'}}, None),
        'd47_letter_unread':           (_doc('guardianship_letter', vf=_sv('review_manually')), {'gl': {}}, None),
        'd48_letter_wrong_doc':        (_doc('guardianship_letter', vf=_sv('wrong_doc')), {'gl': {}}, None),
        'd49_letter_incomplete':       (_doc('guardianship_letter', vf=_sv('incomplete')), {'gl': {}}, None),
        'd50_support_unread':          (_doc('income_support_doc', vf=_sv('')), {}, None),
        'd51_support_wrong_doc':       (_doc('income_support_doc', vf=_sv('wrong_doc')), {}, None),
        'd52_support_ok':              (_doc('income_support_doc', vf=_sv('ok')), {}, None),
        'd53_leaving_cert_deferred':   (_doc('school_leaving_cert', vf=_sv('review_manually')), {}, None),
        'd54_semester_wrong_doc':      (_doc('semester_result', vf=_sv('wrong_doc')), {}, None),
        'd55_semester_ok':             (_doc('semester_result', vf=_sv('ok')), {}, None),
        'd56_bank_read':               (_doc('bank_statement', vf=_sv('read')), {}, None),
        'd57_bank_not_holder':         (_doc('bank_statement', vf=_sv('name_mismatch')), {}, None),
        'd58_bank_incomplete':         (_doc('bank_statement', vf=_sv('incomplete')), {}, None),
        'd59_bank_ok':                 (_doc('bank_statement', vf=_sv('ok')), {}, None),
        'd60_ic_not_run':              (_doc('ic', run=False), {}, None),
        'd61_ic_service_down':         (_doc('ic', error='Vision API quota exceeded'), {}, None),
        'd62_ic_deferred':             (_doc('ic', vf=_DEFERRED, nric=STUDENT_NRIC, name='X'), {}, None),
        'd63_ic_no_nric':              (_doc('ic', name=STUDENT), {}, None),
        'd64_ic_decode_error_blank':   (_doc('ic', error='empty image'), {}, None),
        'd65_ic_nric_mismatch':        (_doc('ic', nric='010101-01-0101', name=STUDENT), {}, None),
        'd66_ic_name_mismatch':        (_doc('ic', nric=STUDENT_NRIC, name='MEENA A/P RAJU'), {}, None),
        'd67_ic_ok':                   (_doc('ic', nric=STUDENT_NRIC, name=STUDENT), {}, None),
        'd68_ic_truncated_ok':         (_doc('ic', nric=STUDENT_NRIC, name='ANBU A/L'), {}, None),
        'd69_water_bill':              (_doc('water_bill', vf=_sv('wrong_doc')), {}, None),
    }


class TestGoldenDocMatch(_GoldenBase):
    SECTION = 'doc_match_verdict'

    def test_action_centre_document_verdict_is_unchanged(self):
        results = {}
        for case, (doc, answers, unjudged) in _dm_cases().items():
            patches = {
                f'{AE}.student_slip_check': lambda d, a=answers: a.get('slip'),
                f'{PE}.student_offer_check': lambda d, a=answers: a.get('offer'),
                f'{PE}.offer_official_status': lambda d, a=answers: a.get('official', 'unknown'),
                f'{IE}.student_income_ic_check': lambda d, a=answers: a.get('pic'),
                f'{IE}.student_income_proof_check': lambda d, a=answers: a.get('proof'),
                f'{IE}.student_str_check': lambda d, a=answers: a.get('str'),
                f'{IE}.student_bc_check': lambda d, a=answers: a.get('bc'),
                f'{IE}.student_guardianship_check': lambda d, a=answers: a.get('gl'),
                'apps.scholarship.resolution._higher_match_verdict': lambda d: 'golden-higher',
                'apps.scholarship.income_str_ownership.str_unjudged_members':
                    lambda app, sc, u=unjudged: list(u or []),
            }
            with ExitStack() as stack:
                _patched(stack, patches)
                results[case] = resolution.doc_match_verdict(doc)
        self.check(results)


# ── 4. Cikgu Gopal's help code (`help_engine.verdict_for_document`) ───────────────────────────

def _hc_cases():
    return {
        'h01_ic_not_run':             (_doc('ic', run=False), {}),
        'h02_ic_deferred':            (_doc('ic', vf=_DEFERRED, nric=STUDENT_NRIC), {}),
        'h03_ic_error':               (_doc('ic', error='empty image', nric=STUDENT_NRIC), {}),
        'h04_ic_no_nric':             (_doc('ic', name=STUDENT), {}),
        'h05_ic_digits_misread':      (_doc('ic', nric='010101-01-0101', name=STUDENT), {}),
        'h06_ic_wrong_card':          (_doc('ic', nric='010101-01-0101', name='MEENA A/P RAJU'), {}),
        'h07_ic_nric_off_no_name':    (_doc('ic', nric='010101-01-0101'), {}),
        'h08_ic_name_mismatch':       (_doc('ic', nric=STUDENT_NRIC, name='MEENA A/P RAJU'), {}),
        'h09_ic_clean':               (_doc('ic', nric=STUDENT_NRIC, name=STUDENT), {}),
        'h10_parent_ic_not_run':      (_doc('parent_ic', run=False, member='father'), {}),
        'h11_parent_ic_tagged':       (_doc('parent_ic', member='mother'), {}),
        'h12_parent_ic_earner':       (_doc('parent_ic'), {}),
        'h13_parent_ic_consent_deferred': (_doc('parent_ic', vf=_DEFERRED, app=_fake_app(earner='')), {}),
        'h14_parent_ic_consent_error': (_doc('parent_ic', error='x', name='A', app=_fake_app(earner='')), {}),
        'h15_parent_ic_consent_blank': (_doc('parent_ic', app=_fake_app(earner='')), {}),
        'h16_parent_ic_consent_ok':   (_doc('parent_ic', name='A', app=_fake_app(earner='')), {}),
        'h17_higher_results':         (_doc('higher_results', vf=_sv('wrong_doc')), {}),
        'h18_slip_unread':            (_doc('results_slip'), {}),
        'h19_slip_wrong_doc':         (_doc('results_slip', vf=_sv('wrong_doc')), {}),
        'h20_slip_unreadable':        (_doc('results_slip', vf=_sv('unreadable')), {}),
        'h21_slip_deferred':          (_doc('results_slip', vf=_sv('review_manually')), {}),
        'h22_slip_name_mismatch':     (_doc('results_slip', vf=_sv('ok')), {'slip': _slip(name='mismatch')}),
        'h23_slip_name_unreadable':   (_doc('results_slip', vf=_sv('ok')), {'slip': _slip(name='unreadable')}),
        'h24_slip_missing_subject':   (_doc('results_slip', vf=_sv('ok')),
                                       {'slip': {**_slip(subjects='mismatch'), 'missing': ['BM']}}),
        'h25_slip_extra_subject':     (_doc('results_slip', vf=_sv('ok')), {'slip': _slip(subjects='mismatch')}),
        'h26_slip_grade_mismatch':    (_doc('results_slip', vf=_sv('ok')), {'slip': _slip(results='mismatch')}),
        'h27_slip_uncertain_skewed':  (_doc('results_slip', vf=_sv('ok')),
                                       {'slip': {**_slip(results='uncertain'), 'was_skewed': True}}),
        'h28_slip_uncertain':         (_doc('results_slip', vf=_sv('ok')), {'slip': _slip(results='uncertain')}),
        'h29_slip_table_skewed':      (_doc('results_slip', vf=_sv('ok')),
                                       {'slip': {**_slip(subjects='unreadable'), 'was_skewed': True}}),
        'h30_slip_results_unreadable': (_doc('results_slip', vf=_sv('ok')), {'slip': _slip(results='unreadable')}),
        'h31_slip_clean':             (_doc('results_slip', vf=_sv('ok')), {'slip': _slip()}),
        'h32_offer_unread':           (_doc('offer_letter'), {}),
        'h33_offer_wrong_doc':        (_doc('offer_letter', vf=_sv('wrong_doc')), {}),
        'h34_offer_deferred':         (_doc('offer_letter', vf=_sv('review_manually')), {}),
        'h35_offer_ic_mismatch':      (_doc('offer_letter', vf=_sv('ok')), {'offer': _chk(ic='mismatch')}),
        'h36_offer_pathway_mismatch': (_doc('offer_letter', vf=_sv('ok')), {'offer': _chk(pathway='mismatch')}),
        'h37_offer_clean':            (_doc('offer_letter', vf=_sv('ok')), {'offer': _chk()}),
        'h38_str_stale':              (_doc('str'), {'str': _sc('stale')}),
        'h39_str_unreadable':         (_doc('str'), {'str': _sc('unreadable')}),
        'h40_str_current_ic_on_file': (_doc('str'), {'str': _sc(), 'ic': True}),
        'h41_str_current_no_ic':      (_doc('str'), {'str': _sc(), 'ic': False}),
        'h42_str_current_approval_missing': (_doc('str'), {'str': _sc(), 'ic': True, 'approval': ('approver',)}),
        'h43_str_salary_route':       (_doc('str', vf=_sv('unreadable'), app=_fake_app(route='salary')),
                                       {'str': _sc()}),
        'h44_payslip_no_ic':          (_doc('salary_slip'), {'member': 'father', 'ic': False}),
        'h45_payslip_needs_approver': (_doc('salary_slip'), {'member': 'father', 'ic': True,
                                                             'approval': ('header',)}),
        'h46_epf_ic_ok':              (_doc('epf'), {'member': 'mother', 'ic': True}),
        'h47_payslip_no_member':      (_doc('salary_slip', vf=_sv('wrong_doc')), {'member': ''}),
        'h48_bill_not_run':           (_doc('water_bill', run=False, address_match='mismatch'), {}),
        'h49_bill_address':           (_doc('electricity_bill', address_match='mismatch'), {}),
        'h50_bill_ok':                (_doc('water_bill', address_match='match', name_match='not_found'), {}),
        'h51_birth_certificate':      (_doc('birth_certificate', vf=_sv('wrong_doc')), {}),
        'h52_guardianship_letter':    (_doc('guardianship_letter', vf=_sv('unreadable')), {}),
        'h53_bank_unread':            (_doc('bank_statement'), {}),
        'h54_bank_not_holder':        (_doc('bank_statement', vf=_sv('name_mismatch')), {}),
        'h55_bank_deferred':          (_doc('bank_statement', vf=_sv('review_manually')), {}),
        'h56_bank_unclear':           (_doc('bank_statement', vf=_sv('incomplete')), {}),
        'h57_bank_ok':                (_doc('bank_statement', vf=_sv('ok')), {}),
        'h58_other_ok':               (_doc('statement_of_intent', vf=_sv('ok')), {}),
        'h59_other_unreadable':       (_doc('statement_of_intent', vf=_sv('unreadable')), {}),
        'h60_other_unknown_code':     (_doc('statement_of_intent', vf=_sv('golden_unknown')), {}),
        'h61_other_name_not_found':   (_doc('statement_of_intent', name_match='not_found'), {}),
        'h62_other_address':          (_doc('statement_of_intent', address_match='mismatch'), {}),
        'h63_other_unreadable_match': (_doc('statement_of_intent', name_match='unreadable'), {}),
        'h64_other_clean':            (_doc('statement_of_intent', name_match='match'), {}),
        # Added after the split's mutation testing (checked against the untouched tree first): a
        # student IC whose name only PARTLY matches (OCR truncation), with and without a good
        # number, and an "other" document whose ADDRESS alone did not read.
        'h65_ic_name_partial':        (_doc('ic', nric=STUDENT_NRIC, name='ANBU A/L'), {}),
        'h66_ic_misread_name_partial': (_doc('ic', nric='010101-01-0101', name='ANBU A/L'), {}),
        'h67_other_address_unreadable': (_doc('statement_of_intent', address_match='unreadable'), {}),
    }


class TestGoldenHelpCode(_GoldenBase):
    SECTION = 'verdict_for_document'

    def test_gopal_help_code_is_unchanged(self):
        results = {}
        for case, (doc, answers) in _hc_cases().items():
            calls = _Calls()
            patches = {
                f'{IE}.income_cluster_advice': calls.fake('income_cluster_advice',
                                                          lambda app, member: f'cluster:{member}'),
                f'{IE}._proof_member': lambda d, a=answers: a.get('member', ''),
                f'{IE}._member_ic_doc': lambda app, m, a=answers: object() if a.get('ic') else None,
                f'{IE}.student_str_check': lambda d, a=answers: a.get('str'),
                f'{AE}.student_slip_check': lambda d, a=answers: a.get('slip'),
                f'{PE}.student_offer_check': lambda d, a=answers: a.get('offer'),
                'apps.scholarship.income_declaration.approval_missing':
                    lambda d, a=answers: tuple(a.get('approval', ())),
            }
            with ExitStack() as stack:
                _patched(stack, patches)
                code = help_engine.verdict_for_document(doc)
            results[case] = {'code': code, 'calls': calls.log}
        self.check(results)
