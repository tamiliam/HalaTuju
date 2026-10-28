"""The two Check-2 asks that complete an STPM student's results — STPM CGPA sprint C4 (2026-10-28).

Owner rulings (2026-10-28): after Submit, Check 2 asks the student for what the profile still
needs to be complete and accurate:

* ``stpm_grades_incomplete`` — an applicant holding COMPLETED STPM results (`holds_completed_stpm`)
  whose entered grades are fewer than Pengajian Am + three other subjects, so there is no PNGK to
  work out (`courses.stpm_pngk.pngk_from_grades` -> None, "not calculated"). Asked to add the
  remaining STPM subjects; closes by itself once the grades give a PNGK.
* ``stpm_koko_confirm`` — an applicant whose STPM co-curriculum score the C2 backfill could not
  work back cleanly. The rule cannot be recomputed any more (production's `stpm_cgpa` already holds
  the PNGK), so the marker is the profile's `stpm_koko_unconfirmed`, set by
  `flag_stpm_koko_unconfirmed` for named application ids and cleared when the student saves a
  score through the onboarding STPM step (`courses.serializers.ProfileUpdateSerializer`). Closes by
  itself once the marker is cleared.

Both are ``kind='explanation'`` items with ``source='check2'`` and ``fact='academic'``: the student
answers by OPENING the onboarding STPM results page (the web links each code there — the Action
Centre shows no reply box for them), not by typing. They sit outside the clarify cap like the
one-tap confirms, and follow the sync's stage rule: raised (or re-raised after the system closed
it) only while the machine may ask (`services.auto_queries_allowed`), closed at any stage.
An officer's waiver is never re-opened, and the student cannot close either by typing
(`ResolutionItemResolveView` refuses `CODES` with `answer_on_page`): they close only when the gap does.

`check2_queries.sync_check2_queries` calls `sync` once; everything else lives here (that file sits
at its size allowance).
"""
from django.db import IntegrityError

GRADES_CODE = 'stpm_grades_incomplete'
KOKO_CODE = 'stpm_koko_confirm'
CODES = (GRADES_CODE, KOKO_CODE)


def holds_completed_stpm(profile) -> bool:
    """Does this profile HOLD completed STPM results, not merely STPM grades? The held kind is STPM
    (`exam_questions.results_held`, the test `higher_owed` uses via `results_route.held_kind`) AND
    a completion stands behind it: the STPM form recorded as completed (`results_exam_type` or
    `completed_qualifications`), or — a legacy row from before the form recorded completions — a
    typed STPM CGPA with no grades at all (the old form saved its CGPA only on completion). A Form
    Six student's exploratory course-guide grades carry neither, so she is never asked."""
    from apps.courses.exam_questions import results_held
    if profile is None or results_held(profile) != 'stpm':
        return False
    recorded = (getattr(profile, 'results_exam_type', '') or '').strip().lower() == 'stpm'
    listed = 'stpm' in (getattr(profile, 'completed_qualifications', None) or [])
    legacy = not (getattr(profile, 'stpm_grades', None) or {}) and getattr(profile, 'stpm_cgpa', None) is not None
    return recorded or listed or legacy


def wanted(application) -> set:
    """The codes this application needs asked now (a subset of `CODES`). Only after Submit, and
    only for a profile holding completed STPM results — a switch to SPM or the third route closes
    both."""
    from apps.courses.stpm_pngk import pngk_from_grades
    profile = getattr(application, 'profile', None)
    if application.profile_completed_at is None or not holds_completed_stpm(profile):
        return set()
    out = set()
    if pngk_from_grades(getattr(profile, 'stpm_grades', None)) is None:
        out.add(GRADES_CODE)
    if getattr(profile, 'stpm_koko_unconfirmed', None) is True:
        out.add(KOKO_CODE)
    return out


def sync(application, existing, now, may_ask) -> bool:
    """Reconcile both asks against `wanted`. `existing` is the sync's {code: check2 item}. True
    when a student-visible ask was raised or re-opened (the caller then re-notifies)."""
    from .models import ResolutionItem
    want, raised = wanted(application), False
    for code in CODES:
        item = existing.get(code)
        if code in want:
            if item is None and may_ask:
                try:
                    ResolutionItem.objects.create(application=application, source='check2', code=code,
                                                  fact='academic', kind='explanation', params={})
                    raised = True
                except IntegrityError:
                    pass                      # created concurrently — fine
            elif item is not None and item.status == 'resolved' and item.resolved_by == 'system' and may_ask:
                item.status, item.resolved_by, item.resolved_at = 'open', '', None
                item.save(update_fields=['status', 'resolved_by', 'resolved_at'])
                raised = True                 # the gap came back (grades removed, flag set again)
        elif item is not None and item.status == 'open':
            item.status, item.resolved_by, item.resolved_at = 'resolved', 'system', now
            item.save(update_fields=['status', 'resolved_by', 'resolved_at'])
    return raised
