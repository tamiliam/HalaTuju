"""Request #78, Part D: the Academic tile leads with the reason for its band.

The Academic band is set by the ladder's RED chips (`verdict_ladder._academic_red_chips`), but the card
raised its items in plain order: the slip's name line (`results_slip_name_near`, amber) came before a red
`academic_missing_subjects`, the higher card's `higher_results_name_near` before a red
`higher_results_kind_differs`, and an SPM slip's red items after every one of the higher card's amber
ones. No academic code is a confident disqualifier, so the web's subtitle shows `unresolved[0]`: an amber
line headed a red tile. `higher_results.academic_fact` now sorts the red-chip codes first (stable), with an
unreadable higher-results slip ahead of them because `fact_bands` reads it as red whatever the chips say.
"""
import re
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import award, higher_owed, higher_results, verdict_ladder
from apps.scholarship.verdict_engine import _fact

_SCHOLARSHIP = Path(higher_results.__file__).resolve().parent


def _codes(fact):
    return [i['code'] for i in fact['unresolved']]


def _spm_card(*codes, status='review'):
    """The SPM card's own answer, its items in the order `verdict_academic` raises them. Items are
    built as `verdict_engine._item` builds them, written out so no dynamic `_item()` call site is added
    (`test_verdict_item_i18n`)."""
    return _fact('academic', status, [], [{'code': c, 'params': {}} for c in codes])


def _higher_check(**over):
    chk = {'name': 'match', 'readable': True, 'kind_status': 'match', 'kind_held': 'stpm',
           'kind_detected': 'stpm', 'cgpa_status': 'match', 'cgpa_slip': 3.5, 'cgpa_entered': 3.5,
           'grades_status': 'match', 'missing': [], 'unrecognised': [], 'mismatched': [], 'uncertain': [],
           'extra': [], 'unchecked': []}
    chk.update(over)
    return chk


def _spm_route(spm):
    with mock.patch.object(higher_results, 'anchors_on_higher', return_value=False), \
            mock.patch.object(higher_owed, 'owed_kind', return_value=''):
        return higher_results.academic_fact(SimpleNamespace(), lambda: spm)


def _higher_route(chk, spm=None):
    """The higher card through `academic_fact`, with only the reads stubbed. `spm` = the SPM card's
    answer when a slip is on file (folded in by `verdict_academic`), else no slip."""
    app = SimpleNamespace(profile=SimpleNamespace())
    slip = SimpleNamespace() if spm is not None else None
    with mock.patch.object(higher_results, 'anchors_on_higher', return_value=True), \
            mock.patch.object(higher_owed, 'cap_undeclared', side_effect=lambda a, fact: fact), \
            mock.patch.object(higher_results, 'higher_doc', return_value=SimpleNamespace()), \
            mock.patch.object(higher_results, 'student_higher_check', return_value=chk), \
            mock.patch.object(higher_results, 'final_owed', return_value=False), \
            mock.patch.object(higher_results, '_scored', return_value=True), \
            mock.patch('apps.scholarship.verdict_engine._latest_doc', return_value=slip), \
            mock.patch.object(higher_results.courses_public, 'results_held', return_value='stpm'):
        return higher_results.academic_fact(app, lambda: spm)


class TestTheRedChipLeads(SimpleTestCase):

    def test_spm_slip_name_near_then_missing_subjects_leads_with_the_red(self):
        fact = _spm_route(_spm_card('results_slip_name_near', 'academic_missing_subjects', 'grades_unverified'))
        self.assertEqual(_codes(fact), ['academic_missing_subjects', 'results_slip_name_near', 'grades_unverified'])

    def test_spm_unreadable_name_then_grade_mismatch_leads_with_the_red(self):
        fact = _spm_route(_spm_card('results_slip_unreadable', 'academic_grade_uncertain',
                                    'academic_grade_band_mismatch', 'academic_extra_subjects'))
        self.assertEqual(_codes(fact), ['academic_grade_band_mismatch', 'academic_extra_subjects',
                                        'results_slip_unreadable', 'academic_grade_uncertain'])

    def test_higher_card_name_near_then_kind_differs_leads_with_the_red(self):
        fact = _higher_route(_higher_check(name='partial', readable=None, kind_status='different',
                                           kind_detected='matric'))
        self.assertEqual(_codes(fact), ['higher_results_kind_differs', 'higher_results_name_near',
                                        'higher_results_unverified'])

    def test_higher_card_red_results_lead_its_amber_lines(self):
        fact = _higher_route(_higher_check(name='partial', cgpa_status='mismatch', cgpa_slip=3.1,
                                           missing=['Kimia'], uncertain=[{'subject': 'Fizik'}]))
        self.assertEqual(_codes(fact), ['higher_results_cgpa_mismatch', 'higher_results_subjects_missing',
                                        'higher_results_name_near', 'higher_results_grade_uncertain'])

    def test_higher_amber_then_spm_red_leads_with_the_spm_red(self):
        fact = _higher_route(_higher_check(name='partial', readable=None),
                             spm=_spm_card('results_slip_name_near', 'academic_missing_subjects'))
        self.assertEqual(_codes(fact), ['academic_missing_subjects', 'higher_results_name_near',
                                        'higher_results_unverified', 'results_slip_name_near'])

    def test_an_unreadable_higher_slip_leads_even_the_red_chips(self):
        """`fact_bands` reads an unreadable higher-results slip as red (Can't verify) on any status,
        above the other-kind cap, so it is the reason for the band when it stands."""
        fact = _higher_route(_higher_check(name='partial', readable=False, kind_status='different',
                                           kind_detected='matric'))
        self.assertEqual(_codes(fact)[:2], ['higher_results_unreadable', 'higher_results_kind_differs'])

    def test_no_red_item_keeps_the_order(self):
        fact = _spm_route(_spm_card('results_slip_name_near', 'academic_grade_uncertain', 'grades_unverified'))
        self.assertEqual(_codes(fact), ['results_slip_name_near', 'academic_grade_uncertain', 'grades_unverified'])

    def test_the_owed_cap_keeps_the_red_first(self):
        """An application owing its higher results: the cap's reason joins after the card's items; a
        red chip still leads."""
        spm = _spm_card('results_slip_name_near', 'academic_missing_subjects')
        with mock.patch.object(higher_results, 'anchors_on_higher', return_value=False), \
                mock.patch.object(higher_owed, 'owed_kind', return_value='stpm'):
            fact = higher_results.academic_fact(SimpleNamespace(), lambda: spm)
        self.assertEqual(_codes(fact), ['academic_missing_subjects', 'results_slip_name_near',
                                        'higher_results_not_on_file'])


class TestTheRedCodesHaveOneHome(SimpleTestCase):

    def test_every_red_code_is_raised_by_an_academic_card(self):
        """No dead entry: each code is an `_item('<code>'` the SPM or the higher card raises (the SPM
        grade pair is built as `'academic_grade_band_mismatch' if ... else 'academic_grade_mismatch'`)."""
        src = ((_SCHOLARSHIP / 'verdict_academic.py').read_text(encoding='utf-8')
               + (_SCHOLARSHIP / 'higher_results.py').read_text(encoding='utf-8'))
        raised = set(re.findall(r"'((?:academic|results_slip|higher_results)_[a-z_]+)'", src))
        self.assertEqual(verdict_ladder.ACADEMIC_RED_CODES - raised, set())

    def test_no_red_code_is_a_confident_disqualifier(self):
        """Why the server must order them: the web's subtitle promotes only confident disqualifiers and
        otherwise shows `unresolved[0]`."""
        self.assertEqual(verdict_ladder.ACADEMIC_RED_CODES & set(award.CONFIDENT_DISQUALIFIERS), set())

    def test_amber_and_grey_lines_are_not_red(self):
        for code in ('results_slip_name_near', 'results_slip_unreadable', 'academic_grade_uncertain',
                     'academic_grades_unchecked', 'higher_results_name_near', 'higher_results_unverified',
                     'higher_results_cgpa_unread', 'higher_results_grade_uncertain',
                     'higher_results_subjects_unrecognised', 'higher_results_not_final'):
            with self.subTest(code=code):
                self.assertNotIn(code, verdict_ladder.ACADEMIC_RED_CODES)
