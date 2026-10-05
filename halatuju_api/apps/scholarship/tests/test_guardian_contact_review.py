"""Request #26 — the adversarial review's findings, pinned (2026-10-05).

F1  CROSS-ORGANISATION. One student, an application in organisation A and an OFFER in organisation
    B. The contact is one per student, so A's org_admin correcting it through A's application would
    move B's signing PIN. While frozen, only the organisation holding the open offer (or a super).
F2  "EVERY CHANGE IS RECORDED" WAS FALSE. A later application form that changes the parent phone
    wrote no row. It does now. (Django's staff-only /admin/ site is the one writer that still
    records nothing — documented, not signalled.)
F3  THE STUDENT'S OWN NUMBER AS THE PARENT'S — first refused; REVERSED by the owner's consent
    reframe (2026-10-05): accepted on every path and flagged for a call instead.
F5  JUNK NUMBERS. The server now accepts what the screen accepts — a Malaysian mobile — and stores
    it in one display form, not as typed.
"""
from django.test import TestCase, override_settings

from apps.scholarship import bursary
from apps.scholarship.models import GuardianContactChange, ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_student,
)
from apps.scholarship.tests.test_guardian_contact import PARENT, URL, _admin_url, _state

APPLY = '/api/v1/scholarship/applications/'
OWN = '017-555 4444'


def _finished_earlier(profile=None):
    """A student whose earlier application is FINISHED (`closed`). One application in play per
    student (`services/apply_gate.py`, TD-337): a second application is filed only once the first
    is finished, so that is the state a "later application form" now arrives from."""
    profile = profile if profile is not None else _state('no_application')[0]
    make_application('closed', student=profile)
    return profile


def _apply(profile, cohort, guardian_phone, **extra):
    return authed_client(profile).post(APPLY, {
        'cohort_code': cohort.code, 'consent_to_contact': True, 'intends_tertiary_2026': True,
        'guardians': [{'name': 'Ravi a/l Muthu', 'phone': guardian_phone}], **extra,
    }, format='json')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestF1_AnotherOrganisationCannotMoveAFrozenContact(TestCase):

    def setUp(self):
        self.org_a, self.org_b = make_org(), make_org()
        cohort_b = make_cohort(owning_organisation=self.org_b)
        self.profile, self.app_b = _state('awarded_offer_open', cohort=cohort_b)   # the OFFER: B
        self.app_a = make_application('recommended', student=self.profile,
                                      cohort=make_cohort(owning_organisation=self.org_a))

    def _post(self, admin, app):
        return authed_client(admin).post(_admin_url(app), {'name': PARENT['name'],
                                                           'phone': '013-999 8888'}, format='json')

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_frozen_the_other_organisations_org_admin_is_refused(self):
        resp = self._post(make_admin('org_admin', owning_org=self.org_a), self.app_a)
        self.assertEqual((resp.status_code, resp.data['code']), (409, 'guardian_contact_locked'))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.guardians, [PARENT])
        self.assertEqual(bursary.guarantor_phone_for(self.app_b), PARENT['phone'])
        self.assertFalse(GuardianContactChange.objects.exists())

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    def test_frozen_the_offering_organisations_org_admin_and_a_super_may(self):
        self.assertEqual(self._post(make_admin('org_admin', owning_org=self.org_b), self.app_b)
                         .status_code, 200)
        self.assertEqual(self._post(make_admin('super', super_admin=True), self.app_a)
                         .status_code, 200)

    @override_settings(BURSARY_AGREEMENT_ENABLED=False)
    def test_unfrozen_the_current_rule_stands(self):
        self.assertEqual(self._post(make_admin('org_admin', owning_org=self.org_a), self.app_a)
                         .status_code, 200)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class TestF2_ASecondApplicationRecordsTheChange(TestCase):

    def test_an_unfrozen_second_application_that_changes_the_phone_writes_one_row(self):
        profile = _finished_earlier()   # was 'recommended' — in play, now refused (apply_gate, TD-337)
        second = make_cohort(is_open=True)
        self.assertEqual(_apply(profile, second, '019-000 1111').status_code, 201)
        new_app = ScholarshipApplication.objects.get(profile=profile, cohort=second)
        row = GuardianContactChange.objects.get()
        self.assertEqual((row.changed_by_role, row.application_id, row.old_phone, row.new_phone),
                         ('student', new_app.pk, PARENT['phone'], '019-000 1111'))

    def test_an_application_that_changes_nothing_writes_no_row(self):
        profile = _finished_earlier()   # was 'recommended' — in play, now refused (apply_gate, TD-337)
        self.assertEqual(_apply(profile, make_cohort(is_open=True), PARENT['phone']).status_code, 201)
        self.assertFalse(GuardianContactChange.objects.exists())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class TestF3_ASharedNumberIsAcceptedAndFlagged(TestCase):
    """F3 was first fixed as a REFUSAL. The owner's consent reframe (2026-10-05) reversed it: a
    shared family phone is common and genuine, so it is ACCEPTED on every path and FLAGGED for a
    call (`parent_call.needs_parent_call`). These are the old refusal tests, inverted."""

    def setUp(self):
        self.profile = make_student(guardians=[dict(PARENT)], contact_phone=OWN)
        self.app = make_application('recommended', student=self.profile)

    def _flagged(self):
        from apps.scholarship.parent_call import needs_parent_call
        self.profile.refresh_from_db()
        return needs_parent_call(self.profile)

    def test_the_profile_path_accepts_it_and_it_is_flagged(self):
        self.assertFalse(self._flagged())
        resp = authed_client(self.profile).put(URL, {'name': 'Ravi', 'phone': '+60175554444'},
                                               format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(self._flagged())
        self.assertEqual(self.profile.guardians[0]['phone'], OWN)

    def test_the_admin_path_accepts_it_and_it_is_flagged(self):
        resp = authed_client(make_admin('super', super_admin=True)).post(
            _admin_url(self.app), {'name': 'Ravi', 'phone': '0175554444'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(self._flagged())

    def test_the_application_form_stores_it_and_it_is_flagged(self):
        # The form arrives from a FINISHED earlier application: setUp's 'recommended' one is in
        # play and the submit would refuse it (`services/apply_gate.py`, TD-337).
        self.profile = _finished_earlier(make_student(guardians=[dict(PARENT)], contact_phone=OWN))
        resp = _apply(self.profile, make_cohort(is_open=True), OWN, contact_phone=OWN)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(self._flagged())
        self.assertEqual(self.profile.guardians, [{'name': 'Ravi a/l Muthu', 'phone': OWN}])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class TestF5_TheServerAcceptsWhatTheScreenAccepts(TestCase):

    def test_junk_foreign_bare_and_landline_numbers_are_refused(self):
        profile, _ = _state('recommended')
        client = authed_client(profile)
        for junk in ('abc0123456789', '+44 20 7946 0958', '123456789', '03-1234 5678',
                     '012-345 678', '011-123 4567'):
            with self.subTest(junk=junk):
                resp = client.put(URL, {'name': 'Ravi', 'phone': junk}, format='json')
                self.assertEqual((resp.status_code, resp.data['code']),
                                 (400, 'guardian_phone_invalid'))
        profile.refresh_from_db()
        self.assertEqual(profile.guardians, [PARENT])

    def test_a_good_number_is_stored_in_one_form_whatever_its_prefix(self):
        profile, _ = _state('recommended')
        client = authed_client(profile)
        for typed, stored in (('+60139998888', '013-999 8888'), ('60 13 999 8888', '013-999 8888'),
                              ('01112345678', '011-1234 5678')):
            with self.subTest(typed=typed):
                resp = client.put(URL, {'name': PARENT['name'], 'phone': typed}, format='json')
                self.assertEqual(resp.status_code, 200, resp.data)
                self.assertEqual(resp.data['phone'], stored)
