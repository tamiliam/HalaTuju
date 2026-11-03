"""Team tables T4 — Team -> Emails -> Admin emails: the ONE list of what an organisation's admins are sent
(`admin_email_catalogue`, served by `GET admin/admin-emails/`).

Pinned from the harm:
  * NO ADMIN EMAIL SHIPS UNLISTED: every non-student ``send_*`` (`student_email_catalogue.NOT_STUDENT_SENDERS`,
    itself a full partition of the emails package) is either a row here or named in ``NOT_ADMIN_SENDERS``
    with its reason — a new sender in neither fails;
  * HalaTuju's own inbox is not shown as the organisation's (lead ruling 2026-11-03);
  * the list carries no address and no organisation data, and opens to exactly the people who read the
    reviewer / sponsor templates — never wider.
"""
from django.test import TestCase, override_settings

from apps.scholarship import admin_email_catalogue as cat
from apps.scholarship import student_email_catalogue as student_cat
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_org
from apps.scholarship.tests.test_student_email_catalogue import _package_senders

URL = '/api/v1/admin/admin-emails/'


class TestEveryAdminEmailIsListed(TestCase):
    def test_the_non_student_senders_are_partitioned_once(self):
        listed = {s for e in cat.CATALOGUE for s in e.senders}
        named = set(cat.NOT_ADMIN_SENDERS)
        self.assertEqual(listed & named, set(), 'A sender is both an admin row and NOT_ADMIN.')
        unclassified = student_cat.NOT_STUDENT_SENDERS - listed - named
        self.assertEqual(unclassified, set(), 'A new non-student send_* must be added to '
                         'admin_email_catalogue.CATALOGUE (an admin email) or NOT_ADMIN_SENDERS.')
        self.assertEqual((listed | named) - student_cat.NOT_STUDENT_SENDERS, set(),
                         'A sender here that the student catalogue does not name as non-student.')

    def test_every_listed_sender_exists_in_the_emails_package(self):
        package = _package_senders()
        for e in cat.CATALOGUE:
            for sender in e.senders:
                with self.subTest(key=e.key, sender=sender):
                    self.assertIn(sender, package)
        self.assertEqual(set(cat.NOT_ADMIN_SENDERS) - package, set())

    def test_keys_are_unique_and_every_reason_is_said(self):
        keys = [e.key for e in cat.CATALOGUE]
        self.assertEqual(len(keys), len(set(keys)))
        for name, reason in cat.NOT_ADMIN_SENDERS.items():
            self.assertTrue(reason.strip(), name)

    def test_the_rows_are_the_ten_read_off_the_senders(self):
        # T4: rows 1-10 of the builder's audit; the six HalaTuju-inbox senders and the three request /
        # profile / contact ones that only reach HalaTuju are NOT the organisation's (lead ruling).
        self.assertEqual([e.key for e in cat.CATALOGUE], [
            'payment_approval', 'payment_check', 'payment_instruction', 'request_question', 'request_quote',
            'verdict_escalation', 'countersign_pending', 'agreement_executed', 'invoice', 'receipt'])
        for halatuju_only in ('send_org_request_submitted_email', 'send_profile_complete_admin_email',
                              'send_contact_submission_admin_email'):
            self.assertEqual(cat.NOT_ADMIN_SENDERS[halatuju_only], 'sent to HalaTuju, not to your team')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.people = {role: make_admin(role, owning_org=cls.org)
                      for role in ('org_admin', 'admin', 'finance', 'reviewer', 'qc')}
        cls.people['super'] = make_admin('super', super_admin=True)

    def _get(self, who):
        return authed_client(self.people[who]).get(URL)

    def test_the_template_editors_read_it_and_nobody_else(self):
        # The sponsor / partner templates' gate (`may_do_admin_work`): super, org_admin, admin.
        for who, code in (('super', 200), ('org_admin', 200), ('admin', 200),
                          ('finance', 403), ('reviewer', 403), ('qc', 403)):
            with self.subTest(who=who):
                self.assertEqual(self._get(who).status_code, code)

    def test_it_serves_the_keys_in_order_and_no_address(self):
        r = self._get('org_admin')
        self.assertEqual(r.json(), {'emails': [{'key': e.key} for e in cat.CATALOGUE]})
        self.assertNotIn(b'@', r.content)

    def test_read_only(self):
        client = authed_client(self.people['org_admin'])
        self.assertEqual(client.patch(URL, {}, format='json').status_code, 405)
        self.assertEqual(client.post(URL, {}, format='json').status_code, 405)
