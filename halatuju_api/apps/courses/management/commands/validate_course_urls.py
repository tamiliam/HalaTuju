"""
Reachability check for the SPM / post-SPM catalogue links.

Complements `validate_stpm_urls` (which is content-aware via Selenium, MOHE-only).
This checks the distinct external URLs stored on `Institution.url` +
`CourseInstitution.hyperlink` (deduped) with a lightweight HTTP GET — stdlib
`urllib`, so **no new dependency and no browser**. It catches the COMMON link rot:
dead domains, 404/410/5xx, timeouts, DNS/SSL failures.

What it does NOT catch (by design): a portal that returns 200 but no longer lists
the programme — that needs per-portal content markers (`validate_stpm_urls` does
this for MOHE). So: this = "is the link reachable", `validate_stpm_urls` = "does
MOHE still list this programme". HTTP status is useless for that deeper check on
server-rendered portals (they 200 regardless).

Usage:
    python manage.py validate_course_urls
    python manage.py validate_course_urls --fix       # clear confirmed-dead (4xx) URLs
    python manage.py validate_course_urls --limit 50  # check first N distinct URLs only
"""
import ssl
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand

from apps.courses.models import CourseInstitution, Institution

_UA = 'HalaTuju-linkcheck/1.0 (+https://halatuju.xyz)'
_CTX = ssl.create_default_context()


def check_url(url, timeout=10):
    """Reachability of a single URL → (status, detail).

    'alive' = 2xx/3xx, or 401/403 (reachable but auth-gated, e.g. a login portal);
    'dead'  = 404/410/other 4xx/5xx (gone);
    'error' = timeout / DNS / SSL / connection failure, OR a malformed/schemeless stored URL
    (e.g. 'foo.edu.my' with no http://) — transient or bad-data, never auto-fixed, never crashes.
    Isolated + tiny so tests can mock `urlopen`. The Request build is INSIDE the try so a malformed
    URL is classified as 'error' rather than raising and aborting the whole run."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': _UA})  # GET
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            return ('alive', getattr(r, 'status', 200))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):       # reachable, just gated
            return ('alive', e.code)
        return ('dead', e.code)        # 404/410/5xx → gone
    except Exception as e:             # URLError, timeout, SSL, malformed URL (ValueError), …
        return ('error', type(e).__name__)


class Command(BaseCommand):
    help = 'Reachability check for catalogue links (Institution.url + CourseInstitution.hyperlink).'

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true',
                            help='Clear confirmed-dead (4xx/5xx) URLs from the DB. Transient errors are never cleared.')
        parser.add_argument('--limit', type=int, default=0, help='Check only the first N distinct URLs.')
        parser.add_argument('--timeout', type=float, default=10.0, help='Per-URL timeout (seconds).')
        parser.add_argument('--workers', type=int, default=1,
                            help='Concurrent URL checks (read-only HTTP GETs parallelise safely). '
                                 'Default 1 (sequential). The dashboard health-check uses ~20 so ~650 URLs '
                                 'finish in well under a minute.')

    def handle(self, *args, **options):
        fix = options['fix']
        limit = options['limit']
        timeout = options['timeout']
        workers = max(1, options['workers'])

        # Distinct non-empty URLs across both fields, with reference counts (so the
        # report + --fix know how many rows each URL backs).
        refs = {}  # url -> {'inst': n, 'offer': n}
        for u in Institution.objects.exclude(url='').values_list('url', flat=True):
            refs.setdefault(u, {'inst': 0, 'offer': 0})['inst'] += 1
        for u in CourseInstitution.objects.exclude(hyperlink='').values_list('hyperlink', flat=True):
            refs.setdefault(u, {'inst': 0, 'offer': 0})['offer'] += 1

        urls = sorted(refs)
        if limit:
            urls = urls[:limit]
        self.stdout.write('Checking %d distinct catalogue URLs (GET, %ss timeout, %d worker%s)...'
                          % (len(urls), timeout, workers, '' if workers == 1 else 's'))

        alive = 0
        dead, errors = [], []

        def _classify(u, status, detail):
            nonlocal alive
            if status == 'alive':
                alive += 1
            elif status == 'dead':
                dead.append((u, detail))
            else:
                errors.append((u, detail))

        if workers == 1:
            for i, u in enumerate(urls, 1):
                status, detail = check_url(u, timeout)
                _classify(u, status, detail)
                if i % 50 == 0:
                    self.stdout.write('  checked %d/%d...' % (i, len(urls)))
        else:
            # Read-only GETs → safe to parallelise; aggregation stays single-threaded here.
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = pool.map(lambda u: (u, *check_url(u, timeout)), urls)
                for i, (u, status, detail) in enumerate(results, 1):
                    _classify(u, status, detail)
                    if i % 100 == 0:
                        self.stdout.write('  checked %d/%d...' % (i, len(urls)))

        self.stdout.write('\nAlive:  %d' % alive)
        self.stdout.write('Dead:   %d (4xx/5xx)' % len(dead))
        self.stdout.write('Errors: %d (timeout/DNS/SSL — transient, not auto-fixed)' % len(errors))

        # Record link-health for the Course Data dashboard.
        from apps.courses.course_data_status import record_status, LINK_HEALTH
        record_status(LINK_HEALTH,
                      {'checked': len(urls), 'alive': alive, 'dead': len(dead), 'errors': len(errors)},
                      detail='python manage.py validate_course_urls')

        if dead:
            self.stdout.write(self.style.WARNING('\n--- DEAD ---'))
            for u, code in sorted(dead):
                r = refs[u]
                self.stdout.write('  [%s] %s  (inst:%d offer:%d)' % (code, u, r['inst'], r['offer']))
        if errors:
            self.stdout.write(self.style.NOTICE('\n--- ERRORS (review manually) ---'))
            for u, why in sorted(errors):
                self.stdout.write('  [%s] %s' % (why, u))

        if fix and dead:
            dead_urls = [u for u, _ in dead]
            ni = Institution.objects.filter(url__in=dead_urls).update(url='')
            no = CourseInstitution.objects.filter(hyperlink__in=dead_urls).update(hyperlink='')
            self.stdout.write(self.style.SUCCESS(
                '\nCleared %d Institution.url + %d CourseInstitution.hyperlink (confirmed dead).' % (ni, no)))
        elif fix:
            self.stdout.write('\nNothing to fix.')
