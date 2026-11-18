"""Sprint LABELS: the hand-granted key sets whose answers MOVE, each declared (the standard presets do not
move: `test_labels_preset_pins.py`).

TD-621: each Overview section opens on its keys (`programme_overview.SECTION_KEYS`), no longer on the role.
TD-622: who may hold a case is the target's keys, `review` or `see_all` (`services.is_review_target`), no
longer the R1 roles; the super's picker lists by the same keys.

No real people: every row here is synthetic.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses import staff_tables
from apps.courses.models import PartnerAdmin
from apps.scholarship import overview_layout, programme_overview as po
from apps.scholarship.models import AssignmentEvent
from apps.scholarship.services import PauseError, assignment, set_paused
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)

ASSIGNABLE = '/api/v1/admin/scholarship/assignable-admins/'
APPLICANT = ('funnel', 'attention', 'applications_series')
# LL1: `ai_prediction` is a FIXED section (not customisable): it follows `see_all`, `qc` or `review`, the keys
# whose B40 scope is not 'none', and is served after the widgets and before the personal pages.
AI = 'ai_prediction'
FULL_AI = (*po.FULL, AI)


class EverySectionHasAKey(TestCase):
    def test_every_section_the_page_can_show_names_its_keys(self):
        self.assertEqual(set(po.SECTION_KEYS), {*overview_layout.CUSTOMISABLE, *po.PAGES, AI})
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

    def test_the_default_admin_invitation_gets_no_money_until_a_money_key_is_ticked(self):
        # DECLARED, AND THE DEFAULT: this is not a hand-granted set. Every Admin invited since T2 starts on
        # `staff_tables.INVITE_START` (`see_all`, `scholars`, and `scholars`' pages), with no money key.
        # Was FULL by the `admin` label; that set opens neither Spending nor Payments, so the Overview's
        # money no longer opens either. The owner was told and accepted it under "permissions decide".
        self.assertEqual(staff_tables.INVITE_START, {'admin': ('see_all', 'scholars')})
        start = staff_tables.invite_permissions('admin')
        self.assertFalse(set(po.MONEY_KEYS) & set(start))
        self.assertEqual(po.sections_for(self.custom('admin', start)), (*APPLICANT, AI))
        # One money key ticked brings the money back.
        self.assertEqual(po.sections_for(self.custom('admin', [*start, 'spending'])), FULL_AI)

    def test_an_admin_without_see_all_gets_no_applicant_widgets(self):
        self.assertEqual(po.sections_for(self.custom('admin', ['spending', 'payments_prepare'])),
                         ('money', 'money_series'))

    def test_a_reviewer_with_see_all_and_spending_gets_the_widgets_and_keeps_her_page(self):
        # Was `('mine',)` by the label (R2, preset-bound).
        self.assertEqual(po.sections_for(self.custom('reviewer', ['review', 'see_all', 'spending'])),
                         (*FULL_AI, 'mine'))

    def test_qc_alone_gets_no_applicant_widgets(self):
        # QC's own `see_all` is not an Admins hat: the preset stays `('qc',)`.
        self.assertEqual(po.sections_for(self.custom('qc', ['see_all', 'qc'])), (AI, 'qc'))

    def test_qc_given_spending_gets_the_money_but_never_the_applicant_widgets(self):
        # Review round: `spending` seats them at Admins, but QC's `see_all` is what `qc` brings, never an
        # Admins hat (`staff_tables.admin_keys` drops it), so only the money opens (was `('qc',)`).
        self.assertEqual(po.sections_for(self.custom('qc', ['see_all', 'qc', 'spending'])),
                         ('money', 'money_series', AI, 'qc'))

    def test_qc_given_any_other_admin_seat_never_opens_the_applicant_widgets(self):
        # Review round: whatever seats a QC person at Admins (a money key, `scholars`, a stored page key),
        # their `see_all` stays QC's. A page key opens no section here; the preset answer stands.
        for extra, served in ((['payments_approve'], ('money', 'money_series', AI, 'qc')),
                              (['scholars'], (AI, 'qc')),
                              (['team.view'], (AI, 'qc')),
                              (['announcements.view'], (AI, 'qc')),
                              (['sponsors.view'], (AI, 'qc'))):
            with self.subTest(extra=extra):
                row = self.custom('qc', ['see_all', 'qc', *extra])
                self.assertTrue(staff_tables.in_admins(row))
                self.assertEqual(po.sections_for(row), served)

    def test_a_saved_qc_alone_reads_as_the_preset(self):
        # `['qc']` is stored; `qc` brings `see_all`, which is still not an Admins hat.
        self.assertEqual(po.sections_for(self.custom('qc', ['qc'])), (AI, 'qc'))

    def test_finance_given_see_all_gets_the_applicant_widgets(self):
        self.assertEqual(po.sections_for(self.custom('finance', ['payments_approve', 'see_all'])), FULL_AI)

    def test_a_qc_given_review_gets_both_pages(self):
        self.assertEqual(po.sections_for(self.custom('qc', ['see_all', 'qc', 'review'])), (AI, 'qc', 'mine'))

    def test_an_admin_given_review_gets_their_own_page_too(self):
        keys = ['see_all', 'scholars', 'spending', 'payments_prepare', 'review']
        self.assertEqual(po.sections_for(self.custom('admin', keys)), (*FULL_AI, 'mine'))

    def test_an_org_admin_without_spending_but_a_payment_key_gets_the_money(self):
        lead = make_admin('org_admin', owning_org=self.org)
        kept = [k for k in lead.permissions if k != 'spending'] + ['payments_approve']
        PartnerAdmin.objects.filter(pk=lead.pk).update(permissions=kept)
        self.assertEqual(po.sections_for(PartnerAdmin.objects.get(pk=lead.pk)), FULL_AI)

    def test_the_lead_and_the_super_never_get_the_personal_pages(self):
        lead = make_admin('org_admin', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=lead.pk).update(permissions=['review', *lead.permissions])
        self.assertEqual(po.sections_for(PartnerAdmin.objects.get(pk=lead.pk)), FULL_AI)
        self.assertEqual(po.sections_for(make_admin('super', super_admin=True)), FULL_AI)


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

    def test_a_reviewer_label_given_qc_alone_is_a_valid_holder(self):
        # DECLARED (review round): `['qc']` is stored as `see_all` + `qc` (`qc` brings `see_all`), so a
        # Reviewer-label row moved from `review` to `qc` can still hold a case, be given one and be paused.
        rv = self.custom('reviewer', ['qc'])
        self.assertEqual(set(rv.permission_set), {'see_all', 'qc'})
        self.assertTrue(assignment.is_review_target(rv))
        self.assertTrue(assignment.holder_can_review(rv))
        self.assertTrue(assignment.may_assign_to(self.super, rv))
        self.assertTrue(assignment.may_pause(rv))
        self.assertIn(rv.id, self.listed())

    def test_rows_holding_neither_key_leave_the_picker(self):
        # Were listed by the label (bug #66) and never offered; the web names a holder the list lacks.
        rows = [self.custom('admin', ['payments_prepare']), self.custom('qc', []),
                self.custom('reviewer', ['spending'])]
        listed = self.listed()
        for a in rows:
            with self.subTest(role=a.role):
                self.assertFalse(assignment.is_review_target(a))
                self.assertNotIn(a.id, listed)


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class PauseIsOfferedOnlyWhereACaseCouldBeHanded(TestCase):
    """Review round (item 4): pause stops NEW work, so `pausable` and `set_paused` ask what `may_hand_to`
    asks of the target (`assignment.may_pause`: in Reviewers and a review target). A switch that pauses
    somebody nobody can hand a case to would be a control that lies."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.lead = make_admin('org_admin', owning_org=cls.org)

    def custom(self, role, keys=None):
        if keys is None:
            return make_admin(role, owning_org=self.org)
        return make_admin(role, owning_org=self.org, permissions=keys)

    def refused(self, a):
        self.assertFalse(assignment.may_pause(a))
        with self.assertRaises(PauseError) as caught:
            set_paused(a, True)
        self.assertEqual(caught.exception.code, 'not_reviewable')
        a.refresh_from_db()
        self.assertIsNone(a.paused_at)

    def test_finance_given_see_all_may_hold_a_case_but_is_not_pausable(self):
        fin = self.custom('finance', ['payments_approve', 'see_all'])
        self.assertTrue(assignment.is_review_target(fin))      # can open a case it already holds
        self.assertFalse(staff_tables.in_reviewers(fin))        # but is never handed a new one
        self.refused(fin)
        # The person page that serves `pausable` lists Reviewers only, so this row is not served at all.
        r = authed_client(self.lead).get(f'/api/v1/admin/reviewers/{fin.pk}/')
        self.assertEqual(r.status_code, 404)

    def test_the_admin_preset_is_not_pausable(self):
        # Declared: was accepted (it holds `see_all`, R1), though since T1 nobody can hand it a case.
        self.refused(self.custom('admin'))

    def test_a_super_and_an_organisation_admin_outside_reviewers_are_not_pausable(self):
        self.refused(make_admin('super', super_admin=True))
        self.refused(PartnerAdmin.objects.get(pk=self.lead.pk))

    def test_everyone_a_case_can_be_handed_to_is_pausable_and_served_so(self):
        client = authed_client(self.lead)
        for a in (self.custom('reviewer'), self.custom('qc'), self.custom('reviewer', ['qc']),
                  self.custom('finance', ['payments_approve', 'review'])):
            with self.subTest(role=a.role, keys=a.permissions):
                self.assertTrue(assignment.may_pause(a))
                self.assertIs(client.get(f'/api/v1/admin/reviewers/{a.pk}/').json()['pausable'], True)
                r = client.post(f'/api/v1/admin/reviewers/{a.pk}/pause/', {'paused': True}, format='json')
                self.assertEqual(r.status_code, 200, r.content[:200])
                set_paused(PartnerAdmin.objects.get(pk=a.pk), False)     # and back again


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ASuperGivesACaseOnlyWithinItsOrganisation(TestCase):
    """Review round (item 6): `may_hand_to` asks a super no organisation, and the super's picker lists
    every organisation's Reviewers. A case handed across would be stranded: its holder could never open
    it (`_AdminBase._org_allows`). `assign_reviewer` now refuses a new holder of another organisation."""

    @classmethod
    def setUpTestData(cls):
        cls.org_a, cls.org_b = make_org(), make_org()
        cls.cohort = make_cohort(owning_organisation=cls.org_a)
        cls.super = make_admin('super', super_admin=True)
        seen = timezone.now()
        cls.near = make_admin('reviewer', owning_org=cls.org_a, first_seen_at=seen)
        cls.far = make_admin('reviewer', owning_org=cls.org_b, first_seen_at=seen)

    def post(self, app, target):
        with patch('apps.scholarship.services.assignment.is_ready_for_assignment', return_value=True):
            return authed_client(self.super).post(
                f'/api/v1/admin/scholarship/applications/{app.id}/assign/', {'reviewer_id': target.id},
                format='json')

    def test_another_organisation_s_reviewer_is_refused(self):
        app = make_application('profile_complete', cohort=self.cohort)
        self.assertTrue(assignment.may_assign_to(self.super, self.far))   # the rule asks no organisation
        r = self.post(app, self.far)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_reviewer'))
        app.refresh_from_db()
        self.assertIsNone(app.assigned_to_id)
        self.assertFalse(AssignmentEvent.objects.filter(application=app).exists())
        # The reviewer could not have opened it.
        self.assertEqual(authed_client(self.far).get(
            f'/api/v1/admin/scholarship/applications/{app.id}/').status_code, 404)

    def test_the_case_s_own_organisation_s_reviewer_is_given_it(self):
        app = make_application('profile_complete', cohort=self.cohort)
        r = self.post(app, self.near)
        self.assertEqual(r.status_code, 200, r.content[:200])
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.near.id)

    def test_a_holder_of_another_organisation_is_still_a_no_op_re_pick(self):
        # T1-d: re-picking the CURRENT holder never refuses (a case already held is never taken away).
        app = make_application('profile_complete', cohort=self.cohort)
        app.assigned_to = self.far
        app.save(update_fields=['assigned_to'])
        self.assertEqual(self.post(app, self.far).status_code, 200)
