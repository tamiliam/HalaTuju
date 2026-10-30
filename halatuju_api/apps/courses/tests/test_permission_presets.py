"""THE GOLDEN TABLE — request #39 (staff permissions), Sprint 1: every gate the arc converts, asked of
every preset (+ super, partner), against TODAY's role checks.

Roadmap: `docs/plans/2026-10-19-staff-permissions-roadmap.md` (Appendix A lists the gates).

WHAT THIS FILE PROVES, in two halves, for every row of `GOLDEN`:

1. **`test_each_gate_answers_today_s_table`** — the REAL gate (the function, or the endpoint through the
   real auth) answers exactly the table, role by role. It was written and run green on the
   UNCONVERTED code: in Sprint 1 no gate reads a permission yet. Sprints 2 and 3 convert the gates and
   must keep this half green, which is what makes the conversion a refactor and not a change.
2. **`test_the_presets_reproduce_today`** — the permission rule each gate WILL read (`rule`), asked of
   the same people through `has_perm` only, gives the same answers. Where it does not, the difference
   is written down in `diverges` with its reason — never silently absorbed. Today there is exactly
   one kind: R1 (the super's wider choice of assignee, kept as a super override, roadmap R1 —
   `services.R1_SUPER_TARGET_ROLES` since Sprint 3). Sprint 1's other finding (the lead tier holds
   `qc` but an org_admin is not on the Reviewers tab) was ruled by the owner on 2026-10-19 ("yes":
   org admins stay off it) and Sprint 3 built exactly that, so its rule now says so.

⚠ SPRINT 3 CONVERTED GROUPS A-D (review, see_all, qc, spending): every probe below already called
the live gate, so after the conversion each one now reads `has_perm`, and the `today` columns did not
move. Sprint 3 ADDED the rows marked `# S3` (the file reads through `_scoped_application`, the
Spending flags and category doors, and the served `assignable` flag) — each written against the
behaviour before the conversion and green on it.

⚠ SPRINT 2 CHANGED ONLY THE ROWS MARKED `s2`, and each names the owner's ruling of 2026-10-19
("Finance role ... I would like the role to be able to approve payment — the work that Suresh does
today"): Finance APPROVES runs, the organisation admin stops countersigning and becomes the fallback
approver, and no preset holds the CHECK any more. Each `s2` row's `today` is the NEW truth and its
`was` keeps the Sprint 1 answer, so the flip stays readable. Every other row's `today` is unchanged;
`payments_read`'s RULE gained "or the lead tier" (its truth did not move), because the lead tier no
longer holds `payments_approve` and still opens Payments.

The reverse sweep (`ReverseSweep`) holds the vocabulary: every catalogue key reaches at least one row,
every stored role resolves, and no row names a key the catalogue does not have.
"""
import datetime
from types import SimpleNamespace
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses import staff_permissions as sp
from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.tests.factories import make_admin

TEST_JWT_SECRET = 'test-supabase-jwt-secret'

#: Every person the table asks about: the five presets, plus the two platform roles.
ROLES = ('super', 'org_admin', 'admin', 'finance', 'qc', 'reviewer', 'partner')

#: Owner ruling quoted by every `s2` row.
S2_RULING = ('owner 2026-10-19 (#39 payments, option A): Admin prepares, Finance APPROVES and that '
             'completes the run; the organisation admin stops countersigning (fallback approver '
             'when nobody else can); a third signer stays one permission away')

R1 = ('R1 (roadmap): today a SUPER may assign any of reviewer/admin/qc/org_admin, while an org_admin '
      'may assign only a reviewer. The permission rule reproduces the org_admin side; the super\'s '
      'wider choice is kept as a super override (services.R1_SUPER_TARGET_ROLES, Sprint 3), and '
      '"assignment grants write" is unchanged. '
      'Production 2026-10-19: one in-play case sits with an org_admin (awarded), none with admin/qc.')


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _t(*roles):
    """A row's `today`: True for the roles named, False for everyone else."""
    return {r: r in roles for r in ROLES}


def _scope_rule(a):
    return 'all' if a.has_perm('see_all') else 'assigned' if a.has_perm('review') else 'none'


def _any_payments(a):
    return any(a.has_perm(k) for k in ('payments_prepare', 'payments_check', 'payments_approve'))


#: gate -> {where, keys, today, rule, diverges, s2}. `rule(admin, case)` is the permission reading
#: the gate will make; `case` is the test case (for the organisation and other fixtures).
GOLDEN = {
    # ── A/B. who reaches the Applications list, and how much of it ──────────────────────────────
    'b40_scope': {
        'where': 'scholarship/views_admin/base.py _b40_scope',
        'keys': ('see_all', 'review'),
        'today': {'super': 'all', 'org_admin': 'all', 'admin': 'all', 'finance': 'none',
                  'qc': 'all', 'reviewer': 'assigned', 'partner': 'none'},
        'rule': lambda a, c: _scope_rule(a),
    },
    'write_unassigned_case': {
        'where': 'base.py _can_review_app (org-wide write: org_admin, qc)',
        'keys': ('qc',),
        'today': _t('super', 'org_admin', 'qc'),
        'rule': lambda a, c: _scope_rule(a) != 'none' and a.has_perm('qc'),
    },
    'write_assigned_case': {
        'where': 'base.py _can_review_app (assignment grants write)',
        'keys': ('see_all', 'review'),
        'today': _t('super', 'org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: _scope_rule(a) != 'none',
    },
    'ai_reliability_card': {
        'where': 'views_admin/verdict.py AdminVerdictMetricsView',
        'keys': ('see_all', 'review'),
        'today': _t('super', 'org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: a.has_perm('see_all') or a.has_perm('review'),
    },
    # ── C. quality check ────────────────────────────────────────────────────────────────────────
    'qc_gate': {
        'where': 'base.py _require_qc (role gate)',
        'keys': ('qc',),
        'today': _t('super', 'org_admin', 'qc'),
        'rule': lambda a, c: a.has_perm('qc'),
    },
    # ── A. who may be given a case ──────────────────────────────────────────────────────────────
    'assignment_target': {
        'where': 'services/assignment.py _can_review (is_review_target: review + R1 override)',
        'keys': ('review',),
        'today': _t('super', 'org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: a.has_perm('review'),
        'diverges': {'org_admin': R1, 'admin': R1, 'qc': R1},
    },
    'propose_interview_times': {
        'where': 'scheduling.py _can_review (services.is_review_target)',
        'keys': ('review',),
        'today': _t('super', 'org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: a.has_perm('review'),
        'diverges': {'org_admin': R1, 'admin': R1, 'qc': R1},
    },
    'pause_target': {
        'where': 'services/assignment.py set_paused (is_review_target)',
        'keys': ('review',),
        'today': _t('super', 'org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: a.has_perm('review'),
        'diverges': {'org_admin': R1, 'admin': R1, 'qc': R1},
    },
    'assignable_list_for_super': {
        'where': 'views_admin/lifecycle.py AdminAssignableAdminsView (listed), read by a super',
        'keys': ('review',),
        'today': _t('super', 'org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: a.has_perm('review'),
        'diverges': {'org_admin': R1, 'admin': R1, 'qc': R1},
    },
    'org_admin_may_assign_to': {
        'where': 'views_admin/verdict.py AdminAssignReviewerView (an org_admin assigns only a review '
                 'holder: services.may_assign_to)',
        'keys': ('review',),
        'today': _t('reviewer'),
        'rule': lambda a, c: (a.has_perm('review')
                              and a.owning_organisation_id == c.org.id),
    },
    'reviewers_tab_lists': {
        'where': 'views_admin/reviewers.py _reviewers (team members holding review or qc; + '
                 'is_super_admin)',
        'keys': ('review', 'qc'),
        'today': _t('super', 'qc', 'reviewer'),
        # Owner 2026-10-19 ("yes"): org admins stay OFF the Reviewers list/tab, so it stays exactly
        # as today, even though the lead tier holds qc. The rule leaves the lead tier out.
        'rule': lambda a, c: (not sp.is_lead_tier(a)
                              and (a.has_perm('review') or a.has_perm('qc'))),
    },
    'read_assigned_file': {                                                   # S3
        'where': 'base.py _scoped_application (a case assigned to X: the cockpit, documents, '
                 'interviews, lifecycle, profiles and verdict all open through it)',
        'keys': ('see_all', 'review'),
        'today': _t('super', 'org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: _scope_rule(a) != 'none',
    },
    'read_unassigned_file': {                                                 # S3
        'where': 'base.py _scoped_application (a same-organisation case assigned to nobody)',
        'keys': ('see_all',),
        'today': _t('super', 'org_admin', 'admin', 'qc'),
        'rule': lambda a, c: _scope_rule(a) == 'all',
    },
    # ── D. spending ─────────────────────────────────────────────────────────────────────────────
    'spending_page': {
        'where': 'views_admin/spending.py _SpendingBase (spending)',
        'keys': ('spending',),
        'today': _t('super', 'org_admin', 'admin'),
        'rule': lambda a, c: a.has_perm('spending'),
    },
    'spending_flags': {                                                       # S3
        'where': 'views_admin/spending_flags.py AdminSpendingFlagView GET (through _SpendingBase)',
        'keys': ('spending',),
        'today': _t('super', 'org_admin', 'admin'),
        'rule': lambda a, c: a.has_perm('spending'),
    },
    'spending_category_write': {                                              # S3
        'where': 'views_admin/spending.py AdminSpendingCategoryView POST (through _SpendingBase)',
        'keys': ('spending',),
        'today': _t('super', 'org_admin', 'admin'),
        'rule': lambda a, c: a.has_perm('spending'),
    },
    # ── E. payments ─────────────────────────────────────────────────────────────────────────────
    'payments_read': {
        'where': 'views_admin/payments.py _payments_admin READ (payments.may_read)',
        'keys': ('payments_prepare', 'payments_check', 'payments_approve'),
        'today': _t('super', 'org_admin', 'admin', 'finance'),
        'rule': lambda a, c: _any_payments(a) or sp.is_lead_tier(a),
    },
    'payments_write': {
        'where': 'views_admin/payments.py _payments_admin WRITE (payments.may_prepare: create / edit '
                 'item / cancel)',
        'keys': ('payments_prepare',),
        'today': _t('super', 'org_admin', 'admin'),
        'rule': lambda a, c: a.has_perm('payments_prepare') or sp.is_lead_tier(a),
    },
    'sign_as_maker': {
        'where': 'payments.py sign at draft',
        'keys': ('payments_prepare',),
        'today': _t('super', 'admin'),
        'rule': lambda a, c: a.has_perm('payments_prepare'),
    },
    'sign_the_check': {
        'where': 'payments_chain.py sign at admin_signed with the check armed (by a custom holder)',
        'keys': ('payments_check',),
        'today': _t('super'),
        'was': _t('super', 'finance'),
        'rule': lambda a, c: a.has_perm('payments_check'),
        's2': S2_RULING + ' — after S2 no preset holds payments_check (dormant until granted).',
    },
    'sign_the_approval': {
        'where': 'payments_chain.py sign at finance_checked (the approval that completes the run)',
        'keys': ('payments_approve',),
        'today': _t('super', 'finance'),
        'was': _t('super', 'org_admin'),
        'rule': lambda a, c: a.has_perm('payments_approve'),
        's2': S2_RULING + ' — after S2 finance approves; org_admin only under the fallback.',
    },
    'check_step_armed_by': {
        'where': 'payments_chain.py finance_check_required (an organisation whose only active member '
                 'is X)',
        'keys': ('payments_check',),
        'today': _t(),
        'was': _t('finance'),
        'rule': lambda a, c: c.alone(a, lambda org: bool(sp.holders(org, 'payments_check'))),
        's2': S2_RULING + ' — re-keyed to "an active member holds payments_check"; wallet credits '
                          'keep the finance-role rule (credit_check_required).',
    },
    'check_step_served_on_a_run': {
        'where': 'views_admin/payments.py _payment_run_detail finance_check_required (a run of an '
                 'organisation whose only active member is X)',
        'keys': ('payments_check',),
        'today': _t(),
        'was': _t('finance'),
        'rule': lambda a, c: c.alone(a, lambda org: bool(sp.holders(org, 'payments_check'))),
        's2': S2_RULING + ' — served as check_step_required beside it; same predicate.',
    },
    'countersign_email_goes_to': {
        'where': 'emails/payment_mail.py send_payment_countersign_email (the approvers, else the '
                 'org admins under the fallback)',
        'keys': ('payments_approve',),
        'today': _t('finance'),
        'was': _t('org_admin'),
        'rule': lambda a, c: a in sp.holders(c.org, 'payments_approve'),
        's2': S2_RULING + ' — the "ready" email goes to the approvers (Finance), else the '
                          'checkers when armed, else the org admins under the fallback.',
    },
    'check_email_goes_to': {
        'where': 'emails/payment_mail.py send_payment_finance_check_email (payments_check holders)',
        'keys': ('payments_check',),
        'today': _t(),
        'was': _t('finance'),
        'rule': lambda a, c: a in sp.holders(c.org, 'payments_check'),
        's2': S2_RULING + ' — goes to payments_check holders, when anybody holds it.',
    },
    'other_active_finance': {
        'where': 'staff_lifecycle._other_active_finance (the role-change consequence: is X another '
                 'active finance member of the target\'s organisation?)',
        'keys': ('payments_approve',),
        'today': _t('finance'),
        'was': _t('finance'),
        'rule': lambda a, c: c.alone(a, lambda org: bool(sp.holders(org, 'payments_approve'))),
        's2': S2_RULING + ' — the answer does not move: the finance ROLE is what both consequences '
                          'turn on (the preset that now APPROVES runs, and the credit check, which '
                          'keeps the finance-role rule); the rule now reads payments_approve.',
    },
    'switch_refused_for_unfinished_run': {
        'where': 'staff_lifecycle.plan_role_change run_in_progress (X made / signed an unfinished '
                 'run and is switched to its role pair)',
        'keys': ('payments_approve',),
        'today': _t('admin'),
        'was': _t('admin'),
        'rule': lambda a, c: c.pair_preset_holds(a, ('payments_approve',)),
        's2': S2_RULING + ' — "cannot check their own run" becomes "cannot approve their own run" '
                          '(the pair preset then holds payments_approve).',
    },
    'switch_refused_with_open_cases': {
        'where': 'staff_lifecycle.plan_role_change has_open_cases (X holds an in-play case and is '
                 'switched to its role pair) — the refusal the S4 PATCH reuses',
        'keys': ('review', 'see_all'),
        'today': _t('admin'),
        'rule': lambda a, c: c.pair_preset_lacks(a, ('review', 'see_all')),
    },
    'assignable_list_for_org_admin': {
        'where': 'views_admin/lifecycle.py AdminAssignableAdminsView (listed), read by an org_admin',
        'keys': ('review',),
        'today': _t('org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: a.has_perm('review') and a.owning_organisation_id == c.org.id,
        'diverges': {r: R1 + ' The org_admin\'s LIST is wide today (the cockpit unions the current '
                         'assignee in from it, bug #66) while its assign endpoint and the web '
                         'picker take reviewers only; S3 keeps the list and serves `assignable`.'
                     for r in ('org_admin', 'admin', 'qc')},
    },
    'assignable_flag_for_org_admin': {                                        # S3
        'where': 'views_admin/lifecycle.py AdminAssignableAdminsView served `assignable` (an '
                 'org_admin reads it; before S3 the web picker computed role == reviewer)',
        'keys': ('review',),
        'today': _t('reviewer'),
        'rule': lambda a, c: (a.has_perm('review')
                              and a.owning_organisation_id == c.org.id),
    },
    'assignable_flag_for_super': {                                            # S3
        'where': 'views_admin/lifecycle.py AdminAssignableAdminsView served `assignable` (a super '
                 'reads it; before S3 the web picker offered a super every listed row)',
        'keys': ('review',),
        'today': _t('super', 'org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: a.has_perm('review'),
        'diverges': {'org_admin': R1, 'admin': R1, 'qc': R1},
    },
    # ── G. the team (lead tier: stays on role in #39, so the key maps but never converts) ────────
    'may_invite_staff': {
        'where': 'courses/views_staff.py AdminInviteView (who may invite)',
        'keys': ('manage_team',),
        'today': _t('super', 'org_admin'),
        'rule': lambda a, c: a.has_perm('manage_team'),
    },
}


#: Sprint 3 review fix 2 — the answers a LEGACY super (`is_super_admin=True`, role 'reviewer') gave
#: before Sprint 3 that differ now: gate -> (before, why). Production has no such row (2026-10-19).
LEGACY_FLAG_MOVED = {
    'org_admin_may_assign_to': (True, 'before S3 the org_admin target rule read role == reviewer, '
                                      'so a same-organisation legacy super with role reviewer could '
                                      'be assigned; may_assign_to says "never a super", which is what '
                                      'its docstring always promised (the assignable list already '
                                      'left every flagged super out).'),
}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class GoldenTable(TestCase):
    """One person per role in one organisation; each row's probe asks the REAL gate."""

    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='golden', name='Golden Org',
                                                      module_scholarship=True)
        self.people = {}
        for role in ROLES:
            if role == 'super':
                a = make_admin('super', super_admin=True)
            elif role == 'partner':
                a = make_admin('partner')
            else:
                a = make_admin(role, owning_org=self.org)
            self.people[role] = a
        # Everybody here USES the console (#39 S2 review fix 4: a payment signer who has never
        # signed in is not counted as eligible). The table asks about people who come to work.
        from django.utils import timezone
        PartnerAdmin.objects.filter(pk__in=[a.pk for a in self.people.values()]).update(
            first_seen_at=timezone.now())
        for a in self.people.values():
            a.refresh_from_db()
        self.client = APIClient()

    # ── probes: each calls the real code and answers like `today` ──────────────────────────────
    def _http(self, admin, method, url, data=None):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(admin.supabase_user_id)}')
        r = getattr(self.client, method)(url, data or {}, format='json')
        self.client.credentials()
        return r

    def _case(self, **kw):
        base = dict(owning_organisation_id=self.org.id, assigned_to_id=None, status='interviewed',
                    verdict_decided_by='')
        base.update(kw)
        return SimpleNamespace(**base)

    def probe_b40_scope(self, a):
        from apps.scholarship.views_admin import _AdminBase
        return _AdminBase()._b40_scope(a)

    def probe_write_unassigned_case(self, a):
        from apps.scholarship.views_admin import _AdminBase
        return _AdminBase()._can_review_app(a, self._case())

    def probe_write_assigned_case(self, a):
        from apps.scholarship.views_admin import _AdminBase
        return _AdminBase()._can_review_app(a, self._case(assigned_to_id=a.id))

    def probe_ai_reliability_card(self, a):
        return self._http(a, 'get', '/api/v1/admin/scholarship/verdict-metrics/').status_code != 403

    def _scoped(self, a, case):
        from apps.scholarship.views_admin import _AdminBase
        view = _AdminBase()
        with mock.patch.object(view, 'get_admin', return_value=a), \
                mock.patch.object(view, '_get_application', return_value=case):
            app, err = view._scoped_application(None, 1)
        return err is None and app is case

    def probe_read_assigned_file(self, a):
        return self._scoped(a, self._case(assigned_to_id=a.id,
                                          owning_organisation_id=a.owning_organisation_id))

    def probe_read_unassigned_file(self, a):
        return self._scoped(a, self._case(owning_organisation_id=a.owning_organisation_id))

    def probe_qc_gate(self, a):
        from apps.scholarship.views_admin import _AdminBase
        view = _AdminBase()
        with mock.patch.object(view, 'get_admin', return_value=a), \
                mock.patch.object(view, '_get_application', return_value=self._case()):
            _, _, err = view._require_qc(None, 1)
        return err is None

    def probe_assignment_target(self, a):
        from apps.scholarship.services.assignment import _can_review
        return _can_review(a)

    def probe_propose_interview_times(self, a):
        from apps.scholarship.scheduling import _can_review
        return _can_review(a)

    def probe_pause_target(self, a):
        from apps.scholarship.services import PauseError, set_paused
        try:
            set_paused(a, True)
        except PauseError:
            return False
        set_paused(a, False)
        return True

    def probe_assignable_list_for_super(self, a):
        caller = make_admin('super', super_admin=True)
        r = self._http(caller, 'get', '/api/v1/admin/scholarship/assignable-admins/')
        self.assertEqual(r.status_code, 200)
        return a.id in {row['id'] for row in r.json()['admins']}

    def probe_org_admin_may_assign_to(self, a):
        from apps.scholarship.views_admin.verdict import AdminAssignReviewerView
        with mock.patch.object(AdminAssignReviewerView, '_scoped_application',
                               return_value=(self._case(status='profile_complete'), None)), \
                mock.patch('apps.scholarship.views_admin.verdict.assign_reviewer'), \
                mock.patch('apps.scholarship.views_admin.verdict.AdminApplicationDetailSerializer',
                           return_value=SimpleNamespace(data={})):
            r = self._http(self.people['org_admin'], 'post',
                           '/api/v1/admin/scholarship/applications/1/assign/',
                           {'reviewer_id': a.id})
        self.assertIn(r.status_code, (200, 400))
        return r.status_code == 200

    def probe_reviewers_tab_lists(self, a):
        from apps.scholarship.views_admin.reviewers import _ReviewersBase
        return a.id in set(_ReviewersBase()._reviewers(None).values_list('id', flat=True))

    def probe_spending_page(self, a):
        return self._http(a, 'get', '/api/v1/admin/scholarship/spending/').status_code != 403

    def probe_spending_flags(self, a):
        return self._http(a, 'get', '/api/v1/admin/scholarship/spending/flag/').status_code != 403

    def probe_spending_category_write(self, a):
        # No body: an admitted caller gets a 400, a refused one a 403.
        r = self._http(a, 'post', '/api/v1/admin/scholarship/spending/category/', {})
        return r.status_code != 403

    def probe_payments_read(self, a):
        return self._http(a, 'get', '/api/v1/admin/scholarship/payment-runs/').status_code != 403

    def probe_payments_write(self, a):
        # A bad date: a caller the role gate admits gets a 400, one it refuses gets a 403.
        r = self._http(a, 'post', '/api/v1/admin/scholarship/payment-runs/', {'payment_date': ''})
        return r.status_code != 403

    def _sign(self, a, status, **signed):
        from apps.scholarship import payments
        fields = dict(status=status, organisation=self.org, admin_signed_email='',
                      finance_signed_email='', org_admin_signed_email='')
        fields.update(signed)
        run = SimpleNamespace(**fields)
        run.save = lambda **kw: None
        with mock.patch('apps.scholarship.emails.send_payment_finance_check_email'), \
                mock.patch('apps.scholarship.emails.send_payment_countersign_email'), \
                mock.patch('apps.scholarship.payments.complete'):
            try:
                payments.sign(run, a, a.name)
            except payments.PaymentsError as e:
                self.assertIn(e.code, ('wrong_role', 'finance_check_required'))
                return False
        return True

    def probe_sign_as_maker(self, a):
        return self._sign(a, 'draft')

    def probe_sign_the_check(self, a):
        # Armed since Sprint 2 by a CUSTOM holder (no preset holds payments_check any more), who is
        # removed again so the other rows never see them.
        checker = make_admin('admin', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=checker.pk).update(permissions=['payments_check'],
                                                          first_seen_at=self.people['admin'].first_seen_at)
        try:
            return self._sign(a, 'admin_signed', admin_signed_email='maker@elsewhere.test')
        finally:
            checker.delete()

    def probe_sign_the_approval(self, a):
        return self._sign(a, 'finance_checked', admin_signed_email='maker@elsewhere.test',
                          finance_signed_email='checker@elsewhere.test')

    def alone(self, a, ask):
        """``ask(org)`` for an organisation whose ONLY active member is ``a``; ``a`` is put back."""
        home = a.owning_organisation
        lone = PartnerOrganisation.objects.create(
            code=f'lone-{a.role}-{PartnerOrganisation.objects.count()}', name=f'Lone {a.role}')
        a.owning_organisation = lone
        a.save(update_fields=['owning_organisation'])
        try:
            return ask(lone)
        finally:
            a.owning_organisation = home
            a.save(update_fields=['owning_organisation'])

    def probe_check_step_armed_by(self, a):
        from apps.scholarship.payments import finance_check_required
        return self.alone(a, finance_check_required)

    def probe_check_step_served_on_a_run(self, a):
        import datetime
        from apps.scholarship.models import PaymentRun
        caller = make_admin('super', super_admin=True)

        def served(org):
            run = PaymentRun.objects.create(organisation=org, payment_date=datetime.date(2026, 11, 1),
                                            reference=f'PR-GOLD-{org.code}', status='admin_signed')
            r = self._http(caller, 'get', f'/api/v1/admin/scholarship/payment-runs/{run.id}/')
            self.assertEqual(r.status_code, 200, r.content)
            return r.json()['finance_check_required']
        return self.alone(a, served)

    def _recipients(self, send):
        from django.core import mail
        run = SimpleNamespace(id=1, reference='PR-GOLD', organisation=self.org,
                              admin_signed_name='Maker', payment_date=datetime.date(2026, 11, 1),
                              admin_signed_email='maker@elsewhere.test', finance_signed_email='',
                              org_admin_signed_email='')
        mail.outbox.clear()
        with mock.patch('apps.scholarship.emails.payment_mail._run_totals', return_value=(1, 100)), \
                mock.patch('apps.scholarship.emails.payment_mail._run_month_label',
                           return_value='November 2026'):
            send(run)
        return {to for m in mail.outbox for to in m.to}

    def probe_countersign_email_goes_to(self, a):
        from apps.scholarship.emails.payment_mail import send_payment_countersign_email
        return a.email in self._recipients(send_payment_countersign_email)

    def probe_check_email_goes_to(self, a):
        from apps.scholarship.emails.payment_mail import send_payment_finance_check_email
        return a.email in self._recipients(send_payment_finance_check_email)

    def probe_other_active_finance(self, a):
        from apps.scholarship.staff_lifecycle import _other_active_finance

        def ask(org):
            target = make_admin('admin', owning_org=org)
            return _other_active_finance(target)
        return self.alone(a, ask)

    def _plan_switch(self, a, open_cases, runs):
        from apps.scholarship import staff_lifecycle as sl
        to = sl.ROLE_PAIRS.get(a.role, 'finance')
        with mock.patch.object(sl, 'open_cases', return_value=open_cases), \
                mock.patch.object(sl, 'runs_in_progress', return_value=runs):
            try:
                sl.plan_role_change(a, to)
            except sl.RoleChangeRefused as e:
                return e.code
        return None

    def probe_switch_refused_for_unfinished_run(self, a):
        return self._plan_switch(a, 0, 1) == 'run_in_progress'

    def probe_switch_refused_with_open_cases(self, a):
        return self._plan_switch(a, 1, 0) == 'has_open_cases'

    def probe_assignable_list_for_org_admin(self, a):
        r = self._http(self.people['org_admin'], 'get', '/api/v1/admin/scholarship/assignable-admins/')
        self.assertEqual(r.status_code, 200)
        return a.id in {row['id'] for row in r.json()['admins']}

    # ── rule helpers: the role pairs are preset-bound (R2), so the rule reads the PAIR's preset ──
    @staticmethod
    def _pair_preset(a):
        from apps.scholarship.staff_lifecycle import ROLE_PAIRS
        if a.is_super or a.role not in ROLE_PAIRS:
            return None
        return set(sp.preset_for(ROLE_PAIRS[a.role]))

    def pair_preset_holds(self, a, keys):
        preset = self._pair_preset(a)
        return preset is not None and bool(preset & set(keys))

    def pair_preset_lacks(self, a, keys):
        preset = self._pair_preset(a)
        return preset is not None and not (preset & set(keys))

    def _assignable_as_read_by(self, caller, a):
        r = self._http(caller, 'get', '/api/v1/admin/scholarship/assignable-admins/')
        self.assertEqual(r.status_code, 200)
        return any(row['id'] == a.id and row['assignable'] for row in r.json()['admins'])

    def probe_assignable_flag_for_org_admin(self, a):
        return self._assignable_as_read_by(self.people['org_admin'], a)

    def probe_assignable_flag_for_super(self, a):
        return self._assignable_as_read_by(make_admin('super', super_admin=True), a)

    def probe_may_invite_staff(self, a):
        # Name and email missing: an admitted caller gets 400, a refused one 403.
        return self._http(a, 'post', '/api/v1/admin/invite/', {'role': 'reviewer'}).status_code != 403

    # ── the two halves ──────────────────────────────────────────────────────────────────────────
    def test_each_gate_answers_today_s_table(self):
        for gate, row in GOLDEN.items():
            probe = getattr(self, f'probe_{gate}')
            for role in ROLES:
                with self.subTest(gate=gate, role=role):
                    self.assertEqual(probe(self.people[role]), row['today'][role],
                                     f'{gate} ({row["where"]}) for {role}')

    def test_the_presets_reproduce_today(self):
        for gate, row in GOLDEN.items():
            with self.subTest(gate=gate):
                differs = {role for role in ROLES
                           if row['rule'](self.people[role], self) != row['today'][role]}
                self.assertEqual(differs, set(row.get('diverges', {})),
                                 f'{gate}: the permission rule and today disagree for {sorted(differs)}; '
                                 f'declared: {sorted(row.get("diverges", {}))}')

    def test_a_legacy_super_flag_on_a_team_role_answers_as_a_super(self):
        """Sprint 3 review fix 2. `is_super_admin=True` with a role other than 'super' (the legacy
        shape) is a SUPER to every gate here, exactly as `has_role` treated it before #39 — with ONE
        answer that moved, declared in `LEGACY_FLAG_MOVED`. Production (read by the lead,
        2026-10-19): NO row has the flag with another role, so nobody is affected; this row exists
        so the shape can never drift silently."""
        from django.utils import timezone
        legacy = make_admin('reviewer', owning_org=self.org, super_admin=True)
        PartnerAdmin.objects.filter(pk=legacy.pk).update(first_seen_at=timezone.now())
        legacy.refresh_from_db()
        for gate, row in GOLDEN.items():
            with self.subTest(gate=gate):
                got = getattr(self, f'probe_{gate}')(legacy)
                self.assertEqual(got, row['today']['super'], f'{gate}: a legacy-flag reviewer')
                if gate in LEGACY_FLAG_MOVED:
                    self.assertNotEqual(got, LEGACY_FLAG_MOVED[gate][0])

    def test_the_lone_member_probe_restores_the_organisation(self):
        # The lone-member rows move a person; the other rows must not see it. (Sprint 2: finance no
        # longer arms the check, so the probe that still answers True for them is asked instead.)
        self.assertTrue(self.probe_other_active_finance(self.people['finance']))
        self.people['finance'].refresh_from_db()
        self.assertEqual(self.people['finance'].owning_organisation_id, self.org.id)
        self.people['partner'].refresh_from_db()
        self.alone(self.people['partner'], lambda org: None)
        self.people['partner'].refresh_from_db()
        self.assertIsNone(self.people['partner'].owning_organisation_id)


class ReverseSweep(TestCase):
    """The vocabulary, from the api side (lessons.md 2026-09-19: the reverse sweep is derived)."""

    def test_every_catalogue_key_reaches_at_least_one_gate(self):
        named = {k for row in GOLDEN.values() for k in row['keys']}
        self.assertEqual(sorted(set(sp.CATALOGUE) - named), [])

    def test_no_row_names_a_key_the_catalogue_lacks(self):
        named = {k for row in GOLDEN.values() for k in row['keys']}
        self.assertEqual(sorted(named - set(sp.CATALOGUE)), [])

    def test_every_row_answers_every_role(self):
        for gate, row in GOLDEN.items():
            with self.subTest(gate=gate):
                self.assertEqual(set(row['today']), set(ROLES))
                self.assertTrue(set(row.get('diverges', {})) <= set(ROLES))

    def test_every_stored_role_resolves(self):
        roles = [r for r, _ in PartnerAdmin.ROLE_CHOICES]
        # Source sign-in S1 (2026-10-30): `source_partner` is outside this table — it reaches no
        # staff gate at all (deny by default, `test_source_user_denied_everywhere.py`) and holds
        # nothing, which is asserted here instead of in every golden row.
        self.assertEqual(sorted(set(roles) - {'source_partner'}), sorted(ROLES))
        self.assertEqual(PartnerAdmin(role='source_partner').permission_set, ())
        for role in roles:
            with self.subTest(role=role):
                a = PartnerAdmin(role=role, is_super_admin=(role == 'super'))
                held = a.permission_set
                self.assertTrue(set(held) <= set(sp.CATALOGUE))
        self.assertEqual(sorted(sp.PRESETS), sorted(sp.TEAM_ROLES))
        self.assertEqual(
            sorted(set(sp.TEAM_ROLES) | {'org_admin', 'super', 'partner', 'source_partner'}),
            sorted(roles))

    def test_every_s2_row_names_the_ruling_and_keeps_what_it_was(self):
        for gate, row in GOLDEN.items():
            if 's2' not in row:
                self.assertNotIn('was', row, gate)
                continue
            with self.subTest(gate=gate):
                self.assertTrue(row['s2'].startswith(S2_RULING))
                self.assertEqual(set(row['was']), set(ROLES))

    def test_the_s2_rows_are_exactly_the_payment_chain(self):
        s2 = sorted(g for g, row in GOLDEN.items() if 's2' in row)
        self.assertEqual(s2, ['check_email_goes_to', 'check_step_armed_by',
                              'check_step_served_on_a_run', 'countersign_email_goes_to',
                              'other_active_finance', 'sign_the_approval', 'sign_the_check',
                              'switch_refused_for_unfinished_run'])
