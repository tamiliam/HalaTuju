"""Which bursary agreement may still be countersigned or witnessed — A1.13 review (finding 1).

WHY. An award withdrawal (`award_withdrawal._apply`, on an approved request) cancels the sponsorship, but the
agreement row stayed live: its signatures stood, it still pointed at the cancelled sponsorship, and
the countersign / witness writers (`bursary.countersign_foundation`, `bursary.record_witness`) had no
status gate. The payments check D4-7 reads only ``foundation_signed_at``, so after a re-award to
another sponsor the student could have been paid on the OLD contract's countersignature. Latent
while ``BURSARY_AGREEMENT_ENABLED`` is off (as on the live API today); closed now anyway.

WHAT, using the agreement's EXISTING fields (no migration):
  * ``void_on_withdrawal`` clears every signature stamp and the sponsorship link, so the row no
    longer ``binds``; the old stamps are returned for the withdrawal's activity row (the audit).
    A re-signing (`bursary.sign_agreement`) writes fresh party signatures and, through
    ``UNSIGNED_COUNTERPARTS``, resets the Foundation's and the witness's to unsigned.
  * ``lock_current`` refuses a countersign or a witness unless the case is in the step's statuses,
    the agreement still ``binds``, and its sponsorship (when it names one) is a HOLDING sponsorship
    of this case. An agreement with no sponsorship link (made before the link, or by a fixture)
    is judged by the first two only: it cannot be matched to a sponsorship.

LOCK ORDER (`status_lock.py`): the application row first, then the agreement row.
"""
from django.db import transaction
from django.db.models import Q

#: The case statuses each step may act on. The Foundation countersigns an AWARDED case (its
#: signature executes the contract → active). The witness is non-blocking and may come after the
#: Foundation (`bursary.record_witness` distributes then), so a funded case is still open to it.
COUNTERSIGN = ('awarded',)
WITNESS = ('awarded', 'active', 'maintenance')
#: Steps that a HELD decline does not stop. A decline still in its cool-off is status 'rejected'
#: with a pending marker (`source_console.held_decline_q`); until the student is told, the case
#: stands as its ``pre_decline_status`` and the witness may still sign (source sign-in review H1).
_HELD_DECLINE_OK = (WITNESS,)

#: The counterparty fields a fresh signing starts from (`bursary.sign_agreement` defaults), and the
#: ones a withdrawal clears.
UNSIGNED_COUNTERPARTS = {
    'foundation_signed_by': '', 'foundation_signed_at': None,
    'witness_org': None, 'witness_signed_by': '', 'witness_name': '', 'witness_signed_at': None,
    'witness_ip': None, 'witness_admin': None,
    'witness_reminded_at': None, 'countersign_reminded_at': None, 'executed_pdf_emailed_at': None,
}
_PARTY_STAMPS = ('student_signed_at', 'guarantor_signed_at', 'foundation_signed_at',
                 'witness_signed_at')
_AUDIT_KEPT = ('foundation_signed_by', 'witness_org_id', 'witness_name', 'witness_signed_by',
               'witness_ip', 'witness_admin_id', 'agreement_sha256', 'pdf_storage_path')


class AgreementNotCurrent(Exception):
    """The agreement may not be countersigned / witnessed. ``reason``: ``case_status`` (the case is
    not in the step's statuses), ``agreement_void`` (it no longer binds — withdrawn) or
    ``agreement_superseded`` (its sponsorship is no longer this case's holding one). The views
    answer 409 ``agreement_not_current``."""
    code = 'agreement_not_current'

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def lock_current(agreement, allowed_statuses):
    """Lock the case, then the agreement; raise ``AgreementNotCurrent`` unless it may be signed now.
    The caller's ``agreement`` and its ``application`` are refreshed from the locked rows. Opens a
    savepoint under the caller's transaction (the doors hold one across the write); a bare caller
    gets the check, with the lock held only for it."""
    from .models import BursaryAgreement, Sponsorship
    from .status_lock import StatusRefused, lock_application_for
    held_ok = allowed_statuses in _HELD_DECLINE_OK
    with transaction.atomic():
        try:
            app = lock_application_for(
                agreement.application, (*allowed_statuses, 'rejected') if held_ok else allowed_statuses)
        except StatusRefused:
            raise AgreementNotCurrent('case_status')
        if app.status == 'rejected' and not (
                app.pending_rejection_category and app.pre_decline_status in allowed_statuses):
            raise AgreementNotCurrent('case_status')     # a decline the student has been told of
        locked = BursaryAgreement.objects.select_for_update().get(pk=agreement.pk)
        for f in BursaryAgreement._meta.concrete_fields:
            if f.name != 'application':
                setattr(agreement, f.attname, getattr(locked, f.attname))
        if not agreement.binds:
            raise AgreementNotCurrent('agreement_void')
        current = Q(status__in=Sponsorship.HOLDING)
        if app.status == 'rejected' and app.rejected_at:
            # A contractual decline lapses the sponsorship at once (`decline.admin_reject`); while
            # it is held, the one it lapsed still counts (re-review 2). Cancelling it reinstates.
            current |= Q(status='lapsed', decided_at__gte=app.rejected_at)
        if agreement.sponsorship_id is not None and not Sponsorship.objects.filter(
                current, pk=agreement.sponsorship_id,
                application_id=agreement.application_id).exists():
            raise AgreementNotCurrent('agreement_superseded')
    return agreement


def is_void(agreement):
    """Voided by a withdrawal: unsigned and linked to no sponsorship. Its old PDF is not shown (the
    path stays on the row, so the orphan-blob sweep keeps the signed file; the audit has it too)."""
    return not agreement.binds and agreement.sponsorship_id is None


def live_agreement(application):
    """The application's agreement, or None when it has none OR it is void (A1.13 third review).
    A voided row is no contract: after a re-award the student must be shown the NEW contract to
    sign (the preview), never "agreement signed" on the dead one. Her signing then overwrites the
    same row (`bursary.sign_agreement`'s update_or_create on the application)."""
    agreement = getattr(application, 'bursary_agreement', None)
    return None if agreement is None or is_void(agreement) else agreement


def void_on_withdrawal(application):
    """Under the caller's application lock: void this case's agreement, if it has one. Returns the
    old signature stamps (ISO text, for the audit row), or None when there was no agreement."""
    from .models import BursaryAgreement
    agreement = BursaryAgreement.objects.select_for_update().filter(application=application).first()
    if agreement is None:
        return None
    was = {f: (getattr(agreement, f).isoformat() if getattr(agreement, f) else None)
           for f in _PARTY_STAMPS}
    was['sponsorship_id'] = agreement.sponsorship_id
    for f in _AUDIT_KEPT:   # re-review 3: everything the void clears that the stamps do not carry
        value = getattr(agreement, f)
        was[f] = value if value is None or isinstance(value, (int, str)) else str(value)
    fields = {**UNSIGNED_COUNTERPARTS, 'student_signed_at': None, 'guarantor_signed_at': None,
              'sponsorship': None}
    for name, value in fields.items():
        setattr(agreement, name, value)
    agreement.save(update_fields=[*fields, 'updated_at'])
    return was
