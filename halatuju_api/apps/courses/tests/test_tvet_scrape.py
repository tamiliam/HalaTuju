"""UP_TVET Sprint F1: provider families, the course-page fetcher, and the dashboard's UP_TVET status.

The fetcher's network call is replaced; these pin what it saves, what it refuses (a page with no
requirement card is never cached, and the run fails loudly), and that it is resumable.
"""
import csv
import os
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.courses.course_data_status import UPTVET
from apps.courses.management.commands import scrape_uptvet_syarat as syarat_cmd
from apps.courses.models import CourseDataStatus
from apps.courses.tvet_families import F1_FAMILIES, family_of


class TestFamilies:
    @pytest.mark.parametrize('name, family', [
        ('ADTEC JTM KAMPUS PEDAS (ILP PEDAS), NEGERI SEMBILAN', 'iljtm'),
        ('INSTITUT TEKNIKAL JEPUN MALAYSIA (JMTI), PULAU PINANG', 'iljtm'),
        ('PROTON INSTITUTE (ADTEC MELAKA), MELAKA', 'iljtm'),
        ('INSTITUT KEMAHIRAN TINGGI BELIA NEGARA PAGOH, JOHOR', 'ilkbs'),
        ('INSTITUT KEMAHIRAN BELIA NEGARA KEMASIK, TERENGGANU', 'ilkbs'),   # KEMASIK is not KEMAS
        ('INSTITUT KEMAHIRAN SUKAN NEGARA (AKBG), SELANGOR', 'ilkbs'),
        ('GIATMARA SEMPORNA, SABAH', 'mara'),
        ('TVETMARA PETALING JAYA (KOLEJ KEMAHIRAN TINGGI MARA PETALING JAYA)', 'mara'),
        ('KAMPUS MALAYSIA CHINA INSTITUT (MCI) - GIATMARA BAGAN DATUK, PERAK', 'mara'),
        ('AKADEMI KEMAHIRAN KEMAS GOPENG, PERAK', 'kemas'),
        ('KOLEJ PERTANIAN MALAYSIA, BUKIT TANGGA, KEDAH', 'pertanian'),
        ('KOLEJ PERIKANAN SULTAN NAZRIN MUIZZUDDIN SHAH LUMUT, PERAK', 'perikanan'),
        ('INSTITUT LATIHAN FAMA KOTA BHARU (ILFKB), KELANTAN', 'fama'),
        ('INSTITUT KRAF NEGARA,\n      SELANGOR', 'kraf'),
        ('KOLEJ UNIVERSITI AGROSAINS MALAYSIA, MELAKA', None),   # unknown: callers flag it
    ])
    def test_family_of(self, name, family):
        assert family_of(name) == family

    def test_f1_is_every_family_but_mara(self):
        assert 'mara' not in F1_FAMILIES and {'iljtm', 'ilkbs', 'kemas', 'fama'} <= set(F1_FAMILIES)


def _catalogue(tmp_path, rows):
    path = tmp_path / 'cat.csv'
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id_kursus', 'institution', 'sektor', 'info_url'])
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


ROWS = [
    {'id_kursus': '1', 'institution': 'ADTEC JTM KAMPUS PEDAS (ILP PEDAS), NEGERI SEMBILAN', 'sektor': 'Awam',
     'info_url': 'https://mohon.tvet.gov.my/awam-kursus/kursus?id_kursus=1'},
    {'id_kursus': '2', 'institution': 'GIATMARA SEMPORNA, SABAH', 'sektor': 'Awam',
     'info_url': 'https://mohon.tvet.gov.my/awam-kursus/kursus?id_kursus=2'},
    {'id_kursus': '3', 'institution': 'KOLEJ SWASTA, SELANGOR', 'sektor': 'Swasta',
     'info_url': 'https://mohon.tvet.gov.my/awam-kursus/kursus?id_kursus=3'},
]
GOOD = '<html><div class="requirement-card">x</div></html>'


class TestScrapeSyarat:
    def test_select_rows_scopes_sektor_and_family(self):
        assert [r['id_kursus'] for r in syarat_cmd.select_rows(ROWS)] == ['1', '2']
        assert [r['id_kursus'] for r in syarat_cmd.select_rows(ROWS, families=['mara'])] == ['2']
        assert [r['id_kursus'] for r in syarat_cmd.select_rows(ROWS, sektor='Swasta')] == ['3']

    def test_saves_pages_and_is_resumable(self, tmp_path):
        cache = tmp_path / 'pages'
        with mock.patch.object(syarat_cmd, 'fetch', return_value=GOOD) as fetch, \
                mock.patch.object(syarat_cmd.time, 'sleep'):
            call_command('scrape_uptvet_syarat', '--csv', _catalogue(tmp_path, ROWS), '--cache-dir', str(cache),
                         stdout=StringIO())
            assert sorted(os.listdir(cache)) == ['1.html', '2.html']
            assert fetch.call_count == 2
            call_command('scrape_uptvet_syarat', '--csv', _catalogue(tmp_path, ROWS), '--cache-dir', str(cache),
                         stdout=StringIO())
            assert fetch.call_count == 2   # nothing fetched twice

    def test_a_page_without_a_requirement_card_is_not_cached_and_fails_loudly(self, tmp_path):
        cache = tmp_path / 'pages'
        with mock.patch.object(syarat_cmd, 'fetch', return_value='<html>Sila log masuk</html>'), \
                mock.patch.object(syarat_cmd.time, 'sleep'):
            with pytest.raises(CommandError, match='no requirement card'):
                call_command('scrape_uptvet_syarat', '--csv', _catalogue(tmp_path, ROWS), '--cache-dir',
                             str(cache), '--limit', '1', stdout=StringIO())
        assert os.listdir(cache) == []

    def test_refuses_an_impolite_delay(self, tmp_path):
        with pytest.raises(CommandError, match='at least 1.5'):
            call_command('scrape_uptvet_syarat', '--csv', _catalogue(tmp_path, ROWS), '--delay', '0.5',
                         stdout=StringIO())


@pytest.mark.django_db
class TestUptvetStatus:
    def test_audit_records_the_dashboard_status(self, tmp_path):
        path = tmp_path / 'cat.csv'
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['institution', 'sektor'])
            writer.writeheader()
            writer.writerows([{'institution': 'A', 'sektor': 'Awam'}, {'institution': 'B', 'sektor': 'Swasta'}])
        call_command('audit_uptvet', '--csv', str(path), stdout=StringIO())
        row = CourseDataStatus.objects.get(key=UPTVET)
        assert row.summary['total'] == 2 and row.summary['awam'] == 1

    def test_the_dashboard_counts_public_programmes_as_available(self):
        from apps.courses.course_data_status import coverage_snapshot, record_status
        record_status(UPTVET, {'total': 1006, 'awam': 943})
        assert coverage_snapshot()['uptvet_available'] == 943
