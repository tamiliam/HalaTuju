"""Request #26 — the owner's final rulings on the consent framing (2026-10-05).

RULING A — SIGNING WAITS FOR THE CALL. Not a lock (the number stays free to change): a check at the
point of signing. While the parent still needs a call, the "ready to sign" invitation is held (and
the accept clock is NOT armed), the guarantor PIN is not sent, and `sign_agreement` refuses —
defence in depth, for a PIN verified before the flag arose. All with BURSARY_AGREEMENT_ENABLED on;
it is off in production, so none of this changes anything today.

RULING B — A "NEEDS A PARENT CALL" LIST: `?parent_call=needed` on the existing applications list,
super + org_admin only, inside the list's own organisation fence, in a constant number of queries.

THE RECORD FIXES — a call is recorded only against the number the admin was SHOWN (a number changed
in between is refused), a confirming call needs a number on file, and a corrected number is stored
with the name the parent gave.
"""
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.scholarship import bursary, parent_call
from apps.scholarship.bursary import BursaryError
from apps.scholarship.guardian_contact import GuardianContactError
from apps.scholarship.tests.contract_helpers import flagship
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_student,
)
from apps.scholarship.tests.test_guardian_contact import _award
from apps.scholarship.tests.test_td229_contract_per_gift import GUAR_PHONE, _deployed, _sign, _signable

SHARED = '017-555 4444'
OTHER = '013-999 8888'
LIST = '/api/v1/admin/scholarship/applications/'


def _clear(profile, app, number):
    return parent_call.record_call(profile, application=app, outcome='shared_confirmed',
                                   consent=True, number=number)


def _flag(app):
    """Make the parent phone the student's own — the shared-phone flag, nothing else changed."""
    profile = app.profile
    profile.contact_phone = profile.guardians[0]['phone']
    profile.save(update_fields=['contact_phone'])
    return profile


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True, PHONE_VERIFY_CHANNEL='sms',
                   TWILIO_ACCOUNT_SID='sid', TWILIO_AUTH_TOKEN='tok',
                   TWILIO_VERIFY_SERVICE_SID='VA-test')
class TestRulingA_SigningWaitsForTheCall(TestCase):

    def setUp(self):
        self.template = _deployed('2026-r26a', flagship(), 'Flagship Signatory')
        self.app = _signable(flagship(), comprehension_template=self.template)
        self.offer = _award(self.app, 'offered')
        self.profile = _flag(self.app)

    @patch('apps.scholarship.storage.upload_object', return_value=True)
    @patch('apps.scholarship.bursary.generate_pdf', return_value=b'%PDF-local')
    def test_sign_agreement_refuses_until_the_call_even_with_a_fresh_pin(self, _pdf, _up):
        self.assertTrue(bursary.guarantor_phone_verification_fresh(self.app))
        with self.assertRaises(BursaryError) as cm:
            _sign(self.app)
        self.assertEqual(cm.exception.code, 'parent_call_needed')
        _clear(self.profile, self.app, GUAR_PHONE)
        self.assertIsNotNone(_sign(self.app).pk)

    @patch('apps.scholarship.whatsapp._post_to_verify', return_value={'status': 'pending'})
    def test_the_pin_is_not_sent_until_the_call(self, post):
        url = '/api/v1/scholarship/award/guarantor/verify-phone/send/'
        resp = authed_client(self.profile).post(url)
        self.assertEqual((resp.status_code, resp.data['code']), (409, 'parent_call_needed'))
        post.assert_not_called()
        _clear(self.profile, self.app, GUAR_PHONE)
        self.assertEqual(authed_client(self.profile).post(url).status_code, 200)

    def test_the_sign_invitation_is_held_and_no_clock_is_armed(self):
        mail.outbox.clear()
        out = StringIO()
        with override_settings(SIGN_INVITE_APP_IDS=str(self.app.pk)):
            call_command('send_sign_invitation_emails', stdout=out)
        self.assertIn(f'held_for_parent_call=[{self.app.pk}]', out.getvalue())
        self.assertEqual(len(mail.outbox), 0)
        self.offer.refresh_from_db()
        self.assertIsNone(self.offer.accept_deadline)
        _clear(self.profile, self.app, GUAR_PHONE)
        out = StringIO()
        with override_settings(SIGN_INVITE_APP_IDS=str(self.app.pk)):
            call_command('send_sign_invitation_emails', stdout=out)
        self.assertIn(f'sent=[{self.app.pk}]', out.getvalue())
        self.offer.refresh_from_db()
        self.assertIsNotNone(self.offer.accept_deadline)

    def test_it_is_not_a_lock_the_number_can_still_change(self):
        resp = authed_client(make_admin('super', super_admin=True)).post(
            f'/api/v1/admin/scholarship/applications/{self.app.pk}/guardian-contact/',
            {'name': 'Rahmah', 'phone': OTHER}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.app.profile.refresh_from_db()
        self.assertIsNone(parent_call.refuse_signing_until_called(self.app))   # no longer shared


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class TestRulingB_TheNeedsACallList(TestCase):

    def setUp(self):
        self.org = make_org()
        self.cohort = make_cohort(owning_organisation=self.org)
        self.flagged = [self._app(SHARED) for _ in range(2)]
        self._app(OTHER)                                       # not shared
        cleared = self._app(SHARED)
        _clear(cleared.profile, cleared, SHARED)               # shared but called
        self.elsewhere = self._app(SHARED, cohort=make_cohort(owning_organisation=make_org()))

    def _app(self, parent_phone, cohort=None):
        student = make_student(guardians=[{'name': 'P', 'phone': parent_phone}], contact_phone=SHARED)
        return make_application('recommended', student=student, cohort=cohort or self.cohort)

    def _ids(self, who):
        resp = authed_client(who).get(LIST, {'parent_call': 'needed'})
        self.assertEqual(resp.status_code, 200, resp.data)
        return {row['id'] for row in resp.data['applications']}

    def test_the_organisations_org_admin_sees_only_its_own_flagged_students(self):
        self.assertEqual(self._ids(make_admin('org_admin', owning_org=self.org)),
                         {a.pk for a in self.flagged})

    def test_a_super_sees_every_organisations(self):
        self.assertEqual(self._ids(make_admin('super', super_admin=True)),
                         {a.pk for a in self.flagged} | {self.elsewhere.pk})

    def test_other_roles_are_refused_the_filter(self):
        for role in ('admin', 'reviewer', 'qc', 'finance'):
            with self.subTest(role=role):
                resp = authed_client(make_admin(role, owning_org=self.org)).get(
                    LIST, {'parent_call': 'needed'})
                self.assertEqual(resp.status_code, 403)

    def test_the_filter_costs_the_same_however_many_rows(self):
        boss = make_admin('super', super_admin=True)

        def count():
            with CaptureQueriesContext(connection) as ctx:
                self._ids(boss)
            return len(ctx.captured_queries)
        before = count()
        for _ in range(4):
            self._app(SHARED)
        self.assertEqual(count(), before)


class TestTheRecordFixes(TestCase):

    def setUp(self):
        self.profile = make_student(guardians=[{'name': 'Ravi', 'phone': SHARED}], contact_phone=SHARED)
        self.app = make_application('recommended', student=self.profile)

    def _call(self, outcome='shared_confirmed', **kw):
        kw.setdefault('consent', True)
        return parent_call.record_call(self.profile, application=self.app, outcome=outcome, **kw)

    def _refused(self, code, **kw):
        with self.assertRaises(GuardianContactError) as cm:
            self._call(**kw)
        self.assertEqual(cm.exception.code, code)

    def test_a_number_changed_between_dialling_and_saving_is_refused(self):
        shown = SHARED                                          # what the dialog displayed
        self.profile.guardians = [{'name': 'Ravi', 'phone': OTHER}]   # the student changes it
        self.profile.save(update_fields=['guardians'])
        for outcome in ('shared_confirmed', 'parent_number_confirmed', 'could_not_reach'):
            with self.subTest(outcome=outcome):
                self._refused('called_number_mismatch', outcome=outcome, number=shown)

    def test_the_dialled_number_is_required(self):
        self._refused('called_number_required', number='')

    def test_a_confirming_call_with_no_number_on_file_is_refused(self):
        self.profile.guardians = [{'name': 'Ravi', 'phone': ''}]
        self.profile.save(update_fields=['guardians'])
        self._refused('no_parent_number', number=SHARED)

    def test_a_corrected_number_is_stored_with_the_name_the_parent_gave(self):
        self._call(outcome='parent_number_corrected', number=OTHER, parent_name='Devi a/p Raman')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.guardians, [{'name': 'Devi a/p Raman', 'phone': OTHER}])

    def test_a_corrected_number_with_no_name_given_keeps_the_stored_name(self):
        self._call(outcome='parent_number_corrected', number=OTHER)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.guardians, [{'name': 'Ravi', 'phone': OTHER}])


class TestTheListAndTheCaseFlagAgree(TestCase):
    """Second review, finding 4: `needing_call_profile_ids` (the list, two queries for a set) and
    `needs_parent_call` (the case flag, one profile) are two implementations of one rule. They agree
    today; this pins that they keep agreeing, over every shape the rule distinguishes."""

    def _student(self, parent_phone, contact_phone=SHARED):
        student = make_student(guardians=[{'name': 'P', 'phone': parent_phone}],
                               contact_phone=contact_phone)
        return student, make_application('recommended', student=student)

    def test_both_give_the_same_answer_for_every_case(self):
        cases = {}
        cases['shared, no call'] = self._student(SHARED)
        s, a = self._student(SHARED)
        _clear(s, a, SHARED)
        cases['shared, cleared'] = (s, a)
        s, a = self._student(SHARED)
        _clear(s, a, SHARED)                                     # cleared for the OLD number…
        s.guardians = [{'name': 'P', 'phone': '012-111 2222'}]   # …then both phones move together
        s.contact_phone = '012-111 2222'
        s.save(update_fields=['guardians', 'contact_phone'])
        cases['cleared for an old number'] = (s, a)
        s, a = self._student(SHARED)
        parent_call.record_call(s, application=a, outcome='shared_confirmed', consent=False, number=SHARED)
        cases['consent no'] = (s, a)
        s, a = self._student(SHARED)
        parent_call.record_call(s, application=a, outcome='could_not_reach', consent=None, number=SHARED)
        cases['could not reach'] = (s, a)
        cases['not shared'] = self._student(OTHER)
        cases['no parent phone'] = self._student('')
        cases['no contact phone'] = self._student(SHARED, contact_phone='')

        from apps.scholarship.models import ScholarshipApplication
        listed = set(parent_call.needing_call_profile_ids(
            ScholarshipApplication.objects.filter(pk__in=[a.pk for _, a in cases.values()])))
        expected_flagged = {'shared, no call', 'cleared for an old number', 'consent no', 'could not reach'}
        for label, (student, _) in cases.items():
            with self.subTest(case=label):
                student.refresh_from_db()
                flag = parent_call.needs_parent_call(student)
                self.assertEqual(flag, student.pk in listed)
                self.assertEqual(flag, label in expected_flagged)
