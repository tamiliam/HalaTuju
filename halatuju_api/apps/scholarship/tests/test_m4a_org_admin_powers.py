"""Sprint M4a (ACCESS-BY-SWITCHES S2, owner Q1 and Q3, 19 Nov): "Organisation admin powers".

ONE key, `organisation.admin`, stored on organisation admin rows only (migration 0100), set and cleared by
a super only, read through ONE helper (`staff_permissions.holds_org_admin_powers`). Done-when:
- the key is never stored on a team row (the write path refuses it, `org_admin_powers_team`) and a stored
  one is ignored;
- only a super sets or clears it; a NULL organisation admin row reads as holding it (fail-safe);
- the organisation's last holder cannot lose it (`last_org_admin_powers`, 409);
- a new organisation admin's invitation carries it (`invite_permissions`);
- each of the six powers (`ORG_ADMIN_POWERS`) turns off with the key;
- the drift test: a gate that calls the helper is named in `ORG_ADMIN_POWERS`, and every name there
  still reads it;
- Q3: for GIVING, the powers count as holding Payments View, Prepare and Approve, never Check (`not_held`).
"""
import ast
import os
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.courses.staff_delete_rules import sole_org_admin_ids
from apps.courses.tests.test_m1a_archive_restore import ARCHIVE, DELETE, READ, SUPABASE
from apps.scholarship import payments, payments_chain, surface_gates
from apps.scholarship.models import StaffActivity
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_org,
)

API = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
APPS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
KEY = v2.ORG_ADMIN_KEY


def _url(target):
    return f'/api/v1/admin/admins/{target.pk}/permissions/'


def _patch(who, target, keys, **extra):
    return authed_client(who).patch(_url(target), {'permissions': list(keys), 'v2': True, 'powers': True, **extra},
                                    format='json')


def _stored(a):
    return PartnerAdmin.objects.get(pk=a.pk).permissions


def _fresh(a):
    return PartnerAdmin.objects.get(pk=a.pk)


class TheHelper(TestCase):
    def test_a_migrated_org_admin_holds_it_and_a_null_row_reads_as_holding_it(self):
        org = make_org()
        lead = make_admin('org_admin', owning_org=org)
        self.assertIn(KEY, lead.permissions)                      # 0100's shape
        self.assertTrue(sp.holds_org_admin_powers(lead))
        null = make_admin('org_admin', owning_org=org, pre_m2b=True)
        self.assertIsNone(null.permissions)
        self.assertTrue(sp.holds_org_admin_powers(null))          # fail-safe, as `org_admin_v2`
        self.assertIn('manage_team', sp.resolve(null))

    def test_a_stored_key_on_any_other_row_is_ignored(self):
        org = make_org()
        for role in ('admin', 'finance', 'reviewer', 'qc'):
            with self.subTest(role=role):
                a = make_admin(role, owning_org=org, permissions=['see_all', KEY])
                self.assertFalse(sp.holds_org_admin_powers(a))
                self.assertNotIn('manage_team', sp.resolve(a))
                self.assertNotIn(KEY, v2.effective_v2(a))
                self.assertFalse(payments.may_prepare(a))
        boss = make_admin('super', super_admin=True)
        self.assertFalse(sp.holds_org_admin_powers(boss))         # a super holds everything anyway
        self.assertIn(KEY, v2.effective_v2(boss))

    def test_a_new_organisation_admins_invitation_carries_it(self):
        self.assertIn(KEY, st.invite_permissions('org_admin'))
        self.assertEqual(st.invite_permissions('org_admin'), list(v2.ORG_ADMIN_FULL))
        for role in ('admin', 'finance', 'reviewer'):
            self.assertNotIn(KEY, st.invite_permissions(role) or ())


class EachPowerTurnsOffWithTheKey(TestCase):
    """The six powers `ORG_ADMIN_POWERS` lists, asked of the same organisation admin with and without the key."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.on = make_admin('org_admin', owning_org=cls.org, first_seen_at='2026-09-01T00:00Z')
        cls.off = make_admin('org_admin', owning_org=cls.org, first_seen_at='2026-09-01T00:00Z')
        PartnerAdmin.objects.filter(pk=cls.off.pk).update(
            permissions=[k for k in cls.off.permissions if k != KEY], is_active=True)
        cls.off.refresh_from_db()
        cls.on.refresh_from_db()

    def test_the_six(self):
        def powers(a):
            return {
                'manage_team': 'manage_team' in sp.resolve(a),
                'pay_bill': 'billing.edit' in v2.effective_v2(a),
                'approve_requests': 'requests.approve' in v2.effective_v2(a),
                'payment_runs': payments.may_read(a) and payments.may_prepare(a),
                'payment_fallback': payments_chain._fallback_may(a),
                # `may_approve_platform_sponsors` also asks `sponsors.approve`, which both hold (ORG_ADMIN_SET)
                'platform_sponsors': surface_gates.may_approve_platform_sponsors(a),
            }
        names = [code for code, _gates in v2.ORG_ADMIN_POWERS]
        self.assertEqual(sorted(powers(self.on)), sorted(names))
        self.assertEqual(powers(self.on), dict.fromkeys(names, True))
        self.assertEqual(powers(self.off), dict.fromkeys(names, False))
        # Payments reads nothing: no View either (the door is the key's).
        self.assertFalse(payments.may_read(self.off))
        self.assertNotIn('payments.view', st.page_keys(self.off))


#: The callers of the helper that are not gates: the editor's own rules (who holds it, who may give what,
#: the card's switch, a tab that predates S2), the payment chain's one-line wrapper, and the ONE count of
#: the last holder (`powers_holder_ids`, read by the untick, Archive, Revoke and Delete; S2 / M4a review)
#: with the Team table's batch of it.
NOT_GATES = {
    'scholarship/staff_permissions_admin.py::held_set',
    'scholarship/staff_permissions_admin.py::not_held',
    'scholarship/staff_permissions_admin.py::v2_editor',
    'courses/staff_delete_rules.py::powers_holder_ids',
    'courses/staff_delete_rules.py::sole_org_admin_ids',
    'scholarship/staff_permissions_admin.py::change_permissions',
    'scholarship/payments_chain.py::_org_admin_powers',
}
READERS = {'holds_org_admin_powers', '_org_admin_powers'}


def _callers(names, root=APPS):
    out = set()
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in ('tests', 'migrations', '__pycache__')]
        for fn in fns:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(dp, fn)
            rel = os.path.relpath(path, root).replace(os.sep, '/')
            with open(path, encoding='utf-8') as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for call in ast.walk(node):
                        if isinstance(call, ast.Call):
                            f = call.func
                            if (getattr(f, 'attr', None) or getattr(f, 'id', None)) in names:
                                out.add(f'{rel}::{node.name}')
    return out


class TheDriftTest(TestCase):
    def test_every_gate_reading_the_powers_is_named_and_every_name_still_reads_them(self):
        named = {g for _code, gates in v2.ORG_ADMIN_POWERS for g in gates}
        callers = _callers(READERS)
        unnamed = sorted(callers - NOT_GATES - named)
        self.assertEqual(unnamed, [], 'a gate reads Organisation admin powers: name it in ORG_ADMIN_POWERS')
        # `may_read` reaches the powers through the Payments door (`effective_v2` adds `payments.view`).
        door = _callers({'opens_door'})
        stale = sorted(g for g in named if g not in callers and g not in door)
        self.assertEqual(stale, [], 'ORG_ADMIN_POWERS names a gate that no longer reads the powers')
        self.assertEqual(sorted(NOT_GATES - callers), [], 'NOT_GATES lists a caller that is gone')


@override_settings(**API)
class TheEditor(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.second = make_admin('org_admin', owning_org=cls.org)
        cls.boss = make_admin('super', super_admin=True)
        cls.member = make_admin('admin', owning_org=cls.org)

    def test_the_card_serves_the_switch_and_its_list(self):
        body = authed_client(self.boss).get(_url(self.lead)).json()
        self.assertEqual(body['org_admin_powers'],
                         {'held': True, 'powers': [code for code, _g in v2.ORG_ADMIN_POWERS]})
        self.assertIsNone(authed_client(self.lead).get(_url(self.member)).json()['org_admin_powers'])

    def test_a_team_row_is_refused_the_key(self):
        for by in (self.lead, self.boss):
            with self.subTest(by=by.role):
                r = _patch(by, self.member, [*_stored(self.member), KEY])
                self.assertEqual((r.status_code, r.json()['code']), (400, 'org_admin_powers_team'))
                self.assertNotIn(KEY, _stored(self.member))

    def test_only_a_super_sets_or_clears_it(self):
        r = _patch(self.second, self.lead, [k for k in _stored(self.lead) if k != KEY])
        self.assertIn(r.status_code, (403, 404), r.content[:300])     # an org admin's card is the super's
        self.assertIn(KEY, _stored(self.lead))
        off = _patch(self.boss, self.lead, [k for k in _stored(self.lead) if k != KEY], dry_run=True)
        self.assertEqual(off.status_code, 200, off.content[:300])
        self.assertIn('org_admin_powers_off', off.json()['consequences'])
        self.assertFalse(off.json()['org_admin_powers_held'])
        self.assertIn(KEY, _stored(self.lead))                        # a dry run writes nothing
        took = _patch(self.boss, self.lead, [k for k in _stored(self.lead) if k != KEY])
        self.assertEqual(took.status_code, 200, took.content[:300])
        self.assertNotIn(KEY, _stored(self.lead))
        self.assertNotIn('manage_team', sp.resolve(_fresh(self.lead)))
        back = _patch(self.boss, self.lead, [*_stored(self.lead), KEY])
        self.assertEqual(back.status_code, 200, back.content[:300])
        self.assertIn(KEY, _stored(self.lead))
        self.assertIn('manage_team', sp.resolve(_fresh(self.lead)))

    def test_the_last_holder_cannot_lose_it(self):
        took = _patch(self.boss, self.second, [k for k in _stored(self.second) if k != KEY])
        self.assertEqual(took.status_code, 200, took.content[:300])
        r = _patch(self.boss, self.lead, [k for k in _stored(self.lead) if k != KEY])
        self.assertEqual((r.status_code, r.json()['code']), (409, 'last_org_admin_powers'))
        self.assertIn(KEY, _stored(self.lead))

    def test_the_card_saves_back_what_it_was_served(self):
        # The web sends the served set (`permissions`, which holds `manage_team`, plus `v2_held` and the key):
        # unchanged it writes nothing; with the key unticked it takes the powers, `manage_team` with them.
        body = authed_client(self.boss).get(_url(self.lead)).json()
        self.assertIn('manage_team', body['permissions'])
        served = [*body['permissions'], *body['v2_held'], KEY]
        same = _patch(self.boss, self.lead, served)
        self.assertEqual(same.status_code, 200, same.content[:300])
        self.assertFalse(same.json()['changed'])
        off = _patch(self.boss, self.lead, [k for k in served if k != KEY])
        self.assertEqual(off.status_code, 200, off.content[:300])
        self.assertNotIn(KEY, _stored(self.lead))
        self.assertNotIn('manage_team', sp.resolve(_fresh(self.lead)))
        r = _patch(self.boss, self.member, [*(_stored(self.member) or ()), 'manage_team'])
        self.assertEqual((r.status_code, r.json()['code']), (400, 'lead_tier'))     # a team row: still refused

    def test_a_tab_from_before_s2_keeps_the_key(self):
        before = [k for k in _stored(self.lead) if k != KEY]
        r = authed_client(self.boss).patch(_url(self.lead), {'permissions': before, 'v2': True},
                                           format='json')       # no `powers: true`
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertIn(KEY, _stored(self.lead))

    def test_q3_the_powers_give_view_prepare_and_approve_never_check(self):
        base = list(_stored(self.member) or ())
        for key in ('payments.view', 'payments_prepare', 'payments_approve'):
            with self.subTest(key=key):
                r = _patch(self.lead, self.member, [*base, key], dry_run=True)
                self.assertEqual(r.status_code, 200, r.content[:300])
        r = _patch(self.lead, self.member, [*base, 'payments_check'], dry_run=True)
        self.assertEqual((r.status_code, r.json()['code']), (403, 'not_held'))
        r = _patch(self.lead, self.member, [*base, 'payments_check'])
        self.assertEqual((r.status_code, r.json()['code']), (403, 'not_held'))
        self.assertNotIn('payments_check', _stored(self.member) or ())
        self.assertEqual(_patch(self.boss, self.member, [*base, 'payments_check']).status_code, 200)
        # The card says it before the click: Check is the one Payments switch the org admin may not give.
        held = authed_client(self.lead).get(_url(self.member)).json()['keys_not_held']
        self.assertIn('payments_check', held)
        self.assertFalse({'payments_prepare', 'payments_approve'} & set(held))


def _unused(uid):
    """A sign-in that was never used (as `test_m1a_archive_restore`'s): Delete may retire it."""
    login = PartnerAdmin.objects.filter(supabase_user_id=uid).first()
    return {'id': uid, 'email': login.email if login else '', 'last_sign_in_at': None,
            'identities': [{'provider': 'email'}], 'app_metadata': {'must_change_password': True}}


def _reviewed(target):
    """Work on record (a recorded verdict), so Delete with `{"archive": true}` archives."""
    StaffActivity.objects.create(actor=target, verb='verdict_recorded', subject_type='application',
                                 subject_id=make_application('submitted').pk)


@override_settings(**SUPABASE)
class TheLastHolderIsKept(TestCase):
    """S2 / M4a review (Opus, should-fix 1): Archive, Revoke and Delete counted active org admin ROWS, so
    with X holding the powers and Y's unticked by a super, removing X left nobody holding them. Each door
    now also refuses the last active holder (`staff_delete_rules.powers_holder_ids`, the ONE count the
    untick reads too), and the Team table marks that row the same way."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.x = make_admin('org_admin', owning_org=cls.org, first_seen_at=timezone.now())   # listed on Team
        cls.y = make_admin('org_admin', owning_org=cls.org, first_seen_at=timezone.now())
        cls.boss = make_admin('super', super_admin=True)

    def setUp(self):
        took = _patch(self.boss, self.y, [k for k in _stored(self.y) if k != KEY])
        self.assertEqual(took.status_code, 200, took.content[:300])
        self.assertFalse(sp.holds_org_admin_powers(_fresh(self.y)))
        self.assertTrue(sp.holds_org_admin_powers(_fresh(self.x)))

    def _delete(self, target, body=None):
        with patch(READ, side_effect=_unused), patch(DELETE, return_value='deleted'):
            return authed_client(self.boss).delete(f'/api/v1/admin/admins/{target.pk}/', body, format='json')

    def _refused(self, r):
        self.assertEqual((r.status_code, r.json().get('code')), (400, 'last_org_admin'), r.content[:300])
        x = _fresh(self.x)
        self.assertTrue(x.is_active)
        self.assertIsNone(x.archived_at)

    def test_archive_refuses_the_last_holder(self):
        _reviewed(self.x)                      # records on file: Delete would archive
        self._refused(self._delete(self.x, ARCHIVE))

    def test_revoke_refuses_the_last_holder(self):
        self._refused(authed_client(self.boss).patch(f'/api/v1/admin/admins/{self.x.pk}/revoke/',
                                                     {'action': 'revoke'}, format='json'))

    def test_delete_refuses_the_last_holder(self):
        self._refused(self._delete(self.x))
        self.assertTrue(PartnerAdmin.objects.filter(pk=self.x.pk).exists())

    def test_the_untick_counts_through_the_same_rule(self):
        from apps.courses import public, staff_delete_rules
        with patch.object(public, 'powers_holder_ids', wraps=staff_delete_rules.powers_holder_ids) as count:
            r = _patch(self.boss, self.x, [k for k in _stored(self.x) if k != KEY])
        self.assertEqual((r.status_code, r.json()['code']), (409, 'last_org_admin_powers'))
        count.assert_called_once_with(self.org.pk)
        self.assertIn(KEY, _stored(self.x))

    def test_the_team_table_marks_the_last_holder_only(self):
        r = authed_client(self.boss).get('/api/v1/admin/staff/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        rows = {row['id']: row for row in r.json()['staff']}
        self.assertEqual((rows[self.x.pk]['delete_never'], rows[self.x.pk]['revocable']), ('sole_org_admin', False))
        self.assertTrue(rows[self.y.pk]['revocable'])
        self.assertEqual(sole_org_admin_ids(self.boss, [_fresh(self.x), _fresh(self.y)]), {self.x.pk})

    def test_the_one_without_the_powers_may_still_go(self):
        r = authed_client(self.boss).patch(f'/api/v1/admin/admins/{self.y.pk}/revoke/', {'action': 'revoke'},
                                           format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertFalse(_fresh(self.y).is_active)
