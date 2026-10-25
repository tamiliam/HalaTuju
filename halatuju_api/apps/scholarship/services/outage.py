"""Is a READ service down? The passive outage checks behind `alert_vision_outage`.

Read-only and free: each check reads the outcome already stored on the documents, and calls no
API. Moved out of `blockers.py` on 2026-10-24, when the Gemini check joined the Vision one — an
outage is not a blocker, and with both checks in it `blockers.py` stood at 597 of its 600 lines.
"""
from datetime import timedelta

from django.utils import timezone

from ..models import ApplicantDocument
from ..read_errors import (IC_SECOND_OPINION_ERROR, OCR_SERVICE_FAILED, RATE_LIMITED,
                           is_ai_service_error, is_ic_decode_error, is_ocr_service_error)

#: The hourly (start-edge) mode compares with the run one hour ago, taken a few minutes EARLIER
#: than an exact hour so Cloud Scheduler's jitter cannot slide the reference past the previous
#: run's outcome. An earlier reference can at worst repeat an alert; it cannot swallow one.
HOURLY_STEP = timedelta(minutes=65)
#: The hourly mode mails on evidence from more than one family: one stuck document is not an outage.
HOURLY_MIN_FAILURES = 2
HOURLY_MIN_APPLICATIONS = 2


def _is_pdf_upload(doc):
    """A PDF by its stored type or name — the outage check never fetches the bytes."""
    ct = (getattr(doc, 'content_type', '') or '').lower().split(';')[0].strip()
    return ct == 'application/pdf' or (getattr(doc, 'storage_path', '') or '').lower().endswith('.pdf')


def _vision_ocr_window(since, until):
    """Google-Vision OCR outcomes stamped in [since, until). IC / parent_ic: a poor image
    ('empty image' / read-nothing) is an attempt but NOT a service failure. Since 2026-10-24 every
    other document's OCR counts too (`run_vision_match_for_document` stamps `vision_run_at` and
    keeps Vision's own error in `vision_error`): no error = a success, a service error by the IC's
    decode-vs-service split (`read_errors.is_ocr_service_error`) = a failure."""
    docs = ApplicantDocument.objects.filter(
        vision_run_at__gte=since, vision_run_at__lt=until,
    ).only('doc_type', 'application_id', 'vision_error', 'vision_nric', 'vision_name',
           'content_type', 'storage_path')
    attempts = successes = service_failures = 0
    apps = set()
    sample = ''
    for d in docs:
        attempts += 1
        err = d.vision_error or ''
        if d.doc_type in ('ic', 'parent_ic'):
            ok = not err and (d.vision_nric or d.vision_name)
            failed = bool(err) and not is_ic_decode_error(err)
        else:
            # A digital PDF is read from its text layer and never reaches Vision, yet the name check
            # still stamps `vision_run_at` — so a clean PDF proves nothing about Vision (round 3).
            ok = not err and not _is_pdf_upload(d)
            failed = is_ocr_service_error(err)
        if ok:
            successes += 1
        elif failed:
            service_failures += 1
            apps.add(d.application_id)
            sample = sample or err
    return attempts, successes, service_failures, len(apps), sample


def _gemini_read_window(since, until):
    """Gemini document reads (field extraction) stamped in [since, until) — 2026-10-24, when
    Gemini's prepaid credit ran out for ~20 hours and the IC-only check above saw nothing. Only a
    read that ASKED Gemini counts (`capture` 'ai' or 'mixed'): an exact deterministic read or a
    letter's OCR text proves nothing about Gemini, our own throttle's 'rate_limited' is not an
    outage, and a supporting document's Vision OCR failure is Vision's, not Gemini's. Success = no
    error; service failure = `read_errors.is_ai_service_error`."""
    attempts = successes = service_failures = 0
    apps = set()
    sample = ''
    for app_id, vf in ApplicantDocument.objects.filter(
            vision_fields_run_at__gte=since, vision_fields_run_at__lt=until,
    ).values_list('application_id', 'vision_fields'):
        vf = vf if isinstance(vf, dict) else {}
        err = vf.get('error') or ''
        if (vf.get('capture') not in ('ai', 'mixed') or err == RATE_LIMITED
                or err.startswith(OCR_SERVICE_FAILED)):
            continue
        attempts += 1
        if not err:
            successes += 1
        elif is_ai_service_error(err):
            service_failures += 1
            apps.add(app_id)
            sample = sample or err
    # TD-390: the IC's Gemini second opinion, where one was REQUIRED, by the IC's own read stamp (an
    # IC never carries `vision_fields_run_at`, so nothing is counted twice). 'theirs' (Gemini looked
    # and refused the image) is an attempt that proves nothing either way.
    for app_id, vf in ApplicantDocument.objects.filter(
            doc_type__in=('ic', 'parent_ic'), vision_run_at__gte=since, vision_run_at__lt=until,
            vision_fields__has_key='ic_second_opinion',
    ).values_list('application_id', 'vision_fields'):
        outcome = (vf or {}).get('ic_second_opinion')
        attempts += 1
        if outcome == 'ok':
            successes += 1
        elif outcome == 'ours':
            service_failures += 1
            apps.add(app_id)
            sample = sample or (vf.get(IC_SECOND_OPINION_ERROR) or '')
    return attempts, successes, service_failures, len(apps), sample


_OUTAGE_WINDOWS = {'vision': _vision_ocr_window, 'gemini': _gemini_read_window}


def _outage_stats(service, until, window_hours, *, min_failures=1, min_apps=1):
    attempts, successes, failures, apps, sample = _OUTAGE_WINDOWS[service](
        until - timedelta(hours=window_hours), until)
    return {'service': service, 'window_hours': window_hours, 'attempts': attempts,
            'successes': successes, 'service_failures': failures, 'failed_applications': apps,
            'sample_error': sample,
            'is_down': (attempts >= 1 and successes == 0
                        and failures >= max(min_failures, 1) and apps >= min_apps)}


def gemini_reads_down(window_hours=2, now=None):
    """True while recent Gemini document reads are ALL failing on our side — the hourly sweep asks
    this before spending a Vision OCR call per document on a re-read that cannot succeed yet."""
    return _outage_stats('gemini', now or timezone.now(), window_hours)['is_down']


def detect_vision_outage(window_hours=24):
    """Passive Google-Vision health signal from recent IC / parent_ic OCR outcomes.

    Returns ``(is_down, stats)``. ``is_down`` is True when there were OCR attempts
    in the window and EVERY one carried a service-level error with NOT ONE success
    — i.e. the OCR *service* (not a single blurry image) has been failing for
    everyone who tried. A poor image ('empty image' / read-nothing) is NOT counted
    as a service failure, so a run of bad uploads alone never trips the alert.

    Read-only; no Vision API calls (so the check itself costs nothing). Pair with a
    daily scheduled run so the admin is alerted once a day while an outage persists.
    """
    stats = _outage_stats('vision', timezone.now(), window_hours)
    return stats['is_down'], stats


def detect_service_outages(window_hours=24, *, start_edge=False, now=None):
    """Every read service DOWN over the last ``window_hours`` — Vision OCR (the rule above) and,
    since 2026-10-24, Gemini document reads — as a list of stats dicts, one per service.

    ``start_edge`` makes it safe to run HOURLY without mailing every hour, and needs no stored
    state: a service is reported only when it is down now AND was NOT down for the same-length
    window ending at the previous hourly run (``HOURLY_STEP`` ago, jitter-tolerant) — i.e. what
    that run would have seen. (Comparing against the ADJACENT window instead would report the same
    outage on two consecutive runs.) A single quiet hour cannot re-arm it inside a window of two
    hours or more: "no attempts" counts as not down only once the WHOLE window is quiet. It also
    needs ``HOURLY_MIN_FAILURES`` failures across ``HOURLY_MIN_APPLICATIONS`` applications, so
    one document cannot page anybody. Without it, this is the daily rule: down → report, every run."""
    now = now or timezone.now()
    edge = ({'min_failures': HOURLY_MIN_FAILURES, 'min_apps': HOURLY_MIN_APPLICATIONS}
            if start_edge else {})
    out = []
    for service in _OUTAGE_WINDOWS:
        stats = _outage_stats(service, now, window_hours, **edge)
        if stats['is_down'] and not (
                start_edge and _outage_stats(service, now - HOURLY_STEP, window_hours, **edge)['is_down']):
            out.append({**stats, 'mode': 'start' if start_edge else 'daily'})
    return out
