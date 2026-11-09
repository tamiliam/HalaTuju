"""Sprint T3 (2026-11-09): ONE person page for every team member — the fields every person payload shares.

The three person pages (Team -> a reviewer, an admin, a mentor) are fed by three existing detail views
(`AdminReviewerDetailView`, `AdminStaffPermissionsView`, `AdminMentorView`). Each now carries the same
`person` block, built here, so the page's header (the table chips, Joined, Last seen) and its Profile
tab read one shape whichever door the viewer came in by.

⚠ AN ALLOWLIST, and a deliberate PII WIDENING on the admin and mentor details (recorded in
`docs/scholarship/role-matrix.md`): the SAME fields, under the SAME rules, the reviewer detail already
served. The home address (`address`, `street_address`, `postcode`, `city`, `state`) is NEVER served.
The phone only under the rule each screen already used:
  * a mentor's own login — their number, which the inviting organisation sees
    (`staff_contact.staff_screen_phone`, S7a);
  * anybody else — `staff_contact.assigner_sees_phone` (they show it to the team, or hold `review`).

⚠ NEVER CREATES A PROFILE ROW. An admin or finance person without `review` has no `ReviewerProfile`
until they save one on their own profile page; a GET that wrote one would be a side effect of looking.
`profile` then reads as all-empty, and the screen says "Not given".

Reads only what the caller has already loaded: `target.reviewer_profile` (select it, or pass ``rp``)
and the mentor link (`staff_tables.in_mentors` reads `target.mentor`).
"""
from apps.courses import staff_permissions as sp
from apps.courses import staff_tables

from .staff_contact import assigner_sees_phone, staff_screen_phone

#: Conversational or better — the reviewer detail's own "speaks this" rule (`_REVIEW_FLUENCY`).
SPOKEN = ('conversational', 'fluent')

#: The exact keys of `person` and of its `profile`. An exact-key-set test pins both, so a new field is a
#: decision.
PERSON_KEYS = ('admin_id', 'mentor_id', 'name', 'email', 'tables', 'lead', 'mentor_only', 'is_active',
               'paused', 'joined_at', 'signed_in', 'last_seen_at', 'profile')
#: The exact keys of `profile`.
PROFILE_KEYS = ('job_title', 'about', 'qualification', 'university', 'graduation_year',
                'field_of_study', 'phone', 'languages', 'other_language')


def _profile_of(target):
    # RelatedObjectDoesNotExist is an AttributeError: nobody has saved a profile yet.
    return getattr(target, 'reviewer_profile', None)


def phone_of(target, rp):
    """The phone this person's page may show, or ''."""
    if rp is None:
        return ''
    if target.is_mentor:
        return staff_screen_phone(target, rp)
    return (rp.phone or '') if assigner_sees_phone(target, rp) else ''


def profile(target, rp=None):
    """The Profile tab's fields (`PROFILE_KEYS`); '' / None / [] for what the person has not filled in."""
    rp = rp if rp is not None else _profile_of(target)
    return {
        'job_title': getattr(rp, 'job_title', '') or '',
        'about': getattr(rp, 'about', '') or '',
        'qualification': getattr(rp, 'highest_qualification', '') or '',
        'university': getattr(rp, 'university', '') or '',
        'graduation_year': getattr(rp, 'graduation_year', None),
        'field_of_study': getattr(rp, 'field_of_study', '') or '',
        'phone': phone_of(target, rp),
        'languages': [code for code, lvl in (
            ('en', getattr(rp, 'english_fluency', '')), ('ms', getattr(rp, 'bm_fluency', '')),
            ('ta', getattr(rp, 'tamil_fluency', ''))) if lvl in SPOKEN],
        'other_language': rp.spoken_other_language() if rp is not None else '',
    }


def person(target, rp=None):
    """The header and Profile tab of `target`'s page (`PERSON_KEYS`). `mentor_id` is set only while they
    mentor (the Mentors table's link); `mentor_only` is a mentor's own login (no staff role, so no
    permissions to change); `signed_in` is False only when the console never recorded a visit (NULL is
    "not recorded"). Name and email are what each of the three payloads already serves this viewer."""
    return {
        'admin_id': target.pk,
        'mentor_id': target.mentor_id if staff_tables.in_mentors(target) else None,
        'name': target.name,
        'email': target.email,
        'tables': list(staff_tables.tables(target)),
        'lead': sp.is_lead_tier(target),
        'mentor_only': target.is_mentor,
        'is_active': target.is_active,
        'paused': target.is_paused,
        'joined_at': target.created_at,
        'signed_in': target.first_seen_at is not None,
        'last_seen_at': target.last_seen_at,
        'profile': profile(target, rp),
    }
