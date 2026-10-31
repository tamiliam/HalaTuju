"""Who must give a phone, who may share it with students, and who sees it (common profile S2).

ONE home for the rules the profile endpoints share (`views_admin/me.py`, `views_admin/reviewers.py`):

- `reviews_cases(admin)` — the reviewer cards' rule on the server (`lib/profileCards.ts`
  `reviewsCases`): holds `review` and is not a super. Such a person MUST keep a phone (the onboarding
  rule) and is the only one who may set "share my phone with students I interview".
- `phone_refusal(admin, data)` — the blank-phone refusal, applied by BOTH writers of the phone while
  the old web (which still saves the phone through `admin/reviewer-profile/`) may be serving.
- `new_profile_defaults(admin)` — what a profile row starts with when it is CREATED: "share with
  students" is on only for somebody who can be shown the switch (review fix L2).
- `assigner_sees_phone(target, profile)` — the reviewer DETAIL serves a phone only when the person
  can be assigned cases (`review`: the person handing out work must reach them, owner 2026-08-02)
  or chose "show my phone to my team" (review fix M1).
"""
from rest_framework import status
from rest_framework.response import Response


def reviews_cases(admin):
    return admin is not None and not admin.is_super and admin.has_perm('review')


def phone_refusal(admin, data):
    """A 400 `phone_required` when a `review` holder sends a blank phone, else None."""
    if 'phone' in data and not str(data.get('phone') or '').strip() and reviews_cases(admin):
        return Response({'error': 'phone_required', 'code': 'phone_required'},
                        status=status.HTTP_400_BAD_REQUEST)
    return None


def new_profile_defaults(admin):
    return {'share_phone_with_students': reviews_cases(admin)}


def assigner_sees_phone(target, profile):
    if profile is None:
        return False
    return bool(profile.share_phone_with_team) or (not target.is_super and target.has_perm('review'))
