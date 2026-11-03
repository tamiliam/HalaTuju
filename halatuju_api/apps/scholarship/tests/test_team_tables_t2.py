"""Team tables T2 (2026-11-03): Team -> Admins / Reviewers -> Add, and Remove from (`staff_tables_admin`).

Roadmap `docs/plans/2026-11-01-team-tables-roadmap.md`; lead rulings Q1-Q4 (decisions.md "Team tables T2").
Every door the brief lists, driven through the real endpoints:

- ADD gives the absolute minimum key (`see_all` / `review`) on top of the MATERIALISED preset — nobody loses
  anything; role is untouched; no email; the sign-in untouched; org-fenced; only a super or an org admin.
- REMOVE takes only that table's keys; refused on the LAST table ("revoke instead"), when only Mentors would
  be left (until T3), while open cases remain (Reviewers), and for the lead at Admins. Role moves only where
  the label would otherwise keep them seated (Q2a / Q2b: Rohini leaving Reviewers becomes an Admin).
- THE ORG ADMIN joins Reviewers by a stored ['review'] (Q1); only themselves or a super (Q4); every other
  key in that list is ignored; the generic editor still refuses the lead; self-QC still holds.
- Revoked people are never offered or added; a pure mentor login added becomes staff (7d link rules).
- Invitations: Admin and Reviewer only; a new Admin stores exactly ['see_all']; an OLD pending finance / qc
  invitation still accepts onto today's preset, and may still be cancelled.
- Maker / checker / approver unchanged: a finance-only person is an Admin with `payments_approve`.
"""
from django.core import mail
from django.test import TestCase, override_settings

from apps.courses import staff_permissions as sp
from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.scholarship import invitations, staff_tables_admin as sta
from apps.scholarship.models import Invitation, StaffPermissionChange
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)

TEAM = '/api/v1/admin/team/{}/'
CANDIDATES = '/api/v1/admin/team/{}/candidates/'
LOCMEM = override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@LOCMEM
class _Base(TestCase):
    def setUp(self):
        mail.outbox = []
        self.org = make_org()
        self.other = make_org()
        self.lead = make_admin('org_admin', owning_org=self.org, name='Suresh')
        self.cohort = make_cohort(owning_organisation=self.org)

    def act(self, caller, table, target, action, dry_run=False):
        return authed_client(caller).post(f'/api/v1/admin/team/{table}/', {
            'admin_id': target.pk, 'action': action, 'dry_run': dry_run}, format='json')

    def candidates(self, caller, table):
        r = authed_client(caller).get(f'/api/v1/admin/team/{table}/candidates/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        return {c['id'] for c in r.json()['candidates']}

    def fresh(self, a):
        return PartnerAdmin.objects.get(pk=a.pk)


class AddToAdmins(_Base):
    def test_a_reviewer_gets_see_all_on_top_of_the_materialised_preset_and_keeps_their_role(self):
        rev = make_admin('reviewer', owning_org=self.org)
        r = self.act(self.lead, 'admins', rev, 'add')
        self.assertEqual(r.status_code, 200, r.content[:300])
        rev = self.fresh(rev)
        self.assertEqual(rev.role, 'reviewer')                     # option B: role untouched
        self.assertEqual(rev.permissions, ['review', 'see_all'])   # nothing lost
        self.assertEqual(st.tables(rev), ('admins', 'reviewers'))
        self.assertFalse(st.may_do_admin_work(rev))                # a key seat: read pages only
        self.assertEqual(mail.outbox, [])                          # no email
        self.assertEqual(rev.supabase_user_id, PartnerAdmin.objects.get(pk=rev.pk).supabase_user_id)
        row = StaffPermissionChange.objects.get(target=rev)
        self.assertEqual((row.before, row.after), (['review'], ['review', 'see_all']))

    def test_a_dry_run_writes_nothing_and_names_the_widened_files(self):
        rev = make_admin('reviewer', owning_org=self.org)
        r = self.act(self.lead, 'admins', rev, 'add', dry_run=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['added'], ['see_all'])
        self.assertIn('files_widened_all', r.json()['consequences'])
        self.assertIsNone(self.fresh(rev).permissions)

    def test_a_qc_holder_is_refused_because_see_all_would_add_nothing(self):
        qc = make_admin('qc', owning_org=self.org)
        r = self.act(self.lead, 'admins', qc, 'add')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'qc_sees_all'))
        self.assertNotIn(qc.pk, self.candidates(self.lead, 'admins'))

    def test_already_there_is_refused_and_never_offered(self):
        adm = make_admin('admin', owning_org=self.org)
        self.assertEqual(self.act(self.lead, 'admins', adm, 'add').json()['code'], 'already_in')
        self.assertNotIn(adm.pk, self.candidates(self.lead, 'admins'))
        self.assertNotIn(self.lead.pk, self.candidates(self.lead, 'admins'))

    def test_a_pure_mentor_login_becomes_an_admin_holding_only_see_all_and_keeps_mentoring(self):
        from django.utils import timezone
        m = make_admin('mentor', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=m.pk).update(first_seen_at=timezone.now())
        self.assertIn(m.pk, self.candidates(self.lead, 'admins'))
        r = self.act(self.lead, 'admins', m, 'add')
        self.assertEqual(r.status_code, 200, r.content[:300])
        m = self.fresh(m)
        self.assertEqual((m.role, m.permissions), ('admin', ['see_all']))
        self.assertTrue(r.json()['opens_admin_pages'])           # role admin: the confirm says so
        self.assertTrue(m.is_staff_mentor and m.mentors_now)       # 7d: the link is kept
        self.assertEqual(st.tables(m), ('admins', 'mentors'))
        self.assertEqual(sp.resolve(m), ('see_all',))

    def test_a_mentor_who_has_not_signed_in_is_not_offered_or_added(self):
        m = make_admin('mentor', owning_org=self.org)
        self.assertNotIn(m.pk, self.candidates(self.lead, 'reviewers'))
        self.assertEqual(self.act(self.lead, 'reviewers', m, 'add').json()['code'], 'not_eligible')


class AddToReviewers(_Base):
    def test_an_admin_gets_review_and_loses_nothing(self):
        adm = make_admin('admin', owning_org=self.org)
        r = self.act(self.lead, 'reviewers', adm, 'add')
        self.assertEqual(r.status_code, 200, r.content[:300])
        adm = self.fresh(adm)
        self.assertEqual(adm.role, 'admin')
        self.assertEqual(adm.permissions, ['review', 'see_all', 'spending', 'payments_prepare'])
        self.assertEqual(st.tables(adm), ('admins', 'reviewers'))

    def test_a_finance_person_gets_review_and_keeps_approving(self):
        fin = make_admin('finance', owning_org=self.org)
        self.act(self.lead, 'reviewers', fin, 'add')
        fin = self.fresh(fin)
        self.assertEqual(fin.permissions, ['review', 'payments_approve'])
        self.assertTrue(fin.has_perm('payments_approve'))

    def test_a_pure_mentor_login_becomes_a_reviewer_on_the_preset(self):
        from django.utils import timezone
        m = make_admin('mentor', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=m.pk).update(first_seen_at=timezone.now())
        self.assertEqual(self.act(self.lead, 'reviewers', m, 'add').status_code, 200)
        m = self.fresh(m)
        self.assertEqual((m.role, m.permissions), ('reviewer', None))
        self.assertEqual(st.tables(m), ('reviewers', 'mentors'))


class Fences(_Base):
    def test_only_a_super_or_an_org_admin_knocks(self):
        rev = make_admin('reviewer', owning_org=self.org)
        for role in ('admin', 'finance', 'qc', 'reviewer'):
            caller = make_admin(role, owning_org=self.org)
            self.assertEqual(self.act(caller, 'admins', rev, 'add').status_code, 403, role)
            self.assertEqual(authed_client(caller).get(CANDIDATES.format('admins')).status_code, 403, role)
        rohini = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all', 'spending'])
        self.assertEqual(self.act(rohini, 'admins', rev, 'add').status_code, 403)
        self.assertIsNone(self.fresh(rev).permissions)

    def test_another_organisations_people_are_404_and_never_listed(self):
        theirs = make_admin('reviewer', owning_org=self.other)
        self.assertEqual(self.act(self.lead, 'admins', theirs, 'add').status_code, 404)
        self.assertEqual(self.act(self.lead, 'reviewers', theirs, 'remove').status_code, 404)
        self.assertNotIn(theirs.pk, self.candidates(self.lead, 'admins'))
        self.assertIsNone(self.fresh(theirs).permissions)

    def test_a_revoked_person_is_not_offered_and_cannot_be_re_added(self):
        gone = make_admin('reviewer', owning_org=self.org, is_active=False)
        self.assertNotIn(gone.pk, self.candidates(self.lead, 'admins'))
        r = self.act(self.lead, 'admins', gone, 'add')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_active'))
        self.assertIsNone(self.fresh(gone).permissions)

    def test_a_super_is_never_a_target(self):
        boss = make_admin('super', super_admin=True)
        caller = make_admin('super', super_admin=True)
        self.assertEqual(self.act(caller, 'admins', boss, 'remove').status_code, 404)

    def test_bad_requests_are_400(self):
        c = authed_client(self.lead)
        for body in ({}, {'admin_id': 'x', 'action': 'add'}, {'admin_id': self.lead.pk, 'action': 'grant'}):
            self.assertEqual(c.post(TEAM.format('admins'), body, format='json').status_code, 400, body)
        self.assertEqual(c.post(TEAM.format('mentors'), {'admin_id': self.lead.pk, 'action': 'add'},
                                format='json').status_code, 400)


class Remove(_Base):
    def test_rohini_leaves_admins_keeping_review_only(self):
        rohini = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all', 'spending'])
        r = self.act(self.lead, 'admins', rohini, 'remove')
        self.assertEqual(r.status_code, 200, r.content[:300])
        rohini = self.fresh(rohini)
        self.assertEqual((rohini.role, rohini.permissions), ('reviewer', None))   # back on the preset
        self.assertEqual(st.tables(rohini), ('reviewers',))

    def test_rohini_leaves_reviewers_and_becomes_an_admin_with_her_admin_keys(self):
        rohini = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all', 'spending'])
        dry = self.act(self.lead, 'reviewers', rohini, 'remove', dry_run=True).json()
        self.assertTrue(dry['opens_admin_pages'])                 # Q2b: a GAIN, said in plain words first
        self.assertEqual(self.act(self.lead, 'reviewers', rohini, 'remove').status_code, 200)
        rohini = self.fresh(rohini)
        self.assertEqual((rohini.role, rohini.permissions), ('admin', ['see_all', 'spending']))
        self.assertEqual(st.tables(rohini), ('admins',))
        self.assertTrue(st.may_do_admin_work(rohini))             # one Admin, as an invited Admin

    def test_an_admin_with_review_leaves_admins_and_becomes_a_reviewer(self):
        adm = make_admin('admin', owning_org=self.org, permissions=['review', 'see_all', 'spending'])
        self.assertEqual(self.act(self.lead, 'admins', adm, 'remove').status_code, 200)
        adm = self.fresh(adm)
        self.assertEqual((adm.role, adm.permissions), ('reviewer', None))
        self.assertFalse(st.may_do_admin_work(adm))

    def test_an_admin_with_qc_leaves_admins_and_becomes_qc_keeping_see_all_for_qc(self):
        adm = make_admin('admin', owning_org=self.org,
                         permissions=['see_all', 'qc', 'spending', 'payments_prepare'])
        self.assertEqual(self.act(self.lead, 'admins', adm, 'remove').status_code, 200)
        adm = self.fresh(adm)
        self.assertEqual((adm.role, adm.permissions), ('qc', None))

    def test_the_last_table_is_refused_revoke_instead(self):
        adm = make_admin('admin', owning_org=self.org)
        r = self.act(self.lead, 'admins', adm, 'remove')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'last_table'))
        rev = make_admin('reviewer', owning_org=self.org)
        self.assertEqual(self.act(self.lead, 'reviewers', rev, 'remove').json()['code'], 'last_table')

    def test_only_mentors_left_is_refused_for_one_who_never_signed_in(self):
        # T3 lifted T2's refusal only where the mentor-login shape is safe (`test_team_tables_t3.py`); a
        # staff mentor who has never signed in is still refused.
        from apps.scholarship.models import Mentor
        adm = make_admin('admin', owning_org=self.org, mentor=Mentor.objects.create(organisation=self.org))
        self.assertIsNone(adm.first_seen_at)
        r = self.act(self.lead, 'admins', adm, 'remove')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'mentors_only'))

    def test_reviewers_refused_while_open_cases_remain(self):
        rohini = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all', 'spending'])
        make_application('assigned', reviewer=rohini, cohort=self.cohort)
        r = self.act(self.lead, 'reviewers', rohini, 'remove')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'has_open_cases'))
        self.assertEqual(self.fresh(rohini).role, 'reviewer')

    def test_the_lead_never_leaves_admins(self):
        caller = make_admin('super', super_admin=True)
        self.assertEqual(self.act(caller, 'admins', self.lead, 'remove').status_code, 404)
        self.assertEqual(self.act(self.lead, 'admins', self.lead, 'remove').status_code, 404)

    def test_a_finance_person_leaving_admins_says_the_credit_check_goes(self):
        fin = make_admin('finance', owning_org=self.org, permissions=['review', 'payments_approve'])
        dry = self.act(self.lead, 'admins', fin, 'remove', dry_run=True).json()
        self.assertTrue(dry['finance_check_off'])
        self.assertEqual(self.act(self.lead, 'admins', fin, 'remove').status_code, 200)
        fin = self.fresh(fin)
        self.assertEqual((fin.role, fin.permissions), ('reviewer', None))
        self.assertFalse(fin.has_perm('payments_approve'))

    def test_the_list_serves_where_remove_is_accepted(self):
        rohini = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all', 'spending'])
        make_application('assigned', reviewer=rohini, cohort=self.cohort)
        adm = make_admin('admin', owning_org=self.org)
        rows = {a['id']: a for a in authed_client(self.lead).get('/api/v1/admin/admins/').json()['admins']}
        self.assertEqual(rows[rohini.pk]['remove'], {'admins': None, 'reviewers': 'has_open_cases'})
        self.assertEqual(rows[rohini.pk]['admin_keys'], ['see_all', 'spending'])
        self.assertEqual(rows[rohini.pk]['reviewer_keys'], ['review'])
        self.assertEqual(rows[adm.pk]['remove'], {'admins': 'last_table'})
        self.assertEqual(rows[self.lead.pk]['remove'], {})       # an org admin is not theirs to act on
        self.assertTrue(rows[self.lead.pk]['lead'])


class OrgAdminJoinsReviewers(_Base):
    def test_self_add_works_and_only_review_is_stored(self):
        self.assertIn(self.lead.pk, self.candidates(self.lead, 'reviewers'))
        r = self.act(self.lead, 'reviewers', self.lead, 'add')
        self.assertEqual(r.status_code, 200, r.content[:300])
        lead = self.fresh(self.lead)
        self.assertEqual(lead.permissions, ['review'])
        self.assertEqual(lead.role, 'org_admin')
        self.assertEqual(sp.resolve(lead), ('review', 'see_all', 'qc', 'spending', 'manage_team'))
        self.assertEqual(st.tables(lead), ('admins', 'reviewers'))

    def test_every_other_key_on_an_org_admin_row_is_ignored(self):
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(
            permissions=['payments_approve', 'payments_check', 'payments_prepare'])
        lead = self.fresh(self.lead)
        self.assertEqual(sp.resolve(lead), sp.preset_for('org_admin'))
        self.assertFalse(st.in_reviewers(lead))
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(permissions=['review', 'payments_approve'])
        lead = self.fresh(self.lead)
        self.assertEqual(sp.resolve(lead), ('review', 'see_all', 'qc', 'spending', 'manage_team'))
        self.assertFalse(lead.has_perm('payments_approve'))

    def test_the_generic_editor_still_refuses_the_lead(self):
        caller = make_admin('super', super_admin=True)
        r = authed_client(caller).patch(f'/api/v1/admin/admins/{self.lead.pk}/permissions/',
                                        {'permissions': ['review', 'see_all', 'qc']}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_editable'))

    def test_a_fellow_org_admin_cannot_add_them(self):
        fellow = make_admin('org_admin', owning_org=self.org)
        self.assertEqual(self.act(fellow, 'reviewers', self.lead, 'add').status_code, 404)
        self.assertNotIn(self.lead.pk, self.candidates(fellow, 'reviewers'))
        self.assertIsNone(self.fresh(self.lead).permissions)

    def test_an_admin_cannot_add_an_org_admin_manage_team_is_no_door(self):
        adm = make_admin('admin', owning_org=self.org, permissions=['see_all', 'manage_team'])
        self.assertNotIn('manage_team', sp.resolve(adm))
        self.assertEqual(self.act(adm, 'reviewers', self.lead, 'add').status_code, 403)
        self.assertIsNone(self.fresh(self.lead).permissions)

    def test_another_organisation_is_refused(self):
        theirs = make_admin('org_admin', owning_org=self.other)
        self.assertEqual(self.act(self.lead, 'reviewers', theirs, 'add').status_code, 404)
        self.assertEqual(self.act(theirs, 'reviewers', self.lead, 'add').status_code, 404)

    def test_a_super_may_add_and_remove_them(self):
        caller = make_admin('super', super_admin=True)
        self.assertEqual(self.act(caller, 'reviewers', self.lead, 'add').status_code, 200)
        self.assertEqual(self.act(caller, 'reviewers', self.lead, 'remove').status_code, 200)
        self.assertIsNone(self.fresh(self.lead).permissions)

    def test_self_remove_goes_back_to_null_and_is_refused_with_open_cases(self):
        self.act(self.lead, 'reviewers', self.lead, 'add')
        app = make_application('assigned', reviewer=self.lead, cohort=self.cohort)
        self.assertEqual(self.act(self.lead, 'reviewers', self.lead, 'remove').json()['code'], 'has_open_cases')
        app.delete()
        self.assertEqual(self.act(self.lead, 'reviewers', self.lead, 'remove').status_code, 200)
        lead = self.fresh(self.lead)
        self.assertIsNone(lead.permissions)
        self.assertEqual(st.tables(lead), ('admins',))

    def test_they_join_the_reviewers_list_and_the_assignment_picker(self):
        from apps.scholarship.services import may_assign_to
        listed = lambda: {r['id'] for r in authed_client(self.lead).get(  # noqa: E731
            '/api/v1/admin/reviewers/').json()['reviewers']}
        self.assertNotIn(self.lead.pk, listed())
        self.assertFalse(may_assign_to(self.lead, self.lead))
        self.act(self.lead, 'reviewers', self.lead, 'add')
        self.assertIn(self.lead.pk, listed())
        self.assertTrue(may_assign_to(self.fresh(self.lead), self.fresh(self.lead)))
        rows = authed_client(self.lead).get('/api/v1/admin/scholarship/assignable-admins/').json()
        rows = rows.get('admins', rows) if isinstance(rows, dict) else rows
        mine = [a for a in rows if a.get('id') == self.lead.pk]
        self.assertEqual(len(mine), 1)
        self.assertTrue(mine[0].get('assignable'))

    def test_after_a_self_add_self_qc_still_blocks_their_own_reviewed_case(self):
        self.act(self.lead, 'reviewers', self.lead, 'add')
        app = make_application('awaiting_qc', outcome='recommend', reviewer=self.lead, cohort=self.cohort)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        r = authed_client(self.lead).post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/qc-decision/',
            {'decision': 'accept'}, format='json')
        self.assertEqual(r.status_code, 403, r.content[:300])
        self.assertIn(r.json()['code'], ('self_qc_forbidden', 'self_verdict_qc_forbidden'))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class Invitations(TestCase):
    def setUp(self):
        self.org = make_org()
        self.lead = make_admin('org_admin', owning_org=self.org)

    def test_only_admin_and_reviewer_are_invitable_and_old_kinds_stay_cancellable(self):
        r = authed_client(self.lead).get('/api/v1/admin/invitations/?kind=admins')
        self.assertEqual(r.json()['invitable_roles'], ['admin'])
        self.assertEqual(r.json()['cancellable_roles'], ['admin', 'finance'])
        r = authed_client(self.lead).get('/api/v1/admin/invitations/?kind=reviewers')
        self.assertEqual(r.json()['invitable_roles'], ['reviewer'])

    def test_an_org_admin_may_no_longer_invite_finance_or_qc(self):
        for role in ('finance', 'qc'):
            r = authed_client(self.lead).post('/api/v1/admin/invite/', {
                'email': f'{role}@new.test', 'name': 'N', 'role': role}, format='json')
            self.assertEqual((r.status_code, r.json()['code']), (403, 'role_not_allowed'), role)

    def test_a_new_admin_row_stores_exactly_see_all(self):
        from apps.courses import staff_reinvite
        row, _, err = staff_reinvite.provision(None, email='new.admin@x.test', name='N', role='admin',
                                               org=None, owning_org=self.org)
        self.assertIsNone(err)
        self.assertEqual(row.permissions, ['see_all'])
        self.assertEqual(st.tables(row), ('admins',))
        rev, _, _ = staff_reinvite.provision(None, email='new.rev@x.test', name='N', role='reviewer',
                                             org=None, owning_org=self.org)
        self.assertIsNone(rev.permissions)

    def test_only_an_admin_starts_below_its_preset(self):
        self.assertEqual(st.invite_permissions('admin'), ['see_all'])
        self.assertIsNone(st.invite_permissions('reviewer'))
        self.assertIsNone(st.invite_permissions('finance'))

    def test_an_old_pending_finance_or_qc_invitation_still_accepts_onto_todays_preset(self):
        for role in ('finance', 'qc', 'admin'):
            account = make_admin(role, owning_org=self.org)     # written when it was sent, before T2
            inv = invitations.create_or_refresh(
                audience='staff', email=account.email, role=role, organisation=self.org,
                partner_admin=account, credential_issued=True, ttl_days=7)
            r = authed_client(account).get('/api/v1/admin/role/')
            self.assertEqual(r.status_code, 200, role)
            account.refresh_from_db()
            self.assertIsNotNone(account.first_seen_at, role)
            self.assertIsNone(account.permissions, role)
            self.assertEqual(sp.resolve(account), sp.preset_for(role), role)
            self.assertEqual(r.json()['permissions'], list(sp.preset_for(role)), role)
            inv.refresh_from_db()
            self.assertEqual(invitations.status_of(inv), 'accepted', role)

    def test_an_old_pending_finance_invitation_may_still_be_cancelled_by_the_org_admin(self):
        account = make_admin('finance', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=account.pk).update(supabase_user_id=None)
        inv = invitations.create_or_refresh(
            audience='staff', email=account.email, role='finance', organisation=self.org,
            partner_admin=account, credential_issued=False, ttl_days=7)
        r = authed_client(self.lead).post(f'/api/v1/admin/invitations/{inv.pk}/cancel/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertTrue(Invitation.objects.filter(pk=inv.pk, revoked_at__isnull=False).exists())


class PaymentChainUnchanged(TestCase):
    """Maker != checker != approver, re-read through T2's derivation: a finance-only person is an Admin
    holding `payments_approve`, and nothing T2 does gives a key without an explicit Add or tick."""

    def test_a_finance_person_is_an_admin_with_approve_and_the_chain_reads_keys(self):
        org = make_org()
        fin = make_admin('finance', owning_org=org)
        self.assertEqual(st.tables(fin), ('admins',))
        self.assertEqual(sta.table_keys(fin, sta.ADMINS), ['payments_approve'])
        self.assertTrue(fin.has_perm('payments_approve'))
        self.assertFalse(fin.has_perm('payments_prepare'))
        adm = make_admin('admin', owning_org=org)
        self.assertTrue(adm.has_perm('payments_prepare'))
        self.assertFalse(adm.has_perm('payments_approve'))
        self.assertEqual([a.pk for a in sp.holders(org, 'payments_approve')], [fin.pk])
        new = make_admin('admin', owning_org=org, permissions=['see_all'])   # an invited Admin
        self.assertFalse(any(new.has_perm(k) for k in ('payments_prepare', 'payments_check',
                                                       'payments_approve', 'spending')))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ChangeRoleUnderT2(TestCase):
    """Review 2026-11-03 (lead ruling, revising Q3): the kept change-role endpoint may not route around T2.
    No switch INTO `finance` or `qc` (409 `label_retired`); a switch OUT keeps the resolved keys exactly."""

    def setUp(self):
        self.org = make_org()
        self.lead = make_admin('org_admin', owning_org=self.org)

    def switch(self, target, role, dry_run=False):
        return authed_client(self.lead).patch(f'/api/v1/admin/admins/{target.pk}/role/',
                                              {'role': role, 'dry_run': dry_run}, format='json')

    def test_no_switch_into_finance_or_qc(self):
        for start, into in (('admin', 'finance'), ('reviewer', 'qc')):
            person = make_admin(start, owning_org=self.org)
            for dry in (True, False):
                r = self.switch(person, into, dry_run=dry)
                self.assertEqual((r.status_code, r.json()['code']), (409, 'label_retired'), (start, dry))
            person.refresh_from_db()
            self.assertEqual((person.role, person.permissions), (start, None))

    def test_finance_to_admin_keeps_exactly_payments_approve(self):
        fin = make_admin('finance', owning_org=self.org)
        r = self.switch(fin, 'admin', dry_run=True)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertFalse(r.json()['permissions_reset'])
        self.assertEqual(r.json()['consequences'], [])
        self.assertEqual(r.json()['consequence'], 'finance_check_off')   # the credit check, as before
        self.assertEqual(self.switch(fin, 'admin').status_code, 200)
        fin.refresh_from_db()
        self.assertEqual((fin.role, fin.permissions), ('admin', ['payments_approve']))
        self.assertEqual(sp.resolve(fin), ('payments_approve',))       # no gain (no see_all), no loss

    def test_qc_to_reviewer_keeps_see_all_and_qc(self):
        qc = make_admin('qc', owning_org=self.org, permissions=['see_all', 'qc', 'spending'])
        self.assertEqual(self.switch(qc, 'reviewer').status_code, 200)
        qc.refresh_from_db()
        self.assertEqual((qc.role, qc.permissions), ('reviewer', ['see_all', 'qc', 'spending']))

    def test_a_switch_out_equal_to_the_new_preset_is_stored_null(self):
        fin = make_admin('finance', owning_org=self.org,
                         permissions=['see_all', 'spending', 'payments_prepare'])
        self.assertEqual(self.switch(fin, 'admin').status_code, 200)
        fin.refresh_from_db()
        self.assertEqual((fin.role, fin.permissions), ('admin', None))


class MayActOnTheLockedRow(_Base):
    """Review 2026-11-03: `change` judges the caller again on the LOCKED row, so a target that moved out
    of the caller's remit between the view's check and the write is refused."""

    def test_a_target_that_left_the_callers_remit_is_refused_under_the_lock(self):
        rev = make_admin('reviewer', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=rev.pk).update(owning_organisation=self.other)   # moved meanwhile
        with self.assertRaises(sta.Refused) as caught:
            sta.change(rev.pk, sta.ADMINS, 'add', by=self.lead)
        self.assertEqual(caught.exception.code, 'not_found')
        self.assertIsNone(self.fresh(rev).permissions)

    def test_a_target_promoted_to_org_admin_meanwhile_is_refused(self):
        rev = make_admin('reviewer', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=rev.pk).update(role='org_admin')
        with self.assertRaises(sta.Refused) as caught:
            sta.change(rev.pk, sta.REVIEWERS, 'add', by=self.lead)
        self.assertEqual(caught.exception.code, 'not_found')
