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
import copy

from apps.courses.tvet_syarat import academic_gate_hits, parse_requirements

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


class TestAcademicCardGates:
    """Review 2026-10-29: a gate written INSIDE an academic option is still a gate. Every line of every
    option is read (an SVM / Tahfiz / open option too, and the text before an option's first item)."""

    def test_gender_and_disability_lines_in_an_academic_card_are_flagged(self):
        reasons = parsed('52502')['unparsed']   # "Temuduga bagi: 1. Perempuan 2. Orang Kurang Upaya ..."
        assert any(u.startswith('gender condition inside academic card') for u in reasons)
        assert any(u.startswith('no_disability condition inside academic card') for u in reasons)

    def _with_line(self, kid, option_index, line):
        p = copy.deepcopy(page(kid))
        card = next(c for c in p['cards'] if 'AKADEMIK' in c['title'].upper())
        card['options'][option_index]['body'].insert(0, ('text', line))
        return parse_requirements(p)

    def test_religion_in_a_non_spm_option_is_flagged(self):
        r = self._with_line('18170', 2, '1. beragama Islam')   # the Tahfiz route's own option
        assert any(u.startswith('religion condition inside academic card') for u in r['unparsed'])

    def test_gender_in_the_open_option_is_flagged_although_the_card_is_open(self):
        r = self._with_line('18170', 0, 'Lelaki sahaja')
        assert any(u.startswith('gender condition inside academic card') for u in r['unparsed'])

    def test_text_before_the_first_spm_item_is_read(self):
        r = self._with_line('33768', 0, 'Calon Bumiputera Sahaja')
        assert any(u.startswith('req_bumiputera condition inside academic card') for u in r['unparsed'])

    def test_a_citizenship_line_is_allowed_when_the_page_sets_it_elsewhere(self):
        r = self._with_line('18170', 1, 'Warganegara Malaysia')
        assert not r['unparsed'] and r['fields']['req_malaysian']

    def test_the_qualified_disability_sentence_is_text_never_a_gate(self):
        line = ('Calon tidak mempunyai ketidakupayaan penglihatan, pendengaran, fizikal atau mental yang '
                'menyukarkan kerja-kerja amali.')
        r = self._with_line('18170', 1, line)
        assert not r['unparsed'] and not r['fields']['no_disability']
        assert academic_gate_hits({'title': '', 'subtitle': '', 'options': [
            {'heading': line, 'body': []}]}) == []

    @pytest.mark.parametrize('kid', ['18170'])
    def test_a_tahfiz_certificate_route_beside_an_spm_route_is_allowed(self, kid):
        r = parsed(kid)   # options: no formal education ATAU SPM ATAU a Sijil Tahfiz Malaysia
        tahfiz = [o for c in page(kid)['cards'] for o in c['options'] if 'Tahfiz' in o['heading']]
        assert tahfiz and not r['unparsed'] and r['open']


class TestAgeText:
    def test_a_numbered_age_line_loses_its_number(self):
        assert parsed('51431')['fields']['remarks'].startswith('Umur 17 hingga 30 tahun.')


class TestMaraWording:
    """Bumi Sprint F2: MARA's own wording (GIATMARA, IKM, KKTM), on its saved pages. The F1 file and the F1b
    fix still rebuild byte for byte from the same parser (`test_ingest_tvet_courses`, `test_fix_held_tvet_flags`)."""

    def test_bare_headings_are_citizenship_and_bumiputera(self):
        # "[Syarat Wajib] Warganegara" / "[Syarat Wajib] Calon Bumiputera" (and "Bumiputera") over the full line
        for kid in ('1142', '48269', '12575'):
            f = parsed(kid)['fields']
            assert f['req_bumiputera'] and f['req_malaysian'], kid

    def test_bumiputera_of_sabah_or_sarawak_is_bumiputera(self):
        r = parsed('13703')   # "Bumiputera / Bumiputera Sabah atau Sarawak" then "Calon Bumiputera Sahaja"
        assert not r['unparsed'] and r['fields']['req_bumiputera']

    def test_a_page_silent_on_bumiputera_and_citizenship_sets_neither(self):
        f = parsed('30784')['fields']   # GIATMARA Ayer Hitam: no Warganegara, no Bumiputera card
        assert not f['req_bumiputera'] and not f['req_malaysian']

    def test_the_blanket_oku_wording_is_no_disability(self):
        f = parsed('48269')['fields']   # "Tidak menerima sebarang jenis Orang Kurang Upaya"
        assert f['no_disability']

    def test_a_blanket_exclusion_in_a_card_summary_is_a_gate(self):
        r = parsed('51470')   # summary "Sihat tubuh badan (Tidak menerima sebarang OKU)", body only health
        assert r['fields']['no_disability'] and any('read from its summary' in w for w in r['warnings'])

    def test_two_gates_on_one_line_are_both_read(self):
        f = parsed('1124')['fields']   # "Sihat tubuh badan (Tidak menerima sebarang OKU) dan TIDAK RABUN WARNA"
        assert f['no_disability'] and f['no_colorblind'] and 'Sihat tubuh badan' in f['remarks']

    def test_gender_in_a_card_summary_is_flagged(self):
        p = copy.deepcopy(page('30784'))
        p['cards'][0]['subtitle'] = 'Lelaki sahaja'
        assert any(u.startswith('gender condition in card') for u in parse_requirements(p)['unparsed'])

    def test_unrecognised_gate_wording_in_a_summary_is_flagged(self):
        p = copy.deepcopy(page('30784'))
        p['cards'][0]['subtitle'] = 'OKU pendengaran tidak diterima'
        assert any('wording in card' in u for u in parse_requirements(p)['unparsed'])

    def test_not_having_finished_school_is_open(self):
        r = parsed('12575')   # PENDIDIKAN: "Syarat minima: Tidak Tamat Sekolah"
        assert r['open'] and not r['unparsed'] and r['fields']['complex_requirements'] is None

    def test_no_formal_education_under_an_experience_heading_is_not_open(self):
        r = parsed('923')   # "2 tahun pengalaman dalam bidang berkaitan / Tiada Pendidikan Formal ..."
        assert any('no SPM route' in u for u in r['unparsed'])

    def test_a_form_three_route_is_not_open_and_the_spm_route_decides(self):
        r = parsed('51470')   # SKM ATAU SPM (BM, Sejarah) ATAU "Tamat Tingkatan 3 / PT3 ... Tiada Pendidikan Formal"
        assert not r['open'] and r['fields']['pass_bm'] and r['fields']['pass_history']

    def test_an_spm_option_naming_vocational_groups_is_still_spm(self):
        r = parsed('1142')   # heading names "kumpulan Vokasional ... (MPV)"; the body is SPM items
        assert not r['unparsed']
        [block] = blocks('1142')
        assert block['groups'][0] == {'count': 1, 'grade': 'D', 'subjects': ['math']}
        assert 'phy' in block['groups'][1]['subjects'] and block['groups'][1]['grade'] == 'C'

    def test_an_spm_slash_skm_heading_over_an_spm_body_is_spm(self):
        [block] = blocks('13703')   # "Sijil Pelajaran Malaysia (SPM) / Sijil Kemahiran Malaysia (SKM)"
        assert block['counted'] == ['bm', 'hist'] and block['remaining'][0]['count'] == 2

    def test_the_mpak_papers_are_real_subjects_off_the_grade_form(self):
        assert tvet_subject_keys('MATEMATIK (MPAK)') == [] and tvet_subject_keys('LUKISAN GEOMETRI & MESIN') == []
        assert any('MATEMATIK (MPAK)' in w for w in parsed('13703')['warnings'])

    def test_a_heading_asking_more_credits_than_the_table_goes_to_the_remarks(self):
        r = parsed('1142')   # "tiga (3) kepujian ... Matematik" over Matematik at D (a remedial Maths note)
        assert r['header_mismatches'] == 1 and 'Program Remedial Matematik' in r['fields']['remarks']

    def test_gig_worker_wording_is_flagged(self):
        assert any('Pekerja Industri GIG' in u for u in parsed('53518')['unparsed'])


class TestMaraOnTheEngine:
    """A reading every applicant meets is the wrong reading (lesson): the general subjects alone never
    meet a MARA academic row, and the strict count-once reading holds."""

    def _eligible(self, kid, grades, disability=False):
        student = StudentProfile(grades=grades, gender='Lelaki', nationality='Warganegara', colorblind=False,
                                 disability=disability)
        student.bumiputera = True
        return check_eligibility(student, dict(parsed(kid)['fields'], course_id=kid))[0]

    def test_the_general_subjects_alone_are_not_enough(self):
        assert not self._eligible('1142', {'bm': 'A', 'hist': 'A'})
        assert not self._eligible('13703', {'bm': 'A', 'hist': 'A'})

    def test_bm_and_sejarah_cannot_also_be_the_other_credit(self):
        # 1142: BM, Sejarah, English pass; Maths D; a science C; and ONE OTHER subject at C
        base = {'bm': 'A', 'hist': 'A', 'eng': 'E', 'math': 'D', 'phy': 'C'}
        assert not self._eligible('1142', base)
        assert self._eligible('1142', dict(base, geo='C'))

    def test_two_more_credits_excluding_the_listed_papers(self):
        assert not self._eligible('13703', {'bm': 'E', 'hist': 'E', 'math': 'C'})
        assert self._eligible('13703', {'bm': 'E', 'hist': 'E', 'math': 'C', 'eng': 'C'})

    def test_a_disabled_student_is_refused_a_blanket_oku_row(self):
        assert not self._eligible('51470', {'bm': 'E', 'hist': 'E'}, disability=True)
        assert self._eligible('51470', {'bm': 'E', 'hist': 'E'})


def _condition_card(number, heading, lines=(), subtitle='', alternatives=None):
    """A synthetic condition card: one option (heading + text lines), or ATAU alternatives."""
    options = alternatives or [(heading, lines)]
    return {'number': number, 'title': 'Syarat', 'subtitle': subtitle, 'joiner': 'DAN',
            'options': [{'label': f'Syarat Pilihan {n}', 'heading': h, 'joiner': 'ATAU' if n > 1 else None,
                         'body': [('text', line) for line in body]}
                        for n, (h, body) in enumerate(options, 1)]}


def _silent_page_with(*cards):
    """GIATMARA Ayer Hitam (30784): no citizenship, Bumiputera, colour or OKU wording anywhere."""
    p = copy.deepcopy(page('30784'))
    p['cards'] += list(cards)
    return parse_requirements(p)


class TestF2ReviewRound1:
    """F2 review round 1: each MARA line rule bites on its own, unknown and/or wording is flagged, and a
    card summary never hides gate wording behind another rule nor re-adds a gate its alternatives dropped."""

    def test_the_silent_page_sets_no_gate(self):
        r = _silent_page_with()
        assert not r['unparsed'] and not any(r['fields'][f] for f in
                                             ('req_malaysian', 'req_bumiputera', 'no_colorblind', 'no_disability'))

    @pytest.mark.parametrize('heading', ['Warganegara', 'Warganegara (wajib)', 'Warganegara Malaysia (Wajib)'])
    def test_a_bare_citizenship_heading_alone_sets_req_malaysian(self, heading):
        r = _silent_page_with(_condition_card('06', heading))
        assert not r['unparsed'] and r['fields']['req_malaysian'] and not r['fields']['req_bumiputera']

    @pytest.mark.parametrize('heading', ['Bumiputera', 'Calon Bumiputera', 'Bumiputera (Wajib)',
                                         'Bumiputera / Bumiputera Sabah atau Sarawak'])
    def test_a_bare_bumiputera_heading_alone_sets_req_bumiputera(self, heading):
        r = _silent_page_with(_condition_card('06', heading))
        assert not r['unparsed'] and r['fields']['req_bumiputera'] and r['fields']['req_malaysian']

    @pytest.mark.parametrize('line', ['2. Tidak Buta Warna', 'Tidak Rabun Warna'])
    def test_not_colour_blind_wording_sets_no_colorblind(self, line):
        r = _silent_page_with(_condition_card('06', 'Tahap Kesihatan', [line]))
        assert not r['unparsed'] and r['fields']['no_colorblind']

    @pytest.mark.parametrize('line', ['Tidak menerima sebaran jenis Orang Kurang Upaya',
                                      '1. Tidak Menerima Sebarang Jenis Kurang Upaya',
                                      'Tidak menerima sebarang Orang Kurang Upaya (OKU)'])
    def test_the_blanket_oku_wording_and_its_typo_set_no_disability(self, line):
        r = _silent_page_with(_condition_card('06', line))
        assert not r['unparsed'] and r['fields']['no_disability']

    def test_a_bare_atau_between_two_spm_rules_is_flagged(self):
        r = parsed('48245')   # "2. ... Kumpulan Matematik/Sains ... C" / "Atau" / "... mata pelajaran lain C"
        assert 'item-level ATAU inside an SPM option: and/or unclear' in r['unparsed']

    def test_gate_wording_beside_another_rule_in_a_summary_is_flagged(self):
        card = _condition_card('06', 'Umur Calon', ['Umur Minimum : 17'], subtitle='Berumur 17 tahun, bukan OKU')
        r = _silent_page_with(card)
        assert any(u.startswith("no_disability wording in card 06's summary") for u in r['unparsed'])
        assert not r['fields']['no_disability']

    def test_a_summary_never_re_adds_a_gate_its_alternatives_dropped(self):
        card = _condition_card('06', '', subtitle='Bumiputera (Wajib)', alternatives=[
            ('Bumiputera', ['Calon Bumiputera Sahaja']), ('Warganegara', ['Warganegara Malaysia Sahaja'])])
        r = _silent_page_with(card)
        assert not r['fields']['req_bumiputera'] and r['fields']['req_malaysian']
        assert any('alternatives disagree' in u for u in r['unparsed'])

    def test_the_same_atau_card_without_a_summary_is_citizen_only(self):
        card = _condition_card('06', '', alternatives=[
            ('Bumiputera', ['Calon Bumiputera Sahaja']), ('Warganegara', ['Warganegara Malaysia Sahaja'])])
        r = _silent_page_with(card)
        assert not r['unparsed'] and r['fields']['req_malaysian'] and not r['fields']['req_bumiputera']
