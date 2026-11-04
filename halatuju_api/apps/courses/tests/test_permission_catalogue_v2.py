"""Team tables T5a — THE v2 GOLDEN TABLE: the new permission vocabulary (`staff_permissions_v2`), its rules,
the alias table, and every live person-shape's EFFECTIVE v2 set, written by hand.

Roadmap `docs/plans/2026-11-01-team-tables-roadmap.md` (T5); the lead's T5 investigation, section F (the
"New set" column), checked against the code. No gate is converted in T5a: this file proves the plumbing
and that nobody would lose a door when T5c-T5e convert the gates (`Coverage`).

WHAT IS HERE
- `Vocabulary`  — the catalogue's shape and rules as data (groups, tiers, implies, dependencies,
  lead-only marks, aliases), and that `team.edit` / `manage_team` are not v2.
- `GoldenV2`    — each live shape (+ qc, super, partner) -> its v2 set, by hand. `resolve()` still
  answers exactly today's tuple for each shape.
- `Coverage`    — each shape x each of TODAY's doors, asked of the REAL gate function: a door that opens
  today must be covered by v2 keys in the shape's set. One door is declared unmapped (`UNMAPPED`).
- `NotYetWritable` — a v2 key cannot be saved and is dropped on read.
- `V2Importers` (T5c, replacing T5a's `NotYetAGate`, lead ruling R6) — only `staff_tables` imports the
  v2 module, and only the allowlisted door modules decide by v2 keys (`staff_tables.opens`).
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses.models import PartnerAdmin
from apps.scholarship.tests.factories import make_admin, make_org

#: The live shapes (investigation F; T1 matrix `SHAPES`), plus qc / super / partner for completeness.
SHAPES = {
    'admin':                  {'role': 'admin'},
    'admin_see_all_spending': {'role': 'admin', 'permissions': ['see_all', 'spending']},
    'admin_inactive':         {'role': 'admin', 'is_active': False},
    'finance':                {'role': 'finance'},
    'org_admin':              {'role': 'org_admin'},
    'org_admin_reviews':      {'role': 'org_admin', 'permissions': ['review']},
    'reviewer':               {'role': 'reviewer'},
    'reviewer_see_all_spending': {'role': 'reviewer', 'permissions': ['review', 'see_all', 'spending']},
    'reviewer_see_all':       {'role': 'reviewer', 'permissions': ['review', 'see_all']},
    'qc':                     {'role': 'qc'},
    # T5b (owner: "QC is self-sufficient"): `qc` with no stored `see_all` — no live row; it reads as the preset.
    'qc_alone':               {'role': 'qc', 'permissions': ['qc']},
    'reviewer_review_qc':     {'role': 'reviewer', 'permissions': ['review', 'qc']},
    'super':                  {'role': 'super', 'super_admin': True},
    'partner':                {'role': 'partner'},
}

_ENGAGEMENT_ALL = ('announcements.view', 'announcements.edit', 'surveys.view', 'surveys.edit',
                   'development.view', 'development.edit', 'mentoring.view', 'mentoring.edit')
_ADMIN_NO_MONEY = ('invitations.view', 'team.view', 'sources.view', 'sources.edit', 'sponsors.view',
                   'sponsors.edit', 'students.view', *_ENGAGEMENT_ALL, 'spending.view', 'spending.edit')
_ORG_READ = ('invitations.view', 'team.view', 'sponsors.view')
_EVERY_PAGE_KEY = (
    'invitations.view', 'invitations.edit', 'team.view', 'sources.view', 'sources.edit',
    'sponsors.view', 'sponsors.edit', 'sponsors.check', 'sponsors.approve', 'billing.view',
    'billing.edit', 'requests.view', 'requests.edit', 'requests.approve', 'settings.edit',
    'students.view', 'students.edit', 'students.approve', 'contracts.view', 'contracts.edit',
    'programmes.edit', *_ENGAGEMENT_ALL, 'payments.view', 'payments.prepare', 'payments.check',
    'payments.approve', 'spending.view', 'spending.edit')

#: shape -> (today's `resolve()` tuple, the hand-written v2 set). Set order does not matter.
GOLDEN_V2 = {
    'admin': (('see_all', 'spending', 'payments_prepare'),
              {*_ADMIN_NO_MONEY, 'payments.view', 'payments.prepare'}),
    'admin_see_all_spending': (('see_all', 'spending'), set(_ADMIN_NO_MONEY)),
    # resolve() ignores is_active (today's tuple stays); sign-in refuses the row, so v2 is empty.
    'admin_inactive': (('see_all', 'spending', 'payments_prepare'), set()),
    'finance': (('payments_approve',),
                {*_ORG_READ, 'sponsors.check', 'payments.view', 'payments.approve'}),
    'org_admin': (('see_all', 'qc', 'spending', 'manage_team'), {*_EVERY_PAGE_KEY, 'qc'}),
    'org_admin_reviews': (('review', 'see_all', 'qc', 'spending', 'manage_team'),
                          {*_EVERY_PAGE_KEY, 'qc', 'review'}),
    'reviewer': (('review',), {'review'}),
    'reviewer_see_all_spending': (('review', 'see_all', 'spending'),
                                  {'review', 'students.view', 'spending.view', 'spending.edit',
                                   *_ORG_READ}),
    'reviewer_see_all': (('review', 'see_all'), {'review', 'students.view', *_ORG_READ}),
    # The `see_all` beside `qc` does not seat a QC at Admins (T1), so no organisation read pages.
    'qc': (('see_all', 'qc'), {'students.view', 'qc'}),
    # T5b: `qc` brings `see_all` (old) / `students.view` (v2), and still seats nobody at Admins.
    'qc_alone': (('see_all', 'qc'), {'students.view', 'qc'}),
    'reviewer_review_qc': (('review', 'see_all', 'qc'), {'review', 'students.view', 'qc'}),
    'super': (sp.CATALOGUE, {*_EVERY_PAGE_KEY, 'review', 'qc'}),
    'partner': ((), set()),
}


def _make(spec, org):
    kw = {'owning_org': None if spec['role'] == 'partner' else org}
    if spec.get('super_admin'):
        kw = {'super_admin': True}
    a = make_admin(spec['role'], **kw)
    fields = {k: spec[k] for k in ('permissions', 'is_active') if k in spec}
    if fields:
        PartnerAdmin.objects.filter(pk=a.pk).update(**fields)
        a.refresh_from_db()
    return a


class Vocabulary(TestCase):

    def test_every_key_names_its_group_page_and_tier(self):
        for key, (group, page, tier, lead_only) in v2.CATALOGUE_V2.items():
            with self.subTest(key=key):
                self.assertIn(group, v2.GROUPS)
                self.assertIn(tier, v2.TIERS)
                self.assertTrue(key.endswith(f'.{tier}'))
                self.assertIsInstance(lead_only, bool)

    def test_the_catalogue_is_the_approved_list(self):
        self.assertEqual(set(v2.CATALOGUE_V2), set(_EVERY_PAGE_KEY))
        self.assertEqual(v2.HATS, ('review', 'qc'))
        self.assertNotIn('team.edit', v2.V2_KEYS)          # ruling: not offered in T5
        self.assertNotIn('manage_team', v2.V2_KEYS)        # stays lead-tier only
        self.assertEqual(v2.CATALOGUE_V2['programmes.edit'][:2], (v2.PROGRAMME, 'programme_settings'))

    def test_the_lead_only_keys_are_exactly_ruling_3(self):
        marked = {k for k, row in v2.CATALOGUE_V2.items() if row[3]}
        self.assertEqual(marked, {
            'programmes.edit', 'invitations.edit', 'sponsors.approve', 'billing.view', 'billing.edit',
            'requests.view', 'requests.edit', 'requests.approve', 'settings.edit', 'contracts.view',
            'contracts.edit', 'students.edit', 'students.approve'})

    def test_every_higher_tier_implies_its_view_and_approve_never_implies_edit(self):
        for key, implied in v2.IMPLIES.items():
            with self.subTest(key=key):
                self.assertNotEqual(v2.CATALOGUE_V2[key][2], v2.VIEW)
                self.assertEqual(implied, (f'{key.rsplit(".", 1)[0]}.view',))
                self.assertFalse(any(i.endswith(('.edit', '.check', '.prepare')) for i in implied))
        self.assertEqual(v2.IMPLIES['sponsors.approve'], ('sponsors.view',))
        self.assertEqual(v2.IMPLIES['payments.prepare'], ('payments.view',))
        self.assertNotIn('settings.edit', v2.IMPLIES)      # no settings.view to imply
        self.assertNotIn('programmes.edit', v2.IMPLIES)    # the gift cards are the "always" landing
        self.assertEqual(v2.with_implied_views(['requests.approve']),
                         ('requests.view', 'requests.approve'))

    def test_the_engagement_keys_need_students_view(self):
        self.assertEqual(v2.DEPENDS_ON_V2, {k: ('students.view',) for k in _ENGAGEMENT_ALL})

    def test_the_qc_hat_implies_students_view(self):
        # T5b: the v2 spelling of `staff_permissions.IMPLIES` — QC sees all students, by itself.
        self.assertEqual(v2.HAT_IMPLIES, {'qc': ('students.view',)})
        self.assertEqual(v2.with_implied_views(['qc']), ('students.view', 'qc'))
        self.assertEqual(v2.with_implied_views(['review']), ('review',))    # review is assigned-only
        self.assertEqual(v2.dependency_gaps(['surveys.view']), {'surveys.view': ('students.view',)})
        self.assertEqual(v2.dependency_gaps(['surveys.view', 'students.view']), {})

    def test_the_aliases_cover_every_old_key_and_name_only_v2_keys(self):
        self.assertEqual(set(v2.ALIASES), set(sp.CATALOGUE))
        self.assertEqual(v2.ALIASES['see_all'], ('students.view',))
        self.assertEqual(v2.ALIASES['spending'], ('spending.view', 'spending.edit'))
        for old, new in (('payments_prepare', 'payments.prepare'), ('payments_check', 'payments.check'),
                         ('payments_approve', 'payments.approve')):
            self.assertEqual(v2.ALIASES[old], ('payments.view', new))
        for targets in v2.ALIASES.values():
            self.assertTrue(set(targets) <= set(v2.V2_KEYS))

    def test_an_unknown_v2_key_raises(self):
        with self.assertRaises(KeyError):
            v2.v2_order(['students.veiw'])


class GoldenV2(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.people = {shape: _make(spec, cls.org) for shape, spec in SHAPES.items()}

    def test_resolve_still_answers_today(self):
        for shape, (today, _) in GOLDEN_V2.items():
            with self.subTest(shape=shape):
                self.assertEqual(sp.resolve(self.people[shape]), today)

    def test_each_shape_s_effective_v2_set(self):
        self.assertEqual(set(GOLDEN_V2), set(SHAPES))
        for shape, (_, expected) in GOLDEN_V2.items():
            with self.subTest(shape=shape):
                self.assertEqual(set(v2.effective_v2(self.people[shape])), expected)

    def test_every_set_is_closed_and_consistent(self):
        for shape, (_, expected) in GOLDEN_V2.items():
            with self.subTest(shape=shape):
                self.assertEqual(set(v2.with_implied_views(expected)), expected)
                self.assertEqual(v2.dependency_gaps(expected), {})

    def test_no_team_member_holds_a_lead_only_key(self):
        lead_only = {k for k, row in v2.CATALOGUE_V2.items() if row[3]}
        for shape, person in self.people.items():
            if person.is_super or person.role == sp.LEAD_ROLE:
                continue
            with self.subTest(shape=shape):
                self.assertEqual(set(v2.effective_v2(person)) & lead_only, set())


def _credit_refused(call):
    from apps.scholarship.sponsorship import CreditError
    try:
        call()
    except CreditError as e:
        return e.code not in ('wrong_role', 'finance_check_required')
    return True


def _credit(status):
    return SimpleNamespace(status=status, programme_id=None, programme=None, recorded_by_email='',
                           finance_checked_by_email='', confirmed_by_email='', save=lambda **kw: None)


def _sign_credit(a, status, check_armed):
    from apps.scholarship import sponsorship
    with mock.patch('apps.scholarship.payments.credit_check_required', return_value=check_armed), \
            mock.patch('apps.scholarship.staff_activity.record'), \
            mock.patch('apps.scholarship.sponsor_notify.send_credit_confirmed'):
        return _credit_refused(lambda: sponsorship.sign_admin_credit(_credit(status), a, a.name))


def _doors():
    """door -> (TODAY's real gate, asked of a person, the v2 keys that must cover it)."""
    from apps.scholarship import (announcements, development, mentor_invite, mentoring,
                                  payments_chain, programme_overview, source_invite, sponsorship,
                                  surface_gates, surveys)
    from apps.scholarship.views_admin import _AdminBase
    from apps.courses import staff_tables
    return {
        'org_read': (staff_tables.may_read_org, _ORG_READ),
        'sponsors_list': (surface_gates.may_read_sponsors, ('sponsors.view',)),
        'team_read': (surface_gates.may_read_team, ('team.view', 'invitations.view')),
        'mentors_read': (mentor_invite.may_read, ('team.view',)),
        'sources_and_terms_and_emails': (staff_tables.may_do_admin_work,
                                         ('sources.view', 'sources.edit', 'sponsors.edit')),
        'announcements': (announcements.may_post, ('announcements.view', 'announcements.edit')),
        'surveys_and_scholar_surveys_tab': (surveys.may_make, ('surveys.view', 'surveys.edit')),
        'development_and_scholar_growth_tab': (development.may_make,
                                               ('development.view', 'development.edit')),
        'scholar_mentoring_tab': (mentoring.may_act, ('mentoring.view', 'mentoring.edit')),
        'students_all': (lambda a: _AdminBase()._b40_scope(a) == 'all', ('students.view',)),
        'assigned_cases': (lambda a: a.has_perm('review'), ('review',)),
        'qc_gate': (lambda a: a.has_perm('qc'), ('qc',)),
        'spending': (lambda a: a.has_perm('spending'), ('spending.view', 'spending.edit')),
        'payments_read': (payments_chain.may_read, ('payments.view',)),
        'payments_prepare': (payments_chain.may_prepare, ('payments.prepare',)),
        'payments_check': (lambda a: a.has_perm('payments_check'), ('payments.check',)),
        'payments_approve': (lambda a: a.has_perm('payments_approve') or sp.is_lead_tier(a),
                             ('payments.approve',)),
        'credit_record': (lambda a: _credit_refused(lambda: sponsorship.record_admin_credit(
            sponsor=None, programme=None, amount=None, external_reference='', admin=a)),
            ('sponsors.edit',)),
        'credit_maker_sign': (lambda a: _sign_credit(a, 'draft', False), ('sponsors.edit',)),
        'credit_check': (lambda a: _sign_credit(a, 'admin_signed', True), ('sponsors.check',)),
        'credit_countersign': (lambda a: _sign_credit(a, 'finance_checked', True),
                               ('sponsors.approve',)),
        'credit_void': (lambda a: _credit_refused(lambda: sponsorship.cancel_admin_credit(
            _credit('confirmed'), a)), ('sponsors.edit',)),
        'invite_mentor': (mentor_invite.may_invite, ('invitations.edit',)),
        'invite_source': (source_invite.may_invite, ('invitations.edit',)),
        'contracts': (surface_gates.may_open_contracts, ('contracts.view', 'contracts.edit')),
        'requests': (surface_gates.requests_role, ('requests.view', 'requests.edit', 'requests.approve')),
        'invoices': (surface_gates.may_read_invoices, ('billing.view',)),
        'overview_layout': (programme_overview.may_customise, ('settings.edit',)),
        'lead_powers': (sp.is_lead_tier, ('programmes.edit', 'students.edit', 'students.approve',
                                          'sponsors.approve', 'billing.edit', 'invitations.edit',
                                          'settings.edit')),
    }


#: A door open today that NO v2 key covers, with why. The graduation-messages list opens by role
#: (`graduation.py:31`: reviewer / admin) and the approved catalogue has no key for it — T5c decides.
UNMAPPED = {'graduation_list': ({'admin', 'admin_see_all_spending', 'reviewer',
                                 'reviewer_see_all_spending', 'reviewer_see_all',
                                 'reviewer_review_qc'},   # T5b shape: the role list opens it, not a key
                                'graduation.py:31 role list reviewer/admin; no v2 key in the catalogue')}

MATRIX = Path(__file__).resolve().parents[2] / 'scholarship' / 'tests' / 'fixtures' / \
    'team_tables_access_before.json'


@override_settings(BILLING_USAGE_ENABLED=True, REQUESTS_ENABLED=True)
class Coverage(TestCase):
    """No access would be lost when T5c-T5e convert the gates: for each shape, every door open today
    is covered by v2 keys in its effective set."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.people = {shape: _make(spec, cls.org) for shape, spec in SHAPES.items()}

    def test_every_open_door_is_covered(self):
        doors = _doors()
        for shape, person in self.people.items():
            if not person.is_active:
                continue                           # sign-in refuses it: the next test
            held = set(v2.effective_v2(person))
            for door, (gate, needs) in doors.items():
                with self.subTest(shape=shape, door=door):
                    if gate(person):
                        self.assertEqual(set(needs) - held, set(), f'{shape} opens {door} today')

    def test_every_door_opens_for_somebody(self):
        # A door no shape opens proves nothing: each probe must reach the real "yes" at least once.
        for door, (gate, _) in _doors().items():
            with self.subTest(door=door):
                self.assertTrue(any(gate(p) for p in self.people.values() if p.is_active))

    def test_the_inactive_admin_opens_nothing_but_its_own_role(self):
        row = json.loads(MATRIX.read_text(encoding='utf-8'))['admin_inactive']
        self.assertEqual([k for k, code in row.items() if 200 <= code < 300], ['GET api/v1/admin/role/'])

    def test_the_unmapped_door_is_still_what_it_says(self):
        from apps.scholarship.views_admin import graduation
        src = Path(graduation.__file__).read_text(encoding='utf-8')
        self.assertIn("admin.role in ('reviewer', 'admin')", src)
        shapes, _ = UNMAPPED['graduation_list']
        self.assertEqual(shapes, {s for s, p in self.people.items() if p.is_active and not p.is_super
                                  and p.role in ('reviewer', 'admin')})


class NotYetWritable(TestCase):

    def test_the_save_door_refuses_every_v2_page_key(self):
        from apps.scholarship.staff_permissions_admin import PermissionChangeRefused, asked_set
        for key in v2.CATALOGUE_V2:
            with self.subTest(key=key):
                with self.assertRaises(PermissionChangeRefused) as caught:
                    asked_set(['review', key])
                self.assertEqual(caught.exception.code, 'unknown_permission')

    def test_a_hand_written_v2_key_is_dropped_on_read(self):
        org = make_org()
        a = make_admin('reviewer', owning_org=org)
        PartnerAdmin.objects.filter(pk=a.pk).update(permissions=['review', 'students.view', 'payments.approve'])
        a.refresh_from_db()
        self.assertEqual(sp.resolve(a), ('review',))
        self.assertEqual(set(v2.effective_v2(a)), {'review'})


#: Team tables T5c (lead ruling R6, replacing T5a's `NotYetAGate`): the ONLY module outside the tests that
#: may import the v2 module. Every door asks `staff_tables.opens`, never v2 directly.
V2_IMPORTERS = {'courses/staff_tables.py'}

#: The modules whose doors decide by v2 keys (`staff_tables.opens(`). It GROWS DOOR BY DOOR: a new door
#: is added here in the same commit as its parity test (`test_team_tables_t5c_doors`), so an unplanned
#: conversion fails. T5c P1 (decisions.md "Team tables T5c", the door -> key table).
V2_DOOR_MODULES = {
    'scholarship/surface_gates.py',          # sponsors.view; team.view + invitations.view
    'scholarship/announcements.py',          # announcements.edit
    'scholarship/surveys.py',                # surveys.edit
    'scholarship/development.py',            # development.edit
    'scholarship/mentoring.py',              # mentoring.edit (may_act, so may_assign)
    'scholarship/mentor_invite.py',          # invitations.edit (may_invite)
    'scholarship/source_invite.py',          # invitations.edit (may_invite)
    'scholarship/views_admin/sponsor_terms.py',   # sponsors.edit
    'scholarship/views_admin/org_emails.py',      # sponsors.edit (sponsor emails)
}


def _app_sources():
    apps_root = Path(__file__).resolve().parents[2]
    for path in apps_root.rglob('*.py'):
        rel = path.relative_to(apps_root).as_posix()
        if '/tests/' in f'/{rel}' or rel == 'courses/staff_permissions_v2.py':
            continue
        yield rel, path.read_text(encoding='utf-8', errors='replace')


class V2Importers(TestCase):
    """R6: v2 became a gate door by door. An import or a door outside these allowlists fails."""

    def test_only_staff_tables_imports_the_v2_module(self):
        users = {rel for rel, src in _app_sources() if 'staff_permissions_v2' in src}
        self.assertEqual(users, V2_IMPORTERS, 'a door asks staff_tables.opens, never v2 directly')

    def test_only_the_converted_doors_decide_by_v2_keys(self):
        doors = {rel for rel, src in _app_sources() if 'staff_tables.opens(' in src}
        self.assertEqual(doors, V2_DOOR_MODULES, 'a new v2 door needs its parity test and a line here')
        self.assertTrue(os.path.isdir(Path(__file__).resolve().parents[2]))
