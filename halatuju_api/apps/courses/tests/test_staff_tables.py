"""Team tables T1: the derivation of a person's tables, and the page gate's doors (`staff_tables`).

The access matrix (`apps/scholarship/tests/test_team_tables_matrix.py`) proves the endpoints did not move;
this file pins the RULE: which table each shape sits at, that the gate is a UNION with today's roles
(nobody loses a page), that the key half admits only the Admins table, and that `see_all` held as `qc`'s
dependency is no admin hat.
"""
from importlib import import_module
from itertools import chain, combinations

from django.test import TestCase
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.scholarship.models import Mentor
from apps.scholarship.tests.factories import make_admin, make_org
_M0097 = import_module('apps.courses.migrations.0097_store_admin_v2_keys')   # M2b: same app


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
    """The union doors (`may_read_org`, `may_do_admin_work`) — v2 keys since T5c P1 (`opens`), answering
    exactly what T1's role rule (widened to the Admins table by a key) answered."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()

    def test_the_gate_answers_the_t1_role_rule_for_every_custom_set(self):
        # Every role × every custom set (unsaved rows: a pure read): T1's rule, restated, still answers
        # for the stored lists migration 0097 left (M2b: the label opens nothing by itself any more).
        for role in ('admin', 'finance', 'qc', 'reviewer', 'org_admin'):
            for keys in _subsets(('review', 'see_all', 'qc', 'spending', 'payments_approve')):
                a = PartnerAdmin(role=role, permissions=list(keys), is_active=True)
                plan = _M0097.plan_row(None, role, True, list(keys), row_id=None)  # M2b: the rows 0097 left
                a.permissions = plan[1] if plan else a.permissions
                read = role in ('org_admin', 'admin', 'finance') or st.in_admins(a)
                work = role in ('org_admin', 'admin')
                self.assertEqual((st.may_read_org(a), st.may_do_admin_work(a)), (read, work), (role, keys))

    def test_an_unknown_key_raises_and_no_key_opens_nothing(self):
        boss = make_admin('org_admin', owning_org=self.org)
        with self.assertRaises(KeyError):
            st.opens(boss, 'announcements.post')
        self.assertFalse(st.opens(boss))
        self.assertFalse(st.opens(None, 'team.view'))

    def test_the_key_half_admits_only_the_admins_table(self):
        rohini = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all', 'spending'])
        self.assertTrue(st.may_read_org(rohini))
        # T1 (conservative), kept by T5c: the admin WORK pages write, and no admin key opens them.
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
        # today), never the admin-work pages (announcements, sources, …) (owner ruling B, 2026-11-03):
        # no old key aliases to an admin-work v2 key — only the org_admin / admin labels hold them.
        for keys in (['review', 'payments_approve'], ['review', 'spending'], ['review', 'payments_prepare']):
            a = make_admin('reviewer', owning_org=self.org, permissions=keys)
            self.assertTrue(st.may_read_org(a), keys)
            self.assertFalse(st.may_do_admin_work(a), keys)

    def test_a_page_opens_by_its_own_key(self):
        rohini = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all', 'spending'])
        self.assertTrue(st.opens(rohini, 'sponsors.view'))           # the Admins table's read pages
        self.assertFalse(st.opens(rohini, 'sponsors.edit'))          # never a write
        self.assertFalse(st.opens(rohini, 'invitations.edit'))       # lead-only
        self.assertFalse(st.opens(rohini, 'sponsors.view', 'sponsors.edit'))   # all-of, never any-of

    def test_lead_only_gates_are_untouched(self):
        """Lead-only pages are not on keys yet (T5e): a person with every team key is still refused."""
        from apps.scholarship import surface_gates
        everything = make_admin('admin', owning_org=self.org,
                                permissions=[k for k in sp.CATALOGUE if k not in sp.LEAD_TIER_ONLY])
        self.assertFalse(surface_gates.may_open_contracts(everything))
        self.assertFalse(surface_gates.requests_role(everything))
        self.assertFalse(surface_gates.may_read_invoices(everything))
