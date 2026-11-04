"""The work PENDING for one person — the stat cards on top of the merged Organisation Overview
(T5c P5b S1, owner rulings 2026-11-05, `docs/decisions.md`).

`pending_for(admin, b40_scope=...)` -> `[{'key', 'count', optional 'due_soon', optional 'oldest_days'}]`.

A CARD THE CALLER MAY NOT SEE IS ABSENT, never sent as zero (owner). The cards follow the person's
roles as a UNION, like `my_programmes`; every count is read through the service that already owns
that rule, so the card and the page it opens can never disagree:

  Admins table (`staff_tables.in_admins`) with an Applications scope of 'all':
      `unassigned`, `overdue` (+ `due_soon`), `awaiting_qc`        <- `programme_overview.attention`
  `surface_gates.may_read_sponsors`:  `sponsors_to_vet`             <- `pending_sponsor_count`
  the `org_read` door (`may_read_org`): `invitations`               <- `invitations.waiting_counts`
  `payments_chain.may_read`:          `payment_runs` waiting for THIS person's step <- `next_step_for`
  the credit CHECKER seat:            `wallet_credits` waiting for THEIR signature  <- `credit_steps`
  Requests live + `requests_role`:    `requests`                    <- `org_requests_queue.needs_action_q`
  Reviewers table holding `review`:   `my_open`, `my_due_soon`, `my_overdue`        <- `programme_overview.mine`
  Reviewers table holding `qc`:       `qc_awaiting` (+ `oldest_days`) <- `qc_queue`, minus the cases
                                      `qc_separation` bars them from (`barred_ids`)
  mentoring now (`mentor_desk.mentor_of`): `mentees`, `not_met` (no meeting at all — the owner ruled
                                      there is no "not met recently" threshold), `asked_help`

THE FENCE: a super reads the pooled platform (`spend_report.ALL_ORGS`, as on the Overview); everybody
else their own organisation; a non-super with no organisation gets no application, review or QC card
(the Overview answers them `no_org`). Payment runs, credits, invitations and requests are fenced on
their own organisation column below. Sponsors are platform accounts (the nav badge's own rule).
"""
from django.utils import timezone

from apps.courses import staff_tables

from . import credit_steps, mentor_desk, mentoring_read, payments_chain, surface_gates


def pending_sponsor_count():
    """Sponsor accounts awaiting vetting — cross-organisation by design (a sponsor is a platform
    account). The ONE home of the rule: the nav badge (`AdminSponsorPendingCountView`) reads it too."""
    from .models import Sponsor
    return Sponsor.objects.filter(status='pending').count()


def _org(admin):
    from . import spend_report
    return spend_report.ALL_ORGS if admin.is_super else admin.owning_organisation


def _application_cards(cards, scope, now, clocks):
    from .programme_overview import attention
    a = attention(scope, now=now, clocks=clocks)
    cards['unassigned'] = {'count': a['unassigned']}
    cards['overdue'] = {'count': a['overdue'], 'due_soon': a['due_soon']}
    cards['awaiting_qc'] = {'count': a['awaiting_qc']}


def _review_cards(cards, scope, admin, now, clocks, org):
    from . import spend_report
    from .programme_overview import mine
    m = mine(scope, admin, now=now, clocks=clocks,
             organisation_id=None if org is spend_report.ALL_ORGS else getattr(org, 'id', None))
    cards['my_open'] = {'count': m['open']}
    cards['my_due_soon'] = {'count': m['due_soon']}
    cards['my_overdue'] = {'count': m['overdue']}


def _qc_card(cards, scope, admin, now):
    from . import qc_separation
    from .programme_overview import qc_queue
    waiting = scope.filter(status='interviewed')
    q = qc_queue(waiting.exclude(pk__in=qc_separation.barred_ids(admin, waiting)), admin, now=now)
    cards['qc_awaiting'] = {'count': q['awaiting'], 'oldest_days': q['oldest_waiting_days']}


def _invitations(admin):
    from . import invitations, mentor_invite
    from .models import Invitation
    # org-fence: an invitation belongs to the organisation that sent it; a super sees all (the
    # Invitations page's own fence, `AdminInvitationsView.get`).
    qs = Invitation.objects.select_related('partner_admin').all()
    qs = qs if admin.is_super else qs.filter(organisation_id=admin.owning_organisation_id)
    counts = invitations.waiting_counts(qs)
    if not mentor_invite.may_read(admin):       # the page's rule: no Mentor kind outside the roster
        counts[invitations.KIND_MENTOR] = 0
    return sum(counts.values())


def _payment_runs(admin):
    from .models import PaymentRun
    # org-fence: the Payments list's own fence — a super is global, everybody else their organisation.
    runs = PaymentRun.objects.filter(status__in=payments_chain._IN_FLIGHT)
    runs = runs if admin.is_super else runs.filter(organisation_id=admin.owning_organisation_id)
    cache = {}                                  # one holders() read per organisation, as on the list
    return sum(1 for r in runs if payments_chain.next_step_for(r, admin, cache) is not None)


def _wallet_credits(admin):
    from .models import Donation
    # org-fence: the Credits page's own fence (`_credit_qs`, on the gift's organisation).
    credits = Donation.objects.filter(status__in=credit_steps.SIGNING).select_related('programme__organisation')
    credits = credits if admin.is_super else credits.filter(
        programme__organisation_id=admin.owning_organisation_id)
    return credit_steps.waiting_for(admin, credits)


def _requests(admin):
    from . import org_requests_queue as queue
    from .models import OrgRequest
    if admin.is_super:
        # org-fence: super is global by design for the triage badge (`AdminOrgRequestCountView`).
        return OrgRequest.objects.filter(queue.needs_action_q(True)).count()
    # org-fence: own org only (org_admin), as on the badge.
    qs = OrgRequest.objects.filter(organisation_id=admin.owning_organisation_id)
    return qs.filter(queue.needs_action_q(False)).count()


def _mentor_cards(cards, admin):
    rows = mentor_desk.current_assignments(admin)
    counts, _last = mentor_desk._meeting_counts([a.pk for a in rows])
    cards['mentees'] = {'count': len(rows)}
    cards['not_met'] = {'count': sum(1 for a in rows if not counts.get(a.pk))}
    cards['asked_help'] = {'count': sum(1 for a in rows if any(mentoring_read.help_asked(a.application).values()))}


def pending_for(admin, *, b40_scope, now=None):
    """The caller's pending cards (see the module docstring). `b40_scope` is `_AdminBase._b40_scope`."""
    from .programme_overview import application_scope
    from .review_sla import clocks as review_clocks
    from . import spend_report
    now = now or timezone.now()
    cards = {}
    org = _org(admin)
    reviews = staff_tables.in_reviewers(admin)
    if org is not None:
        scope = application_scope(org)
        clocks = review_clocks(None if org is spend_report.ALL_ORGS else org)
        if staff_tables.in_admins(admin) and b40_scope == 'all':
            _application_cards(cards, scope, now, clocks)
        if reviews and admin.has_perm('review'):
            _review_cards(cards, scope, admin, now, clocks, org)
        if reviews and admin.has_perm('qc'):
            _qc_card(cards, scope, admin, now)
    if surface_gates.may_read_sponsors(admin):
        cards['sponsors_to_vet'] = {'count': pending_sponsor_count()}
    if staff_tables.may_read_org(admin):
        cards['invitations'] = {'count': _invitations(admin)}
    if payments_chain.may_read(admin):
        cards['payment_runs'] = {'count': _payment_runs(admin)}
    if credit_steps.checks_credits(admin):
        cards['wallet_credits'] = {'count': _wallet_credits(admin)}
    if surface_gates.requests_live() and surface_gates.requests_role(admin):
        cards['requests'] = {'count': _requests(admin)}
    if mentor_desk.mentor_of(admin) is not None:
        _mentor_cards(cards, admin)
    return [{'key': key, **card} for key, card in cards.items()]
