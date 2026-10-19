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
   is written down in `diverges` with its reason — never silently absorbed. Today there are exactly
   two kinds: R1 (the super's wider choice of assignee, kept as a super override, roadmap R1) and one
   Sprint 3 finding on the Reviewers tab.

⚠ SPRINT 2 CHANGES ONLY THE ROWS MARKED `s2`, and each names the owner's ruling of 2026-10-19
("Finance role ... I would like the role to be able to approve payment — the work that Suresh does
today"): Finance APPROVES runs, the organisation admin stops countersigning and becomes the fallback
approver, and no preset holds the CHECK any more. Every other row must stay exactly as it is.

The reverse sweep (`ReverseSweep`) holds the vocabulary: every catalogue key reaches at least one row,
every stored role resolves, and no row names a key the catalogue does not have.
"""
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
      'wider choice is kept as a super override, and "assignment grants write" is unchanged. '
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
        'where': 'services/assignment.py _can_review (REVIEW_ROLES)',
        'keys': ('review',),
        'today': _t('super', 'org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: a.has_perm('review'),
        'diverges': {'org_admin': R1, 'admin': R1, 'qc': R1},
    },
    'propose_interview_times': {
        'where': 'scheduling.py _can_review (REVIEW_ROLES)',
        'keys': ('review',),
        'today': _t('super', 'org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: a.has_perm('review'),
        'diverges': {'org_admin': R1, 'admin': R1, 'qc': R1},
    },
    'pause_target': {
        'where': 'services/assignment.py set_paused (REVIEW_ROLES)',
        'keys': ('review',),
        'today': _t('super', 'org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: a.has_perm('review'),
        'diverges': {'org_admin': R1, 'admin': R1, 'qc': R1},
    },
    'assignable_list_for_super': {
        'where': 'views_admin/lifecycle.py AdminAssignableAdminsView (role__in), read by a super',
        'keys': ('review',),
        'today': _t('super', 'org_admin', 'admin', 'qc', 'reviewer'),
        'rule': lambda a, c: a.has_perm('review'),
        'diverges': {'org_admin': R1, 'admin': R1, 'qc': R1},
    },
    'org_admin_may_assign_to': {
        'where': 'views_admin/verdict.py:520 AdminAssignReviewerView (an org_admin assigns only a reviewer)',
        'keys': ('review',),
        'today': _t('reviewer'),
        'rule': lambda a, c: (a.has_perm('review')
                              and a.owning_organisation_id == c.org.id),
    },
    'reviewers_tab_lists': {
        'where': 'views_admin/reviewers.py _reviewers (role__in reviewer, qc; + is_super_admin)',
        'keys': ('review', 'qc'),
        'today': _t('super', 'qc', 'reviewer'),
        'rule': lambda a, c: a.has_perm('review') or a.has_perm('qc'),
        'diverges': {'org_admin': (
            'SPRINT 3 FINDING: the roadmap says "people who hold review or qc appear on Reviewers", '
            'but the lead tier holds qc and an org_admin is NOT on the Reviewers tab today. S3 must '
            'exclude the lead tier (or the owner must accept org_admins appearing there).')},
    },
    # ── D. spending ─────────────────────────────────────────────────────────────────────────────
    'spending_page': {
        'where': 'views_admin/spending.py _SPENDING_ROLES',
        'keys': ('spending',),
        'today': _t('super', 'org_admin', 'admin'),
        'rule': lambda a, c: a.has_perm('spending'),
    },
    # ── E. payments ─────────────────────────────────────────────────────────────────────────────
    'payments_read': {
        'where': 'views_admin/payments.py _PAYMENTS_READ_ROLES',
        'keys': ('payments_prepare', 'payments_check', 'payments_approve'),
        'today': _t('super', 'org_admin', 'admin', 'finance'),
        'rule': lambda a, c: _any_payments(a),
    },
    'payments_write': {
        'where': 'views_admin/payments.py _PAYMENTS_WRITE_ROLES (create / edit item / cancel)',
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
        'where': 'payments.py sign at admin_signed with the check armed',
        'keys': ('payments_check',),
        'today': _t('super', 'finance'),
        'rule': lambda a, c: a.has_perm('payments_check'),
        's2': S2_RULING + ' — after S2 no preset holds payments_check (dormant until granted).',
    },
    'sign_the_approval': {
        'where': 'payments.py sign at finance_checked (the countersignature that completes the run)',
        'keys': ('payments_approve',),
        'today': _t('super', 'org_admin'),
        'rule': lambda a, c: a.has_perm('payments_approve'),
        's2': S2_RULING + ' — after S2 finance approves; org_admin only under the fallback.',
    },
    'check_step_armed_by': {
        'where': 'payments.py finance_check_required (an organisation whose only active member is X)',
        'keys': ('payments_check',),
        'today': _t('finance'),
        'rule': lambda a, c: c.alone(a, lambda org: bool(sp.holders(org, 'payments_check'))),
        's2': S2_RULING + ' — re-keyed to "an active member holds payments_check"; wallet credits '
                          'keep the finance-role rule (credit_check_required).',
    },
    # ── G. the team (lead tier: stays on role in #39, so the key maps but never converts) ────────
    'may_invite_staff': {
        'where': 'courses/views_staff.py AdminInviteView (who may invite)',
        'keys': ('manage_team',),
        'today': _t('super', 'org_admin'),
        'rule': lambda a, c: a.has_perm('manage_team'),
    },
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
        # Armed: this organisation has an active finance member (the table's own finance person).
        return self._sign(a, 'admin_signed', admin_signed_email='maker@elsewhere.test')

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

    def test_the_lone_member_probe_restores_the_organisation(self):
        # The `check_step_armed_by` row moves a person; the other rows must not see it.
        self.assertTrue(self.probe_check_step_armed_by(self.people['finance']))
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
        self.assertEqual(sorted(roles), sorted(ROLES))
        for role in roles:
            with self.subTest(role=role):
                a = PartnerAdmin(role=role, is_super_admin=(role == 'super'))
                held = a.permission_set
                self.assertTrue(set(held) <= set(sp.CATALOGUE))
        self.assertEqual(sorted(sp.PRESETS), sorted(sp.TEAM_ROLES))
        self.assertEqual(sorted(set(sp.TEAM_ROLES) | {'org_admin', 'super', 'partner'}),
                         sorted(roles))

    def test_the_s2_rows_are_exactly_the_payment_chain(self):
        s2 = sorted(g for g, row in GOLDEN.items() if 's2' in row)
        self.assertEqual(s2, ['check_step_armed_by', 'sign_the_approval', 'sign_the_check'])
