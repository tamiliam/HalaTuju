"""TD-404 — Sabah/Sarawak and Chinese names in every name match.

(1) The shared normaliser (`vision._NAME_NOISE`) treats the Iban/Bidayuh/Kadazan connector ANAK and its
short form AK, and BT/BTE for BINTI, exactly as it already treats BIN/BINTI and A/L/AL — stripped
before any comparison. That is a pure equivalence: it reaches identity, consent, STR, relationship and
document-name checks alike, and can only turn a mismatch into a match.
(2) A household STR whose recipient name differs from a household card in ONE romanised syllable
(TAN AH KOW / TAN AH KAU) is not called a stranger's — that card "cannot judge" the name, so the IC is
asked (the F1 path). Identity is NOT loosened: the student's own IC still needs the exact name.
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student
from apps.scholarship.vision import name_match, relationship_name_match

STUDENT, STUDENT_NRIC = 'Mary Anak Johnny', '080808-13-5566'


def _doc(app, doc_type, **kw):
    kw.setdefault('storage_path', f'test/{doc_type}/{ApplicantDocument.objects.count()}')
    return ApplicantDocument.objects.create(application=app, doc_type=doc_type, **kw)


class TheSharedNormaliser(TestCase):

    def test_anak_and_ak_are_one_connector_in_both_matchers(self):
        for match in (name_match, relationship_name_match):
            with self.subTest(match.__name__):
                self.assertEqual(match('JOHNNY ANAK GABRIEL', 'JOHNNY AK GABRIEL'), 'match')

    def test_bt_and_bte_are_binti(self):
        for short in ('SITI BT ALI', 'SITI BTE ALI'):
            with self.subTest(short):
                self.assertEqual(name_match('SITI BINTI ALI', short), 'match')     # was 'partial'

    def test_the_earlier_probes_are_unchanged(self):
        self.assertEqual(name_match('RAJU A/L MUNI', 'RAJU AL MUNI'), 'match')
        self.assertEqual(name_match('AHMAD @ AMAT BIN ALI', 'AHMAD AMAT BIN ALI'), 'match')
        self.assertEqual(name_match('SITI BINTI ALI', 'SITI ALI'), 'match')

    def test_identity_is_not_loosened(self):
        """The student's own IC keeps its exact spelling: one romanised syllable is still a mismatch."""
        self.assertEqual(name_match('TAN AH KOW', 'TAN AH KAU'), 'mismatch')
        self.assertEqual(name_match('JOHNNY GABRIEL', 'JIMMY GABRIEL'), 'mismatch')

    def test_the_relationship_bucket_matches_anak_and_ak(self):
        """The bucket every birth-certificate / guardianship row is judged by."""
        from apps.scholarship.income_engine.buckets import _name_bucket
        self.assertEqual(_name_bucket('JOHNNY AK GABRIEL', 'JOHNNY ANAK GABRIEL'), 'match')


class TheStudentsOwnIC(TestCase):

    def test_an_iban_ic_printed_with_ak_matches_the_typed_anak(self):
        """The IC's name verdict (the officer's chip and the gate's soft name check) — the gate itself
        ignores the name while the NRIC verifies, so the verdict is the surface that reads it."""
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        app = make_application('profile_complete', student=make_student(name=STUDENT, nric=STUDENT_NRIC))
        ic = _doc(app, 'ic', vision_run_at=timezone.now(), vision_name='MARY AK JOHNNY', vision_nric=STUDENT_NRIC)
        self.assertEqual(ApplicantDocumentSerializer(ic).data['vision_name_verdict'], 'match')


class TheHouseholdSTR(TestCase):
    """STR route, the father the earner; both parents' cards on file and read."""

    def _app(self, father, mother):
        return make_application(
            'profile_complete', income_route='str', income_earner='father', income_working_members=[],
            father_name=father, mother_name=mother, father_occupation='private',
            mother_occupation='homemaker', other_family_members=[],
            student=make_student(name=STUDENT, nric=STUDENT_NRIC))

    def _cards(self, app, father, mother):
        for member, name, nric in (('father', father, '700707-13-5671'), ('mother', mother, '720808-13-5682')):
            _doc(app, 'parent_ic', household_member=member, vision_run_at=timezone.now(),
                 vision_name=name, vision_nric=nric)

    def _str(self, app, name, nric=''):
        _doc(app, 'str', vision_fields={
            'fields': {'recipient_name': name, 'recipient_nric': nric, 'status': 'Lulus', 'year': '2026',
                       'source_type': 'semakan_status'}, 'student_verdict': 'ok', 'error': ''})

    def _str_check(self, app):
        from apps.scholarship.income_engine import student_str_check
        return student_str_check(app.documents.get(doc_type='str'))

    def test_johnny_ak_gabriel_is_the_fathers_str(self):
        app = self._app('Johnny Anak Gabriel', 'Rose Anak Bujang')
        self._cards(app, 'JOHNNY ANAK GABRIEL', 'ROSE ANAK BUJANG')
        self._str(app, 'JOHNNY AK GABRIEL')
        self.assertEqual(self._str_check(app)['name_status'], 'match')

    def test_one_romanised_syllable_is_not_a_stranger_it_asks_for_the_ic(self):
        from apps.scholarship.income_str_ownership import (STR_NOT_HOUSEHOLD, str_owner_ic_asks,
                                                           str_recipient_is_stranger)
        from apps.scholarship.services import income_doc_blockers
        app = self._app('Tan Ah Kau', 'Lim Mei Ling')
        self._cards(app, 'TAN AH KAU', 'LIM MEI LING')
        self._str(app, 'TAN AH KOW')                                  # name only, no NRIC on the STR
        self.assertIs(str_recipient_is_stranger(app), False)
        self.assertEqual(str_owner_ic_asks(app), {'missing': [], 'unreadable': ['father']})
        self.assertNotIn(STR_NOT_HOUSEHOLD, income_doc_blockers(app))

    def test_a_different_given_name_is_still_a_stranger(self):
        from apps.scholarship.income_str_ownership import STR_NOT_HOUSEHOLD, str_recipient_is_stranger
        from apps.scholarship.services import income_doc_blockers
        app = self._app('Tan Ah Kow', 'Lim Mei Ling')
        self._cards(app, 'TAN AH KOW', 'LIM MEI LING')
        self._str(app, 'TAN AH MENG')
        self.assertIs(str_recipient_is_stranger(app), True)
        self.assertIn(STR_NOT_HOUSEHOLD, income_doc_blockers(app))

    def test_a_longer_given_name_sharing_the_initial_is_still_a_stranger(self):
        """KENNETH is not a romanisation of KAU: a syllable is short (≤ 6 letters)."""
        from apps.scholarship.income_str_ownership import str_recipient_is_stranger
        app = self._app('Tan Ah Kau', 'Lim Mei Ling')
        self._cards(app, 'TAN AH KAU', 'LIM MEI LING')
        self._str(app, 'TAN AH KENNETH')
        self.assertIs(str_recipient_is_stranger(app), True)

    def test_a_stranger_nric_still_decides_on_its_own(self):
        """The near-miss excuses only the NAME; a positive NRIC mismatch against every card stands."""
        from apps.scholarship.income_str_ownership import str_recipient_is_stranger
        app = self._app('Tan Ah Kau', 'Lim Mei Ling')
        self._cards(app, 'TAN AH KAU', 'LIM MEI LING')
        self._str(app, 'TAN AH KOW', nric='650303-07-5123')
        self.assertIs(str_recipient_is_stranger(app), True)
