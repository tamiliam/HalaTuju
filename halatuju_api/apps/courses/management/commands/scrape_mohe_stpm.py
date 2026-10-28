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
    # Bumiputera inventory (two independent signals, see below)
    python manage.py scrape_mohe_stpm --jenprog spm --with-bumi --with-syarat --output data/spm/mohe_bumi.csv

Bumiputera signals (both opt-in, both off by default so refresh_stpm is unchanged):
  --with-bumi    a second listing pass with the portal's own "Program BUMI = Ya" filter ticked.
                 Adds ``bumi_portal`` (Y/N). The filter lives in the server session (a form POST),
                 so the pass runs in a fresh browser context and follows the page links it is given.
  --with-syarat  fetches each programme's Syarat modal (``modalSyarat/<cat>/<code>``). Adds
                 ``syarat_khas`` (clean text) and ``bumi_syarat`` (Y/N from the wording).
Never trust one signal alone (docs/lessons.md L539): ``bumi_agreement`` reports where they differ.
"""
import csv
import html as html_lib
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
MODAL_SYARAT_URL = 'https://online.mohe.gov.my/epanduan/ProgramPengajian/modalSyarat/{cat}/{code}'

# Wording MOHE uses for a Bumiputera-only programme, e.g. "Berketurunan Melayu, Anak Negeri
# Sabah, Anak Negeri Sarawak dan Orang Asli sahaja." A programme open to "Bumiputera dan bukan
# Bumiputera" must NOT match, so the negative is checked first.
_BUMI_ONLY_RE = re.compile(
    r'berketurunan\s+melayu|anak\s+negeri\s+sabah|anak\s+negeri\s+sarawak|orang\s+asli'
    r'|bumiputera\s+sahaja|calon\s+bumiputera',
    re.I,
)
_BUMI_OPEN_RE = re.compile(r'bukan\s+bumiputera', re.I)


def modal_url(cat_code, code):
    """URL of a programme's Syarat modal (plain GET, no session needed)."""
    return MODAL_SYARAT_URL.format(cat=cat_code, code=code)


def clean_modal_text(raw_html):
    """Strip tags and collapse whitespace from a Syarat modal response."""
    text = re.sub(r'<[^>]+>', ' ', raw_html or '')
    return re.sub(r'\s+', ' ', html_lib.unescape(text)).strip()


def bumi_in_syarat(text):
    """True when the Syarat wording limits the programme to Bumiputera candidates."""
    if not text or _BUMI_OPEN_RE.search(text):
        return False
    return bool(_BUMI_ONLY_RE.search(text))


def csv_fieldnames(with_bumi, with_syarat):
    """The CSV columns: the base set, plus the Bumi columns for the passes that ran."""
    fieldnames = [
        'course_id', 'course_name', 'university', 'merit',
        'stream', 'mohe_url', 'badges', 'year',
    ]
    if with_bumi:
        fieldnames.append('bumi_portal')
    if with_syarat:
        fieldnames += ['bumi_syarat', 'syarat_khas']
    if with_bumi and with_syarat:
        fieldnames.append('bumi_agreement')
    return fieldnames


def bumi_filter_applied(filtered_total, unfiltered_total):
    """True when ticking "Program BUMI = Ya" gave a real, smaller listing. The filter is a
    session toggle, so an unticked (or double-ticked) filter shows the full count again."""
    return 0 < filtered_total < unfiltered_total


def bumi_agreement(bumi_portal, bumi_syarat):
    """Classify the two Bumi signals for one programme: 'both', 'neither',
    'portal_only' or 'syarat_only'. A blank signal (pass not run) gives ''."""
    if bumi_portal not in ('Y', 'N') or bumi_syarat not in ('Y', 'N'):
        return ''
    return {
        ('Y', 'Y'): 'both', ('N', 'N'): 'neither',
        ('Y', 'N'): 'portal_only', ('N', 'Y'): 'syarat_only',
    }[(bumi_portal, bumi_syarat)]

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
        parser.add_argument(
            '--with-bumi', action='store_true',
            help='Also run a pass with the portal\'s "Program BUMI = Ya" filter; adds bumi_portal.',
        )
        parser.add_argument(
            '--with-syarat', action='store_true',
            help='Also fetch each programme\'s Syarat modal; adds syarat_khas and bumi_syarat.',
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
        cat_totals = {}  # per-category "daripada N", to prove the Bumi filter actually narrowed

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
                        cat_totals[cat_code] = total
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

            if options['with_bumi']:
                self._mark_bumi_portal(browser, all_programmes, categories, jenprog, delay,
                                       max_pages, cat_totals)
            if options['with_syarat']:
                self._fetch_syarat(page, all_programmes, delay)

            browser.close()

        fieldnames = csv_fieldnames(options['with_bumi'], options['with_syarat'])
        if options['with_bumi'] and options['with_syarat']:
            for prog in all_programmes:
                prog['bumi_agreement'] = bumi_agreement(prog['bumi_portal'], prog['bumi_syarat'])

        # Write CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
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
                'cat_code': cat_code,  # not written to the CSV; used for the Syarat modal URL
            })

        return programmes

    def _mark_bumi_portal(self, browser, programmes, categories, jenprog, delay, max_pages, cat_totals):
        """Set ``bumi_portal`` Y/N on every programme from the portal's own Bumi filter."""
        bumi_codes = set()
        for cat_code, _stream in categories:
            bumi_codes |= self._scrape_bumi_codes(
                browser, cat_code, jenprog, delay, max_pages, cat_totals.get(cat_code, 0))
        for prog in programmes:
            prog['bumi_portal'] = 'Y' if prog['course_id'] in bumi_codes else 'N'
        stray = bumi_codes - {p['course_id'] for p in programmes}
        if stray:
            self.stdout.write(self.style.WARNING(
                f'  {len(stray)} Bumi-filter codes were not in the main listing: '
                f'{", ".join(sorted(stray)[:10])}'
            ))

    def _fetch_syarat(self, page, programmes, delay):
        """Set ``syarat_khas`` and ``bumi_syarat`` from each programme's Syarat modal."""
        self.stdout.write(f'\nFetching Syarat for {len(programmes)} programmes...')
        for n, prog in enumerate(programmes, 1):
            resp = page.request.get(modal_url(prog['cat_code'], prog['course_id']))
            text = clean_modal_text(resp.text()) if resp.ok else ''
            prog['syarat_khas'] = text
            prog['bumi_syarat'] = 'Y' if bumi_in_syarat(text) else 'N'
            if n % 50 == 0:
                self.stdout.write(f'  {n}/{len(programmes)}')
            time.sleep(delay / 2)

    def _scrape_bumi_codes(self, browser, cat_code, jenprog, delay, max_pages, unfiltered_total):
        """Return the programme codes the portal lists under its own "Program BUMI = Ya" filter.

        The filter is a server-session form POST that toggles, so this runs in a FRESH context
        (filter off), ticks it once, then follows the page links the filtered page gives us
        (a fresh LISTING_URL could reset the session filter). Fails loudly on a short count."""
        context = browser.new_context()
        page = context.new_page()
        page.goto(LISTING_URL.format(cat=cat_code, jenprog=jenprog, page=1), wait_until='domcontentloaded')
        page.wait_for_selector('.executive-data-value', timeout=30000)
        page.click('button[data-bs-target="#bumiCollapse"]')
        page.wait_for_timeout(400)
        page.click('label[for="bumi_Y"]')
        page.wait_for_timeout(800)
        page.click('button:has-text("Cari")')
        page.wait_for_load_state('domcontentloaded')
        page.wait_for_timeout(3000)

        total_match = re.search(r'daripada (\d+)', page.inner_text('body'))
        expected = int(total_match.group(1)) if total_match else 0
        self.stdout.write(f'\nBumi filter, category {cat_code}: portal reports {expected}')
        if not bumi_filter_applied(expected, unfiltered_total):
            context.close()
            raise CommandError(
                f'Bumi filter did not narrow category {cat_code} ({expected} of {unfiltered_total}). '
                f'The portal form may have changed.'
            )

        codes = set()
        page_num = 1
        while True:
            codes |= set(page.evaluate(
                """() => [...document.querySelectorAll('a[href^="#syarat-am-"]')]
                       .map(a => a.getAttribute('href').slice('#syarat-am-'.length))"""
            ))
            if max_pages and page_num >= max_pages:
                break
            next_link = page.query_selector(f'a[href*="page={page_num + 1}"]')
            if not next_link:
                break
            page_num += 1
            time.sleep(delay)
            page.goto(next_link.get_attribute('href'), wait_until='domcontentloaded')
            page.wait_for_timeout(2000)
        context.close()

        self.stdout.write(f'  Bumi filter collected {len(codes)} codes')
        if not max_pages and scrape_shortfall(len(codes), expected):
            raise CommandError(
                f'Bumi-filter pass looks INCOMPLETE for category {cat_code}: got {len(codes)} codes '
                f'but the portal reports {expected}. The filter may not have applied.'
            )
        return codes
