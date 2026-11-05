"""Request #60 (BrightPath, owner ruling 2026-11-05): a mentor invite sent in error and revoked must not
block the address from being invited as STAFF.

A NARROW exception to the S7d rule "a re-invite never turns a mentor login into another role"
(`staff_reinvite.unused_revoked_mentor` + `may_reuse` + `bring_back`). It applies only when the login
row is a `mentor`, switched off, never signed in (`first_seen_at` NULL), its Mentor record is
deactivated, it has no footprint, and it is in the caller's organisation (or the caller is a super).
Every other mentor row, and every source user, is still refused with the same 409 as before (an org
admin's `not_invitable`; a super's `already_on_team` ... "Ask HalaTuju support").
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_reinvite
from apps.courses.models import PartnerAdmin
from apps.scholarship.models import MentorAssignment
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_org,
)

NEUTRAL = "This email address can't be invited. Ask HalaTuju support."
WELCOME = 'apps.courses.views_staff.send_partner_welcome_email'
CREATE_LOGIN = 'apps.courses.supabase_admin._create_supabase_user'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co')
class RevokedMentorInvitedAsStaff(TestCase):

    def setUp(self):
        self.org = make_org(module_scholarship=True)
        self.other_org = make_org(module_scholarship=True)
        self.lead = make_admin('org_admin', owning_org=self.org)
        self.super = make_admin('super', super_admin=True)

    def _revoked_mentor(self, email='kamala@example.org', org=None, **changes):
        """A mentor invited in error and revoked (`mentor_invite._switch_off`): login off, no UID
        (never linked), never seen, Mentor stamped deactivated. ``changes`` bend one of those."""
        row = make_admin('mentor', owning_org=org or self.org, email=email, name='Kamala')
        mentor_off = changes.pop('mentor_deactivated', True)
        fields = {'is_active': False, 'first_seen_at': None, 'supabase_user_id': None, **changes}
        PartnerAdmin.objects.filter(pk=row.pk).update(**fields)
        if mentor_off:
            type(row.mentor).objects.filter(pk=row.mentor_id).update(deactivated_at=timezone.now())
        row.refresh_from_db()
        return row

    def _invite(self, caller, email, role='reviewer', name='Kamala Devi'):
        with patch(WELCOME, return_value=True), \
                patch(CREATE_LOGIN, return_value=('new-uid-60', False, None)):
            return authed_client(caller).post('/api/v1/admin/invite/',
                                              {'email': email, 'name': name, 'role': role},
                                              format='json')

    def _assert_refused(self, caller, row, role='reviewer'):
        """The 409 is unchanged from before request #60: an org admin gets the neutral
        `not_invitable`; a super (who sees every account) is told whose account it is and to ask
        support (`already_exists_answer`)."""
        r = self._invite(caller, row.email, role=role)
        self.assertEqual(r.status_code, 409, r.content)
        if caller.is_super:
            self.assertEqual(r.json()['code'], 'already_on_team')
            self.assertTrue(r.json()['error'].endswith('Ask HalaTuju support to change this.'))
        else:
            self.assertEqual(r.json(), {'error': NEUTRAL, 'code': 'not_invitable'})
        fresh = PartnerAdmin.objects.get(pk=row.pk)
        self.assertEqual((fresh.role, fresh.mentor_id, fresh.is_active), (row.role, row.mentor_id, row.is_active))

    # ── the exception ──────────────────────────────────────────────────────────────────────────
    def test_a_revoked_never_signed_in_mentor_is_invited_as_a_reviewer(self):
        row = self._revoked_mentor()
        mentor = row.mentor
        r = self._invite(self.lead, row.email)
        self.assertEqual(r.status_code, 201, r.content)
        row.refresh_from_db()
        self.assertEqual((row.role, row.is_active, row.mentor_id, row.name, row.owning_organisation_id),
                         ('reviewer', True, None, 'Kamala Devi', self.org.pk))
        self.assertEqual(row.supabase_user_id, 'new-uid-60')
        self.assertEqual(PartnerAdmin.objects.filter(email__iexact=row.email).count(), 1)
        mentor.refresh_from_db()
        self.assertIsNotNone(mentor.deactivated_at)            # never reactivated
        self.assertFalse(PartnerAdmin.objects.filter(mentor=mentor).exists())

    def test_an_org_admin_may_also_invite_them_as_an_admin(self):
        row = self._revoked_mentor()
        r = self._invite(self.lead, row.email, role='admin')
        self.assertEqual(r.status_code, 201, r.content)
        row.refresh_from_db()
        self.assertEqual((row.role, row.mentor_id), ('admin', None))

    def test_a_super_may_invite_another_organisations_revoked_mentor(self):
        row = self._revoked_mentor(email='kamala@gmail.com', org=self.other_org)
        r = self._invite(self.super, row.email, role='qc')
        self.assertEqual(r.status_code, 201, r.content)
        row.refresh_from_db()
        self.assertEqual((row.role, row.is_active, row.mentor_id), ('qc', True, None))

    # ── everything else stays refused, with the same answer ────────────────────────────────────
    def test_a_mentor_who_has_signed_in_is_refused(self):
        row = self._revoked_mentor(first_seen_at=timezone.now())
        self.assertFalse(staff_reinvite.may_reuse(self.lead, row))
        self._assert_refused(self.lead, row)
        self._assert_refused(self.super, row)

    def test_a_mentor_still_active_is_refused(self):
        row = self._revoked_mentor(is_active=True, mentor_deactivated=False)
        self._assert_refused(self.lead, row)
        self._assert_refused(self.super, row)

    def test_a_switched_off_login_whose_mentor_is_still_active_is_refused(self):
        row = self._revoked_mentor(mentor_deactivated=False)
        self.assertFalse(staff_reinvite.may_reuse(self.super, row))
        self._assert_refused(self.super, row)
        self.assertEqual(staff_reinvite.bring_back(row, name='N', role='reviewer', org=None,
                                                   owning_org=self.org)[2], 'not_reusable')

    def test_a_mentor_with_footprint_is_refused(self):
        row = self._revoked_mentor()
        MentorAssignment.objects.create(application=make_application(), mentor=row.mentor)
        self._assert_refused(self.lead, row)
        self._assert_refused(self.super, row)

    def test_another_organisations_mentor_is_refused_to_an_org_admin(self):
        row = self._revoked_mentor(org=self.other_org)
        self.assertFalse(staff_reinvite.may_reuse(self.lead, row))
        self._assert_refused(self.lead, row)

    def test_a_source_user_is_still_refused(self):
        row = make_admin('source_partner', owning_org=self.org, email='source60@example.org')
        PartnerAdmin.objects.filter(pk=row.pk).update(is_active=False, first_seen_at=None,
                                                      supabase_user_id=None)
        row.refresh_from_db()
        self.assertFalse(staff_reinvite.may_reuse(self.super, row))
        self._assert_refused(self.lead, row)
        self._assert_refused(self.super, row)

    def test_bring_back_never_turns_it_into_a_non_staff_role(self):
        row = self._revoked_mentor()
        self.assertEqual(staff_reinvite.bring_back(row, name='N', role='source_partner', org=None,
                                                   owning_org=self.org)[2], 'not_reusable')
        row.refresh_from_db()
        self.assertEqual(row.role, 'mentor')
