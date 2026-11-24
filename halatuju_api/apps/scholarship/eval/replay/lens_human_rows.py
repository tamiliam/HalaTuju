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
(the QC, the award, a reopen), so today's row may not show it. The rule, which never guesses a stage:
* today's fingerprint equals the stored one: the stage facts are the same as at the decision; it is used.
* else, today's row is hashed again with each other status (`ScholarshipApplication.STATUS_CHOICES`) that
  gives other stage facts. If one of those equals the stored fingerprint, the evidence is the same but
  the stage moved, and the decision's stage cannot be rebuilt from today's row: None (could not
  recompute). If none does, today's fingerprint is used (the evidence or the Submit year moved).
* only a FULL stored context (text ``fingerprint`` and ``key_check``) whose key check is the current one is
  recomputed. Without a stored fingerprint, or under another key, the stage cannot be checked: None.

THE KEY (F3). `verdict_context` uses ``VERDICT_FINGERPRINT_DERIVED_KEY`` only when it is text of exactly 64
hex characters; blank or absent, it falls back to ``SECRET_KEY``. So the key counts as blank unless the
setting is exactly that form AND `verdict_context.key_check()` answers. A blank key recomputes nothing.

READ ONLY. One SELECT for the cases (with their profile and intake), then per DECIDED case only the reads
the two public functions make. No save, no write, no file, no log line, no clock read of its own: per case
both calls run inside `clock.pinned_clock(verdict_decided_at)`. An undecided case gets no engine work.
The caller (phase C) runs it inside `guards.read_only_session` and `netguard.refuse_network`, after
`clock.preload()`.
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


def _other_stage_twins(app, status_codes):
    """Copies of ``app`` in memory, one per status whose stage facts differ from today's and from each
    other's. Nothing is saved: only the copy's ``status`` attribute is set."""
    from apps.scholarship import verdict_context

    def facts(status):
        stand_in = types.SimpleNamespace(profile_completed_at=app.profile_completed_at, status=status)
        return tuple(sorted(verdict_context.stage_facts(stand_in).items()))

    seen = {facts(app.status)}
    for status in status_codes:
        key = facts(status)
        if key in seen:
            continue
        seen.add(key)
        twin = copy.copy(app)
        twin.status = status
        yield twin


def _lens_fingerprint(app, current_key_check, status_codes):
    """The recomputed fingerprint (see THE STAGE in the module docstring), or None."""
    from apps.scholarship import verdict_context
    stored = app.ai_verdict_context
    if current_key_check is None or not _full_context(stored) or stored['key_check'] != current_key_check:
        return None
    try:
        today = verdict_context.build_verdict_context(app)['fingerprint']
    except _FINGERPRINT_ERRORS:
        return None
    if today == stored['fingerprint']:
        return today
    for twin in _other_stage_twins(app, status_codes):
        try:
            other = verdict_context.build_verdict_context(twin)['fingerprint']
        except _FINGERPRINT_ERRORS:
            return None
        if other == stored['fingerprint']:
            return None   # same evidence, another stage: the decision's stage is not today's
    return today


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
           'qc_answers': second_look.stored(verdict), 'fresh_snapshot': None, 'engine_version': version}
    if when is None:
        return row
    with clock.pinned_clock(when):
        row['recomputed_fingerprint'] = _lens_fingerprint(app, current_key_check, status_codes)
        row['fresh_snapshot'] = _lens_snapshot(app, build_verdict)
    return row


def human_lens_rows(*, current_key_check) -> list:
    """One case row per application (EVERY one, decided or not, drafts included), by id. With
    ``current_key_check`` None (a blank key) no fingerprint is recomputed. The rows stay in memory: the
    caller hands them to the lens and keeps them nowhere."""
    from apps.scholarship.models import ScholarshipApplication
    from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION, build_verdict
    status_codes = [code for code, _label in ScholarshipApplication.STATUS_CHOICES]
    cases = list(ScholarshipApplication.objects.select_related('profile', 'cohort').order_by('pk'))
    return [_lens_row(app, current_key_check, VERDICT_ENGINE_VERSION, build_verdict, status_codes)
            for app in cases]


def run_human_lens_on_database(exam_folder, now, freeze=False) -> dict:
    """Read the key facts and every case, then return `lens_human.run_human_lens`'s output unchanged
    (counts, codes and labels only). ``now`` (an aware datetime) and ``exam_folder`` (an absolute path
    outside every repository) are handed in; only ``freeze=True`` may write a missing exam file."""
    key_is_blank, current_key_check = human_lens_key_facts()
    rows = human_lens_rows(current_key_check=current_key_check)
    return lens_human.run_human_lens(rows, exam_folder=exam_folder, key_is_blank=key_is_blank,
                                     current_key_check=current_key_check, now=now, freeze=freeze)
