"""The admin System health light: five rows, each green / amber / red, for super admins (2026-10-28).

Read-only and free — it calls no API. Gemini and Vision are judged from the outcomes already stamped
on documents (the same rules as the outage alert, `services/outage.py`); email and the scheduled
jobs from what their recorders wrote (`system_health_store`). Each row carries a machine `code` and
`params`; the admin web turns them into words in the reader's language (`admin.systemHealth.*`).

The thresholds are named constants below so the rules can be read, and changed, in one place.
"""
import re
from datetime import datetime, timedelta

from django.utils import timezone

from ..cron_health import EXPECTED_CADENCE
from ..models import ApplicantDocument
from .. import system_health_store as store
from .outage import _outage_stats, gemini_read_outcome, ic_second_opinion_outcome, vision_outcome

GREEN, AMBER, RED = 'green', 'amber', 'red'
_RANK = {GREEN: 0, AMBER: 1, RED: 2}

# ── Gemini / Vision ────────────────────────────────────────────────────────────────────────
#: Red when `outage.is_down` holds over this window: every read in it failed on our side.
READ_DOWN_WINDOW_HOURS = 2
#: Amber when any read in this window failed on our side (but the service is not down).
READ_FAILURE_WINDOW_HOURS = 1
#: How far back "last OK" looks, and how many of the newest stamped rows it reads to find one.
LAST_OK_LOOKBACK = timedelta(days=7)
LAST_OK_SCAN = 300

# ── Email ──────────────────────────────────────────────────────────────────────────────────
#: Red when this many sends in a row have failed…
EMAIL_RED_STREAK = 3
#: …or when there were failures and no success at all within this window.
EMAIL_NO_SUCCESS_WINDOW = timedelta(hours=24)
#: Amber when any send failed within this window.
EMAIL_AMBER_WINDOW = timedelta(hours=1)

# ── Scheduled jobs ─────────────────────────────────────────────────────────────────────────
#: A run may land this late before it counts as missed: a tenth of the cadence, at least
#: `CRON_GRACE_MIN` (Scheduler jitter, a slow run) and at most `CRON_GRACE_MAX`.
CRON_GRACE_SHARE = 0.1
CRON_GRACE_MIN = timedelta(minutes=10)
CRON_GRACE_MAX = timedelta(days=1)
#: Red when the last run errored this many times running; amber at one.
CRON_RED_ERRORS = 2

# ── AI credit ──────────────────────────────────────────────────────────────────────────────
#: A Gemini read error that says the bill, not the document: HTTP 402, "prepay(ment)", "credit",
#: "billing" (2026-10-24: "402 RESOURCE_EXHAUSTED … Your prepayment credits are depleted").
_BILLING_ERROR = re.compile(r'\b402\b|prepay|credit|billing', re.IGNORECASE)
CREDIT_WINDOW = timedelta(hours=24)

ROW_KEYS = ('gemini', 'vision', 'email', 'cron', 'credit')


def _row(key, status, code, params=None, last_ok_at=None):
    return {'key': key, 'status': status, 'code': code, 'params': params or {},
            'last_ok_at': last_ok_at.isoformat() if last_ok_at else None}


def _parse(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return dt if timezone.is_aware(dt) else timezone.make_aware(dt)


def _hhmm(dt):
    return timezone.localtime(dt).strftime('%H:%M')


# ── Gemini / Vision ────────────────────────────────────────────────────────────────────────

def _vision_events(now):
    """(stamp, outcome, error) for the newest Vision OCR attempts, newest first."""
    docs = (ApplicantDocument.objects
            .filter(vision_run_at__gte=now - LAST_OK_LOOKBACK, vision_run_at__lte=now)
            .order_by('-vision_run_at')
            .only('doc_type', 'vision_run_at', 'vision_error', 'vision_nric', 'vision_name',
                  'content_type', 'storage_path')[:LAST_OK_SCAN])
    return [(d.vision_run_at, vision_outcome(d), d.vision_error or '') for d in docs]


def _gemini_events(now):
    """(stamp, outcome, error) for the newest Gemini reads — document reads and the IC's required
    second opinion — newest first. Only the keys the rules read are fetched, never the whole read."""
    since = now - LAST_OK_LOOKBACK
    events = []
    reads = (ApplicantDocument.objects
             .filter(vision_fields_run_at__gte=since, vision_fields_run_at__lte=now)
             .order_by('-vision_fields_run_at')
             .values_list('vision_fields_run_at', 'vision_fields__error', 'vision_fields__capture')
             [:LAST_OK_SCAN])
    for stamp, err, capture in reads:
        outcome = gemini_read_outcome({'error': err or '', 'capture': capture})
        if outcome != 'skip':
            events.append((stamp, outcome, err or ''))
    seconds = (ApplicantDocument.objects
               .filter(doc_type__in=('ic', 'parent_ic'), vision_run_at__gte=since,
                       vision_run_at__lte=now, vision_fields__has_key='ic_second_opinion')
               .order_by('-vision_run_at')
               .values_list('vision_run_at', 'vision_fields__ic_second_opinion',
                            'vision_fields__ic_second_opinion_error')[:LAST_OK_SCAN])
    for stamp, opinion, err in seconds:
        events.append((stamp, ic_second_opinion_outcome({'ic_second_opinion': opinion}), err or ''))
    events.sort(key=lambda e: e[0], reverse=True)
    return events


def _last_ok(events):
    return next((stamp for stamp, outcome, _ in events if outcome == 'ok'), None)


def read_service_row(key, now, events):
    """Gemini ('gemini') or Vision ('vision'): red when down over the last
    `READ_DOWN_WINDOW_HOURS`, amber on any service failure in the last `READ_FAILURE_WINDOW_HOURS`."""
    service = key
    last_ok = _last_ok(events)
    down = _outage_stats(service, now, READ_DOWN_WINDOW_HOURS)
    if down['is_down']:
        return _row(key, RED, 'down', {'count': str(down['service_failures']),
                                       'hours': str(READ_DOWN_WINDOW_HOURS)}, last_ok)
    recent = _outage_stats(service, now, READ_FAILURE_WINDOW_HOURS)
    if recent['service_failures']:
        return _row(key, AMBER, 'failures', {'count': str(recent['service_failures']),
                                             'attempts': str(recent['attempts'])}, last_ok)
    if not recent['attempts']:
        return _row(key, GREEN, 'idle', {}, last_ok)
    return _row(key, GREEN, 'ok', {'count': str(recent['successes'])}, last_ok)


def credit_row(now, gemini_events):
    """Red when a recent Gemini read failed with a billing error and none has worked since; amber
    when reads have worked since that error; green otherwise."""
    last_ok = _last_ok(gemini_events)
    billing = next((stamp for stamp, outcome, err in gemini_events
                    if stamp >= now - CREDIT_WINDOW and outcome == 'failed'
                    and _BILLING_ERROR.search(err or '')), None)
    if billing is None:
        return _row('credit', GREEN, 'ok', {}, last_ok)
    params = {'time': _hhmm(billing)}
    if last_ok and last_ok > billing:
        return _row('credit', AMBER, 'recovered', params, last_ok)
    return _row('credit', RED, 'payment_error', params, last_ok)


# ── Email ──────────────────────────────────────────────────────────────────────────────────

def email_row(now, data):
    if not data:
        return _row('email', GREEN, 'no_record')
    last_ok, last_fail = _parse(data.get('last_ok_at')), _parse(data.get('last_fail_at'))
    streak = int(data.get('consecutive_failures') or 0)
    if streak >= EMAIL_RED_STREAK:
        return _row('email', RED, 'failing', {'count': str(streak)}, last_ok)
    if (last_fail and last_fail >= now - EMAIL_NO_SUCCESS_WINDOW
            and (last_ok is None or last_ok < now - EMAIL_NO_SUCCESS_WINDOW)):
        return _row('email', RED, 'no_success', {}, last_ok)
    if last_fail and last_fail >= now - EMAIL_AMBER_WINDOW:
        return _row('email', AMBER, 'recent_failure', {'time': _hhmm(last_fail)}, last_ok)
    return _row('email', GREEN, 'ok', {}, last_ok)


# ── Scheduled jobs ─────────────────────────────────────────────────────────────────────────

def _grace(cadence):
    return min(max(cadence * CRON_GRACE_SHARE, CRON_GRACE_MIN), CRON_GRACE_MAX)


def cadence_word(cadence):
    for word, td in (('every15', timedelta(minutes=15)), ('hourly', timedelta(hours=1)),
                     ('daily', timedelta(days=1)), ('weekly', timedelta(days=7)),
                     ('monthly', timedelta(days=31)), ('yearly', timedelta(days=366))):
        if cadence <= td:
            return word
    return 'yearly'


def age_params(age):
    """A duration as `{amount, unit}` — minutes under two hours, hours under two days, else days —
    so no line ever says "1 hours" (the thresholds keep each unit at two or more)."""
    minutes = int(age.total_seconds() // 60)
    if minutes < 120:
        return {'amount': str(max(minutes, 1)), 'unit': 'minutes'}
    if minutes < 48 * 60:
        return {'amount': str(minutes // 60), 'unit': 'hours'}
    return {'amount': str(minutes // (24 * 60)), 'unit': 'days'}


def job_state(now, cadence, data, since):
    """`(status, code, age, last_ok)` for one scheduled job."""
    grace = _grace(cadence)
    last_ok = _parse((data or {}).get('last_ok_at'))
    errors = int((data or {}).get('consecutive_errors') or 0)
    reference = last_ok or since
    age = (now - reference) if reference else timedelta(0)
    if last_ok is None and (since is None or age <= 2 * cadence + grace) and not errors:
        return GREEN, 'waiting', age, None
    if age > 2 * cadence + grace:
        return RED, ('missed' if last_ok else 'never'), age, last_ok
    if errors >= CRON_RED_ERRORS:
        return RED, 'errored_twice', age, last_ok
    if errors:
        return AMBER, 'errored', age, last_ok
    if age > cadence + grace:
        return AMBER, 'late', age, last_ok
    return GREEN, 'ok', age, last_ok


def cron_row(now, records):
    """The worst scheduled job, named in plain words; green 'ok' when every job is on time."""
    since = _parse((records.get(store.SINCE_KEY) or {}).get('at'))
    worst, latest_ok, waiting = None, None, 0
    for job, cadence in EXPECTED_CADENCE.items():
        status, code, age, last_ok = job_state(now, cadence, records.get(store.CRON_PREFIX + job), since)
        if last_ok and (latest_ok is None or last_ok > latest_ok):
            latest_ok = last_ok
        waiting += code == 'waiting'
        overdue = age / cadence
        if status != GREEN and (worst is None or (_RANK[status], overdue) > (_RANK[worst[0]], worst[4])):
            worst = (status, code, job, age, overdue, cadence, last_ok)
    if worst is None:
        if waiting == len(EXPECTED_CADENCE):
            return _row('cron', GREEN, 'waiting', {}, latest_ok)
        return _row('cron', GREEN, 'ok', {'count': str(len(EXPECTED_CADENCE) - waiting)}, latest_ok)
    status, code, job, age, _, cadence, last_ok = worst
    params = {'job': job, 'cadence': cadence_word(cadence), **age_params(age)}
    return _row('cron', status, code, params, last_ok)


# ── All five ───────────────────────────────────────────────────────────────────────────────

def overall(rows):
    return max((r['status'] for r in rows), key=_RANK.__getitem__, default=GREEN)


def snapshot(now=None):
    """The light's whole payload: the five rows, the worst colour, and when it was checked."""
    now = now or timezone.now()
    records = store.load_all()
    gemini_events = _gemini_events(now)
    rows = [
        read_service_row('gemini', now, gemini_events),
        read_service_row('vision', now, _vision_events(now)),
        email_row(now, records.get(store.EMAIL_KEY)),
        cron_row(now, records),
        credit_row(now, gemini_events),
    ]
    return {'overall': overall(rows), 'checked_at': now.isoformat(), 'rows': rows}
