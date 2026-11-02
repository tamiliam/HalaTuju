"""Team tables T1: the derivation of a person's tables, and the page gate's doors (`staff_tables`).

The access matrix (`apps/scholarship/tests/test_team_tables_matrix.py`) proves the endpoints did not move;
this file pins the RULE: which table each shape sits at, that the gate is a UNION with today's roles
(nobody loses a page), that the key half admits only the Admins table, and that `see_all` held as `qc`'s
dependency is no admin hat.
"""
from itertools import chain, combinations

from django.test import TestCase
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.scholarship.models import Mentor
from apps.scholarship.tests.factories import make_admin, make_org


def _subsets(keys):
    return chain.from_iterable(combinations(keys, n) for n in range(len(keys) + 1))


class Tables(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()

    def _a(self, role, **kw):
        if role != 'partner' and not kw.pop('no_org', False):
            kw.setdefault('owning_org', self.org)
        return make_admin(role, **kw)

    def test_each_preset_sits_where_its_label_says(self):
        self.assertEqual(st.tables(self._a('admin')), ('admins',))
        self.assertEqual(st.tables(self._a('finance')), ('admins',))
        self.assertEqual(st.tables(self._a('reviewer')), ('reviewers',))
        self.assertEqual(st.tables(self._a('qc')), ('reviewers',))   # see_all here is qc's, not an admin's

    def test_the_lead_tier_and_a_super_are_admins_only(self):
        # Owner 2026-10-19: org admins stay off the Reviewers list (T2 lets them join it).
        self.assertEqual(st.tables(self._a('org_admin')), ('admins',))
        self.assertEqual(st.tables(make_admin('super', super_admin=True)), ('admins',))
        self.assertEqual(st.tables(make_admin('reviewer', super_admin=True)), ('admins',))

    def test_a_reviewer_with_admin_keys_sits_at_both(self):
        rohini = self._a('reviewer', permissions=['review', 'see_all', 'spending'])
        self.assertEqual(st.tables(rohini), ('admins', 'reviewers'))
        self.assertEqual(st.admin_keys(rohini), ('see_all', 'spending'))

    def test_see_all_beside_qc_is_no_admin_hat(self):
        self.assertEqual(st.tables(self._a('reviewer', permissions=['review', 'see_all', 'qc'])), ('reviewers',))
        self.assertEqual(st.admin_keys(self._a('qc')), ())
        # …but any other admin key still seats them.
        self.assertEqual(st.tables(self._a('qc', permissions=['see_all', 'qc', 'spending'])),
                         ('admins', 'reviewers'))

    def test_an_admin_with_review_sits_at_both(self):
        self.assertEqual(st.tables(self._a('admin', permissions=['see_all', 'review'])), ('admins', 'reviewers'))
        self.assertEqual(st.tables(self._a('finance', permissions=['payments_approve', 'review'])),
                         ('admins', 'reviewers'))

    def test_a_label_keeps_its_table_whatever_the_custom_set(self):
        # Removing a seat is T2's door ("revoke instead"); T1 never unseats anybody.
        self.assertIn('admins', st.tables(self._a('admin', permissions=[])))
        self.assertIn('reviewers', st.tables(self._a('qc', permissions=[])))

    def test_nobody_outside_the_team_sits_anywhere(self):
        self.assertEqual(st.tables(self._a('partner', org=make_org())), ())
        self.assertEqual(st.tables(self._a('source_partner')), ())
        # A stored list on a non-team row is never read (sp.resolve answers nothing).
        self.assertEqual(st.tables(self._a('source_partner', permissions=['see_all', 'spending'])), ())
        self.assertEqual(st.tables(None), ())

    def test_a_revoked_person_sits_nowhere(self):
        for role in ('admin', 'finance', 'reviewer', 'qc', 'org_admin'):
            self.assertEqual(st.tables(self._a(role, is_active=False)), (), role)
        self.assertEqual(st.tables(self._a('reviewer', is_active=False,
                                           permissions=['review', 'see_all', 'spending'])), ())

    def test_mentors_is_mentors_now(self):
        mentor = self._a('mentor')
        self.assertEqual(st.tables(mentor), ('mentors',))
        lead = self._a('org_admin', mentor=Mentor.objects.create(organisation=self.org))
        self.assertEqual(st.tables(lead), ('admins', 'mentors'))
        stopped = Mentor.objects.create(organisation=self.org, deactivated_at=timezone.now())
        self.assertEqual(st.tables(self._a('reviewer', mentor=stopped)), ('reviewers',))
        # A finance row is never an active mentor (7d), so never at Mentors.
        self.assertEqual(st.tables(self._a('finance', mentor=Mentor.objects.create(organisation=self.org))),
                         ('admins',))


class PageGate(TestCase):
    """`admits`: today's role rule, OR the Admins table by a key — never instead."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()

    def test_the_gate_never_refuses_what_the_role_rule_admits(self):
        # Every role × every custom set: whoever today's role list admits is still admitted.
        for role in ('admin', 'finance', 'qc', 'reviewer', 'org_admin'):
            for keys in _subsets(('review', 'see_all', 'qc', 'spending', 'payments_approve')):
                a = PartnerAdmin(role=role, permissions=list(keys), is_active=True)   # unsaved: a pure read
                for roles in (st.ORG_READ_ROLES, st.ADMIN_WORK_ROLES):
                    if role in roles:
                        self.assertTrue(st.admits(a, roles=roles, admin_keys_any=st.ADMIN_KEYS), (role, keys))
                        self.assertTrue(st.admits(a, roles=roles), (role, keys))

    def test_the_key_half_admits_only_the_admins_table(self):
        rohini = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all', 'spending'])
        self.assertTrue(st.may_read_org(rohini))
        # T1 (conservative): the admin WORK pages write, and no admin key opens them yet.
        self.assertEqual(st.ADMIN_WORK_KEYS, ())
        self.assertFalse(st.may_do_admin_work(rohini))
        # The qc preset holds see_all but is not at the Admins table: it gains nothing.
        qc = make_admin('qc', owning_org=self.org)
        self.assertFalse(st.may_read_org(qc))
        self.assertFalse(st.may_do_admin_work(qc))
        # A plain reviewer, a partner, a source user and a mentor: nothing.
        for a in (make_admin('reviewer', owning_org=self.org), make_admin('partner', org=make_org()),
                  make_admin('source_partner', owning_org=self.org), make_admin('mentor', owning_org=self.org)):
            self.assertFalse(st.may_read_org(a), a.role)
            self.assertFalse(st.may_do_admin_work(a), a.role)

    def test_the_presets_are_reproduced(self):
        expect = {'org_admin': (True, True), 'admin': (True, True), 'finance': (True, False),
                  'qc': (False, False), 'reviewer': (False, False)}
        for role, (read, work) in expect.items():
            a = make_admin(role, owning_org=self.org)
            self.assertEqual((st.may_read_org(a), st.may_do_admin_work(a)), (read, work), role)
        s = make_admin('super', super_admin=True)
        self.assertEqual((st.may_read_org(s), st.may_do_admin_work(s)), (True, True))

    def test_an_action_key_alone_opens_no_admin_work(self):
        # payments_approve / spending are ACTIONS: they open the organisation READ pages (Finance does
        # today), never the admin-work pages (announcements, sources, …), which need see_all.
        for keys in (['review', 'payments_approve'], ['review', 'spending'], ['review', 'payments_prepare']):
            a = make_admin('reviewer', owning_org=self.org, permissions=keys)
            self.assertTrue(st.may_read_org(a), keys)
            self.assertFalse(st.may_do_admin_work(a), keys)

    def test_a_future_key_opens_a_page_by_being_named(self):
        rohini = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all', 'spending'])
        self.assertFalse(st.admits(rohini, roles=('org_admin',)))                         # lead-only
        self.assertTrue(st.admits(rohini, roles=('org_admin',), admin_keys_any=('spending',)))

    def test_lead_only_gates_are_untouched(self):
        """Lead-only pages never call `admits` with keys: a person with every team key is still refused."""
        from apps.scholarship import surface_gates
        everything = make_admin('admin', owning_org=self.org,
                                permissions=[k for k in sp.CATALOGUE if k not in sp.LEAD_TIER_ONLY])
        self.assertFalse(surface_gates.may_open_contracts(everything))
        self.assertFalse(surface_gates.requests_role(everything))
        self.assertFalse(surface_gates.may_read_invoices(everything))
