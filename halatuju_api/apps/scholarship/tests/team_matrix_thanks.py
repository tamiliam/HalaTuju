"""Sprint THANKS (owner 2026-11-16): the access-matrix cells the graduation thank-you moves, for
`test_team_tables_matrix.py`. Kept here so the matrix file does not grow.

The owner's ruling: whoever holds the `review` KEY approves or rejects a thank-you, from the student's case
page; the role is only a label. So:

- the moderation POST (`admin/graduation-messages/<pk>/review/`) asks the `review` key, not the reviewer
  label, then puts the message's CASE through the case read fence (review round). The probe names message
  999999, so a key holder gets 404 and everybody else 403. 404 is also the answer OUTSIDE the case fence on a
  real message (an unassigned reviewer; a finance row given `review`, whose reach is assigned-only), so the
  404 here says only "past the key", never "may decide this message". The reviewer-labelled shapes all hold
  `review` and move nowhere. ONE cell moves: `finance_custom` (a custom set with `review`) now passes the key
  (403 -> 404); on a real message it decides only for a case assigned to it. Nobody gains a message.
- the case page's new read (`applications/<pk>/graduation-messages/`) is a NEW route, so NEW cells. It asks
  the `review` key, then the applicant-detail GET's own fence (`_scoped_application`). A key holder reads
  exactly what they read on the case page; everybody else is 403.
"""

THANKS_POST = 'POST api/v1/admin/graduation-messages/<int:pk>/review/'
THANKS_GET = 'GET api/v1/admin/scholarship/applications/<int:pk>/graduation-messages/'
THANKS_SAME_AS = 'GET api/v1/admin/scholarship/applications/<int:pk>/'
#: The matrix shapes holding `review` (a super holds every key; the reviewer preset holds it).
REVIEW_HOLDERS = ('super', 'reviewer', 'reviewer_admin_keys', 'reviewer_admin_keys_other_org', 'reviewer_mentor',
                  'reviewer_payments_check', 'finance_custom')
#: The one moved POST cell: `(before, after)`.
THANKS_POST_MOVED = {'finance_custom': (403, 404)}


def thanks_cells(shape, before):
    """The cells THANKS adds (the GET) and moves (the POST) for one shape."""
    cells = {THANKS_GET: before[THANKS_SAME_AS] if shape in REVIEW_HOLDERS else 403}
    if shape in THANKS_POST_MOVED:
        was, now = THANKS_POST_MOVED[shape]
        assert before[THANKS_POST] == was, f'{shape}: the declared THANKS BEFORE is wrong'
        cells[THANKS_POST] = now
    return cells
