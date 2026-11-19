"""Sprint M3a (the one principle, 2026-11-14): when an organisation admin's powers become stored keys,
NOBODY's access changes.

Each live row shape is made as it stood BEFORE M3a (`pre_m3=True`; the two production shapes are an
organisation admin storing NULL and one storing ["review"]) and read with the OLD rules — copies of
`staff_permissions.resolve` (the fixed lead tier, plus `review` from Team -> Reviewers) and of
`staff_permissions_v2.effective_v2` (every v2 key for an active organisation admin) patched in for the
"before" read, so every reader built on them answers as the old image did. The rows are then put through
migration 0098's `plan_row` and read with the NEW code. Compared, per shape: the old keys, the v2 page keys,
the menu, the tables, every door, the pending cards, the overview sections, the Reviewers seat, the
assignment rules, the payment approval gate and fallback, the key holders of the organisation, and the
admin route's `opens_elsewhere`. Then Restore, and the Team -> Reviewers Add / Remove round trip (A6).
S2 / M4a: the rows also go through 0100 (the powers key), the old read takes the powers from the role,
and the one owner-ruled difference is the display-only change `factories.M4A_DISPLAY_ONLY` names.
"""
import copy
from contextlib import ExitStack
from importlib import import_module
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.scholarship import my_pending, payments_chain, programme_overview, staff_person
from apps.scholarship.services import assignment
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, m4a_display, make_admin, make_org,
)

M0098 = import_module('apps.courses.migrations.0098_store_org_admin_keys')
M0099 = import_module('apps.courses.migrations.0099_grant_scholars_approve')   # M3c: run after 0098
M0100 = import_module('apps.courses.migrations.0100_store_org_admin_powers')    # M4a: run after 0099
REAL_RESOLVE = sp.resolve
REAL_EFFECTIVE = v2.effective_v2
#: The old keys whose holders the payment, withdrawal and review gates count.
HOLDER_KEYS = ('payments_prepare', 'payments_check', 'payments_approve', 'award_withdraw_approve',
               'see_all', 'scholars', 'qc', 'spending', 'review', 'manage_team')


def _old_resolve(a):
    """`staff_permissions.resolve` before M3a: an organisation admin read as the fixed lead tier (the stored
    list ignored but for `review`)."""
    if a is not None and not a.is_super and a.role == sp.LEAD_ROLE:
        return sp._ordered((*sp.LEAD_TIER, *(('review',) if sp.lead_reviews(a) else ())))
    return REAL_RESOLVE(a)


def _old_effective(a):
    """`staff_permissions_v2.effective_v2` before M3a: an ACTIVE organisation admin held every v2 key
    (`lead_v2`); everybody else read as today (M3a changed no other branch)."""
    if a is not None and not a.is_super and a.is_active and a.role == sp.LEAD_ROLE:
        return v2.v2_order((*v2.CATALOGUE_V2, *(('qc', 'review') if sp.lead_reviews(a) else ('qc',))))
    return REAL_EFFECTIVE(a)


def _old_opens_elsewhere(viewer, target):
    """`staff_person.opens_elsewhere` before M3a: the admin route opened by role."""
    if viewer is None or target is None or target.is_mentor:
        return False
    from apps.courses.staff_fence import staff_target_readable
    if (viewer.is_super or sp.is_lead_tier(viewer)) and staff_target_readable(viewer, target):
        return True
    return _rest_of_opens_elsewhere(viewer, target)


def _rest_of_opens_elsewhere(viewer, target):
    """The reviewer-route half of `opens_elsewhere`, unchanged by M3a."""
    from apps.scholarship import surface_gates
    if not surface_gates.may_read_team(viewer):
        return False
    if not viewer.is_super and (viewer.owning_organisation_id is None
                                or target.owning_organisation_id != viewer.owning_organisation_id):
        return False
    return staff_person.on_reviewer_route(target)


def _m4a(read, a):
    """The old read with only the M4a display change (`factories.M4A_DISPLAY_ONLY`, owner-ruled) applied, for an
    active organisation admin holding the powers."""
    if not (a.is_active and sp.holds_org_admin_powers(a)):     # an inactive row reads no v2 key at all
        return read
    out = dict(read)
    for k in ('effective_v2', 'page_keys'):
        out[k] = m4a_display(read[k])
    return out


def _old_powers(a):
    """`staff_permissions.holds_org_admin_powers` before M4a: the powers were read from the role."""
    return a is not None and sp.is_lead_tier(a)


def _old_rules():
    stack = ExitStack()
    stack.enter_context(mock.patch.object(sp, 'resolve', _old_resolve))
    stack.enter_context(mock.patch.object(v2, 'effective_v2', _old_effective))
    stack.enter_context(mock.patch.object(sp, 'holds_org_admin_powers', _old_powers))
    return stack


def _run(org):
    return SimpleNamespace(organisation_id=org.pk, admin_signed_email='', finance_signed_email='',
                           org_admin_signed_email='', created_by='')


class NobodyChanges(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        org = cls.org

        def shape(role, keys=None, **kw):
            return make_admin(role, owning_org=org, pre_m3=True, permissions=keys, **kw)
        cls.shapes = {
            'org_admin, NULL (live shape 1)': shape('org_admin'),
            'org_admin, ["review"] (live shape 2)': shape('org_admin', ['review']),
            'org_admin, a leftover payment key': shape('org_admin', ['payments_approve', 'see_all']),
            'org_admin, a second one in the organisation': shape('org_admin'),
            'org_admin, revoked': shape('org_admin', is_active=False),
            'org_admin, revoked, ["review"]': shape('org_admin', ['review'], is_active=False),
            'org_admin, archived': shape('org_admin', is_active=False),
            'org_admin, pending (never signed in)': shape('org_admin'),
            'admin, stored': shape('admin', ['see_all', 'scholars', 'spending', 'payments_prepare']),
            'admin, NULL': shape('admin'),
            'admin with a stored lead-only key': shape('admin', ['see_all', 'scholars', 'manage_team']),
            'finance, stored': shape('finance', ['payments_approve']),
            'finance, NULL': shape('finance'),
            'reviewer, NULL': shape('reviewer'),
            'reviewer with admin keys': shape('reviewer', ['review', 'see_all', 'spending']),
            'qc, NULL': shape('qc'),
            'partner': shape('partner'),
            'super': make_admin('super', owning_org=org, super_admin=True, pre_m3=True),
        }
        now = timezone.now()
        signed_in = [a.pk for n, a in cls.shapes.items() if 'pending' not in n]
        PartnerAdmin.objects.filter(pk__in=signed_in).update(first_seen_at=now)
        PartnerAdmin.objects.filter(pk=cls.shapes['org_admin, archived'].pk).update(archived_at=now)
        cls.reviewer = cls.shapes['reviewer, NULL']

    def load(self, a):
        return PartnerAdmin.objects.get(pk=a.pk)

    def migrate(self, a):
        # M3c (D5): 0099 appends `scholars.approve` (the senior letters, until then by role) after 0098.
        # M4a: 0100 appends `organisation.admin` (the powers, until then by role) after 0099.
        for step in (M0098, M0099, M0100):
            a = self.load(a)
            plan = step.plan_row(a.role, a.permissions)
            if plan is not None:
                PartnerAdmin.objects.filter(pk=a.pk).update(permissions=plan[1])
        return self.load(a)

    def read(self, a):
        """Everything a row's access is made of, under whichever rules are in force."""
        out = {
            'resolve': sp.resolve(a),
            'effective_v2': v2.effective_v2(a),
            'page_keys': st.page_keys(a),
            'tables': st.tables(a),
            'doors': {d: st.opens_door(a, d) for d in st.DOOR_KEYS},
            'in_reviewers': st.in_reviewers(a),
            'in_admins': st.in_admins(a),
            'may_do_admin_work': st.may_do_admin_work(a),
            'sections': programme_overview.sections_for(a),
            'is_review_target': assignment.is_review_target(a),
            'super hands to them': assignment.may_hand_to(self.load(self.shapes['super']), a),
            'they hand to a reviewer': assignment.may_hand_to(a, self.reviewer),
            'may_approve a run': payments_chain._may_approve(_run(self.org), a),
        }
        if a.is_active:
            out['pending cards'] = my_pending.pending_for(a, b40_scope='all')
        return out

    def org_reads(self):
        return {
            'holders': {k: [h.pk for h in sp.holders(self.org, k)] for k in HOLDER_KEYS},
            'fallback_approvers': [a.pk for a in payments_chain.fallback_approvers(_run(self.org))],
            'approver_fallback': payments_chain.approver_fallback(_run(self.org)),
            'finance_check_required': payments_chain.finance_check_required(self.org),
        }

    def test_every_shape_reads_the_same_on_every_reader(self):
        rows = {n: self.load(a) for n, a in self.shapes.items()}
        with _old_rules():
            before = {n: self.read(a) for n, a in rows.items()}
            org_before = self.org_reads()
        migrated = {n: self.migrate(a) for n, a in rows.items()}
        after = {n: self.read(a) for n, a in migrated.items()}
        for name in rows:
            with self.subTest(shape=name):
                self.assertEqual(after[name], _m4a(before[name], migrated[name]))
        self.assertEqual(self.org_reads(), org_before)

    def test_the_two_live_shapes_become_the_planned_lists(self):
        full = [*sp.ORG_ADMIN_KEYS, *M0098.V2_KEYS, M0099.KEY, M0100.KEY]
        self.assertEqual(self.migrate(self.shapes['org_admin, NULL (live shape 1)']).permissions, full)
        self.assertEqual(self.migrate(self.shapes['org_admin, ["review"] (live shape 2)']).permissions,
                         ['review', *full])

    def test_opens_elsewhere_answers_the_same_for_every_viewer_and_target(self):
        rows = {n: self.load(a) for n, a in self.shapes.items()}
        with _old_rules():
            before = {(v, t): _old_opens_elsewhere(rows[v], rows[t]) for v in rows for t in rows}
        migrated = {n: self.migrate(a) for n, a in rows.items()}
        after = {(v, t): staff_person.opens_elsewhere(migrated[v], migrated[t]) for v in rows for t in rows}
        self.assertEqual(after, before)

    def test_a_revoked_org_admin_restored_after_the_migration_gets_back_what_it_had(self):
        for name in ('org_admin, revoked', 'org_admin, revoked, ["review"]', 'org_admin, archived'):
            with self.subTest(shape=name):
                restored_before = copy.copy(self.load(self.shapes[name]))
                restored_before.is_active = True
                with _old_rules():
                    old = self.read(restored_before)
                after = self.migrate(self.shapes[name])
                PartnerAdmin.objects.filter(pk=after.pk).update(is_active=True)
                restored = self.load(after)
                self.assertEqual(self.read(restored), _m4a(old, restored))

    def test_a_shape_the_migration_has_not_reached_still_reads_safely(self):
        # NULL is fail-safe: the new code reads it as the full set (A2), so a row the data step missed,
        # or one an old-image writer set back to NULL in the window, keeps every page.
        null = self.load(self.shapes['org_admin, NULL (live shape 1)'])
        with _old_rules():
            old = self.read(null)
        self.assertEqual(self.read(null), _m4a(old, null))      # M4a: NULL holds the powers too


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ReviewersRoundTrip(TestCase):
    """A6: Team -> Reviewers Add / Remove on a migrated organisation admin changes `review` alone."""

    def setUp(self):
        self.org = make_org()
        self.lead = make_admin('org_admin', owning_org=self.org)       # the shape 0098 leaves
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(first_seen_at=timezone.now())

    def act(self, action):
        r = authed_client(self.lead).post('/api/v1/admin/team/reviewers/', {
            'admin_id': self.lead.pk, 'action': action, 'dry_run': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        return PartnerAdmin.objects.get(pk=self.lead.pk)

    def test_add_then_remove_reads_as_the_old_rule_did_at_each_step(self):
        start = PartnerAdmin.objects.get(pk=self.lead.pk)
        with _old_rules():
            old_start = (sp.resolve(start), v2.effective_v2(start), st.tables(start))
        added = self.act('add')
        self.assertEqual(added.permissions, ['review', *start.permissions])    # M3c: 0099's order kept
        old_added = copy.copy(added)
        old_added.permissions = ['review']                              # what the old writer stored
        with _old_rules():
            expected = (sp.resolve(old_added), v2.effective_v2(old_added), st.tables(old_added))
        m4a = _m4a({'effective_v2': expected[1], 'page_keys': ()}, added)['effective_v2']   # M4a display
        self.assertEqual((sp.resolve(added), v2.effective_v2(added), st.tables(added)),
                         (expected[0], m4a, expected[2]))
        removed = self.act('remove')
        self.assertEqual(removed.permissions, start.permissions)
        m4a = _m4a({'effective_v2': old_start[1], 'page_keys': ()}, removed)['effective_v2']
        self.assertEqual((sp.resolve(removed), v2.effective_v2(removed), st.tables(removed)),
                         (old_start[0], m4a, old_start[2]))

    def test_add_on_a_null_row_stores_the_full_set_with_review(self):
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(permissions=None)
        self.assertEqual(self.act('add').permissions, ['review', *v2.ORG_ADMIN_FULL])     # M4a: the powers kept
        self.assertEqual(self.act('remove').permissions, list(v2.ORG_ADMIN_FULL))
