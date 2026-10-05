"""Correcting the parent/guardian contact — by the student, or by an administrator (request #26).

A student asked "how do I change my father's phone number? it is a typo", and nobody could: the
profile page never wrote `guardians`, and the admin serializer publishes it read-only. This module
is the ONE place that corrects it after the apply form, under the owner's rulings of 2026-10-05:

  R1  the student may edit it themselves, EXCEPT while it is frozen;
  R2  it is frozen ONLY while bursary signing is actually possible for that student —
      `signing_window.in_signing_window`, the very rule the PIN views apply. With
      `BURSARY_AGREEMENT_ENABLED` off (production today) NOBODY is frozen;
  R3  a super or org_admin may correct it at ANY time, frozen or not, and every real change is
      recorded (`GuardianContactChange`);
  R7  nothing about WHERE it is stored changes: entry 0 of `profile.guardians`, written through
      `profile_sync.sync_profile_fields` → `merge_guardians` (TD-055), the one writer. So
      `bursary.guarantor_phone_for` reads a corrected number with no change of its own.

See docs/decisions.md, "Parent/guardian contact: editable except while signing is possible".
"""
from django.db import transaction

from .models import GuardianContactChange, ScholarshipApplication
from .services.profile_sync import sync_profile_fields
from .signing_window import in_signing_window
from .whatsapp import normalise_msisdn

#: The apply form's own limits for these two boxes: `name` mirrors `StudentProfile.name`
#: (`ApplicationCreateSerializer.name`, max_length=255) and the phone mirrors
#: `contact_phone` (max_length=20), the column the apply form's other phone box writes.
NAME_MAX = 255
PHONE_MAX = 20

LOCKED = 'guardian_contact_locked'


class GuardianContactError(Exception):
    """A refusal with a stable code the web maps to words."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def has_scholarship_application(profile):
    """R4: the contact is shown on the profile only to a student who has applied at least once.
    There is no draft application — a row exists only from submit (see `factories.STAGES`)."""
    if profile is None:
        return False
    return ScholarshipApplication.objects.filter(profile_id=profile.pk).exists()


def contact_frozen(profile):
    """R2: frozen exactly while a bursary-signing PIN could be sent to this student's guardian.

    ⚠ DO NOT "SIMPLIFY" THIS TO A STATUS CHECK. Freezing at `status == 'awarded'` would lock
    every awarded student indefinitely to protect a control that is switched off; and any rule
    written here instead of read from `signing_window` drifts from the PIN views the first time
    either changes. `test_guardian_contact.py` pins both."""
    if profile is None:
        return False
    return in_signing_window(profile.pk)


def current_contact(profile):
    """`(name, phone)` of guardian entry 0 — what the apply form wrote and this module edits."""
    guardians = getattr(profile, 'guardians', None) or []
    first = guardians[0] if guardians and isinstance(guardians[0], dict) else {}
    return str(first.get('name') or ''), str(first.get('phone') or '')


def clean(name, phone):
    """Validate and tidy one submission. Returns `(name, phone)` or raises the error code.

    The phone must be a number the PIN sender can reach — `whatsapp.normalise_msisdn`, the very
    function that turns it into E.164 for Twilio — so an accepted number can always be texted.
    It is STORED as typed (trimmed), like the apply form stores it; nothing is reformatted."""
    name = ' '.join(str(name or '').split())
    phone = str(phone or '').strip()
    if not name:
        raise GuardianContactError('guardian_name_required')
    if len(name) > NAME_MAX:
        raise GuardianContactError('guardian_name_too_long')
    if not phone or len(phone) > PHONE_MAX or not normalise_msisdn(phone):
        raise GuardianContactError('guardian_phone_invalid')
    return name, phone


def update_guardian_contact(profile, *, name, phone, by_email, by_role, application=None,
                            allow_frozen=False):
    """Correct the parent/guardian contact. Returns the `GuardianContactChange` written, or None
    when nothing changed.

    Refuses `guardian_contact_locked` while `contact_frozen(profile)` unless `allow_frozen`
    (the admin path, R3). The write is `sync_profile_fields` → `merge_guardians`: the form's
    `[{name, phone}]` shape merged onto entry 0, every later entry kept (TD-055). The profile row
    is locked for the read-modify-write so two saves cannot interleave."""
    if by_role not in dict(GuardianContactChange.ROLE_CHOICES):
        raise ValueError(f'unknown by_role {by_role!r}')
    name, phone = clean(name, phone)
    if not allow_frozen and contact_frozen(profile):
        raise GuardianContactError(LOCKED)

    from apps.courses.models import StudentProfile
    with transaction.atomic():
        locked = StudentProfile.objects.select_for_update().get(pk=profile.pk)
        old_name, old_phone = current_contact(locked)
        updated = sync_profile_fields(locked, {'guardians': [{'name': name, 'phone': phone}]})
        profile.guardians = locked.guardians
        if 'guardians' not in updated:
            return None
        if application is None:
            application = (ScholarshipApplication.objects.filter(profile_id=locked.pk)
                           .order_by('-id').first())
        return GuardianContactChange.objects.create(
            profile=locked, application=application,
            old_name=old_name[:NAME_MAX], new_name=name,
            old_phone=old_phone[:32], new_phone=phone,
            changed_by_email=(by_email or '')[:254], changed_by_role=by_role)


def contact_payload(profile):
    """What the student's profile reads: the contact, and the two facts that decide how it shows."""
    name, phone = current_contact(profile)
    return {
        'has_scholarship_application': has_scholarship_application(profile),
        'guardian_contact_locked': contact_frozen(profile),
        'name': name,
        'phone': phone,
    }
