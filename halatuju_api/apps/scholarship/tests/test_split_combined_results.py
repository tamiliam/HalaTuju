"""`split_combined_results` — the team's one-time split of a combined results PDF, and its whole-document
move (2026-10-28). Synthetic fixtures only: a 3-page PDF built here (each page a different WIDTH,
so a part's pages can be told apart), Storage mocked, nothing read by Gemini or Vision.
"""
import io
import json
import os
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from pypdf import PdfReader, PdfWriter

from apps.scholarship import results_route
from apps.scholarship.management.commands import split_combined_results as cmd
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.tests.factories import make_cohort
from apps.scholarship.tests.test_third_route_s4 import DEGREE, POLY, SPM_HELD, STPM_HELD, _app

WIDTHS = (101, 202, 303)        # page 1, 2, 3


def _three_page_pdf():
    writer = PdfWriter()
    for w in WIDTHS:
        writer.add_blank_page(width=w, height=400)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _widths(data):
    return [round(float(p.mediabox.width)) for p in PdfReader(io.BytesIO(data)).pages]


class _Storage:
    """A fake bucket: the original's bytes, and every upload kept by path."""

    def __init__(self, original):
        self.original, self.uploads, self.deleted = original, {}, []

    def download(self, path):
        return self.original

    def upload(self, path, data, content_type):
        self.uploads[path] = (data, content_type)
        return True

    def delete(self, paths):
        self.deleted.extend(paths)
        return True


class SplitCase(TestCase):
    def setUp(self):
        self.cohort = make_cohort(min_stpm_pngk=2.0)      # D16c: this intake asks for STPM-level results
        self.bucket = _Storage(_three_page_pdf())
        for name, fake in (('download_object', self.bucket.download),
                           ('upload_object', self.bucket.upload),
                           ('delete_objects', self.bucket.delete)):
            patcher = patch(f'apps.scholarship.storage.{name}', side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _app(self, stage='shortlisted', plan=DEGREE, held=STPM_HELD, **kw):
        return _app(held, plan, stage=stage, cohort=self.cohort, **kw)

    def _combined(self, app, doc_type='results_slip', **kw):
        kw.setdefault('content_type', 'application/pdf')
        return ApplicantDocument.objects.create(
            application=app, doc_type=doc_type, storage_path=f'test/{doc_type}/orig',
            original_filename='results.pdf',
            vision_fields={'fields': {'exam': 'SPM'}, 'student_verdict': 'ok'}, **kw)

    def _run(self, plan, *args):
        buf = io.StringIO()
        call_command('split_combined_results', '--plan', json.dumps(plan), *args, stdout=buf)
        return buf.getvalue()

    @staticmethod
    def _split(app, doc, parts):
        return {'app': app.id, 'doc': doc.id, 'parts': parts}


class TestPreview(SplitCase):
    def test_preview_writes_nothing(self):
        app = self._app()
        doc = self._combined(app)
        before = ApplicantDocument.objects.count()
        out = self._run([self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'},
                                                {'pages': [2, 3], 'slot': 'higher_results', 'kind': 'stpm'}])])
        self.assertIn('PREVIEW', out)
        self.assertIn('pages 2-3 -> higher_results kind=stpm', out)
        self.assertIn('1 item(s) ready, 0 refused', out)
        self.assertEqual(ApplicantDocument.objects.count(), before)
        self.assertEqual(self.bucket.uploads, {})
        doc.refresh_from_db()
        self.assertIsNone(doc.superseded_at)
        self.assertFalse(ScholarshipApplication.objects.get(pk=app.pk).results_change_notes)

    def test_preview_prints_no_name_or_ic(self):
        app = self._app()
        doc = self._combined(app)
        out = self._run([{'app': app.id, 'doc': doc.id, 'to': 'higher_results', 'kind': 'stpm'}])
        self.assertNotIn('Priya', out)
        self.assertNotIn('030101', out)


class TestApplySplit(SplitCase):
    def test_parts_carry_the_right_pages_and_the_original_becomes_history(self):
        app = self._app()
        doc = self._combined(app)
        self._run([self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'},
                                          {'pages': [2, 3], 'slot': 'higher_results', 'kind': 'stpm'}])],
                  '--apply')
        slip = ApplicantDocument.objects.get(application=app, doc_type='results_slip',
                                             superseded_at__isnull=True)
        higher = ApplicantDocument.objects.get(application=app, doc_type='higher_results',
                                               superseded_at__isnull=True)
        self.assertEqual(_widths(self.bucket.uploads[slip.storage_path][0]), [101])
        self.assertEqual(_widths(self.bucket.uploads[higher.storage_path][0]), [202, 303])
        self.assertEqual(self.bucket.uploads[higher.storage_path][1], 'application/pdf')
        self.assertTrue(higher.storage_path.startswith(f'{app.owning_organisation_id}/{app.id}/higher_results/'))
        self.assertEqual((slip.original_filename, higher.original_filename),
                         ('results.pdf (page 1)', 'results.pdf (pages 2-3)'))
        self.assertEqual((higher.results_kind, slip.results_kind), ('stpm', ''))
        for part in (slip, higher):           # the state `refile_*` leaves: the live sweep reads it
            self.assertEqual(part.vision_fields, {})
            self.assertIsNone(part.vision_run_at)
            self.assertIsNone(part.vision_fields_run_at)
            self.assertEqual(part.content_type, 'application/pdf')
        doc.refresh_from_db()
        self.assertIsNotNone(doc.superseded_at)
        self.assertEqual(doc.superseded_by_id, slip.id)          # the part in its own card
        self.assertEqual(doc.vision_fields['fields'], {'exam': 'SPM'})   # history kept intact

    def test_one_team_note_per_part_with_the_unassigned_pages(self):
        app = self._app()
        doc = self._combined(app)
        self._run([self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'},
                                          {'pages': [2], 'slot': 'higher_results', 'kind': 'stpm'}])],
                  '--apply')
        notes = ScholarshipApplication.objects.get(pk=app.pk).results_change_notes
        self.assertEqual([n['kind'] for n in notes], ['team_split', 'team_split'])
        self.assertEqual({n['slot']: n['pages'] for n in notes},
                         {'results_slip': [1], 'higher_results': [2]})
        for n in notes:
            self.assertEqual((n['by'], n['from_document_id'], n['unassigned_pages']),
                             ('team', doc.id, [3]))
        live_ids = set(ApplicantDocument.objects.filter(
            application=app, superseded_at__isnull=True).values_list('id', flat=True))
        self.assertEqual({n['document_id'] for n in notes}, live_ids)

    def test_a_file_in_the_higher_card_splits_too(self):
        """#273's shape: the combined file sits in the higher card; the SPM page goes out of it."""
        app = self._app()
        doc = self._combined(app, doc_type='higher_results', results_kind='stpm')
        self._run([self._split(app, doc, [{'pages': [1, 2], 'slot': 'higher_results', 'kind': 'stpm'},
                                          {'pages': [3], 'slot': 'results_slip'}])], '--apply')
        doc.refresh_from_db()
        higher = ApplicantDocument.objects.get(application=app, doc_type='higher_results',
                                               superseded_at__isnull=True)
        self.assertEqual(doc.superseded_by_id, higher.id)
        self.assertEqual(_widths(self.bucket.uploads[higher.storage_path][0]), [101, 202])

    def test_an_occupied_target_card_refuses_the_whole_item(self):
        """Review fix 1: a part that lost a promotion contest would never be read — so no contest."""
        app = self._app()
        doc = self._combined(app)
        older = ApplicantDocument.objects.create(application=app, doc_type='higher_results',
                                                 results_kind='stpm', storage_path='test/old')
        plan = [self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'},
                                       {'pages': [2], 'slot': 'higher_results', 'kind': 'stpm'}])]
        self.assertIn(f'already holds live document(s) #{older.id}', self._run(plan))   # the preview names it
        out = self._run(plan, '--apply')
        self.assertIn('REFUSED', out)
        doc.refresh_from_db()
        older.refresh_from_db()
        self.assertIsNone(doc.superseded_at)
        self.assertIsNone(older.superseded_at)
        self.assertEqual(self.bucket.uploads, {})

    def test_every_part_becomes_its_cards_live_document(self):
        app = self._app()
        doc = self._combined(app)
        self._run([self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'},
                                          {'pages': [2, 3], 'slot': 'higher_results', 'kind': 'stpm'}])],
                  '--apply')
        live = ApplicantDocument.objects.filter(application=app, superseded_at__isnull=True)
        self.assertEqual(sorted(live.values_list('doc_type', flat=True)), ['higher_results', 'results_slip'])
        self.assertNotIn(doc.id, live.values_list('id', flat=True))

    def test_a_broken_pdf_refuses_that_item_only(self):
        app = self._app()
        doc = self._combined(app)
        good = self._app()
        good_doc = self._combined(good)
        self.bucket.original = b'%PDF-1.4 this is not really a pdf'
        out = self._run([self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'}]),
                         {'app': good.id, 'doc': good_doc.id, 'to': 'higher_results', 'kind': 'stpm'}],
                        '--apply')
        self.assertIn('could not be opened', out)
        self.assertIn('1 item(s) done, 1 refused', out)

    def test_an_upload_that_raises_midway_deletes_what_was_uploaded(self):
        app = self._app()
        doc = self._combined(app)
        calls = []

        def flaky(path, data, content_type):
            calls.append(path)
            if len(calls) == 2:
                raise TimeoutError('storage went away')
            return True
        with patch('apps.scholarship.storage.upload_object', side_effect=flaky):
            out = self._run([self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'},
                                                    {'pages': [2], 'slot': 'higher_results', 'kind': 'stpm'}])],
                            '--apply')
        self.assertIn('Storage upload failed (TimeoutError)', out)
        self.assertEqual(self.bucket.deleted, calls[:1])
        doc.refresh_from_db()
        self.assertIsNone(doc.superseded_at)
        self.assertEqual(ApplicantDocument.objects.filter(application=app).count(), 1)

    def test_running_the_same_plan_twice_creates_nothing_more(self):
        app = self._app()
        doc = self._combined(app)
        plan = [self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'},
                                       {'pages': [2], 'slot': 'higher_results', 'kind': 'stpm'}])]
        self._run(plan, '--apply')
        count, uploads = ApplicantDocument.objects.count(), len(self.bucket.uploads)
        out = self._run(plan, '--apply')
        self.assertIn('REFUSED', out)
        self.assertIn('not live', out)
        self.assertEqual((ApplicantDocument.objects.count(), len(self.bucket.uploads)), (count, uploads))
        self.assertEqual(len(ScholarshipApplication.objects.get(pk=app.pk).results_change_notes), 2)

    def test_a_failed_upload_writes_no_row(self):
        app = self._app()
        doc = self._combined(app)
        with patch('apps.scholarship.storage.upload_object', return_value=False):
            out = self._run([self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'}])], '--apply')
        self.assertIn('Storage upload failed', out)
        doc.refresh_from_db()
        self.assertIsNone(doc.superseded_at)
        self.assertEqual(ApplicantDocument.objects.filter(application=app).count(), 1)

    def test_the_plan_can_come_from_the_env_var(self):
        app = self._app()
        doc = self._combined(app)
        plan = json.dumps([self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'}])])
        buf = io.StringIO()
        with patch.dict(os.environ, {cmd.ENV_VAR: plan}):
            call_command('split_combined_results', stdout=buf)
        self.assertIn('1 item(s) ready', buf.getvalue())


class TestMoveByTheTeam(SplitCase):
    def test_a_move_into_an_occupied_card_is_refused(self):
        app = self._app()
        doc = self._combined(app)
        live = ApplicantDocument.objects.create(application=app, doc_type='higher_results',
                                                results_kind='stpm', storage_path='test/live')
        out = self._run([{'app': app.id, 'doc': doc.id, 'to': 'higher_results', 'kind': 'stpm'}], '--apply')
        self.assertIn(f'already holds live document(s) #{live.id}', out)
        doc.refresh_from_db()
        self.assertEqual(doc.doc_type, 'results_slip')

    def test_a_whole_document_moves_to_the_higher_card_noted_by_the_team(self):
        app = self._app()
        doc = self._combined(app)
        self._run([{'app': app.id, 'doc': doc.id, 'to': 'higher_results', 'kind': 'stpm'}], '--apply')
        doc.refresh_from_db()
        self.assertEqual((doc.doc_type, doc.results_kind, doc.vision_fields), ('higher_results', 'stpm', {}))
        self.assertIsNone(doc.superseded_at)
        note = ScholarshipApplication.objects.get(pk=app.pk).results_change_notes[-1]
        self.assertEqual((note['kind'], note['by'], note['from'], note['document_id']),
                         ('refiled_higher', 'team', 'results_slip', doc.id))
        self.assertEqual(self.bucket.uploads, {})        # a move uploads nothing

    def test_a_move_to_the_spm_card(self):
        app = self._app()
        doc = self._combined(app, doc_type='higher_results', results_kind='stpm')
        self._run([{'app': app.id, 'doc': doc.id, 'to': 'results_slip'}], '--apply')
        doc.refresh_from_db()
        self.assertEqual((doc.doc_type, doc.results_kind), ('results_slip', ''))
        note = ScholarshipApplication.objects.get(pk=app.pk).results_change_notes[-1]
        self.assertEqual((note['kind'], note['by']), ('refiled_spm', 'team'))

    def test_the_students_own_moves_are_unchanged(self):
        app = self._app()
        doc = self._combined(app)
        results_route.refile_to_higher(app, doc, 'stpm')
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.pk).results_change_notes[-1]['by'],
                         'student')
        back = self._combined(app, doc_type='higher_results')
        results_route.refile_to_spm(app, back)
        self.assertNotIn('by', ScholarshipApplication.objects.get(pk=app.pk).results_change_notes[-1])


class TestGuards(SplitCase):
    def _refusal(self, item):
        out = self._run([item], '--apply')
        self.assertIn('REFUSED', out)
        return out

    def test_each_guard_refuses_and_writes_nothing(self):
        app = self._app()
        other = self._app()
        doc = self._combined(app)
        slip = [{'pages': [1], 'slot': 'results_slip'}]
        cases = {
            'does not belong': {'app': other.id, 'doc': doc.id, 'parts': slip},
            'overlap': self._split(app, doc, [{'pages': [1, 2], 'slot': 'results_slip'},
                                              {'pages': [2], 'slot': 'higher_results', 'kind': 'stpm'}]),
            'not one of': self._split(app, doc, [{'pages': [1], 'slot': 'offer_letter'}]),
            'needs a kind': self._split(app, doc, [{'pages': [2], 'slot': 'higher_results', 'kind': 'ielts'}]),
            "needs a kind in ['asasi'": self._split(app, doc, [{'pages': [2], 'slot': 'higher_results'}]),
            'takes no kind': self._split(app, doc, [{'pages': [1], 'slot': 'results_slip', 'kind': 'stpm'}]),
            'do not exist': self._split(app, doc, [{'pages': [4], 'slot': 'results_slip'}]),
            'one live document per card': self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'},
                                                                 {'pages': [2], 'slot': 'results_slip'}]),
            'page numbers': self._split(app, doc, [{'pages': [0], 'slot': 'results_slip'}]),
            'already in': {'app': app.id, 'doc': doc.id, 'to': 'results_slip'},
            'either': {'app': app.id, 'doc': doc.id},
        }
        for reason, item in cases.items():
            with self.subTest(reason):
                self.assertIn(reason, self._refusal(item))
        self.assertEqual(ApplicantDocument.objects.filter(application=app).count(), 1)
        self.assertEqual(self.bucket.uploads, {})

    def test_an_image_is_never_split(self):
        app = self._app()
        doc = self._combined(app, content_type='image/jpeg')
        doc.original_filename = 'slip.jpg'
        doc.save(update_fields=['original_filename'])
        out = self._refusal(self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'}]))
        self.assertIn('not a PDF', out)

    def test_a_superseded_document_and_a_final_status_are_refused(self):
        app = self._app()
        doc = self._combined(app)
        newer = self._combined(app)
        ApplicantDocument.objects.filter(pk=doc.pk).update(superseded_at=newer.uploaded_at,
                                                           superseded_by=newer)
        self.assertIn('not live', self._refusal({'app': app.id, 'doc': doc.id, 'to': 'higher_results',
                                                 'kind': 'stpm'}))
        ScholarshipApplication.objects.filter(pk=app.pk).update(status='withdrawn')
        self.assertIn('final', self._refusal({'app': app.id, 'doc': newer.id, 'to': 'higher_results',
                                              'kind': 'stpm'}))

    def test_a_refused_item_does_not_stop_the_next(self):
        app = self._app()
        doc = self._combined(app)
        out = self._run([{'app': 999999, 'doc': doc.id, 'to': 'higher_results', 'kind': 'stpm'},
                         {'app': app.id, 'doc': doc.id, 'to': 'higher_results', 'kind': 'stpm'}], '--apply')
        self.assertIn('1 item(s) done, 1 refused', out)


class TestSubmittedSnapshot(SplitCase):
    def test_a_submitted_degree_bound_holder_requires_the_higher_card_after(self):
        app = self._app(stage='profile_complete')
        snap = ScholarshipApplication.objects.get(pk=app.pk).requirements_snapshot
        self.assertNotEqual(snap['documents'].get('higher_results'), 'required')   # a pre-S3 freeze
        doc = self._combined(app)
        out = self._run([self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'},
                                                {'pages': [2], 'slot': 'higher_results', 'kind': 'stpm'}])])
        self.assertIn('snapshot change: yes', out)
        self._run([self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'},
                                          {'pages': [2], 'slot': 'higher_results', 'kind': 'stpm'}])], '--apply')
        snap = ScholarshipApplication.objects.get(pk=app.pk).requirements_snapshot
        self.assertEqual((snap['documents']['higher_results'], snap['documents']['results_slip']),
                         ('required', 'optional'))
        self.assertEqual(snap['amended'][-1]['by'], 'team')
        self.assertTrue(ScholarshipApplication.objects.get(pk=app.pk).results_change_notes[0]['submitted'])

    def test_the_arm_taken_is_recorded(self):
        app = self._app(stage='profile_complete')
        doc = self._combined(app)
        self._run([{'app': app.id, 'doc': doc.id, 'to': 'higher_results', 'kind': 'stpm'}], '--apply')
        amended = ScholarshipApplication.objects.get(pk=app.pk).requirements_snapshot['amended'][-1]
        self.assertEqual(amended['arm'], 'required')

    def test_an_spm_only_record_never_gets_higher_results_required(self):
        """Review fix 2(c): `map_documents`' 'required_with_slip' arm is never applied by the team."""
        app = self._app(stage='profile_complete', held=SPM_HELD)
        before = ScholarshipApplication.objects.get(pk=app.pk).requirements_snapshot
        doc = self._combined(app)
        plan = [{'app': app.id, 'doc': doc.id, 'to': 'higher_results', 'kind': 'stpm'}]
        self.assertIn('snapshot change: no (recorded results are spm, not tertiary)', self._run(plan))
        self._run(plan, '--apply')
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.pk).requirements_snapshot, before)

    def test_a_move_out_of_a_required_higher_card_is_refused(self):
        frozen = {'captured_at': '2026-10-26T12:00:00+08:00', 'questions': {},
                  'documents': {'results_slip': 'optional', 'higher_results': 'required'}}
        app = self._app(stage='profile_complete', requirements_snapshot=frozen)
        doc = self._combined(app, doc_type='higher_results', results_kind='stpm')
        out = self._run([{'app': app.id, 'doc': doc.id, 'to': 'results_slip'}], '--apply')
        self.assertIn('makes required', out)
        doc.refresh_from_db()
        self.assertEqual(doc.doc_type, 'higher_results')

    def test_the_preview_reports_the_semester_ask(self):
        app = self._app()
        doc = self._combined(app)
        out = self._run([{'app': app.id, 'doc': doc.id, 'to': 'higher_results', 'kind': 'stpm'}])
        self.assertIn('semester_result_gap after: ', out)

    def test_a_post_spm_course_keeps_its_snapshot(self):
        app = self._app(stage='profile_complete', plan=POLY)
        before = ScholarshipApplication.objects.get(pk=app.pk).requirements_snapshot
        doc = self._combined(app)
        self._run([{'app': app.id, 'doc': doc.id, 'to': 'higher_results', 'kind': 'stpm'}], '--apply')
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.pk).requirements_snapshot, before)

    def test_not_submitted_means_no_snapshot(self):
        app = self._app()
        doc = self._combined(app)
        self._run([{'app': app.id, 'doc': doc.id, 'to': 'higher_results', 'kind': 'stpm'}], '--apply')
        self.assertIsNone(ScholarshipApplication.objects.get(pk=app.pk).requirements_snapshot)
