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
