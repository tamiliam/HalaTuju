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

M3a (A10, 2026-11-14): a SECOND scan (`lead_counts`, `LEAD_READS`) reports every read of `is_lead_tier`,
`_is_lead_tier`, `lead_reviews` and `LEAD_ROLE` (a call or a reference passed on), with an exact count per
function, and the GATE-LEFT counts are pinned so they only fall as M3b converts the gates.

M3b (2026-11-14): the 37 T5e gates read keys now and their entries are gone; no T5e entry is left. The 14 that
stay (a TARGET read, or M4 / TD-613 / M3c) carry list K's reason, and `GATE_LEFT_PINNED` holds the whole set.
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
    'courses/models/organisations.py::PartnerOrganisationQuerySet.tenants': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/models_staff.py::PartnerAdmin.Meta': ('DISPLAY', 'account kind',
        'DB constraints: which kind may carry a source / mentor link'),
    'courses/models_staff.py::PartnerAdmin.is_member': ('DISPLAY', 'account kind',
        'M1a: a team member in no group; holds no key, so it is the kind of account, not a power'),
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
    'courses/staff_delete_rules.py::_live_org_admin': ('GATE-LEFT', 'target rule',
        'T2 review N4: the sole-org-admin guard reads the TARGET (never strand an organisation without an '
        'organisation admin); list K, M3b'),
    'courses/staff_delete_rules.py::_org_admins': ('GATE-LEFT', 'target rule',
        'T2 review N4: the active org admins of an organisation, counted (and locked) by the sole-org-admin '
        'guard; a TARGET read, list K, M3b'),
    'courses/staff_delete_rules.py::sole_org_admin_ids': ('GATE-LEFT', 'target rule',
        'T2 review N4: the same guard for a whole table in one query; a TARGET read, list K, M3b'),
    'courses/staff_gift.py::for_invite': ('DISPLAY', 'account kind',
        'TD-501 A1.3: the invited kind says which fields the invite asks for (a reviewer names a gift); '
        'it grants or refuses no action'),
    'courses/staff_gift.py::unchosen_rows': ('DISPLAY', 'account kind',
        'TD-501 A1.3: a read-only report lists the rows who review with no gift chosen (a super is left out)'),
    'courses/staff_archive.py::restore': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/staff_reinvite.py::bring_back': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/staff_tables.py::_team_member': ('DISPLAY', 'T5a tables',
        'table membership (which table a person is listed on)'),
    'courses/staff_tables.py::invite_permissions': ('DISPLAY', 'M2b presets',
        'label -> the starting list an invite writes (the admin preset gains ADMIN_PRESET_V2); a write, not a gate'),
    'courses/staff_tables.py::in_reviewers': ('DISPLAY', 'T5a tables',
        'table membership'),
    'courses/views_admin.py::PartnerAdminMixin.get_partner_students': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/staff_fence.py::_deletable_now': ('GATE-LEFT', 'target rule',
        'which TARGET may be deleted now (a never-signed-in org admin is not an org admin\'s to remove); '
        'list K, M3b'),
    'courses/staff_fence.py::manageable_if_restored': ('GATE-LEFT', 'target rule',
        'the caller arm reads manage_team (M3b G1); the TARGET arm stays: an org admin manages only the '
        'manageable roles, never a super or a fellow org admin (list K)'),
    'courses/staff_fence.py::staff_target_readable': ('GATE-LEFT', 'target rule',
        'M1a O10: the caller arm reads manage_team (M3b G1); the TARGET arm stays: a fellow org admin\'s page '
        'is view-only (list K)'),
    'courses/views_referral_partners.py::AdminReferralPartnerDetailView.patch': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'courses/views_staff.py::AdminDeleteView._delete_locked': ('GATE-LEFT', 'target rule',
        'the sole-org-admin guard on the locked TARGET row; list K, M3b'),
    'courses/views_staff.py::AdminInviteView.post': ('GATE-LEFT', 'target rule',
        'the INVITED role: only a super invites an org admin, an org admin invites the team roles; the '
        'caller gate reads manage_team (M3b G1); list K'),
    'courses/views_staff.py::AdminListView.get': ('DISPLAY', 'account kind',
        'the roster lists staff kinds'),
    'courses/views_staff.py::AdminRevokeView._revoke_locked': ('GATE-LEFT', 'target rule',
        'the sole-org-admin guard on the locked TARGET row; list K, M3b'),
    'courses/views_staff.py::_listed_on_people': ('DISPLAY', 'T5a tables',
        'who is listed on People'),
    'courses/views_staff_list.py::StaffListView.get': ('DISPLAY', 'account kind',
        'the M1a Staff list lists staff kinds and mentor logins; the gate is the team_roster door'),
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
    'scholarship/payments_chain.py::fallback_approvers': ('GATE-LEFT', 'T5d',
        'money: fallback approvers are org admins by label (payments fallback rule)'),
    'scholarship/reviewer_onboarding.py::reviewer_profile_complete': ('DISPLAY', 'account kind',
        'first-login landing: the label says which kind of account this is, not what it may do'),
    'scholarship/scheduling.py::propose_slots': ('OVERRIDE', 'owner override',
        'super bypass of the assigned-reviewer rule (getattr role == super): a super holds every key'),
    'scholarship/services/assignment.py::is_review_target': ('GATE-LEFT', 'TD-613',
        'who may HOLD a case: R1_SUPER_TARGET_ROLES by label (T1: no longer who may be GIVEN one); retires '
        'with TD-613 (TD-622), list K'),
    'scholarship/source_invite.py::_reactivate': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/source_invite.py::has_joined': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/source_invite.py::has_person': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/source_invite.py::people_of': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/source_invite.py::sign_in_states': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/sponsorship/credits.py::cancel_admin_credit': ('GATE-LEFT', 'T5d',
        'money: cancelling a credit is gated by the label (getattr role)'),
    'scholarship/sponsorship/credits.py::record_admin_credit': ('GATE-LEFT', 'T5d',
        'money: recording a credit is gated by the label (getattr role)'),
    'scholarship/credit_steps.py::step_refusal': ('GATE-LEFT', 'T5d',
        'money: credit signing by label (maker admin / approver org_admin); moved out of '
        'sponsorship.sign_admin_credit at T5c P5b so the Overview counts with the same rule. '
        'A1.10a (TD-475): the CHECKER step is the key payments_approve now, so finance is no label here'),
    # A1.10a (TD-475): credit_check_required, checks_credits and the last-checker guard
    # (staff_lifecycle.other_active_checker) read the key payments_approve now, not the finance label.
    'scholarship/staff_lifecycle.py::change_role': ('DISPLAY', 'T5a tables',
        'the role change itself (guards the row it rewrites)'),
    'scholarship/staff_mentor.py::add_member': ('DISPLAY', 'M1a account kind',
        'a member joins Mentors: the UPDATE guards on the role it plans to change (concurrency)'),
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
    'scholarship/staff_tables_admin.py::_v2_part': ('DISPLAY', 'M2b presets',
        'table move plan: the label before / after picks which stored v2 keys the move writes (D8)'),
    'scholarship/staff_tables_admin.py::_refuse_basic': ('DISPLAY', 'T5a tables',
        'which rows a table move may touch'),
    'scholarship/staff_tables_admin.py::candidates': ('DISPLAY', 'T5a tables',
        'table candidates list'),
    'scholarship/staff_tables_admin.py::change': ('DISPLAY', 'T5a tables',
        'guards the row it rewrites'),
    'scholarship/staff_tables_admin.py::may_act': ('GATE-LEFT', 'target rule',
        'the caller arms read manage_team (M3b G1); the TARGET arm stays: an org admin never acts on a '
        'fellow org admin (Q4, list K)'),
    'scholarship/staff_tables_admin.py::may_become_mentor': ('DISPLAY', 'T5a tables',
        'table rule'),
    'scholarship/staff_tables_admin.py::plan_table_change': ('DISPLAY', 'T5a tables',
        'table move plan: label before / after'),
    'scholarship/views_admin/applications.py::AdminApplicationDetailView.patch': ('GATE-LEFT', 'M4',
        'the Vircle ID correction (money): stays by label until M4 (list K)'),
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
    'scholarship/views_admin/billing.py::AdminPlatformCostsView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/billing.py::AdminPlatformCostsView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
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
    'scholarship/views_admin/gift_programmes.py::_ProgrammeScopedBase._programmes_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/graduation.py::AdminBursaryCountersignView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/graduation.py::AdminBursaryWitnessView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/invitations.py::AdminInvitationCancelView.post': ('GATE-LEFT', 'target rule',
        'the invitation\'s and the account\'s role NOW (TARGET reads); the caller gate reads '
        'invitations.edit (M3b G2); list K'),
    'scholarship/views_admin/letters.py::_LettersBase._senior': ('GATE-LEFT', 'M3c',
        'senior letters by label: its key (`scholars.approve`, D5) is not in the catalogue yet and needs a data '
        'step; deferred from M3b to M3c'),
    'scholarship/views_admin/lifecycle.py::AdminAssignableAdminsView.get': ('DISPLAY', 'account kind',
        'the LISTED set; who may be picked is the served may_assign_to flag'),
    'scholarship/views_admin/lifecycle.py::AdminScopeListView.get': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/views_admin/me.py::programmes_of': ('DISPLAY', 'account kind',
        'the label says which kind of account this is (table / sign-in / recipient), not what it may do'),
    'scholarship/views_admin/mentors.py::_MentorsBase._in_scope': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/org_config.py::AdminOrganisationConfigurationView._organisation_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/org_config.py::AdminProgrammeConfigurationView._programme_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/overview.py::AdminOverviewLayoutView._organisation_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/requests.py::AdminOrgRequestCountView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/requests.py::AdminOrgRequestListView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/requests.py::_OrgRequestsBase._org_request_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/requests.py::_OrgRequestsBase._serialize': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
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
    'scholarship/views_admin/sponsors.py::AdminReleaseNricLockView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/sponsors.py::AdminSponsorListView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/sponsorships.py::AdminSetAwardAmountView.post': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/sponsorships.py::AdminSponsorDetailView.get': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
    'scholarship/views_admin/staff.py::AdminStaffPermissionsView.get': ('DISPLAY', 'T5a tables',
        'editable flag: team labels only'),
    'scholarship/views_admin/theme.py::AdminOrganisationThemeView._organisation_for': ('OVERRIDE', 'owner override',
        'super-only action (has_role super): a super holds every key; the override stays'),
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


# ── M3a (A10): the lead-tier reads the label scan does not see ───────────────────────────────────────
# `sp.is_lead_tier(x)` / `payments_chain._is_lead_tier(x)` and a load of `LEAD_ROLE` decide by the
# organisation admin's LABEL without spelling `.role ==` on the line, so the scan above missed them (the
# brief's list S: 15 server places). This second scan reports every such read, with an EXACT count per
# function, so a new lead gate cannot ship unseen. A GATE-LEFT entry is DELETED when its gate converts
# (M3b), never reclassified to pass; the ones that stay carry list K's reason.
#: M3a review: every LOAD of these names counts, so a call (`sp.is_lead_tier(x)`) and a reference passed
#: on (`filter(sp.is_lead_tier, rows)`, `key=lead_reviews`) are both seen; `lead_reviews` asks the label too.
LEAD_NAMES = {'is_lead_tier', '_is_lead_tier', 'lead_reviews', 'LEAD_ROLE'}
LEAD_CLASSES = {'DEFINITION', 'DISPLAY', 'TARGET', 'O15', 'M4', 'TD-613', 'GATE-LEFT'}


class _LeadScan(_Scan):
    def visit_Compare(self, node):          # the label scan's own hits are not this scan's
        self.generic_visit(node)

    visit_Call = visit_Compare              # nor are its query / `has_role` calls (the names inside count)

    def visit_Name(self, node):
        if node.id in LEAD_NAMES and isinstance(node.ctx, ast.Load):
            self._hit(node)

    def visit_Attribute(self, node):
        if node.attr in LEAD_NAMES and isinstance(node.ctx, ast.Load):
            self._hit(node)
        self.generic_visit(node)


def lead_counts(root=APPS):
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in ('tests', 'migrations', '__pycache__')]
        for fn in fns:
            if not fn.endswith('.py') or fn.startswith('test_'):
                continue
            rel = os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, '/')
            with open(os.path.join(dp, fn), encoding='utf-8') as fh:
                v = _LeadScan(rel)
                v.visit(ast.parse(fh.read()))
            for key, _ in v.found:
                out[key] = out.get(key, 0) + 1
    return out


#: module::function -> (exact count, class, owner, one-line reason)
LEAD_READS = {
    'courses/staff_permissions.py::is_lead_tier': (1, 'DEFINITION', 'O15', 'defines the lead tier'),
    'courses/staff_permissions.py::lead_reviews': (1, 'DEFINITION', 'T2 Q1',
        'the organisation admin joins Reviewers by a stored `review`'),
    'courses/staff_permissions.py::preset_for': (1, 'DEFINITION', 'M3a A2',
        'the organisation admin\'s preset: ORG_ADMIN_KEYS plus manage_team by role'),
    'courses/staff_permissions.py::resolve': (1, 'O15', 'M3a A2',
        'the stored list read strictly; manage_team held BY ROLE, never stored'),
    'courses/staff_permissions.py::team_holding': (3, 'DISPLAY', 'T5a tables',
        'the Reviewers list also lists an organisation admin who joined it (lead_reviews, in the same query)'),
    'courses/staff_permissions_v2.py::stored_v2': (1, 'DISPLAY', 'M3c',
        'the editor reads no stored v2 key for an organisation admin until M3c makes the row editable'),
    'courses/staff_permissions_v2.py::effective_v2': (1, 'O15', 'M3a A2 / A3, TD-620',
        'billing.edit and requests.approve by role (O15); the money keys by role until M4 (TD-620)'),
    'courses/staff_tables.py::in_reviewers': (1, 'DISPLAY', 'T5a tables',
        'the Reviewers table lists an organisation admin who joined it (lead_reviews)'),
    'courses/staff_tables.py::in_admins': (1, 'TARGET', 'M3a A4',
        'the organisation admin always sits in Admins, by role'),
    'courses/staff_tables.py::groups_to_leave': (1, 'TARGET', 'M3a A4',
        'the Admins seat is held by role, so it is never a group to leave'),
    'scholarship/payments_chain.py::_is_lead_tier': (1, 'M4', 'T5d / TD-620',
        'the payment chain\'s lead-tier helper'),
    'scholarship/payments_chain.py::_may_approve': (1, 'M4', 'T5d / TD-620', 'the fallback approver'),
    'scholarship/payments_chain.py::may_read': (1, 'M4', 'T5d / TD-620', 'who opens Payments'),
    'scholarship/payments_chain.py::may_prepare': (1, 'M4', 'T5d / TD-620', 'who creates a run'),
    'scholarship/payments_chain.py::_refusal': (1, 'M4', 'T5d / TD-620', 'why a step is refused'),
    'scholarship/staff_permissions_admin.py::history_held': (1, 'DISPLAY', 'M3a review',
        'the audit row of a Django-admin role change reads an organisation admin\'s page keys by role'),
    'scholarship/staff_person.py::on_reviewer_route': (2, 'DISPLAY', 'T3',
        'which route lists the target (an organisation admin only when they joined Reviewers)'),
    'scholarship/staff_person.py::person': (1, 'DISPLAY', 'served flag', 'the `lead` badge on the person page'),
    'scholarship/staff_list.py::list_rows': (1, 'DISPLAY', 'served flag', 'the `lead` badge on the Staff list'),
    'scholarship/staff_tables_admin.py::may_act': (1, 'TARGET', 'target rule',
        'the TARGET is an organisation admin (Q4); the caller arms read manage_team since M3b G1'),
    'scholarship/staff_tables_admin.py::_refuse_basic': (1, 'TARGET', 'target rule',
        'which rows may sit in a table (an organisation admin may)'),
    'scholarship/staff_tables_admin.py::table_keys': (2, 'DISPLAY', 'M3c',
        'the chips an organisation admin\'s row shows (review only) until M3c reads the stored set'),
    'scholarship/staff_tables_admin.py::_plan_add': (1, 'DISPLAY', 'M3a A6',
        'the writer adds `review` alone to an organisation admin\'s stored list'),
    'scholarship/staff_tables_admin.py::_plan_remove': (2, 'DISPLAY', 'M3a A6',
        'the writer takes `review` alone from an organisation admin\'s stored list'),
    'scholarship/staff_tables_admin.py::_cheap_refusal': (1, 'TARGET', 'target rule',
        'LEAD_FIXED: the organisation admin always sits in Admins (A4)'),
    'scholarship/staff_tables_admin.py::row_fields': (1, 'DISPLAY', 'served flag', 'the `lead` badge on a table row'),
    'scholarship/views_admin/staff.py::AdminTeamCandidatesView.get': (1, 'DISPLAY', 'served flag',
        'the `lead` badge on a candidate'),
    'scholarship/views_admin/mentors.py::mentor_rows': (1, 'DISPLAY', 'served flag',
        'the `lead` badge on a mentor\'s login'),
}


def test_every_lead_tier_read_is_allowlisted_with_its_exact_count():
    sites = lead_counts()
    unlisted = sorted(set(sites) - set(LEAD_READS))
    assert not unlisted, 'lead-tier read outside LEAD_READS (classify it, or use a key): %s' % unlisted
    stale = sorted(set(LEAD_READS) - set(sites))
    assert not stale, 'LEAD_READS entry no longer in the source: remove it: %s' % stale
    wrong = {k: (sites[k], LEAD_READS[k][0]) for k in sites if sites[k] != LEAD_READS[k][0]}
    assert not wrong, 'lead-tier read count changed (found, listed): %s' % wrong
    for key, (count, cls, owner, reason) in LEAD_READS.items():
        assert count > 0 and cls in LEAD_CLASSES and owner and reason, key


#: M3b (A10): every label gate still standing, by owner. M3b converted the 37 T5e gates and DELETED their
#: entries; the 14 left read a TARGET, or wait for M4 / TD-613 / M3c (list K), and were re-labelled.
GATE_LEFT_PINNED = {
    'courses/staff_delete_rules.py::_live_org_admin': 'target rule',
    'courses/staff_delete_rules.py::_org_admins': 'target rule',
    'courses/staff_delete_rules.py::sole_org_admin_ids': 'target rule',
    'courses/staff_fence.py::_deletable_now': 'target rule',
    'courses/staff_fence.py::manageable_if_restored': 'target rule',
    'courses/staff_fence.py::staff_target_readable': 'target rule',
    'courses/views_staff.py::AdminDeleteView._delete_locked': 'target rule',
    'courses/views_staff.py::AdminInviteView.post': 'target rule',
    'courses/views_staff.py::AdminRevokeView._revoke_locked': 'target rule',
    'scholarship/staff_tables_admin.py::may_act': 'target rule',
    'scholarship/views_admin/invitations.py::AdminInvitationCancelView.post': 'target rule',
    'scholarship/services/assignment.py::is_review_target': 'TD-613',
    'scholarship/views_admin/applications.py::AdminApplicationDetailView.patch': 'M4',
    'scholarship/views_admin/letters.py::_LettersBase._senior': 'M3c',
    'scholarship/credit_steps.py::step_refusal': 'T5d',
    'scholarship/payments_chain.py::fallback_approvers': 'T5d',
    'scholarship/sponsorship/credits.py::cancel_admin_credit': 'T5d',
    'scholarship/sponsorship/credits.py::record_admin_credit': 'T5d',
    'scholarship/views_admin/base.py::_AdminBase._require_reviewer': 'TD-496',
}


def test_the_gate_left_counts_are_pinned():
    # M3b converted the T5e gates and DELETED their entries: none is left, and the set that stays is pinned
    # by owner, so it only ever shrinks. A new label gate fails here: convert it to a key, or classify it
    # with an owner and a TD (and say why in the decisions log).
    t5e = sorted(k for k, (cls, owner, _r) in ALLOWLIST.items() if cls == 'GATE-LEFT' and owner == 'T5e')
    assert t5e == [], t5e
    gate_left = {k: owner for k, (cls, owner, _r) in ALLOWLIST.items() if cls == 'GATE-LEFT'}
    assert gate_left == GATE_LEFT_PINNED
    lead_gates = sum(count for count, cls, _o, _r in LEAD_READS.values() if cls == 'GATE-LEFT')
    assert lead_gates == 0, lead_gates


def test_scanner_catches_a_lead_tier_gate(tmp_path):
    src = ("LEAD_ROLE = 'org_admin'\n"
           "def f(admin):\n    return sp.is_lead_tier(admin)\n"
           "def g(admin):\n    return _is_lead_tier(admin) or is_lead_tier(admin)\n"
           "def h(admin):\n    return admin.role == sp.LEAD_ROLE\n"
           "def k(admin):\n    return admin.role in (LEAD_ROLE,)\n"
           "def n(admin):\n    return admin.has_perm('manage_team')\n"
           "def p(rows):\n    return list(filter(sp.is_lead_tier, rows)) + sorted(rows, key=lead_reviews)\n"
           "def q(admin):\n    return admin.role == 'reviewer' or has_role(admin, 'admin')\n")
    (tmp_path / 'm.py').write_text(src)
    assert lead_counts(str(tmp_path)) == {'m.py::f': 1, 'm.py::g': 2, 'm.py::h': 1, 'm.py::k': 1,
                                          'm.py::p': 2}
