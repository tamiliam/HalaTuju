"""TD-408 — word order in a patronymic name, and the father's name off ANAK / AK / BT.

(1) When BOTH names carry a connector (BIN, BINTI, BT, BTE, ANAK, AK, A/L, A/P, S/O, D/O) and the pair
is a TRUE REVERSAL — A's given name is B's parent's name, A's parent's name is B's given name, and the
given names differ — it is a mismatch: "ALI BIN ABU" (Ali, son of Abu) is not "ABU BIN ALI". A pure veto
in both matchers (`name_match` exact, `relationship_name_match` tolerant, each judging the parts with
itself); every other pair keeps the set comparison exactly — including a Chinese name whose syllable
reads BIN (the live dry-run's regression, 2026-10-28).
(2) `father_name_from_ic` reads the father off a bare ANAK / AK and off BT / BTE, word-bounded.
"""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship.income_engine.buckets import _name_bucket, _romanised_near_miss
from apps.scholarship.income_engine.relationships import (father_link, father_name_from_ic,
                                                          father_relationship, member_relationship_status)
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.name_order import patronymic_reversed, split_patronymic
from apps.scholarship.tests.factories import make_application, make_student
from apps.scholarship.vision import name_match, relationship_name_match

BOTH = (name_match, relationship_name_match)


class AReversedPatronymicIsAnotherPerson(SimpleTestCase):

    def test_reversed_pairs_mismatch_in_both_matchers(self):
        for a, b in (('ALI BIN ABU', 'ABU BIN ALI'),                       # Malay
                     ('SITI BINTI AHMAD', 'AHMAD BINTI SITI'),
                     ('JOHNNY ANAK GABRIEL', 'GABRIEL ANAK JOHNNY'),       # Iban
                     ('JOHNNY AK GABRIEL', 'GABRIEL ANAK JOHNNY'),         # AK = ANAK, still reversed
                     ('MURUGAN A/L RAMASAMY', 'RAMASAMY A/L MURUGAN'),     # Indian
                     ('KUMAR S/O RAJ', 'RAJ A/L KUMAR'),                   # S/O = A/L
                     ('AHMAD BIN ALI', 'ALI BT AHMAD')):                   # different connector, reversed
            for match in BOTH:
                with self.subTest(a=a, b=b, matcher=match.__name__):
                    self.assertEqual(match(a, b), 'mismatch')

    def test_a_reversal_inside_the_parent_part_alone_is_not_vetoed(self):
        """Reversal-only, kept simple: the given names agree, so this is not a reversal at the top level
        and the set comparison stands (as it did before TD-408)."""
        self.assertEqual(relationship_name_match('AHMAD BIN ALI BIN ABU', 'AHMAD BIN ABU BIN ALI'), 'match')

    def test_a_part_that_does_not_line_up_is_not_vetoed(self):
        """The first veto (any part pair mismatching) was too strong: only a true reversal is vetoed."""
        for match in BOTH:
            with self.subTest(match.__name__):
                self.assertEqual(match('ALI ABU BIN AHMAD', 'ALI BIN ABU AHMAD'), 'match')

    def test_the_same_order_still_matches(self):
        for a, b, want in (('ALI BIN ABU', 'ALI BIN ABU', 'match'),
                           ('JOHNNY ANAK GABRIEL', 'JOHNNY AK GABRIEL', 'match'),    # TD-404
                           ('SITI BINTI ALI', 'SITI BT ALI', 'match'),               # TD-404
                           ('SITI BINTI ALI', 'SITI BTE ALI', 'match'),
                           ('RAJ S/O KUMAR', 'RAJ A/L KUMAR', 'match'),
                           ('PRIYA D/O RAMAN', 'PRIYA A/P RAMAN', 'match'),
                           ('ALI BIN ABU', 'ALI BINTI ABU', 'match'),                # gender: as today
                           ('MUHAMMAD ALI BIN ABU', 'ALI BIN ABU', 'partial'),
                           ('ALI BIN ABU BAKAR', 'ALI BIN ABU', 'partial'),
                           ('AHMAD @ AMAT BIN ALI', 'AHMAD AMAT BIN ALI', 'match'),
                           ('ENCIK ALI BIN ABU', 'ALI BIN ABU', 'match')):          # an honorific
            for match in BOTH:
                with self.subTest(a=a, b=b, matcher=match.__name__):
                    self.assertEqual(match(a, b), want)

    def test_a_glued_or_split_token_inside_one_part_still_matches(self):
        self.assertEqual(name_match('LAKSHMI A/P VIJAYAN', 'LAKSHMIA/P VIJAYAN'), 'match')      # #48 glue
        self.assertEqual(name_match('RUSHAIND RA A/P KUMAR', 'RUSHAINDRA A/P KUMAR'), 'match')  # OCR space

    def test_the_tolerant_matcher_still_folds_within_each_part(self):
        self.assertEqual(relationship_name_match('SARAVANAN A/L SUPRAMANIAM', 'SARAWANAN A/L SUPRAMANIAM'),
                         'match')
        self.assertEqual(name_match('SARAVANAN A/L SUPRAMANIAM', 'SARAWANAN A/L SUPRAMANIAM'), 'mismatch')


class ANameWithoutAConnectorIsUnchanged(SimpleTestCase):

    def test_chinese_word_order_still_matches_as_a_set(self):
        for match in BOTH:
            with self.subTest(match.__name__):
                self.assertEqual(match('TAN WEI MING', 'WEI MING TAN'), 'match')
                self.assertEqual(match('TAN AH KOW', 'KOW TAN AH'), 'match')

    def test_one_side_without_a_connector_keeps_the_set_comparison(self):
        for match in BOTH:
            with self.subTest(match.__name__):
                self.assertEqual(match('ALI BIN ABU', 'ABU ALI'), 'match')          # typed without BIN
                self.assertEqual(match('MURUGAN A/L RAMASAMY', 'RAMASAMY MURUGAN'), 'match')
                self.assertEqual(match('SITI BINTI ALI', 'SITI ALI'), 'match')

    def test_slashless_al_ap_are_not_split_on(self):
        """An Arabic AL is a name part; a side that carries only AL / AP is simply not split."""
        self.assertIsNone(split_patronymic('MUHAMMAD AL AMIN'))
        self.assertEqual(name_match('RAJU A/L MUNI', 'RAJU AL MUNI'), 'match')

    def test_a_chinese_bin_syllable_is_not_read_as_a_reversal(self):
        """Live dry-run regression (invented names, the real shape): BIN is a given-name syllable here,
        not a connector. A birth certificate's mother against her card stayed 'partial' before TD-408 and
        must stay so — the first veto turned it into a mismatch."""
        for match in BOTH:
            with self.subTest(match.__name__):
                self.assertEqual(match('WONG BIN BIN MEI MEI KELANA BINTIAR', 'WONG BIN BIN @WONG MEI MEI'),
                                 'partial')
                self.assertEqual(match('TAN BIN HUAT', 'TAN BIN HUAT'), 'match')
                self.assertEqual(match('LIM BIN BIN', 'LIM BIN BIN'), 'match')

    def test_identity_is_not_loosened(self):
        self.assertEqual(name_match('TAN AH KOW', 'TAN AH KAU'), 'mismatch')
        self.assertEqual(name_match('JOHNNY ANAK GABRIEL', 'JIMMY ANAK GABRIEL'), 'mismatch')


class TheSplitter(SimpleTestCase):

    def test_split_at_the_first_connector(self):
        self.assertEqual(split_patronymic('MARY ANAK JOHNNY'), ('MARY ', ' JOHNNY'))
        self.assertEqual(split_patronymic('AHMAD BIN ALI BIN ABU'), ('AHMAD ', ' ALI BIN ABU'))

    def test_word_bounded(self):
        for name in ('BTARA SINGH', 'KAMAL HASSAN', 'AKMAL HAKIM', 'BINTANG SARI', 'TAN WEI MING'):
            with self.subTest(name):
                self.assertIsNone(split_patronymic(name))

    def test_no_given_name_or_no_parent_is_no_split(self):
        for name in ('BIN ALI', 'ENCIK BIN ALI', 'MARY ANAK'):
            with self.subTest(name):
                self.assertIsNone(split_patronymic(name))

    def test_reversal_needs_both_names_split_and_both_cross_pairs(self):
        self.assertIs(patronymic_reversed('ALI BIN ABU', 'ABU BIN ALI', name_match), True)
        self.assertIs(patronymic_reversed('ALI BIN ABU', 'ABU ALI', name_match), False)      # one side unsplit
        self.assertIs(patronymic_reversed('ALI BIN ABU', 'ALI BIN ABU', name_match), False)  # same order
        self.assertIs(patronymic_reversed('ALI BIN ABU', 'ABU BIN OSMAN', name_match), False)  # one cross pair


class TheFathersNameOffTheStudentsName(SimpleTestCase):

    def test_anak_ak_bt_bte_now_derive_the_father(self):
        for student, father in (('MARY ANAK JOHNNY', 'JOHNNY'), ('MARY AK JOHNNY', 'JOHNNY'),
                                ('SITI BT AHMAD', 'AHMAD'), ('SITI BT. AHMAD', 'AHMAD'),
                                ('SITI BTE AHMAD', 'AHMAD'), ('PETER ANAK LELAKI GABRIEL', 'GABRIEL'),
                                ('AHMAD BIN ALI', 'ALI'), ('DIVASHINI A/P MURUGAN', 'MURUGAN')):
            with self.subTest(student):
                self.assertEqual(father_name_from_ic(student), father)

    def test_word_bounded_and_needs_a_given_name(self):
        for student in ('BTARA SINGH', 'AKMAL HAKIM', 'TAN WEI MING', 'AK SUNDARAM', 'BIN ALI', ''):
            with self.subTest(student):
                self.assertEqual(father_name_from_ic(student), '')

    def test_a_leading_ak_title_is_not_the_patronymic(self):
        """Review: AK (Awangku) opens many Sabah/Brunei names; the BIN after it is the connector."""
        self.assertEqual(father_name_from_ic('AK MOHD SHAHRUL BIN AK OSMAN'), 'AK OSMAN')
        self.assertEqual(father_name_from_ic('AK. MOHD SHAHRUL BIN AK. OSMAN'), 'AK. OSMAN')
        self.assertEqual(split_patronymic('AK MOHD SHAHRUL BIN AK OSMAN'), ('AK MOHD SHAHRUL ', ' AK OSMAN'))
        self.assertEqual(father_relationship('AK MOHD SHAHRUL BIN AK OSMAN', 'AK OSMAN BIN AK HASSAN'), 'match')

    def test_a_newly_derived_father_can_only_match(self):
        """Review: a father name only ANAK / AK / BT / BTE gives turns 'unknown' into 'match', never into a
        new 'mismatch' (or 'pending') — anything else keeps the pre-TD-408 'unknown'."""
        self.assertEqual(father_relationship('MARY ANAK JOHNNY', 'JOHNNY ANAK GABRIEL'), 'match')
        self.assertEqual(father_relationship('MARY AK JOHNNY', 'JOHNNY ANAK GABRIEL'), 'match')
        self.assertEqual(father_relationship('SITI BT AHMAD', 'AHMAD BIN OSMAN'), 'match')
        self.assertEqual(father_relationship('MARY ANAK JOHNNY', 'PETER ANAK SIMON'), 'unknown')
        self.assertEqual(father_relationship('SITI BT AHMAD', 'YUSOF BIN OSMAN'), 'unknown')
        self.assertEqual(father_relationship('MARY ANAK JOHNNY', ''), 'unknown')
        # The connectors known before TD-408 answer exactly as they did.
        self.assertEqual(father_relationship('SITI BINTI AHMAD', 'YUSOF BIN OSMAN'), 'mismatch')
        self.assertEqual(father_relationship('SITI BINTI AHMAD', ''), 'pending')

    def test_a_near_spelling_falls_back_to_the_birth_certificate(self):
        student, card = 'MARY ANAK JOHNNY', 'JONNY ANAK GABRIEL'          # JOHNNY / JONNY: not close
        self.assertEqual(father_link(student, card, 'MARY ANAK JOHNNY', 'JONNY ANAK GABRIEL'), 'match')
        self.assertEqual(father_link(student, card), 'unknown')          # no BC: never a new mismatch
        self.assertEqual(member_relationship_status('father', student, card), 'unknown')
        self.assertEqual(member_relationship_status('brother', student, card), 'unknown')

    def test_a_chinese_style_ak_name_with_a_matching_bc_still_matches(self):
        self.assertEqual(father_name_from_ic('TAN AK KOW'), 'KOW')
        self.assertEqual(father_link('TAN AK KOW', 'TAN AH SENG', 'TAN AK KOW', 'TAN AH SENG'), 'match')
        self.assertEqual(father_link('TAN AK KOW', 'TAN AH SENG'), 'unknown')

    def test_the_grandfather_is_not_the_father(self):
        """The veto bites when the derived father name itself carries a connector: the student's
        father is ALI BIN ABU, and ABU BIN ALI is the father's father (or son)."""
        self.assertEqual(father_relationship('AHMAD BIN ALI BIN ABU', 'ALI BIN ABU'), 'match')
        self.assertEqual(father_relationship('AHMAD BIN ALI BIN ABU', 'ABU BIN ALI'), 'mismatch')

    def test_a_siblings_card_is_judged_as_before(self):
        """Unchanged by TD-408: the father's name inside the sibling's full name (a subset counts)."""
        student = 'AHMAD BIN ALI BIN ABU'
        self.assertEqual(member_relationship_status('brother', student, 'HASSAN BIN ALI BIN ABU'), 'match')
        self.assertEqual(member_relationship_status('sister', student, 'AISYAH BINTI ALI BIN ABU'), 'match')
        self.assertEqual(member_relationship_status('brother', 'MARY ANAK JOHNNY', 'PETER ANAK JOHNNY'),
                         'match')
        self.assertEqual(member_relationship_status('brother', 'AHMAD BIN ALI', 'HASSAN BIN ALI'), 'match')
        self.assertEqual(member_relationship_status('brother', 'AHMAD BIN ALI', 'HASSAN BIN OSMAN'), 'mismatch')


class TheNearMissRefusesOnlyAReversal(SimpleTestCase):

    def test_a_romanised_syllable_inside_one_part_is_still_a_near_miss(self):
        self.assertIs(_romanised_near_miss('TAN AH KOW', 'TAN AH KAU'), True)            # TD-404
        self.assertIs(_romanised_near_miss('TAN AH KOW BIN ALI', 'TAN AH KAU BIN ALI'), True)
        self.assertIs(_romanised_near_miss('JOHNNY ANAK KOW', 'JOHNNY AK KAU'), True)

    def test_a_reversed_patronymic_is_not_a_near_miss(self):
        self.assertIs(_romanised_near_miss('KOW ANAK TAN', 'TAN ANAK KAU'), False)   # was True
        self.assertIs(_romanised_near_miss('ALI BIN KOW', 'KAU BIN ALI'), False)

    def test_a_chinese_bin_name_keeps_its_near_miss(self):
        self.assertIs(_romanised_near_miss('TAN BIN KOW', 'TAN BIN KAU'), True)

    def test_the_bucket_reads_a_reversal_as_a_mismatch(self):
        self.assertEqual(_name_bucket('GABRIEL ANAK JOHNNY', 'JOHNNY ANAK GABRIEL'), 'mismatch')
        self.assertEqual(_name_bucket('JOHNNY AK GABRIEL', 'JOHNNY ANAK GABRIEL'), 'match')


def _doc(app, doc_type, **kw):
    kw.setdefault('storage_path', f'test/{doc_type}/{ApplicantDocument.objects.count()}')
    return ApplicantDocument.objects.create(application=app, doc_type=doc_type, **kw)


class TheHouseholdSTR(TestCase):
    """STR route, the father the earner; both parents' cards on file and read. The STR names the
    father's own father (the grandfather): same two words, reversed — not this household's card."""

    def _app(self):
        return make_application(
            'profile_complete', income_route='str', income_earner='father', income_working_members=[],
            father_name='Johnny Anak Gabriel', mother_name='Rose Anak Bujang', father_occupation='private',
            mother_occupation='homemaker', other_family_members=[],
            student=make_student(name='Mary Anak Johnny', nric='080808-13-5566'))

    def _cards_and_str(self, app, str_name):
        for member, name, nric in (('father', 'JOHNNY ANAK GABRIEL', '700707-13-5671'),
                                   ('mother', 'ROSE ANAK BUJANG', '720808-13-5682')):
            _doc(app, 'parent_ic', household_member=member, vision_run_at=timezone.now(),
                 vision_name=name, vision_nric=nric)
        _doc(app, 'str', vision_fields={
            'fields': {'recipient_name': str_name, 'recipient_nric': '', 'status': 'Lulus', 'year': '2026',
                       'source_type': 'semakan_status'}, 'student_verdict': 'ok', 'error': ''})

    def _str_check(self, app):
        from apps.scholarship.income_engine import student_str_check
        return student_str_check(app.documents.get(doc_type='str'))

    def test_the_reversed_name_is_a_stranger(self):
        from apps.scholarship.income_str_ownership import str_recipient_is_stranger
        app = self._app()
        self._cards_and_str(app, 'GABRIEL ANAK JOHNNY')
        self.assertEqual(self._str_check(app)['name_status'], 'mismatch')
        self.assertIs(str_recipient_is_stranger(app), True)

    def test_the_fathers_own_name_with_ak_still_matches(self):
        from apps.scholarship.income_str_ownership import str_recipient_is_stranger
        app = self._app()
        self._cards_and_str(app, 'JOHNNY AK GABRIEL')
        self.assertEqual(self._str_check(app)['name_status'], 'match')
        self.assertIs(str_recipient_is_stranger(app), False)


class TheBirthCertificateFatherRow(TestCase):
    """Review: the BC's father row against a father name only ANAK gives is never a NEW red."""

    def _row(self, bc_father):
        from apps.scholarship.income_engine.doc_checks import student_bc_check
        app = make_application('profile_complete', student=make_student(name='Mary Anak Johnny',
                                                                        nric='080808-13-5566'))
        bc = _doc(app, 'birth_certificate', vision_fields={'fields': {
            'bc_child_name': 'MARY ANAK JOHNNY', 'bc_father_name': bc_father}, 'error': ''})
        return student_bc_check(bc)['father_status']

    def test_a_matching_father_is_green_and_a_different_one_stays_unjudged(self):
        self.assertEqual(self._row('JOHNNY ANAK GABRIEL'), 'match')
        self.assertEqual(self._row('PETER ANAK SIMON'), 'no_ref')      # as before TD-408
