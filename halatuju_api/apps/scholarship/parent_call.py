"""The call to the parent — reasonable, RECORDED steps that the parent is on board (request #26).

THE OWNER'S FRAMING (2026-10-05): "We are not dealing with a potential fraud. We only want the
parent's consent to signing a contract, so in the event of a dispute we could prove we have taken
reasonable steps to ensure the parent is onboard." Nothing here defeats a determined cheat (a second
SIM beats any phone check) and nothing here tries to. It makes sure a doubtful number gets a human
call before the award, and that the call is on the record.

THE FLAG is a LIVE, DERIVED condition — never a stored boolean:
    the parent phone (`guardians[0].phone`) is the student's own `contact_phone` (`same_phone`)
    AND there is no CLEARING call for the CURRENT parent number.
A clearing call is a `kind='call'` row with outcome `shared_confirmed` or
`parent_number_confirmed`, `consent_given=True`, whose `called_number` is that number. A changed
parent number is therefore unchecked again automatically. No lock of any kind follows from it; the
one thing it holds back is the award good-news email (`held_for_parent_call`).

"RECORD CALL" is an admin action (super + org_admin, the correction's fence — see
`views_admin/guardian_contact.py`). For `parent_number_corrected` ONE action records the call AND
stores the corrected phone, so the number on file is exactly the number recorded as called.
"""
import logging

from django.db import transaction

from .guardian_contact import (
    NAME_MAX, GuardianContactError, current_contact, malaysian_mobile,
)
from .models import GuardianContactChange
from .services.profile_sync import sync_profile_fields

logger = logging.getLogger(__name__)

OUTCOMES = tuple(code for code, _ in GuardianContactChange.OUTCOME_CHOICES)
NOTE_MAX = 2000


def _same_phone(a, b):
    from .bursary import same_phone
    return same_phone(a, b)


def shared_phone(profile):
    """The parent phone on file is the student's own contact phone (however either was typed)."""
    _, parent = current_contact(profile)
    return _same_phone(parent, getattr(profile, 'contact_phone', '') or '')


def call_cleared(profile):
    """A clearing call — consent given, a confirming outcome — recorded against the CURRENT number."""
    _, parent = current_contact(profile)
    if not parent:
        return False
    calls = (GuardianContactChange.objects
             .filter(profile_id=profile.pk, kind='call', consent_given=True,
                     call_outcome__in=GuardianContactChange.CLEARING_OUTCOMES)
             .values_list('called_number', flat=True))
    return any(_same_phone(number, parent) for number in calls)


def needs_parent_call(profile):
    """THE FLAG: a shared phone with no clearing call for this number. Asks the database only when
    the phone IS shared, so the ordinary case costs no query."""
    return profile is not None and shared_phone(profile) and not call_cleared(profile)


def held_for_parent_call(application, held=None):
    """True when the award good-news email must WAIT for the call; the id is appended to ``held``
    so the sender can report it. Nothing is stamped, so the next run retries once it is cleared."""
    if not needs_parent_call(getattr(application, 'profile', None)):
        return False
    if held is not None:
        held.append(application.pk)
    logger.info('Award email held for a parent call: application %s', application.pk)
    return True


def record_call(profile, *, application, outcome, consent, number='', parent_name='', note='',
                by_email=''):
    """Record a call an admin made to the parent. Returns the `GuardianContactChange` (kind 'call').

    * ``outcome`` is one of `OUTCOMES`. ``consent`` (parent told about the bursary and agreed) is
      required as yes/no for every outcome except `could_not_reach`, where nobody was spoken to.
    * A confirming outcome is about the number ON FILE: ``number`` may be left blank (it is the
      number on file) and may not name another number (`called_number_mismatch`).
    * `parent_number_corrected` needs a valid Malaysian mobile and STORES it as the parent phone in
      the same transaction (`sync_profile_fields` → `merge_guardians`, the one writer) — the
      evidential point: the number on file is the number recorded as called."""
    if outcome not in OUTCOMES:
        raise GuardianContactError('call_outcome_invalid')
    reached = outcome != 'could_not_reach'
    if reached and consent not in (True, False):
        raise GuardianContactError('call_consent_required')
    parent_name = ' '.join(str(parent_name or '').split())[:NAME_MAX]
    note = str(note or '').strip()[:NOTE_MAX]
    number = str(number or '').strip()

    from apps.courses.models import StudentProfile
    with transaction.atomic():
        locked = StudentProfile.objects.select_for_update().get(pk=profile.pk)
        old_name, old_phone = current_contact(locked)
        if outcome == 'parent_number_corrected':
            number = malaysian_mobile(number)
            if not number:
                raise GuardianContactError('guardian_phone_invalid')
            sync_profile_fields(locked, {'guardians': [
                {'name': old_name or parent_name, 'phone': number}]})
            profile.guardians = locked.guardians
        elif not number:
            number = old_phone
        elif outcome in GuardianContactChange.CLEARING_OUTCOMES and not _same_phone(number, old_phone):
            raise GuardianContactError('called_number_mismatch')
        new_name, new_phone = current_contact(locked)
        return GuardianContactChange.objects.create(
            profile=locked, application=application, kind='call',
            old_name=old_name[:NAME_MAX], new_name=new_name[:NAME_MAX],
            old_phone=old_phone[:32], new_phone=new_phone[:32],
            called_number=number[:32], call_outcome=outcome,
            consent_given=bool(consent) if reached else None,
            parent_name_given=parent_name, note=note,
            changed_by_email=(by_email or '')[:254], changed_by_role='admin')
