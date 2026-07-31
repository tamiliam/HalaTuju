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


# ── API transport (TD-206) ───────────────────────────────────────────────────

def _acquire_token(stdout):
    """A short-lived Supabase access token for a SUPER admin, from the environment or a prompt.

    Order matters: an already-issued token is preferred so the common path stores and types
    nothing. The login fallback exists so the command is usable without first digging a JWT out of
    a browser; it reads the password with `getpass` and keeps neither it nor the email.

    The token is a bearer credential with a lifetime of about an hour. That expiry IS the security
    property this replaces a permanent database password with, so never cache it to disk.
    """
    token = (os.environ.get('HALATUJU_ADMIN_TOKEN') or '').strip()
    if token:
        return token

    url = (getattr(settings, 'SUPABASE_URL', '') or os.environ.get('SUPABASE_URL', '')).rstrip('/')
    anon = (os.environ.get('SUPABASE_ANON_KEY') or '').strip()
    if not url or not anon:
        raise CommandError(
            'No admin token. Either set HALATUJU_ADMIN_TOKEN to a super admin access token, or set '
            'SUPABASE_URL + SUPABASE_ANON_KEY (the publishable key) so this command can log in for '
            'you. Neither is a database password, and neither is stored by this command.')

    import requests as http

    stdout.write('Log in as a SUPER admin (nothing is stored):')
    email = input('  email    : ').strip()
    password = getpass.getpass('  password : ')
    try:
        resp = http.post(f'{url}/auth/v1/token?grant_type=password',
                         headers={'apikey': anon, 'Content-Type': 'application/json'},
                         json={'email': email, 'password': password}, timeout=30)
    except Exception as e:      # noqa: BLE001 — network shapes vary; the message is what matters
        raise CommandError(f'Could not reach Supabase to log in: {e}')
    if resp.status_code != 200:
        raise CommandError(f'Login refused ({resp.status_code}). Check the email and password.')
    token = (resp.json() or {}).get('access_token') or ''
    if not token:
        raise CommandError('Supabase returned no access token.')
    return token


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
        raise CommandError(
            f'The API refused the token ({resp.status_code}). It must belong to an ACTIVE super '
            'admin, and access tokens expire after about an hour — get a fresh one.')
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
        parser.add_argument('--file', required=True,
                            help='Path to the JSON payload (see the module docstring).')
        parser.add_argument('--apply', action='store_true',
                            help='Write the draft. Without it, report only.')
        parser.add_argument('--api', action='store_true',
                            help='Post to the live API instead of writing to the database '
                                 '(TD-206 — no database password needed).')
        parser.add_argument('--api-url', default='',
                            help=f'API base URL. Default: $HALATUJU_API_URL or {_DEFAULT_API}')

    def handle(self, *args, **options):
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
                    repo_sha=sha)
            except org_requests.OrgRequestError as e:
                raise CommandError(f'Refused: {e.code}')
            staged = f'Staged analysis #{analysis.id}'

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'{staged} on request #{rid} as a DRAFT.'))
        self.stdout.write('Nothing has reached the organisation. '
                          'Approve it in the cockpit to post it.')
