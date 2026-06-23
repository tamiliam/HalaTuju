"""
Refresh institution homepage URLs from the AUTHORITATIVE index pages — never guess.

Each institution category publishes an official directory that lists every institution with
its current URL. Re-sourcing from there (vs guessing a domain from a naming pattern — a known
trap, see docs/lessons.md) is the reliable way to fix the dead/renamed links the dashboard's
"Problem links" surface flags.

Sources (registry below):
  matrikulasi  https://www.moe.gov.my/senarai-matrikulasi                          (matched by subdomain id)
  politeknik   https://ambilan.mypolycc.edu.my/portalbpp2/index.asp?pg=politeknik   (matched by institution name)
  kk           https://ambilan.mypolycc.edu.my/portalbpp2/index.asp?pg=kk           (matched by institution name)

SAFE BY DEFAULT — dry-run unless --apply. With --apply it writes ONLY 'canonicalise' proposals
(our institution matched an index entry, the index URL differs AND is reachable). 'missing'
(ours not in the index → maybe renamed/closed) and 'extra' (index has one we lack → coverage gap)
are REPORTED ONLY, never auto-written. A mass-change guard mirrors sync_stpm_mohe. Local operator
tool (needs Playwright + prod DB creds); not run by the service.

Usage:
    python manage.py refresh_institution_urls --source matrikulasi            # dry-run report
    python manage.py refresh_institution_urls --source matrikulasi --apply    # write canonicalisations
    python manage.py refresh_institution_urls --source politeknik --max-changes 30
"""
import re
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.models import Institution
from apps.courses.management.commands.validate_course_urls import check_url

# Abort --apply if it would change more than this fraction of the matched set (bad scrape guard).
MAX_CHANGE_FRACTION = 0.6


def _norm_name(s):
    """Normalise an institution name for matching (case/space/punct/acronym-in-brackets-insensitive)."""
    s = re.sub(r'\([^)]*\)', ' ', s or '')            # drop "(PUO)" acronym parentheticals
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()


def _subdomain(url):
    """First label of the host: https://www.kmm.matrik.edu.my → 'kmm' (drops a leading www.)."""
    m = re.match(r'https?://(?:www\.)?([a-z0-9-]+)\.', (url or '').lower())
    return m.group(1) if m else ''


# ---- per-source parsers: page → {match_key: authoritative_url} ----

def _parse_matrikulasi(links):
    """links = [(text, href)]. Key on the matrik.edu.my subdomain id (our institution_id)."""
    out = {}
    for _text, href in links:
        if 'matrik.edu.my' in href.lower():
            key = _subdomain(href)
            if key:
                out.setdefault(key, href)
    return out


def _parse_polycc(rows):
    """rows = [(name, url)] scraped from the MyPolyCC 'Senarai' table. Key on the normalised name."""
    out = {}
    for name, url in rows:
        url = (url or '').split(' @ ')[0].strip()      # one row lists "a @ b" — take the first
        if name and url.startswith('http'):
            out.setdefault(_norm_name(name), url)
    return out


SOURCES = {
    'matrikulasi': {
        'index_url': 'https://www.moe.gov.my/senarai-matrikulasi',
        'match': 'subdomain',     # our institution_id == the matrik subdomain
        'queryset': lambda: Institution.objects.filter(url__icontains='matrik'),
    },
    'politeknik': {
        'index_url': 'https://ambilan.mypolycc.edu.my/portalbpp2/index.asp?pg=politeknik',
        'match': 'name',
        'queryset': lambda: Institution.objects.filter(institution_name__istartswith='politeknik'),
    },
    'kk': {
        'index_url': 'https://ambilan.mypolycc.edu.my/portalbpp2/index.asp?pg=kk',
        'match': 'name',
        'queryset': lambda: Institution.objects.filter(institution_name__icontains='kolej komuniti'),
    },
}


def build_proposals(institutions, index_map, match, reachable=check_url):
    """PURE classifier. institutions = [(id, name, url)]; index_map = {key: url}.
    Returns {'canonicalise': [...], 'missing': [...], 'extra': [...]}.

    - canonicalise: our institution matches an index key, the index URL differs from ours, AND
      the index URL is reachable (so we don't replace a good URL with a broken one).
    - missing:      our institution has no index match (renamed/closed — human review).
    - extra:        index key we don't hold (coverage gap — human review).
    """
    def key_of(inst_id, name, url):
        return _subdomain(url) or inst_id.lower() if match == 'subdomain' else _norm_name(name)

    canonicalise, missing = [], []
    matched_keys = set()
    for inst_id, name, url in institutions:
        k = key_of(inst_id, name, url)
        idx_url = index_map.get(k)
        if not idx_url:
            missing.append({'id': inst_id, 'name': name, 'current': url})
            continue
        matched_keys.add(k)
        if idx_url.rstrip('/') != (url or '').rstrip('/'):
            status, _ = reachable(idx_url)
            if status in ('alive', 'insecure'):
                canonicalise.append({'id': inst_id, 'name': name, 'current': url, 'proposed': idx_url})
            else:
                missing.append({'id': inst_id, 'name': name, 'current': url,
                                'note': 'index URL %s not reachable (%s)' % (idx_url, status)})
    extra = [{'key': k, 'url': u} for k, u in sorted(index_map.items()) if k not in matched_keys]
    return {'canonicalise': canonicalise, 'missing': missing, 'extra': extra}


class Command(BaseCommand):
    help = 'Refresh institution URLs from an authoritative index page (dry-run; --apply writes canonicalisations).'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True, choices=sorted(SOURCES),
                            help='Which authoritative index to re-source from.')
        parser.add_argument('--apply', action='store_true',
                            help='Write canonicalise proposals (matched + reachable). missing/extra never auto-written.')
        parser.add_argument('--max-changes', type=int, default=0,
                            help='Abort --apply if more than N institutions would change (0 = use the fraction guard).')

    def handle(self, *args, **options):
        source = options['source']
        cfg = SOURCES[source]
        index_map = self._scrape(cfg)
        if not index_map:
            raise CommandError('No entries parsed from %s — inspect the page (DOM may have changed).' % cfg['index_url'])

        institutions = list(cfg['queryset']().values_list('institution_id', 'institution_name', 'url'))
        props = build_proposals(institutions, index_map, cfg['match'])

        self.stdout.write('\n=== refresh_institution_urls: %s ===' % source)
        self.stdout.write('Index entries: %d   Our institutions: %d' % (len(index_map), len(institutions)))
        self._report('CANONICALISE (matched, index differs + reachable — applied with --apply)', props['canonicalise'],
                     lambda p: '  %s  %s\n      %s  ->  %s' % (p['id'], p['name'], p['current'], p['proposed']))
        self._report('MISSING (not in index — review: renamed/closed?)', props['missing'],
                     lambda p: '  %s  %s  (%s)%s' % (p['id'], p['name'], p['current'], (' — ' + p['note']) if p.get('note') else ''))
        self._report('EXTRA (in index, not in our catalogue — coverage gap?)', props['extra'],
                     lambda p: '  %s  ->  %s' % (p['key'], p['url']))

        if not options['apply']:
            self.stdout.write(self.style.NOTICE('\nDry run. Review, then re-run with --apply to write the CANONICALISE set.'))
            self._record(source, props, applied=0)
            return

        # Guard: refuse a mass change from a bad scrape.
        n = len(props['canonicalise'])
        cap = options['max_changes'] or int(len(institutions) * MAX_CHANGE_FRACTION) or 1
        if n > cap:
            raise CommandError('Refusing --apply: %d changes exceeds the cap of %d (looks like a bad scrape; '
                               'verify, or raise --max-changes).' % (n, cap))

        with transaction.atomic():
            for p in props['canonicalise']:
                Institution.objects.filter(institution_id=p['id']).update(url=p['proposed'])
        self.stdout.write(self.style.SUCCESS('\nApplied %d URL canonicalisations.' % n))
        self._record(source, props, applied=n)

    def _scrape(self, cfg):
        """Open the index page and pull (text, href) anchors (matrikulasi) or (name, url) rows (polycc)."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise CommandError('playwright not installed. Run: pip install playwright && playwright install chromium')
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(cfg['index_url'], wait_until='domcontentloaded')
            page.wait_for_timeout(1500)
            if cfg['match'] == 'subdomain':
                links = page.eval_on_selector_all('a[href]', "els => els.map(a => [a.textContent.trim(), a.href])")
                browser.close()
                return _parse_matrikulasi(links)
            # polycc: each table row carries the institution name + an outbound homepage link
            rows = page.eval_on_selector_all('tr', """els => els.map(tr => {
                const a = tr.querySelector('a[href^="http"]');
                const name = (tr.querySelector('td')?.textContent || tr.textContent || '').replace(/\\s+/g,' ').trim();
                return a ? [name.slice(0,120), a.href] : null;
            }).filter(Boolean)""")
            browser.close()
            return _parse_polycc(rows)

    def _report(self, title, items, fmt):
        style = self.style.WARNING if items else self.style.SUCCESS
        self.stdout.write(style('\n--- %s (%d) ---' % (title, len(items))))
        for it in items[:60]:
            self.stdout.write(fmt(it))
        if len(items) > 60:
            self.stdout.write('  … %d more' % (len(items) - 60))

    def _record(self, source, props, applied):
        from apps.courses.course_data_status import record_status
        record_status('url_refresh', {
            'source': source, 'applied': applied,
            'canonicalise': len(props['canonicalise']), 'missing': len(props['missing']),
            'extra': len(props['extra']),
        }, detail='python manage.py refresh_institution_urls --source %s%s' % (source, ' --apply' if applied else ''))
