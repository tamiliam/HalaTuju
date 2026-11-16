"""Sprints THANKS and THANKS-SCHOLARS: the access-matrix cells the graduation thank-you moves, for
`test_team_tables_matrix.py`. Kept here so the matrix file does not grow.

THANKS (owner 2026-11-16, morning) put the thank-you on the case page under the `review` key. The same day
the owner ruled again: "Thank yous are part of the scholar maintenance process." So THANKS-SCHOLARS moved
both routes to the SCHOLAR FILE and its rules (`views_admin/scholar_thanks.py`, `_ScholarsBase`):

- the old moderation POST (`admin/graduation-messages/<pk>/review/`) is RETIRED; its BEFORE cell is dropped
  (`THANKS_OLD_POST`, listed in the matrix's `RETIRED_CELLS`). The case page's read never had a BEFORE cell.
- the new read (`scholars/<pk>/graduation-messages/`) goes through `_file_for` first, exactly as the file's
  own GET does, so every shape answers what it answers on the file GET after S1.
- the new decide POST (`scholars/<pk>/graduation-messages/<message_id>/review/`) goes through `_file_for`
  first, exactly as the result-review POST does, so every shape answers what it answers there after S1.
The probe names the matrix's application, which has NO file, so a `scholars` holder gets 404 and everybody
else 403 (a mentor login 403 at `get_admin`); a reviewer holding `review` alone gains nothing.
"""
from apps.scholarship.tests.team_matrix_s1 import s1_moved_cells

THANKS_OLD_POST = 'POST api/v1/admin/graduation-messages/<int:pk>/review/'
THANKS_GET = 'GET api/v1/admin/scholarship/scholars/<int:pk>/graduation-messages/'
THANKS_POST = 'POST api/v1/admin/scholarship/scholars/<int:pk>/graduation-messages/<int:message_id>/review/'
#: The scholar-file cells each new route answers like (after S1).
THANKS_GET_SAME_AS = 'GET api/v1/admin/scholarship/scholars/<int:pk>/'
THANKS_POST_SAME_AS = 'POST api/v1/admin/scholarship/scholars/<int:pk>/results/<int:result_id>/review/'


def thanks_cells(shape, before):
    """The cells THANKS-SCHOLARS adds for one shape: the scholar file's own answers."""
    after = {**before, **s1_moved_cells(shape, before)}
    return {THANKS_GET: after[THANKS_GET_SAME_AS], THANKS_POST: after[THANKS_POST_SAME_AS]}
