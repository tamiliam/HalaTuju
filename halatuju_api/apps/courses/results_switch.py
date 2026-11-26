"""The STPM / higher → SPM switch (pre-U sprint, owner decision B, 2026-11-26).

`ProfileUpdateSerializer._never_demote_held_results` keeps a profile on the tertiary results it
holds, whatever a write claims — a stale browser must never demote a student. That guard stays for
EVERY write. The one door through it is a write that carries ALL of:

* ``clear_held_results: true`` — sent only by the onboarding sync after the student said "Yes,
  continue with SPM" on /onboarding/exam-type AND then saved her SPM grades (the sign-in door
  never sends it, `resultsSync.signInResultsFields`);
* ``results_exam_type: 'spm'`` and non-empty SPM ``grades`` in the same payload.

Then the held STPM / Matriculation / Asasi / Diploma results are cleared IN THE ATTRS (so they win
over a stale browser copy riding in the same sync), before the serializer's bookkeeping, and the
guard reads the switch as a profile that no longer holds tertiary results. A flag with no SPM
grades beside it clears nothing. Leaving midway sends nothing, so nothing changes.

⚠ A STUDENT WITH AN APPLICATION IN PLAY IS REFUSED (400 ``held_results_locked``): the verdict,
the officer's case page and the documents were all built on the held results, and a submitted
application must never change silently. `held_results_locked` is served on GET /profile/ so the
dialog says so instead of offering the switch; this module is the rule, the web only reads it.
"""
from rest_framework import serializers

#: Statuses after which an application no longer rests on the profile's results.
_ENDED = frozenset({'withdrawn', 'expired', 'rejected', 'closed'})

#: What the switch clears — every results field the guard protects a tertiary holder by, plus
#: the pre-U institution she completed (a fact about results she no longer holds on file).
CLEARED = {
    'stpm_grades': {}, 'stpm_cgpa': None, 'stpm_koko': None,
    'higher_cgpa': None, 'higher_koko': None, 'higher_institution_type': '',
    'completed_qualifications': ['spm'], 'exam_type': 'spm', 'pre_u_studied_at': '',
}


def held_results_locked(profile):
    """True when the student has an application that still rests on her held results."""
    if profile is None or getattr(profile, 'pk', None) is None:
        return False
    return profile.scholarship_applications.exclude(status__in=_ENDED).exists()


def apply_spm_switch(instance, attrs):
    """Honour ``clear_held_results`` (always popped: never a column) — see the module note."""
    confirmed = attrs.pop('clear_held_results', False)
    if not confirmed or instance is None or getattr(instance, 'pk', None) is None:
        return
    if (attrs.get('results_exam_type') or '').strip().lower() != 'spm' or not attrs.get('grades'):
        return
    if held_results_locked(instance):
        raise serializers.ValidationError(
            {'clear_held_results': [serializers.ErrorDetail(
                'Your application uses the results you hold; contact us to change them.',
                code='held_results_locked')]})
    attrs.update({k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
                  for k, v in CLEARED.items()})
