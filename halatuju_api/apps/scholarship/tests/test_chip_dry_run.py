"""The chip dry run, on the TEST database only (never a live one): counts, read-only, bands identical."""
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.scholarship import doc_chips
from apps.scholarship.eval import chip_dry_run
from apps.scholarship.eval import offer_s4_dry_run as dr
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import create_document, make_application


class ChipDryRunTests(TestCase):
    def setUp(self):
        self.app = make_application()
        create_document(self.app, 'ic', storage_path='s')
        create_document(self.app, 'photo', storage_path='s')

    def test_sprint_0_changes_no_chip_and_no_band(self):
        result = chip_dry_run.run_dry(allow_sqlite=True)
        self.assertEqual(result['applications'], 1)
        self.assertTrue(result['bands_identical'])
        self.assertEqual(result['per_type']['ic'], {'docs': 1, 'chips': 2, 'state_changed': 0,
                                                    'pill_changed': 0, 'student_differs': 0})
        self.assertEqual(result['per_type']['photo']['docs'], 1)

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
        with self.assertRaises(chip_dry_run.ChipsRefused):
            with chip_dry_run._chips_refused():
                doc_chips.pill_for([])

    def test_the_guard_trips_even_when_the_caller_swallows_the_raise(self):
        with self.assertRaises(chip_dry_run.ChipsRefused):
            with chip_dry_run._chips_refused():
                try:
                    doc_chips.chips_for({'doc_type': 'ic'})
                except BaseException:               # a verdict path that hid it is still caught
                    pass

    def test_the_guard_is_off_again_afterwards(self):
        real = doc_chips.chips_for
        with chip_dry_run._chips_refused():
            pass
        self.assertIs(doc_chips.chips_for, real)

    def test_superseded_rows_are_skipped_and_output_is_counts_only(self):
        ApplicantDocument.objects.filter(doc_type='photo').update(superseded_at=timezone.now())
        result = chip_dry_run.run_dry(allow_sqlite=True)
        self.assertNotIn('photo', result['per_type'])
        lines = chip_dry_run.render_counts(result).splitlines()
        self.assertRegex(lines[0], r'^applications \d+  bands_identical (True|False)$')   # no ids, no names
        for line in lines[1:]:
            self.assertRegex(line, r'^[a-z_]+\s+docs\s+\d+\s+chips\s+\d+\s+state_changed\s+\d+\s+'
                                   r'pill_changed\s+\d+\s+student_differs\s+\d+$')
