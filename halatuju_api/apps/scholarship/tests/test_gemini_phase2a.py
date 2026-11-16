"""Gemini Phase 2 Option A (owner, 2026-11-14) — 3.8 Flash first, with the owner's exceptions.

Every Flash job moves to gemini-3.8-flash first, 2.5 Flash as its fallback. Two exceptions stay on
2.5 Flash first, exactly as before: the SPM results-slip READ (3.8 returned malformed grades on 26
of 98 slips in the paid eval) and the three GENUINENESS jobs (not tested on 3.8). The offer reader
re-asks 2.5 Flash for the reporting date when 3.8 returns none (lost on 4 of 84 letters).
`docs/decisions.md`, 2026-11-16.

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


# ── The offer reader's reporting-date fallback ───────────────────────────────────────────────────

LETTER = {'candidate_name': 'ZORBEX A/L QUENTARO', 'candidate_nric': '010203-14-5678',
          'candidate_nric_source': 'label', 'programme': 'IJAZAH SARJANA MUDA QORVANE',
          'institution': 'UNIVERSITI QORVANE', 'campus': 'KAMPUS PERLAK', 'intake': 'SESI 1-2031/2032',
          'offer_date': '3 Mac 2031', 'reporting_date': '', 'reporting_date_label': '', 'warnings': []}


def _seam(by_model):
    """A fake `_call_gemini_json`: the model asked is the first of ``models`` (the default cascade's
    head when none is passed), and ``by_model[model]`` is popped in order and answered."""
    scripts = {m: list(a) for m, a in by_model.items()}

    def fake(prompt, schema, **kw):
        model = (kw.get('models') or MODEL_CASCADE)[0]
        fake.calls.append((model, schema, kw))
        a = dict(scripts[model].pop(0))
        return a if '_error' in a else {**a, '_model': model}
    fake.calls = []
    return fake


class TheOfferReportingDateFallback(SimpleTestCase):
    def _read(self, fake, **kw):
        with mock.patch.object(vision, '_call_gemini_json', fake):
            if kw.get('text'):
                return orr.read_offer('SURAT TAWARAN QORVANE')
            return orr.read_offer('', image=_png(), content_type='image/png')

    def test_it_fires_when_3_8_returns_no_reporting_date(self):
        fake = _seam({'gemini-3.8-flash': [LETTER],
                      'gemini-2.5-flash': [{**LETTER, 'programme': 'SOMETHING ELSE',
                                            'reporting_date': '20 Julai 2031',
                                            'reporting_date_label': 'Tarikh Pendaftaran'}]})
        ex = self._read(fake)
        self.assertEqual([c[0] for c in fake.calls], ['gemini-3.8-flash', 'gemini-2.5-flash'])
        self.assertEqual(fake.calls[1][2]['models'], ['gemini-2.5-flash'])
        f = ex['fields']
        self.assertEqual((f['reporting_date'], f['reporting_date_label']), ('20 Jul 2031', 'Tarikh Pendaftaran'))
        self.assertEqual(f['programme'], 'IJAZAH SARJANA MUDA QORVANE')        # 3.8's other fields stay
        self.assertEqual(f['offer_date'], '3 Mac 2031')
        shown = ex['offer_reader_inputs']
        self.assertEqual(shown['reporting_date_from'], 'gemini-2.5-flash')
        self.assertEqual([c['part'] for c in shown['calls']], ['page_1', 'fallback_page_1'])
        self.assertEqual(shown['pages'], 1)                                     # a re-ask is not a page
        self.assertEqual(ex['offer_reader_version'], '2.5.0')

    def test_it_does_not_fire_when_3_8_has_the_date(self):
        fake = _seam({'gemini-3.8-flash': [{**LETTER, 'reporting_date': '17 Ogos 2031',
                                            'reporting_date_label': 'Tarikh Lapor Diri'}]})
        ex = self._read(fake)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(ex['fields']['reporting_date'], '17 Aug 2031')
        self.assertNotIn('reporting_date_from', ex['offer_reader_inputs'])

    def test_it_does_not_fire_when_2_5_already_answered(self):
        """3.8 failed and the cascade answered on 2.5: asking 2.5 again would only repeat it."""
        def fake(prompt, schema, **kw):
            fake.calls.append(kw)
            return {**LETTER, '_model': 'gemini-2.5-flash'}
        fake.calls = []
        self._read(fake)
        self.assertEqual(len(fake.calls), 1)

    def test_an_empty_or_failed_re_ask_keeps_the_3_8_read(self):
        for answer in ({**LETTER, 'programme': 'OTHER'}, {'_error': 'All AI models failed: x'}):
            with self.subTest(answer=answer.get('_error', 'empty')):
                fake = _seam({'gemini-3.8-flash': [LETTER], 'gemini-2.5-flash': [answer]})
                ex = self._read(fake)
                self.assertEqual(ex['error'], '')
                self.assertEqual(ex['fields']['reporting_date'], '')
                self.assertEqual(ex['fields']['programme'], 'IJAZAH SARJANA MUDA QORVANE')
                self.assertEqual(ex['offer_reader_inputs']['reporting_date_from'], '')

    def test_the_text_only_read_falls_back_too(self):
        fake = _seam({'gemini-3.8-flash': [LETTER],
                      'gemini-2.5-flash': [{**LETTER, 'reporting_date': '20 Julai 2031'}]})
        ex = self._read(fake, text=True)
        self.assertNotIn('images', fake.calls[1][2])
        self.assertEqual(ex['fields']['reporting_date'], '20 Jul 2031')
        self.assertEqual(ex['offer_reader_inputs']['calls'][-1]['part'], 'fallback_text')

    def test_a_multi_page_letter_re_asks_the_later_pages_when_page_1_has_none(self):
        from apps.scholarship.tests.test_offer_reader import PAGE_TEXT, text_pdf
        fake = _seam({'gemini-3.8-flash': [LETTER, {'reporting_date': ''}],
                      'gemini-2.5-flash': [LETTER, {'reporting_date': '20 Julai 2031',
                                                    'reporting_date_label': 'Tarikh Pendaftaran'}]})
        with mock.patch.object(vision, '_call_gemini_json', fake):
            ex = orr.read_offer('', image=text_pdf(PAGE_TEXT), content_type='application/pdf')
        parts = [c['part'] for c in ex['offer_reader_inputs']['calls']]
        self.assertEqual(parts, ['page_1', 'later_pages', 'fallback_page_1', 'fallback_later_pages'])
        self.assertIs(fake.calls[3][1], orr.LATER_SCHEMA)
        self.assertEqual(ex['fields']['reporting_date'], '20 Jul 2031')
        self.assertEqual(ex['offer_reader_inputs']['pages'], 3)                # unchanged by the re-ask


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
