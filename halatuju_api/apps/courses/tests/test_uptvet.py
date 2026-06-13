"""Tests for the UP_TVET scraper params + coverage-inventory pure helpers.

The Playwright scrape itself is a local admin tool (browser + network) validated by a real
spike run, not in CI. These cover the importable/pure logic.
"""
from apps.courses.management.commands.scrape_uptvet import CATALOG_URL, CSV_FIELDS
from apps.courses.management.commands.audit_uptvet import _norm_inst, summarise, coverage_gap


def _row(inst, sektor='Awam', kod='TVET/QP1', name='Prog'):
    return {'kod_tauliah': kod, 'name': name, 'kategori': 'Sijil Penuh',
            'institution': inst, 'sektor': sektor, 'reg_fee': '', 'tuition_fee': '',
            'id_kursus': '1', 'info_url': '', 'kelayakan_url': ''}


class TestScraperConstants:
    def test_catalog_url_paginated(self):
        assert 'page={page}' in CATALOG_URL and 'mohon.tvet.gov.my' in CATALOG_URL

    def test_csv_captures_sektor_and_ids(self):
        for f in ('sektor', 'institution', 'id_kursus', 'kelayakan_url'):
            assert f in CSV_FIELDS


class TestNormInst:
    def test_case_space_punct_insensitive(self):
        assert _norm_inst('Institut Kemahiran Belia Negara, Melaka') == _norm_inst('INSTITUT KEMAHIRAN BELIA NEGARA MELAKA')

    def test_blank(self):
        assert _norm_inst('') == '' and _norm_inst(None) == ''


class TestSummarise:
    def test_counts_and_sektor_split(self):
        rows = [_row('A', 'Awam'), _row('A', 'Awam'), _row('B', 'Swasta'), _row('C', '')]
        s = summarise(rows)
        assert s['total'] == 4
        assert s['awam'] == 2
        assert s['swasta'] == 1
        assert s['other'] == 1
        assert s['distinct_institutions'] == 3

    def test_by_institution_ranked(self):
        rows = [_row('Big'), _row('Big'), _row('Big'), _row('Small')]
        s = summarise(rows)
        assert s['by_institution'][0] == ('Big', 3)


class TestCoverageGap:
    def test_new_vs_existing_by_name(self):
        rows = [_row('Kolej Agrosains Malaysia'), _row('Institut Kemahiran Belia Negara')]
        existing = ['INSTITUT KEMAHIRAN BELIA NEGARA']  # we already hold this one
        gap = coverage_gap(rows, existing)
        assert 'Kolej Agrosains Malaysia' in gap['new_institutions']
        assert 'Institut Kemahiran Belia Negara' in gap['existing_institutions']

    def test_awam_new_programme_count(self):
        rows = [
            _row('New Co', 'Awam'),       # new + awam -> counts
            _row('New Co', 'Swasta'),     # new but swasta -> excluded
            _row('Held Co', 'Awam'),      # awam but already held -> excluded
        ]
        gap = coverage_gap(rows, ['Held Co'])
        assert gap['awam_new_programmes'] == 1

    def test_blank_institution_ignored(self):
        rows = [_row('', 'Awam'), _row('Real', 'Awam')]
        gap = coverage_gap(rows, [])
        assert gap['new_institutions'] == ['Real']
