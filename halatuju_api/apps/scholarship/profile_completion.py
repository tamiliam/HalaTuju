"""How complete a staff member's own profile is — the ONE rule (staff nudges Phase A, 2026-11-08).

Owner-settled (brief `docs/plans/2026-11-08-staff-nudges.md`, decisions 1-3). Served on
`GET admin/me/` as `completion`; the Profile page's completion card and the console's profile banner
read it and keep no copy of the rule.

WHO: every account from the organisation admin down — org_admin, admin, finance, reviewer, qc,
mentor, partner, source_partner. **Never a super** (`completion(...)` answers None for one).

WHAT COUNTS, equal weight, only what the person's profile asks of them (the Profile page's card
rules, `lib/profileCards.ts` `cardsFor`, whose server twins live in `staff_contact.py`):

- everyone — `photo`, `name`, `job_title`, `about`, `phone`;
- somebody who works with students (`staff_contact.works_with_students`: a `review` holder or a
  mentor) — also `qualifications` (the Reviewer-hold set as ONE item: qualification, university,
  graduation year, field of study — `reviewer_onboarding`), `language` (English, BM or Tamil at
  conversational or better, the hold's own rule) and `address` (street, postcode, city and state);
- a mentor (a mentor login, or a staff member who mentors now) — also `mentoring_area`.

The optional extras (the fourth language, the share-my-phone switches) never count.

IMPORTANT (the banner's list): `photo` and `phone`, plus `mentoring_area` for a mentor. The address
never (it is private); the Reviewer-hold fields never (the hold already enforces them).

Shape: `{items: [{key, done}], done, total, percent, important_missing: [key]}` — `items` in the
page's order, `percent` rounded DOWN so 100 means every item is done.
"""
from .reviewer_onboarding import LANG_FIELDS, REQUIRED_TEXT_FIELDS, SPEAKS
from .staff_contact import works_with_students

#: The banner's fields, in the order its sentence names them.
IMPORTANT = ('photo', 'phone', 'mentoring_area')
#: The address is done when all four parts are filled.
ADDRESS_FIELDS = ('street_address', 'postcode', 'city', 'state')
#: The qualification half of the Reviewer-hold set (its phone is the card's own item here).
QUALIFICATION_FIELDS = tuple(f for f in REQUIRED_TEXT_FIELDS if f != 'phone')


def _filled(profile, field):
    return bool((getattr(profile, field, '') or '').strip()) if profile is not None else False


def _qualifications(profile):
    return (profile is not None and bool(profile.graduation_year)
            and all(_filled(profile, f) for f in QUALIFICATION_FIELDS))


def _language(profile):
    return profile is not None and any(getattr(profile, f, '') in SPEAKS for f in LANG_FIELDS)


def item_keys(admin):
    """The keys this person's profile asks of them, in page order; () for a super or nobody."""
    if admin is None or admin.is_super:
        return ()
    keys = ['photo', 'name', 'job_title', 'about', 'phone']
    if works_with_students(admin):
        keys += ['qualifications', 'language', 'address']
    if admin.is_mentor or admin.mentors_now:
        keys.append('mentoring_area')
    return tuple(keys)


def completion(admin, profile, mentoring_area=''):
    """The served answer (see the module docstring), or None for a super.

    `profile` is the person's `StaffProfile` row or None (nothing filled yet); `mentoring_area` the
    mentor's own `Mentor.area` ('' for everybody else) — both already read by the caller, so this
    asks the database nothing."""
    keys = item_keys(admin)
    if not keys:
        return None
    done_of = {
        'photo': lambda: _filled(profile, 'photo_path'),
        'name': lambda: bool((admin.name or '').strip()),
        'job_title': lambda: _filled(profile, 'job_title'),
        'about': lambda: _filled(profile, 'about'),
        'phone': lambda: _filled(profile, 'phone'),
        'qualifications': lambda: _qualifications(profile),
        'language': lambda: _language(profile),
        'address': lambda: all(_filled(profile, f) for f in ADDRESS_FIELDS),
        'mentoring_area': lambda: bool((mentoring_area or '').strip()),
    }
    items = [{'key': k, 'done': done_of[k]()} for k in keys]
    done = sum(1 for i in items if i['done'])
    missing = {i['key'] for i in items if not i['done']}
    return {
        'items': items,
        'done': done,
        'total': len(items),
        'percent': done * 100 // len(items),
        'important_missing': [k for k in IMPORTANT if k in missing],
    }
