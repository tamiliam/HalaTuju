"""When each funded student's semester result is DUE, and whether she is late (student maintenance S4b).

THE TERM MODEL (decisions.md, 2026-10-29, S4b) — deliberately simple, every number the organisation's:

  * Her terms run from the day she was FUNDED (``funded_since``: the earliest of ``active_at`` and
    ``vircle_activated_at``, else ``awarded_at``), ``12 / results_terms_per_year`` months each
    (2 a year → six-month terms). Term k ends k term-lengths after that day.
  * A term's result is due ``results_due_days_after_term`` days after the term ends (45 by default),
    and is "not submitted" once ``results_overdue_grace_days`` more have passed (14).
  * NO BACK-DATED DEBT: the first time the schedule sees her, it starts with the term she is IN —
    never with the terms that ended before the feature existed. After that it adds each term as it
    begins, so a later run catches up any term a quiet period skipped.
  * An ACCEPTED result submitted during a term (on or after its start) satisfies the oldest open
    term (``reconcile``), and the result is stamped with that ``term_index``. Un-accepting it (a
    re-review to queried) reopens the term.

We do not read the institution's calendar: there is no reliable source of it, and an officer knows
the student. The settings are the organisation's lever; ``due_on`` is stored per term so a change
moves future terms only.

Writers: ``ensure_expectations`` / ``reconcile`` / ``unlink`` here, and the daily jobs' stamps. The
doors fence (``test_results_review.TestTheDoorsAreTheListedOnes``) names each function.
"""
import calendar
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from .maintenance_scope import is_in_maintenance
from .models import ResultsExpectation


def settings_for(organisation):
    """(terms_per_year, due_days_after_term, overdue_grace_days) for an organisation."""
    from apps.courses import org_config
    return (org_config.value(organisation, 'results_terms_per_year'),
            org_config.value(organisation, 'results_due_days_after_term'),
            org_config.value(organisation, 'results_overdue_grace_days'))


def funded_since(application):
    """The day her funded terms start counting from, or None (never funded)."""
    stamps = [s for s in (application.active_at, application.vircle_activated_at) if s]
    start = min(stamps) if stamps else application.awarded_at
    return timezone.localdate(start) if start else None


def _add_months(day, months):
    month = day.month - 1 + months
    year, month = day.year + month // 12, month % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def term_end(start, k, terms_per_year):
    """The day term k (1-based) ends, counted from `start`."""
    return _add_months(start, k * (12 // terms_per_year))


def term_start(start, k, terms_per_year):
    return term_end(start, k - 1, terms_per_year) if k > 1 else start


def ensure_expectations(application, today=None):
    """Make the rows for every term that has BEGUN and has no row yet (see the module docstring),
    then pair accepted results with open terms. Idempotent; returns how many rows it made."""
    if not is_in_maintenance(application):
        return 0
    start = funded_since(application)
    if start is None:
        return 0
    today = today or timezone.localdate()
    terms, due_days, _grace = settings_for(application.owning_organisation)
    last = (ResultsExpectation.objects.filter(application=application)
            .order_by('-term_index').values_list('term_index', flat=True).first())
    if last is None:                      # first sight: the term she is in, never earlier ones
        k = 1
        while term_end(start, k, terms) < today:
            k += 1
    else:
        k = last + 1
    made = 0
    while term_start(start, k, terms) <= today:
        ends = term_end(start, k, terms)
        _row, created = ResultsExpectation.objects.get_or_create(
            application=application, term_index=k,
            defaults={'term_ends_on': ends, 'due_on': ends + timedelta(days=due_days)})
        made += int(created)
        k += 1
    reconcile(application)
    return made


def reconcile(application):
    """Pair each ACCEPTED result not yet counted against a term with the oldest open term it could
    belong to (submitted on or after that term's start). Stamps both sides."""
    from .results_review import accepted
    open_terms = list(ResultsExpectation.objects.filter(application=application, satisfied_by__isnull=True)
                      .order_by('term_index'))
    if not open_terms:
        return 0
    start = funded_since(application)
    terms, _due, _grace = settings_for(application.owning_organisation)
    results = list(accepted(application.semester_results.filter(term_index__isnull=True))
                   .order_by('created_at', 'id'))
    paired = 0
    with transaction.atomic():
        for exp in open_terms:
            begins = term_start(start, exp.term_index, terms) if start else None
            match = next((r for r in results if begins is None
                          or timezone.localdate(r.created_at) >= begins), None)
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


def next_due(application):
    """Her earliest OPEN term's due date (may already be past), or None."""
    return (ResultsExpectation.objects.filter(application=application, satisfied_by__isnull=True)
            .order_by('due_on').values_list('due_on', flat=True).first())


def is_overdue(due_on, grace_days, today=None):
    """Past the due date AND the grace — "not submitted". Strictly after."""
    if due_on is None:
        return False
    return (today or timezone.localdate()) > due_on + timedelta(days=grace_days)


def not_submitted(application, today=None):
    """True when an open term is past its due date and the organisation's grace."""
    _terms, _due, grace = settings_for(application.owning_organisation)
    return is_overdue(next_due(application), grace, today)


def _open_terms(today):
    """Open terms of students still in maintenance, with what a send needs, oldest due first."""
    from .maintenance_scope import in_maintenance_q
    from .models import ScholarshipApplication
    live = ScholarshipApplication.objects.filter(in_maintenance_q()).values('id')
    return (ResultsExpectation.objects.filter(satisfied_by__isnull=True, application_id__in=live)
            .select_related('application__profile', 'application__cohort__owning_organisation',
                            'application__owning_organisation__configuration')
            .order_by('due_on', 'id'))


def send_due_reminders(today=None, now=None):
    """The "your result is due by …" reminder: from `results_reminder_lead_days` before the due
    date until the due date, at most once every `results_reminder_every_days`, and never while a
    result of hers is waiting for review. Stamps `reminded_at` ONLY when the email went out, so a
    switched-off or failed send is tried again next run. Returns how many were sent."""
    from apps.courses import org_config
    from . import student_comms
    from .results_review import has_pending
    if not student_comms.enabled():
        return 0
    now = now or timezone.now()
    today = today or timezone.localdate(now)
    sent = 0
    for exp in _open_terms(today).filter(due_on__gte=today):
        app = exp.application
        org = app.owning_organisation
        lead = org_config.value(org, 'results_reminder_lead_days')
        every = org_config.value(org, 'results_reminder_every_days')
        if today < exp.due_on - timedelta(days=lead):
            continue
        if exp.reminded_at and timezone.localdate(exp.reminded_at) > today - timedelta(days=every):
            continue
        if has_pending(app):
            continue
        if student_comms.send_student_email(app, 'results_due', due_date=exp.due_on):
            ResultsExpectation.objects.filter(pk=exp.pk).update(reminded_at=now)
            sent += 1
    return sent


def flag_overdue(today=None, now=None):
    """Once a term is past its due date AND the grace: one `results_overdue` line on her file and
    one email to her. `overdue_flagged_at` is stamped when that happens, so each term is flagged
    once. With the switch OFF nothing is flagged (the standing and the filter read the dates, not
    this stamp), so turning it on later still tells every student who is late. Returns the count."""
    from . import activity, student_comms
    from .models.activity import EVENT_RESULTS_OVERDUE
    from .results_review import has_pending
    if not student_comms.enabled():
        return 0
    now = now or timezone.now()
    today = today or timezone.localdate(now)
    flagged = 0
    for exp in _open_terms(today).filter(overdue_flagged_at__isnull=True, due_on__lt=today):
        app = exp.application
        _terms, _due, grace = settings_for(app.owning_organisation)
        if not is_overdue(exp.due_on, grace, today) or has_pending(app):
            continue
        with transaction.atomic():
            if ResultsExpectation.objects.filter(pk=exp.pk, overdue_flagged_at__isnull=True).update(
                    overdue_flagged_at=now) != 1:
                continue                                # another run got there first
            activity.log_event(app, EVENT_RESULTS_OVERDUE, meta={
                'term_index': exp.term_index, 'due_on': exp.due_on.isoformat()})
        student_comms.send_student_email(app, 'results_overdue', due_date=exp.due_on)
        flagged += 1
    return flagged


def ensure_all(today=None):
    """The daily jobs' first step: every in-maintenance student's terms, made and reconciled.
    Returns how many term rows were made."""
    from .maintenance_scope import in_maintenance_q
    from .models import ScholarshipApplication
    made = 0
    for app in (ScholarshipApplication.objects.filter(in_maintenance_q())
                .select_related('owning_organisation__configuration')):
        made += ensure_expectations(app, today)
    return made
