"""Sprint S4a (SCHOLARS-SPLIT, owner rulings 25 Nov): when the Scholars switch splits into View scholars and
Manage scholar files, NOBODY's access changes but the one named gain.

Each row shape is made as it stood BEFORE S4 (`pre_s4=True`: migrations 0097-0100 applied, not 0101) and read
with the OLD rule, frozen here: a scholar-file write and the ordinary letters asked View scholars (`scholars`);
the suspension and termination letters (and with them nothing else) asked the stored `scholars.approve`. The
row then goes through migration 0101's `plan_row` and is read with the NEW code. Compared, per shape: the
groups the row sits in (a switch never places anyone in a group; the groups read here are today's stopgap
`in_admins` from keys, until S6), the old keys, the held v2 switches, every door, the file write, and the
letter kinds. The ONE difference allowed: a row 0101 grants gains `scholars.approve`, its door, and with it
the suspension and termination letters (owner Q3: today's file writers keep their write power).
"""
from importlib import import_module

from django.test import TestCase

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.scholarship import letters as svc
from apps.scholarship import surface_gates
from apps.scholarship.tests.factories import make_admin, make_org

M0101 = import_module('apps.courses.migrations.0101_grant_scholars_manage')
KEY = 'scholars.approve'

#: Row shapes: (role, stored list or None for the role's preset, extra make_admin kwargs).
SHAPES = {
    'admin':                    ('admin', None, {}),
    'admin_inactive':           ('admin', None, {'is_active': False}),
    'admin_see_all_spending':   ('admin', ['see_all', 'scholars', 'spending'], {}),
    'admin_see_all_only':       ('admin', ['see_all', 'spending'], {}),
    'admin_withdraw_only':      ('admin', ['award_withdraw_approve'], {}),
    'reviewer':                 ('reviewer', None, {}),
    'reviewer_admin_keys':      ('reviewer', ['review', 'see_all', 'scholars', 'spending'], {}),
    'finance':                  ('finance', None, {}),
    'qc':                       ('qc', None, {}),
    'qc_spending':              ('qc', ['see_all', 'qc', 'scholars', 'spending'], {}),
    'org_admin':                ('org_admin', None, {}),
    'mentor':                   ('mentor', None, {}),
    'partner':                  ('partner', None, {}),
}


def _old_kinds(a):
    """The letter kinds before S4: the ordinary ones on View scholars, the senior ones on the stored key."""
    if a.is_super:
        return set(svc.KINDS)
    view = surface_gates.may_view_scholars(a)
    senior = KEY in set(v2.effective_v2(a))
    return ({k for k in svc.KINDS if k not in svc.SENIOR_KINDS} if view else set()) | (
        set(svc.SENIOR_KINDS) if senior else set())


def _new_kinds(a):
    return set(svc.KINDS) if surface_gates.may_manage_scholar_files(a) else set()


def _read(a):
    return {
        'tables': st.tables(a),
        'old_keys': sp.resolve(a),
        'v2': set(v2.effective_v2(a)),
        'doors': {door: st.opens_door(a, door) for door in st.DOOR_KEYS},
    }


class NobodyChangesButTheNamedGain(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.rows = {}
        for shape, (role, stored, extra) in SHAPES.items():
            kw = {'owning_org': None if role == 'partner' else cls.org, 'pre_s4': True, **extra}
            if stored is not None:
                kw['permissions'] = stored
            cls.rows[shape] = make_admin(role, **kw)

    def _through_0101(self, a):
        """The row read before, the plan 0101 makes for it, and the row read after (the NEW code). Both are
        read `seated` (a suspended row as if active): what a Restore gives back is compared too."""
        before = PartnerAdmin.objects.get(pk=a.pk)
        plan = M0101.plan_row(before.role, before.permissions)
        if plan is not None:
            PartnerAdmin.objects.filter(pk=a.pk).update(permissions=plan[-1])
        return st.seated(before), plan, st.seated(PartnerAdmin.objects.get(pk=a.pk))

    def test_no_group_seat_key_or_door_moves_but_the_grant(self):
        for shape, a in self.rows.items():
            with self.subTest(shape=shape):
                before, plan, after = self._through_0101(a)
                old, new = _read(before), _read(after)
                gain = {KEY} if plan is not None else set()
                self.assertEqual(new['tables'], old['tables'])          # a switch never moves a group seat
                self.assertEqual(new['old_keys'], old['old_keys'])
                self.assertEqual(new['v2'], old['v2'] | gain)
                self.assertEqual(new['v2'] - old['v2'], gain)
                moved = {d for d in st.DOOR_KEYS if new['doors'][d] != old['doors'][d]}
                self.assertEqual(moved, {'scholar_files'} if plan is not None and not old['doors']['scholar_files']
                                 else set())

    def test_every_file_writer_keeps_the_write_and_nobody_new_gains_it(self):
        for shape, a in self.rows.items():
            with self.subTest(shape=shape):
                before, _plan, after = self._through_0101(a)
                old_writes = surface_gates.may_view_scholars(before)      # the old rule: View scholars wrote
                self.assertEqual(surface_gates.may_manage_scholar_files(after), old_writes)
                self.assertEqual(surface_gates.may_view_scholars(after), surface_gates.may_view_scholars(before))

    def test_the_letters_gain_only_the_senior_kinds_and_only_where_0101_grants(self):
        granted = set()
        for shape, a in self.rows.items():
            with self.subTest(shape=shape):
                before, plan, after = self._through_0101(a)
                old, new = _old_kinds(before), _new_kinds(after)
                self.assertTrue(old <= new)
                if plan is not None:
                    granted.add(shape)
                    self.assertEqual(new - old, set(svc.SENIOR_KINDS))
                else:
                    self.assertEqual(new, old)
        # The admin preset, its custom twins holding View scholars, and their inactive rows; never an org admin.
        self.assertEqual(granted, {'admin', 'admin_inactive', 'admin_see_all_spending',
                                   'reviewer_admin_keys', 'qc_spending'})

    def test_0101_writes_nothing_twice(self):
        for shape, a in self.rows.items():
            with self.subTest(shape=shape):
                _before, _plan, after = self._through_0101(a)
                self.assertIsNone(M0101.plan_row(after.role, after.permissions))
