"""T5c P3 - `role` is only a display name: the inventory guard.

Scans `apps/` (not tests, not migrations) for every place that reads a staff role label to decide something:
a comparison (`x.role ==`, `!=`, `in`, `not in`, a bare `role ==`), a queryset filter (`role=`, `role__in=` on
`filter` / `exclude` / `get` / `Q`), or `has_role(...)`. Each site must sit in an explicit allowlist, by module +
function, with a class and an owner. A NEW label gate (or a leftover after a conversion) fails here, so access
decisions move to the v2 keys (`staff_tables.opens`) and the label stays a display name.

Classes:
  DISPLAY       the label is shown, serialised, or used as the account's KIND (which table / which sign-in), not to
                grant or refuse an action.
  OVERRIDE      the super / org_admin owner override (the lead tier holds every key by design).
  GATE-LEFT     an access decision still made by a label, with the TD or sprint that owns converting it.
  GATE-UNPLANNED  a label gate with no owner (none found in P3).
Adding a site: classify it, name its owner, and add it below; do NOT add a GATE-UNPLANNED without a TD.
"""
import ast
import os

APPS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

#: Family-member roles (guardian, brother, ...) and invitation kinds: not a staff label.
NOT_STAFF_ROLE_FILES = {
    'scholarship/family.py', 'scholarship/income_engine/epf_evidence.py', 'scholarship/income_engine/gaps.py',
    'scholarship/emails/reviewer_mail.py',
}
QUERY_FUNCS = {'filter', 'exclude', 'get', 'Q'}
CLASSES = {'DISPLAY', 'OVERRIDE', 'GATE-LEFT', 'GATE-UNPLANNED'}


def _is_role(node):
    if (isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'getattr' and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant) and node.args[1].value == 'role'):
        return True  # getattr(x, 'role', default) is a role read too
    return ((isinstance(node, ast.Attribute) and node.attr == 'role')
            or (isinstance(node, ast.Name) and node.id == 'role'))


class _Scan(ast.NodeVisitor):
    def __init__(self, rel):
        self.rel, self.stack, self.found = rel, [], []

    def _scoped(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_ClassDef = visit_FunctionDef = visit_AsyncFunctionDef = _scoped

    def _hit(self, node):
        self.found.append((f"{self.rel}::{'.'.join(self.stack) or '<module>'}", node.lineno))

    def visit_Compare(self, node):
        ops = (ast.Eq, ast.NotEq, ast.In, ast.NotIn)
        if any(isinstance(o, ops) for o in node.ops) and any(_is_role(n) for n in [node.left, *node.comparators]):
            self._hit(node)
        self.generic_visit(node)

    def visit_Call(self, node):
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, 'id', '')
        if name in QUERY_FUNCS and any(k.arg in ('role', 'role__in') for k in node.keywords):
            self._hit(node)
        elif name == 'has_role':
            self._hit(node)
        self.generic_visit(node)


def scan(root=APPS):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in ('tests', 'migrations', '__pycache__')]
        for fn in fns:
            if not fn.endswith('.py') or fn.startswith('test_'):
                continue
            rel = os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, '/')
            if rel in NOT_STAFF_ROLE_FILES:
                continue
            with open(os.path.join(dp, fn), encoding='utf-8') as fh:
                v = _Scan(rel)
                v.visit(ast.parse(fh.read()))
            out.extend(v.found)
    return out


def site_counts(root=APPS):
    out = {}
    for key, _ in scan(root):
        out[key] = out.get(key, 0) + 1
    return out


#: module::function -> (class, owner, one-line reason)
ALLOWLIST = {
    'courses/models.py::PartnerOrganisationQuerySet.tenants': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/models_staff.py::PartnerAdmin.Meta': ('DISPLAY', 'account kind',
        'DB constraints: which kind may carry a source / mentor link'),
    'courses/models_staff.py::PartnerAdmin.is_mentor': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/models_staff.py::PartnerAdmin.is_source_user': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/models_staff.py::PartnerAdmin.is_staff_mentor': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/models_staff.py::PartnerAdmin.is_super': ('OVERRIDE', 'owner override',
        'the definition of a super (label or flag)'),
    'courses/models_staff.py::PartnerAdmin.mentors_now': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/models_staff.py::PartnerAdmin.source_binding_problem': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/referral_links.py::mark_refusal': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/staff_permissions.py::org_staff': ('DISPLAY', 'T5a catalogue',
        'the staff `holders` filters by key (A1.13b: moved out of holders); never a super'),
    'courses/staff_permissions.py::is_custom': ('DISPLAY', 'T5a catalogue',
        'preset vs custom set'),
    'courses/staff_permissions.py::is_lead_tier': ('OVERRIDE', 'owner override',
        'defines the lead tier'),
    'courses/staff_permissions.py::lead_reviews': ('OVERRIDE', 'owner override',
        'lead tier reviewing switch'),
    'courses/staff_permissions.py::preset_for': ('DISPLAY', 'T5a catalogue',
        'label -> preset keys (the label is the preset source)'),
    'courses/staff_permissions.py::resolve': ('DISPLAY', 'T5a catalogue',
        'label -> effective v1 keys'),
    'courses/staff_permissions.py::team_holding': ('DISPLAY', 'T5a catalogue',
        'queryset of staff holding a key; the label picks the preset half'),
    'courses/staff_permissions_v2.py::effective_v2': ('DISPLAY', 'T5a catalogue',
        'the v2 resolver reads the label for presets and the lead tier'),
    'courses/staff_delete_rules.py::_live_org_admin': ('GATE-LEFT', 'T5e',
        'T2 review N4: the sole-org-admin guard (lifted from AdminRevokeView, now Delete too); '
        'T5e moves lead powers to keys'),
    'courses/staff_delete_rules.py::_org_admins': ('GATE-LEFT', 'T5e',
        'T2 review N4: the active org admins of an organisation, counted (and locked) by the sole-org-admin '
        'guard; T5e moves lead powers to keys'),
    'courses/staff_delete_rules.py::sole_org_admin_ids': ('GATE-LEFT', 'T5e',
        'T2 review N4: the same guard for a whole table in one query; T5e moves lead powers to keys'),
    'courses/staff_gift.py::for_invite': ('DISPLAY', 'account kind',
        'TD-501 A1.3: the invited kind says which fields the invite asks for (a reviewer names a gift); '
        'it grants or refuses no action'),
    'courses/staff_gift.py::unchosen_rows': ('DISPLAY', 'account kind',
        'TD-501 A1.3: a read-only report lists the rows who review with no gift chosen (a super is left out)'),
    'courses/staff_gift.py::staff_invite_org': ('GATE-LEFT', 'T5e',
        'TD-501 A1.3 review: lifted verbatim from AdminInviteView.post - which organisation an '
        'org_admin or super staff invite binds to; T5e moves lead powers to keys'),
    'courses/staff_reinvite.py::bring_back': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/staff_tables.py::_team_member': ('DISPLAY', 'T5a tables',
        'table membership (which table a person is listed on)'),
    'courses/staff_tables.py::in_admins': ('DISPLAY', 'T5a tables',
        'table membership'),
    'courses/staff_tables.py::in_reviewers': ('DISPLAY', 'T5a tables',
        'table membership'),
    'courses/views_admin.py::PartnerAdminMixin.get_partner_students': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/views_admin.py::_deletable_now': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'courses/views_admin.py::_staff_target_manageable': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'courses/views_referral_partners.py::AdminReferralPartnerDetailView.patch': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/views_staff.py::AdminDeleteView._delete_locked': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'courses/views_staff.py::AdminDeleteView.delete': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'courses/views_staff.py::AdminInviteView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'courses/views_staff.py::AdminListView.get': ('DISPLAY', 'account kind',
        'the roster lists staff kinds'),
    'courses/views_staff.py::AdminResendView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'courses/views_staff.py::AdminRevokeView._revoke_locked': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'courses/views_staff.py::AdminRevokeView.patch': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'courses/views_staff.py::_listed_on_people': ('DISPLAY', 'T5a tables',
        'who is listed on People'),
    'scholarship/bursary.py::foundation_notify_emails': ('DISPLAY', 'account kind',
        'recipient routing: supers receive the notice'),
    'scholarship/emails/payment_mail.py::_instruction_cc': ('DISPLAY', 'account kind',
        'recipient routing: org admins are copied'),
    'scholarship/invitations.py::for_kind': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/invitations.py::kind_of': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/management/commands/backfill_invitations.py::Command.handle': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/management/commands/send_review_nudges.py::Command.handle.escalation_recipients': ('DISPLAY', 'account kind',
        'recipient routing: nudges escalate to the org admin'),
    'scholarship/mentor_invite.py::manageable': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/payments_chain.py::fallback_approvers': ('GATE-LEFT', 'T5d',
        'money: fallback approvers are org admins by label (payments fallback rule)'),
    'scholarship/programme_overview.py::may_customise': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/reviewer_onboarding.py::reviewer_profile_complete': ('DISPLAY', 'account kind',
        'first-login landing: the label says which kind of account this is, not what it may do'),
    'scholarship/scheduling.py::propose_slots': ('OVERRIDE', 'owner override',
        'super bypass of the assigned-reviewer rule (getattr role == super): a super holds every key'),
    'scholarship/services/assignment.py::is_review_target': ('GATE-LEFT', 'T5e',
        'who may receive a case: R1_SUPER_TARGET_ROLES by label; T5e moves assignment targets to keys with may_assign_to'),
    'scholarship/services/assignment.py::may_assign_to': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/source_invite.py::_reactivate': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/source_invite.py::has_joined': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/source_invite.py::has_person': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/source_invite.py::manageable': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/source_invite.py::people_of': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/source_invite.py::sign_in_states': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/sponsorship.py::cancel_admin_credit': ('GATE-LEFT', 'T5d',
        'money: cancelling a credit is gated by the label (getattr role)'),
    'scholarship/sponsorship.py::record_admin_credit': ('GATE-LEFT', 'T5d',
        'money: recording a credit is gated by the label (getattr role)'),
    'scholarship/credit_steps.py::step_refusal': ('GATE-LEFT', 'T5d',
        'money: credit signing by label (maker admin / approver org_admin); moved out of '
        'sponsorship.sign_admin_credit at T5c P5b so the Overview counts with the same rule. '
        'A1.10a (TD-475): the CHECKER step is the key payments_approve now, so finance is no label here'),
    # A1.10a (TD-475): credit_check_required, checks_credits and the last-checker guard
    # (staff_lifecycle.other_active_checker) read the key payments_approve now, not the finance label.
    'scholarship/staff_lifecycle.py::change_role': ('DISPLAY', 'T5a tables',
        'the role change itself (guards the row it rewrites)'),
    'scholarship/staff_mentor.py::candidates': ('DISPLAY', 'T5a tables',
        'who can be made a staff mentor (table rule)'),
    'scholarship/staff_mentor.py::eligible': ('DISPLAY', 'T5a tables',
        'who can be made a staff mentor (table rule)'),
    'scholarship/staff_permissions_admin.py::_refuse_target': ('DISPLAY', 'T5a tables',
        'which rows the Permissions editor can edit (team labels)'),
    'scholarship/staff_permissions_admin.py::_refuse_unlisted': ('DISPLAY', 'T5a tables',
        'keeps a reviewer-tab label listed'),
    'scholarship/staff_permissions_admin.py::change_permissions': ('DISPLAY', 'T5a tables',
        'guards the row it rewrites'),
    'scholarship/staff_person.py::on_reviewer_route': ('DISPLAY', 'T5a tables',
        'T3 review fix 1: table membership, mirroring `_ReviewersBase._reviewers` (a team preset holding review/qc)'),
    'scholarship/staff_tables_admin.py::_plan_remove': ('DISPLAY', 'T5a tables',
        'table move plan: the label after a removal'),
    'scholarship/staff_tables_admin.py::_refuse_basic': ('DISPLAY', 'T5a tables',
        'which rows a table move may touch'),
    'scholarship/staff_tables_admin.py::candidates': ('DISPLAY', 'T5a tables',
        'table candidates list'),
    'scholarship/staff_tables_admin.py::change': ('DISPLAY', 'T5a tables',
        'guards the row it rewrites'),
    'scholarship/staff_tables_admin.py::may_act': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/staff_tables_admin.py::may_become_mentor': ('DISPLAY', 'T5a tables',
        'table rule'),
    'scholarship/staff_tables_admin.py::plan_table_change': ('DISPLAY', 'T5a tables',
        'table move plan: label before / after'),
    'scholarship/surface_gates.py::may_open_contracts': ('GATE-LEFT', 'T5e',
        'R3: contracts stay for T5e'),
    'scholarship/surface_gates.py::may_read_invoices': ('GATE-LEFT', 'T5e',
        'R3: invoices stay for T5e'),
    'scholarship/surface_gates.py::requests_role': ('GATE-LEFT', 'T5e',
        'R3: requests stay for T5e'),
    'scholarship/views_admin/applications.py::AdminApplicationDetailView.patch': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/applications.py::AdminApplicationListView.get': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/applications.py::AdminNudgeStudentView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/applications.py::AdminOrgRejectView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/base.py::_AdminBase._can_review_app': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/base.py::_AdminBase._intake_narrowing': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/base.py::_AdminBase._org_allows': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/base.py::_AdminBase._org_narrowing': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/base.py::_AdminBase._org_scoped': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/base.py::_AdminBase._programme_by_code': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/base.py::_AdminBase._require_reviewer': ('GATE-LEFT', 'TD-496',
        'the graduation moderation door (its only caller); the list beside it was retired (TD-496)'),
    'scholarship/views_admin/billing.py::AdminBillingCorrectionView.delete': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/billing.py::AdminBillingCorrectionView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/billing.py::AdminBillingRatesView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/billing.py::AdminBillingRatesView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/billing.py::AdminBillingUsageView.get': ('GATE-LEFT', 'T5e',
        'R3: billing stays for T5e'),
    'scholarship/views_admin/billing.py::AdminPlatformCostsView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/billing.py::AdminPlatformCostsView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/build_hours.py::AdminOrgBuildHoursView.get': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/build_hours.py::AdminOrgBuildHoursView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/contracts.py::AdminContractDeployView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/contracts.py::AdminContractTemplateListView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/contracts.py::AdminContractTemplateListView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/contracts.py::_ContractsBase._target_org': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/contracts.py::_ContractsBase._template_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/gift_programmes.py::_ProgrammeScopedBase._gate': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/gift_programmes.py::_ProgrammeScopedBase._programmes_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/graduation.py::AdminBursaryCountersignView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/graduation.py::AdminBursaryWitnessView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/guardian_contact.py::_guardian_gate': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    # Request #55: the owner named the writers by role (org admin + super); T5e moves lead powers to keys.
    'scholarship/views_admin/reviewer_notes.py::_may_write': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/invitations.py::AdminInvitationCancelView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/invitations.py::AdminInvitationsView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/invoices.py::_InvoiceBase._caller': ('GATE-LEFT', 'T5e',
        'R3: invoices stay for T5e'),
    'scholarship/views_admin/letters.py::_LettersBase._senior': ('GATE-LEFT', 'T5e',
        'lead powers: only org_admin issues senior letters, by label; T5e moves lead powers to keys'),
    'scholarship/views_admin/lifecycle.py::AdminAssignableAdminsView.get': ('DISPLAY', 'account kind',
        'the LISTED set; who may be picked is the served may_assign_to flag'),
    'scholarship/views_admin/lifecycle.py::AdminCloseApplicationView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/lifecycle.py::AdminScopeListView.get': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/views_admin/me.py::programmes_of': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/views_admin/mentors.py::_MentorsBase._in_scope': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/org_config.py::AdminOrganisationConfigurationView._gate': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/org_config.py::AdminOrganisationConfigurationView._organisation_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/org_config.py::AdminProgrammeConfigurationView._gate': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/org_config.py::AdminProgrammeConfigurationView._programme_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/overview.py::AdminOverviewLayoutView._gate': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/overview.py::AdminOverviewLayoutView._organisation_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/requests.py::AdminOrgRequestCountView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/requests.py::AdminOrgRequestListView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/requests.py::_OrgRequestsBase._org_request_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/requests.py::_OrgRequestsBase._requestee': ('GATE-LEFT', 'T5e',
        'R3: requests stay for T5e'),
    'scholarship/views_admin/requests.py::_OrgRequestsBase._serialize': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/reviewers.py::AdminReviewerPauseView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/reviewers.py::AdminReviewerProgrammeView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/reviewers.py::_ReviewersBase._reviewers': ('DISPLAY', 'T5a tables',
        'table membership: a super is listed on the Reviewers tab, and an org admin does not see supers'),
    'scholarship/views_admin/reviewers.py::_ReviewersBase._side': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/source_users.py::_SourceUserBase._target': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/views_admin/source_users.py::source_kind_extras': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/views_admin/sources.py::AdminSourceNamesView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/sources.py::_SourcesBase._new_source_owner': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/sources.py::_SourcesBase._sources_in_scope': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/sponsor_terms.py::AdminSponsorTermsPublishView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/sponsors.py::AdminReleaseNricLockView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/sponsors.py::AdminSponsorListView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/sponsors.py::AdminSponsorReviewView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/sponsorships.py::AdminSetAwardAmountView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/sponsorships.py::AdminSponsorDetailView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/sponsorships.py::AdminSponsorMembershipView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/staff.py::AdminStaffPermissionsView._target': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/staff.py::AdminStaffPermissionsView.get': ('DISPLAY', 'T5a tables',
        'editable flag: team labels only'),
    'scholarship/views_admin/staff.py::AdminStaffRoleView.patch': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/staff.py::AdminTeamCandidatesView.get': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/staff.py::AdminTeamTableView.post': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/theme.py::AdminOrganisationThemeView._gate': ('GATE-LEFT', 'T5e',
        'lead-tier (org_admin or super) action gated by the label; T5e moves lead powers to keys'),
    'scholarship/views_admin/theme.py::AdminOrganisationThemeView._organisation_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/verdict.py::AdminAssignReviewerView.post': ('GATE-LEFT', 'T5e',
        'lead-tier gate: has_role super OR org_admin by label (not super-only); T5e moves lead powers to keys'),
    'scholarship/views_admin/verdict.py::AdminCancelReopenView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/verdict.py::AdminReopenDecisionView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
}


def test_every_role_read_is_allowlisted():
    sites = site_counts()
    unlisted = sorted(set(sites) - set(ALLOWLIST))
    assert not unlisted, 'role-label read outside the allowlist (classify it, or use a v2 key): %s' % unlisted


def test_allowlist_has_no_stale_or_unowned_entries():
    sites = site_counts()
    assert not sorted(set(ALLOWLIST) - set(sites)), 'allowlist entry no longer in the source: remove it'
    for key, (cls, owner, reason) in ALLOWLIST.items():
        assert cls in CLASSES and owner and reason, key
        assert cls != 'GATE-UNPLANNED', f'{key}: a gate with no owner needs a TD first'


def test_scanner_catches_a_role_gate(tmp_path):
    src = ("def f(admin):\n    return admin.role == 'finance'\n"
           "def g(qs):\n    return qs.filter(role__in=['a'])\n"
           "def h(admin):\n    return admin.is_super\n")
    (tmp_path / 'm.py').write_text(src)
    assert sorted(site_counts(str(tmp_path))) == ['m.py::f', 'm.py::g']
