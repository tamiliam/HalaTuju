"""TD-741: `reread_academic_ocr` — the OCR-only backfill of the slip school (display only) and the
transcript year.

Synthetic words and text only (fictional names). Storage and Vision are mocked; Gemini is patched to fail
the test if it is ever reached."""
import copy
import json
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.academic_compare import SLIP_SCHOOL_READ, slip_school
from apps.scholarship.academic_engine import parse_spm_slip, student_slip_check
from apps.scholarship.management.commands import reread_academic_ocr as cmd
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.serializers.documents import ApplicantDocumentSerializer
from apps.scholarship.tests.factories import create_document, make_application, make_student
from apps.scholarship.tests.test_academic_engine import _slip_words

SCHOOL = 'SMK CONTOH REKAAN'
NAME = 'CALON CONTOH BINTI REKAAN'
SPM_ROWS = [('BAHASA MELAYU', 'A-', 'CEMERLANG'), ('BAHASA INGGERIS', 'C+', 'KEPUJIAN ATAS'),
            ('SEJARAH', 'B', 'KEPUJIAN TINGGI'), ('MATEMATIK', 'A-', 'CEMERLANG'),
            ('SAINS', 'B+', 'KEPUJIAN TERTINGGI')]
SLIP_WORDS = _slip_words([('SIJIL PELAJARAN MALAYSIA', 200), (NAME, 250), (f'SEKOLAH : {SCHOOL}', 300)], SPM_ROWS)
SLIP_TEXT = ' '.join(w['text'] for w in SLIP_WORDS)
MATRIC_TEXT = f'{NAME}\nKOLEJ MATRIKULASI CONTOH\nSESI / SESSION : 2024/2025\nPNGK 3.85'

#: Review round 1 fixture: the slip PRINTS nine subjects ("JUMLAH MATA PELAJARAN : SEMBILAN"); the old
#: Gemini read kept eight, the same eight the student typed. Writing the page's rows would make the
#: printed count 9 and turn this read "short".
NINE = [('BAHASA MELAYU', 'A-', 'CEMERLANG'), ('BAHASA INGGERIS', 'C+', 'KEPUJIAN ATAS'),
        ('PENDIDIKAN MORAL', 'A+', 'CEMERLANG TERTINGGI'), ('SEJARAH', 'B', 'KEPUJIAN TINGGI'),
        ('MATEMATIK', 'A-', 'CEMERLANG'), ('SAINS', 'B+', 'KEPUJIAN TERTINGGI'),
        ('PERTANIAN', 'A', 'CEMERLANG TINGGI'), ('PERNIAGAAN', 'B', 'KEPUJIAN TINGGI'),
        ('BAHASA TAMIL', 'A-', 'CEMERLANG')]
NINE_WORDS = _slip_words([('SIJIL PELAJARAN MALAYSIA', 200), (NAME, 250), (f'SEKOLAH : {SCHOOL}', 300),
                          ('JUMLAH MATA PELAJARAN : SEMBILAN', 900)], NINE)
EIGHT_READ = [{'subject': 'Bahasa Melayu', 'grade': 'A-'}, {'subject': 'Bahasa Inggeris', 'grade': 'C+'},
              {'subject': 'Pendidikan Moral', 'grade': 'A+'}, {'subject': 'Sejarah', 'grade': 'B'},
              {'subject': 'Matematik', 'grade': 'A-'}, {'subject': 'Sains', 'grade': 'B+'},
              {'subject': 'Pertanian', 'grade': 'A'}, {'subject': 'Perniagaan', 'grade': 'B'}]
EIGHT_TYPED = {'bm': 'A-', 'eng': 'C+', 'moral': 'A+', 'hist': 'B', 'math': 'A-', 'sci': 'B+',
               'pertanian': 'A', 'business': 'B'}

FETCH = 'apps.scholarship.vision._fetch_image_bytes'
WORDS = 'apps.scholarship.vision._vision_words'
GEMINI = 'apps.scholarship.vision.extract_document_fields'
IS_PDF = 'apps.scholarship.vision._is_pdf'
PDF_LAYER = 'apps.scholarship.vision._pdf_text_layer'
PAGE1 = 'apps.scholarship.offer_exact.pdf_layers'
CERT = 'apps.scholarship.spm_cert_parse.parse_spm_cert'
HELD = 'apps.courses.public.results_held'


def _ok(words=SLIP_WORDS, text=SLIP_TEXT):
    return {'words': words, 'text': text, 'error': None}


def _canon(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)


class RereadAcademicOcr(TestCase):
    def setUp(self):
        self.app = make_application('shortlisted', student=make_student(name='Calon', nric='030101-14-1234'))
        gemini = mock.patch(GEMINI, side_effect=AssertionError('Gemini must never be called'))
        gemini.start()
        self.addCleanup(gemini.stop)

    def _slip(self, top=None, **fields):
        vf = {'fields': {'candidate_name': NAME, 'exam': 'SIJIL PELAJARAN MALAYSIA TAHUN 2024',
                         'results': [{'subject': 'Sejarah', 'grade': 'B'}], **fields},
              'student_verdict': 'ok', 'capture': 'ai', 'warnings': ['w'], 'error': '',
              'authenticity': {'status': 'genuine', 'score': 0.91}, **(top or {})}
        return create_document(application=self.app, doc_type='results_slip', storage_path='t/slip',
                               content_type='image/jpeg', vision_fields=vf, vision_fields_run_at=timezone.now())

    def _higher(self, kind='matric', detected=None, **extra):
        vf = {'fields': {'candidate_name': NAME, 'exam': 'KEPUTUSAN PEPERIKSAAN', 'cgpa': '3.85',
                         'results_kind_detected': kind if detected is None else detected},
              'student_verdict': 'ok', 'capture': 'ai', 'error': '', 'authenticity': {'status': 'genuine'}, **extra}
        return create_document(application=self.app, doc_type='higher_results', results_kind=kind,
                               storage_path='t/higher', content_type='image/jpeg', vision_fields=vf,
                               vision_fields_run_at=timezone.now())

    def _run(self, *args):
        out, err = StringIO(), StringIO()
        call_command('reread_academic_ocr', *args, stdout=out, stderr=err)
        return out.getvalue() + err.getvalue()

    def _vf(self, doc):
        return ApplicantDocument.objects.get(pk=doc.pk).vision_fields

    # ── dry run ──
    def test_dry_run_reads_nothing_and_writes_nothing(self):
        slip, higher = self._slip(), self._higher()
        before = (copy.deepcopy(slip.vision_fields), copy.deepcopy(higher.vision_fields))
        with mock.patch(FETCH) as fetch, mock.patch(WORDS) as words:
            out = self._run()
        fetch.assert_not_called()
        words.assert_not_called()
        self.assertEqual((self._vf(slip), self._vf(higher)), before)
        self.assertIn('slip_school: fresh=1 known_skip=0 already_filled=0', out)
        self.assertIn('transcript_year: fresh=1 known_skip=0 already_filled=0', out)
        self.assertIn('DRY RUN', out)
        self.assertIn('would_read=2 est_cost_usd=0.0030 cap_usd=2.0000', out)

    def test_dry_run_reports_known_skips_apart_from_fresh_targets(self):
        self._slip()                                                       # fresh
        self._slip(_debug_rows=['BAHASA MELAYU A'])                         # page kept, no school
        self._slip(exam='PEPERIKSAAN PERCUBAAN SPM 2024')                   # a trial: not SPM results
        self._slip(exam='SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2024')          # a higher result in the slot
        create_document(application=self.app, doc_type='results_slip', storage_path='t/c',
                        vision_fields={'fields': {'candidate_name': NAME, 'nric': '030101141234',
                                                  'exam': 'SIJIL PELAJARAN MALAYSIA TAHUN 2024',
                                                  'results': [{'subject': 'Sejarah', 'grade': 'B'}]},
                                       'student_verdict': 'ok', 'capture': 'deterministic', 'error': ''})
        with mock.patch(FETCH) as fetch:
            out = self._run()
        fetch.assert_not_called()
        self.assertIn('slip_school: fresh=1 known_skip=4 already_filled=0', out)
        for why in ('certificate', 'higher_kind', 'not_spm_exam', 'stored_no_school'):
            self.assertIn(f'slip_school known_skip {why}=1', out)
        self.assertIn('would_read=1 ', out)

    # ── apply: one key, nothing else ──
    def test_apply_stores_only_the_school_string_beside_the_read(self):
        slip = self._slip()
        run_at = ApplicantDocument.objects.get(pk=slip.pk).vision_fields_run_at
        before = copy.deepcopy(slip.vision_fields)
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply')
        after = self._vf(slip)
        self.assertEqual(after.pop(SLIP_SCHOOL_READ), SCHOOL)
        self.assertEqual(after, before)                              # every other key identical
        self.assertNotIn('_debug_rows', after['fields'])             # the rows are never written
        doc = ApplicantDocument.objects.get(pk=slip.pk)
        self.assertEqual(ApplicantDocumentSerializer._slip_school(doc)['school'], SCHOOL)  # the tick reads it
        self.assertEqual(doc.vision_fields_run_at, run_at)
        self.assertIn(f'slip_school: written=1 ids=[{slip.pk}]', out)

    def test_apply_writes_only_the_transcript_year(self):
        higher = self._higher()
        before = copy.deepcopy(higher.vision_fields)
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok(None, MATRIC_TEXT)):
            out = self._run('--apply')
        after = self._vf(higher)
        read = after.pop('exam_year_read')
        self.assertEqual(after, before)
        self.assertEqual((read['year'], read['label']), ('2025', 'session'))
        self.assertIn(f'transcript_year: written=1 ids=[{higher.pk}]', out)

    # ── review round 1 blocker: no verdict input moves ──
    def test_a_short_gemini_read_keeps_its_slip_check_and_academic_fact(self):
        from apps.scholarship.verdict_engine import _verdict_academic
        profile = self.app.profile
        profile.grades, profile.school = EIGHT_TYPED, SCHOOL
        profile.save()
        slip = self._slip(results=EIGHT_READ)
        def fresh():
            return ApplicantDocument.objects.select_related('application__profile').get(pk=slip.pk)
        check_before, fact_before = _canon(student_slip_check(fresh())), _canon(_verdict_academic(self.app))
        # The fixture has teeth: the page's rows WOULD change the check (printed count 9, the read short).
        teeth = fresh()
        teeth.vision_fields['fields']['_debug_rows'] = parse_spm_slip(NINE_WORDS)['_debug_rows']
        self.assertNotEqual(_canon(student_slip_check(teeth)), check_before)
        with mock.patch(FETCH, return_value=b'img'), \
                mock.patch(WORDS, return_value=_ok(NINE_WORDS, ' '.join(w['text'] for w in NINE_WORDS))):
            out = self._run('--apply')
        self.assertIn(f'slip_school: written=1 ids=[{slip.pk}]', out)
        self.assertEqual(self._vf(slip)[SLIP_SCHOOL_READ], SCHOOL)
        self.assertEqual(_canon(student_slip_check(fresh())), check_before)
        self.assertEqual(_canon(_verdict_academic(self.app)), fact_before)

    # ── review round 2: whole-verdict proofs ──
    def _verdict_state(self):
        from apps.scholarship import services
        from apps.scholarship.verdict_engine import build_verdict
        return _canon([build_verdict(self.app), services.document_red_blockers(self.app, per_doc=True),
                       services.document_unreadable_blockers(self.app, per_doc=True)])

    def test_a_slip_backfill_leaves_the_whole_verdict_byte_identical(self):
        profile = self.app.profile
        profile.grades, profile.school = EIGHT_TYPED, SCHOOL
        profile.save()
        slip = self._slip(results=EIGHT_READ)
        before = self._verdict_state()
        with mock.patch(FETCH, return_value=b'img'), \
                mock.patch(WORDS, return_value=_ok(NINE_WORDS, ' '.join(w['text'] for w in NINE_WORDS))):
            self._run('--apply')
        self.assertEqual(self._vf(slip)[SLIP_SCHOOL_READ], SCHOOL)
        self.assertEqual(self._verdict_state(), before)

    def test_a_higher_backfill_moves_only_the_year_label(self):
        from apps.scholarship.higher_results import match_verdict, student_higher_check

        def doc():
            return ApplicantDocument.objects.select_related('application__profile').get(pk=higher.pk)
        higher = self._higher()
        before, check, match = self._verdict_state(), student_higher_check(doc()), match_verdict(doc())
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok(None, MATRIC_TEXT)):
            self._run('--apply')
        self.assertEqual(self._vf(higher)['exam_year_read']['year'], '2025')
        self.assertEqual(self._verdict_state(), before)
        self.assertEqual(match_verdict(doc()), match)
        after = student_higher_check(doc())
        moved = {k for k in set(check) | set(after) if check.get(k) != after.get(k)}
        self.assertTrue(moved)                                   # the year label does show
        self.assertLessEqual(moved, {'exam_year', 'exam_year_status'})

    # ── review round 2: decided cases and the old profile-driven gate record ──
    def test_a_decided_application_is_skipped_unless_opted_in(self):
        slip = self._slip()
        self.app.ai_verdict_context = {'schema': 1, 'fingerprint': 'f'}
        self.app.save(update_fields=['ai_verdict_context'])
        with mock.patch(FETCH) as fetch:
            out = self._run('--apply')
        fetch.assert_not_called()
        self.assertIn('slip_school: fresh=0 known_skip=1 already_filled=0', out)
        self.assertIn('slip_school known_skip decided_record=1', out)
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply', '--include-decided')
        self.assertIn(f'slip_school: written=1 ids=[{slip.pk}]', out)

    def test_an_empty_decision_context_is_not_decided(self):
        self._slip()
        self.app.ai_verdict_context = {}
        self.app.save(update_fields=['ai_verdict_context'])
        self.assertIn('slip_school: fresh=1 known_skip=0', self._run())

    def test_the_old_profile_driven_not_spm_record_is_read(self):
        old = self._slip(_slip_ocr_diag={'reason': 'not_spm_exam', 'exam_type': 'stpm'})   # pre-071fbaa9a shape
        self._slip(_slip_ocr_diag={'reason': 'not_spm_exam', 'exam_type': 'stpm', 'by': 'document'})
        out = self._run()
        self.assertIn('slip_school: fresh=1 known_skip=1 already_filled=0', out)
        self.assertIn('slip_school known_skip not_spm_exam=1', out)
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply')
        self.assertIn(f'slip_school: written=1 ids=[{old.pk}]', out)

    # ── safety: a failed read never writes ──
    def test_blob_missing_empty_ocr_and_ocr_error_are_skipped_untouched(self):
        cases = (('blob_missing', None, _ok()), ('ocr_empty', b'img', _ok([], '  ')),
                 ('ocr_error', b'img', {'words': [], 'text': '', 'error': 'quota'}))
        for why, blob, read in cases:
            with self.subTest(why=why):
                ApplicantDocument.objects.all().delete()
                slip, higher = self._slip(), self._higher()
                before = (copy.deepcopy(slip.vision_fields), copy.deepcopy(higher.vision_fields))
                with mock.patch(FETCH, return_value=blob), mock.patch(WORDS, return_value=read):
                    out = self._run('--apply')
                self.assertEqual((self._vf(slip), self._vf(higher)), before)
                self.assertIn(f'skipped {why}=2', out)
                self.assertIn('APPLIED: written=0 skipped=2', out)

    def test_a_page_with_no_year_and_a_slip_that_does_not_lock_are_skipped(self):
        slip, higher = self._slip(), self._higher()
        before = (copy.deepcopy(slip.vision_fields), copy.deepcopy(higher.vision_fields))
        few = _slip_words([('SIJIL PELAJARAN MALAYSIA', 200)], SPM_ROWS[:2])
        with mock.patch(FETCH, return_value=b'img'), \
                mock.patch(WORDS, return_value=_ok(few, 'NO SESSION PRINTED 2025')):
            out = self._run('--apply')
        self.assertEqual((self._vf(slip), self._vf(higher)), before)
        self.assertIn('skipped no_year=1', out)
        self.assertIn('skipped parse_none=1', out)

    def test_a_slip_without_a_school_row_is_skipped(self):
        slip = self._slip()
        before = copy.deepcopy(slip.vision_fields)
        bare = _slip_words([('SIJIL PELAJARAN MALAYSIA', 200), (NAME, 250)], SPM_ROWS)
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok(bare, 'x')):
            out = self._run('--apply')
        self.assertEqual(self._vf(slip), before)
        self.assertIn('skipped no_school=1', out)

    def test_a_certificate_page_is_skipped(self):
        slip = self._slip()
        before = copy.deepcopy(slip.vision_fields)
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok()), \
                mock.patch(CERT, return_value={'results': [{'subject': 'Sejarah', 'grade': 'B'}]}):
            out = self._run('--apply')
        self.assertEqual(self._vf(slip), before)
        self.assertIn('skipped certificate=1', out)

    def test_a_non_spm_page_in_the_slip_slot_is_skipped(self):
        slip = self._slip()
        before = copy.deepcopy(slip.vision_fields)
        stpm = _slip_words([('SIJIL TINGGI PERSEKOLAHAN MALAYSIA', 200), (f'SEKOLAH : {SCHOOL}', 300)], SPM_ROWS)
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok(stpm, 'x')):
            out = self._run('--apply')
        self.assertEqual(self._vf(slip), before)
        self.assertIn('skipped not_spm_exam=1', out)

    def test_an_exception_is_a_skip(self):
        slip = self._slip()
        before = copy.deepcopy(slip.vision_fields)
        with mock.patch(FETCH, side_effect=RuntimeError('boom')):
            out = self._run('--apply')
        self.assertEqual(self._vf(slip), before)
        self.assertIn('skipped error_RuntimeError=1', out)

    def test_a_db_error_on_the_write_still_prints_the_summary(self):
        a, b = self._slip(), self._slip()
        real = cmd._acad_write
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok()), \
                mock.patch.object(cmd, '_acad_write',
                                  side_effect=lambda d, k, v: (_ for _ in ()).throw(DatabaseError('x'))
                                  if d.pk == a.pk else real(d, k, v)):
            out = self._run('--apply')
        self.assertIn(f'skipped write_error_DatabaseError=1 ids=[{a.pk}]', out)
        self.assertIn(f'slip_school: written=1 ids=[{b.pk}]', out)
        self.assertIn('APPLIED: written=1 skipped=1', out)

    def test_the_equality_check_refuses_a_row_changed_since_it_was_classified(self):
        slip = self._slip()
        fresh = {**copy.deepcopy(slip.vision_fields), 'capture': 'deterministic'}

        def _reread_meanwhile(*a, **kw):
            ApplicantDocument.objects.filter(pk=slip.pk).update(vision_fields=fresh)
            return b'img'
        with mock.patch(FETCH, side_effect=_reread_meanwhile), mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply')
        self.assertEqual(self._vf(slip), fresh)
        self.assertIn('skipped changed=1', out)

    # ── the digital-PDF path ──
    def test_a_digital_pdf_transcript_is_read_from_its_text_layer_for_free(self):
        higher = self._higher()
        with mock.patch(FETCH, return_value=b'%PDF'), mock.patch(IS_PDF, return_value=True), \
                mock.patch(PDF_LAYER, return_value=MATRIC_TEXT), mock.patch(WORDS) as words:
            out = self._run('--apply')
        words.assert_not_called()
        self.assertEqual(self._vf(higher)['exam_year_read']['year'], '2025')
        self.assertIn('APPLIED: written=1 skipped=0 spend_usd=0.0000', out)

    def test_a_digital_pdf_slip_still_counts_its_one_word_box_page(self):
        slip = self._slip()
        with mock.patch(FETCH, return_value=b'%PDF'), mock.patch(IS_PDF, return_value=True), \
                mock.patch(PDF_LAYER, return_value=SLIP_TEXT), mock.patch(PAGE1, return_value=(SLIP_TEXT, SLIP_TEXT)), \
                mock.patch(WORDS, return_value=_ok()) as words:
            out = self._run('--apply')
        self.assertEqual(words.call_count, 1)                    # the slip read buys its word boxes
        self.assertEqual(self._vf(slip)[SLIP_SCHOOL_READ], SCHOOL)
        self.assertIn('APPLIED: written=1 skipped=0 spend_usd=0.0015', out)

    # ── higher documents: the held kind against the detected kind ──
    def test_held_kind_against_detected_kind(self):
        with mock.patch(HELD, return_value='diploma'):
            same = self._higher(kind='diploma')                    # detected = held: fresh
            undetected = self._higher(kind='matric', detected='')  # no detection: the held kind serves
            other = self._higher(kind='matric')                    # detected matric, held diploma
            states = {d.pk: cmd._acad_reread_kind(ApplicantDocument.objects.select_related(
                'application__profile').get(pk=d.pk)) for d in (same, undetected, other)}
            out = self._run()
        self.assertEqual(states[same.pk], (cmd.HIGHER, cmd.FRESH))
        self.assertEqual(states[undetected.pk], (cmd.HIGHER, cmd.FRESH))
        self.assertEqual(states[other.pk], (cmd.HIGHER, 'kind_mismatch'))
        self.assertIn('transcript_year: fresh=2 known_skip=1 already_filled=0', out)
        with mock.patch(HELD, return_value='spm'):                 # not tertiary: the doc's own kind holds
            self.assertEqual(cmd._acad_reread_kind(other), (cmd.HIGHER, cmd.FRESH))

    # ── idempotent: already filled and out-of-scope documents are not read ──
    def test_filled_and_out_of_scope_documents_are_never_read(self):
        self._slip(_debug_rows=['SEKOLAH : X'])
        self._slip(top={SLIP_SCHOOL_READ: 'SMK Y'})
        self._higher(exam_year_read={'year': '2025', 'label': 'session', 'reader': 'r'})
        self._higher(kind='stpm')
        create_document(application=self.app, doc_type='results_slip', storage_path='t/u',
                        vision_fields={'fields': {}, 'student_verdict': 'unreadable', 'error': 'x'})
        with mock.patch(FETCH) as fetch:
            out = self._run('--apply')
        fetch.assert_not_called()
        self.assertIn('slip_school: fresh=0 known_skip=0 already_filled=2', out)
        self.assertIn('transcript_year: fresh=0 known_skip=0 already_filled=1', out)

    def test_a_second_run_finds_nothing_left(self):
        self._slip()
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok()):
            self._run('--apply')
        with mock.patch(FETCH) as fetch:
            out = self._run('--apply')
        fetch.assert_not_called()
        self.assertIn('slip_school: fresh=0 known_skip=0 already_filled=1', out)

    # ── limits and resuming ──
    def test_limit_reads_at_most_n(self):
        for _ in range(3):
            self._slip()
        with mock.patch(FETCH, return_value=b'img') as fetch, mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply', '--limit', '1')
        self.assertEqual(fetch.call_count, 1)
        self.assertIn('APPLIED: written=1 skipped=0', out)

    def test_the_cost_cap_stops_before_it_is_passed(self):
        docs = [self._slip() for _ in range(3)]
        self.assertIn('would_read=2 est_cost_usd=0.0030 cap_usd=0.0030', self._run('--max-cost-usd', '0.003'))
        with mock.patch(FETCH, return_value=b'img') as fetch, mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply', '--max-cost-usd', '0.003')
        self.assertEqual(fetch.call_count, 2)
        self.assertIn('spend_usd=0.0030', out)
        self.assertIn(f'STOPPED at the cost cap (US$0.0030); run again with --after-id {docs[1].pk}', out)
        self.assertIn(f'resume_after_id={docs[1].pk}', out)

    def test_after_id_resumes_past_a_skipped_document(self):
        stuck, new = self._slip(), self._slip()
        few = _slip_words([('SIJIL PELAJARAN MALAYSIA', 200)], SPM_ROWS[:2])
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok(few, 'x')):
            first = self._run('--apply', '--limit', '1')
        self.assertIn(f'skipped parse_none=1 ids=[{stuck.pk}]', first)
        self.assertIn(f'resume_after_id={stuck.pk}', first)
        with mock.patch(FETCH, return_value=b'img') as fetch, mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply', '--after-id', str(stuck.pk))
        self.assertEqual(fetch.call_count, 1)
        self.assertIn(f'slip_school: written=1 ids=[{new.pk}]', out)
        self.assertIn(f'resume_after_id={new.pk}', out)

    def test_ids_restricts_the_run(self):
        a, b = self._slip(), self._slip()
        with mock.patch(FETCH, return_value=b'img') as fetch, mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply', '--ids', str(b.pk))
        self.assertEqual(fetch.call_count, 1)
        self.assertIn(f'ids=[{b.pk}]', out)
        self.assertNotIn(SLIP_SCHOOL_READ, self._vf(a))

    # ── no PII ──
    def test_output_carries_no_name_school_or_text(self):
        self._slip(), self._higher()
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, side_effect=[_ok(), _ok(None, MATRIC_TEXT)]):
            out = self._run('--apply') + self._run()
        for secret in (NAME, 'CALON', SCHOOL, 'REKAAN', 'KOLEJ', '030101', 'SESI', 'BAHASA'):
            self.assertNotIn(secret, out.upper())
        self.assertEqual(slip_school({}, {SLIP_SCHOOL_READ: SCHOOL}), SCHOOL)
