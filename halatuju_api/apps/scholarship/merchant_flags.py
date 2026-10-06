"""Flag a shop for review — one organisation's notes log on one shop (request #28 follow-up,
2026-10-06). The models are `models/merchant_flags.py`; the endpoints `views_admin/spending_flags.py`.

────────────────────────────────────────────────────────────────────────────────────────────────
⚠⚠ **TENANCY IS THE WHOLE DESIGN.** A shop's CATEGORY is platform-wide (one `MerchantCategory` row
per shop for everybody). A FLAG is not: it belongs to exactly ONE organisation, and every function
here takes that organisation's id and filters on it at the query. Another organisation's flag is
never read, never counted, and never distinguishable from "no flag" — a read for a shop with no flag
of OURS answers exactly as a read for a shop nobody flagged, and a write for a shop our students
never used is `unknown_merchant`, whoever else may have flagged it.

⚠ **THE ORGANISATION IS RESOLVED ONCE, FROM THE SPENDING DOOR** (`flag_organisation`). An
`org_admin` acts for their own organisation. A super holds `spend_report.ALL_ORGS`, which is NOT an
organisation, so their flag belongs to the organisation that owns the gift they are looking at — one
gift is one organisation — and with no gift named there is no single answer, so they are refused
`programme_required` rather than guessed for.

⚠ **A FLAG NEVER MOVES MONEY.** Nothing in `spend_report` reads these tables; the category, the
chart and every total are exactly what they were. Flagging asks a question; it answers nothing.

⚠ **NOTHING IS DELETED.** open → note* → close → (reopen → …): one row per (organisation, shop),
and every note is kept for ever, including the closing one.
"""
from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from .spending_import import norm_text

#: What a POST may ask for.
ACTIONS = ('open', 'note', 'close')


def flag_organisation(scope, programme):
    """`(organisation_id, error_code)` — the ONE organisation a flag read or write belongs to.

    ⚠ `scope` comes ONLY from `_SpendingBase._spending_admin`: an organisation for an org_admin,
    `ALL_ORGS` for a super. For the super the gift decides (it was resolved inside the fence by
    `_gift_narrowing`), and its `organisation_id` is read without a query.
    """
    from .spend_report import ALL_ORGS

    if scope is ALL_ORGS:
        if programme is None:
            return None, 'programme_required'
        return programme.organisation_id, None
    return scope.pk, None


def open_flag_merchants(org_id) -> set:
    """The shops THIS organisation has an OPEN flag on — one query for the whole page."""
    from .models import MerchantFlag

    if org_id is None:
        return set()
    # org-fence: organisation_id — a flag is one organisation's; another's is never read here.
    return set(MerchantFlag.objects.filter(organisation_id=org_id, is_open=True)
               .values_list('merchant', flat=True))


def _log(flag):
    """The notes, oldest first — the model's own ordering."""
    return [{
        'kind': n.kind,
        'body': n.body,
        'author': n.author_email,
        'at': n.created_at.isoformat(),
    } for n in flag.notes.all()] if flag is not None else []


def flag_log(org_id, merchant) -> dict:
    """`{merchant, flagged, notes}` for THIS organisation's flag on `merchant`.

    ⚠ NO FLAG OF OURS (including another organisation's flag on the same shop, or a shop we never
    used) answers `flagged: False, notes: []` — the same bytes either way, so a read cannot be used
    to learn whether somebody else is looking at a shop.
    """
    from .models import MerchantFlag

    merchant = norm_text(merchant)
    # org-fence: organisation_id — this organisation's flag only, never another's.
    flag = MerchantFlag.objects.filter(organisation_id=org_id, merchant=merchant).first()
    return {
        'merchant': merchant,
        'flagged': bool(flag and flag.is_open),
        'notes': _log(flag),
    }


def change_flag(org_id, merchant, action, note, email, txns):
    """Open, note or close THIS organisation's flag on `merchant`. Returns `(log, error_code)`.

    `txns` is the caller's FENCED spend queryset (`spend_report._txns(org_id, programme)`): the
    shop must be one this organisation's students actually used, exactly as for a category
    correction — so a guessed or another organisation's shop name is `unknown_merchant`.

    Codes: `merchant_required`, `unknown_action`, `note_required`, `note_too_long`,
    `unknown_merchant`, `already_flagged` (open on an open flag), `not_flagged` (note or close
    with no open flag).
    """
    from .models import NOTE_MAX, MerchantFlag, MerchantFlagNote

    merchant = norm_text(merchant)
    note = (note or '').strip() if isinstance(note, str) else ''
    if not merchant:
        return None, 'merchant_required'
    if action not in ACTIONS:
        return None, 'unknown_action'
    if not note:
        return None, 'note_required'
    if len(note) > NOTE_MAX:
        return None, 'note_too_long'
    if not txns.filter(merchant=merchant).exists():
        return None, 'unknown_merchant'
    email = (email or '')[:254]
    now = timezone.now()
    try:
        with transaction.atomic():
            # org-fence: organisation_id — this organisation's flag only. Locked, so two people
            # pressing Flag at once cannot both open it.
            flag = (MerchantFlag.objects.select_for_update()
                    .filter(organisation_id=org_id, merchant=merchant).first())
            if action == 'open':
                if flag is None:
                    # org-fence: created FOR this organisation's id, and no other.
                    flag = MerchantFlag.objects.create(
                        organisation_id=org_id, merchant=merchant, is_open=True,
                        opened_at=now, opened_by_email=email)
                elif flag.is_open:
                    return None, 'already_flagged'
                else:
                    # REOPEN the same flag: the history continues on one log.
                    flag.is_open, flag.opened_at, flag.opened_by_email = True, now, email
                    flag.closed_at, flag.closed_by_email = None, ''
                    flag.save(update_fields=['is_open', 'opened_at', 'opened_by_email',
                                             'closed_at', 'closed_by_email'])
            elif flag is None or not flag.is_open:
                return None, 'not_flagged'
            elif action == 'close':
                flag.is_open, flag.closed_at, flag.closed_by_email = False, now, email
                flag.save(update_fields=['is_open', 'closed_at', 'closed_by_email'])
            # org-fence: through `flag`, read above on this organisation's id.
            MerchantFlagNote.objects.create(flag=flag, kind=action, body=note, author_email=email)
    except IntegrityError:
        # The other half of a race the lock cannot cover: two FIRST opens, neither row yet there.
        return None, 'already_flagged'
    return {'merchant': merchant, 'flagged': flag.is_open, 'notes': _log(flag)}, None
