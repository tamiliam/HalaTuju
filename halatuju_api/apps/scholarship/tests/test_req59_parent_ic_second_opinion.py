"""Request #59 (2026-11-05) — a parent's IC second opinion was measured against the STUDENT.

When the cheap Vision read of a MyKad looks doubtful, `vision.run_vision_for_document` asks Gemini
to re-read the card, and `_merge_ic_reads` accepts Gemini's NAME only when it agrees with the
reference the deterministic read did not. That reference was always the student's own profile — so
for a FATHER's card (whose name is never his child's) a correct second reading was thrown away, the
misread name was kept, and the father's card then "did not match" his own salary slip: blocked.

The fix compares a parent's card with THAT parent's own reference (`parent_ic_reference`: the name
the student entered for that member, and that member's own income proof), on the same `name_match`
bar the student's own card uses. The student's own IC is unchanged. Every AI call is mocked.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship import vision
from apps.scholarship.income_engine import parent_ic_reference
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student

_IMAGE = b'\xff\xd8\xff\xe0 not a real jpeg, never decoded'
STUDENT_NRIC = '050101-14-1234'
FATHER_NRIC = '700101-14-5677'


def _doc(application, doc_type, member='', **kw):
    kw.setdefault('storage_path', f'test/{doc_type}/{ApplicantDocument.objects.count()}')
    kw.setdefault('content_type', 'image/jpeg')
    return ApplicantDocument.objects.create(application=application, doc_type=doc_type,
                                            household_member=member, **kw)


def _slip(application, member, name, nric=''):
    return _doc(application, 'salary_slip', member, vision_fields={
        'fields': {'name': name, 'nric': nric, 'gross_income': '1800.00', 'period': 'Oct 2026'},
        'student_verdict': 'ok', 'error': ''})


def _read(doc, *, nric, name, second):
    """The real MyKad pipeline: Vision answers `nric`/`name`, the mocked Gemini answers `second`."""
    ocr = {'nric': nric, 'name': name, 'address': '', 'error': None}
    with patch('apps.scholarship.vision._fetch_image_bytes', return_value=_IMAGE), \
            patch('apps.scholarship.vision.extract_mykad', return_value=ocr), \
            patch('apps.scholarship.vision._gemini_ic_second_opinion', return_value=second) as g:
        vision.run_vision_for_document(doc)
    doc.refresh_from_db()
    g.assert_called_once()                     # every case here is a doubtful read that escalates
    return doc


def _app(*, route='salary', earner='father', student_name='Arun A/L Kumar', **kw):
    kw.setdefault('father_name', 'Kumar A/L Raju')
    kw.setdefault('mother_name', 'Saraswathy A/P Muthu')
    kw.setdefault('other_family_members', [])
    return make_application('profile_complete', income_route=route, income_earner=earner,
                            income_working_members=[earner] if route == 'salary' else [],
                            student=make_student(nric=STUDENT_NRIC, name=student_name), **kw)


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, IC_GEMINI_FALLBACK_ENABLED=True)
class AFathersCardIsComparedWithTheFather(TestCase):

    def test_a_second_reading_that_matches_the_fathers_entered_name_is_accepted(self):
        app = _app()
        pic = _read(_doc(app, 'parent_ic', 'father'), nric=FATHER_NRIC, name='KUMAR A/L RAJV',
                    second={'nric': FATHER_NRIC, 'name': 'KUMAR A/L RAJU', 'address': ''})
        self.assertEqual(pic.vision_name, 'KUMAR A/L RAJU')
        self.assertEqual(pic.vision_fields['capture'], 'ai')

    def test_a_second_reading_that_does_not_match_the_father_is_rejected(self):
        app = _app()
        pic = _read(_doc(app, 'parent_ic', 'father'), nric=FATHER_NRIC, name='KUMAR A/L RAJV',
                    second={'nric': FATHER_NRIC, 'name': 'SUBRAMANIAM A/L VELU', 'address': ''})
        self.assertEqual(pic.vision_name, 'KUMAR A/L RAJV')        # the deterministic read stands

    def test_the_fathers_own_salary_slip_name_is_a_reference_too(self):
        app = _app(father_name='')                                 # nothing typed for him
        _slip(app, 'father', 'KUMAR A/L RAJU')
        pic = _read(_doc(app, 'parent_ic', 'father'), nric=FATHER_NRIC, name='KUMAR A/L RAJV',
                    second={'nric': FATHER_NRIC, 'name': 'KUMAR A/L RAJU', 'address': ''})
        self.assertEqual(pic.vision_name, 'KUMAR A/L RAJU')

    def test_a_confident_read_of_the_father_is_never_overridden(self):
        """The deterministic read already agrees with the slip: Gemini's different name loses, as on
        the student's own card (the bar is the same; only the person changed)."""
        app = _app(father_name='Kumar Raju')
        _slip(app, 'father', 'KUMAR A/L RAJU')
        pic = _read(_doc(app, 'parent_ic', 'father'), nric='', name='KUMAR A/L RAJU',
                    second={'nric': FATHER_NRIC, 'name': 'KUMAR A/L RAJU SAMY', 'address': ''})
        self.assertEqual(pic.vision_name, 'KUMAR A/L RAJU')

    def test_the_second_reading_must_agree_with_the_name_not_merely_be_close(self):
        """`name_match` is exact on the name's parts — a near spelling is not agreement. The bar
        was not loosened for a parent (the tolerant relationship matcher is NOT used here)."""
        app = _app()
        pic = _read(_doc(app, 'parent_ic', 'father'), nric=FATHER_NRIC, name='XXXX YYYY',
                    second={'nric': FATHER_NRIC, 'name': 'KUMAR A/L RAJOO', 'address': ''})
        self.assertEqual(pic.vision_name, 'XXXX YYYY')

    def test_the_numbers_are_compared_with_the_fathers_slip_not_the_student(self):
        app = _app()
        _slip(app, 'father', 'KUMAR A/L RAJU', FATHER_NRIC)
        pic = _read(_doc(app, 'parent_ic', 'father'), nric='700101-14-5617', name='KUMAR A/L RAJU',
                    second={'nric': FATHER_NRIC, 'name': 'KUMAR A/L RAJU', 'address': ''})
        self.assertEqual(pic.vision_nric, FATHER_NRIC)              # recovered the glare-blurred digit
        other = _read(_doc(app, 'parent_ic', 'father'), nric='700101-14-5617', name='KUMAR A/L RAJU',
                      second={'nric': STUDENT_NRIC, 'name': 'KUMAR A/L RAJU', 'address': ''})
        self.assertEqual(other.vision_nric, '700101-14-5617')       # the student's number is no reference

    def test_the_gate_that_blocked_the_student_now_clears(self):
        """The #59 shape end to end: the father's card, misread, against his own clear salary slip."""
        from apps.scholarship.income_engine import student_income_ic_check
        from apps.scholarship.services import document_red_blockers
        app = _app()
        _slip(app, 'father', 'KUMAR A/L RAJU', FATHER_NRIC)
        pic = _read(_doc(app, 'parent_ic', 'father'), nric=FATHER_NRIC, name='KUMAR A/L RAJV',
                    second={'nric': FATHER_NRIC, 'name': 'KUMAR A/L RAJU', 'address': ''})
        chk = student_income_ic_check(pic)
        self.assertEqual((chk['proof_name_status'], chk['proof_nric_status']), ('match', 'match'))
        self.assertNotIn('parent_ic_person_mismatch', document_red_blockers(app))


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, IC_GEMINI_FALLBACK_ENABLED=True)
class AFatherAndChildWhoShareOnlyASurname(TestCase):
    def setUp(self):
        self.app = _app(student_name='Lim Wei Ming', father_name='Lim Ah Kow')

    def test_the_second_reading_must_be_the_fathers_name(self):
        pic = _read(_doc(self.app, 'parent_ic', 'father'), nric=FATHER_NRIC, name='LIM AH KOV',
                    second={'nric': FATHER_NRIC, 'name': 'LIM AH KOW', 'address': ''})
        self.assertEqual(pic.vision_name, 'LIM AH KOW')

    def test_the_childs_name_on_the_fathers_card_never_passes_on_the_shared_surname(self):
        """Before #59 this was ACCEPTED: the child's name agreed with the student's own profile."""
        pic = _read(_doc(self.app, 'parent_ic', 'father'), nric=FATHER_NRIC, name='LIM AH KOV',
                    second={'nric': FATHER_NRIC, 'name': 'LIM WEI MING', 'address': ''})
        self.assertEqual(pic.vision_name, 'LIM AH KOV')

    def test_another_lim_is_not_the_father(self):
        pic = _read(_doc(self.app, 'parent_ic', 'father'), nric=FATHER_NRIC, name='LIM AH KOV',
                    second={'nric': FATHER_NRIC, 'name': 'LIM CHEE KEONG', 'address': ''})
        self.assertEqual(pic.vision_name, 'LIM AH KOV')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, IC_GEMINI_FALLBACK_ENABLED=True)
class AMotherOrGuardiansCardIsComparedWithThatPerson(TestCase):

    def test_the_mothers_card_takes_her_own_name(self):
        app = _app(earner='mother')
        mic = _read(_doc(app, 'parent_ic', 'mother'), nric='720202-14-5678', name='SARASWATHY A/P MUTHV',
                    second={'nric': '720202-14-5678', 'name': 'SARASWATHY A/P MUTHU', 'address': ''})
        self.assertEqual(mic.vision_name, 'SARASWATHY A/P MUTHU')

    def test_the_fathers_name_on_the_mothers_card_is_rejected(self):
        app = _app(earner='mother')
        mic = _read(_doc(app, 'parent_ic', 'mother'), nric='720202-14-5678', name='SARASWATHY A/P MUTHV',
                    second={'nric': '720202-14-5678', 'name': 'KUMAR A/L RAJU', 'address': ''})
        self.assertEqual(mic.vision_name, 'SARASWATHY A/P MUTHV')

    def test_the_guardians_card_takes_the_guardians_entered_name(self):
        app = _app(earner='guardian', other_family_members=[{'name': 'Velu A/L Samy',
                                                             'relationship': 'guardian'}])
        gic = _read(_doc(app, 'parent_ic', 'guardian'), nric='600303-14-5111', name='VELU A/L SAMV',
                    second={'nric': '600303-14-5111', 'name': 'VELU A/L SAMY', 'address': ''})
        self.assertEqual(gic.vision_name, 'VELU A/L SAMY')

    def test_an_untagged_card_is_the_declared_earners(self):
        app = _app(route='str', earner='father')
        pic = _read(_doc(app, 'parent_ic', ''), nric=FATHER_NRIC, name='KUMAR A/L RAJV',
                    second={'nric': FATHER_NRIC, 'name': 'KUMAR A/L RAJU', 'address': ''})
        self.assertEqual(pic.vision_name, 'KUMAR A/L RAJU')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TheReferenceItself(TestCase):

    def test_the_str_is_the_earners_document_only(self):
        app = _app(route='str', earner='father')
        _doc(app, 'str', 'father', vision_fields={'fields': {
            'recipient_name': 'KUMAR A/L RAJU', 'recipient_nric': '700101145677', 'status': 'Lulus'}})
        father = parent_ic_reference(_doc(app, 'parent_ic', 'father'))
        self.assertEqual((father.names, father.nric), (['Kumar A/L Raju', 'KUMAR A/L RAJU'], '700101145677'))
        mother = parent_ic_reference(_doc(app, 'parent_ic', 'mother'))
        self.assertEqual((mother.names, mother.nric), (['Saraswathy A/P Muthu'], ''))

    def test_the_student_is_never_in_a_parents_reference(self):
        app = _app()
        ref = parent_ic_reference(_doc(app, 'parent_ic', 'father'))
        self.assertNotIn('Arun A/L Kumar', ref.names)
        self.assertNotEqual(ref.nric, STUDENT_NRIC)

    def test_no_member_means_no_reference(self):
        app = _app(earner='')
        ref = parent_ic_reference(_doc(app, 'parent_ic', ''))
        self.assertEqual((ref.names, ref.nric), ([], ''))


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, IC_GEMINI_FALLBACK_ENABLED=True)
class TheStudentsOwnCardIsUnchanged(TestCase):
    def setUp(self):
        self.app = _app()

    def test_a_second_reading_of_her_own_name_is_accepted(self):
        ic = _read(_doc(self.app, 'ic'), nric=STUDENT_NRIC, name='ARUN A/L KUMAP',
                   second={'nric': STUDENT_NRIC, 'name': 'ARUN A/L KUMAR', 'address': ''})
        self.assertEqual(ic.vision_name, 'ARUN A/L KUMAR')

    def test_her_fathers_name_on_her_own_card_is_rejected(self):
        """The father's reference belongs to his card only — it never vouches for the student's."""
        ic = _read(_doc(self.app, 'ic'), nric=STUDENT_NRIC, name='ARUN A/L KUMAP',
                   second={'nric': STUDENT_NRIC, 'name': 'KUMAR A/L RAJU', 'address': ''})
        self.assertEqual(ic.vision_name, 'ARUN A/L KUMAP')

    def test_the_merge_with_a_plain_profile_is_the_old_rule(self):
        class _P:
            nric, name = STUDENT_NRIC, 'Arun A/L Kumar'
        det = {'nric': STUDENT_NRIC, 'name': 'ARUN A/L KUMAP', 'address': '', 'error': None}
        self.assertEqual(vision._merge_ic_reads(det, {'name': 'ARUN'}, _P())['name'], 'ARUN')   # partial
        self.assertEqual(vision._merge_ic_reads(det, {'name': 'SOMEONE ELSE'}, _P())['name'], 'ARUN A/L KUMAP')
        self.assertEqual(vision._merge_ic_reads(det, {'name': 'ARUN A/L KUMAR'}, None)['name'], 'ARUN A/L KUMAP')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, IC_GEMINI_FALLBACK_ENABLED=True)
class TheEdgesOfTheParentReference(TestCase):
    """Adversarial-review lows: odd rosters never let a wrong person's card clear the slip check."""

    def _blockers(self, app):
        from apps.scholarship.services import document_red_blockers
        return document_red_blockers(app)

    def test_a_one_word_father_name_does_not_let_the_childs_card_clear_the_slip_check(self):
        app = _app(student_name='Ahmad Bin Ismail', father_name='ISMAIL')
        _slip(app, 'father', 'ISMAIL BIN HASSAN', FATHER_NRIC)
        pic = _read(_doc(app, 'parent_ic', 'father'), nric='700101-14-5617', name='AHMAD BIN ISMAL',
                    second={'nric': '700101-14-5617', 'name': 'AHMAD BIN ISMAIL', 'address': ''})
        from apps.scholarship.income_engine import student_income_ic_check
        chk = student_income_ic_check(pic)
        self.assertNotEqual(chk['proof_name_status'], 'match')      # the card-vs-slip check still bites
        self.assertIn('parent_ic_person_mismatch', self._blockers(app))

    def test_the_uncles_name_on_the_card_with_the_aunts_slip_stays_blocked(self):
        app = _app(earner='guardian', other_family_members=[
            {'name': 'Velu A/L Samy', 'relationship': 'guardian'},
            {'name': 'Meena A/P Raman', 'relationship': 'guardian'}])
        _slip(app, 'guardian', 'MEENA A/P RAMAN', '650505-14-5222')
        gic = _read(_doc(app, 'parent_ic', 'guardian'), nric='600303-14-5111', name='VELU A/L SAMV',
                    second={'nric': '600303-14-5111', 'name': 'VELU A/L SAMY', 'address': ''})
        from apps.scholarship.income_engine import student_income_ic_check
        chk = student_income_ic_check(gic)
        self.assertNotEqual(chk['proof_name_status'], 'match')
        self.assertIn('parent_ic_person_mismatch', self._blockers(app))

    def test_an_untagged_mothers_card_is_not_given_the_fathers_name(self):
        app = _app(route='str', earner='father')
        pic = _read(_doc(app, 'parent_ic', ''), nric='720202-14-5678', name='SARASWATHY A/P MUTHV',
                    second={'nric': '720202-14-5678', 'name': 'SARASWATHY A/P MUTHU', 'address': ''})
        self.assertEqual(pic.vision_name, 'SARASWATHY A/P MUTHV')   # cheap reading kept, as today

    def test_a_failing_reference_lookup_keeps_the_cheap_reading(self):
        app = _app()
        with patch('apps.scholarship.income_engine.identity_checks._roster_candidates',
                   side_effect=RuntimeError('boom')):
            pic = _read(_doc(app, 'parent_ic', 'father'), nric=FATHER_NRIC, name='KUMAR A/L RAJV',
                        second={'nric': FATHER_NRIC, 'name': 'KUMAR A/L RAJU', 'address': ''})
        self.assertEqual(pic.vision_name, 'KUMAR A/L RAJV')
        self.assertEqual(pic.vision_error, '')
