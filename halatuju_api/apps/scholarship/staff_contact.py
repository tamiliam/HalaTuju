"""Who must give a phone, who may share it with students, and who sees it (common profile S2).

ONE home for the rules the profile endpoints share (`views_admin/me.py`, `views_admin/reviewers.py`):

- `reviews_cases(admin)` — the reviewer cards' rule on the server (`lib/profileCards.ts`
  `reviewsCases`): holds `review` and is not a super. Such a person MUST keep a phone (the onboarding
  rule) and is the only one who may set "share my phone with students I interview".
- `works_with_students(admin)` — `reviews_cases`, or a MENTOR (student maintenance S7a, 2026-10-31),
  or — S7d, 2026-11-01 — a STAFF member who mentors NOW (`PartnerAdmin.mentors_now`: an active mentor
  record; a staff member who stopped mentoring drops back to their staff rule). THE rule for the phone being required, for "share my phone with students" and for the reviewer
  cards a mentor also fills in (qualifications, languages, address — `ReviewerProfileView`). The web
  twin is `lib/profileCards.ts` `worksWithStudents`.
- `phone_refusal(admin, data)` — the blank-phone refusal of `admin/me/`, the phone's ONE writer since
  TD-439 (`admin/reviewer-profile/` serves the phone but no longer writes it).
- `new_profile_defaults(admin)` — what a profile row starts with when it is CREATED: "share with
  students" is on only for somebody who can be shown the switch (review fix L2) — and NOT for a staff
  member who also mentors (S7d owner ruling: they gave the number for staff use; it starts OFF, as the
  Add sets an existing profile's, `staff_mentor.add`). A pure mentor keeps 7a's ON default.
- `assigner_sees_phone(target, profile)` — the reviewer DETAIL serves a phone only when the person
  can be assigned cases (`review`: the person handing out work must reach them, owner 2026-08-02)
  or chose "show my phone to my team" (review fix M1).
"""
from rest_framework import status
from rest_framework.response import Response


def reviews_cases(admin):
    return admin is not None and not admin.is_super and admin.has_perm('review')


def works_with_students(admin):
    """A `review` holder (not a super), a mentor, or a staff member who mentors now (S7d): somebody
    students meet. See the module docstring."""
    return reviews_cases(admin) or (admin is not None and (admin.is_mentor or admin.mentors_now))


def phone_refusal(admin, data):
    """A 400 `phone_required` when somebody who works with students sends a blank phone, else None."""
    if 'phone' in data and not str(data.get('phone') or '').strip() and works_with_students(admin):
        return Response({'error': 'phone_required', 'code': 'phone_required'},
                        status=status.HTTP_400_BAD_REQUEST)
    return None


def new_profile_defaults(admin):
    return {'share_phone_with_students': reviews_cases(admin) or (admin is not None and admin.is_mentor)}


def assigner_sees_phone(target, profile):
    if profile is None:
        return False
    return bool(profile.share_phone_with_team) or (not target.is_super and target.has_perm('review'))
