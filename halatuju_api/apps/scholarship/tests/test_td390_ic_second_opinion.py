"""TD-390 — during a Gemini outage the IC's second opinion silently did not run.

`vision.run_vision_for_document` asks Gemini to re-read a MyKad when the deterministic Vision read is
low-confidence (a field missing, or disagreeing with what the student typed). When that call failed
on OUR side the half read was stored as if complete, so the identity gate told the student her IC
did not match (or could not be read) — a card Gemini would have rescued — and nothing retried it or
counted it.

Owner-approved design (2026-10-25): record the skipped second opinion on the row; the gate says
"service down, try later" — and STILL blocks; every reader of a mismatch read off half a read says
"pending" and asks the student for nothing; the hourly sweep re-runs it; the outage alert counts it.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import read_errors, vision
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student

_402 = ("All AI models failed: gemini-2.5-flash: 402 RESOURCE_EXHAUSTED. Your prepayment credits are "
        "depleted.; gemini-2.5-flash-lite: 402 RESOURCE_EXHAUSTED.")
_REJECTED = 'No model could read this document: gemini-2.5-flash: 400 Unable to process input image.'
_IMAGE = b'\xff\xd8\xff\xe0 not a real jpeg, never decoded'
STUDENT_NRIC = '050101-14-1234'
MISREAD_NRIC = '050101-14-1284'          # one glare-blurred digit
STUDENT_NAME = 'Kavitha A/P Rajan'


def _doc(application, doc_type='ic', **kw):
    kw.setdefault('storage_path', f'test/{doc_type}/{ApplicantDocument.objects.count()}')
    kw.setdefault('content_type', 'image/jpeg')
    return ApplicantDocument.objects.create(application=application, doc_type=doc_type, **kw)


def _read(doc, *, nric, name, second):
    """Run the real MyKad pipeline with Vision answering `nric`/`name` and the Gemini second
    opinion answering `second` (a dict — `{'_error': …}` or the fields it read)."""
    ocr = {'nric': nric, 'name': name, 'address': '', 'error': None}
    with patch('apps.scholarship.vision._fetch_image_bytes', return_value=_IMAGE), \
            patch('apps.scholarship.vision.extract_mykad', return_value=ocr), \
            patch('apps.scholarship.vision._gemini_ic_second_opinion', return_value=second) as g:
        result = vision.run_vision_for_document(doc)
    doc.refresh_from_db()
    return result, g


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, IC_GEMINI_FALLBACK_ENABLED=True)
class TheStudentsOwnIc(TestCase):
    def setUp(self):
        self.app = make_application('shortlisted', student=make_student(nric=STUDENT_NRIC, name=STUDENT_NAME))

    def _gate(self):
        from apps.scholarship.services import consent_blockers, ic_identity_blockers
        return ic_identity_blockers(self.app), consent_blockers(self.app)

    def test_a_402_on_the_second_opinion_is_service_down_and_still_blocks(self):
        ic = _doc(self.app)
        _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME, second={'_error': _402})
        self.assertTrue(read_errors.ic_second_opinion_deferred(ic))
        self.assertGreater(ic.vision_fields[read_errors.IC_SECOND_OPINION_UNTIL],
                           (timezone.now() + timedelta(hours=71)).timestamp())
        gate, consent = self._gate()
        self.assertEqual(gate, ['ic_service_down'])              # not ic_nric_mismatch
        self.assertIn('ic_service_down', consent)                # a deferred IC never passes identity
        self.assertNotIn('ic_nric_mismatch', consent)

    def test_a_matching_name_with_no_nric_does_not_pass_on_half_a_read(self):
        """Review finding 2: the NRIC is the identity key, and it is the field the second opinion
        was asked for — a name alone must not carry a deferred card through the gate."""
        ic = _doc(self.app)
        _read(ic, nric='', name=STUDENT_NAME, second={'_error': _402})
        self.assertEqual(self._gate()[0], ['ic_service_down'])

    def test_the_deferral_only_delays_a_signal_it_never_hides_one(self):
        """Review finding 3: inside the 72-hour window the card is "try later"; past it the stored
        read is complete again — its mismatch, and the officer's flag, come back exactly as before."""
        from apps.scholarship.anomaly_engine import detect_anomalies
        ic = _doc(self.app)
        _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME, second={'_error': _402})
        start = timezone.now()
        for hours, gate, flagged in ((71, ['ic_service_down'], False), (73, ['ic_nric_mismatch'], True)):
            with self.subTest(hours=hours), \
                    patch('django.utils.timezone.now', return_value=start + timedelta(hours=hours)):
                self.assertEqual(self._gate()[0], gate)
                self.assertIs('vision_nric_mismatch' in [a['code'] for a in detect_anomalies(self.app)], flagged)

    def test_nothing_read_at_all_is_service_down_too(self):
        ic = _doc(self.app)
        _read(ic, nric='', name='', second={'_error': _402})
        self.assertEqual(self._gate()[0], ['ic_service_down'])

    def test_a_document_level_rejection_keeps_the_old_answer(self):
        ic = _doc(self.app)
        _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME, second={'_error': _REJECTED})
        self.assertFalse(read_errors.ic_second_opinion_deferred(ic))
        self.assertEqual(ic.vision_fields['ic_second_opinion'], 'theirs')
        self.assertEqual(self._gate()[0], ['ic_nric_mismatch'])

    def test_a_clean_read_asks_no_second_opinion_and_carries_no_mark(self):
        ic = _doc(self.app)
        _, g = _read(ic, nric=STUDENT_NRIC, name=STUDENT_NAME, second={'_error': _402})
        g.assert_not_called()
        self.assertNotIn(read_errors.IC_SECOND_OPINION_ERROR, ic.vision_fields)
        self.assertNotIn('ic_second_opinion', ic.vision_fields)
        self.assertEqual(self._gate()[0], [])

    def test_a_new_outage_after_the_window_lapsed_starts_a_new_window(self):
        """Review round 2, finding 2: the deadline is renewed when a new failure lands on a lapsed mark."""
        ic = _doc(self.app)
        _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME, second={'_error': _402})
        ic.vision_fields = {**ic.vision_fields,
                            read_errors.IC_SECOND_OPINION_UNTIL: int(timezone.now().timestamp()) - 60}
        ic.save(update_fields=['vision_fields'])
        self.assertFalse(read_errors.ic_second_opinion_deferred(ic))
        _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME, second={'_error': _402})
        self.assertTrue(read_errors.ic_second_opinion_deferred(ic))
        self.assertAlmostEqual(ic.vision_fields[read_errors.IC_SECOND_OPINION_UNTIL],
                               (timezone.now() + timedelta(hours=72)).timestamp(), delta=120)

    def test_a_later_read_with_the_second_opinion_clears_the_mark_and_passes(self):
        ic = _doc(self.app)
        _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME, second={'_error': _402})
        _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME,
              second={'nric': STUDENT_NRIC, 'name': STUDENT_NAME, 'address': ''})
        self.assertFalse(read_errors.ic_second_opinion_deferred(ic))
        self.assertNotIn(read_errors.IC_SECOND_OPINION_UNTIL, ic.vision_fields)
        self.assertEqual(ic.vision_fields['ic_second_opinion'], 'ok')
        self.assertEqual(self._gate()[0], [])

    def test_a_re_run_during_an_outage_never_replaces_a_completed_read(self):
        ic = _doc(self.app)
        _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME,
              second={'nric': STUDENT_NRIC, 'name': STUDENT_NAME, 'address': ''})
        self.assertEqual(ic.vision_nric, STUDENT_NRIC)
        r, _ = _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME, second={'_error': _402})
        self.assertTrue(r.get('stale_kept'))
        self.assertEqual(ic.vision_nric, STUDENT_NRIC)            # the completed read stands
        self.assertFalse(read_errors.ic_second_opinion_deferred(ic))
        self.assertEqual(self._gate()[0], [])

    def test_a_vision_failure_on_re_run_keeps_the_half_read_and_its_mark(self):
        ic = _doc(self.app)
        _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME, second={'_error': _402})
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=_IMAGE), \
                patch('apps.scholarship.vision.extract_mykad',
                      return_value={'nric': '', 'name': '', 'address': '', 'error': '403 billing'}):
            vision.run_vision_for_document(ic)
        ic.refresh_from_db()
        self.assertEqual(ic.vision_nric, MISREAD_NRIC)
        self.assertTrue(read_errors.ic_second_opinion_deferred(ic))

    def test_the_identity_verdict_raises_no_name_confirm_off_half_a_read(self):
        """NRIC verified, name read wrong, second opinion skipped: the gate lets her through on the
        NRIC (unchanged), and the verdict says "service down" instead of asking her to confirm a
        name Gemini might have read right."""
        from apps.scholarship.resolution import _ticketable_unresolved
        from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION, build_verdict
        ic = _doc(self.app)
        _read(ic, nric=STUDENT_NRIC, name='KAVTHA RAJN BINTI', second={'_error': _402})
        identity = next(f for f in build_verdict(self.app) if f['fact'] == 'identity')
        codes = [i['code'] for i in identity['unresolved']]
        self.assertIn('ic_service_down', codes)
        self.assertNotIn('name_mismatch', codes)
        self.assertNotIn('name_mismatch', _ticketable_unresolved(self.app))
        self.assertEqual(VERDICT_ENGINE_VERSION, '2026-10-25.1')

    def test_the_students_chips_and_coach_do_not_call_it_a_mismatch(self):
        from apps.scholarship.help_engine import verdict_for_document
        from apps.scholarship.identity import compare
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        ic = _doc(self.app)
        _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME, second={'_error': _402})
        from apps.scholarship.resolution import doc_match_verdict
        data = ApplicantDocumentSerializer(ic).data
        self.assertEqual(data['vision_nric_verdict'], '')
        self.assertEqual(doc_match_verdict(ic), 'pending')        # an IC request is neither failed nor met
        self.assertEqual(verdict_for_document(ic), 'review_manually')
        self.assertEqual(compare(ic, self.app.profile)['nric'], 'unknown')

    def test_no_officer_anomaly_is_raised_off_half_a_read(self):
        from apps.scholarship.anomaly_engine import detect_anomalies
        ic = _doc(self.app)
        _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME, second={'_error': _402})
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('vision_nric_mismatch', codes)
        ic.vision_fields = {k: v for k, v in ic.vision_fields.items()
                            if k != read_errors.IC_SECOND_OPINION_ERROR}
        ic.save(update_fields=['vision_fields'])               # the same read, complete: it flags
        self.assertIn('vision_nric_mismatch', [a['code'] for a in detect_anomalies(self.app)])


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class AParentsIc(TestCase):
    """A parent's card is always compared with the STUDENT's profile by `_should_gemini_ic`, so it
    always asks for the second opinion — an outage marks every one, and its readers must say pending."""

    def setUp(self):
        self.app = make_application('profile_complete', income_route='str', income_earner='father',
                                    student=make_student(nric=STUDENT_NRIC, name='Arun A/L Kumar'))

    def _parent(self, name):
        pic = _doc(self.app, 'parent_ic', household_member='father')
        _read(pic, nric='700101-14-5677', name=name, second={'_error': _402})
        return pic

    def test_a_deferred_parent_ic_is_pending_and_asks_for_nothing(self):
        from apps.scholarship.help_engine import verdict_for_document
        from apps.scholarship.income_engine import student_income_ic_check
        from apps.scholarship.resolution import STUDENT_DOC_REQUEST_CODES, _ticketable_unresolved, doc_match_verdict
        from apps.scholarship.services import document_red_blockers, document_unreadable_blockers
        pic = self._parent('RAMASAMY A/L GOPAL')       # misread — no patronymic link to "Kumar"
        self.assertTrue(read_errors.ic_second_opinion_deferred(pic))
        chk = student_income_ic_check(pic)
        self.assertEqual(chk['name_status'], 'pending')
        self.assertTrue(chk['deferred'])
        self.assertEqual(doc_match_verdict(pic), 'pending')
        self.assertNotIn('parent_ic_person_mismatch', document_red_blockers(self.app))
        self.assertNotIn('income_document_unreadable', document_unreadable_blockers(self.app))
        asks = set(_ticketable_unresolved(self.app))
        self.assertFalse(asks & {'father_patronymic_mismatch', 'earner_ic_unreadable'})
        self.assertFalse(asks & STUDENT_DOC_REQUEST_CODES & {'earner_ic_unreadable'})
        self.assertNotIn(verdict_for_document(pic), ('unreadable', 'income_relationship_mismatch'))

    def test_a_blank_deferred_parent_ic_is_service_down_in_the_verdict(self):
        from apps.scholarship.help_engine import verdict_for_document
        from apps.scholarship.services import document_unreadable_blockers
        from apps.scholarship.verdict_engine import build_verdict
        pic = self._parent('')
        income = next(f for f in build_verdict(self.app) if f['fact'] == 'income')
        codes = [i['code'] for i in income['unresolved']]
        self.assertIn('ic_service_down', codes)
        self.assertNotIn('earner_ic_unreadable', codes)
        self.assertNotIn('income_document_unreadable', document_unreadable_blockers(self.app))
        self.assertNotEqual(verdict_for_document(pic), 'unreadable')

    def test_the_salary_route_says_service_down_too(self):
        from apps.scholarship.verdict_engine import build_verdict
        self.app.income_route, self.app.income_working_members = 'salary', ['father']
        self.app.save(update_fields=['income_route', 'income_working_members'])
        self._parent('')
        income = next(f for f in build_verdict(self.app) if f['fact'] == 'income')
        codes = [i['code'] for i in income['unresolved']]
        self.assertIn('ic_service_down', codes)
        self.assertNotIn('earner_ic_unreadable', codes)

    def test_a_birth_certificate_compared_with_a_deferred_mothers_card_shows_no_clash(self):
        from apps.scholarship.income_engine import student_bc_check
        self.app.income_earner = 'mother'
        self.app.save(update_fields=['income_earner'])
        mic = _doc(self.app, 'parent_ic', household_member='mother')
        _read(mic, nric='720202-14-5678', name='ZZZ QQQ', second={'_error': _402})   # misread name
        bc = _doc(self.app, 'birth_certificate', vision_fields={
            'fields': {'bc_child_name': 'Arun A/L Kumar', 'bc_mother_name': 'Saraswathy A/P Muthu',
                       'bc_mother_nric': '720202145679'},
            'student_verdict': 'ok', 'error': ''})
        self.assertNotEqual(student_bc_check(bc)['mother_status'], 'mismatch')

    def test_an_str_compared_only_with_the_earners_deferred_card_names_no_stranger(self):
        from apps.scholarship.income_engine import student_str_check
        self._parent('RAMASAMY A/L GOPAL')
        str_doc = _doc(self.app, 'str', household_member='father', vision_fields={
            'fields': {'recipient_name': 'KUMAR A/L RAJU', 'recipient_nric': '700101145699',
                       'status': 'Lulus', 'source_type': 'semakan_status'},
            'student_verdict': 'ok', 'error': ''})
        sc = student_str_check(str_doc)
        self.assertNotEqual(sc['name_status'], 'mismatch')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class AnotherMembersDeferredCardClearsNoStranger(TestCase):
    """Review finding 1 (blocker): the first cut held back the STR mismatch when ANY household card
    was half-read, so an unrelated mother's deferred card let a stranger's STR through the gate.
    Only the earner's OWN deferred card, with no clean card to decide it, may hold a mismatch back."""

    def _household(self, route):
        app = make_application('profile_complete', income_route=route, income_earner='father',
                               income_working_members=['father'] if route == 'salary' else [],
                               father_name='Muthu A/L Raman', mother_name='Siti Binti Ahmad',
                               father_occupation='private', mother_occupation='homemaker',
                               other_family_members=[],
                               student=make_student(nric=STUDENT_NRIC, name='Arun A/L Muthu'))
        father = _doc(app, 'parent_ic', household_member='father', vision_run_at=timezone.now(),
                      vision_name='MUTHU A/L RAMAN', vision_nric='690101-14-5671')   # clean read
        mother = _doc(app, 'parent_ic', household_member='mother')
        _read(mother, nric='710202-14-5682', name='SITI BINTI AHMAD', second={'_error': _402})
        self.assertTrue(read_errors.ic_second_opinion_deferred(mother))
        self.assertFalse(read_errors.ic_second_opinion_deferred(father))
        _doc(app, 'str', household_member='father', vision_fields={
            'fields': {'recipient_name': 'LIM AH KOW', 'recipient_nric': '650303-07-5123',
                       'status': 'Lulus', 'year': '2026', 'source_type': 'semakan_status'},
            'student_verdict': 'ok', 'error': ''})
        return app, mother

    def _blocked_both_ways(self, route):
        """The gate's answer with the mother's card deferred, and with that mark removed."""
        from apps.scholarship.income_engine import student_str_check
        from apps.scholarship.services import income_doc_blockers
        app, mother = self._household(route)
        sc = student_str_check(app.documents.get(doc_type='str'))
        deferred = income_doc_blockers(app)
        mother.vision_fields = {k: v for k, v in mother.vision_fields.items()
                                if k != read_errors.IC_SECOND_OPINION_ERROR}
        mother.save(update_fields=['vision_fields'])
        return sc, deferred, income_doc_blockers(app)

    def test_a_strangers_str_still_blocks_on_the_str_route(self):
        from apps.scholarship.income_str_ownership import STR_NOT_HOUSEHOLD
        sc, deferred, clean = self._blocked_both_ways('str')
        self.assertEqual(sc['name_status'], 'mismatch')        # father's clean card decides it
        self.assertIn(STR_NOT_HOUSEHOLD, clean)                 # what live f3105a5b answers
        self.assertEqual(deferred, clean)                       # the mother's deferral changes nothing

    def _earner_only_household(self, route, *, mother_clean=False):
        """Scenario B (owner ruling 2026-10-25): the father is the earner and his OWN card is half-read;
        the mother is not in the household (deceased) unless `mother_clean`, when her card reads cleanly."""
        app = make_application('profile_complete', income_route=route, income_earner='father',
                               income_working_members=['father'] if route == 'salary' else [],
                               father_name='Muthu A/L Raman', father_occupation='private',
                               mother_name='Siti Binti Ahmad',
                               mother_occupation='homemaker' if mother_clean else 'deceased',
                               other_family_members=[],
                               student=make_student(nric=STUDENT_NRIC, name='Arun A/L Muthu'))
        father = _doc(app, 'parent_ic', household_member='father')
        _read(father, nric='690101-14-5671', name='MUTHU A/L RAMAN', second={'_error': _402})
        if mother_clean:
            _doc(app, 'parent_ic', household_member='mother', vision_run_at=timezone.now(),
                 vision_name='SITI BINTI AHMAD', vision_nric='710202-14-5682')
        _doc(app, 'str', household_member='father', vision_fields={
            'fields': {'recipient_name': 'LIM AH KOW', 'recipient_nric': '650303-07-5123',
                       'status': 'Lulus', 'year': '2026', 'source_type': 'semakan_status'},
            'student_verdict': 'ok', 'error': ''})
        return app

    def test_scenario_b_waits_inside_the_window_and_blames_after_it(self):
        from apps.scholarship.income_str_ownership import STR_NOT_HOUSEHOLD
        from apps.scholarship.services import consent_blockers, income_doc_blockers
        for route in ('str', 'salary'):
            with self.subTest(route=route):
                app = self._earner_only_household(route)
                held = income_doc_blockers(app)
                self.assertIn('ic_service_down', held)          # "still checking, try later"
                self.assertNotIn(STR_NOT_HOUSEHOLD, held)       # never the student's fault
                self.assertEqual(consent_blockers(app).count('ic_service_down'), 1)
                with patch('django.utils.timezone.now', return_value=timezone.now() + timedelta(hours=73)):
                    lapsed = income_doc_blockers(app)
                self.assertIn(STR_NOT_HOUSEHOLD, lapsed)        # the old answer, once the window lapses
                self.assertNotIn('ic_service_down', lapsed)

    def test_scenario_c_a_clean_card_decides_and_the_answer_is_unchanged(self):
        from apps.scholarship.income_str_ownership import STR_NOT_HOUSEHOLD
        from apps.scholarship.services import income_doc_blockers
        app = self._earner_only_household('str', mother_clean=True)
        out = income_doc_blockers(app)
        self.assertIn(STR_NOT_HOUSEHOLD, out)
        self.assertNotIn('ic_service_down', out)

    def test_the_salary_route_answer_is_untouched_by_the_mothers_deferral(self):
        sc, deferred, clean = self._blocked_both_ways('salary')
        self.assertEqual(sc['name_status'], 'mismatch')        # the father's clean card still decides
        self.assertEqual(deferred, clean)


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TheSweepAndTheAlert(TestCase):
    def setUp(self):
        self.app = make_application('shortlisted', student=make_student(nric=STUDENT_NRIC, name=STUDENT_NAME))

    def _deferred_ic(self, app=None, hours_ago=3):
        ic = _doc(app or self.app)
        _read(ic, nric=MISREAD_NRIC, name=STUDENT_NAME, second={'_error': _402})
        ApplicantDocument.objects.filter(pk=ic.pk).update(
            vision_run_at=timezone.now() - timedelta(hours=hours_ago))
        ic.refresh_from_db()
        return ic

    def _sweep(self, second):
        from apps.scholarship.services import reprocess_unread_ic_documents
        ocr = {'nric': MISREAD_NRIC, 'name': STUDENT_NAME, 'address': '', 'error': None}
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=_IMAGE), \
                patch('apps.scholarship.vision.extract_mykad', return_value=ocr) as v, \
                patch('apps.scholarship.vision._gemini_ic_second_opinion', return_value=second) as g:
            return reprocess_unread_ic_documents(), v, g

    def test_the_sweep_re_runs_a_deferred_ic_and_it_passes(self):
        from apps.scholarship.services import ic_identity_blockers
        ic = self._deferred_ic()
        r, _, g = self._sweep({'nric': STUDENT_NRIC, 'name': STUDENT_NAME, 'address': ''})
        self.assertEqual(g.call_count, 1)
        ic.refresh_from_db()
        self.assertFalse(read_errors.ic_second_opinion_deferred(ic))
        self.assertEqual(ic_identity_blockers(self.app), [])
        self.assertEqual(r, {'scanned': 1, 'processed': 1, 'errored': 0})

    def test_still_down_one_probe_then_the_gate_holds_the_rest(self):
        other = make_application('shortlisted', student=make_student(nric=STUDENT_NRIC))
        first, second = self._deferred_ic(), self._deferred_ic(other)
        r, vision_calls, _ = self._sweep({'_error': _402})
        self.assertEqual(vision_calls.call_count, 1)              # one paid OCR, then stop
        self.assertEqual(r['scanned'], 1)
        r, vision_calls, _ = self._sweep({'_error': _402})        # its failure is the recent window now
        self.assertEqual((r['scanned'], vision_calls.call_count), (0, 0))
        for ic in (first, second):
            ic.refresh_from_db()
            self.assertTrue(read_errors.ic_second_opinion_deferred(ic))
            self.assertEqual(ic.vision_nric, MISREAD_NRIC)        # never degraded

    def test_a_closed_case_or_a_spent_window_is_left_alone(self):
        from apps.scholarship.services.read_retry import service_error_documents
        closed = self._deferred_ic(make_application('rejected', student=make_student(nric=STUDENT_NRIC)))
        spent = self._deferred_ic()
        spent.vision_fields = {**spent.vision_fields,
                               read_errors.IC_SECOND_OPINION_UNTIL: int(timezone.now().timestamp()) - 1}
        spent.save(update_fields=['vision_fields'])
        live = self._deferred_ic()
        ids = [d.id for d in service_error_documents(200)]
        self.assertIn(live.id, ids)
        self.assertNotIn(closed.id, ids)
        self.assertNotIn(spent.id, ids)

    def test_the_cockpit_re_run_door_writes_the_same_mark(self):
        from apps.scholarship.reextract import reextract_document
        ic = _doc(self.app)
        ocr = {'nric': MISREAD_NRIC, 'name': STUDENT_NAME, 'address': '', 'error': None}
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=_IMAGE), \
                patch('apps.scholarship.vision.extract_mykad', return_value=ocr), \
                patch('apps.scholarship.vision._gemini_ic_second_opinion', return_value={'_error': _402}):
            reextract_document(ic)
        ic.refresh_from_db()
        self.assertTrue(read_errors.ic_second_opinion_deferred(ic))

    def test_the_never_read_path_writes_the_same_mark(self):
        ic = _doc(self.app, vision_run_at=None)
        self._sweep({'_error': _402})
        ic.refresh_from_db()
        self.assertTrue(read_errors.ic_second_opinion_deferred(ic))

    def test_the_alert_counts_a_required_second_opinion_without_double_counting(self):
        from apps.scholarship.services import detect_service_outages
        self._deferred_ic(hours_ago=1)
        self._deferred_ic(make_application('shortlisted', student=make_student(nric=STUDENT_NRIC)), hours_ago=1)
        down = {s['service']: s for s in detect_service_outages(2)}
        self.assertIn('gemini', down)
        self.assertEqual((down['gemini']['attempts'], down['gemini']['service_failures']), (2, 2))
        ok = _doc(self.app)
        _read(ok, nric=MISREAD_NRIC, name=STUDENT_NAME,
              second={'nric': STUDENT_NRIC, 'name': STUDENT_NAME, 'address': ''})
        self.assertNotIn('gemini', [s['service'] for s in detect_service_outages(2)])
