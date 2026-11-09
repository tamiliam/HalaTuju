"""Sprint S1 (owner 2026-11-09): the access-matrix cells the Scholars key moves, for `test_team_tables_matrix.py`.

Kept here so the matrix file (near its 600-line mark) does not grow. Brief
`docs/plans/2026-11-09-s1-scholars-access.md`; decisions.md "S1".

S1-c: the Scholars door is its own key, `scholars`. `review`, `qc` and `see_all` alone no longer open it, so
every shape that read the list by one of those (the qc and reviewer presets, a finance row holding `review`,
a reviewer holding `payments_check`, a reviewer who also mentors) is now refused at the door: 403 on the
list, the file, every tab and every write. The one exception is the mentoring ACTION route: the probe's
action is `x`, which the view answers 404 before it asks who is knocking, exactly as before.

S1-g: the saved rows holding `see_all` gain `scholars` in the data migration, so the matrix's shapes that
hold `see_all` are written in their post-migration state (`SHAPES`) and none of their cells moves. The
admin preset (S1-a) holds it, so the `admin` label's shapes move nowhere either.

The web menu half (`MenuAndEndpointAgree`) hides the Scholars row from exactly the same shapes
(`teamTablesMatrix.test.ts`, `s1Moves.ts`).
"""

SCHOLARS_PREFIX = 'api/v1/admin/scholarship/scholars/'
#: The action route answers an unknown action (the probe's `x`) 404 before its door.
S1_ACTION_ROUTE = 'POST api/v1/admin/scholarship/scholars/<int:pk>/mentoring/<str:action>/'
#: The shapes the Scholars door now refuses (S1-c).
S1_SHUT = ('qc', 'reviewer', 'finance_custom', 'reviewer_payments_check', 'reviewer_mentor')
S1_WEB_PAGE = '/admin/scholars'


def s1_moved_cells(shape, before):
    """`{probe: status}` S1 moves for `shape`, from its BEFORE row (`before`)."""
    if shape not in S1_SHUT:
        return {}
    return {p: (404 if p == S1_ACTION_ROUTE else 403)
            for p in before if p.split(' ', 1)[1].startswith(SCHOLARS_PREFIX)}


def s1_web_shown(shape, href, shown):
    """Whether the console offers `href` to `shape` after S1 (the Scholars row is shut exactly where the
    endpoint is)."""
    return False if href == S1_WEB_PAGE and shape in S1_SHUT else shown
