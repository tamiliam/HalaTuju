"""Request #26 — the owner's consent framing (2026-10-05): reasonable, RECORDED steps, not fraud.

"We only want the parent's consent to signing a contract, so in the event of a dispute we could
prove we have taken reasonable steps to ensure the parent is onboard." What is pinned here:

* THE FLAG is live and derived: a parent phone equal to the student's own, with no consenting
  confirming call recorded against THAT number. A changed number is unchecked again by itself.
* "RECORD CALL" — super + org_admin, the correction's fence; `parent_number_corrected` stores the
  number it records as called, in one action.
* THE AWARD EMAIL WAITS for the call, on BOTH senders, and reports who it held.
* RETENTION — the trail survives the student's account deletion, like the signed agreement.
* Second review C (the guardians shape) and D (any offer in another organisation refuses).
"""
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.scholarship import parent_call, sponsorship
from apps.scholarship.guardian_contact import GuardianContactError, update_guardian_contact
from apps.scholarship.models import GuardianContactChange, ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_student,
)
from apps.scholarship.tests.test_guardian_contact import _award

SHARED = '017-555 4444'
OTHER = '013-999 8888'


def _shared_student(**kw):
    return make_student(guardians=[{'name': 'Ravi a/l Muthu', 'phone': SHARED}],
                        contact_phone=SHARED, **kw)


def _call_url(app):
    return f'/api/v1/admin/scholarship/applications/{app.pk}/guardian-call/'


class TestTheFlag(TestCase):
    """Live and derived — a function, never a stored boolean."""

    def setUp(self):
        self.profile = _shared_student()
        self.app = make_application('recommended', student=self.profile)

    def _call(self, outcome, consent, number=SHARED):
        return parent_call.record_call(self.profile, application=self.app, outcome=outcome,
                                       consent=consent, number=number, by_email='o@x.test')

    def test_a_shared_phone_with_no_call_is_flagged_and_a_different_one_is_not(self):
        self.assertTrue(parent_call.needs_parent_call(self.profile))
        self.assertFalse(parent_call.needs_parent_call(
            make_student(guardians=[{'name': 'P', 'phone': OTHER}], contact_phone=SHARED)))
        self.assertFalse(parent_call.needs_parent_call(make_student(contact_phone=SHARED)))

    def test_a_consenting_confirming_call_clears_it(self):
        for outcome in ('shared_confirmed', 'parent_number_confirmed'):
            with self.subTest(outcome=outcome):
                GuardianContactChange.objects.all().delete()
                self._call(outcome, True)
                self.assertFalse(parent_call.needs_parent_call(self.profile))

    def test_no_consent_or_no_answer_never_clears_it(self):
        self._call('shared_confirmed', False)
        self._call('could_not_reach', None)
        self.assertTrue(parent_call.needs_parent_call(self.profile))
        self.assertIsNone(GuardianContactChange.objects.get(call_outcome='could_not_reach').consent_given)

    def test_a_changed_number_is_unchecked_again_by_itself(self):
        self._call('shared_confirmed', True)
        self.assertFalse(parent_call.needs_parent_call(self.profile))
        self.profile.contact_phone = '012-111 2222'
        self.profile.save(update_fields=['contact_phone'])
        update_guardian_contact(self.profile, name='Ravi a/l Muthu', phone='012-111 2222',
                                by_email='', by_role='student')
        self.assertTrue(parent_call.needs_parent_call(self.profile))

    def test_a_confirming_call_names_the_number_on_file_or_nothing(self):
        with self.assertRaises(GuardianContactError) as cm:
            self._call('parent_number_confirmed', True, number=OTHER)
        self.assertEqual(cm.exception.code, 'called_number_mismatch')
        self.assertEqual(self._call('shared_confirmed', True, number='+60175554444')
                         .called_number, '+60175554444')

    def test_consent_must_be_said_when_somebody_was_reached(self):
        with self.assertRaises(GuardianContactError) as cm:
            self._call('shared_confirmed', None)
        self.assertEqual(cm.exception.code, 'call_consent_required')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class TestRecordCallEndpoint(TestCase):

    def setUp(self):
        self.cohort = make_cohort()
        self.profile = _shared_student()
        self.app = make_application('recommended', student=self.profile, cohort=self.cohort)

    def _post(self, who, **body):
        body.setdefault('outcome', 'shared_confirmed')
        body.setdefault('consent', True)
        body.setdefault('number', SHARED)   # the number the dialog displayed
        return authed_client(who).post(_call_url(self.app), body, format='json')

    def test_super_and_the_organisations_org_admin_may(self):
        for admin in (make_admin('super', super_admin=True),
                      make_admin('org_admin', owning_org=self.cohort.owning_organisation)):
            with self.subTest(role=admin.role):
                resp = self._post(admin)
                self.assertEqual(resp.status_code, 200, resp.data)
                self.assertFalse(resp.data['needs_call'])

    def test_every_other_role_is_refused_and_another_organisation_is_404(self):
        for role in ('admin', 'reviewer', 'qc', 'finance', 'partner'):
            with self.subTest(role=role):
                self.assertEqual(self._post(make_admin(
                    role, owning_org=self.cohort.owning_organisation)).status_code, 403)
        self.assertEqual(self._post(make_admin('org_admin', owning_org=make_org())).status_code, 404)
        self.assertFalse(GuardianContactChange.objects.exists())

    def test_corrected_stores_exactly_the_number_recorded_as_called(self):
        resp = self._post(make_admin('super', super_admin=True), outcome='parent_number_corrected',
                          number='+60139998888', parent_name='Ravi', note='Father, own phone')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.profile.refresh_from_db()
        row = GuardianContactChange.objects.get(kind='call')
        self.assertEqual(self.profile.guardians[0]['phone'], OTHER)
        self.assertEqual((row.called_number, row.old_phone, row.new_phone), (OTHER, SHARED, OTHER))
        self.assertEqual((row.parent_name_given, row.note, row.changed_by_role),
                         ('Ravi', 'Father, own phone', 'admin'))
        self.assertFalse(resp.data['needs_call'])     # no longer shared

    def test_corrected_with_a_bad_number_changes_nothing(self):
        resp = self._post(make_admin('super', super_admin=True), outcome='parent_number_corrected',
                          number='03-1234 5678')
        self.assertEqual((resp.status_code, resp.data['code']), (400, 'guardian_phone_invalid'))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.guardians[0]['phone'], SHARED)
        self.assertFalse(GuardianContactChange.objects.exists())

    def test_the_cockpit_payload_carries_the_live_flag(self):
        boss = make_admin('super', super_admin=True)
        url = f'/api/v1/admin/scholarship/applications/{self.app.pk}/'
        self.assertTrue(authed_client(boss).get(url).data['guardian_needs_call'])
        self._post(boss)
        self.assertFalse(authed_client(boss).get(url).data['guardian_needs_call'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestSecondReviewD_AnyOfferElsewhereRefuses(TestCase):

    def test_an_offer_in_another_organisation_refuses_even_when_one_is_in_mine(self):
        # Both creation orders: `award_application` returns ONE offer, so whichever it happens to
        # pick, asking it alone lets one of these two through.
        for mine_first in (True, False):
            mine, theirs = make_org(), make_org()
            profile = _shared_student()
            apps = {}
            for org in ((mine, theirs) if mine_first else (theirs, mine)):
                apps[org.pk] = make_application('awarded', student=profile,
                                                cohort=make_cohort(owning_organisation=org))
                _award(apps[org.pk], 'offered')
            app_mine = apps[mine.pk]
            for url in (_call_url(app_mine),
                        f'/api/v1/admin/scholarship/applications/{app_mine.pk}/guardian-contact/'):
                with self.subTest(mine_first=mine_first, url=url):
                    resp = authed_client(make_admin('org_admin', owning_org=mine)).post(
                        url, {'outcome': 'shared_confirmed', 'consent': True,
                              'name': 'Ravi', 'phone': OTHER}, format='json')
                    self.assertEqual((resp.status_code, resp.data['code']),
                                     (409, 'guardian_contact_locked'))


@override_settings(AWARD_OFFER_EMAIL_COOLOFF_HOURS=0, BURSARY_AGREEMENT_ENABLED=False)
class TestTheAwardEmailWaitsForTheCall(TestCase):

    def setUp(self):
        self.profile = _shared_student(contact_email='kavi@example.test')
        self.app = make_application('awarded', student=self.profile)
        self.award = _award(self.app, 'offered')

    def test_the_release_holds_a_flagged_student_unstamped_and_reports_the_id(self):
        mail.outbox.clear()
        held = []
        self.assertEqual(sponsorship.release_award_offer_emails(held=held), 0)
        self.assertEqual((held, len(mail.outbox)), ([self.app.pk], 0))
        self.award.refresh_from_db()
        self.assertIsNone(self.award.offer_emailed_at)    # unstamped, so the next run retries
        parent_call.record_call(self.profile, application=self.app, outcome='shared_confirmed',
                                consent=True, number=SHARED)
        self.assertEqual(sponsorship.release_award_offer_emails(held=[]), 1)

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_the_contract_mode_branch_holds_too(self):
        held = []
        self.assertEqual(sponsorship.release_award_offer_emails(held=held), 0)
        self.assertEqual(held, [self.app.pk])

    def test_the_release_command_reports_it(self):
        out = StringIO()
        call_command('release_award_offer_emails', stdout=out)
        self.assertIn(f'held_for_parent_call=[{self.app.pk}]', out.getvalue())

    def test_the_owner_forced_send_holds_it_too(self):
        mail.outbox.clear()
        out = StringIO()
        with override_settings(AWARD_EMAIL_APP_IDS=str(self.app.pk)):
            call_command('send_award_offer_emails', stdout=out)
        self.assertIn(f'held_for_parent_call=[{self.app.pk}]', out.getvalue())
        self.assertEqual(len(mail.outbox), 0)
        self.award.refresh_from_db()
        self.assertIsNone(self.award.offer_emailed_at)

    def test_an_unflagged_student_is_sent_as_before(self):
        self.profile.contact_phone = OTHER
        self.profile.save(update_fields=['contact_phone'])
        held = []
        self.assertEqual(sponsorship.release_award_offer_emails(held=held), 1)
        self.assertEqual(held, [])


class TestRetentionFollowsTheAgreement(TestCase):

    def test_the_trail_survives_the_students_account_deletion(self):
        profile = _shared_student()
        app = make_application('awarded', student=profile)
        parent_call.record_call(profile, application=app, outcome='shared_confirmed', consent=True,
                                number=SHARED)
        profile.delete()
        row = GuardianContactChange.objects.get()
        self.assertIsNone(row.profile_id)
        self.assertEqual(row.application_id, app.pk)
        self.assertTrue(ScholarshipApplication.objects.filter(pk=app.pk).exists())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSecondReviewC_TheGuardiansShape(TestCase):

    def _apply(self, guardians):
        student = make_student()
        return authed_client(student).post('/api/v1/scholarship/applications/', {
            'cohort_code': make_cohort(is_open=True).code, 'consent_to_contact': True,
            'guardians': guardians}, format='json')

    def test_only_empty_or_one_name_and_phone_entry_is_accepted(self):
        for bad in ([[], {'name': 'A', 'phone': OTHER}], [{'name': 'A', 'phone': OTHER}] * 2,
                    [{'name': 'A', 'phone': OTHER, 'relationship': 'father'}],
                    [{'name': 'A', 'phone': 123}], {'name': 'A', 'phone': OTHER}, 'x'):
            with self.subTest(bad=bad):
                resp = self._apply(bad)
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertIn('guardians', resp.data)
        for good in ([], [{'name': 'A', 'phone': OTHER}]):
            with self.subTest(good=good):
                self.assertEqual(self._apply(good).status_code, 201)
