"""Sprint M1a (team membership, 2026-11-10): the `member` role ("No group") and the archive columns.

Brief `docs/plans/2026-11-10-m1-staff-list-brief.md` §2 and §8. Courses 0096 recreates the
`partner_admin_mentor_iff_mentor` check with `member` in the role list; it is applied BY HAND to
production before the deploy, so `ConstraintShapesTest` proves the recreated check passes on EVERY
row shape production can hold today, and still refuses the two shapes it existed to refuse.
"""
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.courses.models_staff import MENTOR_LINK_ROLES, NOT_STAFF_ROLES, STAFF_MENTOR_ROLES
from apps.scholarship.models import Mentor
from apps.scholarship.tests.factories import make_admin, make_org

_CHECK = 'partner_admin_mentor_iff_mentor'


def _force(admin, **fields):
    """Write straight to the table (no model `save()` check), so only the DATABASE check decides."""
    PartnerAdmin.objects.filter(pk=admin.pk).update(**fields)


class ConstraintShapesTest(TestCase):
    """Every row shape alive in production on 2026-11-10, plus the two new ones, against the check."""

    def setUp(self):
        self.org = make_org()

    def _mentor(self):
        return Mentor.objects.create(organisation=self.org)

    def test_the_check_names_exactly_the_link_roles(self):
        check = next(c for c in PartnerAdmin._meta.constraints if c.name == _CHECK)
        self.assertIn(('role__in', MENTOR_LINK_ROLES), check.condition.children[1].children)
        self.assertEqual(MENTOR_LINK_ROLES,
                         ('mentor', 'org_admin', 'admin', 'reviewer', 'qc', 'finance', 'member'))

    def test_every_role_without_a_mentor_link_passes_except_mentor(self):
        for role, _label in PartnerAdmin.ROLE_CHOICES:
            if role == PartnerAdmin.MENTOR_ROLE:
                continue
            with self.subTest(role=role):
                admin = make_admin(role, owning_org=self.org, super_admin=(role == 'super'))
                self.assertIsNone(PartnerAdmin.objects.get(pk=admin.pk).mentor_id)

    def test_every_link_role_with_a_mentor_link_passes(self):
        # Today: a mentor login, a staff member who also mentors (S7d), finance keeping the link
        # (lead 2026-11-01). New: a member keeping the link (M1a).
        for role in ('mentor', *STAFF_MENTOR_ROLES, 'finance', 'member'):
            with self.subTest(role=role):
                admin = make_admin(role, owning_org=self.org, mentor=self._mentor())
                self.assertIsNotNone(PartnerAdmin.objects.get(pk=admin.pk).mentor_id)

    def test_a_mentor_without_its_link_is_still_refused(self):
        admin = make_admin('mentor', owning_org=self.org)
        with self.assertRaises(IntegrityError), transaction.atomic():
            _force(admin, mentor=None)

    def test_a_link_on_a_role_that_may_not_carry_one_is_still_refused(self):
        for role in ('super', 'partner'):
            with self.subTest(role=role):
                admin = make_admin(role, owning_org=self.org, super_admin=(role == 'super'))
                with self.assertRaises(IntegrityError), transaction.atomic():
                    _force(admin, mentor=self._mentor())

    def test_the_old_check_would_have_refused_a_member_with_a_link(self):
        # The reason 0096 exists: without `member` in the list, the last-group door could not keep the link.
        admin = make_admin('reviewer', owning_org=self.org, mentor=self._mentor())
        _force(admin, role='member')
        self.assertEqual(PartnerAdmin.objects.get(pk=admin.pk).role, 'member')

    def test_archived_rows_of_every_shape_pass(self):
        now = timezone.now()
        for role in ('mentor', 'reviewer', 'finance', 'member', 'admin'):
            with self.subTest(role=role):
                kw = {'mentor': self._mentor()} if role in ('mentor', 'finance') else {}
                admin = make_admin(role, owning_org=self.org, **kw)
                _force(admin, archived_at=now, archived_by_email='lead@example.test', is_active=False)
                row = PartnerAdmin.objects.get(pk=admin.pk)
                self.assertTrue(row.is_archived)
                self.assertEqual(row.archived_by_email, 'lead@example.test')

    def test_a_new_row_defaults_to_not_archived(self):
        admin = make_admin('reviewer', owning_org=self.org)
        row = PartnerAdmin.objects.get(pk=admin.pk)
        self.assertIsNone(row.archived_at)
        self.assertEqual(row.archived_by_email, '')
        self.assertFalse(row.is_archived)


class MemberModelShapeTest(TestCase):
    """§2 item 1: a member is staff (listed), holds no key, and never mentors now."""

    def setUp(self):
        self.org = make_org()

    def test_member_is_listed_staff_not_an_outsider(self):
        self.assertNotIn('member', NOT_STAFF_ROLES)
        self.assertNotIn('member', STAFF_MENTOR_ROLES)
        self.assertEqual(dict(PartnerAdmin.ROLE_CHOICES)['member'], 'No group')

    def test_member_with_a_kept_link_never_mentors_now(self):
        admin = make_admin('member', owning_org=self.org, mentor=Mentor.objects.create(organisation=self.org))
        self.assertTrue(admin.is_member)
        self.assertTrue(admin.is_staff_mentor)
        self.assertFalse(admin.mentors_now)
        self.assertIsNone(admin.source_binding_problem())

    def test_member_without_a_link_is_a_valid_row(self):
        admin = make_admin('member', owning_org=self.org)
        self.assertTrue(admin.is_member)
        self.assertFalse(admin.is_staff_mentor)
        self.assertIsNone(admin.source_binding_problem())
