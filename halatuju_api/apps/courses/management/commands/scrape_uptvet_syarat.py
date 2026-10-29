"""Fetch the public UP_TVET course pages ("Pra-Syarat Kursus") for a catalogue CSV (Bumi Sprint F1).

`scrape_uptvet` writes the catalogue; each row's `info_url` (`awam-kursus/kursus?id_kursus=N`) is a
static, public HTML page whose `div.requirement-card` blocks carry the entry requirements and whose
header names the campus. This command saves those pages, one file per `id_kursus`, into a CACHE folder
(gitignored), so the parser (`tvet_syarat.py`) and the review file are rebuilt offline and a re-run
only fetches what is missing. NO DB writes.

    python manage.py scrape_uptvet_syarat --csv data/tvet/uptvet_latest.csv --limit 10   # validate first
    python manage.py scrape_uptvet_syarat --csv data/tvet/uptvet_latest.csv               # every Awam row
    python manage.py scrape_uptvet_syarat --families iljtm,ilkbs --refresh                # re-fetch some

Polite: one request at a time, `--delay` seconds apart (default 1.5). Resumable: a cached page is
never fetched again unless `--refresh`. LOUD: a page with no requirement card is not cached (a login
wall, an error page or a DOM change would otherwise be parsed as "no requirements"); it is listed
and the command exits with an error after the run, so nothing quietly reads as open.
"""
import csv
import os
import time
import urllib.request

from django.core.management.base import BaseCommand, CommandError

from apps.courses.tvet_families import family_of

DEFAULT_CACHE = os.path.join('data', 'tvet', 'pages')
CARD_MARKER = 'requirement-card'
USER_AGENT = 'Mozilla/5.0 (compatible; HalaTuju course guide; +https://halatuju.xyz)'


def select_rows(rows, sektor='Awam', families=None):
    """Catalogue rows in scope: the sektor (case-insensitive), and when given, only these families."""
    wanted = {f.strip() for f in families or [] if f.strip()}
    return [r for r in rows
            if (r.get('sektor') or '').strip().lower() == sektor.lower()
            and (not wanted or family_of(r.get('institution')) in wanted)]


def page_path(cache_dir, id_kursus):
    return os.path.join(cache_dir, f'{id_kursus}.html')


def fetch(url, timeout=30):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode('utf-8', 'replace')


class Command(BaseCommand):
    help = 'Save the public UP_TVET course pages (entry requirements) for a catalogue CSV (no DB writes)'

    def add_arguments(self, parser):
        parser.add_argument('--csv', default=os.path.join('data', 'tvet', 'uptvet_latest.csv'))
        parser.add_argument('--sektor', default='Awam', help='Awam (public, the default) or Swasta')
        parser.add_argument('--families', default='', help='Comma list of provider families (tvet_families.py)')
        parser.add_argument('--limit', type=int, default=0, help='Fetch at most N pages (0 = all)')
        parser.add_argument('--delay', type=float, default=1.5, help='Seconds between requests (>= 1.5)')
        parser.add_argument('--cache-dir', default=DEFAULT_CACHE, help='Where pages are saved (gitignored)')
        parser.add_argument('--refresh', action='store_true', help='Re-fetch pages already cached')

    def handle(self, *args, **options):
        if options['delay'] < 1.5:
            raise CommandError('--delay must be at least 1.5 seconds (be polite to UP_TVET).')
        try:
            with open(options['csv'], encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
        except FileNotFoundError:
            raise CommandError(f"CSV not found: {options['csv']} (run scrape_uptvet first)")
        rows = select_rows(rows, options['sektor'], options['families'].split(','))
        cache = options['cache_dir']
        os.makedirs(cache, exist_ok=True)
        todo = [r for r in rows if options['refresh'] or not os.path.exists(page_path(cache, r['id_kursus']))]
        cached = len(rows) - len(todo)
        if options['limit']:
            todo = todo[:options['limit']]
        self.stdout.write(f'{len(rows)} rows in scope; {cached} already cached; fetching {len(todo)}.')
        failures = []
        for n, row in enumerate(todo, 1):
            if n > 1:
                time.sleep(options['delay'])
            try:
                html = fetch(row['info_url'])
            except Exception as exc:  # network / HTTP error: report, keep going
                failures.append(f"{row['id_kursus']}: {exc}")
                continue
            if CARD_MARKER not in html:
                failures.append(f"{row['id_kursus']}: no requirement card on {row['info_url']}")
                continue
            with open(page_path(cache, row['id_kursus']), 'w', encoding='utf-8', newline='\n') as f:
                f.write(html)
            if n % 25 == 0:
                self.stdout.write(f'  {n}/{len(todo)} fetched')
        self.stdout.write(f'Done: {len(todo) - len(failures)} saved to {cache}, {len(failures)} failed.')
        if failures:
            raise CommandError('Pages NOT saved (fix or re-run; never parse these as open):\n  '
                               + '\n  '.join(failures))
