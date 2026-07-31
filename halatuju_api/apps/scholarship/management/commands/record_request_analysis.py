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

**Writes through the SERVICE layer** (`org_requests.record_analysis`), never raw ORM, so the body /
citation / window rules hold identically however the row is created. Standing project rule, which
extends verbatim to this table: never write to `org_request_analyses` through Supabase MCP.

⚠ **The dev database here is SQLite.** Run against production only with the prod `DB_*` exported
from `gcloud run services describe halatuju-api` — the first line of output is always the database
being written to, so read it before answering the confirmation.

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
import json
import os
import subprocess

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.scholarship import org_requests
from apps.scholarship.models import OrgRequest

# The repository root — this file is at <root>/halatuju_api/apps/scholarship/management/commands/.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), *([os.pardir] * 5)))


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


class Command(BaseCommand):
    help = "Stage the engineer's analysis on an org request as a draft. Report by default."

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True,
                            help='Path to the JSON payload (see the module docstring).')
        parser.add_argument('--apply', action='store_true',
                            help='Write the draft. Without it, report only.')

    def handle(self, *args, **options):
        apply = options['apply']
        db = connection.settings_dict
        # First line, always: this command can be pointed at production, and the local default is
        # SQLite. Read it before trusting anything below.
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")

        try:
            with open(options['file'], encoding='utf-8') as fh:
                payload = json.load(fh)
        except (OSError, ValueError) as e:
            raise CommandError(f'Could not read the payload: {e}')
        if not isinstance(payload, dict):
            raise CommandError('The payload must be a JSON object.')

        req = OrgRequest.objects.filter(pk=payload.get('request_id')).first()
        if req is None:
            raise CommandError(f"No org request with id {payload.get('request_id')!r}.")

        body = (payload.get('body') or '').strip()
        files = payload.get('cited_files') or []
        if not isinstance(files, list):
            raise CommandError('cited_files must be a list of repo-relative paths.')

        # The guard that makes this a command rather than a form.
        missing = _missing_paths([f for f in files if isinstance(f, str)])
        if missing:
            raise CommandError(
                'These cited files do not exist in the working tree, so they are not evidence:\n  '
                + '\n  '.join(missing))

        sha = _repo_sha()
        self.stdout.write('')
        self.stdout.write(f'Request #{req.id} [{req.status}] {req.title}')
        self.stdout.write(f'  organisation : {req.organisation.name}')
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

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Staged analysis #{analysis.id} on request #{req.id} as a DRAFT.'))
        self.stdout.write('Nothing has reached the organisation. '
                          'Approve it in the cockpit to post it.')
