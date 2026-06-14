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

# A browser-like UA: some portals reject the default urllib UA. (We treat 401/403 as alive anyway,
# but a real UA avoids servers that hang/close on an unknown client.)
_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
_CTX = ssl.create_default_context()
_NOVERIFY = ssl._create_unverified_context()  # retry context for cert-invalid-but-reachable sites


def _is_ssl_failure(exc):
    """Did this failure come from TLS/cert verification (so it's worth a no-verify retry)?"""
    if isinstance(exc, ssl.SSLError):
        return True
    reason = getattr(exc, 'reason', None)
    return isinstance(reason, ssl.SSLError) or 'CERTIFICATE' in str(getattr(exc, 'reason', '')).upper()


def _error_kind(exc):
    """A short, human category for an 'error' (so the dashboard can group failures).
    'dns' = domain not found · 'timeout' = too slow · 'conn' = refused/reset/unreachable ·
    'badurl' = malformed · else the exception class name."""
    s = (str(getattr(exc, 'reason', exc)) or '').lower()
    name = type(exc).__name__
    if isinstance(exc, (TimeoutError,)) or 'timed out' in s or 'timeout' in s:
        return 'timeout'
    if 'getaddrinfo' in s or 'name or service' in s or 'nodename' in s or 'no address' in s or '11001' in s:
        return 'dns'
    if 'refused' in s or 'reset' in s or 'unreachable' in s or 'connection' in s:
        return 'conn'
    if isinstance(exc, ValueError):
        return 'badurl'
    return name


def _check_once(url, timeout=10):
    """One reachability attempt for a URL → (status, detail). See `check_url` for the taxonomy.

    Robustness: a schemeless stored value (e.g. 'foo.edu.my') is normalised to https://; the whole
    body is inside try/except so a bad URL is classified, never raised (one bad row must not abort
    the run). Isolated + tiny so tests can mock `urlopen`."""
    try:
        target = url if url.lower().startswith(('http://', 'https://')) else 'https://' + url
        req = urllib.request.Request(target, headers={'User-Agent': _UA})  # GET
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                return ('alive', getattr(r, 'status', 200))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):       # server responded but refused THIS page → AMBIGUOUS:
                return ('gated', e.code)   # a login wall (fine) OR a wrong/old path (broken, e.g. PD)
            return ('dead', e.code)        # 404/410/5xx → gone
        except Exception as e:             # URLError, timeout, SSL, …
            if _is_ssl_failure(e):
                # Cert/TLS rejection on a host that may be perfectly alive → retry without verify.
                try:
                    with urllib.request.urlopen(req, timeout=timeout, context=_NOVERIFY) as r:
                        return ('insecure', getattr(r, 'status', 200))
                except urllib.error.HTTPError as e2:
                    if e2.code in (401, 403):
                        return ('gated', e2.code)
                    return ('dead', e2.code)
                except Exception as e2:
                    return ('error', _error_kind(e2))
            return ('error', _error_kind(e))
    except Exception as e:                 # malformed URL etc. — classify, never crash
        return ('error', _error_kind(e))


# A transient 'error' (slow / momentarily-unreachable host) is worth one retry before we report it:
# MY gov/edu portals routinely take 10-20s to first-byte, so a single 10s attempt produces lots of
# false "broken" flags. DNS/badurl are NOT retried (they won't change on a retry).
_RETRYABLE = {'timeout', 'conn'}


def check_url(url, timeout=10, retries=1):
    """Reachability of a single URL → (status, detail), with a retry for transient slowness.

    'alive'    = clean 2xx/3xx;
    'gated'    = 401/403 — the server responded but refused THIS page. AMBIGUOUS: usually a login
                 wall (fine), occasionally a wrong/old path the user hits as an error page (e.g.
                 Politeknik Port Dickson's old bare URL 403'd; the real site is at /web/). Reachable,
                 but surfaced for a human to eyeball — never auto-fixed, never silently "alive".
    'insecure' = reachable ONLY when TLS cert verification is skipped (the site is up, but its cert
                 chain doesn't validate in urllib — common on MY gov/edu sites that are fine in a
                 browser). Counted as reachable, tracked separately, never auto-fixed.
    'dead'     = 404/410/other 4xx/5xx (gone);
    'error'    = timeout / DNS / connection failure, OR a malformed URL.

    The report layer (below) splits results into SEVERITIES so the dashboard stops crying wolf:
    genuinely BROKEN (gone/dns/badurl — actionable) · ACCESS-BLOCKED (gated 401/403 — eyeball) ·
    COULDN'T-VERIFY (timeout/conn — very likely up, just unconfirmed). A transient error is retried
    once before being reported."""
    result = _check_once(url, timeout)
    if result[0] == 'error' and result[1] in _RETRYABLE and retries > 0:
        for _ in range(retries):
            result = _check_once(url, timeout)
            if not (result[0] == 'error' and result[1] in _RETRYABLE):
                break
    return result


# Failure severities, derived from the (status, kind) of a failed check. BROKEN is actionable
# (the link really needs fixing); UNVERIFIED means "almost certainly alive, just slow/blocked from
# the server we check from" — informational, not a to-do.
BROKEN_KINDS = {'gone', 'dns', 'badurl'}      # 'gone' = the dead/4xx/5xx bucket


class Command(BaseCommand):
    help = 'Reachability check for catalogue links (Institution.url + CourseInstitution.hyperlink).'

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true',
                            help='Clear confirmed-dead (4xx/5xx) URLs from the DB. Transient errors are never cleared.')
        parser.add_argument('--limit', type=int, default=0, help='Check only the first N distinct URLs.')
        parser.add_argument('--timeout', type=float, default=10.0, help='Per-URL timeout (seconds).')
        parser.add_argument('--retries', type=int, default=1,
                            help='Retries for a transient (timeout/conn) failure. Default 1 (good for '
                                 'targeted checks). The bulk dashboard run uses 0 — the timeout already '
                                 'catches slow-but-alive sites, and a retry would double the slow tail.')
        parser.add_argument('--workers', type=int, default=1,
                            help='Concurrent URL checks (read-only HTTP GETs parallelise safely). '
                                 'Default 1 (sequential). The dashboard health-check uses ~20 so ~650 URLs '
                                 'finish in well under a minute.')

    def handle(self, *args, **options):
        fix = options['fix']
        limit = options['limit']
        timeout = options['timeout']
        retries = max(0, options['retries'])
        workers = max(1, options['workers'])

        # Distinct non-empty URLs across both fields, with reference counts (so the
        # report + --fix know how many rows each URL backs) + the institution name(s)
        # behind each URL (so the dashboard can show WHO a broken link belongs to).
        refs = {}   # url -> {'inst': n, 'offer': n}
        names = {}  # url -> set of institution names
        for u, nm in Institution.objects.exclude(url='').values_list('url', 'institution_name'):
            refs.setdefault(u, {'inst': 0, 'offer': 0})['inst'] += 1
            names.setdefault(u, set()).add(nm)
        for u, nm in (CourseInstitution.objects.exclude(hyperlink='')
                      .values_list('hyperlink', 'institution__institution_name')):
            refs.setdefault(u, {'inst': 0, 'offer': 0})['offer'] += 1
            names.setdefault(u, set()).add(nm)

        urls = sorted(refs)
        if limit:
            urls = urls[:limit]
        self.stdout.write('Checking %d distinct catalogue URLs (GET, %ss timeout, %d worker%s)...'
                          % (len(urls), timeout, workers, '' if workers == 1 else 's'))

        alive = 0
        insecure = 0  # reachable only without cert verification — a subset of "reachable"
        dead, errors, gated = [], [], []  # gated = 401/403 (server refused this page — ambiguous)

        def _classify(u, status, detail):
            nonlocal alive, insecure
            if status == 'alive':
                alive += 1
            elif status == 'insecure':
                alive += 1      # reachable → counts as alive
                insecure += 1   # …but track the cert-invalid subset
            elif status == 'gated':
                gated.append((u, detail))   # 401/403 — surfaced for review, NOT silently alive
            elif status == 'dead':
                dead.append((u, detail))
            else:
                errors.append((u, detail))

        if workers == 1:
            for i, u in enumerate(urls, 1):
                status, detail = check_url(u, timeout, retries=retries)
                _classify(u, status, detail)
                if i % 50 == 0:
                    self.stdout.write('  checked %d/%d...' % (i, len(urls)))
        else:
            # Read-only GETs → safe to parallelise; aggregation stays single-threaded here.
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = pool.map(lambda u: (u, *check_url(u, timeout, retries=retries)), urls)
                for i, (u, status, detail) in enumerate(results, 1):
                    _classify(u, status, detail)
                    if i % 100 == 0:
                        self.stdout.write('  checked %d/%d...' % (i, len(urls)))

        # Build the per-URL failure list (dead + errors) WITH the institution(s) behind each,
        # so the dashboard's "Problem links" drill-down can group + show who owns each bad link.
        def _failure(u, kind, detail=''):
            r = refs.get(u, {'inst': 0, 'offer': 0})
            return {'url': u, 'kind': kind, 'detail': str(detail),
                    'institutions': sorted(names.get(u, []))[:5], 'refs': r['inst'] + r['offer']}
        failures = ([_failure(u, 'gone', code) for u, code in sorted(dead)]
                    + [_failure(u, 'gated', code) for u, code in sorted(gated)]
                    + [_failure(u, why) for u, why in sorted(errors)])

        # Split failures into three severities: genuinely BROKEN (see BROKEN_KINDS) vs ACCESS-BLOCKED
        # (gated 401/403 — server's there but refused this page; eyeball it) vs COULDN'T-VERIFY
        # (timeout/conn — almost certainly alive). The dashboard headline counts BROKEN only.
        broken = [f for f in failures if f['kind'] in BROKEN_KINDS]
        gated_f = [f for f in failures if f['kind'] == 'gated']
        unverified = [f for f in failures if f['kind'] not in BROKEN_KINDS and f['kind'] != 'gated']

        self.stdout.write('\nAlive:        %d (incl. %d insecure-cert but reachable)' % (alive, insecure))
        self.stdout.write('Broken:       %d (gone/DNS/malformed — actionable)' % len(broken))
        self.stdout.write('Access-blocked: %d (401/403 — login wall OR wrong path; eyeball)' % len(gated_f))
        self.stdout.write("Couldn't verify: %d (timeout/connection — slow from here, likely alive)" % len(unverified))

        # Record link-health for the Course Data dashboard. `insecure` is a subset of `alive`.
        # `broken`/`gated`/`unverified` are the headline severities; `dead`/`errors` kept for back-compat.
        from apps.courses.course_data_status import record_status, LINK_HEALTH
        record_status(LINK_HEALTH,
                      {'checked': len(urls), 'alive': alive, 'insecure': insecure,
                       'broken': len(broken), 'gated': len(gated_f), 'unverified': len(unverified),
                       'dead': len(dead), 'errors': len(errors),
                       'failures': failures[:300]},  # bounded; the full list is also printed below
                      detail='python manage.py validate_course_urls')

        if broken:
            self.stdout.write(self.style.WARNING('\n--- BROKEN (actionable: gone / DNS / malformed) ---'))
            for f in broken:
                r = refs.get(f['url'], {'inst': 0, 'offer': 0})
                self.stdout.write('  [%s/%s] %s  (inst:%d offer:%d)'
                                  % (f['kind'], f['detail'], f['url'], r['inst'], r['offer']))
        if gated_f:
            self.stdout.write(self.style.NOTICE(
                '\n--- ACCESS-BLOCKED (401/403 — login wall OR wrong/old path, review) ---'))
            for f in gated_f:
                self.stdout.write('  [%s] %s' % (f['detail'], f['url']))
        if unverified:
            self.stdout.write(self.style.NOTICE(
                "\n--- COULDN'T VERIFY (slow/blocked from here — likely alive, NOT auto-fixed) ---"))
            for f in unverified:
                self.stdout.write('  [%s] %s' % (f['kind'], f['url']))

        if fix and dead:
            dead_urls = [u for u, _ in dead]
            ni = Institution.objects.filter(url__in=dead_urls).update(url='')
            no = CourseInstitution.objects.filter(hyperlink__in=dead_urls).update(hyperlink='')
            self.stdout.write(self.style.SUCCESS(
                '\nCleared %d Institution.url + %d CourseInstitution.hyperlink (confirmed dead).' % (ni, no)))
        elif fix:
            self.stdout.write('\nNothing to fix.')
