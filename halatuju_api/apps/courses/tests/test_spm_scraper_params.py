"""Tests for the scrape_mohe_stpm parameterisation (jenprog stpm/spm + detail URL builder).

These cover the PURE logic only — the Playwright scrape itself is a local admin tool that
needs a browser + network, so it is validated by a real spike run, not in CI.
"""
from apps.courses.management.commands.scrape_mohe_stpm import (
    LISTING_URL,
    JENPROG_CATEGORIES,
    JENPROG_ALL_CATEGORIES,
    CATEGORIES,
    bumi_agreement,
    bumi_filter_applied,
    bumi_in_syarat,
    clean_modal_text,
    csv_fieldnames,
    detail_url,
    modal_url,
    syarat_am_text,
)


class TestJenprogCategories:
    def test_stpm_categories_unchanged(self):
        # STPM keeps both streams — back-compat for the existing pipeline.
        assert JENPROG_CATEGORIES['stpm'] == [('S', 'science'), ('A', 'arts')]
        assert CATEGORIES == [('S', 'science'), ('A', 'arts')]

    def test_spm_defaults_to_current_year_only(self):
        # A refresh wants the live catalogue (A), not past-year (B).
        assert JENPROG_CATEGORIES['spm'] == [('A', 'current')]

    def test_spm_past_year_available_but_not_default(self):
        codes_default = [c for c, _ in JENPROG_CATEGORIES['spm']]
        codes_all = [c for c, _ in JENPROG_ALL_CATEGORIES['spm']]
        assert 'B' not in codes_default
        assert 'B' in codes_all and 'A' in codes_all


class TestListingUrl:
    def test_jenprog_is_parameterised(self):
        spm = LISTING_URL.format(cat='A', jenprog='spm', page=1)
        stpm = LISTING_URL.format(cat='S', jenprog='stpm', page=2)
        assert 'jenprog=spm' in spm and 'kategoriCalon/A' in spm and 'page=1' in spm
        assert 'jenprog=stpm' in stpm and 'page=2' in stpm


class TestDetailUrl:
    def test_spm_suffix(self):
        url = detail_url('UK0010001', 'A', 'spm')
        assert url == 'https://online.mohe.gov.my/epanduan/carianNamaProgram/UK/UK0010001/A/spm'

    def test_stpm_suffix_unchanged(self):
        url = detail_url('UM1234567', 'S', 'stpm')
        assert url.endswith('/UM/UM1234567/S/stpm')

    def test_prefix_is_first_two_chars(self):
        assert detail_url('UR4521002', 'A', 'spm').split('/carianNamaProgram/')[1].startswith('UR/')

    def test_empty_code_returns_blank(self):
        assert detail_url('', 'A', 'spm') == ''
        assert detail_url(None, 'A', 'spm') == ''


class TestBumiSyarat:
    # Real MOHE wording (UY0000015, fetched 2026-10-28).
    REAL = ("Mendapat sekurang-kurangnya Gred C dalam mata pelajaran Sejarah. "
            "Berketurunan Melayu, Anak Negeri Sabah, Anak Negeri Sarawak dan Orang Asli sahaja.")

    def test_real_bumi_wording_matches(self):
        assert bumi_in_syarat(self.REAL)

    def test_each_marker_alone_matches(self):
        for t in ['Berketurunan Melayu sahaja', 'Anak Negeri Sabah', 'anak negeri sarawak',
                  'Orang Asli', 'Calon Bumiputera sahaja']:
            assert bumi_in_syarat(t), t

    def test_open_to_non_bumi_does_not_match(self):
        assert not bumi_in_syarat('Terbuka kepada calon Bumiputera dan bukan Bumiputera.')

    def test_plain_requirements_do_not_match(self):
        assert not bumi_in_syarat('Gred C bagi matapelajaran BAHASA MELAYU.')
        assert not bumi_in_syarat('')
        assert not bumi_in_syarat(None)

    def test_feeder_badge_wording_is_not_a_bumi_rule(self):
        # The listing badge "Program Perintis (Feeder) Bumiputera" sits on open programmes too.
        assert not bumi_in_syarat('Program Perintis (Feeder) Bumiputera')


class TestModalHelpers:
    def test_modal_url(self):
        assert modal_url('A', 'UY0000015') == (
            'https://online.mohe.gov.my/epanduan/ProgramPengajian/modalSyarat/A/UY0000015')

    def test_clean_modal_text(self):
        raw = '<div><p>Gred&nbsp;C</p>\n  <li>Orang Asli</li></div>'
        assert clean_modal_text(raw) == 'Gred C Orang Asli'
        assert clean_modal_text('') == ''


class TestBumiFilterGuard:
    def test_narrowed_listing_is_applied(self):
        assert bumi_filter_applied(136, 369)

    def test_full_count_means_filter_not_applied(self):
        assert not bumi_filter_applied(369, 369)

    def test_zero_means_not_applied(self):
        assert not bumi_filter_applied(0, 369)


class TestBumiAgreement:
    def test_all_four_cases(self):
        assert bumi_agreement('Y', 'Y') == 'both'
        assert bumi_agreement('N', 'N') == 'neither'
        assert bumi_agreement('Y', 'N') == 'portal_only'
        assert bumi_agreement('N', 'Y') == 'syarat_only'

    def test_missing_signal_is_blank(self):
        assert bumi_agreement('', 'Y') == ''
        assert bumi_agreement('Y', None) == ''


class TestCsvFieldnames:
    BASE = ['course_id', 'course_name', 'university', 'merit', 'stream', 'mohe_url', 'badges', 'year']

    def test_default_columns_unchanged(self):
        # refresh_stpm and the sync commands read this shape.
        assert csv_fieldnames(False, False) == self.BASE

    def test_bumi_columns_added_only_for_passes_that_ran(self):
        assert csv_fieldnames(True, False) == self.BASE + ['bumi_portal']
        assert csv_fieldnames(False, True) == self.BASE + ['bumi_syarat', 'syarat_khas']
        assert csv_fieldnames(True, True)[-1] == 'bumi_agreement'

    def test_syarat_am_column_is_last_and_opt_in(self):
        assert csv_fieldnames(True, True) == csv_fieldnames(True, True, False)
        assert csv_fieldnames(True, True, True)[-1] == 'syarat_am'
        assert csv_fieldnames(False, False, True) == self.BASE + ['syarat_am']


# A real listing-page fragment (MOHE e-Panduan, SPM category A, 2026-10-29), whitespace trimmed.
LISTING_SNIPPET = (
    '<a class="nav-link" id="syarat-am-tab-UY0000010" href="#syarat-am-UY0000010">Syarat Am</a>'
    '<div class="card border-0 tab-pane fade show active" id="syarat-am-UY0000010" role="tabpanel"'
    ' aria-labelledby="syarat-am-tab-UY0000010"> <div class="pl-2 pb-3"> <ol>'
    ' <li>Warganegara Malaysia yang mempunyai <b>No. Kad Pengenalan / My Kad</b>.</li>'
    ' <li>Memiliki <b>Sijil Pelajaran Malaysia (SPM)</b> dengan mendapat sekurang-kurangnya :-</li>'
    ' <ol type="i"> <li> Gred <b>C</b> bagi matapelajaran <b>BAHASA MELAYU</b>. </li>'
    ' <li> Gred <b>E</b> bagi matapelajaran <b>SEJARAH</b>. </li>'
    ' <li><b>EMPAT (4) C</b> dalam mana-mana matapelajaran yang belum dikira.</li> </ol> </ol> </div>'
    ' <div class="pl-2 pb-3"> <ol> <ol type="i"> </ol> </ol> </div> </div>'
    ' <!--Paparan Syarat khas Tab--> <div class="card border-0 tab-pane fade"'
    ' id="syarat-Khas-UY0000010" role="tabpanel"> Mendapat sekurang-kurangnya Gred C </div>'
)


class TestSyaratAmText:
    def test_reads_the_pane_of_the_named_programme(self):
        assert syarat_am_text(LISTING_SNIPPET, 'UY0000010') == (
            'Warganegara Malaysia yang mempunyai No. Kad Pengenalan / My Kad . Memiliki Sijil '
            'Pelajaran Malaysia (SPM) dengan mendapat sekurang-kurangnya :- Gred C bagi '
            'matapelajaran BAHASA MELAYU . Gred E bagi matapelajaran SEJARAH . EMPAT (4) C dalam '
            'mana-mana matapelajaran yang belum dikira.')

    def test_never_spills_into_the_syarat_khas_pane(self):
        assert 'Mendapat' not in syarat_am_text(LISTING_SNIPPET, 'UY0000010')

    def test_the_tab_link_is_not_the_pane(self):
        # `syarat-am-tab-<code>` must not be mistaken for the pane `syarat-am-<code>`.
        assert syarat_am_text(LISTING_SNIPPET.split('<div class="card')[0], 'UY0000010') == ''

    def test_absent_programme_or_page_is_blank(self):
        assert syarat_am_text(LISTING_SNIPPET, 'UE0545001') == ''
        assert syarat_am_text('', 'UY0000010') == ''
        assert syarat_am_text(None, 'UY0000010') == ''
