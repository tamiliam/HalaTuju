"""Sprint M1a (2026-11-10): an archived row is on no list and out of reach by id (brief §5).

The census (`test_m1_archive_reader_census.py`) names every reader; these drive the ones M1a filtered:
the staff list, the Reviewers list, the gift report, the Invitations list and its Cancel, the Mentors tab
(list, detail, actions), "Add a staff member as mentor", the locked re-reads under a role or permission
change, the team-table gate and the invitations backfill. Each has a live control row beside it.
"""
import io

from django.core.management import call_command
from django.utils import timezone

from apps.courses import staff_gift
from apps.courses.models import PartnerAdmin
from apps.courses.tests.test_m1a_archive_restore import ARCHIVE, _Base, _reviewed
from apps.scholarship import invitations, staff_lifecycle, staff_permissions_admin, staff_tables_admin
from apps.scholarship.models import Invitation, MentorAssignment
from apps.scholarship.tests.factories import authed_client, make_admin, make_application


def _ids(rows):
    return {r['id'] for r in rows}


class TestArchivedStaffOnNoList(_Base):
    def setUp(self):
        self.target = make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now())
        self.live = make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now())
        self.invs = {a.pk: invitations.create_or_refresh(
            audience='staff', email=a.email, name=a.name, role='reviewer', organisation=self.org,
            invited_by=self.lead, partner_admin=a, credential_issued=True) for a in (self.target, self.live)}
        _reviewed(self.target)
        self.assertEqual(self.delete(self.lead, self.target, ARCHIVE).status_code, 200)

    def test_the_staff_list(self):
        r = authed_client(self.super).get('/api/v1/admin/admins/')
        self.assertEqual(r.status_code, 200, r.content[:200])
        body = r.json()
        ids = _ids(body if isinstance(body, list) else body['admins'])
        self.assertIn(self.live.pk, ids)
        self.assertNotIn(self.target.pk, ids)

    def test_the_reviewers_list(self):
        r = authed_client(self.lead).get('/api/v1/admin/reviewers/')
        self.assertEqual(r.status_code, 200, r.content[:200])
        ids = _ids(r.json()['reviewers'])
        self.assertIn(self.live.pk, ids)
        self.assertNotIn(self.target.pk, ids)

    def test_the_gift_report(self):
        ids = set(staff_gift.unchosen_rows().values_list('pk', flat=True))
        self.assertIn(self.live.pk, ids)
        self.assertNotIn(self.target.pk, ids)

    def test_the_invitations_list_and_its_cancel(self):
        client = authed_client(self.lead)
        r = client.get('/api/v1/admin/invitations/?kind=reviewers&all=1')   # cancelled ones too
        self.assertEqual(r.status_code, 200, r.content[:200])
        ids = _ids(r.json()['invitations'])
        self.assertIn(self.invs[self.live.pk].pk, ids)
        self.assertNotIn(self.invs[self.target.pk].pk, ids)
        r = client.post(f'/api/v1/admin/invitations/{self.invs[self.target.pk].pk}/cancel/', {}, format='json')
        self.assertEqual(r.status_code, 404, r.content[:200])

    def test_the_locked_re_reads_and_the_table_gate(self):
        with self.assertRaises(staff_lifecycle.RoleChangeRefused) as role:
            staff_lifecycle.change_role(self.target.pk, 'admin', by=self.lead)
        self.assertEqual(role.exception.code, 'not_found')
        with self.assertRaises(staff_permissions_admin.PermissionChangeRefused) as keys:
            staff_permissions_admin.change_permissions(self.target.pk, ['review'], by=self.lead)
        self.assertEqual(keys.exception.code, 'not_found')
        self.target.refresh_from_db()
        self.assertFalse(staff_tables_admin.may_act(self.super, self.target, 'reviewers'))
        self.assertTrue(staff_tables_admin.may_act(self.super, self.live, 'admins'))

    def test_add_a_staff_member_as_mentor_answers_404(self):
        r = authed_client(self.lead).post('/api/v1/admin/mentors/staff/', {'admin_id': self.target.pk},
                                          format='json')
        self.assertEqual(r.status_code, 404, r.content[:200])
        self.target.refresh_from_db()
        self.assertIsNone(self.target.mentor_id)

    def test_the_invitations_backfill_skips_them(self):
        bare = make_admin('admin', owning_org=self.org)
        gone = make_admin('admin', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=gone.pk).update(archived_at=timezone.now(), is_active=False,
                                                       supabase_user_id=None)
        call_command('backfill_invitations', '--apply', stdout=io.StringIO())
        self.assertTrue(Invitation.objects.filter(partner_admin=bare).exists())
        self.assertFalse(Invitation.objects.filter(partner_admin=gone).exists())


class TestArchivedMentorOffTheMentorsTab(_Base):
    def setUp(self):
        self.login = make_admin('mentor', owning_org=self.org, first_seen_at=timezone.now())
        self.live = make_admin('mentor', owning_org=self.org, first_seen_at=timezone.now())
        MentorAssignment.objects.create(application=make_application('active'), mentor=self.login.mentor,
                                        ended_at=timezone.now())
        r = self.delete(self.lead, self.login, ARCHIVE, url=f'/api/v1/admin/mentors/{self.login.mentor_id}/')
        self.assertEqual(r.status_code, 200, r.content[:200])

    def test_the_list(self):
        r = authed_client(self.lead).get('/api/v1/admin/mentors/')
        self.assertEqual(r.status_code, 200, r.content[:200])
        ids = _ids(r.json()['mentors'])
        self.assertIn(self.live.mentor_id, ids)
        self.assertNotIn(self.login.mentor_id, ids)

    def test_the_detail_and_every_action_answer_404(self):
        client, pk = authed_client(self.lead), self.login.mentor_id
        self.assertEqual(client.get(f'/api/v1/admin/mentors/{pk}/').status_code, 404)
        for action in ('resend', 'revoke', 'deactivate', 'reactivate', 'remove'):
            with self.subTest(action=action):
                r = client.post(f'/api/v1/admin/mentors/{pk}/{action}/', {}, format='json')
                self.assertEqual(r.status_code, 404, r.content[:200])
        self.login.refresh_from_db()
        self.assertEqual((self.login.is_active, self.login.supabase_user_id), (False, None))
