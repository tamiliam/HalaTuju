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

from apps.courses import staff_tables


def may_read_sponsors(admin):
    """The Sponsors list (`AdminSponsorListView`), the sponsor detail and the sponsorships list: the v2
    key `sponsors.view` (Team tables T5c). Its holders are T1's: super / org_admin / Admin-General /
    finance — finance READ-ONLY (role matrix 2026-07-23) — and a person at the ADMINS table by an admin
    key; qc and reviewer are refused."""
    return staff_tables.opens_door(admin, 'sponsors_read')


def may_read_team(admin):
    """The organisation's People / Reviewers / Invitations screens (`_ReviewersBase._side`): the v2 keys
    `team.view` AND `invitations.view` (Team tables T5c — one door serves both pages, so it asks both).
    Holders as T1: super / org_admin / admin / finance, or the ADMINS table by an admin key."""
    return staff_tables.opens_door(admin, 'team_read')


def billing_live():
    """`BILLING_USAGE_ENABLED`: a non-super sees no billing surface (dark 404) while it is off."""
    return bool(getattr(settings, 'BILLING_USAGE_ENABLED', False))


def may_read_invoices(admin):
    """The invoices screen (`_InvoiceBase._caller`): `billing.view` (M3b G7), while billing is live for
    anyone but a super (a super reads it always). Holders: a super, an organisation admin."""
    if admin is None:
        return False
    return bool(admin.is_super or (billing_live() and staff_tables.opens_door(admin, 'billing_read')))


def may_read_billing(admin):
    """The usage and build-hours reads (`AdminBillingUsageView`, `AdminOrgBuildHoursView.get`):
    `billing.view` (M3b G7). Paying the bill is `billing.edit` (O15), and no endpoint pays yet."""
    return staff_tables.opens_door(admin, 'billing_read')


def may_open_contracts(admin):
    """READ the contract templates (`_ContractsBase`, a GET): `contracts.view` (M3b G9)."""
    return staff_tables.opens_door(admin, 'contracts_read')


def may_write_contracts(admin):
    """WRITE a contract template (`_ContractsBase`, any other method): `contracts.edit` (M3b G9).
    Deploying a template stays super only (OVERRIDE, in its view)."""
    return staff_tables.opens_door(admin, 'contracts_write')


def may_edit_settings(admin):
    """The organisation's settings, theme and Overview layout: `settings.edit` (M3b G3)."""
    return staff_tables.opens_door(admin, 'settings')


def may_edit_programmes(admin):
    """A gift's settings (programme configuration, the gift-scoped pages): `programmes.edit` (M3b G4)."""
    return staff_tables.opens_door(admin, 'programme_settings')


def may_edit_invitations(admin):
    """Send or cancel an invitation (`views_admin/invitations.py`): `invitations.edit` (M3b G2)."""
    return staff_tables.opens_door(admin, 'invitations')


def may_assign(admin):
    """Give a case to a reviewer (`AdminAssignReviewerView`, `assignment.may_hand_to`): `students.edit`
    (M3b G5). Never to yourself (E3): that is the hand-off rule's, not this door's."""
    return staff_tables.opens_door(admin, 'assign')


def may_work_students(admin):
    """Nudge a student, the parent-call filter, correct a guardian, write notes for the reviewer:
    `students.edit` (M3b G5)."""
    return staff_tables.opens_door(admin, 'students_write')


def may_decide(admin):
    """Drop a shortlisted applicant, close an application before award: `students.approve` (M3b G5)."""
    return staff_tables.opens_door(admin, 'decide')


def may_vet_sponsors(admin):
    """Vet a sponsor account, accept a sponsor into a gift, publish sponsor terms: `sponsors.approve`
    (M3b G6). Vetting a sponsor ACCOUNT reaches every organisation (owner decision D6)."""
    return staff_tables.opens_door(admin, 'sponsor_vet')


def requests_live():
    """`REQUESTS_ENABLED`: the Requests space answers 404 to everybody while it is off."""
    return bool(getattr(settings, 'REQUESTS_ENABLED', False))


def requests_role(admin):
    """READ the Requests area (`_OrgRequestsBase._org_side`, the pending card, the activity list):
    `requests.view` (M3b G8). Holders: a super, an organisation admin."""
    return staff_tables.opens_door(admin, 'requests_read')


def may_write_requests(admin):
    """Raise a request, answer, defer or modify a quote, comment, attach: `requests.edit` (M3b G8)."""
    return staff_tables.opens_door(admin, 'requests_write')


def may_decide_requests(admin):
    """Approve or decline a quote: `requests.approve` (O15: an organisation admin holds it by role;
    M3b G8)."""
    return staff_tables.opens_door(admin, 'requests_decide')
