"""
Scrape the public UP_TVET Perdana course catalogue (mohon.tvet.gov.my).

This is the TVET counterpart to scrape_mohe_stpm. UP_TVET covers ~12 ministries / 685
institutions; HalaTuju currently holds only ILJTM + ILKBS (~83 courses). This scraper
acquires the FULL public catalogue into a CSV for a coverage inventory (audit_uptvet) —
it does NOT write to the DB (ingest is a later, golden-master-adjacent sprint).

The catalogue is server-rendered, paginated HTML (no JSON API):
    https://mohon.tvet.gov.my/awam-kursus/katalog?page=N        (20 cards/page, ~50 pages)

Each card carries: Kod Tauliah, name, Yuran Daftar/Pengajian (fees), Kategori, Institusi,
**Sektor (Awam/Swasta — the catalogue mixes both)**, an Info-Kursus detail URL (`id_kursus`)
and a Semak-Kelayakan (eligibility) URL. The Sektor field is captured so the inventory /
a future ingest can scope to public (Awam) providers.

Usage:
    python manage.py scrape_uptvet --output data/tvet/uptvet_latest.csv
    python manage.py scrape_uptvet --output /tmp/spike.csv --max-pages 2   # parser-validation spike
"""
import csv
import re
import time

from django.core.management.base import BaseCommand, CommandError

CATALOG_URL = 'https://mohon.tvet.gov.my/awam-kursus/katalog?page={page}'

CSV_FIELDS = [
    'kod_tauliah', 'name', 'kategori', 'institution', 'sektor',
    'reg_fee', 'tuition_fee', 'id_kursus', 'info_url', 'kelayakan_url', 'page',
]


class Command(BaseCommand):
    help = 'Scrape the public UP_TVET Perdana course catalogue to a CSV (no DB writes)'

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, required=True, help='Output CSV file path')
        parser.add_argument(
            '--delay', type=float, default=1.0,
            help='Seconds between page loads (be polite to the UP_TVET servers)',
        )
        parser.add_argument(
            '--max-pages', type=int, default=0,
            help='Stop after this many pages (0 = all). Use a small value for a quick spike.',
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
        max_pages = options['max_pages']

        all_cards = []
        last_page = None  # highest page number the pagination advertises (a sanity bound)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page_num = 1
            while True:
                url = CATALOG_URL.format(page=page_num)
                page.goto(url, wait_until='domcontentloaded')
                try:
                    page.wait_for_selector('text=Kod Tauliah', timeout=30000)
                except Exception:
                    self.stdout.write('  Warning: timed out waiting for cards')
                page.wait_for_timeout(800)

                if page_num == 1:
                    last_page = self._read_last_page(page)
                    if last_page:
                        self.stdout.write(f'  Pagination advertises up to page {last_page} '
                                          f'(≈{last_page * 20} programmes)')

                cards = self._parse_cards(page)
                if not cards:
                    break
                for c in cards:
                    c['page'] = page_num
                all_cards.extend(cards)
                self.stdout.write(f'  Page {page_num}: {len(cards)} cards (total {len(all_cards)})')

                if max_pages and page_num >= max_pages:
                    self.stdout.write(f'  Reached --max-pages={max_pages}, stopping.')
                    break
                if last_page and page_num >= last_page:
                    break
                next_link = page.query_selector(f'a[href*="page={page_num + 1}"]')
                if not next_link:
                    break
                page_num += 1
                time.sleep(delay)

            browser.close()

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(all_cards)

        awam = sum(1 for c in all_cards if c['sektor'].lower() == 'awam')
        swasta = sum(1 for c in all_cards if c['sektor'].lower() == 'swasta')
        self.stdout.write(self.style.SUCCESS(
            f'\nDone: {len(all_cards)} programmes written to {output_path} '
            f'(Awam {awam} · Swasta {swasta} · other/blank {len(all_cards) - awam - swasta})'
        ))

        # Soft sanity check (no hard guard — this writes a CSV, not the DB). A full run that
        # got far fewer than the advertised page count likely means a DOM change broke the parser.
        if not max_pages and last_page and len(all_cards) < last_page * 20 * 0.8:
            self.stdout.write(self.style.WARNING(
                f'  NOTE: scraped {len(all_cards)} but pagination implied ≈{last_page * 20}. '
                f'Inspect the CSV before trusting it — the UP_TVET DOM may have changed.'
            ))

    @staticmethod
    def _read_last_page(page):
        """Highest page number in the pagination control (a sanity bound)."""
        nums = []
        for a in page.query_selector_all('a[href*="page="]'):
            href = a.get_attribute('href') or ''
            m = re.search(r'page=(\d+)', href)
            if m:
                nums.append(int(m.group(1)))
        return max(nums) if nums else None

    def _parse_cards(self, page):
        """Parse programme cards from the current page via label-anchored extraction."""
        cards = page.evaluate(r"""() => {
            const results = [];
            // Each card has exactly one numbered <h6> ("1. CODE NAME"). Anchor on it, then walk
            // UP to the enclosing card row (the ancestor that also carries the Sektor label +
            // the Info-Kursus link) — fields can span sibling columns, so don't require one div.
            const headings = [...document.querySelectorAll('h6')].filter(h => /^\s*\d+\.\s/.test(h.textContent));
            const cardEls = [];
            for (const h of headings) {
                let el = h;
                for (let i = 0; i < 8 && el; i++) {
                    el = el.parentElement;
                    if (el && /Sektor/.test(el.textContent) && el.querySelector('a[href*="id_kursus="]')) break;
                }
                if (el && !cardEls.includes(el)) cardEls.push(el);
            }

            const labelVal = (el, label) => {
                // Find the <strong>label:</strong> value text within the card.
                const strong = [...el.querySelectorAll('strong')].find(s => s.textContent.trim().startsWith(label));
                if (!strong) return '';
                // value is the strong's parent text minus the label
                return (strong.parentElement.textContent || '').replace(strong.textContent, '').trim();
            };
            const feeVal = (el, label) => {
                const m = (el.textContent || '').match(new RegExp(label + '\\s*:?\\s*RM?\\s*([\\d,]+)'));
                return m ? m[1].replace(/,/g, '') : '';
            };

            for (const el of cardEls) {
                const h6 = el.querySelector('h6');
                let heading = (h6 ? h6.textContent : '').replace(/\s+/g, ' ').trim();
                heading = heading.replace(/^\d+\.\s*/, '');  // strip "1. "
                const kod = labelVal(el, 'Kod Tauliah') || (heading.split(' ')[0] || '');
                // name = heading minus a leading code token
                let name = heading;
                if (kod && name.startsWith(kod)) name = name.slice(kod.length).trim();

                const sektor = labelVal(el, 'Sektor');
                const kategori = labelVal(el, 'Kategori');
                const institution = labelVal(el, 'Institusi');

                let info_url = '', kelayakan_url = '', id_kursus = '';
                for (const a of el.querySelectorAll('a[href]')) {
                    const h = a.getAttribute('href') || '';
                    if (/id_kursus=/.test(h)) { info_url = h; const m = h.match(/id_kursus=(\d+)/); if (m) id_kursus = m[1]; }
                    else if (/semak-pra-syarat/.test(h)) { kelayakan_url = h; }
                }

                results.push({
                    kod_tauliah: kod, name, kategori, institution, sektor,
                    reg_fee: feeVal(el, 'Yuran Daftar'),
                    tuition_fee: feeVal(el, 'Yuran Pengajian'),
                    id_kursus, info_url, kelayakan_url,
                });
            }
            return results;
        }""")
        return cards
