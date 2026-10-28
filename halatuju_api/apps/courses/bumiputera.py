"""⚠ THE BUMIPUTERA ANSWER — COURSE GUIDE ONLY (Bumi coverage Sprint B, owner ruling 2026-10-28).

`StudentProfile.bumiputera` is the student's own answer, used for ONE thing: showing Bumiputera-only
courses (UiTM, MARA — `StpmRequirement.req_bumiputera`) to a Malaysian who said yes. It must NEVER
reach the scholarship engine or apps, sponsor views, reports, the partner/admin student detail or
the partner CSV export — that is what keeps the s44(6) "we do not collect ethnicity" stance true
for the bursary (docs/decisions.md). Guard tests that FAIL if it leaks:
`apps/courses/tests/test_bumiputera.py`, `apps/scholarship/tests/test_bumiputera_blind.py`,
`apps/reports/tests/test_views.py`.

Every rule about it lives here, so the readers (STPM eligibility, both course searches) and the
writers (profile PUT and sync) cannot drift apart:
  * a foreign student is never Bumiputera;
  * NULL (not answered) and anything that is not a clear yes read as "no".
"""
from .serializers import normalize_nationality

_TRUTHY = {'1', 'true', 'yes', 'y', 'on'}


def is_malaysian(nationality):
    """True only for a Malaysian nationality, in any of the spellings the profile and web send."""
    return normalize_nationality(nationality) == 'Warganegara'


def resolve_bumiputera(value, nationality='Warganegara'):
    """THE ONE READ RULE: True only for a yes (a real True, or a truthy query-string spelling)
    from a Malaysian. None / absent / anything else is False; a foreign student is always False."""
    if isinstance(value, bool):
        yes = value
    elif isinstance(value, str):
        yes = value.strip().lower() in _TRUTHY
    else:
        yes = False
    return yes and is_malaysian(nationality)


def search_bumiputera(query_params):
    """Does this course search come from a Bumiputera student? ONE reader for both searches
    (`CourseSearchView`, `StpmSearchView`): the web sends `?bumiputera=1` only for a Malaysian
    who said yes; an optional non-Malaysian `nationality` forces "no". Absent = not Bumi."""
    return resolve_bumiputera(query_params.get('bumiputera'),
                              query_params.get('nationality') or 'Warganegara')


def foreign_never_bumi(profile, validated):
    """THE ONE WRITE RULE, for `serializer.save(**…)` in the profile PUT and sync: when the
    nationality on file AFTER this write is not Malaysian, store NULL — whatever was sent, and
    also when only the nationality changed (a switch to Foreign wipes a stored yes)."""
    nationality = validated.get('nationality', profile.nationality)
    if is_malaysian(nationality):
        return {}
    if 'bumiputera' in validated or 'nationality' in validated or profile.bumiputera is not None:
        return {'bumiputera': None}
    return {}


def nationality_payload(profile):
    """The nationality and the Bumiputera answer that hangs off it, for the student's OWN profile
    read (`ProfileView.get`) — never a staff, sponsor or partner payload."""
    return {'nationality': profile.nationality, 'bumiputera': profile.bumiputera}
