"""Team tables T5c (P1, P2) — THE PARITY TEST: each page door converted to v2 keys (`staff_tables.opens`)
answers exactly what its T1 rule answered, for every live shape the access matrix uses plus extras.

Roadmap `docs/plans/2026-11-01-team-tables-roadmap.md` (T5c); decisions.md "Team tables T5c" (lead rulings
R1-R6 and the door -> key table). P2 adds the Sources door (`_SourcesBase.may_open`, which Sources,
Partner emails and the witness override all ride) and the credit ledger READ (`_CreditsBase.may_read`). A1.10a
(TD-497, TD-498) adds the last union-door callers (roster, Mentors list, Admin emails, credit record / cancel /
sign) and each page's `.view` read door, every one at its T1 holders. The HTTP proof is the access matrix (`test_team_tables_matrix`), run
UNCHANGED against its frozen fixture; this file proves each door FUNCTION, so a conversion that happens
to be unreachable by the matrix's probes still cannot move.

THE OLD RULES are restated below exactly as they were at main 307d204c (`staff_tables.admits` and the two
lead-only invite checks) — frozen copies, because the code they lived in is gone.

⚠ ONE DELIBERATE TIGHTENING: an INACTIVE row now opens no door (`effective_v2` answers nothing for it);
T1's role half admitted an inactive `admin` / `finance` / `org_admin` by its label. Every caller asks
about the SIGNED-IN person, and sign-in refuses an inactive row first (`views_admin.get_admin` reads
`is_active=True`; matrix row `admin_inactive`), so no request can see the difference.
"""
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.courses import staff_permissions_v2 as v2
from apps.courses import staff_tables as st
from apps.scholarship import (announcements, development, mentor_invite, mentoring, source_invite,
                              surface_gates, surveys)
from apps.scholarship.models import Mentor
from apps.scholarship.tests.factories import make_admin, make_org, make_programme
from apps.scholarship.tests.test_team_tables_matrix import SHAPES as MATRIX_SHAPES
from apps.scholarship.views_admin.credits import _CreditsBase
from apps.scholarship.views_admin.org_emails import AdminTeamAdminEmailsView, _SponsorEmailsBase
from apps.scholarship.views_admin.sources import _SourcesBase
from apps.scholarship.views_admin.sponsor_terms import _SponsorTermsBase

#: The matrix's shapes, plus the extras the lead asked for (qc alone, reviewer + see_all, a gift-limited
#: admin, finance) and a few edges (an empty custom set, a super on a team label, more inactive rows).
SHAPES = {
    **MATRIX_SHAPES,
    'qc_alone':             {'role': 'qc', 'permissions': ['qc']},
    'reviewer_see_all':     {'role': 'reviewer', 'permissions': ['review', 'see_all']},
    'admin_gift_limited':   {'role': 'admin', 'gift': True},
    'finance_gift_limited': {'role': 'finance', 'gift': True},
    'reviewer_gift_limited_admin_keys': {'role': 'reviewer', 'gift': True,
                                         'permissions': ['review', 'see_all', 'spending']},
    'admin_empty_set':      {'role': 'admin', 'permissions': []},
    'finance_empty_set':    {'role': 'finance', 'permissions': []},
    'org_admin_reviews':    {'role': 'org_admin', 'permissions': ['review']},
    'reviewer_super':       {'role': 'reviewer', 'super_admin': True},
    'org_admin_inactive':   {'role': 'org_admin', 'is_active': False},
    'finance_inactive':     {'role': 'finance', 'is_active': False},
    'reviewer_admin_keys_inactive': {'role': 'reviewer', 'is_active': False,
                                     'permissions': ['review', 'see_all', 'spending']},
}


# ── T1's rules, frozen (main 307d204c) ───────────────────────────────────────────────────────────────
def _t1_admits(a, roles, admin_keys_any=()):
    if a is None:
        return False
    if a.is_super or a.role in roles:
        return True
    if not admin_keys_any or not st.in_admins(a):
        return False
    held = st.admin_keys(a)
    return any(k in held for k in admin_keys_any)


def old_read_org(a):
    return _t1_admits(a, ('org_admin', 'admin', 'finance'), st.ADMIN_KEYS)


def old_admin_work(a):
    return _t1_admits(a, ('org_admin', 'admin'))


def old_lead_invite(a):
    return a is not None and (a.is_super or a.role == 'org_admin')


class _App(SimpleNamespace):
    pass


def _doors(app):
    """door -> (the converted gate, T1's rule, the v2 keys it now asks — every one held)."""
    def assign(gate_act):
        return lambda a: (a is not None and gate_act(a) and mentoring._same_org(a, app))
    return {
        'staff_tables.may_read_org': (st.may_read_org, old_read_org, v2.ORG_READ_V2),
        'staff_tables.may_do_admin_work': (st.may_do_admin_work, old_admin_work, v2.ADMIN_WORK_V2),
        'surface_gates.may_read_sponsors': (surface_gates.may_read_sponsors, old_read_org, ('sponsors.view',)),
        'surface_gates.may_read_team': (surface_gates.may_read_team, old_read_org,
                                        ('team.view', 'invitations.view')),
        'announcements.may_post': (announcements.may_post, old_admin_work, ('announcements.edit',)),
        'surveys.may_make': (surveys.may_make, old_admin_work, ('surveys.edit',)),
        'development.may_make': (development.may_make, old_admin_work, ('development.edit',)),
        'mentoring.may_act': (mentoring.may_act, old_admin_work, ('mentoring.edit',)),
        'mentoring.may_assign': (lambda a: mentoring.may_assign(a, app), assign(old_admin_work),
                                 ('mentoring.edit',)),
        'mentor_invite.may_invite': (mentor_invite.may_invite, old_lead_invite, ('invitations.edit',)),
        # A1.10a (TD-497): the Mentors list on `mentoring.view`, NOT `team.view` (finance holds that).
        'mentor_invite.may_read': (mentor_invite.may_read, old_admin_work, ('mentoring.view',)),
        'source_invite.may_invite': (source_invite.may_invite, old_lead_invite, ('invitations.edit',)),
        'sponsor_terms': (_SponsorTermsBase.may_author, old_admin_work, ('sponsors.edit',)),
        'sponsor_emails': (_SponsorEmailsBase.may_open, old_admin_work, ('sponsors.edit',)),
        'team_admin_emails': (AdminTeamAdminEmailsView.may_open, old_admin_work, ('sources.view',)),
        # P2 — T1's `_SourcesBase` asked `may_do_admin_work`; the credit screens asked `may_read_org`.
        'sources': (_SourcesBase.may_open, old_admin_work, ('sources.edit',)),
        'credits.may_read': (_CreditsBase.may_read, old_read_org, ('sponsors.view',)),
        # ── A1.10a (TD-497): the last union-door callers, each on its own keys, the same holders. ──
        'team_roster': (lambda a: st.opens_door(a, 'team_roster'), old_admin_work,
                        ('team.view', 'mentoring.view')),
        # Record / cancel: the DOOR now refuses whoever the service refused by role (T1's admin-work set);
        # T1's door was `may_read_org` and the service answered 400 wrong_role to the rest.
        'credits.may_write': (_CreditsBase.may_write, old_admin_work, ('sponsors.edit',)),
        'credits.may_sign': (_CreditsBase.may_sign, old_read_org, ('sponsors.view',)),
        # ── A1.10a (TD-498): each page's read on its `.view` (today held by exactly its `.edit` holders). ──
        'announcements.may_read': (announcements.may_read_announcements, old_admin_work, ('announcements.view',)),
        'surveys.may_read': (surveys.may_read_surveys, old_admin_work, ('surveys.view',)),
        'development.may_read': (development.may_read_development, old_admin_work, ('development.view',)),
        'mentoring.may_read': (mentoring.may_read_mentoring, old_admin_work, ('mentoring.view',)),
        'sources.may_read': (_SourcesBase.may_read, old_admin_work, ('sources.view',)),
    }


#: The doors whose key is the ADMIN WORK set (R1): the `admin` preset opens each, finance none.
ADMIN_WORK_DOORS = ('staff_tables.may_do_admin_work', 'announcements.may_post', 'surveys.may_make',
                    'development.may_make', 'mentoring.may_act', 'mentoring.may_assign',
                    'mentor_invite.may_read', 'sponsor_terms', 'sponsor_emails', 'team_admin_emails', 'sources',
                    'team_roster', 'credits.may_write', 'announcements.may_read', 'surveys.may_read',
                    'development.may_read', 'mentoring.may_read', 'sources.may_read')
READ_DOORS = ('staff_tables.may_read_org', 'surface_gates.may_read_sponsors', 'surface_gates.may_read_team',
              'credits.may_read', 'credits.may_sign')
LEAD_DOORS = ('mentor_invite.may_invite', 'source_invite.may_invite')


class DoorParity(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org, cls.other = make_org(), make_org()
        cls.programme = make_programme(organisation=cls.org)
        cls.people = {}
        for shape, spec in SHAPES.items():
            org = cls.other if spec.get('org') == 'b' else cls.org
            kw = {}
            if spec.get('super_admin'):
                kw['super_admin'] = True
            else:
                kw['owning_org'] = None if spec['role'] == 'partner' else org
            for field in ('permissions', 'is_active'):
                if field in spec:
                    kw[field] = spec[field]
            if spec.get('gift'):
                kw['programme'] = cls.programme
            if spec.get('mentor') or spec['role'] == 'mentor':
                m = Mentor.objects.create(organisation=org)
                if spec.get('mentor_deactivated'):
                    m.deactivated_at = timezone.now()
                    m.save(update_fields=['deactivated_at'])
                kw['mentor'] = m
            if spec['role'] == 'partner':
                kw['org'] = make_org()
            cls.people[shape] = make_admin(spec['role'], **kw)

    def setUp(self):
        # A file of organisation A in maintenance (the fence and the state are not what is under test).
        patcher = mock.patch('apps.scholarship.mentoring.is_in_maintenance', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.doors = _doors(_App(owning_organisation_id=self.org.id))

    def _active(self):
        return {s: p for s, p in self.people.items() if p.is_active}

    def test_the_shapes_are_built_as_written(self):
        self.assertEqual(self.people['admin_gift_limited'].programme_id, self.programme.id)
        self.assertEqual(self.people['qc_alone'].permissions, ['qc'])
        self.assertFalse(self.people['finance_inactive'].is_active)

    def test_every_door_answers_its_t1_rule_for_every_active_shape(self):
        for shape, person in self._active().items():
            for door, (new, old, _) in self.doors.items():
                with self.subTest(shape=shape, door=door):
                    self.assertEqual(new(person), old(person))

    def test_every_door_is_exactly_its_v2_keys(self):
        for shape, person in self.people.items():
            held = set(v2.effective_v2(person))
            for door, (new, _, keys) in self.doors.items():
                with self.subTest(shape=shape, door=door):
                    self.assertEqual(new(person), set(keys) <= held)

    def test_every_door_opens_for_somebody_and_refuses_somebody(self):
        # A door every shape opens (or none does) would make the parity above prove nothing.
        for door, (new, _, _) in self.doors.items():
            with self.subTest(door=door):
                answers = {new(p) for p in self._active().values()}
                self.assertEqual(answers, {True, False})

    def test_an_inactive_row_opens_no_door(self):
        inactive = {s: p for s, p in self.people.items() if not p.is_active}
        self.assertEqual(set(inactive), {'admin_inactive', 'mentor_inactive', 'org_admin_inactive',
                                         'finance_inactive', 'reviewer_admin_keys_inactive'})
        for shape, person in inactive.items():
            for door, (new, _, _) in self.doors.items():
                with self.subTest(shape=shape, door=door):
                    self.assertFalse(new(person))
        # The tightening, stated: T1's role half admitted these labels (sign-in refuses them first).
        self.assertTrue(old_admin_work(self.people['admin_inactive']))
        self.assertTrue(old_lead_invite(self.people['org_admin_inactive']))

    def test_r1_the_admin_preset_does_every_admin_work_door_and_finance_none(self):
        for shape in ('admin', 'admin_see_all_spending', 'admin_gift_limited', 'admin_empty_set', 'admin_mentor'):
            for door in ADMIN_WORK_DOORS + READ_DOORS:
                with self.subTest(shape=shape, door=door):
                    self.assertTrue(self.doors[door][0](self.people[shape]))
            for door in LEAD_DOORS:
                with self.subTest(shape=shape, door=door):
                    self.assertFalse(self.doors[door][0](self.people[shape]))
        for shape in ('finance', 'finance_custom', 'finance_gift_limited', 'finance_empty_set'):
            for door in ADMIN_WORK_DOORS + LEAD_DOORS:
                with self.subTest(shape=shape, door=door):
                    self.assertFalse(self.doors[door][0](self.people[shape]))
            for door in READ_DOORS:
                with self.subTest(shape=shape, door=door):
                    self.assertTrue(self.doors[door][0](self.people[shape]))

    def test_a_person_at_admins_by_keys_reads_and_never_works(self):
        for shape in ('reviewer_admin_keys', 'reviewer_admin_keys_other_org', 'reviewer_see_all',
                      'qc_spending', 'reviewer_payments_check', 'reviewer_gift_limited_admin_keys'):
            for door in READ_DOORS:
                with self.subTest(shape=shape, door=door):
                    self.assertTrue(self.doors[door][0](self.people[shape]))
            for door in ADMIN_WORK_DOORS + LEAD_DOORS:
                with self.subTest(shape=shape, door=door):
                    self.assertFalse(self.doors[door][0](self.people[shape]))

    def test_qc_and_reviewers_open_no_door(self):
        for shape in ('qc', 'qc_alone', 'reviewer', 'reviewer_mentor', 'mentor', 'partner', 'source_partner'):
            for door, (new, _, _) in self.doors.items():
                with self.subTest(shape=shape, door=door):
                    self.assertFalse(new(self.people[shape]))

    def test_the_lead_and_a_super_open_every_door(self):
        for shape in ('org_admin', 'org_admin_mentor', 'org_admin_reviews', 'super', 'reviewer_super'):
            for door, (new, _, _) in self.doors.items():
                with self.subTest(shape=shape, door=door):
                    self.assertTrue(new(self.people[shape]))

    def test_may_assign_keeps_its_organisation_fence(self):
        other_file = _App(owning_organisation_id=self.other.id)
        self.assertTrue(mentoring.may_assign(self.people['admin'], _App(owning_organisation_id=self.org.id)))
        self.assertFalse(mentoring.may_assign(self.people['admin'], other_file))
        self.assertTrue(mentoring.may_assign(self.people['super'], other_file))

    def test_the_credit_doors_each_ask_their_own_key_never_the_union(self):
        # A1.10a (TD-497): record / cancel ask `credits_write` (`sponsors.edit`), sign asks `credits_sign`
        # (`sponsors.view`; the service then decides the step), the ledger read `credits_read`. None asks
        # a union door.
        base = _CreditsBase()
        with mock.patch('apps.courses.staff_tables.may_read_org') as read_union, \
                mock.patch('apps.courses.staff_tables.may_do_admin_work') as work_union:
            for shape, write, sign in (('finance', False, True), ('reviewer_admin_keys', False, True),
                                       ('admin', True, True), ('org_admin', True, True), ('super', True, True),
                                       ('reviewer', False, False), ('qc', False, False)):
                with self.subTest(shape=shape), \
                        mock.patch.object(_CreditsBase, 'get_admin', return_value=self.people[shape]):
                    self.assertEqual(base._credits_admin(None)[1] is None, write)
                    self.assertEqual(base._credits_signer(None)[1] is None, sign)
                    self.assertEqual(base._credits_reader(None)[1] is None, sign)
            self.assertEqual((read_union.call_count, work_union.call_count), (0, 0))

    def test_every_source_surface_rides_the_one_sources_door(self):
        # A1.10a (TD-498): a GET asks `sources_read` (`sources.view`), a write `sources` (`sources.edit`).
        from apps.scholarship.views_admin.lifecycle import AdminApplicationWitnessView
        from apps.scholarship.views_admin.org_emails import AdminPartnerEmailDetailView, AdminPartnerEmailsView
        from apps.scholarship.views_admin.sources import AdminSourceDetailView, AdminSourcesView
        for view in (AdminSourcesView, AdminSourceDetailView, AdminPartnerEmailsView,
                     AdminPartnerEmailDetailView, AdminApplicationWitnessView):
            for method in ('GET', 'POST', 'PATCH', 'DELETE'):
                with self.subTest(view=view.__name__, method=method):
                    self.assertTrue(issubclass(view, _SourcesBase))
                    request = SimpleNamespace(method=method)
                    with mock.patch.object(view, 'get_admin', return_value=self.people['finance']):
                        admin, err = view()._sources_admin(request)
                    self.assertIsNone(admin)
                    self.assertEqual(err.status_code, 403)
                    with mock.patch.object(view, 'get_admin', return_value=self.people['admin']):
                        admin, err = view()._sources_admin(request)
                    self.assertIsNone(err)
                    expect = 'sources_read' if method == 'GET' else 'sources'
                    with mock.patch('apps.courses.staff_tables.opens_door', return_value=False) as door, \
                            mock.patch.object(view, 'get_admin', return_value=self.people['admin']):
                        view()._sources_admin(request)
                    self.assertEqual(door.call_args[0][1], expect)
