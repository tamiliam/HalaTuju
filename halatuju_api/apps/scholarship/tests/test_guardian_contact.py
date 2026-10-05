"""Request #26 — correcting the parent/guardian contact (owner rulings R1–R7, 2026-10-05).

What these tests are for, in the order the failures would hurt:

1. **R2, the freeze.** The contact is frozen ONLY while a bursary-signing PIN could actually be sent
   — the flag on AND an offered award. The test most likely to be "simplified" away later is the
   first one: with the flag OFF (production today) an awarded student is NOT frozen.
2. **The freeze and the signing path agree.** `contact_frozen` must say "frozen" in exactly the
   states where the real PIN-send view would send a PIN. Driven through the real endpoint, so a
   change to either side that makes them disagree fails here.
3. **The edit reaches the PIN.** After a correction, `bursary.guarantor_phone_for` — the only
   number a PIN goes to — returns the new number; nothing about where it is stored moved (R7).
4. **Every real change is recorded, a no-op is not**, and `merge_guardians` semantics hold.
5. **Who may correct it.** A student, except while frozen; super + org_admin any time; everyone
   else refused; another tenant's application 404, never 403.
"""
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import bursary, emails, guardian_contact
from apps.scholarship.models import GuardianContactChange, Sponsor, Sponsorship
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_student,
)

PARENT = {'name': 'Ravi a/l Muthu', 'phone': '012-345 6789'}
URL = '/api/v1/scholarship/guardian-contact/'


def _admin_url(app):
    return f'/api/v1/admin/scholarship/applications/{app.pk}/guardian-contact/'


def _student(**kw):
    kw.setdefault('guardians', [dict(PARENT)])
    return make_student(**kw)


def _sponsor():
    return Sponsor.objects.create(
        supabase_user_id=f'spon-{timezone.now().timestamp()}', name='Jane Sponsor',
        email='jane@sponsor.example', phone='0123', source='friend',
        consent_at=timezone.now(), status='approved')


def _award(app, status):
    """A sponsorship in `status` on `app` — 'offered' is the unaccepted award (the signing window),
    'active' is accepted (student + guarantor signed), 'lapsed' declined."""
    return Sponsorship.objects.create(sponsor=_sponsor(), application=app,
                                      amount=Decimal('2000'), status=status)


def _state(name, cohort=None):
    """One product state, built through the factory. Returns (profile, application|None)."""
    profile = _student()
    if name == 'no_application':
        return profile, None
    if name == 'recommended':
        return profile, make_application('recommended', student=profile, cohort=cohort)
    if name == 'awarded_offer_open':          # the signing window
        app = make_application('awarded', student=profile, cohort=cohort)
        _award(app, 'offered')
        return profile, app
    if name == 'awarded_signed_awaiting_countersign':
        app = make_application('awarded', student=profile, cohort=cohort)
        _award(app, 'active')
        return profile, app
    if name == 'active_agreement_executed':
        app = make_application('active', student=profile, cohort=cohort)
        _award(app, 'active')
        return profile, app
    if name == 'offer_declined':
        app = make_application('recommended', student=profile, cohort=cohort)
        _award(app, 'lapsed')
        return profile, app
    raise ValueError(name)


STATES = ('no_application', 'recommended', 'awarded_offer_open',
          'awarded_signed_awaiting_countersign', 'active_agreement_executed', 'offer_declined')


class TestTheFreezeRuleR2(TestCase):
    """R2: frozen only while bursary signing is actually possible for this student."""

    @override_settings(BURSARY_AGREEMENT_ENABLED=False)
    def test_flag_off_an_awarded_student_with_an_open_offer_is_NOT_frozen_owner_ruling_R2(self):
        # ⚠ The owner's ruling, and the one most likely to be "simplified" to a status check.
        # Signing is OFF in production; freezing at 'awarded' would lock every awarded student
        # indefinitely to protect a control that cannot run. Do not change this assertion.
        profile, app = _state('awarded_offer_open')
        self.assertEqual(app.status, 'awarded')
        self.assertFalse(guardian_contact.contact_frozen(profile))

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_flag_on_and_the_offer_open_is_frozen(self):
        profile, _ = _state('awarded_offer_open')
        self.assertTrue(guardian_contact.contact_frozen(profile))

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_flag_on_after_the_agreement_is_executed_is_not_frozen(self):
        profile, _ = _state('active_agreement_executed')
        self.assertFalse(guardian_contact.contact_frozen(profile))

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_flag_on_once_student_and_guarantor_have_signed_is_not_frozen(self):
        # The PIN can no longer be sent (the offer is no longer 'offered'), and the number that was
        # verified is stamped on the application, so the profile copy is free again.
        profile, _ = _state('awarded_signed_awaiting_countersign')
        self.assertFalse(guardian_contact.contact_frozen(profile))

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_flag_on_without_an_offer_is_not_frozen(self):
        for name in ('no_application', 'recommended', 'offer_declined'):
            with self.subTest(name):
                profile, _ = _state(name)
                self.assertFalse(guardian_contact.contact_frozen(profile))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   PHONE_VERIFY_CHANNEL='sms', TWILIO_ACCOUNT_SID='sid',
                   TWILIO_AUTH_TOKEN='tok', TWILIO_VERIFY_SERVICE_SID='VA-test')
class TestTheFreezeAgreesWithTheSigningPath(TestCase):
    """R2's single source of truth: frozen ⇔ the real PIN-send view would send a PIN."""

    @patch('apps.scholarship.whatsapp._post_to_verify', return_value={'status': 'pending'})
    def test_contact_frozen_matches_the_pin_send_view_in_every_state(self, _post):
        for flag in (False, True):
            for name in STATES:
                with self.subTest(flag=flag, state=name), \
                        override_settings(BURSARY_AGREEMENT_ENABLED=flag):
                    cache.clear()
                    profile, _ = _state(name)
                    resp = authed_client(profile).post(
                        '/api/v1/scholarship/award/guarantor/verify-phone/send/')
                    pin_reachable = (resp.data or {}).get('code') not in (
                        'bursary_disabled', 'no_offer')
                    self.assertEqual(guardian_contact.contact_frozen(profile), pin_reachable,
                                     f'{resp.status_code} {resp.data}')
                    # And the window is exactly one state, with the flag on.
                    self.assertEqual(pin_reachable, flag and name == 'awarded_offer_open')


@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class TestTheService(TestCase):

    def test_a_change_is_recorded_with_old_and_new(self):
        profile, app = _state('recommended')
        change = guardian_contact.update_guardian_contact(
            profile, name='Ravi a/l Muthu', phone='013-999 8888',
            by_email='s@example.test', by_role='student')
        self.assertIsNotNone(change)
        self.assertEqual((change.old_name, change.new_name), ('Ravi a/l Muthu', 'Ravi a/l Muthu'))
        self.assertEqual((change.old_phone, change.new_phone), ('012-345 6789', '013-999 8888'))
        self.assertEqual((change.changed_by_role, change.changed_by_email), ('student', 's@example.test'))
        self.assertEqual(change.application_id, app.pk)
        profile.refresh_from_db()
        self.assertEqual(profile.guardians, [{'name': 'Ravi a/l Muthu', 'phone': '013-999 8888'}])

    def test_a_save_that_changes_nothing_writes_no_row(self):
        profile, _ = _state('recommended')
        change = guardian_contact.update_guardian_contact(
            profile, name=PARENT['name'], phone=PARENT['phone'], by_email='', by_role='student')
        self.assertIsNone(change)
        self.assertEqual(GuardianContactChange.objects.count(), 0)

    def test_the_corrected_number_is_the_one_the_signing_pin_goes_to(self):
        profile, app = _state('awarded_offer_open')
        self.assertEqual(bursary.guarantor_phone_for(app), '012-345 6789')
        guardian_contact.update_guardian_contact(
            profile, name=PARENT['name'], phone='019-222 3333', by_email='', by_role='student')
        app.profile.refresh_from_db()
        self.assertEqual(bursary.guarantor_phone_for(app), '019-222 3333')

    def test_merge_semantics_keep_other_keys_and_later_entries(self):
        # TD-055: the same person keeps their other keys; a second entry is never thrown away.
        profile = _student(guardians=[
            {'name': 'Ravi a/l Muthu', 'phone': '012-345 6789', 'relationship': 'father'},
            {'name': 'Mala', 'phone': '011-1111 2222'}])
        make_application('recommended', student=profile)
        guardian_contact.update_guardian_contact(
            profile, name='ravi a/l muthu', phone='013-999 8888', by_email='', by_role='student')
        profile.refresh_from_db()
        self.assertEqual(profile.guardians, [
            {'name': 'ravi a/l muthu', 'phone': '013-999 8888', 'relationship': 'father'},
            {'name': 'Mala', 'phone': '011-1111 2222'}])

    def test_a_different_person_does_not_inherit_the_old_relationship(self):
        profile = _student(guardians=[
            {'name': 'Ravi a/l Muthu', 'phone': '012-345 6789', 'relationship': 'father'}])
        make_application('recommended', student=profile)
        guardian_contact.update_guardian_contact(
            profile, name='Devi a/p Raman', phone='012-345 6789', by_email='', by_role='student')
        profile.refresh_from_db()
        self.assertEqual(profile.guardians, [{'name': 'Devi a/p Raman', 'phone': '012-345 6789'}])

    def test_validation_refuses_with_stable_codes(self):
        profile, _ = _state('recommended')
        cases = [('', '012-345 6789', 'guardian_name_required'),
                 ('A' * 256, '012-345 6789', 'guardian_name_too_long'),
                 ('Ravi', '', 'guardian_phone_invalid'),
                 ('Ravi', 'abc', 'guardian_phone_invalid'),
                 ('Ravi', '0' * 21, 'guardian_phone_invalid')]
        for name, phone, code in cases:
            with self.subTest(code=code, phone=phone):
                with self.assertRaises(guardian_contact.GuardianContactError) as ctx:
                    guardian_contact.update_guardian_contact(
                        profile, name=name, phone=phone, by_email='', by_role='student')
                self.assertEqual(ctx.exception.code, code)
        profile.refresh_from_db()
        self.assertEqual(profile.guardians, [PARENT])

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_frozen_refuses_the_student_but_not_the_admin(self):
        profile, app = _state('awarded_offer_open')
        with self.assertRaises(guardian_contact.GuardianContactError) as ctx:
            guardian_contact.update_guardian_contact(
                profile, name=PARENT['name'], phone='013-999 8888', by_email='', by_role='student')
        self.assertEqual(ctx.exception.code, 'guardian_contact_locked')
        change = guardian_contact.update_guardian_contact(
            profile, name=PARENT['name'], phone='013-999 8888', by_email='boss@example.test',
            by_role='admin', application=app, allow_frozen=True)
        self.assertEqual(change.changed_by_role, 'admin')
        self.assertEqual(bursary.guarantor_phone_for(app), '013-999 8888')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class TestTheStudentEndpoint(TestCase):

    def test_get_without_an_application_says_so(self):
        profile, _ = _state('no_application')
        resp = authed_client(profile).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['has_scholarship_application'])
        self.assertFalse(resp.data['guardian_contact_locked'])

    def test_get_with_an_application(self):
        profile, _ = _state('awarded_offer_open')
        resp = authed_client(profile).get(URL)
        self.assertEqual(resp.data, {'has_scholarship_application': True,
                                     'guardian_contact_locked': False, **PARENT})

    def test_put_without_an_application_is_refused(self):
        profile, _ = _state('no_application')
        resp = authed_client(profile).put(URL, {'name': 'X', 'phone': '013-999 8888'},
                                          format='json')
        self.assertEqual((resp.status_code, resp.data['code']), (403, 'no_application'))
        profile.refresh_from_db()
        self.assertEqual(profile.guardians, [PARENT])

    def test_put_corrects_and_records_a_student_change(self):
        profile, _ = _state('recommended')
        resp = authed_client(profile).put(URL, {'name': PARENT['name'], 'phone': '013-999 8888'},
                                          format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['changed'])
        self.assertEqual(resp.data['phone'], '013-999 8888')
        row = GuardianContactChange.objects.get()
        self.assertEqual((row.changed_by_role, row.old_phone), ('student', '012-345 6789'))

    def test_put_bad_phone_is_a_400_with_a_code(self):
        profile, _ = _state('recommended')
        resp = authed_client(profile).put(URL, {'name': 'Ravi', 'phone': '12'}, format='json')
        self.assertEqual((resp.status_code, resp.data['code']), (400, 'guardian_phone_invalid'))

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_put_while_frozen_is_refused_with_the_code_and_changes_nothing(self):
        profile, _ = _state('awarded_offer_open')
        client = authed_client(profile)
        self.assertTrue(client.get(URL).data['guardian_contact_locked'])
        resp = client.put(URL, {'name': PARENT['name'], 'phone': '013-999 8888'}, format='json')
        self.assertEqual((resp.status_code, resp.data['code']), (409, 'guardian_contact_locked'))
        profile.refresh_from_db()
        self.assertEqual(profile.guardians, [PARENT])
        self.assertFalse(GuardianContactChange.objects.exists())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestTheAdminEndpoint(TestCase):
    """R3: super + org_admin only, at any time (frozen included), org-fenced, recorded."""

    def setUp(self):
        self.cohort = make_cohort()
        self.profile, self.app = _state('awarded_offer_open', cohort=self.cohort)
        self.body = {'name': 'Ravi a/l Muthu', 'phone': '013-999 8888'}

    def _post(self, admin):
        return authed_client(admin).post(_admin_url(self.app), self.body, format='json')

    def test_super_corrects_even_while_frozen_and_it_is_recorded(self):
        self.assertTrue(guardian_contact.contact_frozen(self.profile))
        boss = make_admin('super', super_admin=True)
        resp = self._post(boss)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {'name': 'Ravi a/l Muthu', 'phone': '013-999 8888',
                                     'changed': True})
        row = GuardianContactChange.objects.get()
        self.assertEqual((row.changed_by_role, row.changed_by_email, row.application_id),
                         ('admin', boss.email, self.app.pk))
        self.app.refresh_from_db()
        self.app.profile.refresh_from_db()
        self.assertEqual(bursary.guarantor_phone_for(self.app), '013-999 8888')

    def test_org_admin_of_the_owning_organisation_corrects(self):
        admin = make_admin('org_admin', owning_org=self.cohort.owning_organisation)
        self.assertEqual(self._post(admin).status_code, 200)

    def test_every_other_role_is_refused(self):
        for role in ('admin', 'reviewer', 'qc', 'finance', 'partner'):
            with self.subTest(role=role):
                admin = make_admin(role, owning_org=self.cohort.owning_organisation)
                self.assertEqual(self._post(admin).status_code, 403)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.guardians, [PARENT])
        self.assertFalse(GuardianContactChange.objects.exists())

    def test_another_organisations_org_admin_gets_404_not_403(self):
        stranger = make_admin('org_admin', owning_org=make_org())
        self.assertEqual(self._post(stranger).status_code, 404)
        self.assertFalse(GuardianContactChange.objects.exists())

    def test_a_student_token_is_not_an_admin(self):
        self.assertEqual(self._post(self.profile.supabase_user_id).status_code, 403)

    def test_bad_phone_is_a_400(self):
        self.body['phone'] = 'nope'
        resp = self._post(make_admin('super', super_admin=True))
        self.assertEqual((resp.status_code, resp.data['code']), (400, 'guardian_phone_invalid'))


class TestTheCompletionEmailReminderR5(TestCase):

    def test_both_languages_ask_the_student_to_check_the_parent_phone(self):
        mail.outbox.clear()
        emails.send_profile_complete_student_email('s@example.test', student_name='Kavi')
        body = mail.outbox[-1].body
        self.assertIn('check that your parent or guardian’s phone number on your profile is '
                      'correct', body)
        self.assertIn('nombor telefon ibu bapa atau penjaga dalam profil anda adalah betul', body)
