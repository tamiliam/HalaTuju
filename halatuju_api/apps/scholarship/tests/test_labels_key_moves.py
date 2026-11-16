"""Sprint LABELS: the hand-granted key sets whose answers MOVE, each declared (the standard presets do not
move: `test_labels_preset_pins.py`).

TD-621: each Overview section opens on its keys (`programme_overview.SECTION_KEYS`), no longer on the role.
TD-622: who may hold a case is the target's keys, `review` or `see_all` (`services.is_review_target`), no
longer the R1 roles; the super's picker lists by the same keys.

No real people: every row here is synthetic.
"""
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses import staff_tables
from apps.courses.models import PartnerAdmin
from apps.scholarship import overview_layout, programme_overview as po
from apps.scholarship.services import assignment
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_org

ASSIGNABLE = '/api/v1/admin/scholarship/assignable-admins/'
APPLICANT = ('funnel', 'attention', 'applications_series')


class EverySectionHasAKey(TestCase):
    def test_every_section_the_page_can_show_names_its_keys(self):
        self.assertEqual(set(po.SECTION_KEYS), {*overview_layout.CUSTOMISABLE, *po.PAGES})
        self.assertEqual(set(po.FULL), set(overview_layout.CUSTOMISABLE))
        for section, keys in po.SECTION_KEYS.items():
            with self.subTest(section=section):
                self.assertTrue(keys)
                for key in keys:
                    sp.holds(None, key)          # an unknown key raises

    def test_no_role_table_is_left(self):
        for name in ('SECTIONS_BY_ROLE', 'KEYED_ROWS'):
            self.assertFalse(hasattr(po, name), name)
        self.assertFalse(hasattr(assignment, 'R1_SUPER_TARGET_ROLES'))


class TheOverviewMovesForHandGrantedKeys(TestCase):
    """Declared moves: each row was answered by its LABEL before, and is answered by its KEYS now."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()

    def custom(self, role, keys):
        return make_admin(role, owning_org=self.org, permissions=keys)

    def test_an_admin_invited_since_t2_gets_no_money_without_a_money_key(self):
        # Was FULL by the `admin` label. The invitation's start set (`see_all`, `scholars` + its pages)
        # opens neither Spending nor Payments, so the Overview's money no longer opens either.
        a = self.custom('admin', staff_tables.invite_permissions('admin'))
        self.assertEqual(po.sections_for(a), APPLICANT)

    def test_an_admin_without_see_all_gets_no_applicant_widgets(self):
        self.assertEqual(po.sections_for(self.custom('admin', ['spending', 'payments_prepare'])),
                         ('money', 'money_series'))

    def test_a_reviewer_with_see_all_and_spending_gets_the_widgets_and_keeps_her_page(self):
        # Was `('mine',)` by the label (R2, preset-bound).
        self.assertEqual(po.sections_for(self.custom('reviewer', ['review', 'see_all', 'spending'])),
                         (*po.FULL, 'mine'))

    def test_qc_alone_gets_no_applicant_widgets(self):
        # QC's own `see_all` is not an Admins hat: the preset stays `('qc',)`.
        self.assertEqual(po.sections_for(self.custom('qc', ['see_all', 'qc'])), ('qc',))

    def test_qc_given_spending_sits_at_admins_so_their_see_all_opens_the_widgets(self):
        # Declared: `spending` seats them at Admins, where the `see_all` they hold counts (was `('qc',)`).
        self.assertEqual(po.sections_for(self.custom('qc', ['see_all', 'qc', 'spending'])),
                         (*po.FULL, 'qc'))

    def test_finance_given_see_all_gets_the_applicant_widgets(self):
        self.assertEqual(po.sections_for(self.custom('finance', ['payments_approve', 'see_all'])), po.FULL)

    def test_a_qc_given_review_gets_both_pages(self):
        self.assertEqual(po.sections_for(self.custom('qc', ['see_all', 'qc', 'review'])), ('qc', 'mine'))

    def test_an_admin_given_review_gets_their_own_page_too(self):
        keys = ['see_all', 'scholars', 'spending', 'payments_prepare', 'review']
        self.assertEqual(po.sections_for(self.custom('admin', keys)), (*po.FULL, 'mine'))

    def test_an_org_admin_without_spending_but_a_payment_key_gets_the_money(self):
        lead = make_admin('org_admin', owning_org=self.org)
        kept = [k for k in lead.permissions if k != 'spending'] + ['payments_approve']
        PartnerAdmin.objects.filter(pk=lead.pk).update(permissions=kept)
        self.assertEqual(po.sections_for(PartnerAdmin.objects.get(pk=lead.pk)), po.FULL)

    def test_the_lead_and_the_super_never_get_the_personal_pages(self):
        lead = make_admin('org_admin', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=lead.pk).update(permissions=['review', *lead.permissions])
        self.assertEqual(po.sections_for(PartnerAdmin.objects.get(pk=lead.pk)), po.FULL)
        self.assertEqual(po.sections_for(make_admin('super', super_admin=True)), po.FULL)


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class WhoMayHoldACaseMovesForHandGrantedKeys(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.super = make_admin('super', super_admin=True)

    def custom(self, role, keys):
        return make_admin(role, owning_org=self.org, permissions=keys, first_seen_at=timezone.now())

    def listed(self):
        return {r['id'] for r in authed_client(self.super).get(ASSIGNABLE).json()['admins']}

    def test_finance_given_see_all_may_hold_a_case_and_is_listed(self):
        # Was no target (the `finance` label was not an R1 role); `see_all` opens the case.
        fin = self.custom('finance', ['payments_approve', 'see_all'])
        self.assertTrue(assignment.is_review_target(fin))
        self.assertFalse(assignment.may_assign_to(self.super, fin))   # not in Reviewers
        self.assertIn(fin.id, self.listed())

    def test_finance_given_qc_may_be_given_a_case_by_a_super(self):
        fin = self.custom('finance', ['payments_approve', 'qc'])      # `qc` brings `see_all`, seats Reviewers
        self.assertTrue(assignment.is_review_target(fin))
        self.assertTrue(assignment.may_assign_to(self.super, fin))

    def test_a_reviewer_label_with_see_all_and_no_review_may_hold_a_case(self):
        rv = self.custom('reviewer', ['see_all'])
        self.assertTrue(assignment.is_review_target(rv))
        self.assertTrue(assignment.may_assign_to(self.super, rv))      # in Reviewers by the label (T1)

    def test_rows_holding_neither_key_leave_the_picker(self):
        # Were listed by the label (bug #66) and never offered; the web names a holder the list lacks.
        rows = [self.custom('admin', ['payments_prepare']), self.custom('qc', []),
                self.custom('reviewer', ['spending'])]
        listed = self.listed()
        for a in rows:
            with self.subTest(role=a.role):
                self.assertFalse(assignment.is_review_target(a))
                self.assertNotIn(a.id, listed)
