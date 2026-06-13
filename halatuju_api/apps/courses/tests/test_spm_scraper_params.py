"""Tests for the scrape_mohe_stpm parameterisation (jenprog stpm/spm + detail URL builder).

These cover the PURE logic only — the Playwright scrape itself is a local admin tool that
needs a browser + network, so it is validated by a real spike run, not in CI.
"""
from apps.courses.management.commands.scrape_mohe_stpm import (
    LISTING_URL,
    JENPROG_CATEGORIES,
    JENPROG_ALL_CATEGORIES,
    CATEGORIES,
    detail_url,
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
