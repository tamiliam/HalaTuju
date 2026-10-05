"""Correcting the parent/guardian contact — by the student, or by an administrator (request #26).

A student asked "how do I change my father's phone number? it is a typo", and nobody could: the
profile page never wrote `guardians`, and the admin serializer publishes it read-only. This module
is the ONE place that corrects it after the apply form, under the owner's rulings of 2026-10-05:

  R1  the student may edit it themselves, EXCEPT while it is frozen;
  R2  it is frozen ONLY while bursary signing is actually possible for that student —
      `signing_window.in_signing_window`, the very rule the PIN views apply. With
      `BURSARY_AGREEMENT_ENABLED` off (production today) NOBODY is frozen;
  R3  a super or org_admin may correct it at ANY time, frozen or not — but while it is frozen an
      org_admin only when THEIR organisation holds the open offer (review F1, 2026-10-05) — and
      every real change made through the product is recorded (`GuardianContactChange`). Django's
      staff-only `/admin/` site is the one writer that records nothing;
  R7  nothing about WHERE it is stored changes: entry 0 of `profile.guardians`, written through
      `profile_sync.sync_profile_fields` → `merge_guardians` (TD-055), the one writer. So
      `bursary.guarantor_phone_for` reads a corrected number with no change of its own.

See docs/decisions.md, "Parent/guardian contact: editable except while signing is possible".
"""
import re

from django.db import transaction

from .models import GuardianContactChange, ScholarshipApplication
from .services.profile_sync import sync_profile_fields
from .signing_window import award_application, in_signing_window, signing_enabled

#: The apply form's own limits for these two boxes: `name` mirrors `StudentProfile.name`
#: (`ApplicationCreateSerializer.name`, max_length=255) and the phone mirrors
#: `contact_phone` (max_length=20), the column the apply form's other phone box writes.
NAME_MAX = 255
PHONE_MAX = 20

LOCKED = 'guardian_contact_locked'
IS_STUDENTS = 'guardian_phone_is_students'


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


def frozen_for_organisation(profile, organisation_id):
    """Review F1: frozen AND the open offer belongs to ANOTHER organisation than ``organisation_id``.

    A student may hold an application in organisation A and an offer in organisation B. The
    contact is one per student, so A's org_admin correcting it through A's application would move
    B's signing PIN. While frozen, only the organisation holding the open offer (or a super) may."""
    if profile is None or not signing_enabled():
        return False
    offer_app = award_application(profile.pk)
    return offer_app is not None and offer_app.owning_organisation_id != organisation_id


def malaysian_mobile(raw):
    """The parent phone as the screen accepts it (`isValidMobile`, review F5), in its local
    display form ``01X-XXX XXXX`` / ``011-XXXX XXXX``; '' when it is not a Malaysian mobile.

    Only digits, spaces, dashes and one leading ``+`` may be typed; ``+60`` / ``60`` / ``0060``
    become the local ``0``. A mobile is ``01X`` — ``011`` 11 digits, the rest 10 — because the
    PIN is an SMS and a landline cannot receive one. ⚠ Deliberately stricter than
    `whatsapp.normalise_msisdn`, which stays lenient: Vircle, phone-verify and every outbound
    WhatsApp send read stored numbers of every historical shape through it."""
    raw = str(raw or '').strip()
    if not raw or not re.fullmatch(r'\+?[\d\s-]+', raw):
        return ''
    d = re.sub(r'\D', '', raw)
    for prefix in ('0060', '60'):
        if d.startswith(prefix):
            d = '0' + d[len(prefix):]
            break
    if not d.startswith('01') or len(d) != (11 if d.startswith('011') else 10):
        return ''
    return f'{d[:3]}-{d[3:-4]} {d[-4:]}'


def is_students_own(phone, profile):
    """Review F3: the student's own contact phone typed as the parent's — the self-verify the
    whole PIN gate exists to stop."""
    from .bursary import same_phone
    own = getattr(profile, 'contact_phone', '') or ''
    return bool(own) and same_phone(phone, own)


def record_change(profile, old, *, application, by_email, by_role):
    """Write a `GuardianContactChange` when entry 0's name or phone actually moved from ``old``
    (a ``(name, phone)`` pair); None when it did not. Shared by this module and the apply form."""
    new_name, new_phone = current_contact(profile)
    if (new_name, new_phone) == tuple(old):
        return None
    return GuardianContactChange.objects.create(
        profile=profile, application=application,
        old_name=old[0][:NAME_MAX], new_name=new_name[:NAME_MAX],
        old_phone=old[1][:32], new_phone=new_phone[:32],
        changed_by_email=(by_email or '')[:254], changed_by_role=by_role)


def screen_form_guardians(profile, data):
    """The APPLY FORM's guardians, screened before `sync_profile_fields` writes them. Mutates
    ``data``; returns the stored ``(name, phone)`` from before, for `record_change`.

    * Frozen (gap A): the form's guardians are dropped and the stored one stands — a second
      application to another open round must not move the number the signing PIN goes to.
    * The phone is the student's OWN (review F3; compared with the form's own `contact_phone`,
      which syncs in the same call, else the stored one): it is not stored as the parent's. The
      stored parent phone stands if there is one; otherwise the name is kept with no phone.
    Never refuses: the application is still created and every other field syncs."""
    old = current_contact(profile)
    if 'guardians' not in data:
        return old
    if contact_frozen(profile):
        data.pop('guardians')
        return old
    form = data['guardians']
    if isinstance(form, list) and form and isinstance(form[0], dict):
        from .bursary import same_phone
        own = data.get('contact_phone') or getattr(profile, 'contact_phone', '') or ''
        if own and same_phone(str(form[0].get('phone') or ''), own):
            if old[1]:
                data.pop('guardians')
            else:
                data['guardians'] = [{**form[0], 'phone': ''}] + form[1:]
    return old


def current_contact(profile):
    """`(name, phone)` of guardian entry 0 — what the apply form wrote and this module edits."""
    guardians = getattr(profile, 'guardians', None) or []
    first = guardians[0] if guardians and isinstance(guardians[0], dict) else {}
    return str(first.get('name') or ''), str(first.get('phone') or '')


def clean(name, phone, profile=None):
    """Validate and tidy one submission. Returns `(name, phone)` or raises the error code.

    The phone must be a Malaysian mobile (`malaysian_mobile`, the same rule as the screen) and
    is STORED in its local display form, not as typed. It may not be the student's own number."""
    name = ' '.join(str(name or '').split())
    if not name:
        raise GuardianContactError('guardian_name_required')
    if len(name) > NAME_MAX:
        raise GuardianContactError('guardian_name_too_long')
    if len(str(phone or '').strip()) > PHONE_MAX:
        raise GuardianContactError('guardian_phone_invalid')
    phone = malaysian_mobile(phone)
    if not phone:
        raise GuardianContactError('guardian_phone_invalid')
    if is_students_own(phone, profile):
        raise GuardianContactError(IS_STUDENTS)
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
    name, phone = clean(name, phone, profile)
    if not allow_frozen and contact_frozen(profile):
        raise GuardianContactError(LOCKED)

    from apps.courses.models import StudentProfile
    with transaction.atomic():
        locked = StudentProfile.objects.select_for_update().get(pk=profile.pk)
        old = current_contact(locked)
        updated = sync_profile_fields(locked, {'guardians': [{'name': name, 'phone': phone}]})
        profile.guardians = locked.guardians
        if 'guardians' not in updated:
            return None
        if application is None:
            application = (ScholarshipApplication.objects.filter(profile_id=locked.pk)
                           .order_by('-id').first())
        return record_change(locked, old, application=application, by_email=by_email,
                             by_role=by_role)


def contact_payload(profile):
    """What the student's profile reads: the contact, and the two facts that decide how it shows."""
    name, phone = current_contact(profile)
    return {
        'has_scholarship_application': has_scholarship_application(profile),
        'guardian_contact_locked': contact_frozen(profile),
        'name': name,
        'phone': phone,
    }
