"""The SPM Syarat parser (`spm_syarat.py`, Bumi Sprint D1), from REAL MOHE texts — one test per
clause shape — and the whole UiTM batch: 84 parsed, 3 flagged, none guessed."""
import csv
from pathlib import Path

import pytest

from apps.courses.spm_syarat import parse_requirements, subject_keys

DATA = Path(__file__).resolve().parents[3] / 'data' / 'spm' / 'mohe_bumi_2026-10-29.csv'
AM = ('Warganegara Malaysia yang mempunyai No. Kad Pengenalan / My Kad . Memiliki Sijil Pelajaran '
      'Malaysia (SPM) dengan mendapat sekurang-kurangnya :- Gred C bagi matapelajaran BAHASA MELAYU . '
      'Gred E bagi matapelajaran SEJARAH . DUA (2) C dalam mana-mana matapelajaran yang belum dikira.')
BUMI = 'Berketurunan Melayu, Anak Negeri Sabah, Anak Negeri Sarawak dan Orang Asli sahaja.'


def parse(khas, am=AM):
    result = parse_requirements(am, khas)
    return result['fields'], result['unparsed'], result['warnings']


def _rows():
    with open(DATA, encoding='utf-8') as f:
        return {r['course_id']: r for r in csv.DictReader(f)}


class TestSyaratAm:
    def test_flags_and_its_own_block(self):
        fields, unparsed, _ = parse(BUMI)
        assert unparsed == []
        assert fields['req_malaysian'] and fields['credit_bm'] and fields['pass_history']
        assert fields['complex_requirements']['count_once'][0] == {
            'counted': ['bm', 'hist'], 'groups': [],
            'remaining': [{'count': 2, 'grade': 'C', 'exclude': []}]}

    def test_sejarah_at_c_has_no_flag_so_it_is_a_group(self):
        am = AM.replace('Gred E bagi matapelajaran SEJARAH', 'Gred C bagi matapelajaran SEJARAH')
        fields, unparsed, _ = parse(BUMI, am)
        assert unparsed == [] and not fields.get('pass_history')
        assert fields['complex_requirements']['count_once'][0]['groups'] == [
            {'count': 1, 'grade': 'C', 'subjects': ['hist']}]

    @pytest.mark.parametrize('am', ['', 'Warganegara Malaysia yang mempunyai No. Kad Pengenalan / My Kad . '
                                        'Pemohon mestilah menduduki Sijil Pelajaran Malaysia (SPM) dan boleh '
                                        'membaca, menulis dan mengira.'])
    def test_an_unknown_am_shape_is_flagged(self, am):
        assert parse(BUMI, am)[1]


class TestSyaratKhasClauses:
    def test_single_subject_uses_the_exact_flag(self):
        fields, unparsed, _ = parse('Mendapat sekurang-kurangnya Gred B dalam mata pelajaran Bahasa Inggeris. ' + BUMI)
        assert unparsed == [] and fields['credit_eng_b'] and fields['req_bumiputera']

    def test_c_in_matematik_is_not_credit_math(self):
        # `credit_math` means Math OR Add Math, so "C in Matematik" is a one-subject group.
        fields, _, _ = parse('Mendapat sekurang-kurangnya Gred C dalam mata pelajaran Matematik. ' + BUMI)
        assert not fields.get('credit_math')
        assert fields['complex_requirements']['or_groups'] == [{'count': 1, 'grade': 'C', 'subjects': ['math']}]

    def test_one_of_list(self):
        fields, _, _ = parse('Mendapat sekurang-kurangnya Gred C dalam SATU (1) mata pelajaran berikut : '
                             '• Matematik / Matematik Tambahan ' + BUMI)
        assert fields['complex_requirements']['or_groups'] == [
            {'count': 1, 'grade': 'C', 'subjects': ['math', 'addmath']}]

    def test_one_from_each_bullet_becomes_plain_groups(self):
        fields, _, _ = parse('Mendapat sekurang-kurangnya Gred C dalam DUA (2) mata pelajaran berikut : '
                             '• Matematik / Matematik Tambahan • Biologi / Fizik ' + BUMI)
        assert fields['complex_requirements']['or_groups'] == [
            {'count': 1, 'grade': 'C', 'subjects': ['math', 'addmath']},
            {'count': 1, 'grade': 'C', 'subjects': ['bio', 'phy']}]

    def test_a_bullet_of_alternatives_among_others_becomes_a_slotted_block(self):
        fields, _, _ = parse('Mendapat sekurang-kurangnya Gred D dalam DUA (2) mata pelajaran berikut : '
                             '• Geografi / Ekonomi • Biologi • Fizik ' + BUMI)
        block = fields['complex_requirements']['count_once'][1]
        assert block['groups'][0]['slots'] == [['geo', 'ekonomi'], ['bio'], ['phy']]
        assert 'or_groups' not in fields['complex_requirements']

    def test_remaining_with_exclude_puts_the_whole_khas_in_one_block(self):
        rows = _rows()
        fields, unparsed, _ = parse(rows['UE0380001']['syarat_khas'], rows['UE0380001']['syarat_am'])
        assert unparsed == [] and fields['distinction_eng']
        assert 'or_groups' not in fields['complex_requirements']
        assert fields['complex_requirements']['count_once'][1] == {
            'counted': ['eng'],
            'groups': [{'count': 1, 'grade': 'C', 'subjects': ['math', 'addmath']}],
            'remaining': [{'count': 3, 'grade': 'A-', 'exclude': ['eng', 'math', 'addmath']}]}

    @pytest.mark.parametrize('tail', ['yang belum diambil kira', 'yang belum dikira', 'selain diatas'])
    def test_every_remaining_wording(self, tail):
        fields, unparsed, _ = parse(
            f'Mendapat sekurang-kurangnya Gred C dalam mana-mana SATU (1) mata pelajaran {tail} ' + BUMI)
        assert unparsed == []
        assert fields['complex_requirements']['count_once'][1]['remaining'] == [
            {'count': 1, 'grade': 'C', 'exclude': []}]

    def test_the_geomatik_typo(self):
        rows = _rows()
        fields, unparsed, _ = parse(rows['UE4581004']['syarat_khas'], rows['UE4581004']['syarat_am'])
        assert unparsed == []
        assert fields['complex_requirements']['count_once'][1]['remaining'] == [
            {'count': 1, 'grade': 'C', 'exclude': []}, {'count': 1, 'grade': 'E', 'exclude': []}]

    def test_any_five_credits_is_min_credits(self):
        fields, _, _ = parse('Mendapat sekurang-kurangnya Gred C dalam mana-mana LIMA (5) mata pelajaran ' + BUMI)
        assert fields['min_credits'] == 5

    def test_interview(self):
        fields, _, _ = parse('Lulus ujian dan / atau temu duga yang ditetapkan. ' + BUMI)
        assert fields['req_interview']

    def test_no_bumi_sentence_no_bumi_flag(self):
        assert not parse('Mendapat sekurang-kurangnya Gred C dalam mata pelajaran Bahasa Inggeris.')[0]['req_bumiputera']


class TestFlaggedNeverGuessed:
    def test_atau(self):
        assert any('ATAU' in r for r in parse(_rows()['UE4811004']['syarat_khas'])[1])

    def test_two_grades_over_one_list(self):
        assert any('two grades' in r for r in parse(_rows()['UE0520001']['syarat_khas'])[1])

    def test_an_unknown_subject_name(self):
        unparsed = parse('Mendapat sekurang-kurangnya Gred C dalam SATU (1) mata pelajaran berikut : '
                         '• Matematik / Ilmu Ghaib ' + BUMI)[1]
        assert unparsed == ["unknown subject name: 'Ilmu Ghaib'"]

    def test_an_unrecognised_clause(self):
        assert parse('Mendapat sekurang-kurangnya sesuatu yang lain. ' + BUMI)[1]

    def test_a_known_name_without_a_form_key_is_dropped_with_a_warning(self):
        fields, unparsed, warnings = parse(
            'Mendapat sekurang-kurangnya Gred E dalam DUA (2) mata pelajaran berikut : '
            '• Kimia • Pengurusan Ladang ' + BUMI)
        assert unparsed == [] and warnings == ["no grade-form key, dropped from its list: 'Pengurusan Ladang'"]
        assert fields['complex_requirements']['or_groups'][0]['subjects'] == ['chem']


class TestSubjectNames:
    def test_case_insensitive_and_the_arabic_alias(self):
        assert subject_keys('bahasa inggeris') == ['eng']
        assert subject_keys("Al-lughah Al-arabiah Al-mu'asirah") == ['bahasa_arab', 'lughah_arabiah']
        assert subject_keys('Hiasan Dalaman Asas') == subject_keys('Hiasan Dalaman')
        assert subject_keys('Nope') is None


def test_the_uitm_batch():
    """All 87 UiTM rows: 84 parse faithfully and carry the Bumi flag; 3 are flagged for D2."""
    flagged = {}
    for cid, row in _rows().items():
        if not cid.startswith('UE'):
            continue
        fields, unparsed, _ = parse(row['syarat_khas'], row['syarat_am'])
        if unparsed:
            flagged[cid] = unparsed
        else:
            assert fields['req_bumiputera'] and fields['req_malaysian'], cid
    assert sorted(flagged) == ['UE0520001', 'UE0545001', 'UE4811004']
