"""The admin System health light's recorders — the ONLY writers of `SystemHealthStatus` (2026-10-28).

Two choke-points call in here, and nothing else does:

  * `mail_backend.RecordingSMTPBackend.send_messages` — every email the service sends goes through
    Django's one configured backend, so recording there sees every send (`record_email`);
  * `cron_health.run_job`, the body of `CronRunView` — every Cloud Scheduler job (`record_cron`).

⚠ A RECORDER MUST NEVER BREAK WHAT IT WATCHES. Every write is (1) deferred with
`transaction.on_commit`, so it never takes a row lock inside the caller's transaction (an email sent
mid-request would otherwise hold the `email` row until that request committed, and two such requests
could deadlock on it), and runs at once when there is no transaction; (2) its own short transaction;
(3) wrapped so ANY failure — the table not migrated yet, a dropped connection — is a log line.

⚠ NO PERSONAL DATA. Timestamps, counts and an exception CLASS name only. An exception's message is
never stored: an SMTP refusal lists its recipients' addresses.
"""
import logging

from django.db import transaction
from django.utils import timezone

log = logging.getLogger(__name__)

EMAIL_KEY = 'email'
CRON_PREFIX = 'cron:'
#: When the recorders first wrote anything. A job with no run recorded is "waiting", not "missed",
#: until two of its cadences have passed since then (`services/system_health.py`).
SINCE_KEY = 'cron:_since'
#: The stored error name is cut to this — a class name, never a message.
_ERROR_MAX = 80
#: How many failure timestamps the email row keeps (newest first) — enough to count a day's worth.
_RECENT_FAILURES_KEPT = 10

#: Once this process has seen `SINCE_KEY` exist, it stops asking (one query saved per write).
_since_seen = False


def error_name(exc) -> str:
    """The exception's CLASS name and nothing else (see the module docstring for why)."""
    return type(exc).__name__[:_ERROR_MAX] if exc is not None else ''


def _now_iso():
    return timezone.now().isoformat()


def _apply(key, mutate):
    """Read-modify-write one row in its own short transaction. Raises; `_record` catches."""
    global _since_seen
    from .models import SystemHealthStatus
    with transaction.atomic():
        row = SystemHealthStatus.objects.select_for_update().filter(key=key).first()
        data = dict(row.data) if row and isinstance(row.data, dict) else {}
        mutate(data)
        SystemHealthStatus.objects.update_or_create(key=key, defaults={'data': data})
    if not _since_seen:
        SystemHealthStatus.objects.get_or_create(key=SINCE_KEY, defaults={'data': {'at': _now_iso()}})
        _since_seen = True


def _record(key, mutate):
    """Schedule the write after the caller's transaction (at once when there is none). Never raises."""
    def write():
        try:
            _apply(key, mutate)
        except Exception as e:  # a status write must never break a send or a cron run
            log.warning('System health: could not record %s (%s)', key, error_name(e))
    try:
        transaction.on_commit(write)
    except Exception as e:  # same rule, for the scheduling itself
        log.warning('System health: could not schedule %s (%s)', key, error_name(e))


def record_email(ok: bool, error: str = ''):
    """One call of the mail backend: `ok` when every message in it was accepted."""
    def mutate(d):
        now = _now_iso()
        if ok:
            d['last_ok_at'] = now
            d['consecutive_failures'] = 0
        else:
            d['last_fail_at'] = now
            d['last_error'] = (error or 'send failed')[:_ERROR_MAX]
            d['consecutive_failures'] = int(d.get('consecutive_failures') or 0) + 1
            # The newest failure times, so the light can count failures within a day.
            d['recent_failures'] = ([now] + list(d.get('recent_failures') or []))[:_RECENT_FAILURES_KEPT]
    _record(EMAIL_KEY, mutate)


def record_cron(job: str, ok: bool, error: str = ''):
    """One run of a Cloud Scheduler job through `CronRunView`."""
    def mutate(d):
        now = _now_iso()
        d['last_run_at'] = now
        if ok:
            d['last_ok_at'] = now
            d['consecutive_errors'] = 0
        else:
            d['last_error_at'] = now
            d['last_error'] = (error or 'failed')[:_ERROR_MAX]
            d['consecutive_errors'] = int(d.get('consecutive_errors') or 0) + 1
    _record(CRON_PREFIX + job, mutate)


def load_all() -> dict:
    """Every recorded row as `{key: data}`; `{}` when the table cannot be read (not migrated yet)."""
    from .models import SystemHealthStatus
    try:
        with transaction.atomic():   # a savepoint: a failed read cannot poison a caller's transaction
            return {r.key: (r.data if isinstance(r.data, dict) else {})
                    for r in SystemHealthStatus.objects.all()}
    except Exception as e:  # the light degrades to "nothing recorded yet"
        log.warning('System health: could not read the store (%s)', error_name(e))
        return {}
