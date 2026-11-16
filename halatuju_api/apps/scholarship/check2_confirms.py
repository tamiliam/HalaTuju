"""Check 2 - the two one-tap STUDENT confirms that mirror a state Check 2 does not compute itself:
the pathway queries (mirrored from the live verdict) and the household-size confirm.

Moved verbatim out of ``check2_queries.py`` (H3b, 2026-11-16, moves only) to keep that module under
the 600-line standard. ``check2_queries`` re-exports every name here, so each import and patch on
the old path still works, and ``sync_check2_queries`` still calls them by their old names.
"""
from django.db import IntegrityError

from .models import ResolutionItem


# The pathway STUDENT queries mirrored from the verdict — all student-visible (source='check2', NOT
# in resolution.RESOLUTION_SPECS, so they never become a hidden 'system' item): 'pathway_confirm'
# (one-tap "is this where you're going?") + 'pathway_undeclared' (an ambiguous offer we can't pin —
# the student picks their exact course on the profile page) + 'pathway_type_switch' (TD-161: the
# offer is a different pathway TYPE than declared — confirm the switch; Yes → confirm_pathway adopts
# the type). code → kind. Owner 2026-07-15 / 2026-07-18.
_PATHWAY_QUERY_KINDS = {'pathway_confirm': 'confirm', 'pathway_undeclared': 'explanation',
                        'pathway_type_switch': 'confirm'}


def _sync_pathway_confirm(application, existing, now):
    """Reconcile the Check-2 pathway student queries (``pathway_confirm`` + ``pathway_undeclared``)
    from the live verdict. Routed through Check 2 (``source='check2'``) so the flag governs
    visibility + the email; the student answers in place (Yes → ``confirm_pathway`` writes their final
    pathway for the confirm; picking a course on the profile page clears the undeclared one). The
    verdict engine detects the state; here we only mirror it into the student queue + auto-resolve
    each once the verdict no longer raises it. The verdict raises AT MOST ONE of the two at a time."""
    from .models import ApplicantDocument
    raised = False
    # Both queries require an offer letter — skip the verdict compute (and its cost) otherwise; a
    # lingering item after the offer is gone is closed below.
    verdict_params = {code: None for code in _PATHWAY_QUERY_KINDS}
    if ApplicantDocument.objects.filter(
            application=application, doc_type='offer_letter', superseded_at__isnull=True).exists():
        from .verdict_engine import build_verdict
        for fact in build_verdict(application):
            if fact['fact'] != 'pathway':
                continue
            for it in fact['unresolved']:
                if it['code'] in verdict_params:
                    verdict_params[it['code']] = it.get('params', {})
    for code, kind in _PATHWAY_QUERY_KINDS.items():
        params, item = verdict_params[code], existing.get(code)
        if params is not None and item is None:
            try:
                ResolutionItem.objects.create(
                    application=application, source='check2', code=code,
                    fact='pathway', kind=kind, params=params)
                raised = True   # a new student-visible query appeared → caller re-notifies
            except IntegrityError:
                pass  # created concurrently — fine
        elif params is None and item is not None and item.status == 'open':
            # No longer raised (confirmed / course picked / offer replaced) → close the question.
            item.status = 'resolved'
            item.resolved_by = 'system'
            item.resolved_at = now
            item.save(update_fields=['status', 'resolved_by', 'resolved_at'])
    return raised


def _sync_household_size_confirm(application, existing, now):
    """Reconcile the ``household_size_confirm`` STUDENT query (a one-tap 'confirm', like
    ``pathway_confirm``). Raised when the itemised roster OUTNUMBERS the stated household size
    (``household_size_shortfall`` — the per-capita denominator may be too small, so income looks
    overstated): we ask the student "you listed N people but entered a size of M — is N right?".

    Non-mutating: a student 'Yes' resolves the query (``resolved_by='student'``) and the cockpit then
    shows the roster count with a tick + "Declared: M" (per the household_check ``confirmed`` flag);
    we NEVER rewrite the stated size. Because confirming does not change the size, the over-count
    persists — so once the student has confirmed we must NOT re-ask (guard on the student-resolved
    item). If the over-count later disappears (the student edited their size/roster), an unanswered
    query auto-closes."""
    from .income_engine import household_size_shortfall
    hs = household_size_shortfall(application)
    item = existing.get('household_size_confirm')
    # Already answered by the student → settled; never re-ask (the over-count still exists by design).
    if item is not None and getattr(item, 'resolved_by', '') == 'student':
        return False
    if hs and item is None:
        try:
            ResolutionItem.objects.create(
                application=application, source='check2', code='household_size_confirm',
                fact='income', kind='confirm',
                params={'described': hs['described'], 'size': hs['size']})
            return True
        except IntegrityError:
            pass  # created concurrently — fine
    elif not hs and item is not None and item.status == 'open':
        item.status = 'resolved'
        item.resolved_by = 'system'
        item.resolved_at = now
        item.save(update_fields=['status', 'resolved_by', 'resolved_at'])
    return False
