"""
Scrape STPM programmes from MOHE ePanduan portal.

Outputs a CSV with: course_id, course_name, university, merit, stream, mohe_url, badges
This CSV is the input for the sync command.

Usage:
    python manage.py scrape_mohe_stpm --output data/stpm/mohe_latest.csv
    python manage.py scrape_mohe_stpm --output data/stpm/mohe_latest.csv --category S
    python manage.py scrape_mohe_stpm --output data/stpm/mohe_latest.csv --category A
"""
import csv
import re
import time

from django.core.management.base import BaseCommand


LISTING_URL = 'https://online.mohe.gov.my/epanduan/ProgramPengajian/kategoriCalon/{cat}?jenprog=stpm&page={page}'

CATEGORIES = [
    ('S', 'science'),
    ('A', 'arts'),
]


class Command(BaseCommand):
    help = 'Scrape STPM programmes from MOHE ePanduan portal'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', type=str, required=True,
            help='Output CSV file path',
        )
        parser.add_argument(
            '--category', type=str, default='',
            help='Scrape only one category: S (science) or A (arts). Default: both.',
        )
        parser.add_argument(
            '--delay', type=float, default=1.0,
            help='Seconds to wait between page loads (be polite to MOHE servers)',
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
        cat_filter = options['category'].upper()

        categories = CATEGORIES
        if cat_filter:
            categories = [(c, s) for c, s in CATEGORIES if c == cat_filter]

        all_programmes = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for cat_code, stream_name in categories:
                self.stdout.write(f'\nScraping category {cat_code} ({stream_name})...')
                page_num = 1

                while True:
                    url = LISTING_URL.format(cat=cat_code, page=page_num)
                    page.goto(url, wait_until='networkidle')

                    # Extract total from heading "Paparan X - Y daripada Z carian"
                    heading = page.query_selector('h5')
                    heading_text = heading.inner_text() if heading else ''

                    if page_num == 1:
                        total_match = re.search(r'daripada (\d+)', heading_text)
                        total = int(total_match.group(1)) if total_match else 0
                        self.stdout.write(f'  Found {total} programmes')

                    # Parse programme cards
                    cards = self._parse_cards(page, cat_code, stream_name)
                    if not cards:
                        break

                    all_programmes.extend(cards)
                    self.stdout.write(
                        f'  Page {page_num}: {len(cards)} programmes '
                        f'(total so far: {len(all_programmes)})'
                    )

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

    def _parse_cards(self, page, cat_code, stream_name):
        """Parse programme cards from the current page."""
        cards = page.evaluate("""() => {
            const results = [];
            const container = document.querySelector('h5')?.closest('div')?.parentElement;
            if (!container) return results;

            const cardDivs = container.querySelectorAll(':scope > div');
            for (const card of cardDivs) {
                const nameLink = card.querySelector('a[href="#"]');
                if (!nameLink) continue;

                const name = nameLink.textContent.replace('#', '').trim();

                const uniP = card.querySelector('p');
                const university = uniP ? uniP.textContent.trim() : '';

                const allText = card.innerText;
                const codeMatch = allText.match(/KOD PROGRAM\\s*([A-Z]{2}\\d+)/);
                const code = codeMatch ? codeMatch[1] : '';

                const meritMatch = allText.match(/(\\d+\\.\\d+)%/);
                const merit = meritMatch ? meritMatch[1] : '';

                const yearMatch = allText.match(/TAHUN\\s*(\\d{4})/);
                const year = yearMatch ? yearMatch[1] : '';

                const badgeEls = card.querySelectorAll('[class*="cursor"]');
                const badges = [];
                for (const b of badgeEls) {
                    const t = b.textContent.trim();
                    if (t && !t.includes('Merit') && t.length < 30) {
                        badges.push(t);
                    }
                }

                if (code) {
                    results.push({ name, university, code, merit, year, badges: badges.join('|') });
                }
            }
            return results;
        }""")

        mohe_base = 'https://online.mohe.gov.my/epanduan/carianNamaProgram'
        programmes = []
        for item in cards:
            prefix = item['code'][:2] if item['code'] else ''
            programmes.append({
                'course_id': item['code'],
                'course_name': item['name'],
                'university': item['university'],
                'merit': item['merit'],
                'stream': stream_name,
                'mohe_url': f"{mohe_base}/{prefix}/{item['code']}/{cat_code}/stpm" if item['code'] else '',
                'badges': item['badges'],
                'year': item['year'],
            })

        return programmes
