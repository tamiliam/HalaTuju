"""Sprint S1b owner ruling (20 Nov): a re-invite after Cancel behaves EXACTLY as a brand-new invite.

Owner: "I should be able to invite again if desired as if new." So two organisations run side by side:
in one a never-before-seen address is invited; in the other an address is invited, cancelled (S1b: the
invitee is archived) and invited again. Every surface the lead reads, and the invitee's first sign-in,
must serve the same thing for both, once ids, addresses and clocks are set aside. The old revoked
invitation stays in the database untouched (the audit record) but is on no list. Supabase is mocked.
"""
import re
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship.models import Invitation, Mentor
from apps.scholarship.tests.factories import authed_client, make_admin, make_org
from apps.scholarship.tests.test_s1b_cancel_archives import NAME, _Base

FRESH = 'meena.fresh@example.org'
AGAIN = 'meena.again@example.org'
ISO = re.compile(r'^\d{4}-\d\d-\d\dT')


def _same_shape(value, swap, key=''):
    """``value`` with this scenario's own ids, addresses and codes swapped for tokens and every
    timestamp read as 'T', so two scenarios can be compared field by field. A number is swapped only
    under an id key (a count of 1 is not invitation 1)."""
    if isinstance(value, dict):
        return {k: _same_shape(v, swap, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_same_shape(v, swap, key) for v in value]
    if isinstance(value, str) and ISO.match(value):
        return 'T'
    if isinstance(value, str) or (type(value) is int and (key == 'id' or key.endswith('_id'))):
        return swap.get(value, value)
    return value


class TestAReInviteAfterCancelBehavesAsNew(_Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.org_new, cls.org_again = make_org(), make_org()
        cls.lead_new = make_admin('org_admin', owning_org=cls.org_new, first_seen_at=timezone.now())
        cls.lead_again = make_admin('org_admin', owning_org=cls.org_again, first_seen_at=timezone.now())

    # ── the two scenarios ────────────────────────────────────────────────────────────
    def fresh(self):
        return self.invite(self.lead_new, email=FRESH, uid='uid-new')

    def reinvited(self, *, mentor=False):
        first, account = self.invite(self.lead_again, email=AGAIN, uid='uid-again-1')
        PartnerAdmin.objects.filter(pk=account.pk).update(created_at=timezone.now() - timedelta(days=30))
        if mentor:   # added to Mentors before they ever signed in
            self.add_to_mentors(self.lead_again, account)
        self.assertEqual(self.cancel(self.lead_again, first).status_code, 200)
        first.refresh_from_db()
        self.revoked_at = first.revoked_at
        inv, back = self.invite(self.lead_again, email=AGAIN, uid='uid-again-2')
        self.assertEqual(back.pk, account.pk)          # the same row, restored (M1a)
        return first, inv, back

    def add_to_mentors(self, lead, account):
        r = authed_client(lead).post('/api/v1/admin/mentors/staff/', {'admin_id': account.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content[:300])

    def swap(self, lead, org, account, *invs):
        out = {account.pk: 'PERSON', account.email: 'EMAIL', lead.pk: 'LEAD', lead.email: 'LEAD_EMAIL',
               org.pk: 'ORG', org.code: 'ORG_CODE', org.name: 'ORG_NAME',
               account.supabase_user_id or '-': 'UID'}
        out.update({inv.pk: 'INVITATION' for inv in invs})
        return out

    def served(self, lead, org, account, inv):
        """Everything the lead reads about ``account``, and what they themselves see on first sign-in."""
        from apps.scholarship import staff_mentor, staff_tables_admin
        c, swap = authed_client(lead), self.swap(lead, org, account, inv)

        def get(url):
            r = c.get(url)
            self.assertEqual(r.status_code, 200, (url, r.content[:300]))
            return r.json()

        def mine(rows):
            return [r for r in rows if r.get('id') == account.pk or r.get('email') == account.email]

        out = {
            'invitations': get('/api/v1/admin/invitations/?kind=reviewers'),
            'invitations_all': get('/api/v1/admin/invitations/?kind=reviewers&all=1'),
            'admins_list': mine(get('/api/v1/admin/admins/')['admins']),
            'reviewers_list': mine(get('/api/v1/admin/reviewers/')['reviewers']),
            'reviewer_page': get(f'/api/v1/admin/reviewers/{account.pk}/'),
            'person_page': get(f'/api/v1/admin/admins/{account.pk}/permissions/'),
            'my_pending': get('/api/v1/admin/scholarship/my-pending/'),
            'mentors_list': mine(get('/api/v1/admin/mentors/')['mentors']),
            'mentor_picker': account.pk in {a.pk for a in staff_mentor.candidates([org.pk])},
            'team_picker': account.pk in {
                a.pk for a, _ in staff_tables_admin.candidates(lead, 'admins', org.pk)},
        }
        return _same_shape(out, swap)

    def first_sign_in(self, account, inv, lead, org):
        account.refresh_from_db()
        r = authed_client(account).get('/api/v1/admin/role/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        inv.refresh_from_db()
        return _same_shape({'role': r.json(), 'invitation': inv.accepted_at is not None},
                           self.swap(lead, org, account, inv))

    # ── the pins ─────────────────────────────────────────────────────────────────────
    def test_every_surface_serves_the_same_as_a_brand_new_invitee(self):
        inv_new, new = self.fresh()
        old, inv_again, again = self.reinvited()
        want = self.served(self.lead_new, self.org_new, new, inv_new)
        got = self.served(self.lead_again, self.org_again, again, inv_again)
        self.maxDiff = None
        self.assertEqual(got, want)
        self.assertEqual(len(want['invitations_all']['invitations']), 1)   # one row, never the old one too
        again.refresh_from_db()
        self.assertGreater(again.created_at, timezone.now() - timedelta(minutes=1))   # "Joined" is today

    def test_the_first_sign_in_is_the_same_and_closes_only_the_new_invitation(self):
        inv_new, new = self.fresh()
        old, inv_again, again = self.reinvited()
        self.assertEqual(self.first_sign_in(again, inv_again, self.lead_again, self.org_again),
                         self.first_sign_in(new, inv_new, self.lead_new, self.org_new))
        inv_again.refresh_from_db()
        self.assertIsNotNone(inv_again.accepted_at)
        old.refresh_from_db()
        self.assertIsNone(old.accepted_at)                      # the cancelled one is never "accepted"
        self.assertEqual(old.revoked_at, self.revoked_at)       # and its record is untouched

    def test_the_cancelled_invitation_stays_as_the_record_but_on_no_list(self):
        old, inv, again = self.reinvited()
        self.assertTrue(Invitation.objects.filter(pk=old.pk, revoked_at=self.revoked_at).exists())
        for url in ('/api/v1/admin/invitations/?kind=reviewers',
                    '/api/v1/admin/invitations/?kind=reviewers&all=1'):
            body = authed_client(self.lead_again).get(url).json()
            self.assertEqual([r['id'] for r in body['invitations']], [inv.pk], url)
            self.assertEqual(body['totals']['reviewers'], 1, url)

    def test_a_cancelled_invitation_nobody_re_sent_is_unchanged(self):
        inv, account = self.invite(self.lead_again, email=AGAIN, uid='uid-again-1')
        self.assertEqual(self.cancel(self.lead_again, inv).status_code, 200)
        body = authed_client(self.lead_again).get('/api/v1/admin/invitations/?kind=reviewers&all=1').json()
        self.assertEqual(body['invitations'], [])                # as S1b built it: off the list

    def test_a_mentor_link_that_never_mentored_goes_like_a_new_invitees(self):
        inv_new, new = self.fresh()
        old, inv_again, again = self.reinvited(mentor=True)
        again.refresh_from_db()
        self.assertIsNone(again.mentor_id)
        want = self.served(self.lead_new, self.org_new, new, inv_new)
        got = self.served(self.lead_again, self.org_again, again, inv_again)
        self.maxDiff = None
        self.assertEqual(got, want)
        self.assertTrue(got['mentor_picker'])                   # Add to Mentors offers them again
        self.assertEqual(got['mentors_list'], [])                # never "Mentored before"
        # The mentor record made for them stays, deactivated, as the record.
        self.assertTrue(Mentor.objects.filter(organisation=self.org_again,
                                              deactivated_at__isnull=False).exists())
        self.add_to_mentors(self.lead_again, again)               # and adding them works as for anyone

    def test_a_restored_person_who_had_signed_in_keeps_their_joined_date(self):
        from apps.courses import staff_archive
        joined = timezone.now() - timedelta(days=90)
        row = make_admin('reviewer', owning_org=self.org_again, first_seen_at=joined)
        PartnerAdmin.objects.filter(pk=row.pk).update(created_at=joined, archived_at=timezone.now(),
                                                      is_active=False, supabase_user_id=None)
        back, _, err = staff_archive.restore(row, name=NAME, role='reviewer', org=None,
                                             owning_org=self.org_again)
        self.assertIsNone(err)
        back.refresh_from_db()
        self.assertEqual(back.created_at, joined)               # a returning colleague, not a new one

    def test_a_mentor_link_with_a_scholar_on_record_is_kept(self):
        from apps.scholarship.models import MentorAssignment
        from apps.scholarship.tests.factories import make_application
        first, account = self.invite(self.lead_again, email=AGAIN, uid='uid-again-1')
        self.add_to_mentors(self.lead_again, account)
        account.refresh_from_db()
        MentorAssignment.objects.create(application=make_application('submitted'), mentor=account.mentor,
                                        ended_at=timezone.now())   # mentored once, now ended
        self.assertEqual(self.cancel(self.lead_again, first).status_code, 200)
        inv, back = self.invite(self.lead_again, email=AGAIN, uid='uid-again-2')
        back.refresh_from_db()
        self.assertEqual(back.mentor_id, account.mentor_id)      # the history stays theirs (M1a)


class TestOwnerRuling23NovTheChangesListAndPastMentoring(TestAReInviteAfterCancelBehavesAsNew):
    """Owner, 23 Nov: tidy BOTH places S1b left showing earlier history. Read filters only: the
    `staff_permission_changes` rows and every scholar-side record stay as they were."""

    def change(self, account, org, by, *, role='org_admin'):
        from apps.scholarship.models import StaffPermissionChange
        return StaffPermissionChange.objects.create(
            target=account, target_email=account.email, organisation=org, role=account.role,
            before=['review'], after=['review', 'see_all'], changed_by_email=by.email if by else '',
            changed_by_role=role)

    def history(self, lead, account):
        r = authed_client(lead).get(f'/api/v1/admin/admins/{account.pk}/permissions/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.json()['history']

    def reinvited_after_a_change(self):
        first, account = self.invite(self.lead_again, email=AGAIN, uid='uid-again-1')
        old = self.change(account, self.org_again, self.lead_again)   # a key change before the Cancel
        self.assertEqual(self.cancel(self.lead_again, first).status_code, 200)
        inv, back = self.invite(self.lead_again, email=AGAIN, uid='uid-again-2')
        self.assertEqual(back.pk, account.pk)
        return old, inv, back

    def test_the_changes_list_of_a_re_invited_person_reads_as_a_brand_new_invitees(self):
        from apps.scholarship.models import StaffPermissionChange
        inv_new, new = self.fresh()
        old, inv_again, again = self.reinvited_after_a_change()
        want = self.served(self.lead_new, self.org_new, new, inv_new)
        got = self.served(self.lead_again, self.org_again, again, inv_again)
        self.maxDiff = None
        self.assertEqual(got, want)
        self.assertEqual(got['person_page']['history'], [])
        self.assertTrue(StaffPermissionChange.objects.filter(pk=old.pk, target=again).exists())   # kept
        later = self.change(again, self.org_again, self.lead_again)   # a change after the re-invite shows
        self.assertEqual([h['at'] for h in self.history(self.lead_again, again)],
                         [later.created_at.isoformat().replace('+00:00', 'Z')])

    def test_a_person_never_cancelled_keeps_their_full_changes_list(self):
        inv, account = self.invite(self.lead_again, email=AGAIN, uid='uid-again-1')
        self.change(account, self.org_again, None, role='migration')   # a migration's row
        self.change(account, self.org_again, self.lead_again)
        rows = self.history(self.lead_again, account)
        self.assertEqual(len(rows), 2)
        self.assertEqual([r['by_migration'] for r in rows], [False, True])

    def test_ordinary_staff_with_no_invitation_keep_their_migration_rows(self):
        row = make_admin('reviewer', owning_org=self.org_again, first_seen_at=timezone.now())
        self.change(row, self.org_again, None, role='migration')
        self.assertEqual(len(self.history(self.lead_again, row)), 1)

    def test_a_restored_person_who_had_signed_in_keeps_their_changes_list(self):
        from apps.courses import staff_archive
        inv, account = self.invite(self.lead_again, email=AGAIN, uid='uid-again-1')
        self.change(account, self.org_again, self.lead_again)
        PartnerAdmin.objects.filter(pk=account.pk).update(
            first_seen_at=timezone.now(), archived_at=timezone.now(), is_active=False, supabase_user_id=None)
        account.refresh_from_db()
        back, _, err = staff_archive.restore(account, name=NAME, role='reviewer', org=None,
                                             owning_org=self.org_again)
        self.assertIsNone(err)
        self.assertEqual(len(self.history(self.lead_again, back)), 1)

    def test_a_re_invited_former_mentor_is_offered_as_new_and_the_scholars_file_keeps_the_history(self):
        from apps.scholarship import mentoring_read
        from apps.scholarship.models import MentorAssignment, MentoringSession
        from apps.scholarship.tests.factories import make_application
        inv_new, new = self.fresh()
        first, account = self.invite(self.lead_again, email=AGAIN, uid='uid-again-1')
        self.add_to_mentors(self.lead_again, account)
        account.refresh_from_db()
        mentor_id, app = account.mentor_id, make_application('submitted')
        done = MentorAssignment.objects.create(application=app, mentor=account.mentor, ended_at=timezone.now())
        MentoringSession.objects.create(application=app, mentor=account.mentor, assignment=done,
                                        met_on=timezone.now().date(), mode=MentoringSession.MODE_PHONE)
        self.assertEqual(self.cancel(self.lead_again, first).status_code, 200)
        inv_again, again = self.invite(self.lead_again, email=AGAIN, uid='uid-again-2')
        again.refresh_from_db()
        self.assertEqual(again.mentor_id, mentor_id)               # the link is kept: the name lives on it
        want = self.served(self.lead_new, self.org_new, new, inv_new)
        got = self.served(self.lead_again, self.org_again, again, inv_again)
        # Kept on purpose: their name is on a scholar's records, so Delete counts that work (`work`,
        # `deletable`): it archives them instead of erasing them. Everything else reads as new.
        work = ('work', 'deletable', 'delete_never')

        def bare(rows):
            return [{k: v for k, v in r.items() if k not in work} for r in rows]
        self.maxDiff = None
        for key in ('mentor_picker', 'mentors_list', 'invitations', 'invitations_all', 'team_picker'):
            self.assertEqual(got[key], want[key], key)
        for key in ('admins_list', 'reviewers_list'):
            self.assertEqual(bare(got[key]), bare(want[key]), key)
        self.assertEqual(bare([got['person_page']]), bare([want['person_page']]))
        self.assertTrue(got['mentor_picker'])                     # Add to Mentors offers them again
        self.assertEqual(got['mentors_list'], [])                  # never "Mentored before"
        self.assertIsNone(got['person_page']['person']['mentor_id'])

        def file():
            return mentoring_read.file_payload(self.lead_again, app)
        before = file()
        self.assertEqual([(h['id'], h['name']) for h in before['history']], [(done.pk, NAME)])
        self.assertEqual([m['mentor_name'] for m in before['meetings']], [NAME])
        self.add_to_mentors(self.lead_again, again)                # added like anyone
        again.refresh_from_db()
        self.assertEqual(again.mentor_id, mentor_id)               # the same record, switched back on
        self.assertIsNone(again.mentor.deactivated_at)
        self.assertTrue(MentorAssignment.objects.filter(pk=done.pk, ended_at__isnull=False).exists())
        self.assertEqual(file()['history'], before['history'])     # the scholar's file is unchanged
        self.assertEqual(file()['meetings'], before['meetings'])

    def test_a_staff_mentor_removed_while_here_is_still_mentored_before(self):
        from apps.scholarship import staff_mentor
        from apps.scholarship.models import MentorAssignment
        from apps.scholarship.tests.factories import make_application
        row = make_admin('reviewer', owning_org=self.org_again, first_seen_at=timezone.now())
        self.add_to_mentors(self.lead_again, row)
        row.refresh_from_db()
        MentorAssignment.objects.create(application=make_application('submitted'), mentor=row.mentor,
                                        ended_at=timezone.now())
        Mentor.objects.filter(pk=row.mentor_id).update(deactivated_at=timezone.now())
        row.refresh_from_db()
        self.assertFalse(staff_mentor.mentored_before_joining(row))
        self.assertNotIn(row.pk, {a.pk for a in staff_mentor.candidates([self.org_again.pk])})
        body = authed_client(self.lead_again).get('/api/v1/admin/mentors/').json()['mentors']
        self.assertEqual([m['status'] for m in body if m['id'] == row.mentor_id], ['inactive'])
        r = authed_client(self.lead_again).post('/api/v1/admin/mentors/staff/', {'admin_id': row.pk},
                                                format='json')
        self.assertEqual(r.status_code, 409)                       # still `resume`'s, as before
