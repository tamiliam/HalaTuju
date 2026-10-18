"""
Writing the apply form back to the canonical profile, and the intake snapshot.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`. Then, on 2026-10-03
(TD-055), the guardians write-back became a merge (`merge_guardians`) instead of an overwrite.
"""
from django.utils import timezone

from ..shortlisting import count_spm_a_grades

# Financial fields the apply form may collect/refresh. Their canonical home is
# the StudentProfile (HalaTuju onboarding doesn't gather income), so the form
# writes them back to the profile rather than duplicating them on the
# application — avoiding a clash on the hierarchy of truth.
_PROFILE_WRITEBACK_FIELDS = (
    'household_income', 'household_size', 'receives_str', 'receives_jkm',
)

# About Me + My Family scalar fields the apply form now edits inline and commits
# on submit (S9). Same write-back-to-profile rule as the financial fields. NRIC
# is intentionally excluded — it changes only via the validated claim path,
# never an unchecked write (see docs/decisions.md, soft-NRIC).
_PROFILE_ABOUTME_FIELDS = (
    'name', 'school', 'preferred_state', 'contact_phone',
    'preferred_call_language', 'referral_source',
)

# Per-application fields that genuinely belong on the ScholarshipApplication row.
_APP_FIELDS = (
    'intended_pathway', 'intends_tertiary_2026', 'consent_to_contact', 'form_data',
    # Plans + Support intake (Sprint 7); mentoring_candidate is coordinator-set, not collected here.
    'field_of_study', 'pathways_considered', 'top_choices', 'upu_status',
    'other_scholarships', 'other_scholarships_text',
    'help_university', 'help_scholarship', 'anything_else',
    # Plans redesign (context-aware step) — all optional/additive
    'pathway_certainty', 'chosen_pathway', 'pre_u_track', 'pre_u_institution',
    'chosen_programme', 'uncertainty_reasons', 'uncertainty_note',
    # Truthfulness declaration signature (declared_at stamped separately below)
    'declaration_name',
)


#: The two keys the apply form's My Family block owns on the FIRST guardian entry.
_APPLY_GUARDIAN_KEYS = ('name', 'phone')


def _same_name(a, b):
    return ' '.join(str(a or '').split()).casefold() == ' '.join(str(b or '').split()).casefold()


def merge_guardians(existing, incoming):
    """TD-055 (2026-10-03): the apply form's guardians list, MERGED onto the stored one.

    The form collects ONE parent/guardian — ``[{name, phone}]``, or ``[]`` when both boxes are
    blank — and used to REPLACE the whole stored list with it, so any other key on that entry
    (``relationship``, ``occupation``, ``income`` — the model's documented shape) and any second
    entry were thrown away. Now the form writes only what it owns:

    * a filled form replaces entry 0's ``name`` and ``phone`` and keeps every later entry; entry 0's
      other keys are kept ONLY when the form names the SAME person (names equal, ignoring case and
      surrounding space) — a different name is a different guardian, and carrying the old one's
      relationship, occupation or income onto them would be a false record (review F4);
    * a blanked form removes entry 0's ``name`` and ``phone``; the entry goes only if nothing else
      is left on it; later entries stay.

    ⚠ For every list the apply form can have written itself — ``[]`` or one ``{name, phone}`` —
    the stored answer is IDENTICAL to the old overwrite (pinned in ``test_guardians_merge.py``).
    It differs only where some other writer stored more."""
    if not isinstance(incoming, list) or (incoming and not isinstance(incoming[0], dict)):
        return incoming                     # not the form's shape: written as sent, as before
    existing = [dict(g) for g in (existing if isinstance(existing, list) else [])
                if isinstance(g, dict)]
    first = existing[0] if existing else {}
    rest = existing[1:]
    kept = {k: v for k, v in first.items() if k not in _APPLY_GUARDIAN_KEYS}
    if incoming:
        same = _same_name(first.get('name'), incoming[0].get('name'))
        return [{**(kept if same else {}), **incoming[0]}] + rest
    return ([kept] if kept else []) + rest


def sync_profile_fields(profile, data, programme=None):
    """
    Write the form's financial + About Me/My Family fields back to the canonical
    profile (commit-on-submit, S9). Only keys that are present and non-None
    overwrite (the form may legitimately omit a field that is already on the
    profile). Parent/guardian details land in the ``guardians`` JSON list, and
    the referring-organisation code resolves to the ``source`` FK — never to
    ``referred_by_org`` (two columns, 2026-10-09). NRIC is never written here — claim path only.
    ``programme`` is the gift applied to: a source is resolved among ITS offered sources only, so
    without one (the guardian-contact writers, which never carry the answer) no source is found.
    Returns the fields actually changed.
    """
    if profile is None:
        return []
    updated = []
    for field in _PROFILE_WRITEBACK_FIELDS + _PROFILE_ABOUTME_FIELDS:
        if field in data and data[field] is not None:
            if getattr(profile, field, None) != data[field]:
                setattr(profile, field, data[field])
                updated.append(field)

    # Parent/guardian name + phone live in the guardians JSON list — MERGED, never replaced (TD-055).
    if 'guardians' in data and data['guardians'] is not None:
        merged = merge_guardians(profile.guardians, data['guardians'])
        if profile.guardians != merged:
            profile.guardians = merged
            updated.append('guardians')

    # Changing the contact phone invalidates any prior verification (mirrors PUT /profile/).
    if 'contact_phone' in updated:
        profile.contact_phone_verified = False
        updated.append('contact_phone_verified')

    # The SOURCE column (two columns, 2026-10-09): the bursary answer names an offered source, or
    # nothing. ⚠ IT NEVER TOUCHES `referred_by_org` — that is the REFERRAL PARTNER's column, written
    # only by a `?ref=` link (`apps.courses.referral_links`); writing it here put every student who
    # picked CUMIG on CUMIG's course-selector list. A key the write does not carry leaves it alone.
    # ⚠ ONLY AN OFFERED SOURCE (per-gift sources S2): the apply view has already refused a code its
    # gift does not offer (`gift_sources.is_offered`), and the lookup is the gift's OWN offered list
    # (sources Sprint B: a code is unique per organisation, so never by code alone). A FIXED choice
    # (halatuju / social / other) is a chip, never an organisation: no lookup, so it collects no one.
    from .. import gift_sources
    referral = data.get('referral_source')
    if referral is not None:
        source = None
        if referral and referral not in gift_sources.FIXED_CODES:
            source = gift_sources.offered_sources(programme).filter(code=referral).first()
        if profile.source_id != getattr(source, 'pk', None):
            profile.source = source
            updated.append('source')

    if updated:
        profile.save(update_fields=list(dict.fromkeys(updated)) + ['updated_at'])

    return updated


def build_intake_snapshot(profile, app_data):
    """
    Freeze what the applicant declared at submit time — profile-derived academic
    + financial values plus the per-application fields. This is immutable audit
    evidence, NOT the live source of truth (the profile remains canonical).
    """
    p = profile
    return {
        'captured_at': timezone.now().isoformat(),
        'profile': {
            'name': getattr(p, 'name', '') if p else '',
            'school': getattr(p, 'school', '') if p else '',
            'preferred_state': getattr(p, 'preferred_state', '') if p else '',
            'contact_phone': getattr(p, 'contact_phone', '') if p else '',
            'preferred_call_language': getattr(p, 'preferred_call_language', '') if p else '',
            'guardians': getattr(p, 'guardians', []) if p else [],
            'referral_source': getattr(p, 'referral_source', '') if p else '',
            'exam_type': getattr(p, 'exam_type', '') if p else '',
            'grades': getattr(p, 'grades', {}) if p else {},
            'stpm_cgpa': getattr(p, 'stpm_cgpa', None) if p else None,
            'spm_a_count': count_spm_a_grades(getattr(p, 'grades', None) if p else None),
            'household_income': getattr(p, 'household_income', None) if p else None,
            'household_size': getattr(p, 'household_size', None) if p else None,
            'receives_str': bool(getattr(p, 'receives_str', False)) if p else False,
            'receives_jkm': bool(getattr(p, 'receives_jkm', False)) if p else False,
        },
        'application': {
            'intended_pathway': app_data.get('intended_pathway', ''),
            'intends_tertiary_2026': app_data.get('intends_tertiary_2026', True),
            'consent_to_contact': app_data.get('consent_to_contact', False),
            'form_data': app_data.get('form_data', {}),
            'field_of_study': app_data.get('field_of_study', ''),
            'pathways_considered': app_data.get('pathways_considered', []),
            'top_choices': app_data.get('top_choices', []),
            'upu_status': app_data.get('upu_status', ''),
            'other_scholarships': app_data.get('other_scholarships', []),
            'other_scholarships_text': app_data.get('other_scholarships_text', ''),
            'help_university': app_data.get('help_university', ''),
            'help_scholarship': app_data.get('help_scholarship', ''),
            'anything_else': app_data.get('anything_else', ''),
            # Plans redesign (context-aware step)
            'pathway_certainty': app_data.get('pathway_certainty', ''),
            'chosen_pathway': app_data.get('chosen_pathway', ''),
            'pre_u_track': app_data.get('pre_u_track', ''),
            'pre_u_institution': app_data.get('pre_u_institution', ''),
            'chosen_programme': app_data.get('chosen_programme', {}),
            'uncertainty_reasons': app_data.get('uncertainty_reasons', []),
            'uncertainty_note': app_data.get('uncertainty_note', ''),
        },
    }
