"""TD-741: `reread_academic_ocr` — the OCR-only backfill of the slip school rows and the transcript year.

Synthetic words and text only (fictional names). Storage and Vision are mocked; Gemini is patched to fail
the test if it is ever reached."""
import copy
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.academic_compare import slip_school
from apps.scholarship.management.commands import reread_academic_ocr as cmd
from apps.scholarship.models import ApplicantDocument
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

FETCH = 'apps.scholarship.vision._fetch_image_bytes'
WORDS = 'apps.scholarship.vision._vision_words'
GEMINI = 'apps.scholarship.vision.extract_document_fields'


def _ok(words=SLIP_WORDS, text=SLIP_TEXT):
    return {'words': words, 'text': text, 'error': None}


class RereadAcademicOcr(TestCase):
    def setUp(self):
        self.app = make_application('shortlisted', student=make_student(name='Calon', nric='030101-14-1234'))
        gemini = mock.patch(GEMINI, side_effect=AssertionError('Gemini must never be called'))
        gemini.start()
        self.addCleanup(gemini.stop)

    def _slip(self, **fields):
        vf = {'fields': {'candidate_name': NAME, 'exam': 'SIJIL PELAJARAN MALAYSIA TAHUN 2024',
                         'results': [{'subject': 'Sejarah', 'grade': 'B'}], **fields},
              'student_verdict': 'ok', 'capture': 'ai', 'warnings': ['w'], 'error': '',
              'authenticity': {'status': 'genuine', 'score': 0.91}}
        return create_document(application=self.app, doc_type='results_slip', storage_path='t/slip',
                               content_type='image/jpeg', vision_fields=vf, vision_fields_run_at=timezone.now())

    def _higher(self, kind='matric', **extra):
        vf = {'fields': {'candidate_name': NAME, 'exam': 'KEPUTUSAN PEPERIKSAAN', 'cgpa': '3.85',
                         'results_kind_detected': kind},
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
        self.assertIn('slip_school: targets=1 already_filled=0', out)
        self.assertIn('transcript_year: targets=1 already_filled=0', out)
        self.assertIn('DRY RUN', out)
        self.assertIn('would_read=2 est_cost_usd=0.0030', out)

    # ── apply: one key, nothing else ──
    def test_apply_writes_only_the_slip_rows(self):
        slip = self._slip()
        run_at = ApplicantDocument.objects.get(pk=slip.pk).vision_fields_run_at
        before = copy.deepcopy(slip.vision_fields)
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply')
        after = self._vf(slip)
        rows = after['fields'].pop('_debug_rows')
        self.assertEqual(after, before)                              # every other key identical
        self.assertEqual(slip_school({'_debug_rows': rows}), SCHOOL)  # the school now reads
        self.assertEqual(ApplicantDocument.objects.get(pk=slip.pk).vision_fields_run_at, run_at)
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

    def test_a_concurrent_re_read_wins(self):
        slip = self._slip()
        fresh = {**copy.deepcopy(slip.vision_fields), 'capture': 'deterministic'}

        def _reread_meanwhile(*a, **kw):
            ApplicantDocument.objects.filter(pk=slip.pk).update(vision_fields=fresh)
            return b'img'
        with mock.patch(FETCH, side_effect=_reread_meanwhile), mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply')
        self.assertEqual(self._vf(slip), fresh)
        self.assertIn('skipped changed=1', out)

    # ── idempotent: already filled and out-of-scope documents are not read ──
    def test_filled_and_out_of_scope_documents_are_never_read(self):
        self._slip(_debug_rows=['SEKOLAH : X'])
        self._slip(_slip_ocr_diag={'reason': 'parse_none', 'capture': [{'text': 'SEKOLAH'}]})
        self._higher(exam_year_read={'year': '2025', 'label': 'session', 'reader': 'r'})
        self._higher(kind='stpm')
        create_document(application=self.app, doc_type='results_slip', storage_path='t/u',
                        vision_fields={'fields': {}, 'student_verdict': 'unreadable', 'error': 'x'})
        with mock.patch(FETCH) as fetch:
            out = self._run('--apply')
        fetch.assert_not_called()
        self.assertIn('slip_school: targets=0 already_filled=2', out)
        self.assertIn('transcript_year: targets=0 already_filled=1', out)

    def test_a_second_run_finds_nothing_left(self):
        self._slip()
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, return_value=_ok()):
            self._run('--apply')
        with mock.patch(FETCH) as fetch:
            out = self._run('--apply')
        fetch.assert_not_called()
        self.assertIn('slip_school: targets=0 already_filled=1', out)

    # ── limits ──
    def test_limit_reads_at_most_n(self):
        for _ in range(3):
            self._slip()
        with mock.patch(FETCH, return_value=b'img') as fetch, mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply', '--limit', '1')
        self.assertEqual(fetch.call_count, 1)
        self.assertIn('APPLIED: written=1 skipped=0', out)

    def test_the_cost_cap_stops_before_it_is_passed(self):
        for _ in range(3):
            self._slip()
        self.assertIn('would_read=2 est_cost_usd=0.0030 cap_usd=0.00', self._run('--max-cost-usd', '0.003'))
        with mock.patch(FETCH, return_value=b'img') as fetch, mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply', '--max-cost-usd', '0.003')
        self.assertEqual(fetch.call_count, 2)
        self.assertIn('spend_usd=0.0030', out)
        self.assertIn('STOPPED at the cost cap', out)

    def test_ids_restricts_the_run(self):
        a, b = self._slip(), self._slip()
        with mock.patch(FETCH, return_value=b'img') as fetch, mock.patch(WORDS, return_value=_ok()):
            out = self._run('--apply', '--ids', str(b.pk))
        self.assertEqual(fetch.call_count, 1)
        self.assertIn(f'ids=[{b.pk}]', out)
        self.assertNotIn('_debug_rows', self._vf(a)['fields'])

    # ── no PII ──
    def test_output_carries_no_name_school_or_text(self):
        self._slip(), self._higher()
        with mock.patch(FETCH, return_value=b'img'), mock.patch(WORDS, side_effect=[_ok(), _ok(None, MATRIC_TEXT)]):
            out = self._run('--apply') + self._run()
        for secret in (NAME, 'CALON', SCHOOL, 'REKAAN', 'KOLEJ', '030101', 'SESI', 'BAHASA'):
            self.assertNotIn(secret, out.upper())
        self.assertTrue(cmd.VISION_PAGE_USD > 0)
