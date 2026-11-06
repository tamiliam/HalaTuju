"""TD-501 / SEC-17 (audit fix A1.3) — a reviewer invite names its gift.

Owner ruling "b": inviting a reviewer asks for an explicit choice, one gift or every gift. No choice
is refused (400). A gift outside the owning organisation is 404. Admins are not asked. A re-invite
stores the gift the new invite chose, never NULL. A read-only report lists the reviewer rows whose
gift was never chosen. And a reviewer invited to gift A cannot read a gift-B case.

No real student data: every name and address here is synthetic.
"""
import io
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.courses import staff_gift
from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme,
)

INVITE = '/api/v1/admin/invite/'
APPS = '/api/v1/admin/scholarship/applications/'
CREATE = 'apps.courses.views_admin.http_requests.post'
WELCOME = 'apps.courses.views_staff.send_partner_welcome_email'


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   SUPABASE_URL='https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY='k')
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bp = PartnerOrganisation.objects.get(code='brightpath')
        cls.gift_a = make_programme(organisation=cls.bp, name_en='Gift A')
        cls.gift_b = make_programme(organisation=cls.bp, name_en='Gift B')
        cls.elsewhere = make_programme(organisation=make_org(), name_en='Another tenant gift')
        cls.org_admin = make_admin('org_admin', owning_org=cls.bp, uid='gift-oa-uid')

    def _invite(self, body, caller=None):
        payload = {'email': 'new.reviewer@example.org', 'name': 'New Reviewer', 'role': 'reviewer'}
        payload.update(body)
        with patch(CREATE) as create, patch(WELCOME, return_value=True):
            create.return_value = MagicMock(status_code=200, text='ok', json=lambda: {'id': 'gift-new-uid'})
            return authed_client(caller or self.org_admin).post(INVITE, payload, format='json')


class TestTheInviteAsksForTheGift(_Base):
    def test_no_choice_is_refused_and_nothing_is_written(self):
        r = self._invite({})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'gift_required'))
        self.assertFalse(PartnerAdmin.objects.filter(email='new.reviewer@example.org').exists())

    def test_an_unknown_choice_is_refused(self):
        r = self._invite({'gift_scope': 'some'})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'gift_required'))

    def test_one_gift_without_naming_it_is_refused(self):
        for bad in (None, '', 'abc', 0, -3, True):
            with self.subTest(programme_id=bad):
                body = {'gift_scope': 'one'}
                if bad is not None:
                    body['programme_id'] = bad
                r = self._invite(body)
                self.assertEqual((r.status_code, r.json()['code']), (400, 'gift_required'))

    def test_one_gift_is_stored(self):
        r = self._invite({'gift_scope': 'one', 'programme_id': self.gift_a.id})
        self.assertEqual(r.status_code, 201, r.content)
        row = PartnerAdmin.objects.get(email='new.reviewer@example.org')
        self.assertEqual((row.role, row.programme_id), ('reviewer', self.gift_a.id))

    def test_a_gift_id_sent_as_text_is_accepted(self):
        r = self._invite({'gift_scope': 'one', 'programme_id': str(self.gift_b.id)})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(PartnerAdmin.objects.get(email='new.reviewer@example.org').programme_id,
                         self.gift_b.id)

    def test_another_organisations_gift_is_404_and_nothing_is_written(self):
        r = self._invite({'gift_scope': 'one', 'programme_id': self.elsewhere.id})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(PartnerAdmin.objects.filter(email='new.reviewer@example.org').exists())

    def test_every_gift_is_an_explicit_choice(self):
        r = self._invite({'gift_scope': 'every'})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(PartnerAdmin.objects.get(email='new.reviewer@example.org').programme_id)

    def test_every_gift_with_a_gift_named_is_refused(self):
        r = self._invite({'gift_scope': 'every', 'programme_id': self.gift_a.id})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'gift_conflict'))

    def test_a_super_inviting_a_reviewer_is_asked_too(self):
        boss = make_admin('super', super_admin=True, uid='gift-super-uid')
        self.assertEqual(self._invite({}, caller=boss).status_code, 400)
        r = self._invite({'gift_scope': 'one', 'programme_id': self.gift_a.id}, caller=boss)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(PartnerAdmin.objects.get(email='new.reviewer@example.org').programme_id,
                         self.gift_a.id)

    def test_an_admin_invite_is_unchanged(self):
        r = self._invite({'role': 'admin'})
        self.assertEqual(r.status_code, 201, r.content)
        row = PartnerAdmin.objects.get(email='new.reviewer@example.org')
        self.assertEqual((row.role, row.programme_id), ('admin', None))

    def test_only_the_reviewer_is_gift_scoped(self):
        self.assertEqual(staff_gift.GIFT_SCOPED_ROLES, frozenset({'reviewer'}))
        for role in ('admin', 'qc', 'finance', 'org_admin', 'partner', 'mentor', 'source_partner'):
            with self.subTest(role=role):
                self.assertEqual(staff_gift.for_invite({}, role, self.bp), (None, None))


class TestAReinviteKeepsTheGift(_Base):
    """Regression: `staff_reinvite.bring_back` used to write `programme = None` on every re-invite,
    so a cancelled reviewer came back covering every gift whatever the new invite said."""

    def _cancelled(self, programme):
        # A Google address: no password is issued, so the re-invite touches no Supabase login.
        return PartnerAdmin.objects.create(
            email='again.reviewer@gmail.com', name='Old Name', role='reviewer', is_active=False,
            owning_organisation=self.bp, programme=programme)

    def _reinvite(self, body):
        return self._invite({'email': 'again.reviewer@gmail.com', 'name': 'Again', **body})

    def test_a_reinvite_stores_the_gift_it_chose(self):
        row = self._cancelled(programme=self.gift_b)
        r = self._reinvite({'gift_scope': 'one', 'programme_id': self.gift_a.id})
        self.assertEqual(r.status_code, 201, r.content)
        row.refresh_from_db()
        self.assertTrue(row.is_active)
        self.assertEqual(row.programme_id, self.gift_a.id)

    def test_a_reinvite_to_the_same_gift_keeps_it(self):
        row = self._cancelled(programme=self.gift_a)
        r = self._reinvite({'gift_scope': 'one', 'programme_id': self.gift_a.id})
        self.assertEqual(r.status_code, 201, r.content)
        row.refresh_from_db()
        self.assertEqual(row.programme_id, self.gift_a.id)

    def test_a_reinvite_without_a_choice_is_refused_and_the_row_stays_off(self):
        row = self._cancelled(programme=self.gift_a)
        r = self._reinvite({})
        self.assertEqual(r.status_code, 400)
        row.refresh_from_db()
        self.assertEqual((row.is_active, row.programme_id), (False, self.gift_a.id))


class TestAGiftAReviewerCannotReadAGiftBCase(_Base):
    """The read is fenced by the organisation and by ASSIGNMENT (`_scoped_application`), so a
    reviewer invited to gift A reads none of gift B's cases they were not given."""

    def test_list_and_detail(self):
        r = self._invite({'gift_scope': 'one', 'programme_id': self.gift_a.id})
        self.assertEqual(r.status_code, 201, r.content)
        reviewer = PartnerAdmin.objects.get(email='new.reviewer@example.org')
        self.assertEqual(reviewer.programme_id, self.gift_a.id)
        mine = make_application(cohort=make_cohort(programme=self.gift_a), reviewer=reviewer)
        gift_b_case = make_application(cohort=make_cohort(programme=self.gift_b))
        self.assertEqual(gift_b_case.programme_id, self.gift_b.id)
        client = authed_client(reviewer)

        listed = client.get(APPS)
        self.assertEqual(listed.status_code, 200, listed.content[:300])
        ids = {row['id'] for row in listed.json()['applications']}
        self.assertIn(mine.id, ids)              # the control: this reviewer can read a case
        self.assertNotIn(gift_b_case.id, ids)
        # Same organisation, not assigned: `_scoped_application` refuses with the role 403.
        self.assertEqual(client.get(f'{APPS}{gift_b_case.id}/').status_code, 403)


class TestTheReport(_Base):
    def _report(self):
        out = io.StringIO()
        call_command('staff_gift_report', stdout=out)
        return out.getvalue()

    def test_lists_only_reviewers_with_no_gift_and_writes_nothing(self):
        unchosen = make_admin('reviewer', owning_org=self.bp, name='Hidden Name',
                              email='hidden.person@example.org')
        chosen = make_admin('reviewer', owning_org=self.bp, programme=self.gift_a)
        an_admin = make_admin('admin', owning_org=self.bp)
        before = list(PartnerAdmin.objects.order_by('id').values_list('id', 'programme_id', 'is_active'))

        text = self._report()

        listed = {line.split('\t')[0] for line in text.splitlines()[2:]}
        self.assertIn(str(unchosen.id), listed)
        self.assertNotIn(str(chosen.id), listed)
        self.assertNotIn(str(an_admin.id), listed)
        self.assertIn('reviewer\tbrightpath\tyes', text)
        # No personal data beyond the id: never the name or the email.
        self.assertNotIn('Hidden Name', text)
        self.assertNotIn('hidden.person@example.org', text)
        after = list(PartnerAdmin.objects.order_by('id').values_list('id', 'programme_id', 'is_active'))
        self.assertEqual(before, after)

    def test_an_empty_report_says_so(self):
        PartnerAdmin.objects.filter(role='reviewer').delete()
        self.assertIn('Reviewer rows with no gift chosen: 0', self._report())
