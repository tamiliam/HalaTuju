"""The replay's read-only guards (design 3.4 and 3.5). Nothing here writes; everything here refuses.

* `check_environment` - the job starts only when no key that could write, pay or send is present.
* `check_database_url` - the `replay_ro` role, through the SESSION pooler port 5432 (never 6543); the only
  query parameter allowed is `sslmode=require|verify-ca|verify-full` (`options`, `service`, `hostaddr`...
  would steer the connection or set session-level settings). libpq's PG* variables are forbidden too.
* `refuse_non_reads` - the statement filter: the reviewed `offer_s4_dry_run.refuse_writes`, plus row locks
  (`FOR UPDATE` and kin), `SELECT ... INTO`, more than one statement, comments, and any function call
  that is schema-qualified or not in ALLOWED_FUNCTIONS; only the exact snapshot preamble and the two
  transaction-level timeouts below are let through on top.
* `read_only_session` - ONE transaction: `REPEATABLE READ, READ ONLY` and `SET LOCAL` lock / idle
  timeouts at TRANSACTION level (never a session setting), proved with `SHOW`, optionally exporting or
  joining a snapshot, ALWAYS rolled back.
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
#: `PG` covers libpq's own variables (PGHOST, PGUSER, PGPASSWORD, PGOPTIONS, PGSERVICE, PGSSLMODE...),
#: which would otherwise steer the connection around the checked URL.
FORBIDDEN_ENV_PREFIXES = (
    'DATABASE_URL', 'DB_', 'PG', 'GEMINI', 'OPENAI', 'ANTHROPIC', 'GOOGLE_', 'GCS_', 'AWS_', 'SUPABASE_',
    'BREVO', 'ANYMAIL', 'EMAIL_HOST', 'SENDGRID', 'MAILGUN', 'TWILIO_', 'VIRCLE_', 'CRON_SECRET',
    'SENTRY', 'AIRTABLE', 'DOCUMENT_BACKUP', 'SPONSOR_MOCK',
)
#: The ONLY URL query parameter allowed, and its only values (an encrypted connection, never off).
ALLOWED_SSLMODES = ('require', 'verify-ca', 'verify-full')
#: The one host the URL may name, once URL-decoded: a DNS name or an IPv4 address (dot-separated labels of
#: letters, digits and inner dashes). No comma (a host list), no `/` (a socket directory), no `%`, no `[`.
_SINGLE_HOST = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$')

ISOLATION_SQL = 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'
#: Transaction-level (SET LOCAL) timeouts: the job gives way instead of blocking. A statement that would
#: wait for a lock gives up after LOCK_TIMEOUT; a transaction left idle is ended by the server. The
#: parent waits for the children to join, so its idle limit is longer than the join wait.
LOCK_TIMEOUT = '5s'
IDLE_TIMEOUT_CHILD = '2min'
IDLE_TIMEOUT_PARENT = '12min'
_LOCK_SQL = f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"
_IDLE_SQL = "SET LOCAL idle_in_transaction_session_timeout = '{}'"
_SNAPSHOT_ID = re.compile(r'^[0-9A-F]{1,16}-[0-9A-F]{1,16}(-[0-9]{1,10})?$')
#: The ONLY statements let through that `refuse_writes` would refuse: the transaction preamble.
_PREAMBLE = re.compile(r"^(SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                       r"|SET TRANSACTION SNAPSHOT '[0-9A-F]{1,16}-[0-9A-F]{1,16}(-[0-9]{1,10})?')$")
_TIMEOUT_SQL = frozenset({_LOCK_SQL, _IDLE_SQL.format(IDLE_TIMEOUT_CHILD), _IDLE_SQL.format(IDLE_TIMEOUT_PARENT)})
#: Reads that still take a lock or write: row locks, SELECT INTO a table, sequences, advisory locks,
#: configuration, large objects, remote links, notifications, killing other backends.
_READ_THAT_WRITES = re.compile(
    r'\bFOR\s+(NO\s+KEY\s+)?UPDATE\b|\bFOR\s+(KEY\s+)?SHARE\b|\bINTO\b'
    r'|\b(nextval|setval|set_config|pg_advisory\w*|pg_try_advisory\w*|lo_\w+|dblink\w*|pg_notify'
    r'|pg_terminate_backend|pg_cancel_backend|pg_reload_conf|pg_export_snapshot)\s*\(', re.I)
_EXPORT_SQL = 'SELECT pg_export_snapshot()'
#: Something followed by `(`: an optional `.` before it (a schema-qualified call), then a quoted name
#: (`"nextval"`, `U&"..."`) or a bare word.
_CALL = re.compile(r'(\.\s*)?(?:(?:U&)?"((?:[^"]|"")*)"|\b([A-Za-z_][A-Za-z0-9_$]*))\s*\(')
#: Bare SQL words that may stand before `(` without being a call.
_SQL_WORDS = frozenset({
    'select', 'from', 'where', 'and', 'or', 'not', 'in', 'exists', 'as', 'on', 'join', 'any', 'all', 'some',
    'when', 'then', 'else', 'case', 'having', 'by', 'distinct', 'union', 'except', 'intersect', 'with',
    'over', 'filter', 'between', 'is', 'like', 'ilike', 'limit', 'offset', 'using', 'values', 'lateral',
})
#: The only functions a replay read may call: what the ORM and the course-data load emit. Lower case;
#: a quoted name must match exactly. R2 adds to it only when a refused read shows up as could_not_run.
ALLOWED_FUNCTIONS = frozenset({
    'count', 'sum', 'avg', 'min', 'max', 'coalesce', 'nullif', 'greatest', 'least', 'cast', 'lower', 'upper',
    'length', 'trim', 'abs', 'round', 'floor', 'ceil', 'extract', 'date_trunc', 'array_agg', 'string_agg',
    'json', 'json_extract', 'json_type', 'jsonb_typeof', 'jsonb_array_length',
})


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
    from urllib.parse import parse_qs, unquote, urlsplit
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
    query = parse_qs(parts.query, keep_blank_values=True)
    if (set(query) - {'sslmode'} or len(query.get('sslmode', ['require'])) != 1
            or query.get('sslmode', ['require'])[0] not in ALLOWED_SSLMODES
            or (parts.query and not query)):
        raise WriteRefused('replay: the URL may carry only sslmode=require, verify-ca or verify-full')
    if not parts.hostname:
        raise WriteRefused('replay: the database URL has no host')
    # dj_database_url URL-decodes the host, and libpq reads `h1,h2` as a list of hosts to try (and a
    # leading `/` as a socket directory): check the DECODED host part, and accept only one DNS name.
    host = unquote(parts.hostname)
    if ',' in unquote(parts.netloc.rpartition('@')[2]) or not _SINGLE_HOST.match(host):
        raise WriteRefused('replay: the database URL must name exactly one host')
    return host, port


# ── The statement filter (layer 4) ────────────────────────────────────────────────────────────
def refuse_non_reads(execute, sql, params, many, context):
    """`execute_wrapper`: the snapshot preamble passes; a read that locks or writes is refused; the rest
    goes through the reviewed `offer_s4_dry_run.refuse_writes`, which refuses every non-read."""
    s = str(sql or '').strip()
    if _PREAMBLE.match(s) or s in _TIMEOUT_SQL:
        return execute(sql, params, many, context)
    if s == _EXPORT_SQL and getattr(context.get('connection'), '_replay_may_export', False):
        return execute(sql, params, many, context)
    first = s.split()[0] if s.split() else ''
    if ';' in (s[:-1] if s.endswith(';') else s) or '--' in s or '/*' in s:
        raise WriteRefused(f'replay: refused more than one statement or a comment: {first}')
    if _READ_THAT_WRITES.search(s) or _refused_call(s):
        raise WriteRefused(f'replay: refused a locking, writing or unlisted call: {first}')
    return refuse_writes(execute, sql, params, many, context)


def _refused_call(s):
    """True when ``s`` calls a function that is schema-qualified, quoted unlike the allow-list, or not
    in ALLOWED_FUNCTIONS. Bare SQL words before `(` (IN, EXISTS, AS...) are not calls."""
    for m in _CALL.finditer(s):
        qualified, quoted, bare = m.group(1), m.group(2), m.group(3)
        if qualified:
            return True
        if quoted is not None:
            if quoted not in ALLOWED_FUNCTIONS:
                return True
        elif bare.lower() not in ALLOWED_FUNCTIONS and bare.lower() not in _SQL_WORDS:
            return True
    return False


# ── The transaction (layers 2 and 3) ──────────────────────────────────────────────────────────
def valid_snapshot_id(snapshot):
    s = str(snapshot or '')
    if not _SNAPSHOT_ID.match(s):
        raise WriteRefused('replay: not a snapshot id')
    return s


def begin_snapshot(cursor, *, snapshot=None, export=False):
    """The transaction's FIRST statements: repeatable read + read only for THIS transaction, joining
    ``snapshot`` if given; the transaction-level timeouts (the exporting parent waits for the children, so
    its idle limit is the longer one); then proved with SHOW. Returns the exported snapshot id when
    ``export``."""
    cursor.execute(ISOLATION_SQL)
    if snapshot:
        cursor.execute(f"SET TRANSACTION SNAPSHOT '{valid_snapshot_id(snapshot)}'")
    cursor.execute(_LOCK_SQL)
    cursor.execute(_IDLE_SQL.format(IDLE_TIMEOUT_PARENT if export else IDLE_TIMEOUT_CHILD))
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
    ('apps.scholarship.vision', '_vision_words', 'Vision'),
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
