"""
Saving the deeper application detail the student edits after shortlisting.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from ..models import FundingNeed


_DEEPER_FIELDS = (
    'aspirations', 'plans', 'fears', 'justification',
    # "Your story" guided narrative fields (S2 redesign)
    'first_in_family', 'parents_occupation',
    # TD-061: siblings_studying boolean dropped; only the count remains (S15).
    'siblings_studying_count',
    'family_context', 'daily_life',
    # Income Check-1 wizard answers (Documents → Household income).
    'income_route', 'income_earner', 'income_working_members', 'income_declared',
    'income_nonearning', 'earner_work_status',
    'household_other_earners', 'siblings_in_school', 'siblings_in_tertiary',
    # Structured family roster (redesign 2026-06) — the new inputs. first_in_family
    # + parents_occupation above are DERIVED from these on save (see below).
    'father_name', 'father_occupation', 'father_occupation_other',
    'mother_name', 'mother_occupation', 'mother_occupation_other',
    'other_family_members',
)


_PROFILE_ADDRESS_FIELDS = ('address', 'postal_code', 'city')


def save_application_details(application, data):
    """Persist deeper-info fields, upsert funding-need, and sync address to profile.

    Address lives on the student profile (alongside preferred_state set during
    /apply), not on the application. The Story tab on /scholarship/application
    sends it here so the student saves everything with one button.
    """
    from .. import family
    deeper = {k: data[k] for k in _DEEPER_FIELDS if k in data}
    # Normalise the optional member pool to a safe shape before persisting.
    if 'other_family_members' in deeper:
        deeper['other_family_members'] = family.clean_other_members(deeper['other_family_members'])
    if deeper:
        for k, v in deeper.items():
            setattr(application, k, v)
        # The structured roster is now the INPUT; keep the two legacy columns
        # (first_in_family, parents_occupation) in sync as OUTPUTS so every
        # downstream reader (profile_engine, anomaly_engine, ledger) works unchanged.
        # Only takes over once the student has entered structured data — grandfathered
        # apps keep their existing free text / toggle until they re-enter.
        derived = []
        if family.has_structured_roster(application):
            application.first_in_family = family.derive_first_in_family(application)
            derived.append('first_in_family')
            summary = family.parents_occupation_summary(application)
            if summary:
                application.parents_occupation = summary
                derived.append('parents_occupation')
        update_fields = list(dict.fromkeys(list(deeper.keys()) + derived)) + ['updated_at']
        application.save(update_fields=update_fields)
        # Mirror the roster back to the profile (the durable home) while the application
        # is still open, so /profile and the Story editor stay identical. Once the
        # application is decided its copy freezes and the profile is decoupled.
        if (application.profile
                and application.status not in family.DECIDED_STATUSES
                and any(k in deeper for k in family.PROFILE_FAMILY_FIELDS)):
            family.copy_family_roster(application, application.profile)
            application.profile.save(update_fields=list(family.PROFILE_FAMILY_FIELDS))
    fn_data = data.get('funding_need')
    if fn_data is not None:
        FundingNeed.objects.update_or_create(application=application, defaults=fn_data)
    addr = {k: data[k] for k in _PROFILE_ADDRESS_FIELDS if k in data}
    if addr and application.profile:
        for k, v in addr.items():
            setattr(application.profile, k, v)
        application.profile.save(update_fields=list(addr.keys()))
    return application
