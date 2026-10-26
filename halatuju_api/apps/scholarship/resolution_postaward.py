"""The two post-award OPERATIONAL tasks of the Action Centre — bank details and the Vircle eWallet.

Moved VERBATIM out of `resolution.py` (third results route S4, 2026-10-27) because that file sat at
the 600-line standard and S4 had to add one rule to it. Every name is re-exported from
`resolution`, so `from .resolution import VIRCLE_CODE` and every other importer are unchanged.
"""
from django.db import IntegrityError
from django.utils import timezone


# Post-award bank-details capture. A dedicated task (NOT verdict-derived — it's a
# post-award operational step, not a verification gap), so it lives outside CODE_TO_TICKET
# and is ALWAYS visible to the student (see views.ResolutionItemListView._student_visible),
# independent of the Check-2 query flag.
BANK_DETAILS_CODE = 'bank_details_missing'
# The student needs a payout account while AWARDED (signing) or ACTIVE (executed, awaiting
# the first payout). It leaves the Action Centre once they confirm one, or the award ends.
BANK_CAPTURE_STATES = frozenset({'awarded', 'active'})


def sync_bank_details_item(application):
    """Reconcile the post-award bank-details task: ensure ONE open ``bank_details_missing``
    item while the student is awarded/active with no confirmed payout account, and resolve
    it once a ``BankAccount`` is confirmed (or the award leaves those states). Idempotent.

    Gated by ``BANK_DETAILS_CAPTURE_ENABLED`` (default OFF — feature being deprecated): while
    OFF, ``wanted`` is forced False, so no task is ever created and any existing open one is
    swept to resolved (it drops out of the Action Centre)."""
    from django.conf import settings
    from .models import BankAccount, ResolutionItem
    enabled = getattr(settings, 'BANK_DETAILS_CAPTURE_ENABLED', False)
    has_account = BankAccount.objects.filter(application=application).exists()
    wanted = enabled and application.status in BANK_CAPTURE_STATES and not has_account
    existing = application.resolution_items.filter(code=BANK_DETAILS_CODE).first()
    if wanted and existing is None:
        try:
            ResolutionItem.objects.create(
                application=application, source='system', code=BANK_DETAILS_CODE,
                fact='other', kind='doc', doc_type='bank_statement', params={},
            )
        except IntegrityError:
            pass  # created concurrently — fine
    elif wanted and existing is not None and existing.status != 'open':
        # Self-heal: the task is still needed (awarded/active, no account) but was resolved —
        # e.g. wrongly swept by a verdict sync, or the status bounced. RE-OPEN it so an
        # un-uploaded bank task can never silently read as "done". (Bug fix 2026-06-29.)
        existing.status = 'open'
        existing.resolved_by = ''
        existing.resolved_at = None
        existing.save(update_fields=['status', 'resolved_by', 'resolved_at'])
    elif existing is not None and existing.status == 'open' and not wanted:
        existing.status = 'resolved'
        existing.resolved_by = 'system'
        existing.resolved_at = timezone.now()
        existing.save(update_fields=['status', 'resolved_by', 'resolved_at'])


# Post-award Vircle eWallet setup — the same shape as the bank-details task above: a post-award
# OPERATIONAL step, not a verification gap, so it lives outside CODE_TO_TICKET and is always
# visible to an awarded/active student (independent of the Check-2 query flag).
#
# It is a 'confirm' item, and what the student types is the MOBILE NUMBER they registered with
# Vircle — stored on the item's own resolution_text (exactly how a clarify answer is stored).
# That row IS the record: Vircle tells us nothing back, so this is the student's CLAIM, never a
# verification. Nothing here may call it "verified".
VIRCLE_CODE = 'vircle_setup_pending'
VIRCLE_SETUP_STATES = frozenset({'awarded', 'active'})


def sync_vircle_item(application):
    """Reconcile the Vircle setup task. Idempotent.

    This function NEVER CREATES the task — that is deliberate. The task is raised by whatever
    SENT the email (``vircle.raise_setup_task``, called from the award-email paths), so it appears
    only for a student who was actually told what it is for. If creation lived here instead, then
    the moment ``VIRCLE_SETUP_ENABLED`` flipped on, every awarded student would find a "set up
    your eWallet" card they had never been emailed about.

    It only SWEEPS: an open task is resolved once the student leaves awarded/active (the award
    ended — nothing to set up), or while the feature is switched off.

    It never RE-OPENS a resolved task either: resolving it is the student saying "my Vircle
    account is active", and that claim doesn't expire — re-opening would nag someone who has
    already done the work.
    """
    from django.conf import settings
    enabled = getattr(settings, 'VIRCLE_SETUP_ENABLED', False)
    existing = application.resolution_items.filter(code=VIRCLE_CODE).first()
    if existing is None or existing.status != 'open':
        return
    still_wanted = enabled and application.status in VIRCLE_SETUP_STATES
    if not still_wanted:
        existing.status = 'resolved'
        existing.resolved_by = 'system'
        existing.resolved_at = timezone.now()
        existing.save(update_fields=['status', 'resolved_by', 'resolved_at'])
