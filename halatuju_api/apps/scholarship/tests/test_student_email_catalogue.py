"""Student maintenance S6a — the catalogue of every email a student receives (`student_email_catalogue`).

Pinned from the harm:
  * NO STUDENT EMAIL SHIPS UNDOCUMENTED: every `send_*` in `apps.scholarship.emails` is either in the
    catalogue or named as not-for-a-student; a new sender in neither fails here;
  * the switchable set is EXACTLY the owner's ruling (2026-10-30) — nothing that carries a credential,
    a decision, an offer or a clock can be silenced, even by a row written straight into the table;
  * the wording shown is the sending module's own dict (no second copy to drift);
  * "last sent" is this organisation's alone, split correctly where two entries share a sender.
"""
import importlib
import pkgutil
from datetime import timedelta

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import emails, student_email_catalogue as cat, usage
from apps.scholarship.models import StudentEmailLog, StudentEmailSwitch, UsageEvent
from apps.scholarship.tests.factories import make_application, make_cohort

#: The owner's ruling, 2026-10-30: rows 4, 12, 13/14, 15, 19, 23 and 26-28 of the S6 pre-flight.
OWNER_SWITCHABLE = {
    'application_received', 'question_reminder', 'submission_received', 'profile_complete',
    'interviewer_assigned', 'interview_reminders', 'award_confirmed',
    'results_due', 'results_overdue', 'result_queried',
}


def _package_senders():
    found = set()
    for info in pkgutil.iter_modules(emails.__path__):
        module = importlib.import_module(f'{emails.__name__}.{info.name}')
        for name, obj in vars(module).items():
            if name.startswith('send_') and callable(obj) and getattr(obj, '__module__', '') == module.__name__:
                found.add(name)
    return found


class TestTheCatalogueCoversEveryStudentEmail(TestCase):
    def test_every_sender_in_the_emails_package_is_classified_once(self):
        package = _package_senders()
        listed = {s for e in cat.CATALOGUE for s in e.senders}
        self.assertEqual(listed & cat.NOT_STUDENT_SENDERS, set())
        unclassified = package - listed - cat.NOT_STUDENT_SENDERS
        self.assertEqual(unclassified, set(), 'A new send_* in apps.scholarship.emails must be added to '
                         'student_email_catalogue.CATALOGUE (a student email) or NOT_STUDENT_SENDERS.')
        self.assertEqual(cat.NOT_STUDENT_SENDERS - package, set(), 'A stale NOT_STUDENT_SENDERS name.')

    def test_every_listed_sender_exists(self):
        from apps.courses import profile_claim
        package = _package_senders()
        for e in cat.CATALOGUE:
            for sender in e.senders:
                with self.subTest(key=e.key, sender=sender):
                    self.assertTrue(sender in package or hasattr(profile_claim, sender))

    def test_keys_are_unique_and_every_entry_is_well_formed(self):
        self.assertEqual(len(cat.BY_KEY), len(cat.CATALOGUE))
        for e in cat.CATALOGUE:
            with self.subTest(key=e.key):
                self.assertIn(e.group, cat.GROUPS)
                self.assertIn(e.languages, ('en_ms_ta', 'en_ms', 'en'))
                self.assertIn(e.tracked, ('meter', 'log', None))
                self.assertNotEqual(e.switchable, bool(e.lock), 'switchable XOR a lock with its reason')
                if e.tracked == 'meter':
                    self.assertTrue(e.senders)
                if e.flag:
                    self.assertTrue(hasattr(settings, e.flag[0]))

    def test_the_switchable_set_is_exactly_the_owners_ruling(self):
        self.assertEqual(set(cat.SWITCHABLE), OWNER_SWITCHABLE)

    def test_the_wording_shown_is_the_senders_own_dict_in_every_language_it_sends(self):
        from apps.scholarship.emails import student_decisions
        self.assertEqual(cat.wording(cat.BY_KEY['application_received'])['ms']['subject'],
                         student_decisions.ACK_SUBJECTS['ms'])
        for e in cat.CATALOGUE:
            if not e.wording:
                continue
            with self.subTest(key=e.key):
                shown = cat.wording(e)
                self.assertEqual(set(shown), {'en', 'ms', 'ta'})
                self.assertTrue(all(v['subject'] and v['body'] for v in shown.values()))

    def test_partner_access_is_a_link_to_sources_not_a_second_copy(self):
        e = cat.BY_KEY['partner_access']
        self.assertEqual((e.managed_on, e.switchable, e.wording), ('sources', False, ()))


class TestTheGate(TestCase):
    def setUp(self):
        self.app = make_application('maintenance')
        self.org = self.app.owning_organisation

    def test_no_row_means_on_and_a_row_turns_it_off(self):
        self.assertTrue(cat.may_send(self.app, 'application_received'))
        cat.set_switch(self.org, 'application_received', False)
        self.assertFalse(cat.may_send(self.app, 'application_received'))
        self.assertTrue(cat.may_send(make_application('maintenance'), 'application_received'))   # another org
        cat.set_switch(self.org, 'application_received', True)
        self.assertTrue(cat.may_send(self.org, 'application_received'))

    def test_a_locked_email_cannot_be_switched_and_a_row_written_behind_the_api_does_nothing(self):
        for key in ('declined', 'award_offer', 'verify_email', 'partner_access', 'no_such_email'):
            with self.subTest(key=key):
                with self.assertRaises(cat.NotSwitchable):
                    cat.set_switch(self.org, key, False)
        with self.assertRaises(cat.NotSwitchable):
            cat.set_switch(self.org, 'results_due', 'false')          # a bool, never a string
        StudentEmailSwitch.objects.create(organisation=self.org, key='declined', enabled=False)
        self.assertTrue(cat.may_send(self.app, 'declined'))
        with self.assertRaises(KeyError):
            cat.may_send(self.app, 'no_such_email')                   # a typo is a bug, not a send


class TestLastSent(TestCase):
    def setUp(self):
        self.expired = make_application('expired')
        self.org = self.expired.owning_organisation
        cohort = self.expired.cohort
        self.closed = make_application('submitted', cohort=cohort, status='closed')
        self.other = make_application('expired')                     # another organisation

    def _meter(self, app, source, when):
        row = UsageEvent.objects.create(organisation_id=app.owning_organisation_id, application=app,
                                        service=usage.EMAIL, source=source)
        UsageEvent.objects.filter(pk=row.pk).update(created_at=when)

    def test_the_meter_split_by_status_and_fenced_to_the_organisation(self):
        now = timezone.now()
        self._meter(self.expired, 'send_application_closed_email', now - timedelta(days=3))
        self._meter(self.closed, 'send_application_closed_email', now - timedelta(days=1))
        self._meter(self.other, 'send_acknowledgement_email', now)
        sent = cat.last_sent(self.org)
        self.assertEqual(sent['application_expired'].date(), (now - timedelta(days=3)).date())
        self.assertEqual(sent['closed_by_officer'].date(), (now - timedelta(days=1)).date())
        self.assertNotIn('application_received', sent)

    def test_the_worded_family_reads_its_own_log_and_only_a_successful_send(self):
        StudentEmailLog.objects.create(organisation=self.org, application=self.expired, key='results_due', ok=False)
        self.assertNotIn('results_due', cat.last_sent(self.org))
        StudentEmailLog.objects.create(organisation=self.org, application=self.expired, key='results_due', ok=True)
        self.assertIn('results_due', cat.last_sent(self.org))
        self.assertNotIn('results_overdue', cat.last_sent(self.org))

    @override_settings(MAINTENANCE_REMINDERS_ENABLED=False, PROFILE_COMPLETE_EMAIL_ENABLED=False)
    def test_the_payload_says_when_the_platform_holds_an_email_back(self):
        rows = {r['key']: r for r in cat.payload(make_cohort().owning_organisation)}
        self.assertEqual(len(rows), len(cat.CATALOGUE))
        self.assertFalse(rows['results_due']['platform_on'])
        self.assertTrue(rows['submission_received']['platform_on'])   # sent when the flag is OFF
        self.assertFalse(rows['profile_complete']['platform_on'])
        self.assertTrue(rows['declined']['platform_on'])
        self.assertEqual(rows['declined']['lock'], 'decision')
        self.assertTrue(rows['application_received']['enabled'])
