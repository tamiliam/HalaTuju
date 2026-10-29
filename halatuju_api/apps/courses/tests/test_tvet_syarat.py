"""UP_TVET Sprint F1: the course-page reader and the requirement parser, one test per shape, on pages
saved from the public portal (`fixtures/tvet_pages/<id_kursus>.html`, trimmed: no contact person).

The owner's rulings these pin (decisions.md 2026-10-29): a "no formal education" option makes the card
open; only the SPM option is the academic rule; age / health are TEXT; colour-blindness, citizenship,
Bumiputera and "Bujang" are flags; gender or religion wording, an unknown line, or a card with no SPM
route is UNPARSED; inside an SPM option each subject counts once; the table wins over its heading.
"""
from pathlib import Path

import pytest

from apps.courses.engine import StudentProfile, check_eligibility
from apps.courses.spm_count_once import count_once_failure
from apps.courses.tvet_pages import card_text, read_page
from apps.courses.tvet_subjects import tvet_subject_keys
from apps.courses.tvet_syarat import parse_requirements

PAGES = Path(__file__).resolve().parent / 'fixtures' / 'tvet_pages'


def page(kid):
    return read_page((PAGES / f'{kid}.html').read_text(encoding='utf-8'))


def parsed(kid):
    return parse_requirements(page(kid))


def blocks(kid):
    return (parsed(kid)['fields']['complex_requirements'] or {}).get('count_once', [])


class TestReadPage:
    def test_reads_the_title_campus_and_cards(self):
        p = page('33935')
        assert p['name'] == 'Sijil Teknologi Pembuatan (Pemesinan)'
        assert p['institution'] == 'ADTEC JTM KAMPUS PEDAS (ILP PEDAS)' and p['negeri'] == 'NEGERI SEMBILAN'
        assert p['tempoh'] == '27 Bulan'
        assert [c['title'] for c in p['cards']] == ['Umur', 'Warganegara', 'Syarat Persekolahan',
                                                     'Syarat Am Kemasukan']
        assert [c['joiner'] for c in p['cards']] == [None, 'DAN', 'DAN', 'DAN']
        options = p['cards'][2]['options']
        assert [o['label'] for o in options] == ['Syarat Pilihan 1', 'Syarat Pilihan 2']
        assert options[1]['joiner'] == 'ATAU'

    def test_a_table_is_one_token_in_document_order(self):
        body = page('33935')['cards'][2]['options'][0]['body']
        assert body[:3] == [('text', 'Calon mestilah'), ('text', '1. Tamat Tingkatan 5'), ('text', 'Bil. Subjek : 2')] \
            or body[0] == ('text', '1. Tamat Tingkatan 5')
        table = [v for k, v in body if k == 'table'][0]
        assert table['rows'] == [['1103', 'BAHASA MELAYU'], ['1249', 'SEJARAH']]

    def test_card_text_is_the_reviewers_source(self):
        assert 'Tiada Pendidikan Formal' in card_text(page('33935')['cards'][2])


class TestOpenAndConditions:
    def test_a_no_formal_education_option_makes_the_card_open(self):
        r = parsed('33935')
        assert r['open'] and not r['unparsed']
        f = r['fields']
        assert f['complex_requirements'] is None and not f.get('pass_bm') and f['min_credits'] == 0

    def test_citizenship_and_colour_blindness_are_flags_age_and_health_are_text(self):
        f = parsed('33935')['fields']
        assert f['req_malaysian'] and f['no_colorblind']
        assert not f['no_disability']   # the QUALIFIED "... yang menyukarkan kerja amali" is text
        assert f['remarks'].startswith('Umur 17-35 tahun.') and 'Sihat tubuh badan' in f['remarks']
        assert 'menyukarkan kerja-kerja amali' in f['remarks']

    def test_bumiputera_only(self):
        f = parsed('35006')['fields']   # GIATMARA (Sprint F2's data; the parser is shared)
        assert f['req_bumiputera'] and f['req_malaysian']

    def test_bumiputera_or_citizen_is_citizen_only(self):
        r = parsed('29731')   # PERDA-TECH: "Calon Bumiputera Sahaja" ATAU "Warganegara Malaysia Sahaja"
        assert r['fields']['req_malaysian'] and not r['fields']['req_bumiputera']

    def test_bujang_is_shown_never_gated(self):
        assert parsed('45223')['fields']['single']   # the engine reads `single` as display only

    def test_interview(self):
        f = parsed('10007')['fields']
        assert f['req_interview'] and 'temuduga' in f['remarks']


class TestFlagged:
    def test_gender_wording_is_flagged(self):
        assert any('gender' in u for u in parsed('35192')['unparsed'])

    def test_religion_and_unknown_lines_are_flagged(self):
        reasons = parsed('34523')['unparsed']
        assert any(u.startswith('religion') for u in reasons)
        assert any('hafazan' in u for u in reasons)

    def test_no_spm_route_is_flagged(self):
        assert any('no SPM route' in u for u in parsed('11162')['unparsed'])

    def test_any_n_inside_alternatives_cannot_be_represented(self):
        assert any('inside alternative' in u for u in parsed('1474')['unparsed'])


class TestSpmRules:
    def test_items_in_one_option_count_once(self):
        r = parsed('33768')   # Lulus 2 wajib; 1 Matematik; 1 Sains/Teknikal
        assert not r['unparsed']
        f = r['fields']
        assert f['pass_bm'] and f['pass_history']
        [block] = blocks('33768')
        assert block['counted'] == ['bm', 'hist']
        assert [g['subjects'][:2] for g in block['groups']] == [['math', 'addmath'], ['sci', 'addsci']]

    def test_selain_di_atas_excludes_everything_named_before(self):
        [block] = blocks('10754')   # 3. LULUS satu subjek lain selain di atas (table: "any other")
        assert block['remaining'] == [{'count': 1, 'grade': 'E', 'exclude': ['bm', 'hist', 'math', 'addmath']}]

    def test_a_second_rule_inside_one_item(self):
        r = parsed('10007')   # 2. KEPUJIAN: Bahasa Inggeris, Dan Matematik / ... / Teknikal
        assert r['fields']['credit_english']
        [block] = blocks('10007')
        assert 'eng' in block['counted'] and block['groups'][0]['subjects'][:3] == ['math', 'addmath', 'sci']
        assert block['remaining'][0]['count'] == 1 and 'eng' in block['remaining'][0]['exclude']

    def test_wide_table_wins_over_its_heading(self):
        r = parsed('29731')   # Wajib table says Matematik C; the heading says "remedial if no credit"
        assert r['header_mismatches'] == 1 and 'UP_TVET: "Sekiranya' in r['fields']['remarks']
        [block] = blocks('29731')
        assert {'count': 1, 'grade': 'C', 'subjects': ['math']} in block['groups']

    def test_the_svm_alternative_is_ignored(self):
        r = parsed('33777')
        assert not r['unparsed'] and blocks('33777')[0]['groups'][0]['subjects'] == ['math', 'sci', 'phy', 'chem']


def _student(**grades):
    return StudentProfile(grades=grades, gender='Lelaki', nationality='Warganegara',
                          colorblind=False, disability=False)


class TestEngineOnRealRows:
    """The parsed rows through the engine: a reading every applicant meets would be wrong (lesson)."""

    def _eligible(self, kid, student):
        req = dict(parsed(kid)['fields'], course_id=kid)
        return check_eligibility(student, req)[0]

    def test_only_the_general_subjects_is_not_enough(self):
        assert not self._eligible('10754', _student(bm='E', hist='E'))
        assert not self._eligible('10754', _student(bm='E', hist='E', math='E'))
        assert self._eligible('10754', _student(bm='E', hist='E', math='E', geo='E'))

    def test_add_maths_beside_maths_is_not_another_subject(self):
        grades = {'bm': 'E', 'hist': 'E', 'math': 'E', 'addmath': 'E'}
        assert count_once_failure(grades, blocks('10754'))
        assert not count_once_failure(dict(grades, phy='E'), blocks('10754'))

    def test_one_subject_cannot_fill_two_items(self):
        # 33768: Matematik / Tambahan, then a science; Additional Maths is not on the science list.
        assert count_once_failure({'bm': 'E', 'hist': 'E', 'math': 'E'}, blocks('33768'))
        assert not count_once_failure({'bm': 'E', 'hist': 'E', 'math': 'E', 'phy': 'E'}, blocks('33768'))

    def test_an_open_row_admits_a_student_with_no_results(self):
        assert self._eligible('33935', _student())

    def test_a_foreign_student_is_refused_a_citizens_only_row(self):
        foreign = StudentProfile(grades={}, gender='Lelaki', nationality='Bukan Warganegara',
                                 colorblind=False, disability=False)
        assert not self._eligible('33935', foreign)

    def test_colour_blind_is_refused_where_the_page_says_so(self):
        blind = StudentProfile(grades={}, gender='Lelaki', nationality='Warganegara', colorblind=True,
                               disability=False)
        assert not self._eligible('33935', blind)

    def test_a_disabled_student_is_not_refused_by_the_qualified_text(self):
        disabled = StudentProfile(grades={}, gender='Lelaki', nationality='Warganegara', colorblind=False,
                                  disability=True)
        assert self._eligible('33935', disabled)


class TestSubjectNames:
    @pytest.mark.parametrize('name, keys', [
        ('BAHASA MELAYU', ['bm']), ('MATEMATIK TAMBAHAN', ['addmath']),
        ('ASUHAN DAN PENDIDIKAN AWAL KANAK-KANAK', None),
        ('TEKNOLOGI ELEKTRIK', []), ('NOT A SUBJECT', None),
    ])
    def test_lookup(self, name, keys):
        found = tvet_subject_keys(name)
        if name == 'ASUHAN DAN PENDIDIKAN AWAL KANAK-KANAK':
            assert found and len(found) == 1   # the MOHE table's '&' spelling, folded
        else:
            assert found == keys
