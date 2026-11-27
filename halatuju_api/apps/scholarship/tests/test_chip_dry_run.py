"""The chip dry run, on the TEST database only (never a live one): counts, read-only, bands identical."""
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.scholarship import doc_chips, doc_chips_student
from apps.scholarship.eval import chip_dry_run
from apps.scholarship.eval import offer_s4_dry_run as dr
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import create_document, make_application


class ChipDryRunTests(TestCase):
    def setUp(self):
        self.app = make_application()
        create_document(self.app, 'ic', storage_path='s')
        create_document(self.app, 'photo', storage_path='s')

    def test_today_changes_no_chip_and_no_band_for_either_audience(self):
        result = chip_dry_run.run_dry(allow_sqlite=True)
        self.assertEqual(result['applications'], 1)
        self.assertTrue(result['bands_identical'])
        self.assertEqual(result['chip_fallbacks'], 0)                # N6: a clean run proves 0 fallbacks
        # an unread card: the officer sees two grey chips, the student no checklist yet
        self.assertEqual(result['per_type']['ic'], {'docs': 1, 'chips': 2, 'state_changed': 0,
                                                    'pill_changed': 0, 'student_chips': 0,
                                                    'student_state_changed': 0, 'student_pill_changed': 0})
        self.assertEqual(result['per_type']['photo']['docs'], 1)

    def test_both_audiences_are_counted_from_their_own_payload(self):
        create_document(self.app, 'semester_result', storage_path='s', vision_name_match='found')
        result = chip_dry_run.run_dry(allow_sqlite=True)
        row = result['per_type']['semester_result']
        self.assertEqual(row['student_chips'], 1)                    # the supporting-document chip
        self.assertEqual((row['student_state_changed'], row['student_pill_changed']), (0, 0))

    def test_a_student_target_rule_is_counted_on_the_student_side_only(self):
        create_document(self.app, 'semester_result', storage_path='s', vision_name_match='found')

        def target(payload):
            return [{**c, 'state': 'red'} for c in doc_chips_student.chips_for(payload)]
        row = chip_dry_run.run_dry(student_new=target, allow_sqlite=True)['per_type']['semester_result']
        self.assertEqual(row['student_state_changed'], 1)
        self.assertEqual(row['state_changed'], 0)

    def test_a_target_rule_is_counted_per_type(self):
        def target(payload):
            return [{**c, 'state': 'amber'} for c in doc_chips.chips_for(payload)]
        result = chip_dry_run.run_dry(new=target, allow_sqlite=True)
        self.assertEqual(result['per_type']['ic']['state_changed'], 2)
        self.assertEqual(result['per_type']['ic']['pill_changed'], 1)     # unread -> check
        self.assertEqual(result['per_type']['photo']['state_changed'], 0)

    def test_it_runs_inside_the_read_only_rollback(self):
        seen = []
        real = dr.read_only_rollback

        def spy(**kw):
            seen.append(kw)
            return real(**kw)
        with mock.patch.object(dr, 'read_only_rollback', spy):
            chip_dry_run.run_dry(allow_sqlite=True)
        self.assertEqual(seen, [{'allow_sqlite': True}])

    def test_it_refuses_a_non_postgres_database_unless_told(self):
        with self.assertRaises(dr.WriteRefused):
            chip_dry_run.run_dry()

    def test_the_guard_trips_if_build_verdict_reaches_the_chips_through_the_serializer(self):
        """The rig is on the MODULE the serializer calls through, so a verdict path that serialized a
        document (the only road to the chips) is refused, and the serializer's fallback cannot hide it."""
        from apps.scholarship import verdict_engine
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        real = verdict_engine.build_verdict
        calls = []

        def leaky(application):
            calls.append(1)
            if len(calls) > 1:                      # the AFTER pass, inside the guard
                ApplicantDocumentSerializer(application.documents.first()).data
            return real(application)
        with mock.patch.object(verdict_engine, 'build_verdict', leaky):
            with self.assertRaises(chip_dry_run.ChipsRefused):
                chip_dry_run.run_dry(allow_sqlite=True)

    def test_the_guard_trips_on_a_direct_call_too(self):
        for module in (doc_chips, doc_chips_student):
            for name in chip_dry_run.public_chip_functions(module):
                with (self.subTest(module.__name__, name=name),
                      self.assertRaises(chip_dry_run.ChipsRefused) as caught):
                    with chip_dry_run._chips_refused():
                        getattr(module, name)([])
                self.assertIn('doc_chips / doc_chips_student', str(caught.exception))   # names both modules

    def test_the_guard_covers_every_public_chip_function_not_only_chips_for(self):
        self.assertEqual(chip_dry_run.public_chip_functions(doc_chips),
                         ['chips_for', 'fact_chips', 'fact_status', 'pill_for', 'year_chip'])
        self.assertEqual(chip_dry_run.public_chip_functions(doc_chips_student),
                         ['chips_for', 'genuineness_note_key', 'pill_for'])

    def test_the_guard_trips_when_a_verdict_path_calls_year_chip(self):
        from apps.scholarship import verdict_engine
        real = verdict_engine.build_verdict
        calls = []

        def leaky(application):
            calls.append(1)
            if len(calls) > 1:
                doc_chips.year_chip({'doc_type': 'str'})
            return real(application)
        with (mock.patch.object(verdict_engine, 'build_verdict', leaky),
              self.assertRaises(chip_dry_run.ChipsRefused)):
            chip_dry_run.run_dry(allow_sqlite=True)

    def test_n6_a_chip_fallback_is_counted_by_the_run(self):
        def boom(*_a, **_k):
            raise ValueError('x')
        with (mock.patch.object(doc_chips_student, 'chips_for', boom),
              self.assertLogs('apps.scholarship.serializers.documents', 'ERROR') as logs):
            from apps.scholarship.serializers import documents as documents_ser
            documents_ser._CHIP_FALLBACK_LOGGED.discard('ValueError')
            result = chip_dry_run.run_dry(student_old=lambda p: [], student_new=lambda p: [],
                                          allow_sqlite=True)
        self.assertEqual(result['chip_fallbacks'], 2)                 # the ic and the photo, student side
        self.assertTrue(logs.output)
        self.assertIn('chip_fallbacks 2', chip_dry_run.render_counts(result).splitlines()[0])

    def test_the_guard_trips_even_when_the_caller_swallows_the_raise(self):
        with self.assertRaises(chip_dry_run.ChipsRefused):
            with chip_dry_run._chips_refused():
                try:
                    doc_chips.chips_for({'doc_type': 'ic'})
                except BaseException:               # a verdict path that hid it is still caught
                    pass

    def test_the_guard_is_off_again_afterwards(self):
        real = doc_chips.chips_for, doc_chips_student.chips_for, doc_chips_student.pill_for
        with chip_dry_run._chips_refused():
            pass
        self.assertEqual((doc_chips.chips_for, doc_chips_student.chips_for, doc_chips_student.pill_for), real)

    def test_superseded_rows_are_skipped_and_output_is_counts_only(self):
        ApplicantDocument.objects.filter(doc_type='photo').update(superseded_at=timezone.now())
        result = chip_dry_run.run_dry(allow_sqlite=True)
        self.assertNotIn('photo', result['per_type'])
        lines = chip_dry_run.render_counts(result).splitlines()
        self.assertRegex(lines[0], r'^applications \d+  bands_identical (True|False)  chip_fallbacks \d+$')
        for line in lines[1:]:
            self.assertRegex(line, r'^[a-z_]+\s+docs\s+\d+\s+chips\s+\d+\s+state_changed\s+\d+\s+'
                                   r'pill_changed\s+\d+\s+student_chips\s+\d+\s+'
                                   r'student_state_changed\s+\d+\s+student_pill_changed\s+\d+$')
