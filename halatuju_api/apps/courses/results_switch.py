"""The STPM / higher → SPM switch (pre-U sprint, owner decision B, 2026-11-26).

`ProfileUpdateSerializer._never_demote_held_results` keeps a profile on the tertiary results it
holds, whatever a write claims — a stale browser must never demote a student. That guard stays for
EVERY write. The one door through it is a write that carries ALL of:

* ``clear_held_results: true`` — sent only by the onboarding sync after the student said "Yes,
  continue with SPM" on /onboarding/exam-type AND then saved their SPM grades (the sign-in door
  never sends it, `resultsSync.signInResultsFields`);
* ``results_exam_type: 'spm'`` and non-empty SPM ``grades`` in the same payload.

Then the held STPM / Matriculation / Asasi / Diploma results are cleared IN THE ATTRS (so they win
over a stale browser copy riding in the same sync), before the serializer's bookkeeping, and the
guard reads the switch as a profile that no longer holds tertiary results. A flag with no SPM
grades beside it clears nothing. Leaving midway sends nothing, so nothing changes.

⚠ A STUDENT WITH AN APPLICATION THAT RESTS ON THE HELD RESULTS IS REFUSED (400
``held_results_locked``): every application except a rejected, withdrawn or expired one — a CLOSED
one may have been awarded on them (review round 1). The verdict, the officer's case page and the
documents were all built on the held results, and they must never change silently.
`held_results_locked` is served on GET /profile/ so the dialog says so instead of offering the
switch; this module is the rule, the web only reads it.

⚠ THE CLEARED RESULTS STAY CLEARED (review round 1, `ignore_stale_held_resend`). After the switch
the profile holds SPM only, but another device — or this one, when the sync's answer was lost —
still has the old STPM / third-route copies and its next sync sends them again. On an SPM-only
profile those fields are DROPPED unless the same write records that exam as completed
(``results_exam_type`` = 'stpm', or the third-route kind): a genuine move back still saves.
"""
from rest_framework import serializers

from .exam_questions import THIRD_ROUTE

#: Statuses after which an application no longer rests on the profile's results. NOT 'closed':
#: a closed case may have been awarded (review round 1). A rejected one may still switch.
_ENDED = frozenset({'withdrawn', 'expired', 'rejected'})

#: What the switch clears — every results field the guard protects a tertiary holder by, the
#: STPM co-curriculum ask's marker, and the pre-U institution they completed (a fact about
#: results they no longer hold on file). `spm_prereq_grades` and `muet_band` stay: both are
#: valid for an SPM student.
CLEARED = {
    'stpm_grades': {}, 'stpm_cgpa': None, 'stpm_koko': None, 'stpm_koko_unconfirmed': None,
    'higher_cgpa': None, 'higher_koko': None, 'higher_institution_type': '',
    'completed_qualifications': ['spm'], 'exam_type': 'spm', 'pre_u_studied_at': '',
}

_STPM_FIELDS = ('stpm_grades', 'stpm_cgpa', 'stpm_koko', 'stpm_koko_confirmed')
_HIGHER_FIELDS = ('higher_cgpa', 'higher_koko', 'higher_institution_type')


def held_results_locked(profile):
    """True when the student has an application that still rests on their held results."""
    if profile is None or getattr(profile, 'pk', None) is None:
        return False
    return profile.scholarship_applications.exclude(status__in=_ENDED).exists()


def apply_spm_switch(instance, attrs):
    """Honour ``clear_held_results`` (always popped: never a column) — see the module note.
    Returns True when the clear was applied to ``attrs``."""
    confirmed = attrs.pop('clear_held_results', False)
    if not confirmed or instance is None or getattr(instance, 'pk', None) is None:
        return False
    if (attrs.get('results_exam_type') or '').strip().lower() != 'spm' or not attrs.get('grades'):
        return False
    if held_results_locked(instance):
        raise serializers.ValidationError(
            {'clear_held_results': [serializers.ErrorDetail(
                'Your application uses the results you hold; contact us to change them.',
                code='held_results_locked')]})
    attrs.update({k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
                  for k, v in CLEARED.items()})
    return True


def keep_stored_on_blank(instance, attrs, switched):
    """A blank school never wipes a stored one (the /profile page and the sign-in sync both send
    `school` whatever it holds); a first school, or a change to another non-blank one, passes.
    Pre-U sprint: the same for `pre_u_studied_at` (as the apply write-back has), except the switch
    to SPM's own clear of it (``switched``)."""
    for field in ('school', 'pre_u_studied_at'):
        if field == 'pre_u_studied_at' and switched:
            continue
        if field in attrs and not (attrs[field] or '').strip() \
                and (getattr(instance, field, '') or '').strip():
            attrs.pop(field)


def _holds_spm_only(instance):
    """The state the switch leaves: completed SPM only, and no STPM / third-route results on file."""
    if instance is None or getattr(instance, 'pk', None) is None:
        return False
    if list(getattr(instance, 'completed_qualifications', None) or []) != ['spm']:
        return False
    return (not (getattr(instance, 'stpm_grades', None) or {})
            and getattr(instance, 'stpm_cgpa', None) is None
            and getattr(instance, 'higher_cgpa', None) is None)


def ignore_stale_held_resend(instance, attrs):
    """On an SPM-only profile, drop incoming STPM / third-route results unless this write records
    that exam as completed (see the module note). The SPM fields, `spm_prereq_grades` and
    `muet_band` are never touched."""
    if not _holds_spm_only(instance):
        return
    recorded = (attrs.get('results_exam_type') or '').strip().lower()
    if recorded != 'stpm':
        for f in _STPM_FIELDS:
            attrs.pop(f, None)
    if recorded not in THIRD_ROUTE:
        for f in _HIGHER_FIELDS:
            attrs.pop(f, None)
