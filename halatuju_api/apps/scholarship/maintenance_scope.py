"""Who is "in maintenance" — the ONE predicate (student maintenance Sprint 1, 2026-10-29).

WHY. Owner ruling 2026-10-29 (decisions.md, top entry): a funded student has ONE file from award
acceptance to closure. Every in-programme gate used to accept only ``active`` / ``maintenance``,
but the real cohort (65 BrightPath students on 2026-10-29) is paid every month while still at
``awarded`` with a Vircle wallet live — so none of them could record a semester result, be put on
hold, or reach the in-programme page. The gates now all ask THIS module instead of carrying their
own status list.

WHAT COUNTS as in maintenance:
  * ``awarded`` with ``vircle_activated_at`` set — the award is accepted and the wallet is live,
    i.e. the student is being paid by the payment runs; OR
  * ``active`` / ``maintenance`` (``closure.FUNDED_STATUSES``) — funded by nature.
An ``awarded`` student WITHOUT a live wallet is not yet in maintenance (no money moves for her).

WHO HAS A FILE (``has_file``) — the in-maintenance students, plus a CLOSED student who was in it,
for READ-ONLY access (the closed notice, the thank-you relay):
  * closed with ``active_at`` stamped (funded; the TD-352 rule, and ``closure.ever_awarded_q``'s
    closed half), OR
  * closed with ``vircle_activated_at`` set AND a POST-award-only closure reason
    (graduated / completed / lapsed / terminated).
⚠ ``vircle_activated_at`` ALONE on a closed record is NOT a safe signal, and is deliberately not
used: ``award_revert.revert_to_pool`` sends a fallen-through award back to ``recommended`` (or
``interviewed``) WITHOUT clearing the wallet stamp, and such a case may later be closed as
``stalled`` from a pre-award status — exactly the TD-352 case that must NOT count. A pre-award
close may only record ``stalled`` / ``withdrawn`` (``closure.PRE_AWARD_REASONS``), so a reason
outside that set proves the close came from awarded / active / maintenance. A post-award close
recorded as ``stalled`` / ``withdrawn`` with no ``active_at`` therefore fails CLOSED (no file) —
the cautious side; ``closure.close_application`` is the only writer of ``status='closed'``.

THE STATUS STATE MACHINE IS UNCHANGED. Nothing here moves a status; ``awarded`` stays
``awarded``. This is a read over fields the product already writes.

``in_maintenance_q`` / ``has_file_q`` are the queryset forms; ``is_in_maintenance`` /
``has_file`` the single-record mirrors (``test_maintenance_scope`` proves each pair agrees on
every status x wallet x stamp combination).
"""
from django.db.models import Q

from .closure import FUNDED_STATUSES, POST_AWARD_REASONS, PRE_AWARD_REASONS

#: The status that is in maintenance only with a live wallet.
_AWARDED = 'awarded'
#: Reasons only a close from awarded / active / maintenance may record (see the docstring).
POST_AWARD_ONLY_REASONS = tuple(r for r in POST_AWARD_REASONS if r not in PRE_AWARD_REASONS)


def in_maintenance_q():
    """The queryset form of ``is_in_maintenance``."""
    return (Q(status=_AWARDED, vircle_activated_at__isnull=False)
            | Q(status__in=FUNDED_STATUSES))


def is_in_maintenance(application):
    """True when ``application`` is in the funded maintenance loop (see the module docstring)."""
    if application is None:
        return False
    if application.status in FUNDED_STATUSES:
        return True
    return application.status == _AWARDED and application.vircle_activated_at is not None


def _closed_with_file_q():
    return Q(status='closed') & (
        Q(active_at__isnull=False)
        | Q(vircle_activated_at__isnull=False, closure_reason__in=POST_AWARD_ONLY_REASONS))


def has_file_q():
    """The queryset form of ``has_file``."""
    return in_maintenance_q() | _closed_with_file_q()


def has_file(application):
    """True when the student has a maintenance file: in maintenance now, or closed after being
    in it (read-only). A stalled pre-award close never has one (TD-352)."""
    if is_in_maintenance(application):
        return True
    if application is None or application.status != 'closed':
        return False
    if application.active_at is not None:
        return True
    return (application.vircle_activated_at is not None
            and application.closure_reason in POST_AWARD_ONLY_REASONS)
