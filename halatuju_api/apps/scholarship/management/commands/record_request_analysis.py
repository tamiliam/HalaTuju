"""
Stage the ENGINEER'S ANALYSIS on an org request, as a DRAFT (TD-204).

Owner ruling, 2026-07-31: *"Gemini's role is only initial analysis. It has no access to the
codebase and cannot reliably do much. You have to do the proper analysis and estimate the workload,
and I want you to post as well, with my approval."*

This is the "post as well" half. It writes a DRAFT and nothing else — the owner approves it in the
cockpit, and only approval puts the prose in front of the requesting organisation. Staging is not a
privileged act because a draft is invisible to them by construction; approval is the control.

**THE REASON THIS IS A COMMAND AND NOT A FORM: it runs inside the repo, so it can check that every
cited file actually EXISTS.** An unchecked citation is decoration. The standing rule is that the
estimate must cite its files — 3.5h on request #3 named the mailer and the hook and was checkable
in a minute; 24h on the sponsor invite named nothing and was wrong by a factor of six. A path that
does not resolve is refused here rather than reaching the owner as evidence.

It also captures `repo_sha` from git automatically, so an estimate always records the commit it was
read against — a citation three weeks stale is worth knowing about.

⚠ **A COMPLETION report states TOTAL spent vs TOTAL planned** (owner, 2026-08-01), summed across
EVERY non-superseded analysis on the request — never just the leg you have in front of you. A
request that was re-scoped mid-flight (#6: 2h for one module, then 4h more once the owner widened
it to the whole console) reports six planned, not four, and says why the plan moved. Reporting the
last leg alone drops earlier effort and flatters the number exactly when the request was hardest.

## Two modes, and API is the one to use (TD-206, 2026-08-01)

**`--api` (recommended): no database password anywhere.** Posts to the super-only endpoint that
already exists (`POST /admin/scholarship/requests/<id>/analysis/`), authenticated by a SHORT-LIVED
Supabase access token. Nothing durable is stored: the token is held in memory for the length of one
command, and if you log in here the password is read with `getpass` and never written down.

Staging used to require exporting live `DB_*` from `gcloud run services describe` onto a laptop. It
was done twice in one sprint and deleted twice — a MANUAL mitigation, and those fail eventually,
because the day you forget is indistinguishable from the day you remember. The endpoint was already
there; only the transport was wrong.

    HALATUJU_ADMIN_TOKEN=<jwt> python manage.py record_request_analysis --file a.json --api --apply
    python manage.py record_request_analysis --file a.json --api --apply    # prompts to log in

**Direct database (the default, for local development).** Writes through the SERVICE layer
(`org_requests.record_analysis`), never raw ORM, so the body / citation / window rules hold
identically however the row is created. Standing project rule, which extends verbatim to this
table: never write to `org_request_analyses` through Supabase MCP.

⚠ **The dev database here is SQLite.** The first line of output is always the target — the database
in DB mode, the API host in `--api` mode — so read it before answering for anything.

The payload is JSON so multi-kilobyte prose never goes on a command line:

    {
      "request_id": 2,
      "estimated_hours": "4.0",          // optional; owner-only, never shown to the requester
      "cited_files": ["apps/scholarship/referrals.py", "..."],
      "authored_by": "claude-opus-5",    // optional
      "proposed_kind": "feature",        // optional; PREFILLS the owner's triage form, applies nothing
      "proposed_lane": "small_change",   // optional; same
      "body": "Plain-language reasoning. THIS is what the organisation reads."
    }

    python manage.py record_request_analysis --file analysis.json           # report only
    python manage.py record_request_analysis --file analysis.json --apply
"""
import getpass
import json
import os
import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.scholarship import org_requests
from apps.scholarship.models import OrgRequest

# The repository root — this file is at <root>/halatuju_api/apps/scholarship/management/commands/.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), *([os.pardir] * 5)))

# The live service. Overridable by --api-url / HALATUJU_API_URL for a staging host or a local
# runserver; the default is deliberately the real one, because staging an analysis against a
# database nobody reads is a silent no-op and this command's whole job is to be read.
_DEFAULT_API = 'https://halatuju-api-l6l7b6xaia-as.a.run.app'

_ANALYSIS_PATH = '/api/v1/admin/scholarship/requests/{rid}/analysis/'
_DETAIL_PATH = '/api/v1/admin/scholarship/requests/{rid}/'


def _repo_sha():
    """The commit the analysis was read against, or '' if git is unavailable.

    Best-effort by design: a missing SHA weakens the record slightly, and failing the whole
    command over it would be worse.
    """
    try:
        out = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=_REPO_ROOT,
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ''
    except Exception:       # noqa: BLE001 — never fail an analysis over provenance metadata
        return ''


def _missing_paths(paths):
    """The cited paths that do not exist in the working tree.

    Repo-relative (the form stored and shown to the owner). A path escaping the repo root is
    reported as missing rather than resolved — a citation is a pointer into THIS codebase.
    """
    missing = []
    for path in paths:
        full = os.path.normpath(os.path.join(_REPO_ROOT, path))
        if not full.startswith(_REPO_ROOT) or not os.path.exists(full):
            missing.append(path)
    return missing


# ── The local credential file (gitignored, repo root) ────────────────────────

_ENV_PATH = os.path.join(_REPO_ROOT, '.env')


def _env_value(key):
    """A value from the process environment, falling back to the gitignored root `.env`.

    Nothing in this project loads that file into Django, so the command reads it itself rather
    than asking the owner to export three variables before every run.
    """
    live = (os.environ.get(key) or '').strip()
    if live:
        return live
    try:
        with open(_ENV_PATH, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                name, _, value = line.partition('=')
                if name.strip() == key:
                    return value.strip().strip('"').strip("'")
    except OSError:
        pass
    return ''


def _env_write(values):
    """Update-or-append keys in the root `.env`, leaving every other line exactly as it was.

    Rewritten in full because there is no partial-write primitive, so the read-modify-write must
    preserve comments and ordering or it will quietly eat someone's notes.
    """
    try:
        with open(_ENV_PATH, encoding='utf-8') as fh:
            lines = fh.read().splitlines()
    except OSError:
        lines = []

    remaining = dict(values)
    out = []
    for line in lines:
        name = line.partition('=')[0].strip()
        if name in remaining:
            out.append(f'{name}={remaining.pop(name)}')
        else:
            out.append(line)
    out.extend(f'{k}={v}' for k, v in remaining.items())
    with open(_ENV_PATH, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(out) + '\n')


# ── API transport (TD-206) ───────────────────────────────────────────────────

def _token_from_supabase(grant, payload, *, stdout):
    """One Supabase token exchange. Returns (access_token, refresh_token).

    ⚠ Supabase ROTATES the refresh token on every use: the reply carries a NEW one and the old
    one stops working. Failing to persist the new value turns a "set it up once" credential into a
    single-use one that breaks on the SECOND run, when nobody is watching any more.
    """
    url = _env_value('SUPABASE_URL') or getattr(settings, 'SUPABASE_URL', '')
    anon = _env_value('SUPABASE_ANON_KEY')
    if not url or not anon:
        raise CommandError(
            'SUPABASE_URL and SUPABASE_ANON_KEY (the publishable key) must be in the environment '
            'or the gitignored root .env. Neither is a secret in the dangerous sense — the '
            'publishable key ships in the browser bundle — but neither is guessable either.')

    import requests as http

    try:
        resp = http.post(f'{url.rstrip("/")}/auth/v1/token?grant_type={grant}',
                         headers={'apikey': anon, 'Content-Type': 'application/json'},
                         json=payload, timeout=30)
    except Exception as e:      # noqa: BLE001 — network shapes vary; the message is what matters
        raise CommandError(f'Could not reach Supabase: {e}')
    if resp.status_code != 200:
        # ⚠ SURFACE SUPABASE'S OWN REASON. The first cut said only "(400). Check the email and
        # password", which sent the owner hunting for a typo in a password that does not exist:
        # the super account is GOOGLE-ONLY (`encrypted_password` is null), so the password grant
        # can never succeed for it. A status code with a guessed cause attached is worse than a
        # status code alone, because it is confidently wrong.
        try:
            body = resp.json() or {}
            reason = body.get('error_description') or body.get('msg') or body.get('error') or ''
        except ValueError:
            reason = resp.text[:200]
        hint = ('The stored refresh token is spent or revoked — re-bootstrap.'
                if grant == 'refresh_token' else
                'If this account signs in with GOOGLE it has no password to grant, and never '
                'will: bootstrap a refresh token instead (--bootstrap-file).')
        raise CommandError(
            f'Supabase refused the {grant} grant ({resp.status_code}): {reason or "no reason given"}. {hint}')

    data = resp.json() or {}
    access = data.get('access_token') or ''
    if not access:
        raise CommandError('Supabase returned no access token.')
    return access, (data.get('refresh_token') or '')


def _mint_session(stdout):
    """A session of the command's OWN, minted with the service-role key. No browser, no password.

    Two calls, exactly what following an emailed magic link does: `admin/generate_link` returns a
    `hashed_token` (service role), and `/verify` exchanges it for a real session (publishable key).

    ⚠ THIS IS THE ONLY ROUTE THAT SURVIVES THIS PROJECT'S SETTINGS, and each alternative failed for
    a different structural reason, all of them permanent:
      • the password grant is behind CAPTCHA ("request disallowed (no captcha_token found)"), and a
        command line cannot produce a captcha token — so `--bootstrap-login` can never work here;
      • the super account signs in with GOOGLE, so for a long time it had no password at all;
      • a refresh token copied from the browser dies the moment the browser rotates it ("Already
        Used") — two clients cannot share one rotation family.
    Minting sidesteps all three: a fresh, independent session per run, nothing stored, nothing to
    expire, nothing to rotate out from under it.

    ⚠ IT ADDS NO PRIVILEGE. Anything reachable with the minted session was already reachable with
    the service-role key directly — that key bypasses row-level security entirely. What it buys is
    that the write travels through the API's flag, role, org-fence and service-layer gates instead
    of around them, which is the whole point of TD-206. Be honest about that in any note claiming
    the laptop holds "no powerful credential": it holds this one, and always did.
    """
    url = (_env_value('SUPABASE_URL') or getattr(settings, 'SUPABASE_URL', '')).rstrip('/')
    service = _env_value('SUPABASE_SERVICE_ROLE_KEY') or getattr(
        settings, 'SUPABASE_SERVICE_ROLE_KEY', '')
    anon = _env_value('SUPABASE_ANON_KEY')
    email = _env_value('HALATUJU_ADMIN_EMAIL')
    if not (url and service and anon and email):
        return ''          # not configured for minting — the caller falls through

    import requests as http

    svc = {'apikey': service, 'Authorization': f'Bearer {service}',
           'Content-Type': 'application/json'}
    try:
        gr = http.post(f'{url}/auth/v1/admin/generate_link',
                       headers=svc, json={'type': 'magiclink', 'email': email}, timeout=30)
    except Exception as e:      # noqa: BLE001
        raise CommandError(f'Could not reach Supabase to mint a session: {e}')
    if gr.status_code != 200:
        raise CommandError(
            f'Could not mint a session ({gr.status_code}): {gr.text[:200]}. '
            f'Is {email} still a user on this project?')
    hashed = (gr.json() or {}).get('hashed_token') or ''
    if not hashed:
        raise CommandError('Supabase returned no hashed_token to exchange.')

    try:
        vr = http.post(f'{url}/auth/v1/verify',
                       headers={'apikey': anon, 'Content-Type': 'application/json'},
                       json={'type': 'magiclink', 'token_hash': hashed}, timeout=30)
    except Exception as e:      # noqa: BLE001
        raise CommandError(f'Could not exchange the minted link: {e}')
    if vr.status_code != 200:
        raise CommandError(f'The minted link would not exchange ({vr.status_code}): {vr.text[:200]}')
    access = (vr.json() or {}).get('access_token') or ''
    if not access:
        raise CommandError('The exchange returned no access token.')
    return access


def _acquire_token(stdout, *, force_login=False):
    """A short-lived Supabase access token for a SUPER admin.

    ⚠ ``force_login`` skips BOTH stored credentials and goes straight to the password grant. It
    exists because the ordinary order is a trap for the one command that has to repair things: a
    SPENT refresh token would be tried first, fail with "Already Used", and the bootstrap that was
    meant to replace it would never reach the prompt. The recovery path must not depend on the
    thing it is recovering from.

    Three sources, in order, and the order is the whole design:

    1. ``HALATUJU_ADMIN_TOKEN`` — an explicit override for a one-off run.
    2. ``HALATUJU_REFRESH_TOKEN`` — the ordinary path. Mints a fresh access token, so nobody has
       to fetch one by hand ever again, and immediately stores the ROTATED refresh token.
    3. An interactive login, which also stores the refresh token so step 2 works next time.

    Access tokens live about an hour and are never written down. The refresh token IS durable, and
    that is a deliberate, smaller concession than what it replaced: it is scoped to one admin's
    cockpit role rather than the whole database, it grants nothing that login does not, and
    "sign out everywhere" revokes it. A `DB_PASSWORD` had none of those properties.
    """
    token = '' if force_login else (os.environ.get('HALATUJU_ADMIN_TOKEN') or '').strip()
    if token:
        return token

    # The ordinary path: mint a fresh session. Nothing is stored, so nothing can go stale.
    if not force_login:
        minted = _mint_session(stdout)
        if minted:
            return minted

    refresh = '' if force_login else _env_value('HALATUJU_REFRESH_TOKEN')
    if refresh:
        access, rotated = _token_from_supabase('refresh_token', {'refresh_token': refresh},
                                               stdout=stdout)
        if rotated and rotated != refresh:
            _env_write({'HALATUJU_REFRESH_TOKEN': rotated})
        return access

    # Refuse BEFORE prompting. Asking for a password we cannot possibly exchange wastes the typing
    # and, worse, teaches the habit of entering it into a program that then fails.
    if not (_env_value('SUPABASE_URL') or getattr(settings, 'SUPABASE_URL', '')) \
            or not _env_value('SUPABASE_ANON_KEY'):
        raise CommandError(
            'No credential and nothing to log in with. Set HALATUJU_ADMIN_TOKEN for a one-off run, '
            'or put SUPABASE_URL + SUPABASE_ANON_KEY (the publishable key) in the gitignored root '
            '.env — then --bootstrap-file stores a refresh token and this never asks again.')

    stdout.write('No stored credential. Log in as a SUPER admin (the password is not stored):')
    email = input('  email    : ').strip()
    password = getpass.getpass('  password : ')
    access, rotated = _token_from_supabase('password', {'email': email, 'password': password},
                                           stdout=stdout)
    if rotated:
        _env_write({'HALATUJU_REFRESH_TOKEN': rotated})
        stdout.write('Stored the refresh token in .env - this was the last manual login.')
    return access


def _api_call(method, api_url, path, token, *, payload=None):
    """One authenticated call, with the API's own error CODE surfaced rather than a bare status.

    The endpoint answers `analysis_required` / `files_required` / `body_required` and friends; a
    caller told only "400" would have to go and read the source to learn which rule it broke.
    """
    import requests as http

    url = api_url.rstrip('/') + path
    try:
        resp = http.request(method, url, headers={'Authorization': f'Bearer {token}'},
                            json=payload, timeout=60)
    except Exception as e:      # noqa: BLE001
        raise CommandError(f'Could not reach the API at {url}: {e}')

    if resp.status_code in (401, 403):
        # ⚠ Print what the API SAID, not what we assume it meant. The first cut answered every
        # refusal with "tokens expire after about an hour — get a fresh one", and the real answer
        # was "Admin access required": the token was valid and unexpired, but belonged to an
        # ANONYMOUS session with no admin row behind it. Second time in one day that a guessed
        # cause cost more than the bare status would have.
        try:
            said = (resp.json() or {}).get('error') or resp.text[:200]
        except ValueError:
            said = resp.text[:200]
        extra = ('401 means the token did not verify — usually expired (they last about an hour).'
                 if resp.status_code == 401 else
                 '403 means it verified but carries no super-admin identity. A token copied from a '
                 'browser can belong to an ANONYMOUS session rather than your signed-in one.')
        raise CommandError(f'The API refused the token ({resp.status_code}): {said}. {extra}')
    if resp.status_code == 404:
        raise CommandError(
            'Not found (404). Either no request with that id, or it belongs to another '
            'organisation, or REQUESTS_ENABLED is off on this service.')
    if resp.status_code >= 400:
        try:
            code = (resp.json() or {}).get('error') or resp.text[:200]
        except ValueError:
            code = resp.text[:200]
        raise CommandError(f'Refused ({resp.status_code}): {code}')
    try:
        return resp.json()
    except ValueError:
        return {}


class Command(BaseCommand):
    help = "Stage the engineer's analysis on an org request as a draft. Report by default."

    def add_arguments(self, parser):
        parser.add_argument('--file', required=False,
                            help='Path to the JSON payload (see the module docstring).')
        parser.add_argument('--bootstrap-file', default='',
                            help='One-time: a JSON file holding {supabase_url?, '
                                 'supabase_anon_key?, refresh_token?}. Moves them into the '
                                 'gitignored .env and DELETES the source file. Never pass a '
                                 'credential on the command line - shell history keeps it.')
        parser.add_argument('--bootstrap-login', action='store_true',
                            help='One-time: log in and store a refresh token, so no access token '
                                 'is ever fetched by hand again. Creates its OWN session - it will '
                                 'not disturb the one your browser is using.')
        parser.add_argument('--apply', action='store_true',
                            help='Write the draft. Without it, report only.')
        parser.add_argument('--api', action='store_true',
                            help='Post to the live API instead of writing to the database '
                                 '(TD-206 — no database password needed).')
        parser.add_argument('--api-url', default='',
                            help=f'API base URL. Default: $HALATUJU_API_URL or {_DEFAULT_API}')

    def _bootstrap(self, path):
        """Move a refresh token (and optionally the Supabase URL / publishable key) into `.env`.

        A FILE rather than an argument because a credential on a command line is a credential in
        shell history, and the source is deleted afterwards so the copy does not outlive the move.
        """
        try:
            with open(path, encoding='utf-8') as fh:
                raw = fh.read().strip()
        except OSError as e:
            raise CommandError(f'Could not read the bootstrap file: {e}')

        # Either a JSON object or a file holding NOTHING BUT the refresh token. The raw form
        # exists so a credential can go straight from the browser into a text file and then into
        # `.env` without ever being read aloud, pasted into a chat, or typed on a command line —
        # every one of which leaves a copy somewhere that outlives the move.
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError
        except ValueError:
            if not raw:
                raise CommandError('The bootstrap file is empty.')
            data = {'refresh_token': raw}

        wanted = {'HALATUJU_REFRESH_TOKEN': (data.get('refresh_token') or '').strip(),
                  'SUPABASE_URL': (data.get('supabase_url') or '').strip(),
                  'SUPABASE_ANON_KEY': (data.get('supabase_anon_key') or '').strip(),
                  'HALATUJU_ADMIN_EMAIL': (data.get('admin_email') or '').strip()}
        values = {k: v for k, v in wanted.items() if v}
        if not values:
            raise CommandError('The bootstrap file carried none of refresh_token / supabase_url / '
                               'supabase_anon_key.')

        _env_write(values)
        try:
            os.unlink(path)
        except OSError:
            self.stdout.write(self.style.WARNING(
                f'Stored, but could not delete {path} - remove it by hand, it holds a credential.'))

        self.stdout.write(self.style.SUCCESS(
            f'Stored {", ".join(sorted(values))} in {_ENV_PATH} (gitignored).'))
        self.stdout.write('Future runs mint their own short-lived token. No more manual fetching.')

    def handle(self, *args, **options):
        if options['bootstrap_file']:
            self._bootstrap(options['bootstrap_file'])
            return
        if options['bootstrap_login']:
            # A FRESH session, deliberately. Reusing the refresh token out of a browser would put
            # two clients in one rotation family: the moment this command minted a token the
            # browser's copy would be spent, and the owner would find themselves signed out of the
            # cockpit by their own tooling.
            _acquire_token(self.stdout, force_login=True)
            self.stdout.write(self.style.SUCCESS('Logged in and stored a refresh token.'))
            self.stdout.write('Your browser session is untouched. This will not ask again.')
            return
        if not options['file']:
            raise CommandError('--file is required (or --bootstrap-file for the one-time setup).')

        apply = options['apply']
        use_api = options['api']
        api_url = (options['api_url'] or os.environ.get('HALATUJU_API_URL') or _DEFAULT_API)

        # First line, always: this command can be pointed at production, and the local default is
        # SQLite. Read it before trusting anything below.
        if use_api:
            self.stdout.write(f'API: {api_url}')
        else:
            db = connection.settings_dict
            self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")

        try:
            with open(options['file'], encoding='utf-8') as fh:
                payload = json.load(fh)
        except (OSError, ValueError) as e:
            raise CommandError(f'Could not read the payload: {e}')
        if not isinstance(payload, dict):
            raise CommandError('The payload must be a JSON object.')

        rid = payload.get('request_id')
        body = (payload.get('body') or '').strip()
        files = payload.get('cited_files') or []
        if not isinstance(files, list):
            raise CommandError('cited_files must be a list of repo-relative paths.')

        # The guard that makes this a command rather than a form. It runs in BOTH modes and BEFORE
        # any network call — the citation check is the reason this exists, so it can never be the
        # thing that gets skipped because a transport was slow or a token had expired.
        missing = _missing_paths([f for f in files if isinstance(f, str)])
        if missing:
            raise CommandError(
                'These cited files do not exist in the working tree, so they are not evidence:\n  '
                + '\n  '.join(missing))

        sha = _repo_sha()

        token = None
        if use_api:
            token = _acquire_token(self.stdout)
            detail = _api_call('GET', api_url, _DETAIL_PATH.format(rid=rid), token)
            title = detail.get('title') or ''
            status = detail.get('status') or '?'
            org_name = detail.get('organisation_name') or '?'
        else:
            req = OrgRequest.objects.filter(pk=rid).first()
            if req is None:
                raise CommandError(f'No org request with id {rid!r}.')
            title, status, org_name = req.title, req.status, req.organisation.name

        self.stdout.write('')
        self.stdout.write(f'Request #{rid} [{status}] {title}')
        self.stdout.write(f'  organisation : {org_name}')
        self.stdout.write(f'  hours        : {payload.get("estimated_hours") or "(none)"}   '
                          '(owner-only - the requester never sees this)')
        proposal = ' / '.join(x for x in (payload.get('proposed_kind'),
                                          payload.get('proposed_lane')) if x)
        self.stdout.write(f'  proposed     : {proposal or "(no opinion)"}   '
                          '(prefills the triage form - the owner still presses Run)')
        self.stdout.write(f'  repo sha     : {sha[:12] or "(git unavailable)"}')
        self.stdout.write(f'  cited files  : {len(files)}, all present')
        for path in files:
            self.stdout.write(f'      {path}')
        self.stdout.write('')
        self.stdout.write('  body (this IS what the organisation reads once you approve it):')
        for line in body.splitlines() or ['(empty)']:
            self.stdout.write(f'      {line}')

        if not apply:
            self.stdout.write('')
            self.stdout.write('Report only - re-run with --apply to stage this draft.')
            return

        if use_api:
            _api_call('POST', api_url, _ANALYSIS_PATH.format(rid=rid), token, payload={
                'body': body,
                'estimated_hours': payload.get('estimated_hours'),
                'cited_files': files,
                'authored_by': payload.get('authored_by') or '',
                'repo_sha': sha,
                'proposed_kind': payload.get('proposed_kind') or '',
                'proposed_lane': payload.get('proposed_lane') or '',
            })
            staged = 'Staged the analysis'
        else:
            try:
                analysis = org_requests.record_analysis(
                    req, None,
                    body=body,
                    estimated_hours=payload.get('estimated_hours'),
                    cited_files=files,
                    authored_by=payload.get('authored_by') or '',
                    repo_sha=sha,
                    # ⚠ THE PROPOSAL TRAVELS ON BOTH PATHS OR ON NEITHER. Omitted here until
                    # 2026-08-18, so every analysis staged against a database — the DEFAULT mode —
                    # silently lost its proposed triage while the dry-run report printed it back
                    # as though it had been carried. The owner's triage form then seeded from the
                    # AI's reading instead of the engineer's, on the two values that decide whether
                    # the organisation is CHARGED.
                    proposed_kind=payload.get('proposed_kind') or '',
                    proposed_lane=payload.get('proposed_lane') or '')
            except org_requests.OrgRequestError as e:
                raise CommandError(f'Refused: {e.code}')
            staged = f'Staged analysis #{analysis.id}'

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'{staged} on request #{rid} as a DRAFT.'))
        self.stdout.write('Nothing has reached the organisation. '
                          'Approve it in the cockpit to post it.')
