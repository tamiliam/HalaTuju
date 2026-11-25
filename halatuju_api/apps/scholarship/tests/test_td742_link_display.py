"""TD-742 linkage Phase 1 (owner ruling 25 Nov 2026): the case-page DISPLAY of the identity links.

Display only. These tests pin the four rulings on the new ``display_*`` fields, the junk-name
guard, the readers' guard for NEW reads, and that every DECISION output (the check dicts the gates
read, and ``doc_match_verdict``) is unchanged by the display layer. All names and numbers are fake.
"""
import copy
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.scholarship.doc_parse import parse_by_labels
from apps.scholarship.income_engine import (student_bc_check, student_income_ic_check,
                                            student_income_proof_check, student_str_check)
from apps.scholarship.link_display import (NOT_READ, bc_display, income_ic_display,
                                           income_proof_display, str_display)
from apps.scholarship.name_guard import clean_person_name, name_not_read, pick_name
from apps.scholarship.resolution import doc_match_verdict
from apps.scholarship.serializers.documents import ApplicantDocumentSerializer
from apps.scholarship.tests.test_doc_parse import _KWSP, _LETTER

_STUDENT = 'KAVI A/L RAMAN'
_MOTHER = 'LETCHUMI A/P CONTOH'
_FATHER = 'RAMAN A/L CONTOH'
_MOTHER_NRIC = '760101-04-5002'
_FATHER_NRIC = '730101-04-5001'
_STRANGER = 'SOMEONE ELSE ENTIRELY'
_STRANGER_NRIC = '800808-08-8888'


class _QS(list):
    def order_by(self, *a, **k):
        return self

    def first(self):
        return self[0] if self else None

    def exists(self):
        return bool(self)


class _Docs:
    def __init__(self, docs):
        self._docs = docs

    def filter(self, doc_type=None, household_member=None, household_member__in=None, **kw):
        out = []
        for d in self._docs:
            if doc_type is not None and d.doc_type != doc_type:
                continue
            hm = getattr(d, 'household_member', '')
            if household_member is not None and hm != household_member:
                continue
            if household_member__in is not None and hm not in household_member__in:
                continue
            out.append(d)
        return _QS(out)


def _bc(*, mother_nric=_MOTHER_NRIC, mother=_MOTHER):
    return SimpleNamespace(
        doc_type='birth_certificate', household_member='', vision_run_at=object(), vision_error='',
        vision_fields={'fields': {'bc_child_name': _STUDENT, 'bc_mother_name': mother,
                                  'bc_mother_nric': mother_nric, 'bc_father_name': _FATHER,
                                  'bc_father_nric': _FATHER_NRIC},
                       'student_verdict': 'ok', 'authenticity': {'status': 'genuine'}})


def _ic(*, name=_MOTHER, nric=_MOTHER_NRIC, member='mother'):
    return SimpleNamespace(doc_type='parent_ic', household_member=member, vision_name=name,
                           vision_nric=nric, vision_address='KL', vision_run_at=object(),
                           vision_error='', vision_fields={})


def _str(*, name=_MOTHER, nric=_MOTHER_NRIC):
    return SimpleNamespace(doc_type='str', household_member='',
                           vision_fields={'fields': {'recipient_name': name, 'recipient_nric': nric,
                                                     'status': 'lulus', 'year': '2026'}})


def _slip(*, name=_MOTHER, nric=_MOTHER_NRIC):
    return SimpleNamespace(doc_type='salary_slip', household_member='mother',
                           vision_fields={'fields': {'name': name, 'nric': nric,
                                                     'gross_income': '1500.00', 'period': 'OCT 2026'},
                                          'student_verdict': 'ok'})


def _app(docs, *, route='str'):
    app = SimpleNamespace(income_route=route, income_earner='mother',
                          income_working_members=['mother'] if route == 'salary' else [],
                          profile=SimpleNamespace(name=_STUDENT, nric='050101-04-9999'),
                          cohort=SimpleNamespace(year=2026))
    app.documents = _Docs(docs)
    for d in docs:
        d.application = app
    return app


def _decisions(docs):
    """Every decision output the gates read for these docs, deep-copied."""
    out = []
    for d in docs:
        out.append(copy.deepcopy({
            'str': student_str_check(d), 'ic': student_income_ic_check(d),
            'proof': student_income_proof_check(d), 'bc': student_bc_check(d),
            'verdict': doc_match_verdict(d)}))
    return out


# ── The junk-name guard ──────────────────────────────────────────────────────────
class TestNameGuard(SimpleTestCase):
    def test_punctuation_only_is_not_read(self):
        self.assertEqual(clean_person_name(':'), '')
        self.assertTrue(name_not_read(' : '))

    def test_label_word_is_not_read(self):
        self.assertEqual(clean_person_name('NAMA'), '')
        self.assertEqual(clean_person_name('Nama Penerima'), '')

    def test_under_four_letters_is_not_read(self):
        self.assertEqual(clean_person_name('AB'), '')

    def test_label_with_glued_ic_is_not_read(self):
        self.assertEqual(clean_person_name('NAME 800101-14-1234'), '')

    def test_real_name_keeps_its_name_and_drops_a_glued_ic(self):
        self.assertEqual(clean_person_name('SITI BINTI CONTOH 800101141234'), 'SITI BINTI CONTOH')
        self.assertEqual(clean_person_name(': SITI BINTI CONTOH (800101-14-1234)'), 'SITI BINTI CONTOH')
        self.assertEqual(clean_person_name(_MOTHER), _MOTHER)

    def test_blank_and_none(self):
        self.assertEqual(clean_person_name(None), '')
        self.assertEqual(clean_person_name(''), '')

    def test_pick_name_skips_junk_and_says_when_only_junk_was_found(self):
        self.assertEqual(pick_name(':', None, _MOTHER), (_MOTHER, False))
        self.assertEqual(pick_name(':', 'NAMA', ''), ('', True))
        self.assertEqual(pick_name(None, '', '  '), ('', False))


# ── The readers, for NEW reads only ──────────────────────────────────────────────
class TestReaderGuard(SimpleTestCase):
    def test_str_letter_with_junk_recipient_goes_to_the_ai(self):
        text = _LETTER.replace('AHMAD BIN TESTABU', ':')
        self.assertIsNone(parse_by_labels('str', text))

    def test_str_letter_unchanged_with_a_real_name(self):
        r = parse_by_labels('str', _LETTER)
        self.assertEqual(r['recipient_name'], 'AHMAD BIN TESTABU')

    def test_str_skips_a_junk_candidate_for_a_clean_one(self):
        # The labelled recipient value is junk; the patronymic name line is used instead.
        text = _LETTER.replace('Nama Penerima : AHMAD BIN TESTABU', 'Nama Penerima : NAMA')
        r = parse_by_labels('str', text)
        self.assertEqual(r['recipient_name'], 'AHMAD BIN TESTABU')

    def test_epf_with_junk_member_name_goes_to_the_ai(self):
        self.assertIsNone(parse_by_labels('epf', _KWSP.replace('AHMAD BIN TESTABU', ':', 1)))

    def test_epf_unchanged_with_a_real_name(self):
        self.assertEqual(parse_by_labels('epf', _KWSP)['name'], 'AHMAD BIN TESTABU')


# ── Case 177: chain holds, the STR recipient name read ':' ────────────────────────
class TestCase177Shape(SimpleTestCase):
    def setUp(self):
        self.ic, self.bc, self.str_doc = _ic(), _bc(), _str(name=':')
        _app([self.ic, self.bc, self.str_doc])

    def test_str_recipient_row_is_grey_not_read(self):
        out = str_display(self.str_doc, student_str_check(self.str_doc))
        self.assertEqual(out['display_name_status'], NOT_READ)
        self.assertEqual(out['display_nric_status'], 'match')

    def test_parent_ic_shows_no_wrong_card_and_no_red_name_row(self):
        chk = student_income_ic_check(self.ic)
        out = income_ic_display(self.ic, chk)
        self.assertFalse(out['display_wrong_card'])
        self.assertNotEqual(out['display_proof_name_status'], 'mismatch')
        self.assertEqual(out['display_proof_nric_status'], 'match')

    def test_bc_mother_row_green(self):
        self.assertEqual(bc_display(self.bc, student_bc_check(self.bc))['display_mother_status'], 'match')

    def test_decision_fields_are_todays(self):
        # Phase 1 changes no decision: the chain still forces the STR match and the card's
        # decision wrong_card flag is what it was.
        sc = student_str_check(self.str_doc)
        self.assertEqual((sc['name_status'], sc['nric_status']), ('match', 'match'))
        self.assertTrue(student_income_ic_check(self.ic)['wrong_card'])

    def test_serializer_serves_both_side_by_side(self):
        out = ApplicantDocumentSerializer.get_str_check(None, self.str_doc)
        self.assertEqual(out['name_status'], 'match')
        self.assertEqual(out['display_name_status'], NOT_READ)


# ── A clean RED disagreement (no chain) shows on the proof, not on the card ───────
class TestCleanRedOnTheProof(SimpleTestCase):
    def setUp(self):
        self.ic, self.str_doc = _ic(), _str(name=_STRANGER, nric=_STRANGER_NRIC)
        _app([self.ic, self.str_doc])

    def test_str_rows_red(self):
        out = str_display(self.str_doc, student_str_check(self.str_doc))
        self.assertEqual(out['display_name_status'], 'mismatch')
        self.assertEqual(out['display_nric_status'], 'mismatch')

    def test_card_neutral_not_red_and_not_wrong_card(self):
        chk = student_income_ic_check(self.ic)
        self.assertEqual(chk['proof_name_status'], 'mismatch')     # decision unchanged
        out = income_ic_display(self.ic, chk)
        self.assertEqual(out['display_proof_name_status'], 'no_ref')
        self.assertEqual(out['display_proof_nric_status'], 'no_ref')
        self.assertFalse(out['display_wrong_card'])


# ── A real wrong card under the chain still says so, on the card only ─────────────
class TestRealWrongCard(SimpleTestCase):
    def setUp(self):
        self.ic = _ic(name=_FATHER, nric=_FATHER_NRIC)     # the father's card in the mother slot
        self.bc, self.str_doc = _bc(), _str()
        _app([self.ic, self.bc, self.str_doc])

    def test_card_says_wrong_card(self):
        out = income_ic_display(self.ic, student_income_ic_check(self.ic))
        self.assertTrue(out['display_wrong_card'])

    def test_str_and_bc_compared_with_the_chain_anchor_stay_green(self):
        out = str_display(self.str_doc, student_str_check(self.str_doc))
        self.assertEqual((out['display_name_status'], out['display_nric_status']), ('match', 'match'))
        self.assertEqual(bc_display(self.bc, student_bc_check(self.bc))['display_mother_status'], 'match')


# ── A slip group: the chain compared only the first slip ─────────────────────────
class TestSlipGroup(SimpleTestCase):
    def setUp(self):
        self.first, self.blank, self.label = _slip(), _slip(name='', nric=''), _slip(name='NAMA')
        _app([_ic(), _bc(), self.first, self.blank, self.label], route='salary')

    def _display(self, doc):
        return income_proof_display(doc, student_income_proof_check(doc))

    def test_first_slip_green(self):
        out = self._display(self.first)
        self.assertEqual((out['display_name_status'], out['display_nric_status']), ('match', 'match'))

    def test_unread_slip_grey_not_green(self):
        self.assertEqual(student_income_proof_check(self.blank)['name_status'], 'match')   # decision
        out = self._display(self.blank)
        self.assertEqual((out['display_name_status'], out['display_nric_status']), (NOT_READ, NOT_READ))

    def test_label_word_name_grey_number_still_compared(self):
        out = self._display(self.label)
        self.assertEqual((out['display_name_status'], out['display_nric_status']), (NOT_READ, 'match'))


# ── Decisions are byte-identical with the display layer in place ─────────────────
class TestDecisionsUnchanged(SimpleTestCase):
    def _scenarios(self):
        yield [_ic(), _bc(), _str(name=':')], 'str'
        yield [_ic(), _str(name=_STRANGER, nric=_STRANGER_NRIC)], 'str'
        yield [_ic(name=_FATHER, nric=_FATHER_NRIC), _bc(), _str()], 'str'
        yield [_ic(), _bc(), _slip(), _slip(name='', nric=''), _slip(name='NAMA')], 'salary'

    def test_decision_outputs_identical_and_display_keys_only_added(self):
        for docs, route in self._scenarios():
            _app(docs, route=route)
            before = _decisions(docs)
            for d in docs:
                for fn, check in ((str_display, student_str_check), (income_ic_display, student_income_ic_check),
                                  (income_proof_display, student_income_proof_check),
                                  (bc_display, student_bc_check)):
                    chk = check(d)
                    if chk:
                        added = fn(d, chk)
                        self.assertTrue(all(k.startswith('display_') for k in added))
                        self.assertFalse(set(added) & set(chk))
            self.assertEqual(_decisions(docs), before)
