"""The replay's read-only guards (design 3.4 and 3.5). Nothing here writes; everything here refuses.

* `check_environment` - the job starts only when no key that could write, pay or send is present.
* `check_database_url` - the `replay_ro` role, through the SESSION pooler port 5432 (never 6543), with no
  startup `options` (a session-level setting would ride in there).
* `refuse_non_reads` - the statement filter: the reviewed `offer_s4_dry_run.refuse_writes`, plus row locks
  (`FOR UPDATE` and kin), `SELECT ... INTO` and the write-capable functions; only the exact snapshot
  preamble below is let through on top.
* `read_only_session` - ONE transaction: `REPEATABLE READ, READ ONLY` at TRANSACTION level (never a
  session setting), proved with `SHOW`, optionally exporting or joining a snapshot, ALWAYS rolled back.
* `run_case` - one case inside its own savepoint, always rolled back; any refusal or error becomes
  `{"error": "<ClassName>"}` and the run goes on.
"""
import contextlib
import re
import sys
from unittest import mock

from apps.scholarship.eval.offer_s4_dry_run import Unreachable, WriteRefused, refuse_writes

from .scrub import error_record

__all__ = ['WriteRefused', 'Unreachable', 'MailRefused', 'check_environment', 'check_database_url',
           'refuse_non_reads', 'begin_snapshot', 'read_only_session', 'run_case', 'shut_doors']

#: The replay's database URL is read from this name and nothing else. `DATABASE_URL` (the live api's
#: full-power URL) must be ABSENT, so a mistake cannot fall back to it.
DB_ENV = 'REPLAY_DATABASE_URL'
ROLE = 'replay_ro'
SESSION_POOLER_PORT = 5432
TRANSACTION_POOLER_PORT = 6543

#: Name prefixes of anything that writes, pays, sends or reads Storage. Present and non-empty = refuse.
FORBIDDEN_ENV_PREFIXES = (
    'DATABASE_URL', 'DB_', 'GEMINI', 'OPENAI', 'ANTHROPIC', 'GOOGLE_', 'GCS_', 'AWS_', 'SUPABASE_',
    'BREVO', 'ANYMAIL', 'EMAIL_HOST', 'SENDGRID', 'MAILGUN', 'TWILIO_', 'VIRCLE_', 'CRON_SECRET',
    'SENTRY', 'AIRTABLE', 'DOCUMENT_BACKUP', 'SPONSOR_MOCK',
)

ISOLATION_SQL = 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'
_SNAPSHOT_ID = re.compile(r'^[0-9A-F]{1,16}-[0-9A-F]{1,16}(-[0-9]{1,10})?$')
#: The ONLY statements let through that `refuse_writes` would refuse: the transaction preamble.
_PREAMBLE = re.compile(r"^(SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                       r"|SET TRANSACTION SNAPSHOT '[0-9A-F]{1,16}-[0-9A-F]{1,16}(-[0-9]{1,10})?')$")
#: Reads that still take a lock or write: row locks, SELECT INTO a table, sequences, advisory locks,
#: configuration, large objects, remote links, notifications, killing other backends.
_READ_THAT_WRITES = re.compile(
    r'\bFOR\s+(NO\s+KEY\s+)?UPDATE\b|\bFOR\s+(KEY\s+)?SHARE\b|\bINTO\b'
    r'|\b(nextval|setval|set_config|pg_advisory\w*|pg_try_advisory\w*|lo_\w+|dblink\w*|pg_notify'
    r'|pg_terminate_backend|pg_cancel_backend|pg_reload_conf|pg_export_snapshot)\s*\(', re.I)
_EXPORT_SQL = 'SELECT pg_export_snapshot()'


class MailRefused(BaseException):
    """Something tried to send an email."""


class RefusingEmailBackend:
    """The replay's EMAIL_BACKEND: opening or sending raises. A BaseException, like the other refusals."""

    def __init__(self, *args, **kwargs):
        pass

    def open(self):
        raise MailRefused('replay: email is refused')

    def send_messages(self, messages):
        raise MailRefused('replay: email is refused')

    def close(self):
        pass


# ── Preflight ──────────────────────────────────────────────────────────────────────────────────
def check_environment(env):
    """Refuse (WriteRefused, naming the variables, never their values) when a forbidden key is present."""
    bad = sorted(k for k, v in env.items()
                 if v and k != DB_ENV and k.upper().startswith(FORBIDDEN_ENV_PREFIXES))
    if bad:
        raise WriteRefused('replay: forbidden variables in the environment: ' + ', '.join(bad))
    return True


def check_database_url(url):
    """(host, port) of a replay URL that passes; WriteRefused otherwise. The message never quotes the URL."""
    from urllib.parse import parse_qs, urlsplit
    if not url:
        raise WriteRefused(f'replay: {DB_ENV} is not set')
    parts = urlsplit(url)
    if parts.scheme not in ('postgres', 'postgresql'):
        raise WriteRefused('replay: the database URL is not PostgreSQL')
    try:
        port = parts.port
    except ValueError:
        port = None
    if port == TRANSACTION_POOLER_PORT:
        raise WriteRefused('replay: port 6543 is the transaction pooler; use the session pooler, 5432')
    if port != SESSION_POOLER_PORT:
        raise WriteRefused('replay: the database URL must name the session pooler port 5432')
    if (parts.username or '').split('.', 1)[0] != ROLE:
        raise WriteRefused(f'replay: the database user must be the {ROLE} role')
    if any(k.lower() == 'options' for k in parse_qs(parts.query)):
        raise WriteRefused('replay: startup options are refused (they set session-level settings)')
    if not parts.hostname:
        raise WriteRefused('replay: the database URL has no host')
    return parts.hostname, port


# ── The statement filter (layer 4) ────────────────────────────────────────────────────────────
def refuse_non_reads(execute, sql, params, many, context):
    """`execute_wrapper`: the snapshot preamble passes; a read that locks or writes is refused; the rest
    goes through the reviewed `offer_s4_dry_run.refuse_writes`, which refuses every non-read."""
    s = str(sql or '').strip()
    if _PREAMBLE.match(s):
        return execute(sql, params, many, context)
    if s == _EXPORT_SQL and getattr(context.get('connection'), '_replay_may_export', False):
        return execute(sql, params, many, context)
    if _READ_THAT_WRITES.search(s):
        raise WriteRefused(f'replay: refused a locking or writing read: {s.split()[0] if s.split() else ""}')
    return refuse_writes(execute, sql, params, many, context)


# ── The transaction (layers 2 and 3) ──────────────────────────────────────────────────────────
def valid_snapshot_id(snapshot):
    s = str(snapshot or '')
    if not _SNAPSHOT_ID.match(s):
        raise WriteRefused('replay: not a snapshot id')
    return s


def begin_snapshot(cursor, *, snapshot=None, export=False):
    """The transaction's FIRST statements: repeatable read + read only for THIS transaction, joining
    ``snapshot`` if given; then proved with SHOW. Returns the exported snapshot id when ``export``."""
    cursor.execute(ISOLATION_SQL)
    if snapshot:
        cursor.execute(f"SET TRANSACTION SNAPSHOT '{valid_snapshot_id(snapshot)}'")
    cursor.execute('SHOW transaction_read_only')
    row = cursor.fetchone()
    if not row or str(row[0]).lower() != 'on':
        raise WriteRefused('replay: the transaction did not become read only')
    cursor.execute('SHOW transaction_isolation')
    row = cursor.fetchone()
    if not row or str(row[0]).lower() != 'repeatable read':
        raise WriteRefused('replay: the transaction is not repeatable read')
    if export:
        cursor.execute(_EXPORT_SQL)
        return valid_snapshot_id((cursor.fetchone() or [''])[0])
    return None


def _unreachable(what):
    def _raise(*a, **k):
        raise Unreachable(f'replay: {what} was reached')
    return _raise


#: (module prefix, attribute, what). Every LOADED module under the prefix that holds the attribute has it
#: shut, so a re-export and the defining module are both covered (vision is a package on main, a file on
#: v3.1.0). The real wall is that the job has no key and no network; these make a reach loud and early.
DOORS = (
    ('apps.scholarship.vision', '_fetch_image_bytes', 'Storage'),
    ('apps.scholarship.vision', '_call_gemini_json', 'Gemini'),
    ('apps.scholarship.vision', '_vision_document_text', 'Vision'),
    ('apps.scholarship.usage', 'record_usage', 'the usage meter'),
    ('google.genai', 'Client', 'Gemini'),
)


@contextlib.contextmanager
def shut_doors():
    """Storage, Gemini, Vision, the meter and email raise if reached, for the length of the block."""
    from django.test.utils import override_settings
    with contextlib.ExitStack() as stack:
        for prefix, attr, what in DOORS:
            for name, mod in list(sys.modules.items()):
                if mod is not None and (name == prefix or name.startswith(prefix + '.')) \
                        and attr in vars(mod):
                    stack.enter_context(mock.patch.object(mod, attr, _unreachable(what)))
        stack.enter_context(override_settings(
            EMAIL_BACKEND=__name__ + '.RefusingEmailBackend'))
        yield


@contextlib.contextmanager
def read_only_session(*, snapshot=None, export=False, allow_sqlite=False):
    """ONE read-only transaction, always rolled back, every door shut. Yields the exported snapshot id
    (``export``), else None. ``allow_sqlite`` is for the tests' database only (no snapshot there)."""
    from django.db import connection, transaction
    if connection.vendor != 'postgresql' and not allow_sqlite:
        raise WriteRefused(f'replay: expects PostgreSQL, got {connection.vendor}')
    connection.ensure_connection()          # connection set-up runs before the filter is in place
    with contextlib.ExitStack() as stack:
        stack.enter_context(shut_doors())
        stack.enter_context(connection.execute_wrapper(refuse_non_reads))
        with transaction.atomic():
            try:
                exported = None
                if connection.vendor == 'postgresql':
                    connection._replay_may_export = bool(export)
                    try:
                        with connection.cursor() as cur:
                            exported = begin_snapshot(cur, snapshot=snapshot, export=export)
                    finally:
                        connection._replay_may_export = False
                yield exported
            finally:
                transaction.set_rollback(True)          # never committed, error or not


#: What a case may raise and still be recorded (the run goes on). KeyboardInterrupt / SystemExit stop it.
CASE_ERRORS = (Exception, WriteRefused, Unreachable, MailRefused)


def run_case(fn):
    """``fn()`` inside its own savepoint, always rolled back. Its answer, or ``{"error": "<ClassName>"}``."""
    from django.db import transaction
    from .netguard import NetworkRefused
    try:
        with transaction.atomic():
            try:
                return fn()
            finally:
                transaction.set_rollback(True)
    except CASE_ERRORS + (NetworkRefused,) as exc:
        return error_record(exc)
