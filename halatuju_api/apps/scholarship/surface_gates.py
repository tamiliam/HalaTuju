"""Who may OPEN each admin surface — one predicate per surface, shared by the surface's own view and
by the activity reader (common profile S4 review, M3, 2026-10-31).

Before this, each gate was written inline in its view, so the activity list (`staff_activity_read`)
could only COPY it, and a copy is a second rule that drifts: an org_admin demoted to reviewer kept
reading a benefactor's name on their activity list after `admin/sponsors/` had started answering 403.
Now the view and the reader ask the same function, so the label disappears the moment the screen
does. Each predicate takes a `PartnerAdmin` and answers a bool; the views keep their own 404-vs-403
choice around it.
"""
from django.conf import settings


def may_read_sponsors(admin):
    """The Sponsors list (`AdminSponsorListView`): super / org_admin / Admin-General / finance —
    finance READ-ONLY (role matrix 2026-07-23); qc and reviewer are refused."""
    return admin is not None and (admin.is_super or admin.role in ('org_admin', 'admin', 'finance'))


def may_read_team(admin):
    """The organisation's People / Reviewers / Invitations screens (`_ReviewersBase._side`)."""
    return admin is not None and (admin.is_super or admin.role in ('org_admin', 'admin', 'finance'))


def billing_live():
    """`BILLING_USAGE_ENABLED`: a non-super sees no billing surface (dark 404) while it is off."""
    return bool(getattr(settings, 'BILLING_USAGE_ENABLED', False))


def may_read_invoices(admin):
    """The invoices screen (`_InvoiceBase._caller`): a super, or an org_admin while billing is live."""
    if admin is None:
        return False
    return bool(admin.is_super or (billing_live() and admin.role == 'org_admin'))


def may_open_contracts(admin):
    """The contract templates (`_ContractsBase._contract_admin`): a super or an org_admin."""
    return admin is not None and (admin.is_super or admin.role == 'org_admin')


def requests_live():
    """`REQUESTS_ENABLED`: the Requests space answers 404 to everybody while it is off."""
    return bool(getattr(settings, 'REQUESTS_ENABLED', False))


def requests_role(admin):
    """The roles that OPEN the Requests area (`_OrgRequestsBase._org_side`): org_admin or super."""
    return admin is not None and (admin.is_super or admin.role == 'org_admin')
