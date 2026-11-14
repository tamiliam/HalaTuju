"""Sprint M3b (2026-11-14): the organisation admin's page powers read KEYS, not the role, and nobody's access
changes but one rule (E3: nobody gives a case to themselves).

Every converted gate is asked for every row shape, as M3a's data step 0098 left it, and compared with the
role rule it replaced (`a super, or an organisation admin`). The pair gates (who may act on whom) are asked
for every caller and target, with the old caller arm (`caller.role == 'org_admin'`) patched back in for the
"before" read. Then the keys are shown to be what decides: an organisation admin whose stored list lacks a
key is refused that gate, and a team row that stores a lead-only key is still refused. Last, E3 at the
service, the endpoint and the picker, for a super and an organisation admin, and a case still given to an
organisation admin in Reviewers by somebody else.

No real people: every row is made by the factory and named by its role.
"""
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_fence
from apps.courses import staff_permissions_v2 as v2
from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.scholarship import programme_overview, staff_tables_admin, surface_gates
from apps.scholarship.models import AssignmentEvent
from apps.scholarship.services import AssignmentError, assign_reviewer
from apps.scholarship.services import assignment
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org, make_programme,
)

REAL_HAS_PERM = PartnerAdmin.has_perm
READY = 'apps.scholarship.services.assignment.is_ready_for_assignment'
PICKER = '/api/v1/admin/scholarship/assignable-admins/'

#: gate -> the predicate the endpoint asks now (M3b). Each replaced `admin.is_super or admin.role ==
#: 'org_admin'` (or `has_role(admin, 'super', 'org_admin')`, the same thing).
GATES = {
    'G1 manage_team (team, staff, reviewers pages)': lambda a: a.has_perm('manage_team'),
    'G2 invitations.edit': surface_gates.may_edit_invitations,
    'G3 settings.edit': surface_gates.may_edit_settings,
    'G3 the Overview layout': programme_overview.may_customise,
    'G4 programmes.edit': surface_gates.may_edit_programmes,
    'G5 assign (students.edit)': surface_gates.may_assign,
    'G5 students.edit': surface_gates.may_work_students,
    'G5 students.approve': surface_gates.may_decide,
    'G6 sponsors.approve': surface_gates.may_vet_sponsors,
    'G7 billing.view': surface_gates.may_read_billing,
    'G8 requests.view': surface_gates.requests_role,
    'G8 requests.edit': surface_gates.may_write_requests,
    'G8 requests.approve': surface_gates.may_decide_requests,
    'G9 contracts.view': surface_gates.may_open_contracts,
    'G9 contracts.edit': surface_gates.may_write_contracts,
}


def _old_gate(a):
    return a.is_super or a.role == 'org_admin'


def _old_has_perm(self, key):
    """The caller arm before M3b G1: `caller.role == 'org_admin'` where the code now asks manage_team."""
    if key == 'manage_team':
        return self.role == 'org_admin'
    return REAL_HAS_PERM(self, key)


def _old_may_hand_to(caller, target):
    """`assignment.may_hand_to` before M3b, copied: no self rule, and the organisation admin by role."""
    if not (st.in_reviewers(target) and assignment.is_review_target(target)):
        return False
    if caller.is_super:
        return True
    return caller.role == 'org_admin' and target.owning_organisation_id == caller.owning_organisation_id


class EveryGateReadsTheSame(TestCase):
    @classmethod
    def setUpTestData(cls):
        org, far = make_org(), make_org()
        cls.org = org

        def shape(role, keys=None, owner=org, **kw):
            return make_admin(role, owning_org=owner, permissions=keys, **kw)
        cls.shapes = {
            'org_admin (0098 shape)': shape('org_admin'),
            'org_admin in Reviewers': shape('org_admin', ['review']),
            'org_admin, a second one': shape('org_admin'),
            'org_admin of another organisation': shape('org_admin', owner=far),
            'org_admin, revoked': shape('org_admin', is_active=False),
            'org_admin, archived': shape('org_admin', is_active=False),
            'admin, stored': shape('admin', ['see_all', 'scholars', 'spending', 'payments_prepare']),
            'admin with a stored manage_team': shape('admin', ['see_all', 'scholars', 'manage_team']),
            'admin storing lead-only v2 keys': shape('admin', ['see_all', 'settings.edit', 'students.edit',
                                                               'students.approve', 'requests.approve',
                                                               'contracts.edit', 'billing.view']),
            'finance': shape('finance', ['payments_approve']),
            'reviewer': shape('reviewer'),
            'reviewer of another organisation': shape('reviewer', owner=far),
            'reviewer with admin keys': shape('reviewer', ['review', 'see_all', 'spending']),
            'qc': shape('qc'),
            'partner': shape('partner'),
            'super': make_admin('super', owning_org=org, super_admin=True),
        }
        now = timezone.now()
        PartnerAdmin.objects.filter(pk__in=[a.pk for a in cls.shapes.values()]).update(first_seen_at=now)
        PartnerAdmin.objects.filter(pk=cls.shapes['org_admin, archived'].pk).update(archived_at=now)

    def rows(self):
        return {n: PartnerAdmin.objects.get(pk=a.pk) for n, a in self.shapes.items()}

    def test_every_converted_gate_answers_as_the_role_rule_did(self):
        # An inactive row never reaches a gate: `get_admin` refuses it first (it reads `is_active=True`).
        for name, a in self.rows().items():
            if not a.is_active:
                continue
            for gate, new in GATES.items():
                with self.subTest(shape=name, gate=gate):
                    self.assertEqual(bool(new(a)), _old_gate(a))

    def test_the_invoices_screen_answers_as_before_with_billing_on_and_off(self):
        for live in (False, True):
            with override_settings(BILLING_USAGE_ENABLED=live):
                for name, a in self.rows().items():
                    if a.is_active:
                        with self.subTest(shape=name, live=live):
                            self.assertEqual(surface_gates.may_read_invoices(a),
                                             a.is_super or (live and a.role == 'org_admin'))

    def test_the_pair_gates_answer_as_before_for_every_caller_and_target(self):
        rows = self.rows()
        pairs = [(c, t) for c in rows for t in rows if rows[c].is_active]     # `get_admin` refuses the rest

        def read():
            return {(c, t): (staff_fence.manageable_if_restored(rows[c], rows[t]),
                             staff_fence.staff_target_readable(rows[c], rows[t]),
                             staff_tables_admin.may_act(rows[c], rows[t], staff_tables_admin.ADMINS),
                             staff_tables_admin.may_act(rows[c], rows[t], staff_tables_admin.REVIEWERS))
                    for c, t in pairs}
        with mock.patch.object(PartnerAdmin, 'has_perm', _old_has_perm):
            before = read()
        self.assertEqual(read(), before)

    def test_the_hand_off_rule_changes_only_for_yourself(self):
        rows = self.rows()
        changed = []
        for c, caller in rows.items():
            if not caller.is_active:                    # `get_admin` refuses an inactive caller first
                continue
            for t, target in rows.items():
                old = _old_may_hand_to(caller, target)
                with self.subTest(caller=c, target=t):
                    self.assertEqual(assignment.may_hand_to(caller, target), old and caller.pk != target.pk)
                if old and caller.pk == target.pk:
                    changed.append(c)
        self.assertEqual(changed, ['org_admin in Reviewers'])      # E3 bites exactly where it should


class TheKeysDecide(TestCase):
    """The gate reads the stored key: a list without it is refused; a team row cannot store one."""

    def setUp(self):
        self.org = make_org()
        self.lead = make_admin('org_admin', owning_org=self.org)

    def without(self, *keys):
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(
            permissions=[k for k in v2.ORG_ADMIN_SET if k not in keys])
        return PartnerAdmin.objects.get(pk=self.lead.pk)

    def test_an_org_admin_without_a_key_is_refused_that_gate_and_keeps_the_others(self):
        # A key and every key that implies it go (`edit` / `approve` => `view`; `qc` => `see_all`).
        for keys, gate in ((('settings.edit',), surface_gates.may_edit_settings),
                           (('programmes.edit',), surface_gates.may_edit_programmes),
                           (('invitations.edit',), surface_gates.may_edit_invitations),
                           (('students.edit',), surface_gates.may_assign),
                           (('students.edit',), surface_gates.may_work_students),
                           (('students.approve',), surface_gates.may_decide),
                           (('sponsors.approve',), surface_gates.may_vet_sponsors),
                           (('requests.edit',), surface_gates.may_write_requests),
                           (('contracts.view', 'contracts.edit'), surface_gates.may_open_contracts),
                           (('contracts.edit',), surface_gates.may_write_contracts)):
            with self.subTest(keys=keys):
                lead = self.without(*keys)
                self.assertFalse(gate(lead))
                self.assertTrue(lead.has_perm('manage_team'))

    def test_the_by_role_keys_cannot_be_taken_away(self):
        # O15: manage_team, requests.approve and billing.edit are held BY ROLE, never stored, and the two
        # v2 ones bring their page's view: so the Requests list and the billing pages stay open.
        lead = self.without('requests.approve', 'requests.view', 'billing.view')
        self.assertTrue(lead.has_perm('manage_team'))
        self.assertTrue(surface_gates.may_decide_requests(lead))
        self.assertTrue(surface_gates.requests_role(lead))
        self.assertTrue(surface_gates.may_read_billing(lead))

    def test_without_students_edit_an_org_admin_hands_out_no_case(self):
        reviewer = make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now())
        self.assertTrue(assignment.may_hand_to(self.lead, reviewer))
        self.assertFalse(assignment.may_hand_to(self.without('students.edit'), reviewer))

    def test_the_overview_sections_follow_see_all_and_spending(self):
        full = programme_overview.sections_for(self.lead)
        self.assertIn('funnel', full)
        self.assertIn('money', full)
        no_see_all = programme_overview.sections_for(self.without('see_all', 'qc'))   # qc brings see_all
        self.assertFalse({'funnel', 'attention', 'applications_series'} & set(no_see_all))
        self.assertIn('money', no_see_all)
        no_spending = programme_overview.sections_for(self.without('spending'))
        self.assertFalse({'money', 'money_series'} & set(no_spending))
        self.assertIn('funnel', no_spending)


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class NobodyGivesACaseToThemselves(TestCase):
    """E3 (owner 2026-11-14), at the service, the endpoint and the picker."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.gift = make_programme(organisation=cls.org, name_en='Gift M3b')
        now = timezone.now()
        cls.boss = make_admin('super', super_admin=True, first_seen_at=now)
        cls.lead = make_admin('org_admin', owning_org=cls.org, permissions=['review'], first_seen_at=now)
        cls.fellow = make_admin('org_admin', owning_org=cls.org, first_seen_at=now)

    def case(self, **kw):
        return make_application('profile_complete', cohort=make_cohort(programme=self.gift), **kw)

    def post(self, caller, app, target):
        with mock.patch(READY, return_value=True):
            return authed_client(caller).post(f'/api/v1/admin/scholarship/applications/{app.id}/assign/',
                                              {'reviewer_id': target.id}, format='json')

    def test_the_org_admin_is_in_reviewers(self):
        self.assertTrue(st.in_reviewers(self.lead))

    def test_the_service_refuses_a_self_assignment(self):
        for who in (self.lead, self.boss):
            with self.subTest(caller=who.role):
                app = self.case()
                with mock.patch(READY, return_value=True), self.assertRaises(AssignmentError) as e:
                    assign_reviewer(app, reviewer=who, by_admin=who)
                self.assertEqual(e.exception.code, 'self_assign')
                app.refresh_from_db()
                self.assertIsNone(app.assigned_to_id)

    def test_the_endpoint_refuses_a_self_assignment(self):
        for who in (self.lead, self.boss):
            with self.subTest(caller=who.role):
                app = self.case()
                r = self.post(who, app, who)
                self.assertEqual((r.status_code, r.json()['code']), (400, 'self_assign'), r.content[:300])
                self.assertEqual(r.json()['error'], 'You cannot give a case to yourself.')
                self.assertFalse(AssignmentEvent.objects.filter(application=app).exists())

    def test_somebody_else_may_still_give_the_org_admin_a_case(self):
        for who in (self.boss, self.fellow):
            with self.subTest(caller=who.role):
                app = self.case()
                r = self.post(who, app, self.lead)
                self.assertEqual(r.status_code, 200, r.content[:300])
                self.assertEqual(r.json()['assigned_to_id'], self.lead.id)

    def test_a_case_already_held_is_not_refused_on_a_re_pick(self):
        # T1-d: re-saving the current holder is a no-op, so a case the org admin holds keeps its holder.
        app = self.case()
        self.post(self.fellow, app, self.lead)
        r = self.post(self.lead, app, self.lead)
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.lead.id)
        self.assertEqual(AssignmentEvent.objects.filter(application=app).count(), 1)

    def test_the_picker_lists_the_caller_but_never_offers_them(self):
        for who, offered in ((self.lead, False), (self.fellow, True), (self.boss, True)):
            with self.subTest(caller=who.role, offered=offered):
                rows = {r['id']: r for r in authed_client(who).get(PICKER).json()['admins']}
                self.assertIn(self.lead.id, rows)                  # listed: the cockpit names a holder (bug #66)
                self.assertIs(rows[self.lead.id]['assignable'], offered)
