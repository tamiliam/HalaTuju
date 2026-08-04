"""Request #10, the owed half — the seven reviewer emails NOBODY can edit, shown read-only.

The owner's reason for asking, verbatim in substance: *"their existence and content are known to
the org_admin. If not specified, they'll exist in the background without anyone paying attention to
them until something breaks."* The five editable templates shipped on 2 August; this list did not,
and it was inside the same quoted line.

**The claim that carries the weight is that the preview cannot drift from the mail.** A screen that
shows an org_admin prose which merely RESEMBLES what we send is worse than a screen that shows
nothing — it is true on the day it is written and quietly false after the next edit, with nobody
looking. So `test_the_preview_IS_the_email` sends each one for real through the existing sender and
compares the delivered subject and body against what the endpoint served, character for character.
Break the split (let a builder and its sender diverge) and that test fails; it is the only reason
this list is trustworthy enough to publish.
"""
import jwt
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import emails as emails_mod
from apps.scholarship import reviewer_system_emails as sysmail

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
URL = '/api/v1/admin/reviewers/system-emails/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='sys', name='System Emails Org')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='sys-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='dina@sys.test')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='sys-rv', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Anand', email='anand@sys.test')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _rows(self):
        self._auth('sys-oa')
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['emails']


class TestTheList(_Base):
    def test_all_six_are_listed(self):
        keys = [x['key'] for x in self._rows()]
        self.assertEqual(keys, [k for k, _ in sysmail.SYSTEM_EMAILS])
        self.assertEqual(len(keys), 6)

    def test_THE_JOINING_EMAIL_IS_NOT_HERE_ANY_MORE(self):
        # ⚠ Owner, 2026-08-04: it became editable under Organisation → Invitations, so listing it
        # here as well showed one letter in two places — read-only in this list, editable in the
        # other. That is worse than either alone: an org_admin reading THIS list would conclude the
        # wording was fixed. Asserted as an ABSENCE because nothing else can see a duplicate, and
        # because restoring it would look like a harmless addition.
        self.assertNotIn('partner_welcome', [x['key'] for x in self._rows()])

    def test_every_one_carries_a_subject_and_a_body(self):
        # The owner asked for CONTENT, not a list of names. A row with an empty body would satisfy
        # "the seven are shown" and defeat the entire point of showing them.
        for row in self._rows():
            self.assertTrue(row['subject'].strip(), row['key'])
            self.assertGreater(len(row['body'].strip()), 200, row['key'])

    def test_no_placeholder_survives(self):
        # The sibling guard on the editable five. A `{ref}` reaching this screen would read as a
        # defect in the email itself to anybody looking at it.
        for row in self._rows():
            for token in ('{', '}'):
                self.assertNotIn(token, row['subject'], row['key'])
                self.assertNotIn(token, row['body'], row['key'])

    def test_NO_EMAIL_LEFT_IN_THIS_LIST_CARRIES_A_CREDENTIAL(self):
        # The credential-carrying letter left with `partner_welcome` (2026-08-04), so today nothing
        # here is sensitive — and this asserts the PROPERTY rather than the empty list, so an
        # eighth email that does carry one fails until it is flagged. The `sensitive` mechanism is
        # deliberately kept for that case; see `SENSITIVE_KEYS`.
        for row in self._rows():
            self.assertNotIn('temporary password', row['body'], row['key'])
            self.assertFalse(row['sensitive'], row['key'])

    def test_the_escalation_is_flagged_as_reaching_more_than_the_reviewer(self):
        # It also goes to the organisation's own admins. Exactly the kind of fact that stays
        # invisible until it surprises somebody.
        rows = {x['key']: x for x in self._rows()}
        self.assertTrue(rows['verdict_escalation']['wider_audience'])
        self.assertFalse(rows['interview_booked']['wider_audience'])


class TestItCannotDriftFromTheMail(_Base):
    """The load-bearing test. See the module docstring."""

    def test_the_preview_IS_the_email(self):
        rows = {x['key']: x for x in self._rows()}
        to = 'anand@sys.test'
        # Each sender called with the SAME sample particulars the catalogue renders, then the
        # delivered message compared against what the screen served.
        senders = [
            # `partner_welcome` left this list on 2026-08-04 — it is editable under Invitations
            # now, and its own byte-identity proof lives in `test_invitations.py`.
            ('interview_booked', lambda: emails_mod.send_reviewer_interview_booked_email(
                to, reviewer_name='Reviewer', applicant_name='the applicant',
                start=sysmail.SAMPLE_START, meeting_url='https://meet.google.com/…',
                ref='HT-0000', duration_min=30, calendar_invite_sent=True)),
            ('interview_reminder', lambda: emails_mod.send_reviewer_interview_reminder_email(
                to, reviewer_name='Reviewer', applicant_name='the applicant',
                start=sysmail.SAMPLE_START, meeting_url='https://meet.google.com/…',
                when='1day', ref='HT-0000', verdict_due='25/09/2026')),
            ('interview_cancelled', lambda: emails_mod.send_reviewer_interview_cancelled_email(
                to, reviewer_name='Reviewer', applicant_name='the applicant',
                ref='HT-0000', reason='Something came up at home.')),
            ('alternatives_requested',
             lambda: emails_mod.send_reviewer_alternatives_requested_email(
                 to, reviewer_name='Reviewer', applicant_name='the applicant',
                 note='I have class at both of those times.', ref='HT-0000')),
            ('student_message', lambda: emails_mod.send_reviewer_student_message_email(
                to, reviewer_name='Reviewer', applicant_name='the applicant',
                message='I am running about ten minutes late.', ref='HT-0000',
                interview_start=sysmail.SAMPLE_START)),
            ('verdict_escalation', lambda: emails_mod.send_verdict_escalation_email(
                to, applicant_name='the applicant', ref='HT-0000',
                reviewer_name='Reviewer', due_by='25/09/2026')),
        ]
        self.assertEqual([k for k, _ in senders], [k for k, _ in sysmail.SYSTEM_EMAILS],
                         'a sender was added or reordered without updating this proof')
        for key, send in senders:
            mail.outbox = []
            send()
            self.assertEqual(len(mail.outbox), 1, f'{key} did not send')
            msg = mail.outbox[0]
            self.assertEqual(msg.subject, rows[key]['subject'], key)
            self.assertEqual(msg.body, rows[key]['body'], key)


class TestTheGate(_Base):
    def test_an_org_admin_may_read_it(self):
        self._auth('sys-oa')
        self.assertEqual(self.client.get(URL).status_code, 200)

    def test_a_reviewer_may_not(self):
        # Same audience as the rest of the Reviewers surface — a volunteer reads their own emails
        # in their own inbox, not on a screen about how the organisation runs them.
        self._auth('sys-rv')
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_a_stranger_may_not(self):
        self.assertIn(self.client.get(URL).status_code, (401, 403))

    def test_there_is_no_way_to_change_any_of_it(self):
        # Read-only is the whole statement being made. If a write verb ever answers here, the
        # screen has started lying about what it is.
        self._auth('sys-oa')
        for verb in (self.client.post, self.client.patch, self.client.put, self.client.delete):
            self.assertEqual(verb(URL, {}, format='json').status_code, 405)
