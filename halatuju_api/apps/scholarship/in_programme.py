"""B40 Phase E/F (F9a) — the in-programme student lifecycle.

This module owns the WRITES for a student who is already in the programme
(``status='sponsored'``): recording latest-semester results, the separate 18+
``promotional_use`` consent, and the anonymity-preserving graduation thank-you
relay. The coarse, non-identifying ``progress_state`` a sponsor sees is DERIVED
from the latest ``SemesterResult`` by ``pool.derive_progress_state`` (a read, kept
in ``pool`` so the allowlist serializer has no dependency on this module).

Import direction is one-way — ``in_programme → pool → models`` — so there is no
import cycle: this module reuses ``pool.scan_anon_for_identifiers`` (the structural
identifier gate) for the graduation relay, and ``services`` for consent + the
``is_minor`` age check.
"""
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from . import pool, services
from .models import GraduationMessage, SemesterResult


class InProgrammeError(Exception):
    """Raised for an out-of-order / disallowed in-programme action. Carries a short
    ``code`` (e.g. 'not_in_programme', 'minor_not_allowed', 'bad_cgpa') for the view."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


# A student only has an in-programme lifecycle once their award is accepted.
def _require_in_programme(application):
    # In-programme = funded: active (executed/pre-payout) or maintenance (funded).
    if application is None or application.status not in ('active', 'maintenance'):
        raise InProgrammeError('not_in_programme')


# ── Latest-semester results → progress signal ────────────────────────────────

_CGPA_MIN, _CGPA_MAX = Decimal('0'), Decimal('4')


def _clean_cgpa(cgpa):
    """Validate/normalise a CGPA to a 0.00–4.00 Decimal, or None when omitted.
    Raises InProgrammeError('bad_cgpa') on a non-numeric / out-of-range value."""
    if cgpa is None or cgpa == '':
        return None
    try:
        value = Decimal(str(cgpa)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        raise InProgrammeError('bad_cgpa')
    if value < _CGPA_MIN or value > _CGPA_MAX:
        raise InProgrammeError('bad_cgpa')
    return value


def record_semester_result(application, *, semester='', cgpa=None,
                           graduated=False, results_slip=None, note=''):
    """Record one in-programme semester result for a sponsored student.

    The ``results_slip`` (an ``ApplicantDocument``) is myNADI-only evidence — it
    never crosses to a sponsor; only the derived ``cgpa``/``graduated`` band does
    (via ``pool.derive_progress_state``). Each call appends a row; the latest by
    ``created_at`` is the one the progress signal reads. Returns the new row."""
    _require_in_programme(application)
    return SemesterResult.objects.create(
        application=application,
        semester=(semester or '').strip()[:50],
        cgpa=_clean_cgpa(cgpa),
        graduated=bool(graduated),
        results_slip=results_slip,
        note=(note or '').strip()[:500],
    )


# ── promotional_use consent — SEPARATE, 18+ ONLY (owner decision 2026-06-09) ──
# A distinct versioned consent from share_with_sponsors / onboarding. A minor can
# NEVER grant it — there is deliberately no guardian path (unlike the sponsorship
# consent): using a student's story/photo for promotion is the student's own adult
# choice. Enforced server-side from the NRIC-derived age.
PROMO_CONSENT_TYPE = 'promotional_use'


def grant_promotional_consent(application, *, locale='en', ip=None):
    """Record the student's own ``promotional_use`` consent. Hard 18+ gate: raises
    InProgrammeError('minor_not_allowed') if the NRIC indicates an age under 18 —
    there is no guardian fallback by design. ``granted_by='self'`` always."""
    _require_in_programme(application)
    if services.is_minor(getattr(application, 'profile', None)):
        raise InProgrammeError('minor_not_allowed')
    return services.record_consent(
        application, consent_type=PROMO_CONSENT_TYPE, locale=locale,
        granted_by='self', guardian_name='', guardian_relationship='', ip=ip,
    )


def withdraw_promotional_consent(application):
    """Withdraw any active promotional_use consent (PDPA: it is revocable)."""
    return application.consents.filter(
        consent_type=PROMO_CONSENT_TYPE, is_active=True,
    ).update(is_active=False)


def has_promotional_consent(application):
    return application.consents.filter(
        consent_type=PROMO_CONSENT_TYPE, is_active=True,
    ).exists()


# ── Graduation thank-you relay (scan → staff-approve → anonymous) ────────────

def submit_graduation_message(application, *, raw_text):
    """A student submits a graduation thank-you. ``pool.scan_anon_for_identifiers``
    is the STRUCTURAL gate: if the message contains the student's OWN identifying
    tokens (name/school/city/NRIC/phone/email), the row is saved ``blocked`` with
    the leaked fields in ``scan_result`` and the student must edit and resubmit. A
    clean message is ``pending`` (awaiting myNADI staff approval). Each submit
    appends a row; the relay surfaces only the ``approved`` ones. Returns the row."""
    _require_in_programme(application)
    text = (raw_text or '').strip()
    if not text:
        raise InProgrammeError('empty_message')
    leaked = pool.scan_anon_for_identifiers(text, getattr(application, 'profile', None))
    return GraduationMessage.objects.create(
        application=application,
        raw_text=text,
        scan_result=leaked,
        status='blocked' if leaked else 'pending',
    )


def approve_graduation_message(message, *, by_email, scrubbed_text=None):
    """myNADI staff approve a pending message. ``scrubbed_text`` (a light staff
    redaction) defaults to ``raw_text``; it is RE-SCANNED so a staff edit can never
    reintroduce an identifier (raises InProgrammeError('scrubbed_leak') on a leak).
    Only a ``pending`` message can be approved (a ``blocked`` one must be edited and
    resubmitted by the student first)."""
    if message.status != 'pending':
        raise InProgrammeError('not_reviewable')
    text = (scrubbed_text if scrubbed_text is not None else message.raw_text).strip()
    if not text:
        raise InProgrammeError('empty_message')
    leaked = pool.scan_anon_for_identifiers(
        text, getattr(message.application, 'profile', None))
    if leaked:
        raise InProgrammeError('scrubbed_leak')
    message.scrubbed_text = text
    message.status = 'approved'
    message.approved_by = (by_email or '')[:254]
    message.reviewed_at = timezone.now()
    message.save(update_fields=['scrubbed_text', 'status', 'approved_by', 'reviewed_at'])
    return message


def reject_graduation_message(message, *, by_email, review_note=''):
    """myNADI staff decline a pending message."""
    if message.status not in ('pending', 'blocked'):
        raise InProgrammeError('not_reviewable')
    message.status = 'rejected'
    message.approved_by = (by_email or '')[:254]
    message.review_note = (review_note or '')[:500]
    message.reviewed_at = timezone.now()
    message.save(update_fields=['status', 'approved_by', 'review_note', 'reviewed_at'])
    return message


def approved_messages_for_sponsor(sponsor):
    """The approved graduation messages for the students this sponsor actively funds,
    each carrying ONLY the anonymous ``ref`` + scrubbed text + approved time — never
    the student's identity. Returns a list of plain dicts for the relay serializer."""
    app_ids = list(
        sponsor.sponsorships.filter(status='active').values_list('application_id', flat=True)
    )
    if not app_ids:
        return []
    qs = (
        GraduationMessage.objects
        .filter(application_id__in=app_ids, status='approved')
        .order_by('-reviewed_at')
    )
    return [
        {
            'ref': pool.pool_ref(m.application_id),
            'text': m.scrubbed_text,
            'approved_at': m.reviewed_at,
        }
        for m in qs
    ]
