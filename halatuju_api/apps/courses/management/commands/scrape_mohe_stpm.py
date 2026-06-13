"""
Scrape programmes from the MOHE ePanduan portal — STPM (degree) or SPM (post-SPM) track.

Outputs a CSV with: course_id, course_name, university, merit, stream, mohe_url, badges, year
This CSV is the input for the sync command (sync_stpm_mohe for STPM, sync_spm_mohe for SPM).

The portal exposes the same card structure under two ``jenprog`` values — ``stpm`` (degree,
categories S/A) and ``spm`` (Asasi/diploma/cert at Poly/KK/UA, categories A=current-year /
B=past-year). The parser is identical; only the listing URL's ``jenprog`` + the detail-URL
suffix differ, so one scraper serves both via --jenprog.

Usage:
    # STPM (default — unchanged behaviour)
    python manage.py scrape_mohe_stpm --output data/stpm/mohe_latest.csv
    python manage.py scrape_mohe_stpm --output data/stpm/mohe_latest.csv --category S
    # SPM (post-SPM catalogue; defaults to category A = current year)
    python manage.py scrape_mohe_stpm --jenprog spm --output data/spm/mohe_latest.csv
    python manage.py scrape_mohe_stpm --jenprog spm --category A --max-pages 1 --output /tmp/spike.csv
"""
import csv
import re
import time

from django.core.management.base import BaseCommand, CommandError


MOHE_DETAIL_BASE = 'https://online.mohe.gov.my/epanduan/carianNamaProgram'


def detail_url(code, cat_code, jenprog):
    """Build the ePanduan programme-detail URL for a scraped card (pure, testable).

    ``jenprog`` ('stpm'|'spm') is the trailing path segment — the only part that differs
    between the two tracks, so the same builder serves both."""
    if not code:
        return ''
    prefix = code[:2]
    return f'{MOHE_DETAIL_BASE}/{prefix}/{code}/{cat_code}/{jenprog}'


def scrape_shortfall(actual, expected, tolerance=0.95):
    """True when a scrape looks incomplete — far fewer programmes than MOHE's own
    reported total (the 'daripada N' count it prints on page 1). Guards against a
    silent DOM-change failure that returns partial/zero cards. ``expected == 0``
    means we couldn't read the total, so we can't judge → treated as not-a-shortfall."""
    return expected > 0 and actual < expected * tolerance


LISTING_URL = 'https://online.mohe.gov.my/epanduan/ProgramPengajian/kategoriCalon/{cat}?jenprog={jenprog}&page={page}'

# Candidate categories per jenprog. STPM = the two streams (unchanged). SPM defaults to the
# current-year category only (A) — a refresh wants the live catalogue, not past-year (B), which
# stays available via --category B.
JENPROG_CATEGORIES = {
    'stpm': [('S', 'science'), ('A', 'arts')],
    'spm': [('A', 'current')],
}
# All categories that may be requested via --category for each jenprog (validates the filter).
JENPROG_ALL_CATEGORIES = {
    'stpm': [('S', 'science'), ('A', 'arts')],
    'spm': [('A', 'current'), ('B', 'past')],
}

# Back-compat alias: the STPM categories (some tests/tools import CATEGORIES directly).
CATEGORIES = JENPROG_CATEGORIES['stpm']


class Command(BaseCommand):
    help = 'Scrape STPM programmes from MOHE ePanduan portal'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', type=str, required=True,
            help='Output CSV file path',
        )
        parser.add_argument(
            '--jenprog', type=str, default='stpm', choices=sorted(JENPROG_CATEGORIES),
            help='Which ePanduan track to scrape: stpm (degree, default) or spm (post-SPM catalogue).',
        )
        parser.add_argument(
            '--category', type=str, default='',
            help='Scrape only one category. STPM: S (science) / A (arts). '
                 'SPM: A (current year) / B (past year). Default: the jenprog default set.',
        )
        parser.add_argument(
            '--delay', type=float, default=1.0,
            help='Seconds to wait between page loads (be polite to MOHE servers)',
        )
        parser.add_argument(
            '--max-pages', type=int, default=0,
            help='Stop after this many listing pages per category (0 = no limit). '
                 'Use a small value for a quick parser-validation spike.',
        )
        parser.add_argument(
            '--allow-partial', action='store_true',
            help='Write the CSV even if far fewer programmes were scraped than MOHE reports '
                 '(use only when MOHE genuinely has fewer programmes, not when the parser broke).',
        )

    def handle(self, *args, **options):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.stderr.write(self.style.ERROR(
                'playwright is not installed. Run: pip install playwright && playwright install chromium'
            ))
            return

        output_path = options['output']
        delay = options['delay']
        jenprog = options['jenprog']
        max_pages = options['max_pages']
        cat_filter = options['category'].upper()

        categories = JENPROG_CATEGORIES[jenprog]
        if cat_filter:
            valid = JENPROG_ALL_CATEGORIES[jenprog]
            categories = [(c, s) for c, s in valid if c == cat_filter]
            if not categories:
                raise CommandError(
                    f'--category {cat_filter} is not valid for --jenprog {jenprog}. '
                    f'Valid: {", ".join(c for c, _ in valid)}.'
                )

        all_programmes = []
        expected_total = 0  # sum of MOHE's own "daripada N" counts, for the sanity check

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for cat_code, stream_name in categories:
                self.stdout.write(f'\nScraping category {cat_code} ({stream_name})...')
                page_num = 1

                while True:
                    url = LISTING_URL.format(cat=cat_code, jenprog=jenprog, page=page_num)
                    page.goto(url, wait_until='domcontentloaded')
                    # Wait for programme cards to render (executive-data-value elements)
                    try:
                        page.wait_for_selector('.executive-data-value', timeout=30000)
                    except Exception:
                        self.stdout.write('  Warning: timed out waiting for cards to load')
                    # Brief extra wait for any remaining JS rendering
                    page.wait_for_timeout(2000)

                    # Extract total from heading "Paparan X - Y daripada Z carian"
                    heading_text = ''
                    for h5 in page.query_selector_all('h5'):
                        text = h5.inner_text()
                        if 'daripada' in text:
                            heading_text = text
                            break

                    if page_num == 1:
                        total_match = re.search(r'daripada (\d+)', heading_text)
                        total = int(total_match.group(1)) if total_match else 0
                        expected_total += total
                        self.stdout.write(f'  Found {total} programmes')

                    # Parse programme cards
                    cards = self._parse_cards(page, cat_code, stream_name, jenprog)
                    if not cards:
                        break

                    all_programmes.extend(cards)
                    self.stdout.write(
                        f'  Page {page_num}: {len(cards)} programmes '
                        f'(total so far: {len(all_programmes)})'
                    )

                    # Stop early for a parser-validation spike.
                    if max_pages and page_num >= max_pages:
                        self.stdout.write(f'  Reached --max-pages={max_pages}, stopping this category.')
                        break

                    # Check if there's a next page
                    next_link = page.query_selector(f'a[href*="page={page_num + 1}"]')
                    if not next_link:
                        break

                    page_num += 1
                    time.sleep(delay)

            browser.close()

        # Write CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'course_id', 'course_name', 'university', 'merit',
                'stream', 'mohe_url', 'badges', 'year',
            ])
            writer.writeheader()
            writer.writerows(all_programmes)

        self.stdout.write(self.style.SUCCESS(
            f'\nDone: {len(all_programmes)} programmes written to {output_path}'
        ))

        # Sanity check: did we scrape roughly what MOHE says it has? A silent DOM
        # change returns partial/zero cards — fail loudly so a bad CSV is never synced.
        actual_total = len(all_programmes)
        # A --max-pages run is a deliberate partial scrape, so the shortfall guard would
        # always trip — skip it (the guard only protects full refresh runs that feed a sync).
        if max_pages:
            self.stdout.write(self.style.NOTICE(
                '\n(--max-pages set: this is a partial spike, shortfall guard skipped. '
                'Do NOT feed this CSV to a sync.)'
            ))
        elif scrape_shortfall(actual_total, expected_total) and not options['allow_partial']:
            raise CommandError(
                f'Scrape looks INCOMPLETE: got {actual_total} programmes but MOHE reports '
                f'{expected_total}. The CSV was written to {output_path} for inspection, but '
                f'do NOT sync it — the likely cause is a MOHE site change breaking the parser. '
                f'Fix the scraper, or pass --allow-partial if MOHE genuinely has fewer programmes.'
            )

    def _parse_cards(self, page, cat_code, stream_name, jenprog='stpm'):
        """Parse programme cards from the current page."""
        cards = page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const nameLinks = document.querySelectorAll('a[href="#"]');

            for (const link of nameLinks) {
                // Walk up to find the card container (must have executive-data-value elements)
                let card = link;
                for (let i = 0; i < 8; i++) {
                    card = card.parentElement;
                    if (!card) break;
                    if (card.querySelectorAll('.executive-data-value').length >= 2) break;
                }
                if (!card || !card.querySelectorAll('.executive-data-value').length) continue;

                // Extract name (strip # markers and whitespace)
                const name = link.textContent.replace(/#/g, '').trim();
                if (!name || name === 'Program Pengajian') continue;

                // Extract university from <p> tag near the link
                const uniP = link.parentElement?.querySelector('p');
                const university = uniP ? uniP.textContent.trim() : '';

                // Extract structured data fields
                const labels = card.querySelectorAll('.executive-data-label');
                const values = card.querySelectorAll('.executive-data-value');
                const data = {};
                for (let k = 0; k < labels.length; k++) {
                    data[labels[k].textContent.trim()] = values[k]?.textContent?.trim() || '';
                }

                const code = data['KOD PROGRAM'] || '';
                if (!code || seen.has(code)) continue;
                seen.add(code);

                const meritRaw = data['PURATA MARKAH MERIT'] || '';
                const meritMatch = meritRaw.match(/([\\.\\d]+)%/);
                const merit = meritMatch ? meritMatch[1] : '';

                const year = data['TAHUN'] || '';

                // Extract badges (within THIS card only)
                const badgeEls = card.querySelectorAll('[class*="cursor"]');
                const badges = [];
                for (const b of badgeEls) {
                    const t = b.textContent.trim();
                    if (t && t !== '#' && !t.includes('Merit') && t.length < 30) {
                        badges.push(t);
                    }
                }

                results.push({ name, university, code, merit, year, badges: badges.join('|') });
            }
            return results;
        }""")

        programmes = []
        for item in cards:
            programmes.append({
                'course_id': item['code'],
                'course_name': item['name'],
                'university': item['university'],
                'merit': item['merit'],
                'stream': stream_name,
                'mohe_url': detail_url(item['code'], cat_code, jenprog),
                'badges': item['badges'],
                'year': item['year'],
            })

        return programmes
