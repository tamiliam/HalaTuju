"""When each funded student's semester result is DUE, and whether she is late (student maintenance S4b).

THE TERM MODEL (decisions.md, 2026-10-29, S4b) — deliberately simple, every number the organisation's:

  * The FIRST time the schedule sees her, her term is placed by counting ``12 / results_terms_per_year``
    months from the day she was FUNDED (``funded_since``: the earliest of ``active_at`` and
    ``vircle_activated_at``, else ``awarded_at``) — and it is the term she is IN, never one that ended
    before (NO BACK-DATED DEBT).
  * After that every term CHAINS from the last row: it starts on the last row's ``term_ends_on`` and
    runs the length the setting says AT THE MOMENT THE ROW IS MADE (review H1, 2026-10-29). Each row
    stores ``term_starts_on`` / ``term_ends_on`` / ``due_on``, so a later change to the settings — or to
    a funding stamp — can never move, overlap or back-date a term already made.
  * A term's result is due ``results_due_days_after_term`` days after it ends, and she is "not
    submitted" once ``results_overdue_grace_days`` more have passed — unless a result of hers, sent on
    or after that term began, is waiting for the officer (the officer's queue is not her lateness).
  * An ACCEPTED result submitted on or after a term's stored start meets the oldest open term
    (``reconcile``); a second accepted result for a semester already counted does not use up a term.
  * NO MORE TERMS once a graduating result is accepted or her file is ``ready_to_close``; a CLOSED file
    is never late (``next_due`` / ``late`` read nothing for a student out of maintenance).

Writers: ``ensure_expectations`` / ``reconcile`` / ``unlink`` here, and the daily jobs' stamps. The
doors fence (``test_results_review.TestTheDoorsAreTheListedOnes``) names each function.
"""
import calendar
import logging
import re
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from .maintenance_scope import is_in_maintenance
from .models import ResultsExpectation

log = logging.getLogger(__name__)


def settings_for(organisation):
    """(terms_per_year, due_days_after_term, overdue_grace_days) for an organisation."""
    from apps.courses import org_config
    return (org_config.value(organisation, 'results_terms_per_year'),
            org_config.value(organisation, 'results_due_days_after_term'),
            org_config.value(organisation, 'results_overdue_grace_days'))


def funded_since(application):
    """The day her funded terms are first counted from, or None (never funded)."""
    stamps = [s for s in (application.active_at, application.vircle_activated_at) if s]
    start = min(stamps) if stamps else application.awarded_at
    return timezone.localdate(start) if start else None


def _add_months(day, months):
    month = day.month - 1 + months
    year, month = day.year + month // 12, month % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def term_end(start, k, terms_per_year):
    """The day term k (1-based) ends, counted from `start` — used ONLY to place her first term."""
    return _add_months(start, k * (12 // terms_per_year))


def finished(application):
    """No more terms: a graduating result has been accepted, or her file is ready to close."""
    from .results_review import accepted
    return (application.maintenance_substate == 'ready_to_close'
            or accepted(application.semester_results.filter(graduated=True)).exists())


def ensure_expectations(application, today=None):
    """Make the row for every term that has BEGUN and has none yet (module docstring), then pair
    accepted results with open terms. Idempotent; returns how many rows it made."""
    if not is_in_maintenance(application) or finished(application):
        return 0
    today = today or timezone.localdate()
    terms, due_days, _grace = settings_for(application.owning_organisation)
    last = ResultsExpectation.objects.filter(application=application).order_by('-term_index').first()
    if last is None:                      # first sight: the term she is in, never earlier ones
        start = funded_since(application)
        if start is None:
            return 0
        k = 1
        while term_end(start, k, terms) < today:
            k += 1
        begins = term_end(start, k - 1, terms) if k > 1 else start
    else:                                 # chain: the next term starts where the last one ended
        k, begins = last.term_index + 1, last.term_ends_on
    made = 0
    while begins <= today:
        ends = _add_months(begins, 12 // terms)
        _row, created = ResultsExpectation.objects.get_or_create(
            application=application, term_index=k,
            defaults={'term_starts_on': begins, 'term_ends_on': ends,
                      'due_on': ends + timedelta(days=due_days)})
        made += int(created)
        k, begins = k + 1, ends
    reconcile(application)
    return made


def _semester_key(text):
    """A semester label as a comparison key: case, spacing and punctuation folded ("Sem 1" = "sem-1")."""
    return re.sub(r'[^a-z0-9]+', '', (text or '').lower())


def reconcile(application):
    """Pair each ACCEPTED result not yet counted against a term with the oldest open term it could
    belong to (submitted on or after that term's STORED start). A result whose semester is one
    already counted does not use up a new term (review M5). Stamps both sides."""
    from .results_review import accepted
    open_terms = list(ResultsExpectation.objects.filter(application=application, satisfied_by__isnull=True)
                      .order_by('term_index'))
    if not open_terms:
        return 0
    counted = {_semester_key(s) for s in accepted(application.semester_results.filter(term_index__isnull=False))
               .values_list('semester', flat=True)}
    results = []
    for r in accepted(application.semester_results.filter(term_index__isnull=True)).order_by('created_at', 'id'):
        key = _semester_key(r.semester)
        if key and key in counted:
            continue                                  # the same semester, sent again
        if key:
            counted.add(key)
        results.append(r)
    paired = 0
    with transaction.atomic():
        for exp in open_terms:
            match = next((r for r in results if timezone.localdate(r.created_at) >= exp.term_starts_on), None)
            if match is None:
                continue
            results.remove(match)
            exp.satisfied_by = match
            exp.save(update_fields=['satisfied_by'])
            match.term_index = exp.term_index
            match.save(update_fields=['term_index'])
            paired += 1
    return paired


def unlink(result):
    """A result that is no longer accepted stops counting: its term reopens."""
    result.refresh_from_db(fields=['term_index'])      # `reconcile` stamped another instance
    if result.term_index is None:
        return
    with transaction.atomic():
        ResultsExpectation.objects.filter(satisfied_by=result).update(satisfied_by=None)
        result.term_index = None
        result.save(update_fields=['term_index'])


def oldest_open(application):
    """Her earliest OPEN term (may already be past due), or None — always None out of maintenance
    (a closed file is never late) and once she has finished."""
    if not is_in_maintenance(application):
        return None
    return (ResultsExpectation.objects.filter(application=application, satisfied_by__isnull=True)
            .order_by('due_on', 'id').first())


def next_due(application):
    row = oldest_open(application)
    return row.due_on if row else None


def is_overdue(due_on, grace_days, today=None):
    """Past the due date AND the grace — "not submitted". Strictly after."""
    if due_on is None:
        return False
    return (today or timezone.localdate()) > due_on + timedelta(days=grace_days)


def pending_since(application, day):
    """A result of hers is waiting for review that she sent on or after `day` (review M3)."""
    from .results_review import PENDING
    return application.semester_results.filter(review_status=PENDING, created_at__date__gte=day).exists()


def late(application, today=None):
    """THE "not submitted" rule (standing, both jobs, the hub): her oldest open term is past its due
    date and the grace, she has not finished, and nothing she sent since that term began is waiting."""
    row = oldest_open(application)
    if row is None or finished(application):
        return False
    _terms, _due, grace = settings_for(application.owning_organisation)
    return is_overdue(row.due_on, grace, today) and not pending_since(application, row.term_starts_on)


def not_submitted(application, today=None):
    return late(application, today)


def _live_applications():
    from .maintenance_scope import in_maintenance_q
    from .models import ScholarshipApplication
    return (ScholarshipApplication.objects.filter(in_maintenance_q())
            .exclude(maintenance_substate='ready_to_close')
            .select_related('profile', 'cohort__owning_organisation', 'owning_organisation__configuration'))


def _may_email(application):
    """Due and overdue emails: the switch on, and not while she is on hold (review L9 — the owner's
    to reverse; her rows and standing still update)."""
    from . import student_comms
    from .maintenance import is_on_hold
    return student_comms.enabled() and not is_on_hold(application)


def send_due_reminders(today=None, now=None):
    """The "your result is due by …" reminder: from `results_reminder_lead_days` before the due
    date until the due date, at most once every `results_reminder_every_days`, ONE per student per
    run (her oldest open term), never while something she sent this term waits for review. The row
    is CLAIMED first (compare-and-set on `reminded_at`) and given back if the send fails. Returns
    how many were sent."""
    from apps.courses import org_config
    from . import student_comms
    if not student_comms.enabled():
        return 0
    now = now or timezone.now()
    today = today or timezone.localdate(now)
    sent = 0
    for app in _live_applications():
        try:
            if not _may_email(app) or finished(app):
                continue
            exp = oldest_open(app)
            if exp is None or exp.due_on < today:
                continue
            org = app.owning_organisation
            if today < exp.due_on - timedelta(days=org_config.value(org, 'results_reminder_lead_days')):
                continue
            every = org_config.value(org, 'results_reminder_every_days')
            if exp.reminded_at and timezone.localdate(exp.reminded_at) > today - timedelta(days=every):
                continue
            if pending_since(app, exp.term_starts_on):
                continue
            if ResultsExpectation.objects.filter(pk=exp.pk, reminded_at=exp.reminded_at).update(
                    reminded_at=now) != 1:
                continue                                      # another run claimed it
            if student_comms.send_student_email(app, 'results_due', due_date=exp.due_on):
                sent += 1
            else:                                             # give the claim back: try again tomorrow
                ResultsExpectation.objects.filter(pk=exp.pk, reminded_at=now).update(reminded_at=exp.reminded_at)
        except Exception:  # noqa: BLE001 — one student's failure must not stop the run
            log.exception('results-due reminder failed for application %s', app.id)
    return sent


def flag_overdue(today=None, now=None):
    """Each student who is late (``late``): ONE `results_overdue` line on her file the first time a
    term goes late (all her late rows stamped `overdue_flagged_at`), and ONE email naming the oldest
    due date — sent when the switch is on and she is not on hold, retried on the next run until it
    goes (`overdue_emailed_at`, kept apart from the flag, review L8). The flag and the line are
    written whatever the switch says; only the email waits for it. Returns how many were flagged."""
    from . import activity, student_comms
    from .models.activity import EVENT_RESULTS_OVERDUE
    now = now or timezone.now()
    today = today or timezone.localdate(now)
    flagged = 0
    for app in _live_applications():
        try:
            if not late(app, today):
                continue
            _terms, _due, grace = settings_for(app.owning_organisation)
            rows = [r for r in ResultsExpectation.objects.filter(application=app, satisfied_by__isnull=True)
                    .order_by('due_on', 'id') if is_overdue(r.due_on, grace, today)]
            fresh = [r.pk for r in rows if r.overdue_flagged_at is None]
            if fresh:
                with transaction.atomic():
                    if ResultsExpectation.objects.filter(pk__in=fresh, overdue_flagged_at__isnull=True).update(
                            overdue_flagged_at=now):
                        activity.log_event(app, EVENT_RESULTS_OVERDUE, meta={
                            'term_index': rows[0].term_index, 'due_on': rows[0].due_on.isoformat(),
                            'terms_late': len(rows)})
                        flagged += 1
            unsent = [r.pk for r in rows if r.overdue_emailed_at is None]
            if unsent and _may_email(app) and student_comms.send_student_email(
                    app, 'results_overdue', due_date=rows[0].due_on):
                ResultsExpectation.objects.filter(pk__in=unsent).update(overdue_emailed_at=now)
        except Exception:  # noqa: BLE001 — one student's failure must not stop the run
            log.exception('results-overdue flag failed for application %s', app.id)
    return flagged


def ensure_all(today=None):
    """The daily jobs' first step: every in-maintenance student's terms, made and reconciled.
    Returns how many term rows were made."""
    made = 0
    for app in _live_applications():
        try:
            made += ensure_expectations(app, today)
        except Exception:  # noqa: BLE001
            log.exception('results terms failed for application %s', app.id)
    return made
