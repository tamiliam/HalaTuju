"""Gemini Phase 2 Option A (owner, 2026-11-14) — 3.8 Flash first, with the owner's exceptions.

Every Flash job moves to gemini-3.8-flash first, 2.5 Flash as its fallback. Two exceptions stay on
2.5 Flash first, exactly as before: the SPM results-slip READ (3.8 returned malformed grades on 26
of 98 slips in the paid eval) and the three GENUINENESS jobs (not tested on 3.8). The offer reader's
second read (2.6.0, `OFFER_RETRY_MODEL`, never 2.5) replaced its 2.5 reporting-date re-ask.
`docs/decisions.md`, 2026-11-16 and 2026-11-18.

No call leaves the machine: the genai client is a fake, or the seam is patched.
"""
import io
import json
from types import SimpleNamespace
from unittest import mock
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import apply_copy_draft as acd
from apps.scholarship import offer_reader as orr
from apps.scholarship import vision
from apps.scholarship.profile_engine import FLASH_25_CASCADE, MODEL_CASCADE


def _png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (60, 80), 'white').save(buf, format='PNG')
    return buf.getvalue()


def _client(answer='{}'):
    """A stand-in `genai.Client` that answers every model with ``answer`` and records the models
    it was asked for, in order."""
    client = MagicMock()
    client.asked = []

    def generate_content(model, contents, config=None):
        client.asked.append(model)
        return SimpleNamespace(text=answer, usage_metadata=None)
    client.models.generate_content.side_effect = generate_content
    return client


class _RealSeam(TestCase):
    """Drives the REAL `vision._call_gemini_json` with a fake client, so the model order asserted is
    the order the provider would see — not what a patched seam was handed."""

    def _first_model(self, fn):
        client = _client()
        with override_settings(GEMINI_API_KEY='test-key'), patch('google.genai.Client', return_value=client):
            fn()
        self.assertTrue(client.asked, 'no model was asked')
        return client.asked[0]


class TheCascades(SimpleTestCase):
    def test_the_default_cascade_is_3_8_then_the_2_5_cascade(self):
        self.assertEqual(MODEL_CASCADE, ['gemini-3.8-flash', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'])
        self.assertEqual(FLASH_25_CASCADE, ['gemini-2.5-flash', 'gemini-2.5-flash-lite'])

    def test_the_other_cascades_moved_too(self):
        from apps.courses.management.commands import generate_stpm_headlines, map_course_careers
        from apps.reports import report_engine
        for name, cascade in (('report_engine', report_engine.MODEL_CASCADE),
                              ('map_course_careers', map_course_careers.MODEL_CASCADE),
                              ('generate_stpm_headlines', generate_stpm_headlines.MODEL_CASCADE)):
            with self.subTest(cascade=name):
                self.assertEqual(cascade[:2], ['gemini-3.8-flash', 'gemini-2.5-flash'])

    def test_the_apply_copy_default_is_3_8(self):
        from halatuju.settings import base
        import os
        self.assertEqual(base.APPLY_COPY_DRAFT_MODEL,
                         os.environ.get('APPLY_COPY_DRAFT_MODEL', 'gemini-3.8-flash'))


class TheResultsSlipReadIsPinnedTo2_5(_RealSeam):
    """THE PER-TYPE PIN. `doc_read` chooses its cascade by document type."""

    def test_the_cascade_by_type(self):
        self.assertEqual(vision.doc_read_cascade('results_slip'), FLASH_25_CASCADE)
        for doc_type in ('salary_slip', 'epf', 'water_bill', 'electricity_bill', 'str'):
            with self.subTest(doc_type=doc_type):
                self.assertEqual(vision.doc_read_cascade(doc_type), MODEL_CASCADE)

    def test_a_results_slip_image_is_read_on_2_5_first(self):
        model = self._first_model(lambda: vision.extract_document_fields(
            '', 'results_slip', image=_png(), content_type='image/png'))
        self.assertEqual(model, 'gemini-2.5-flash')

    def test_a_results_slip_text_is_read_on_2_5_first(self):
        model = self._first_model(lambda: vision.extract_document_fields('SIJIL PELAJARAN MALAYSIA', 'results_slip'))
        self.assertEqual(model, 'gemini-2.5-flash')

    def test_a_salary_slip_is_read_on_3_8_first(self):
        model = self._first_model(lambda: vision.extract_document_fields('PENYATA GAJI', 'salary_slip'))
        self.assertEqual(model, 'gemini-3.8-flash')

    def test_an_electricity_bill_image_is_read_on_3_8_first(self):
        model = self._first_model(lambda: vision.extract_document_fields(
            '', 'electricity_bill', image=_png(), content_type='image/png'))
        self.assertEqual(model, 'gemini-3.8-flash')

    def test_a_2_5_failure_on_a_results_slip_never_reaches_3_8(self):
        client = MagicMock()
        client.asked = []

        def generate_content(model, contents, config=None):
            client.asked.append(model)
            raise RuntimeError('503 UNAVAILABLE')
        client.models.generate_content.side_effect = generate_content
        with override_settings(GEMINI_API_KEY='test-key'), patch('google.genai.Client', return_value=client):
            vision.extract_document_fields('SIJIL PELAJARAN MALAYSIA', 'results_slip')
        self.assertEqual(client.asked, FLASH_25_CASCADE)


class TheGenuinenessJobsStayOn2_5(_RealSeam):
    def test_ic_genuineness(self):
        self.assertEqual(self._first_model(lambda: vision.ic_genuineness(_png(), 'image/png')),
                         'gemini-2.5-flash')

    def test_results_slip_genuineness(self):
        from apps.scholarship.genuineness.results_doc import results_visual_markers
        self.assertEqual(self._first_model(lambda: results_visual_markers(_png(), 'image/png')),
                         'gemini-2.5-flash')

    def test_supporting_document_genuineness(self):
        self.assertEqual(self._first_model(lambda: vision.doc_genuineness(_png(), 'image/png', 'str')),
                         'gemini-2.5-flash')

    def test_an_ordinary_json_job_starts_on_3_8(self):
        """The control: the same seam with no ``models`` walks the default cascade."""
        self.assertEqual(self._first_model(lambda: vision._call_gemini_json('p', {'type': 'object'})),
                         'gemini-3.8-flash')


# ── The offer reader's second read (2.6.0; it replaced 2.5.0's reporting-date re-ask on 2.5) ────────

LETTER = {'candidate_name': 'ZORBEX A/L QUENTARO', 'candidate_nric': '010203-14-5678',
          'candidate_nric_source': 'label', 'programme': 'IJAZAH SARJANA MUDA QORVANE',
          'institution': 'UNIVERSITI QORVANE', 'campus': 'KAMPUS PERLAK', 'intake': 'SESI 1-2031/2032',
          'offer_date': '3 Mac 2031', 'reporting_date': '', 'reporting_date_label': '', 'warnings': []}
DATED = {**LETTER, 'reporting_date': '17 Ogos 2031', 'reporting_date_label': 'Tarikh Lapor Diri'}
#: The live blank read (docs 7395, 7409): programme, institution and intake MISSING, not empty.
BLANK = {k: v for k, v in LETTER.items() if k not in ('programme', 'institution', 'intake')}
#: A second read that found everything — and a DIFFERENT identity, which must never be taken.
RESCUE = {**LETTER, 'candidate_name': 'QUENTARO A/L ZORBEX', 'candidate_nric': '990101-14-9999',
          'reporting_date': '20 Julai 2031', 'reporting_date_label': 'Tarikh Pendaftaran',
          'warnings': ['The campus line is faint.']}
THREE_EIGHT = 'gemini-3.8-flash'


def _seam(by_model):
    """A fake `_call_gemini_json`: the model asked is the first of ``models`` (the default cascade's
    head when none is passed), and ``by_model[model]`` is popped in order and answered."""
    scripts = {m: list(a) for m, a in by_model.items()}

    def fake(prompt, schema, **kw):
        model = (kw.get('models') or MODEL_CASCADE)[0]
        fake.calls.append((model, schema, kw, prompt))
        a = dict(scripts[model].pop(0))
        return a if '_error' in a else {**a, '_model': model}
    fake.calls = []
    return fake


class TheOfferSchema(SimpleTestCase):
    def test_every_field_is_required_and_an_empty_string_still_answers(self):
        required = orr.OFFER_SCHEMA['required']
        self.assertEqual(set(required), set(orr._FIELDS) | {'candidate_nric_source'})
        self.assertNotIn('warnings', required)
        self.assertTrue(all(orr.OFFER_SCHEMA['properties'][f]['type'] == 'string' for f in required))
        self.assertEqual(orr.LATER_SCHEMA['required'], list(orr.LATER_FIELDS))

    def test_the_sdk_takes_the_required_list(self):
        """Offline: the installed google-genai parses the schema WITH its required list (both models
        are sent the same `response_schema`)."""
        from google.genai import types
        for schema in (orr.OFFER_SCHEMA, orr.LATER_SCHEMA):
            self.assertEqual(types.Schema.model_validate(schema).required, schema['required'])


class TheOfferSecondRead(SimpleTestCase):
    def _read(self, fake, kind='photo'):
        from apps.scholarship.tests.test_offer_reader import PAGE_TEXT, blank_pdf, text_pdf
        with mock.patch.object(vision, '_call_gemini_json', fake):
            if kind == 'text':
                return orr.read_offer('SURAT TAWARAN QORVANE')
            if kind in ('pdf', 'short'):                # 'short': PAGE_TEXT's page 1 is a header (<200)
                page_1 = PAGE_TEXT[0] + ('' if kind == 'short' else ' BUTIRAN TAWARAN IJAZAH QORVANE' * 8)
                return orr.read_offer('', image=text_pdf([page_1, *PAGE_TEXT[1:]]), content_type='application/pdf')
            if kind == 'scan':
                return orr.read_offer('', image=blank_pdf(), content_type='application/pdf')
            return orr.read_offer('', image=_png(), content_type='image/png')

    def test_missing_core_keys_count_as_blank_and_the_retry_fills_them(self):
        fake = _seam({THREE_EIGHT: [BLANK, RESCUE]})
        ex = self._read(fake)
        self.assertEqual(len(fake.calls), 2)
        f = ex['fields']
        self.assertEqual((f['programme'], f['institution'], f['intake']),
                         ('IJAZAH SARJANA MUDA QORVANE', 'UNIVERSITI QORVANE', 'SESI 1-2031/2032'))
        self.assertEqual((f['reporting_date'], f['reporting_date_label']), ('20 Jul 2031', 'Tarikh Pendaftaran'))
        self.assertEqual(f['candidate_name'], 'ZORBEX A/L QUENTARO')            # identity: first read only
        self.assertEqual(ex['_raw_identity']['candidate_nric'], '010203-14-5678')
        self.assertIn('The campus line is faint.', ex['warnings'])                # the rescue's own warnings
        shown = ex['offer_reader_inputs']
        self.assertIs(shown['primary_blank'], True)
        self.assertEqual(shown['retry_for'], ['blank', 'reporting_date'])
        self.assertEqual(set(shown['retry_filled']),
                         {'programme', 'institution', 'intake', 'reporting_date', 'reporting_date_label'})
        self.assertEqual(shown['reporting_date_from'], THREE_EIGHT)
        self.assertEqual([c['part'] for c in shown['calls']], ['page_1', 'retry_images'])
        self.assertEqual([c['model'] for c in shown['calls']], [THREE_EIGHT, THREE_EIGHT])
        self.assertEqual(shown['pages'], 1)                                     # a retry is not a page
        self.assertEqual(ex['offer_reader_version'], '2.6.0')

    def test_a_retry_that_comes_back_blank_too_keeps_the_blank_read_and_never_retries_again(self):
        for second in (BLANK, {'_error': 'All AI models failed: x'}):
            with self.subTest(second=second.get('_error', 'blank')):
                fake = _seam({THREE_EIGHT: [BLANK, second]})
                ex = self._read(fake)
                self.assertEqual(len(fake.calls), 2)                            # one retry, no more
                self.assertEqual(ex['error'], '')
                for field in orr.CORE_FIELDS:
                    self.assertFalse(ex['fields'].get(field))
                self.assertEqual(ex['fields']['candidate_name'], 'ZORBEX A/L QUENTARO')
                shown = ex['offer_reader_inputs']
                self.assertIs(shown['primary_blank'], True)
                self.assertEqual(shown['retry_filled'], [])
                self.assertEqual(shown['reporting_date_from'], '')

    def test_a_full_first_read_makes_no_retry(self):
        fake = _seam({THREE_EIGHT: [DATED]})
        ex = self._read(fake)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(ex['fields']['reporting_date'], '17 Aug 2031')
        shown = ex['offer_reader_inputs']
        self.assertIs(shown['primary_blank'], False)
        for key in ('retry_for', 'retry_filled', 'reporting_date_from'):
            self.assertNotIn(key, shown)

    def test_a_partly_filled_first_read_is_not_blank(self):
        """Programme blank but the institution read (or the other way round): not a failed read, no retry."""
        for gap in ('programme', 'institution'):
            with self.subTest(gap=gap):
                fake = _seam({THREE_EIGHT: [{**DATED, gap: ''}]})
                ex = self._read(fake)
                self.assertEqual(len(fake.calls), 1)
                self.assertIs(ex['offer_reader_inputs']['primary_blank'], False)

    def test_programme_and_institution_blank_is_a_blank_read_even_with_an_intake(self):
        fake = _seam({THREE_EIGHT: [{**DATED, 'programme': '', 'institution': ''}, RESCUE]})
        ex = self._read(fake)
        self.assertEqual(len(fake.calls), 2)
        shown = ex['offer_reader_inputs']
        self.assertIs(shown['primary_blank'], True)
        self.assertEqual(shown['retry_for'], ['blank'])
        self.assertEqual(set(shown['retry_filled']), {'programme', 'institution'})
        self.assertEqual(ex['fields']['intake'], 'SESI 1-2031/2032')            # the first read's, kept

    def test_a_blank_page_1_is_rescued_even_when_pages_2_3_give_the_intake(self):
        """Review finding 1: the blank test is on the PAGE-1 answer, before the pages 2-3 merge."""
        later = {'intake': 'SESI 1-2031/2032', 'reporting_date': '17 Ogos 2031',
                 'reporting_date_label': 'Tarikh Lapor Diri'}
        fake = _seam({THREE_EIGHT: [BLANK, later, {**RESCUE, 'intake': 'SESI LAIN'}]})
        ex = self._read(fake, 'pdf')
        shown = ex['offer_reader_inputs']
        self.assertEqual([c['part'] for c in shown['calls']], ['page_1', 'later_pages', 'retry_text_layer'])
        self.assertIs(shown['primary_blank'], True)
        self.assertEqual(shown['retry_for'], ['blank'])                       # the date came from pages 2-3
        f = ex['fields']
        self.assertEqual((f['programme'], f['institution']), ('IJAZAH SARJANA MUDA QORVANE', 'UNIVERSITI QORVANE'))
        self.assertEqual(f['intake'], 'SESI 1-2031/2032')                       # pages 2-3 still win
        self.assertEqual(f['reporting_date'], '17 Aug 2031')
        self.assertEqual(set(shown['retry_filled']), {'programme', 'institution'})

    def test_the_retry_fills_blanks_only(self):
        first = {**BLANK, 'candidate_name': '', 'campus': 'KAMPUS PERLAK', 'offer_date': '3 Mac 2031'}
        second = {**RESCUE, 'campus': 'KAMPUS LAIN', 'offer_date': '9 Mac 2031', 'stream': 'Sains'}
        ex = self._read(_seam({THREE_EIGHT: [first, second]}))
        f = ex['fields']
        self.assertEqual(f['campus'], 'KAMPUS PERLAK')                          # never overwritten
        self.assertEqual(f['offer_date'], '3 Mac 2031')
        self.assertEqual(f['stream'], 'Sains')                                  # a blank, filled
        self.assertEqual(f['programme'], 'IJAZAH SARJANA MUDA QORVANE')
        self.assertFalse(f.get('candidate_name'))                               # identity is never filled
        filled = ex['offer_reader_inputs']['retry_filled']
        self.assertNotIn('campus', filled)
        self.assertFalse(set(filled) & set(orr._NOT_FROM_RETRY))

    def test_a_date_only_retry_takes_the_date_pair_only(self):
        second = {**LETTER, 'programme': 'SOMETHING ELSE', 'stream': 'Sains',
                  'reporting_date': '20 Julai 2031', 'reporting_date_label': 'Tarikh Pendaftaran'}
        ex = self._read(_seam({THREE_EIGHT: [LETTER, second]}))
        f = ex['fields']
        self.assertEqual((f['reporting_date'], f['reporting_date_label']), ('20 Jul 2031', 'Tarikh Pendaftaran'))
        self.assertEqual(f['programme'], 'IJAZAH SARJANA MUDA QORVANE')
        self.assertFalse(f.get('stream'))                                       # not a blank read
        shown = ex['offer_reader_inputs']
        self.assertIs(shown['primary_blank'], False)
        self.assertEqual(shown['retry_for'], ['reporting_date'])
        self.assertEqual(shown['retry_filled'], ['reporting_date', 'reporting_date_label'])
        self.assertEqual(shown['reporting_date_from'], THREE_EIGHT)

    def test_the_date_fallback_and_the_retry_use_the_setting(self):
        other = 'gemini-retry-under-test'
        fake = _seam({THREE_EIGHT: [LETTER], other: [{**LETTER, 'reporting_date': '20 Julai 2031'}]})
        with override_settings(OFFER_RETRY_MODEL=other):
            ex = self._read(fake)
        self.assertEqual(fake.calls[1][2]['models'], [other])                   # that model only, no cascade
        self.assertEqual(ex['offer_reader_inputs']['reporting_date_from'], other)
        self.assertEqual(ex['fields']['reporting_date'], '20 Jul 2031')

    def test_the_setting_defaults_to_3_8_the_env_overrides_it_and_no_2_5_is_hard_coded(self):
        with override_settings(OFFER_RETRY_MODEL=''), mock.patch.dict('os.environ', {}) as env:
            env.pop('OFFER_RETRY_MODEL', None)
            self.assertEqual(orr.retry_model(), THREE_EIGHT)
            env['OFFER_RETRY_MODEL'] = 'gemini-from-env'
            self.assertEqual(orr.retry_model(), 'gemini-from-env')
        for value, model in (('  gemini-x-flash \n', 'gemini-x-flash'), ('   ', THREE_EIGHT),
                             ('gemini-2.5-flash', THREE_EIGHT), (' Gemini-2.5-Flash-Lite', THREE_EIGHT),
                             ('models/gemini-2.5-flash', THREE_EIGHT)):            # re-check item 2
            with self.subTest(value=value), override_settings(OFFER_RETRY_MODEL=value), \
                    mock.patch.dict('os.environ', {'OFFER_RETRY_MODEL': ' '}), \
                    self.assertLogs('apps.scholarship.offer_reader', 'WARNING') as logs:
                orr.logger.warning('marker')                                    # assertLogs needs one record
                self.assertEqual(orr.retry_model(), model)
            self.assertEqual(any('refused' in line for line in logs.output), '2.5' in value)
        constants = [v for k, v in vars(orr).items() if not k.startswith('__') and isinstance(v, str)]
        self.assertFalse([v for v in constants if '2.5' in v])
        self.assertFalse(hasattr(orr, 'REPORTING_DATE_FALLBACK_MODEL'))

    def test_a_text_layer_pdf_gets_the_text_first_retry(self):
        fake = _seam({THREE_EIGHT: [BLANK, {}, RESCUE]})                         # page 1, pages 2-3, retry
        ex = self._read(fake, 'pdf')
        shown = ex['offer_reader_inputs']
        self.assertEqual([c['part'] for c in shown['calls']], ['page_1', 'later_pages', 'retry_text_layer'])
        _, schema, kw, prompt = fake.calls[2]
        self.assertIs(schema, orr.OFFER_SCHEMA)
        self.assertNotIn('images', kw)                                          # text alone, no image
        self.assertNotIn('media_resolution', kw)
        self.assertEqual(kw['models'], [THREE_EIGHT])
        self.assertIn('SURAT TAWARAN QORVANE', prompt)
        for later_page in ('TARIKH PENDAFTARAN DAN TEMPAT', 'SYARAT TAWARAN DAN YURAN', 'PAGE FOUR'):
            self.assertNotIn(later_page, prompt)                                # review finding 2: page 1 only
        self.assertIn('page 1 of a 4-page', prompt)
        self.assertNotIn('IMAGE decides', prompt)
        self.assertEqual(ex['fields']['programme'], 'IJAZAH SARJANA MUDA QORVANE')
        self.assertEqual(shown['pages'], 3)                                     # unchanged by the retry

    def test_a_header_only_text_layer_gets_the_page_1_image_retry(self):
        """Re-check item 4: a page-1 layer under `RETRY_MIN_TEXT_CHARS` (the body an image) is too thin."""
        self.assertEqual(orr.RETRY_MIN_TEXT_CHARS, 200)
        fake = _seam({THREE_EIGHT: [BLANK, {}, RESCUE]})
        ex = self._read(fake, 'short')
        shown = ex['offer_reader_inputs']
        self.assertEqual([c['part'] for c in shown['calls']], ['page_1', 'later_pages', 'retry_images'])
        self.assertEqual(len(fake.calls), 3)                                    # still one retry call
        self.assertEqual(fake.calls[2][2]['images'], fake.calls[0][2]['images'])  # page 1 only
        self.assertNotIn('media_resolution', fake.calls[2][2])                  # at the default resolution
        self.assertEqual(fake.calls[2][2]['models'], [THREE_EIGHT])
        self.assertEqual(ex['fields']['programme'], 'IJAZAH SARJANA MUDA QORVANE')

    def test_a_photo_gets_the_image_retry_at_the_default_resolution(self):
        fake = _seam({THREE_EIGHT: [BLANK, RESCUE]})
        self._read(fake)
        first, second = fake.calls[0][2], fake.calls[1][2]
        self.assertEqual(first['media_resolution'], orr.MEDIA_RESOLUTION)
        self.assertEqual(len(second['images']), 1)
        self.assertNotIn('media_resolution', second)

    def test_a_scanned_pdf_gets_the_image_retry(self):
        fake = _seam({THREE_EIGHT: [BLANK, RESCUE]})
        ex = self._read(fake, 'scan')
        self.assertEqual([c['part'] for c in ex['offer_reader_inputs']['calls']], ['page_1', 'retry_images'])
        self.assertEqual(len(fake.calls[1][2]['images']), 1)
        self.assertNotIn('media_resolution', fake.calls[1][2])

    def test_a_multi_page_scanned_pdf_retries_on_the_page_1_image_only(self):
        """Review finding 2: a reply form or a second letter on pages 2-3 never reaches the retry."""
        from PIL import Image
        buf = io.BytesIO()
        pages = [Image.new('RGB', (600, 800), c) for c in ('white', 'gray', 'black')]
        pages[0].save(buf, format='PDF', save_all=True, append_images=pages[1:])
        fake = _seam({THREE_EIGHT: [BLANK, {}, RESCUE]})
        with mock.patch.object(vision, '_call_gemini_json', fake):
            ex = orr.read_offer('', image=buf.getvalue(), content_type='application/pdf')
        shown = ex['offer_reader_inputs']
        self.assertEqual([c['part'] for c in shown['calls']], ['page_1', 'later_pages', 'retry_images'])
        page_1, retry = fake.calls[0][2]['images'], fake.calls[2][2]['images']
        self.assertEqual(retry, page_1)                                         # the same page-1 image, alone
        self.assertNotIn('media_resolution', fake.calls[2][2])                  # at the default resolution
        self.assertIn('page 1 of a 3-page', fake.calls[2][3])
        self.assertEqual(ex['fields']['programme'], 'IJAZAH SARJANA MUDA QORVANE')

    def test_a_retry_filled_date_brings_its_own_label(self):
        """Review finding 4: a first-read label with no date never rides on the retry's date."""
        first = {**LETTER, 'reporting_date_label': 'Tarikh Mula Kuliah'}
        for label, kept in (('Tarikh Pendaftaran', 'Tarikh Pendaftaran'), ('', '')):
            with self.subTest(retry_label=label):
                second = {**LETTER, 'reporting_date': '20 Julai 2031', 'reporting_date_label': label}
                ex = self._read(_seam({THREE_EIGHT: [first, second]}))
                self.assertEqual(ex['fields']['reporting_date'], '20 Jul 2031')
                self.assertEqual(ex['fields']['reporting_date_label'], kept)
                self.assertEqual(ex['offer_reader_inputs']['retry_filled'], ['reporting_date', 'reporting_date_label'])
        ex = self._read(_seam({THREE_EIGHT: [first, LETTER]}))                  # no date: the label stays
        self.assertEqual(ex['fields']['reporting_date_label'], 'Tarikh Mula Kuliah')
        self.assertEqual(ex['offer_reader_inputs']['retry_filled'], [])

    def test_a_rescue_keeps_the_identity_warnings_and_drops_only_the_filled_ones(self):
        """Review finding 5."""
        first = {**BLANK, 'warnings': ['The IC number is blurred.', "The student's name is partly cut off.",
                                       'The programme and the institution could not be found.',
                                       'The page has a coffee stain.', 'The campus line is faint.']}
        second = {**RESCUE, 'warnings': ['The campus line is faint.', 'The IC number looks different.',
                                         'The intake session is printed twice.']}
        ex = self._read(_seam({THREE_EIGHT: [first, second]}))
        self.assertEqual(ex['warnings'], ['The IC number is blurred.', "The student's name is partly cut off.",
                                          'The page has a coffee stain.', 'The campus line is faint.',
                                          'The intake session is printed twice.'])

    def test_a_date_only_retry_drops_the_stale_date_warning_and_adds_only_date_warnings(self):
        first = {**LETTER, 'warnings': ['The reporting date could not be found.', 'The IC number is blurred.']}
        second = {**LETTER, 'reporting_date': '20 Julai 2031', 'reporting_date_label': 'Tarikh Pendaftaran',
                  'warnings': ['The registration date is handwritten.', 'The programme title is faint.']}
        ex = self._read(_seam({THREE_EIGHT: [first, second]}))
        self.assertEqual(ex['warnings'], ['The IC number is blurred.', 'The registration date is handwritten.'])
        ex = self._read(_seam({THREE_EIGHT: [first, {**LETTER, 'warnings': ['Faint.']}]}))   # nothing filled
        self.assertEqual(ex['warnings'], first['warnings'])

    def test_a_date_only_retry_keeps_warnings_that_only_mention_reporting_or_registration(self):
        """Re-check item 1(a): the date pair needs a date word too."""
        probes = ['This looks like a registration confirmation slip, not the offer letter itself',
                  'The letterhead shows only the Pejabat Pendaftar, not the faculty.',
                  'The reporting venue is not printed.']
        stale = ['The reporting date could not be found.', 'The Tarikh Lapor Diri label has no date beside it.']
        first = {**LETTER, 'warnings': probes + stale}
        second = {**LETTER, 'reporting_date': '20 Julai 2031', 'reporting_date_label': 'Tarikh Pendaftaran'}
        ex = self._read(_seam({THREE_EIGHT: [first, second]}))
        self.assertEqual(ex['offer_reader_inputs']['retry_filled'], ['reporting_date', 'reporting_date_label'])
        self.assertEqual(orr._merge_warnings(first['warnings'], [], ex['offer_reader_inputs']['retry_filled'],
                                             ['reporting_date']), probes)      # the two stale ones, dropped
        # End to end the venue note goes too, but by the older "optional field not printed" noise filter.
        self.assertEqual(ex['warnings'], probes[:2])

    def test_a_blank_retry_keeps_code_and_red_flag_warnings_it_did_not_answer(self):
        """Re-check item 1(b)(c): only a COURSE code warning is about `programme_code`; a red flag about the
        document always stays, whatever field it names."""
        kept = ['The QR code at the bottom could not be checked.', 'The programme name looks edited.',
                'The institution name may have been altered.', 'The programme and the IC show a mismatch.',
                'The institution logo looks forged.', 'This is not an offer letter from the institution.',
                'The programme line looks tampered with.', 'Ini bukan surat tawaran program ini.']
        first = {**BLANK, 'warnings': kept + ['The course code could not be found.',
                                              'The programme and the institution could not be found.']}
        second = {**RESCUE, 'programme_code': 'UW6526001', 'warnings': []}
        ex = self._read(_seam({THREE_EIGHT: [first, second]}))
        self.assertIn('programme_code', ex['offer_reader_inputs']['retry_filled'])
        self.assertEqual(ex['warnings'], kept)                                  # the two stale ones, dropped

    def test_a_non_string_warning_never_breaks_the_read(self):
        """Re-check item 3: warnings are coerced to strings (empty ones skipped), so the merge never raises."""
        first = {**BLANK, 'warnings': [['a', 'list'], None, '', '  ', 7, 'The page has a coffee stain.']}
        second = {**RESCUE, 'warnings': [{'odd': 1}, 'The campus line is faint.', None]}
        ex = self._read(_seam({THREE_EIGHT: [first, second]}))
        self.assertEqual(ex['error'], '')
        self.assertEqual(ex['fields']['programme'], 'IJAZAH SARJANA MUDA QORVANE')
        self.assertEqual(ex['warnings'], ["['a', 'list']", '7', 'The page has a coffee stain.', "{'odd': 1}",
                                          'The campus line is faint.'])
        self.assertEqual(orr._merge_warnings('One warning.', None, [], ['blank']), ['One warning.'])
        ex = self._read(_seam({THREE_EIGHT: [{**DATED, 'warnings': [['x'], 'Faint.']}]}))   # no retry at all
        self.assertEqual((ex['error'], ex['warnings']), ('', ["['x']", 'Faint.']))

    def test_the_text_only_read_re_asks_its_ocr_text(self):
        fake = _seam({THREE_EIGHT: [BLANK, RESCUE]})
        ex = self._read(fake, 'text')
        self.assertNotIn('images', fake.calls[1][2])
        self.assertEqual(ex['offer_reader_inputs']['calls'][-1]['part'], 'retry_text')
        self.assertEqual(ex['fields']['institution'], 'UNIVERSITI QORVANE')

    def test_the_3_8_error_path_is_unchanged(self):
        """3.8 failed and the cascade answered on 2.5: kept as before, no second read. Every model
        failed: the error, as before."""
        def fake(prompt, schema, **kw):
            fake.calls.append(kw)
            return {**BLANK, '_model': 'gemini-2.5-flash'}
        fake.calls = []
        ex = self._read(fake)
        self.assertEqual(len(fake.calls), 1)
        self.assertIs(ex['offer_reader_inputs']['primary_blank'], True)
        self.assertNotIn('retry_for', ex['offer_reader_inputs'])

        failed = _seam({THREE_EIGHT: [{'_error': 'All AI models failed: x'}]})
        ex = self._read(failed)
        self.assertEqual(len(failed.calls), 1)
        self.assertEqual((ex['fields'], ex['error']), ({}, 'All AI models failed: x'))


# ── The apply-copy draft and the batch commands ──────────────────────────────────────────────────

class TheApplyCopyDraftFallsBack(SimpleTestCase):
    def test_a_3_8_failure_moves_to_2_5(self):
        asked = []
        good = json.dumps({'title': 'T', 'intro': 'I', 'criteria': ['a']})

        def seam(prompt, model, timeout_ms=None):
            asked.append(model)
            if model == 'gemini-3.8-flash':
                raise RuntimeError('503 UNAVAILABLE')
            return good
        programme = SimpleNamespace(pk=1, apply_copy={'en': {'title': 'T', 'intro': 'I', 'criteria': ['a']}})
        with override_settings(APPLY_COPY_DRAFT_MODEL='gemini-3.8-flash'), \
                patch.object(acd, '_gemini_generate', side_effect=seam):
            block = acd.draft(programme, 'ms')
        self.assertEqual(asked, ['gemini-3.8-flash', 'gemini-2.5-flash'])
        self.assertEqual(block['criteria'], ['a'])


class TheStpmHeadlinesCommandFallsBack(SimpleTestCase):
    def test_a_3_8_failure_asks_2_5_with_its_own_config(self):
        from apps.courses.management.commands import generate_stpm_headlines as gsh
        client = MagicMock()
        seen = []

        def generate_content(model, contents, config=None):
            seen.append((model, config))
            if model == 'gemini-3.8-flash':
                raise RuntimeError('503')
            return SimpleNamespace(text='{"headlines": {"C1": "x"}}')
        client.models.generate_content.side_effect = generate_content
        self.assertEqual(gsh._ask(client, ['p']), {'C1': 'x'})
        self.assertEqual([m for m, _ in seen], ['gemini-3.8-flash', 'gemini-2.5-flash'])
        self.assertNotIn('thinking_config', seen[0][1])
        self.assertEqual(seen[1][1]['thinking_config'], {'thinking_budget': 0})
