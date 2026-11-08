"""Test helpers for the A1.13b award withdrawal (maker and checker). Not a test module: dummy staff only.

`maker_in(org)` / `checker_in(org)` make SIGNED-IN staff of the organisation in each seat (the maker an
`admin` team member given `award_withdraw_request` by hand — no preset holds it; the checker the
organisation admin, whose fixed lead tier holds `award_withdraw_approve`). `withdraw_now(app)` runs the
whole chain — request, then approval by a different person — where an older test withdrew in one call.
"""
from django.utils import timezone

from apps.scholarship import award_withdrawal_chain as chain
from apps.scholarship.tests.factories import make_admin

EXPLANATION = 'Zxq internal explanation: the offer letter was found to be for a different course.'
MAKER_KEYS = ['see_all', 'spending', 'payments_prepare', 'award_withdraw_request']


def maker_in(org, **kw):
    kw.setdefault('permissions', list(MAKER_KEYS))
    kw.setdefault('first_seen_at', timezone.now())
    return make_admin('admin', owning_org=org, **kw)


def checker_in(org, **kw):
    kw.setdefault('first_seen_at', timezone.now())
    return make_admin('org_admin', owning_org=org, **kw)


def withdraw_now(app, *, maker=None, checker=None, explanation=EXPLANATION, note=''):
    """Request and approve ``app``'s withdrawal; returns the approved request row. Run it inside
    ``captureOnCommitCallbacks`` when the emails matter. A case with no owning organisation (an older
    fixture) is given a new one first: both seats belong to an organisation."""
    if app.owning_organisation_id is None:
        from apps.scholarship.models import ScholarshipApplication
        from apps.scholarship.tests.factories import make_org
        ScholarshipApplication.objects.filter(pk=app.pk).update(owning_organisation=make_org())
        app.refresh_from_db()
    org = app.owning_organisation
    maker = maker or maker_in(org)
    checker = checker or checker_in(org)
    row = chain.request_withdrawal(app, by_admin=maker, explanation=explanation)
    row = chain.approve_withdrawal(row.pk, by_admin=checker, note=note)
    app.refresh_from_db()           # the caller's copy reads the withdrawn case, as the old one-step call left it
    return row
