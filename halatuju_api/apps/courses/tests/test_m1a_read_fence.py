"""Sprint M1a (2026-11-10): the person page's read fence and the self guards (owner O10, brief §6), each
table's own preset on the person GET (O12, addendum), and no phone on any group table (owner O16).

O10: an org admin OPENS a fellow org admin's page (and their own), view-only: `editable` and `manageable`
false, no Delete, no Suspend; every write on that person stays refused. Nobody suspends or deletes
themselves. O16: the Admins, Reviewers and Mentors lists carry no `phone` key, even for somebody who shows
it to their team; the person page's `person` block keeps it under today's rule.
"""
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.courses.staff_delete_rules import delete_fields
from apps.courses.staff_fence import staff_target_readable
from apps.courses.tests.test_m1a_archive_restore import _Base
from apps.scholarship import staff_tables_admin
from apps.scholarship.models import StaffProfile
from apps.scholarship.tests.factories import authed_client, make_admin, make_org

NOW = timezone.now


def _page(caller, target):
    return authed_client(caller).get(f'/api/v1/admin/admins/{target.pk}/permissions/')


class TestTheReadFence(_Base):
    def setUp(self):
        self.fellow = make_admin('org_admin', owning_org=self.org, first_seen_at=NOW())
        self.reviewer = make_admin('reviewer', owning_org=self.org, first_seen_at=NOW())

    def test_a_fellow_org_admins_page_opens_view_only(self):
        r = _page(self.lead, self.fellow)
        self.assertEqual(r.status_code, 200, r.content[:300])
        body = r.json()
        self.assertEqual((body['editable'], body['manageable'], body['revocable']), (False, False, False))
        self.assertTrue(body['delete_never'])
        self.assertFalse(body['deletable'])
        self.assertEqual(body['person']['admin_id'], self.fellow.pk)

    def test_their_own_page_opens_view_only(self):
        body = _page(self.lead, self.lead).json()
        self.assertEqual((body['editable'], body['manageable'], body['revocable'], body['delete_never']),
                         (False, False, False, True))

    def test_a_manageable_persons_page_is_unchanged(self):
        body = _page(self.lead, self.reviewer).json()
        self.assertEqual((body['editable'], body['manageable'], body['revocable']), (True, True, True))

    def test_every_write_on_a_fellow_org_admin_stays_refused(self):
        client, pk = authed_client(self.lead), self.fellow.pk
        writes = {
            'permissions': client.patch(f'/api/v1/admin/admins/{pk}/permissions/', {'permissions': []},
                                        format='json'),
            'role': client.patch(f'/api/v1/admin/admins/{pk}/role/', {'role': 'admin'}, format='json'),
            'revoke': client.patch(f'/api/v1/admin/admins/{pk}/revoke/', {'action': 'revoke'}, format='json'),
            'delete': self.delete(self.lead, self.fellow),
            'tables': client.post('/api/v1/admin/team/reviewers/', {'admin_id': pk, 'action': 'add'},
                                  format='json'),
        }
        for name, r in writes.items():
            with self.subTest(write=name):
                self.assertIn(r.status_code, (403, 404), r.content[:200])
        self.fellow.refresh_from_db()
        self.assertEqual((self.fellow.role, self.fellow.is_active), ('org_admin', True))

    def test_never_wider_than_one_organisation_and_never_a_super_or_a_mentor_login(self):
        elsewhere = make_admin('org_admin', owning_org=make_org(), first_seen_at=NOW())
        login = make_admin('mentor', owning_org=self.org, first_seen_at=NOW())
        for target in (elsewhere, self.super, login):
            with self.subTest(target=target.role):
                self.assertFalse(staff_target_readable(self.lead, target))
                self.assertEqual(_page(self.lead, target).status_code, 404)
        archived = make_admin('org_admin', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=archived.pk).update(archived_at=NOW(), is_active=False)
        archived.refresh_from_db()
        self.assertFalse(staff_target_readable(self.lead, archived))

    def test_a_reviewer_still_opens_no_page(self):
        self.assertEqual(_page(self.reviewer, self.lead).status_code, 403)


class TestNoSelfSuspendNoSelfDelete(_Base):
    def test_a_super_cannot_suspend_themselves(self):
        r = authed_client(self.super).patch(f'/api/v1/admin/admins/{self.super.pk}/revoke/',
                                            {'action': 'revoke'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (403, 'self'))

    def test_an_org_admin_cannot_suspend_themselves(self):
        r = authed_client(self.lead).patch(f'/api/v1/admin/admins/{self.lead.pk}/revoke/',
                                           {'action': 'revoke'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (403, 'self'))
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.is_active)

    def test_the_delete_answer_for_yourself_is_never(self):
        fields = delete_fields(self.super, self.super)
        self.assertEqual((fields['delete_never'], fields['deletable'], fields['revocable']), (True, False, False))


class TestTablePresets(_Base):
    def test_every_role_gets_a_preset_for_both_tables(self):
        for role in ('org_admin', 'admin', 'reviewer', 'qc', 'finance', 'member'):
            with self.subTest(role=role):
                presets = staff_tables_admin.table_presets(make_admin(role, owning_org=self.org))
                self.assertEqual(set(presets), {'admins', 'reviewers'})
                self.assertTrue(set(presets['admins']) <= set(staff_tables_admin.ADMIN_TABLE_KEYS))
                self.assertTrue(set(presets['reviewers']) <= set(staff_tables_admin.REVIEWER_TABLE_KEYS))
                self.assertTrue(presets['admins'] and presets['reviewers'])

    def test_a_reviewer_reads_review_and_an_admin_add_where_their_label_gives_nothing(self):
        presets = staff_tables_admin.table_presets(make_admin('reviewer', owning_org=self.org))
        self.assertEqual(presets['reviewers'], ['review'])
        self.assertEqual(set(presets['admins']), set(staff_tables_admin.ADD_KEYS['admins']))

    def test_the_person_get_carries_them(self):
        target = make_admin('reviewer', owning_org=self.org, first_seen_at=NOW())
        body = _page(self.lead, target).json()
        self.assertEqual(body['table_presets'], staff_tables_admin.table_presets(target))


class TestNoPhoneOnAGroupTable(_Base):
    """Owner O16: a phone shows on the person page only, never on the Admins, Reviewers or Mentors table."""

    PHONE = '+60 11-0000 0001'

    def setUp(self):
        self.shown = make_admin('reviewer', owning_org=self.org, first_seen_at=NOW(), name='Shown Reviewer')
        self.admin = make_admin('admin', owning_org=self.org, first_seen_at=NOW(), name='Shown Admin')
        self.login = make_admin('mentor', owning_org=self.org, first_seen_at=NOW(), name='Shown Mentor')
        for who in (self.shown, self.admin, self.login):
            StaffProfile.objects.create(partner_admin=who, phone=self.PHONE, share_phone_with_team=True)

    def test_no_list_carries_a_phone_even_when_shared(self):
        client = authed_client(self.lead)
        for url, key in (('/api/v1/admin/admins/', 'admins'), ('/api/v1/admin/reviewers/', 'reviewers'),
                         ('/api/v1/admin/mentors/', 'mentors')):
            with self.subTest(url=url):
                r = client.get(url)
                self.assertEqual(r.status_code, 200, r.content[:200])
                body = r.json()
                rows = body if isinstance(body, list) else body[key]
                self.assertTrue(rows)
                for row in rows:
                    self.assertNotIn('phone', row)
                self.assertNotIn(self.PHONE, str(body))

    def test_the_person_page_keeps_it_when_shared_and_lacks_it_when_not(self):
        self.assertEqual(_page(self.lead, self.admin).json()['person']['profile']['phone'], self.PHONE)
        StaffProfile.objects.filter(partner_admin=self.admin).update(share_phone_with_team=False)
        self.assertEqual(_page(self.lead, self.admin).json()['person']['profile']['phone'], '')

    def test_the_mentor_page_keeps_the_mentor_login_s_own_number(self):
        r = authed_client(self.lead).get(f'/api/v1/admin/mentors/{self.login.mentor_id}/')
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertNotIn('phone', r.json()['mentor'])
        self.assertEqual(r.json()['person']['profile']['phone'], self.PHONE)
