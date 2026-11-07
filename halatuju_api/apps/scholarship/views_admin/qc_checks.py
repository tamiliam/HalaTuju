"""The QC accept's cheap checks, kept out of `verdict.py` for its 600-line limit (A1.5 fix round 3).

Moved verbatim from `views_admin/verdict.py`, which imports them back; nothing else uses them.
"""
from rest_framework import status
from rest_framework.response import Response

from .. import birth_state
from ..models import SponsorProfile


def _overall(app):
    """The reviewer's recorded overall verdict ('accept', 'decline', ...), or None."""
    return (app.officer_verdict if isinstance(app.officer_verdict, dict) else {}).get('overall')


def _accept_absolute_stop(app):
    """The QC ACCEPT-to-recommend refusals that NO override passes, or None. (Extracted from
    `AdminQcDecisionView.post` when the second one joined; the decline-confirm path never reaches
    here.)

    1. Reporting-date stop (owner 2026-07-23): a case cannot be accepted without a settled
       reporting date. Deliberately an ABSOLUTE stop, unlike the red-fact floor — there is no
       override, because the honest remedy is to record the date, not to wave the case through.
       Three things silently default off a missing date: the bursary SIZE (a continuing student is
       committed RM3,000 instead of RM1,000), payment eligibility, and the semester-result request.
       QC clears it by reopening the case so the reviewer can enter the date
       (AdminReportingDateView) — hence the box shows at 'interviewing' / on a reopen, not here.
    2. TD-465 review: an APPROVE verdict must carry its bursary (`award_required`, no override).
       Four routes fill the date without re-recording the verdict (an offer re-read, a cancelled
       reopen, verify-accept and the reporting-date box), so a case whose verdict sized nothing
       (an unknown STPM start year) could reach `recommended` with no amount. Re-recording the
       verdict sizes it from the known date; that is the remedy, not an override.
    3. TD-376/377 review: on a ruled intake the IC must be LOCKED to reach `recommended`
       (`birth_state.ic_unlocked_for_rule`). No override can make an unlocked IC safe, and QC
       accept never re-locks it silently: verify-accept re-locks it and runs the duplicate check.
    4. A2.1 review: the final profile is still being written (`profile_pending`, no override).
       QC-Accept publishes the sponsor text, so QC must read the final one; the remedy is to wait
       for the `finalise-profiles` cron (a few minutes) and reload. A FAILED one refuses too
       (`profile_failed`, A2.1 re-review): accepting would publish the old text a reopen called
       wrong, or move an empty profile to `recommended` with nothing published. The remedy is to
       run finalise again from the case.
    """
    if app.reporting_date is None:
        return Response(
            {'error': 'This student has no reporting date. Reopen the case so the reviewer can '
                      'record it and record the verdict again (which sets the proposed bursary), '
                      'then accept.',
             'code': 'reporting_date_required'},
            status=status.HTTP_400_BAD_REQUEST)
    if _overall(app) == 'accept' and app.award_amount is None:
        return Response(
            {'error': 'The proposed bursary is missing. Reopen the case so the reviewer can '
                      'record the verdict again (that sets the bursary), then accept.',
             'code': 'award_required'},
            status=status.HTTP_400_BAD_REQUEST)
    if birth_state.ic_unlocked_for_rule(app.profile,
                                        getattr(app.cohort, 'allowed_birth_states', None)):
        return Response({'error': birth_state.IC_UNLOCKED_MESSAGE,
                         'code': birth_state.IC_UNLOCKED},
                        status=status.HTTP_400_BAD_REQUEST)
    finalise_state = (SponsorProfile.objects.filter(application=app)
                      .values_list('finalise_state', flat=True).first())
    if finalise_state == 'pending':
        return Response(
            {'error': 'The final sponsor profile is still being written. Wait a few minutes, '
                      'reload the page and read it, then accept.',
             'code': 'profile_pending'},
            status=status.HTTP_400_BAD_REQUEST)
    if finalise_state == 'failed':
        return Response(
            {'error': 'The final sponsor profile could not be written. Run finalise again from '
                      'the case, wait a few minutes, reload the page and read it, then accept.',
             'code': 'profile_failed'},
            status=status.HTTP_400_BAD_REQUEST)
    return None


def _not_awaiting_qc():
    """The same 400 as `_require_qc`, for a case that left QC after the view read it (A1.5)."""
    return Response({'error': 'This case is not awaiting QC.', 'code': 'not_awaiting_qc'},
                    status=status.HTTP_400_BAD_REQUEST)
