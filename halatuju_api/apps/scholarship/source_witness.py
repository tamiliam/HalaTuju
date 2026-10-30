"""A source WITNESSES the bursary contract — the one write (source sign-in S4, 2026-10-30).

Roadmap: `docs/plans/2026-10-30-source-sign-in-roadmap.md` (S4; conflicts C13, C14). Who may ask and
which application are the view's (`views_admin/source_console.AdminSourceWitnessView`, through
`source_access` and `source_console.can_witness`); this module only records, once.

⚠ ONCE, AND RACE-SAFE. `record_once` re-reads the agreement under `select_for_update` and refuses a
witness already recorded (`AlreadyWitnessed`, the views' 409 `already_witnessed`), so two clicks — or
a source and a super at the same moment — can never record twice, re-render the PDF twice or send
the Foundation's nudge twice. The super's fallback (`AdminBursaryWitnessView`) goes through it too.

⚠ EVERYTHING AFTER THE STAMP IS `bursary.record_witness`, UNCHANGED: the re-render, then the
Foundation's countersign nudge, or — when the Foundation signed first — the executed distribution.
This module adds only what the agreement keeps about a SOURCE's witness: the IP it was recorded from
(`witness_ip`, beside `student_ip` / `guarantor_ip`) and the source user who recorded it
(`witness_admin`). A super's record leaves both NULL.

⚠ `has_console` IS THE EMAIL BUTTON RULE. A witness email may send a source to its console only
when somebody there can open it: the source is switched on and an ACTIVE user of it has signed in
(`source_invite.has_joined` — the Sources page's own "joined"). Otherwise the email keeps asking them
to reply, because a link to a page nobody can open is the broken promise the 2026-08-03 fix removed.
"""
from django.db import transaction


class AlreadyWitnessed(Exception):
    """The witness is already recorded on this agreement."""


def has_console(source):
    """Can somebody at ``source`` open its console today? (The witness emails' button rule.)"""
    if source is None or not getattr(source, 'is_active', False):
        return False
    from .source_invite import has_joined
    return has_joined(source)


def console_link(source, application):
    """The address a witness email may carry for ``source``: the application's page, which the web
    routes a source user to its own view of (S4) — or '' when nobody there can sign in."""
    if not has_console(source):
        return ''
    from .bursary import _cockpit_link
    return _cockpit_link(application)


def record_once(agreement, *, org, by_name, witness_name='', admin=None, ip=None):
    """Record the witness through `bursary.record_witness`, exactly once; returns the agreement.

    ``admin`` / ``ip`` are the SOURCE user and their address (a super passes neither). Raises
    `AlreadyWitnessed` when a witness is already on the agreement — read under the row lock, never
    from the caller's possibly stale copy."""
    from . import bursary
    from .models import BursaryAgreement
    with transaction.atomic():
        # No select_related: Postgres refuses FOR UPDATE on the nullable side of an outer join
        # (`witness_org`), and SQLite (the tests) would never show it.
        locked = BursaryAgreement.objects.select_for_update().get(pk=agreement.pk)
        if locked.witness_signed_at is not None:
            raise AlreadyWitnessed()
        bursary.record_witness(locked, org=org, by_name=by_name, witness_name=witness_name)
        if admin is not None or ip is not None:
            locked.witness_admin = admin
            locked.witness_ip = ip
            locked.save(update_fields=['witness_admin', 'witness_ip', 'updated_at'])
    return locked
