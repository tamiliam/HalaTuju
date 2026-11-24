"""LL5 phase C2 - the coach grade's DATABASE door: it reads every DECIDED case through the ORM, READ ONLY,
builds the records `coach_grade.coach_report` takes, and returns its report (counts, percents, version
labels, month labels and fixed codes only).

THE RECORD, the same four fields F4's live score card reads (`prediction_metrics.metrics` hands the same
values to `ai_score.score_marks`), in `coach_grade`'s order: ``ai_verdict_snapshot`` (each fact's band is
re-derived from it by `ai_score` with today's `fact_bands` rules), ``officer_verdict`` as stored (the
reviewer's Pass / Fail per fact, the Fail reasons under `fail_reasons.KEY`, and the QC's second-look
answers under `second_look.KEY` where they exist), ``ai_verdict_engine_version`` (through
`stored_version_label`) and ``verdict_decided_at``. Who decided and the row id are never selected (a
four-field record is read like a full one). The QC answers are passed on inside the stored verdict and,
as on F4's card, do not change a mark: `coach_grade`'s mirror claim is F4's score. A case with no
``verdict_decided_at`` (a reject before interview) is never selected, and `coach_grade` drops one anyway.

THE VERSION LABEL is database text. It is passed on only when it is exactly
`verdict_engine.PRE_VERSIONING` or has the engine version shape (`lens_result_schema.engine_version_ok`),
after str's own strip; any other stored label is passed as None, so `coach_grade` files it under its
unknown-version label. The stored text is never printed, written or returned.

READ ONLY. One SELECT of four columns, no save, no update, no delete, no raw SQL, no file, no log line.
The records stay in memory. The caller (`child.write_coach_grade`) runs it inside
`guards.read_only_session` and `netguard.refuse_network`.

DEBUG: with Django ``DEBUG`` on, Django keeps and logs each SQL statement. `coach_grade_on_database` then
refuses with `coach_debug_refusal` (``{"refusal": "debug_on"}``) before any query.
"""
from __future__ import annotations

from . import lens_human
from .lens_result_schema import engine_version_ok

#: The columns read, in `coach_grade`'s record order. Nothing else is selected.
RECORD_FIELDS = ('ai_verdict_snapshot', 'officer_verdict', 'ai_verdict_engine_version', 'verdict_decided_at')


def coach_debug_refusal() -> dict:
    """The whole run refused under DEBUG: one fixed code, nothing read."""
    return {'refusal': lens_human.DEBUG_ON}


def stored_version_label(raw):
    """``raw`` (the stored engine version) when, after str's own strip, it is `PRE_VERSIONING` or has the
    engine version shape; else None (the unknown version). Only a value whose real type is text counts."""
    from apps.scholarship.verdict_engine import PRE_VERSIONING
    if not issubclass(type(raw), str):
        return None
    label = str.strip(raw)
    if label == PRE_VERSIONING or engine_version_ok(label):
        return str(label)
    return None


def coach_records() -> list:
    """``[(snapshot, verdict, version label or None, decided at)]``, one per decided case (one SELECT)."""
    from apps.scholarship.models import ScholarshipApplication
    rows = (ScholarshipApplication.objects.filter(verdict_decided_at__isnull=False)
            .order_by().values_list(*RECORD_FIELDS))
    return [(snapshot, verdict, stored_version_label(version), when) for snapshot, verdict, version, when in rows]


def coach_grade_on_database() -> dict:
    """`coach_grade.coach_report` over every decided case, with the extra line that leaves out the
    interview Fails (`coach_grade.INTERVIEW_FAILS`). Under Django ``DEBUG``: `coach_debug_refusal`,
    before any query."""
    from django.conf import settings
    if settings.DEBUG:
        return coach_debug_refusal()
    from apps.scholarship import coach_grade
    return coach_grade.coach_report(coach_records(), leave_out_reasons=coach_grade.INTERVIEW_FAILS)
