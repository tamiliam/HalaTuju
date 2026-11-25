"""LL5 phase B2b - the human lens's DATABASE half: it reads every application through the ORM, READ ONLY,
builds the case rows `lens_human.run_human_lens` takes (`lens_human.CASE_FIELDS`), and calls the lens.

WHAT IT CALLS, and why (F1). The live decision (`views_admin/verdict.AdminRecordVerdictView.post`) stamps
``ai_verdict_snapshot = verdict_engine.build_verdict(app)``, ``ai_verdict_engine_version =
verdict_engine.VERDICT_ENGINE_VERSION`` and ``ai_verdict_context = verdict_context.verdict_context_or_empty(app)``
(which is `verdict_context.build_verdict_context`). This module calls the SAME public functions on the
row as the ORM gives it today: `build_verdict_context` for the fingerprint, `build_verdict` for the fresh
snapshot. Nothing is re-implemented. The document rows the fingerprint reads come only through a private
helper, so `evidence_fingerprint` is not called directly.

THE STAGE (F2). The fingerprint hashes the stage facts (`verdict_context.stage_facts`: the Submit year and
three status buckets), and the stage at the decision is not stored. The status moves after a decision
(the QC, the award, a reopen), so today's row may not show it. The rule (narrow B), which never guesses a
stage; ``recompute_note`` (`lens_human.RECOMPUTE_REASONS`) says why a FULL case has no fingerprint:
* only a FULL stored context (text ``fingerprint`` and ``key_check``) whose key check is the current one is
  recomputed; under another key (or none): None, ``key_not_current``. A caught error: ``recompute_error``.
* today's fingerprint equals the stored one: used (matched directly), the snapshot built on today's row.
  But PAST THE AWARD today (review round 1, B1: `at_past_award_stage`, a split the stage facts do not
  cover, where the live door never stamps): None, ``past_award_stage``, no snapshot.
* else each TWIN (`_other_stage_twins`: an in-memory copy per other stage-facts group, never past the
  award) is hashed. A match means the same evidence under another stage. Valid (note ``twin``) only when
  every matching twin is IN REVIEW (`verdict_context.stage_facts`'s own ``in_review_status``, asked per
  copy) and their snapshots, built on the COPIES, are byte-identical: the fingerprint is the stored one
  and the snapshot is the twin's. A lone match in the decided group: ``decided_group_twin``; any other
  match set: ``twin_not_unique``. In review is safe: there every stage-linked input the engine reads is
  hashed in the stage facts or pinned (the clock), and no status there is past the award. A decided-group
  twin is never recovered (release-lead rule).
* no twin matches: today's fingerprint (the evidence or the Submit year moved; not valid), with no
  snapshot past the award (B1) and today's snapshot otherwise.
The exam-old cases (no stored fingerprint) are NOT refused: their snapshot is built under today's stage,
past-award split included; that is their written known limit.

THE KEY (F3). `verdict_context` uses ``VERDICT_FINGERPRINT_DERIVED_KEY`` only when it is text of exactly 64
hex characters; blank or absent, it falls back to ``SECRET_KEY``. So the key counts as blank unless the
setting is exactly that form AND `verdict_context.key_check()` answers. A blank key recomputes nothing.

READ ONLY. One SELECT for the cases (with their profile and intake), then per DECIDED case only the reads
the two public functions make. No save, no write, no file, no log line, no clock read of its own: per case
both calls run inside `clock.pinned_clock(verdict_decided_at)`. `time.time` is left unpinned: on this path
only `income_declaration`'s approval-window checks read it, and what they feed into the verdict
(`approval_counts`) is the same either side of the window (a test holds it). An undecided case gets no
engine work.
The caller (phase C) runs it inside `guards.read_only_session` and `netguard.refuse_network`, after
`clock.preload()`.

SAFETY (LL5 phase C1b).
* DEBUG: with Django ``DEBUG`` on, Django keeps and logs each SQL statement, case ids included. So
  `run_human_lens_on_database` refuses the whole run with `lens_human.DEBUG_ON` before any query or file.
* AN OPEN DOCUMENT SNAPSHOT: a twin is a copy with the same model and id, so a `document_snapshot` open for
  the case would serve the twin the case's photographed rows. `human_lens_rows` asks
  `document_snapshot.is_open_for` for every case before any engine work or twin, and raises
  `OpenSnapshotError` (no case data in it). It is a RuntimeError, so no catch here turns it into a note.
* PROFILES: a twin shares the real case's profile object. Nothing here writes to a profile, on a twin or
  not; only the twin's ``status`` attribute is set (a test holds the profile's values and the SQL).
"""
from __future__ import annotations

import copy
import json
import string
import types

from . import clock, lens_human

# A bad stored value the fingerprint cannot hash: no canonical form (TypeError) or NaN (ValueError).
_FINGERPRINT_ERRORS = (TypeError, ValueError)
# What the verdict engine raises on a stored value of an odd shape (it catches these itself in places).
# AttributeError is NOT caught: it is also what a renamed field gives, a programming error.
_SNAPSHOT_ERRORS = (TypeError, ValueError, KeyError)
_DERIVED_KEY_LENGTH = 64
_HEX_DIGITS = frozenset(string.hexdigits)


class OpenSnapshotError(RuntimeError):
    """The rows were asked for while a document snapshot is open for a case. Its twins would read that
    case's photographed document rows, so the whole run stops. The message holds no case data."""

    def __init__(self):
        super().__init__('human lens rows: a document snapshot is open for a case; '
                         'run the lens outside every document snapshot')


def human_lens_key_facts() -> tuple:
    """``(key_is_blank, current_key_check)``. Not blank only when the setting is text of exactly 64 hex
    characters (the one form `verdict_context` uses instead of ``SECRET_KEY``) and `key_check()` answers;
    then ``current_key_check`` is `verdict_context.key_check()`. Else ``(True, None)``. The setting is
    looked at only to check its form; it is never stored, returned or logged."""
    from django.conf import settings
    from django.core.exceptions import ImproperlyConfigured

    from apps.scholarship import verdict_context
    given = getattr(settings, 'VERDICT_FINGERPRINT_DERIVED_KEY', None)
    well_formed = (isinstance(given, str) and len(given) == _DERIVED_KEY_LENGTH
                   and set(given) <= _HEX_DIGITS)
    if not well_formed:
        return True, None
    try:
        check = verdict_context.key_check()
    except ImproperlyConfigured:
        return True, None
    return False, check


def _full_context(context) -> bool:
    """The stored context carries a fingerprint and a key check, both text (the lens's FULL shape)."""
    return (isinstance(context, dict) and isinstance(context.get('fingerprint'), str)
            and isinstance(context.get('key_check'), str))


def at_past_award_stage(status, active_at) -> bool:
    """The past-award split as `income_declaration` reads it for a document's case: the status is in
    `closure.POST_AWARD_STATUSES`, or it is closed with ``active_at`` set (`closure.ever_awarded_q`).
    A drift test holds it to the engine's own private rule."""
    from apps.scholarship import closure
    return status in closure.POST_AWARD_STATUSES or (status == 'closed' and active_at is not None)


def _recomputable(app, current_key_check) -> bool:
    """A FULL stored context under the current key check: the only case whose fingerprint is recomputed."""
    stored = app.ai_verdict_context
    return current_key_check is not None and _full_context(stored) and stored['key_check'] == current_key_check


def _other_stage_twins(app, status_codes):
    """Copies of ``app`` in memory, one per status whose stage facts differ from today's and from each
    other's, never a past-award status. Nothing is saved: only the copy's ``status`` attribute is set."""
    from apps.scholarship import verdict_context

    def facts(status):
        stand_in = types.SimpleNamespace(profile_completed_at=app.profile_completed_at, status=status)
        return tuple(sorted(verdict_context.stage_facts(stand_in).items()))

    seen = {facts(app.status)}
    for status in status_codes:
        key = facts(status)
        if key in seen or at_past_award_stage(status, app.active_at):
            continue
        seen.add(key)
        twin = copy.copy(app)
        twin.status = status
        yield twin


def _fingerprint(app):
    from apps.scholarship import verdict_context
    return verdict_context.build_verdict_context(app)['fingerprint']


def _in_review(twin) -> bool:
    """The stage facts' own in-review bucket for this copy (public `verdict_context.stage_facts`)."""
    from apps.scholarship import verdict_context
    return verdict_context.stage_facts(twin)['in_review_status'] is True


def _by_twin(app, stored_fingerprint, status_codes, build_verdict):
    """``(fingerprint, note, snapshot)`` from the twins once today's fingerprint differs from the stored
    one, or None when no twin matches (see THE STAGE). Snapshots are built on the copies only."""
    matches = [twin for twin in _other_stage_twins(app, status_codes) if _fingerprint(twin) == stored_fingerprint]
    if not matches:
        return None
    if not all(_in_review(twin) for twin in matches):
        return None, 'decided_group_twin' if len(matches) == 1 else 'twin_not_unique', None
    snapshots = [_lens_snapshot(twin, build_verdict) for twin in matches]
    if len({json.dumps(snapshot, sort_keys=True) for snapshot in snapshots}) > 1:
        return None, 'twin_not_unique', None
    return stored_fingerprint, lens_human.RECOVERED_BY_TWIN, snapshots[0]


def _recompute(app, current_key_check, status_codes, build_verdict):
    """``(recomputed_fingerprint, recompute_note, fresh_snapshot)`` for a decided case (THE STAGE)."""
    stored = app.ai_verdict_context
    if not _full_context(stored):
        return None, None, _lens_snapshot(app, build_verdict)
    if not _recomputable(app, current_key_check):
        return None, 'key_not_current', _lens_snapshot(app, build_verdict)
    past_award = at_past_award_stage(app.status, app.active_at)
    note = None
    try:
        today = _fingerprint(app)
        if today == stored['fingerprint']:
            return (None, 'past_award_stage', None) if past_award else (today, None, _lens_snapshot(app, build_verdict))
        by_twin = _by_twin(app, stored['fingerprint'], status_codes, build_verdict)
    except _FINGERPRINT_ERRORS:
        today, by_twin, note = None, None, 'recompute_error'
    if by_twin is not None:
        return by_twin
    # evidence changed, or a caught error: today's snapshot as before, none past the award (B1)
    return today, note, None if past_award else _lens_snapshot(app, build_verdict)


def _lens_snapshot(app, build_verdict):
    """`build_verdict(app)` as the live save stores it (a JSON round trip, as the column gives it back),
    or None when the engine cannot read this case's stored data or the result has no stored form (a
    value JSON cannot hold, or NaN, which the jsonb column refuses)."""
    try:
        return json.loads(json.dumps(build_verdict(app), allow_nan=False))
    except _SNAPSHOT_ERRORS:
        return None


def _lens_row(app, current_key_check, version, build_verdict, status_codes) -> dict:
    from apps.scholarship import second_look
    verdict = app.officer_verdict
    when = app.verdict_decided_at
    row = {'application_id': app.pk, 'verdict_decided_at': when,
           'stored_context': app.ai_verdict_context, 'recomputed_fingerprint': None,
           'human_verdict': verdict if isinstance(verdict, dict) else None,
           'qc_answers': second_look.stored(verdict), 'fresh_snapshot': None, 'engine_version': version,
           'recompute_note': None}
    if when is None:
        return row
    with clock.pinned_clock(when):
        recomputed = _recompute(app, current_key_check, status_codes, build_verdict)
    row['recomputed_fingerprint'], row['recompute_note'], row['fresh_snapshot'] = recomputed
    return row


def human_lens_rows(*, current_key_check) -> list:
    """One case row per application (EVERY one, decided or not, drafts included), by id. With
    ``current_key_check`` None (a blank key) no fingerprint is recomputed. The rows stay in memory: the
    caller hands them to the lens and keeps them nowhere. Raises `OpenSnapshotError` before any engine
    work or twin when a document snapshot is open for any case."""
    from apps.scholarship import document_snapshot
    from apps.scholarship.models import ScholarshipApplication
    from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION, build_verdict
    status_codes = [code for code, _label in ScholarshipApplication.STATUS_CHOICES]
    cases = list(ScholarshipApplication.objects.select_related('profile', 'cohort').order_by('pk'))
    if any(document_snapshot.is_open_for(app) for app in cases):
        raise OpenSnapshotError()
    return [_lens_row(app, current_key_check, VERDICT_ENGINE_VERSION, build_verdict, status_codes)
            for app in cases]


def _debug_refusal() -> dict:
    """The lens output's top-level keys with nothing read (no count, no engine version), and each exam
    refused with `lens_human.DEBUG_ON` the way the lens refuses an exam (``refusal`` and ``status``)."""
    status = f'refused: {lens_human.DEBUG_ON}'
    return {'engine_version': None, 'cases_read': None, 'not_decided': None, 'no_human_verdict': None,
            'context_failed': None, 'context_failed_line': None,
            'exams': {name: {'exam': name, 'refusal': lens_human.DEBUG_ON, 'status': status}
                      for name in lens_human.EXAM_NAMES}}


def run_human_lens_on_database(exam_folder, now, freeze=False) -> dict:
    """Read the key facts and every case, then return `lens_human.run_human_lens`'s output unchanged
    (counts, codes and labels only). ``now`` (an aware datetime) and ``exam_folder`` (an absolute path
    outside every repository) are handed in; only ``freeze=True`` may write a missing exam file.
    With Django ``DEBUG`` on: `_debug_refusal`, before any query and any file, in both modes."""
    from django.conf import settings
    if settings.DEBUG:
        return _debug_refusal()
    key_is_blank, current_key_check = human_lens_key_facts()
    rows = human_lens_rows(current_key_check=current_key_check)
    return lens_human.run_human_lens(rows, exam_folder=exam_folder, key_is_blank=key_is_blank,
                                     current_key_check=current_key_check, now=now, freeze=freeze)
