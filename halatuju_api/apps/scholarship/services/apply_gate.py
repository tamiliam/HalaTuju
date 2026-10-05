"""May this student start an application here? — ONE home for the answer (TD-337).

The owner's rulings (tamiliam, 2026-10-05; decisions.md):
  1. "If a student is currently active in a programme -- i.e. awarded, and hasn't been closed --
     the student may not apply for another programme under the same organisation."
  2. "No. One application in process, or one award, for each organisation."

What is BUILT, for the submit and for every apply-page visit, in this order:
  0. IN PLAY ANYWHERE → refused (``application_in_progress``). She holds an application, in ANY
     organisation, whose student-facing status is not FINISHED. The blocking application is that
     one (the newest, should legacy data hold several).
  1. SAME ROUND → refused (``already_applied``). She already holds a non-expired application in
     this very round (needs a resolved open round) — the old per-round rule: a declined student
     cannot re-apply to the round that declined her.
  2. Otherwise allowed — a FINISHED application never blocks another programme or a later round.

⚠ DELIBERATELY STRICTER THAN THE RULING ACROSS ORGANISATIONS (lead decision, 2026-10-05, after the
adversarial review). The ruling is per organisation, so an application in play in organisation B
would not, by itself, stop an application to A. It does here, because the student side cannot yet
carry two LIVE applications: `_current_application` refuses 13 student endpoints with 409
`application_ambiguous`, the application page shows a linkless "several" card, onboarding and the
banner pick by position, and the embargo masking differs between them. Carrying two is roadmap
M2–M4 (not built, not approved). While only one organisation runs rounds this changes nothing; it
must be RELAXED TOGETHER WITH M2, never before. The organisation is therefore not read here at all.

⚠ THE EMBARGO MUST NOT LEAK. "In play" is judged on the STUDENT-FACING status
(``student_status.student_facing_status``), not the raw one. A decline whose email is still
embargoed reads to her as the stage she was declined from; were the gate to read the raw
'rejected', the form would suddenly let her in and tell her the outcome before the email does.

⚠ THE ANSWER DOES NOT DEPEND ON WHETHER A CODE EXISTS. A student in play is answered
``application_in_progress`` on ANY visit — known code, unknown code, closed gift, bare, nothing
open — and a student with nothing in play is answered ``allowed`` on an unknown or a closed code
alike. So the apply gate cannot be used to tell which codes exist or whose they are.

The submit (``ApplicationListCreateView.post`` → ``apply_verdict``, always with a round) and the apply
page's question (``views_apply_gate.ApplyGateView`` → ``verdict_for_visit``, with or without an open
round) read this module; the web keeps no copy of the rule.
"""
from dataclasses import dataclass

from ..models import ScholarshipApplication
from ..student_status import student_facing_status

ALLOWED = ''
IN_PROGRESS = 'application_in_progress'
ALREADY_APPLIED = 'already_applied'

#: The sentence a refused submit carries beside its ``code`` (the 409 body keeps its old shape).
REFUSAL = {
    IN_PROGRESS: 'You already have an application in progress.',
    ALREADY_APPLIED: 'You have already applied to this round.',
}

#: Student-facing statuses after which an application no longer holds her place. Every other
#: status is IN PLAY. `test_apply_gate.py` asserts the two sets partition
#: `ScholarshipApplication.STATUS_CHOICES` exactly, so a new status cannot slip through unclassified.
FINISHED_STATUSES = frozenset({'rejected', 'withdrawn', 'closed', 'expired'})
IN_PLAY_STATUSES = frozenset({
    'submitted', 'shortlisted', 'profile_complete', 'interviewing', 'interviewed',
    'recommended', 'awarded', 'active', 'maintenance',
})

#: The fields the rule reads — nothing else is loaded.
_FIELDS = ('id', 'cohort_id', 'status', 'pending_rejection_category', 'pre_decline_status',
           'submitted_at')


@dataclass(frozen=True)
class ApplyVerdict:
    """``reason`` is '' (allowed), ``IN_PROGRESS`` or ``ALREADY_APPLIED``; ``application`` is the
    student's own application that blocks, or None."""
    reason: str = ALLOWED
    application: object = None

    @property
    def allowed(self):
        return not self.reason


def _hers(**by):
    return list(ScholarshipApplication.objects.filter(**by)
                .only(*_FIELDS).order_by('-submitted_at', '-id'))


def her_applications(profile):
    """The student's applications, newest first, with only the fields the rule reads. None (no
    profile) has none — never ``filter(profile=None)``, which would match orphaned rows."""
    return [] if profile is None else _hers(profile=profile)


def _in_play(apps):
    """Her newest application still IN PLAY (student-facing status), or None."""
    return next((a for a in apps if student_facing_status(a) not in FINISHED_STATUSES), None)


def in_play_application(user_id):
    """The caller's CURRENT application — the one in play, by the student-facing status — or None.
    For a student-side read that must answer about it rather than an older, finished one."""
    return _in_play(_hers(profile_id=user_id)) if user_id else None


def verdict_in(apps, cohort):
    """The verdict for ``cohort`` over an already-loaded list of her applications. Pure."""
    live = _in_play(apps)
    if live is not None:
        return ApplyVerdict(IN_PROGRESS, live)
    same = next((a for a in apps if a.cohort_id == cohort.id and a.status != 'expired'), None)
    return ApplyVerdict(ALREADY_APPLIED, same) if same is not None else ApplyVerdict()


def apply_verdict(profile, cohort):
    """May ``profile`` start an application to ``cohort``?"""
    return verdict_in(her_applications(profile), cohort)


def _over_rounds(apps, cohorts):
    """In play → refused for every round by definition; else refused only if she has already
    applied to EVERY open round (the chooser asks, and the page asks again with the pick)."""
    verdicts = [verdict_in(apps, c) for c in cohorts]
    if not verdicts or any(v.allowed for v in verdicts):
        return ApplyVerdict()
    return verdicts[0]


def verdict_over_rounds(profile, cohorts):
    """For a page that has not yet named one of several open rounds."""
    return _over_rounds(her_applications(profile), cohorts)


def verdict_for_visit(profile, programme_code=''):
    """The apply PAGE's question — `GET /scholarship/apply-gate/` — which, unlike the submit, may
    name no open round at all (closed is the normal state for most of the year).

      * In play anywhere → ``IN_PROGRESS`` on EVERY visit, before the code is even looked at — a
        known, unknown or closed code, a bare visit, nothing open. An applicant on her closed gift's
        link is sent to her application, and the answer says nothing about the code.
      * Otherwise: the code's open round (or, bare, the one open round) → ``ALREADY_APPLIED`` if she
        holds a non-expired application in it; several open → refused only if already applied to
        every one; no open round, or an unknown code → allowed (the intake answers "closed").
    """
    from .errors import AmbiguousOpenCohort
    from .intake import resolve_open_cohort
    from ..models import ScholarshipCohort
    apps = her_applications(profile)
    live = _in_play(apps)
    if live is not None:
        return ApplyVerdict(IN_PROGRESS, live)
    try:
        cohort = resolve_open_cohort(programme_code=(programme_code or '').strip())
    except AmbiguousOpenCohort as exc:
        return _over_rounds(apps, ScholarshipCohort.objects.filter(code__in=exc.codes))
    return verdict_in(apps, cohort) if cohort is not None else ApplyVerdict()
