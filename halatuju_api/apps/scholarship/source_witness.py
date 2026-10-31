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


class WitnessChanged(Exception):
    """The application's resolved witness is no longer the organisation the caller checked — the
    override moved between the caller's read and the row lock (review L2)."""


def has_console(source):
    """Can somebody at ``source`` open its console today? (The witness emails' button rule.)"""
    if source is None or not getattr(source, 'is_active', False):
        return False
    from .source_invite import has_joined
    return has_joined(source)


def console_link(source, application):
    """The address a witness email may carry for ``source``: the application's page, which the web
    routes a source user to its own view of (S4) — or '' when nobody there can sign in.

    ⚠ DEPLOY PRECONDITION (review M2): the web route `/admin/scholarship/<id>` must send a SOURCE user
    to its own view of the application before this link can land anywhere — web and api deploy in
    the same push. With `BURSARY_AGREEMENT_ENABLED` off no witness email is sent anyway."""
    if not has_console(source):
        return ''
    from .bursary import _cockpit_link
    return _cockpit_link(application)


def record_once(agreement, *, org, by_name, witness_name='', admin=None, ip=None, actor=None):
    """Record the witness through `bursary.record_witness`, exactly once; returns the agreement.

    ``admin`` / ``ip`` are the SOURCE user and their address (a super passes neither). Under the row
    locks — never from the caller's possibly stale copies — it raises `AlreadyWitnessed` when a
    witness is already on the agreement, and `WitnessChanged` when the application's resolved
    witness (`bursary._resolve_witness_org`, re-read now) is no longer ``org`` (review L2).

    ⚠ THE SIDE EFFECTS STAY INSIDE THE TRANSACTION (review L2 asked to move them to
    `transaction.on_commit` only if the super's path and its tests were unchanged — they are not):
    `record_witness` re-renders and uploads the PDF and sends the Foundation's nudge or the executed
    distribution inline, and the super's fallback and its suite (`test_bursary_agreement.py`, which
    asserts the re-render and the mail on the same call, inside `TestCase` where on-commit callbacks
    never run) rely on that. The cost is a longer-held lock on ONE agreement row, at a volume of a
    handful of witnesses a month.

    The witness is a `contract_witnessed` row on the witnessing person's own activity list (common
    profile S3), in this transaction: ``admin`` for a source user, ``actor`` for the super's fallback
    (which passes no ``admin``, because ``witness_admin`` names a SOURCE user only). Both doors come
    through here, so the row is written once whichever door was used."""
    from . import bursary, staff_activity
    from .models import BursaryAgreement, ScholarshipApplication
    with transaction.atomic():
        # The application FIRST (the override lives on it), then the agreement. `of=('self',)` and
        # no select_related on the agreement: Postgres refuses FOR UPDATE on the nullable side of an
        # outer join, and SQLite (the tests) would never show it.
        application = (ScholarshipApplication.objects.select_for_update(of=('self',))
                       .select_related('witness_org', 'source').get(pk=agreement.application_id))
        locked = BursaryAgreement.objects.select_for_update().get(pk=agreement.pk)
        if locked.witness_signed_at is not None:
            raise AlreadyWitnessed()
        resolved = bursary._resolve_witness_org(application)
        if resolved is None or org is None or resolved.pk != org.pk:
            raise WitnessChanged()
        locked.application = application
        bursary.record_witness(locked, org=org, by_name=by_name, witness_name=witness_name)
        if admin is not None or ip is not None:
            locked.witness_admin = admin
            locked.witness_ip = ip
            locked.save(update_fields=['witness_admin', 'witness_ip', 'updated_at'])
        staff_activity.record(actor or admin, staff_activity.CONTRACT_WITNESSED, application,
                              meta=lambda: {'agreement': locked,
                                            'by': 'source' if admin is not None else 'staff'})
    return locked
