"""TD-130 (code half): the decision and query emails carry the same harmless `mailto:`
List-Unsubscribe the interview mail has, and no one-click POST.

Brevo injects its own List-Unsubscribe on everything it relays, and a mistaken click may add
the student to its suppression list — silently stopping service mail. Our mailto shim makes the
"Unsubscribe" a note to the support inbox instead. The DEFINITIVE fix (Brevo's List-Help on
transactional mail) is the owner's action and is not in this code.

Every assertion on the message other than the headers is the old `send_mail` message: the
change is headers only.
"""
from types import SimpleNamespace

from django.core import mail
from django.test import SimpleTestCase

from apps.scholarship import emails
from apps.scholarship.emails import student_decisions as sd
from apps.scholarship.emails import student_queries as sq
from apps.scholarship.emails.shared import _P

TO = 'priya@example.com'
_SENDS = {
    'acknowledgement': lambda: emails.send_acknowledgement_email(TO, 'Priya', 'B40'),
    'submission_received': lambda: emails.send_submission_received_email(TO, 'Priya', 'B40'),
    'pass': lambda: emails.send_pass_email(TO, 'Priya', 'B40'),
    'award_confirmed': lambda: emails.send_award_confirmed_email(TO, 'Priya', 'B40'),
    'request_info': lambda: sq.send_request_info_email(TO, 'Priya', 'B40', 'your IC'),
    'query_reminder': lambda: sq.send_query_reminder_email(TO, 'Priya', 'B40', 2, 3),
    'query_raised': lambda: sq.send_query_raised_email(TO, 'Priya', 'B40', 2),
}


class TestTheShimRidesOnEveryDecisionAndQuerySend(SimpleTestCase):

    def setUp(self):
        mail.outbox = []

    def test_each_send_carries_the_mailto_shim_and_no_one_click_post(self):
        self.assertGreaterEqual(len(_SENDS), 7)
        for name, send in _SENDS.items():
            with self.subTest(send=name):
                mail.outbox = []
                self.assertTrue(send())
                [msg] = mail.outbox
                self.assertEqual(msg.extra_headers.get('List-Unsubscribe'),
                                 f'<mailto:{_P.email_support}'
                                 '?subject=Unsubscribe%20from%20BrightPath%20Bursary%20emails>')
                self.assertNotIn('List-Unsubscribe-Post', msg.extra_headers)
                self.assertEqual(msg.to, [TO])
                self.assertEqual(msg.from_email, _P.email_from)

    def test_the_message_is_otherwise_what_send_mail_sent(self):
        emails.send_pass_email(TO, 'Priya', 'B40', lang='ms')
        [msg] = mail.outbox
        self.assertEqual(msg.subject, sd.PASS_SUBJECTS['ms'].format(programme='B40'))
        self.assertTrue(msg.body.startswith('Salam Priya'))
        self.assertEqual((msg.cc, msg.bcc, msg.reply_to), ([], [], []))   # as `send_mail` set
        self.assertEqual(getattr(msg, 'alternatives', []), [])          # still plain text only
        emails.send_query_raised_email(TO, 'Priya', 'B40', 2)
        raised = mail.outbox[1]
        self.assertEqual(raised.body, sq.QUERY_RAISED_BODIES['en'].format(
            name='Priya', programme='B40', n=2,
            link=f'{_P.frontend_url}/scholarship/application'))

    def test_a_tenant_decision_points_at_the_TENANTS_support_address(self):
        tenant = SimpleNamespace(email_support='help@tenant.example', email_from='t@tenant.example',
                                 frontend_url='https://tenant.example',
                                 programme_name=lambda lang: 'Sinar & Co Gift')
        self.assertTrue(sd._send(TO, sd.PASS_SUBJECTS, sd.PASS_BODIES, 'Priya', 'Gift', 'en',
                                 branding=tenant))
        [msg] = mail.outbox
        header = msg.extra_headers['List-Unsubscribe']
        self.assertEqual(header, '<mailto:help@tenant.example'
                                 '?subject=Unsubscribe%20from%20Sinar%20%26%20Co%20Gift%20emails>')
        self.assertNotIn(_P.email_support, header)
        # Review F6: the subject names the SENDER's programme — never "B40", never BrightPath.
        self.assertNotIn('B40', header)
        self.assertNotIn('BrightPath', header)
        self.assertEqual(msg.from_email, 't@tenant.example')
