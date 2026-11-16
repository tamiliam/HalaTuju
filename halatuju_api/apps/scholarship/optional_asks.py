"""H7: "I don't have this" on an OPTIONAL Check 2 document ask.

An ask is optional when its ``DOC_SPECS`` entry carries ``'optional': True`` (check2_queries): the
per-member EPF statements, the two utility-bill re-asks and the school-leaving certificate. Never a
document that could be required (an IC, a payslip, a results slip ...).

A student who has no such document taps "I don't have this", picks a reason from a short per-document
list (or "Other" with a note) and the ask CLOSES. Nothing else moves: no verdict, award or money rule
reads these asks (they are soft requests; the gap is only ever read to decide whether to ASK). The
reason is kept on ``params`` (``declined_reason`` / ``declined_note``), NOT in ``resolution_text``, so
it never reaches the AI prompts that quote a student's typed answers. The Check 2 sync never re-opens
a declined item (``check2_queries.sync_check2_queries`` asks ``is_declined``).
"""
from django.utils import timezone

OTHER = 'other'

#: doc_type -> {reason key: the English words the reviewer reads}. The student's own words (any of
#: en / ms / ta) live in the front end's i18n; the key is the contract. Every list ends with 'other'.
REASONS = {
    'epf': {
        'no_epf_job': 'Does not work in a job that pays EPF (for example self-employed, farmer, odd jobs)',
        'abroad': 'Works abroad',
        'cannot_get_now': 'Has EPF, but cannot get the statement now',
        'not_with_us': 'Does not live with us, or we have no contact',
        OTHER: 'Other',
    },
    'electricity_bill': {
        'landlord_pays': 'The landlord pays it, or it is in the rent',
        'shared_meter': 'We share a meter with another house',
        'no_supply': 'We have no electricity supply',
        'lost_bill': 'We lost the bill and cannot get a copy',
        OTHER: 'Other',
    },
    'water_bill': {
        'no_water_bill': 'We use a well, river or hill water (no water bill)',
        'landlord_pays': 'The landlord pays it, or it is in the rent',
        'shared_meter': 'We share a meter with another house',
        'lost_bill': 'We lost the bill and cannot get a copy',
        OTHER: 'Other',
    },
    'school_leaving_cert': {
        'not_given_yet': 'The school has not given it to me yet',
        'lost_asked_copy': 'I lost it and I am asking for a copy',
        'cannot_reach_school': 'I cannot reach the school',
        OTHER: 'Other',
    },
}

MAX_NOTE = 500


def is_optional(item):
    """True when this item is a Check 2 document ask marked optional in ``DOC_SPECS``."""
    from .check2_queries import DOC_SPECS
    if item.source != 'check2' or item.kind != 'doc':
        return False
    spec = DOC_SPECS.get(item.code)
    return bool(spec and spec.get('optional') and spec.get('doc_type') in REASONS)


def is_declined(item):
    """True when the student closed this ask with "I don't have this" (it is never asked again)."""
    return bool((item.params or {}).get('declined_reason'))


def reasons_for(item):
    """The reason keys this item accepts (empty for a required ask)."""
    return list(REASONS[item.doc_type]) if is_optional(item) and item.doc_type in REASONS else []


def decline(item, reason, note=''):
    """Close an optional ask with the student's reason. Returns ``None`` on success, else the error
    code: ``reason_not_allowed`` (a required ask), ``invalid_reason``, or ``note_required`` ("Other"
    needs words). The caller has already checked the item is open and the student's own."""
    if not is_optional(item):
        return 'reason_not_allowed'
    reason = str(reason or '').strip()
    if reason not in REASONS.get(item.doc_type, {}):
        return 'invalid_reason'
    note = str(note or '').strip()[:MAX_NOTE]
    if reason == OTHER and not note:
        return 'note_required'
    params = {k: v for k, v in (item.params or {}).items() if k not in ('declined_reason', 'declined_note')}
    params['declined_reason'] = reason
    if note:
        params['declined_note'] = note
    item.params = params
    item.status = 'resolved'
    item.resolved_by = 'student'
    item.resolved_at = timezone.now()
    item.save(update_fields=['params', 'status', 'resolved_by', 'resolved_at'])
    return None
