"""Case 1048: topic-coded salary-slip warnings (the read tags them; the display hides payslip-only TOPICS on a
declaration; an untagged or older read falls back to the word filter), the guard on who may name the topics,
and the paid eval `eval_warning_topics` (mocked: no AI call is ever made here)."""
import re
from contextlib import ExitStack
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase

from apps.scholarship import vision
from apps.scholarship.income_engine.declaration_name import has_keep_word, payslip_only_warning, shown_warnings
from apps.scholarship.management.commands import eval_warning_topics as ev
from apps.scholarship.models import ApplicantDocument, ApplicantDocumentOcrText
from apps.scholarship.tests.factories import make_application, make_cohort, make_student
from apps.scholarship.tests.source_walk import API_ROOT, _relative, walk_sources
from apps.scholarship.vision import warning_topics as wt
from apps.scholarship.vision.schemas import _FIELD_SCHEMAS

SEAM = 'apps.scholarship.vision._call_gemini_json'
OCR = 'apps.scholarship.vision.extract_text'
FETCH = 'apps.scholarship.vision._fetch_image_bytes'

NO_EMPLOYER = 'No employer name is shown'
NO_PERIOD = 'The pay period is not stated'
HANDWRITTEN = 'The document is handwritten'
ALTERED = 'The amount looks altered'
YTD = 'Year-to-date gross is not shown'      # dropped by the salary-slip clean-up (optional field)


def _doc(topics=None, seen='declaration', doc_type='salary_slip'):
    vf = {'authenticity': {'doc_seen': seen}, 'fields': {'gross_income': '1200'}}
    if topics is not None:
        vf[wt.KEY] = topics
    return SimpleNamespace(doc_type=doc_type, vision_fields=vf, id=1, application_id=1, application=object())


class TheTopicListTests(SimpleTestCase):
    def test_every_code_is_payslip_only_or_kept_never_both(self):
        self.assertEqual(set(wt.TOPICS), wt.PAYSLIP_ONLY_TOPICS | wt.KEPT_TOPICS)
        self.assertFalse(wt.PAYSLIP_ONLY_TOPICS & wt.KEPT_TOPICS)
        self.assertEqual(len(wt.TOPICS), len(set(wt.TOPICS)))
        self.assertIn('other', wt.KEPT_TOPICS)

    def test_valid_topics(self):
        ws = [NO_EMPLOYER, HANDWRITTEN]
        self.assertTrue(wt.valid_topics(ws, ['employer_missing', 'other']))
        self.assertTrue(wt.valid_topics([], []))
        for bad in (None, 'employer_missing', ['employer_missing'], ['employer_missing', 'other', 'other'],
                    ['employer_missing', 'made_up'], ['employer_missing', 3], ('employer_missing', 'other')):
            self.assertFalse(wt.valid_topics(ws, bad), bad)
        self.assertFalse(wt.valid_topics(None, []))

    def test_keep_aligned_cuts_both_lists_together(self):
        self.assertEqual(wt.keep_aligned(['a', 'b', 'c'], ['other', 'altered', 'unreadable'], [0, 2]),
                         (['a', 'c'], ['other', 'unreadable']))
        self.assertEqual(wt.keep_aligned(['a', 'b'], ['nope', 'other'], [0, 1]), (['a', 'b'], ['nope', 'other']))
        self.assertEqual(wt.keep_aligned(['a', 'b', 'c'], ['other', 'other'], [0, 1]), (['a', 'b'], None))
        self.assertEqual(wt.keep_aligned(['a'], None, [0]), (['a'], None))


class TheSchemaAndPromptTests(SimpleTestCase):
    def test_only_the_salary_slip_schema_asks_for_topics(self):
        prop = _FIELD_SCHEMAS['salary_slip']['properties'][wt.KEY]
        self.assertEqual(prop, {'type': 'array', 'items': {'type': 'string', 'enum': list(wt.TOPICS)}})
        for doc_type, schema in _FIELD_SCHEMAS.items():
            if doc_type != 'salary_slip':
                self.assertNotIn(wt.KEY, schema.get('properties', {}), doc_type)

    def _read(self, doc_type, answer):
        with patch(SEAM, return_value=answer) as m:
            out = vision.extract_document_fields('SOME OCR TEXT', doc_type)
        return out, m.call_args[0][0]

    def test_the_prompt_line_is_for_the_salary_slip_only(self):
        _, prompt = self._read('salary_slip', {'warnings': []})
        self.assertIn(wt.PROMPT_LINE.strip(), prompt)
        _, prompt = self._read('epf', {'warnings': []})
        self.assertNotIn('warning_topics', prompt)

    def test_the_read_returns_aligned_topics_and_never_puts_them_in_fields(self):
        out, _ = self._read('salary_slip', {'gross_income': '1200', 'warnings': [NO_EMPLOYER, YTD, ALTERED],
                                            wt.KEY: ['employer_missing', 'gross_missing', 'altered']})
        self.assertEqual(out['warnings'], [NO_EMPLOYER, ALTERED])
        self.assertEqual(out[wt.KEY], ['employer_missing', 'altered'])
        self.assertNotIn(wt.KEY, out['fields'])

    def test_invalid_topics_are_left_as_they_came_until_a_warning_drops(self):
        out, _ = self._read('salary_slip', {'warnings': [NO_EMPLOYER, ALTERED], wt.KEY: ['employer_missing', 'x']})
        self.assertEqual(out[wt.KEY], ['employer_missing', 'x'])
        out, _ = self._read('salary_slip', {'warnings': [NO_EMPLOYER, YTD, ALTERED], wt.KEY: ['other', 'other']})
        self.assertEqual(out['warnings'], [NO_EMPLOYER, ALTERED])
        self.assertNotIn(wt.KEY, out)

    def test_no_topics_means_no_key(self):
        out, _ = self._read('salary_slip', {'warnings': [NO_EMPLOYER]})
        self.assertNotIn(wt.KEY, out)

    def test_another_type_never_carries_topics(self):
        out, _ = self._read('epf', {'name': 'X', 'warnings': [HANDWRITTEN], wt.KEY: ['other']})
        self.assertNotIn(wt.KEY, out)
        self.assertNotIn(wt.KEY, out['fields'])

    def test_the_stored_read_keeps_the_topics_beside_the_warnings(self):
        from apps.scholarship.vision.field_extraction import _EX_KEPT
        self.assertIn(wt.KEY, _EX_KEPT)


class TheTaggedDisplayTests(SimpleTestCase):
    WS = [NO_EMPLOYER, NO_PERIOD, HANDWRITTEN]

    def test_payslip_only_topics_hide_on_a_declaration(self):
        doc = _doc(['employer_missing', 'pay_period_missing', 'other'])
        self.assertEqual(shown_warnings(doc, self.WS), [HANDWRITTEN])

    def test_new_wording_the_word_filter_misses_is_hidden_by_its_code(self):
        odd = 'Company details could not be located anywhere on this page'
        self.assertFalse(payslip_only_warning(odd))
        self.assertEqual(shown_warnings(_doc(['employer_missing']), [odd]), [])

    def test_a_keep_word_always_shows_even_under_a_payslip_only_code(self):
        ws = ['No employer chop or stamp', 'The pay period on the IC copy differs', 'Pay period looks altered']
        self.assertTrue(all(has_keep_word(w) for w in ws))
        self.assertEqual(shown_warnings(_doc(['employer_missing', 'pay_period_missing', 'pay_period_missing']), ws),
                         ws)

    def test_a_kept_code_shows_even_when_the_words_would_hide_it(self):
        self.assertTrue(payslip_only_warning(NO_EMPLOYER))
        self.assertEqual(shown_warnings(_doc(['other']), [NO_EMPLOYER]), [NO_EMPLOYER])

    def test_bad_topics_fall_back_to_the_word_filter_for_the_whole_list(self):
        words = [w for w in self.WS if not payslip_only_warning(w)]
        self.assertEqual(words, [HANDWRITTEN])
        for bad in (None, ['employer_missing'], ['employer_missing', 'pay_period_missing', 'made_up'],
                    ['other', 'other', 'other', 'other'], 'employer_missing'):
            self.assertEqual(shown_warnings(_doc(bad), self.WS), words, bad)

    def test_never_mixed_one_bad_code_sends_every_warning_to_the_words(self):
        odd = 'Company details could not be located anywhere on this page'
        self.assertEqual(shown_warnings(_doc(['employer_missing', 'nope']), [odd, NO_EMPLOYER]), [odd])

    def test_not_a_declaration_or_not_a_salary_slip_shows_everything(self):
        topics = ['employer_missing', 'pay_period_missing', 'other']
        for doc in (_doc(topics, seen='private'), _doc(topics, seen=''), _doc(topics, doc_type='epf')):
            self.assertIs(shown_warnings(doc, self.WS), self.WS)

    def test_a_doc_without_vision_fields_falls_back(self):
        doc = SimpleNamespace(doc_type='salary_slip', vision_fields=None)
        self.assertIs(shown_warnings(doc, self.WS), self.WS)      # no stored read: not seen as a declaration

    def test_a_signing_date_pay_period_note_is_hidden_under_its_code(self):
        """"signing" holds the keep stem "sign", but a date phrase that only says WHEN it was signed is not a
        signature note: the declaration's "date is the signing date, not a pay period" note hides."""
        w = 'The date shown is the declaration signing date rather than a specific pay period'
        self.assertTrue(has_keep_word(w))
        self.assertEqual(shown_warnings(_doc(['pay_period_missing']), [w]), [])
        for phrase in ('date of signing', 'date signed', 'signed date', 'signed on'):
            self.assertEqual(shown_warnings(_doc(['pay_period_missing']), [f'The {phrase} is not a pay period']), [],
                             phrase)

    def test_signature_notes_still_show_under_a_payslip_only_code(self):
        for w in ('The declaration is not signed', 'No signature or stamp', 'Signature missing',
                  'The signing date appears altered', 'Unsigned'):
            for code in ('pay_period_missing', 'employer_missing'):
                self.assertEqual(shown_warnings(_doc([code]), [w]), [w], (w, code))


class OnlyTheReaderAndTheDisplayNameTheTopicsTests(SimpleTestCase):
    """No verdict, chip, score, genuineness or money may read a topic: only these modules may name them."""

    ALLOWED = frozenset({
        'halatuju_api/apps/scholarship/vision/warning_topics.py',
        'halatuju_api/apps/scholarship/vision/schemas.py',
        'halatuju_api/apps/scholarship/vision/gemini_read.py',
        'halatuju_api/apps/scholarship/vision/sanitize.py',
        'halatuju_api/apps/scholarship/vision/field_extraction.py',      # keeps the key on the stored read
        'halatuju_api/apps/scholarship/income_engine/declaration_name.py',
        'halatuju_api/apps/scholarship/management/commands/eval_warning_topics.py',
        'halatuju_api/apps/scholarship/model_registry.py',     # pins the module's text by path; reads no topic
    })
    NAME = re.compile(r'warning_topics')

    @classmethod
    def offenders(cls, sources):
        return sorted(rel for rel, text in sources if rel not in cls.ALLOWED and cls.NAME.search(text))

    def _sources(self):
        why = 'the topic-code guard reads every non-test API module (case 1048)'
        for path in walk_sources(API_ROOT / 'apps', '*.py', 300, why):
            rel = _relative(path)
            if '/tests/' not in rel:
                yield rel, path.read_text(encoding='utf-8')

    def test_only_the_listed_modules_name_the_topics(self):
        sources = list(self._sources())
        self.assertEqual(self.offenders(sources), [])
        self.assertEqual(self.ALLOWED - {rel for rel, text in sources if self.NAME.search(text)}, set())

    def test_the_guard_fails_on_a_synthetic_reader(self):
        fake = [('halatuju_api/apps/scholarship/verdict_engine.py',
                 "topics = doc.vision_fields.get('warning_topics')"),
                ('halatuju_api/apps/scholarship/vision/schemas.py', "KEY = 'warning_topics'")]
        self.assertEqual(self.offenders(fake), ['halatuju_api/apps/scholarship/verdict_engine.py'])


def _answer(warnings, topics, **fields):
    return {'name': 'X', 'gross_income': '1200', 'net_income': '1000', 'period': 'JAN', 'employer': 'E',
            **fields, 'warnings': warnings, wt.KEY: topics}


class _Slips(TestCase):
    def setUp(self):
        self.cohort = make_cohort()

    def slip(self, seen='declaration', capture='ai', fields=None):
        app = make_application(cohort=self.cohort, student=make_student())
        vf = {'authenticity': {'doc_seen': seen}, 'capture': capture, 'warnings': [],
              'fields': fields or {'name': 'X', 'gross_income': '1200', 'net_income': '1000', 'period': 'JAN',
                                   'employer': 'E'}}
        return ApplicantDocument.objects.create(application=app, doc_type='salary_slip', storage_path='test/slip',
                                                content_type='image/jpeg', vision_fields=vf)

    def run_cmd(self, *args, seam=None, fetch=b'img', ocr=None):
        out = StringIO()
        with ExitStack() as stack:
            m = stack.enter_context(patch(SEAM, **(seam or {'return_value': _answer([], [])})))
            f = stack.enter_context(patch(FETCH, return_value=fetch))
            stack.enter_context(patch(OCR, return_value=ocr or {'text': 'SOME OCR TEXT', 'error': None}))
            call_command('eval_warning_topics', *args, stdout=out)
        return out.getvalue(), m, f


class TheEvalDryRunTests(_Slips):
    def test_counts_only_no_fetch_no_ai_call(self):
        for _ in range(3):
            self.slip()
        self.slip(capture='deterministic')
        text, seam, fetch = self.run_cmd()
        seam.assert_not_called()
        fetch.assert_not_called()
        self.assertIn('DRY RUN', text)
        self.assertIn('salary slips to re-read: 3', text)
        self.assertIn('label-parsed passed over: 1', text)

    def test_the_arguments(self):
        bad = [('--run',), ('--run', '--limit', '5'), ('--run', '--max-cost-usd', '0.5'),
               ('--run', '--limit', '5', '--max-cost-usd', '1.01'), ('--run', '--limit', '5', '--max-cost-usd', '0'),
               ('--run', '--limit', '5', '--max-cost-usd', 'x'), ('--limit', str(ev.MAX_LIMIT + 1)), ('--limit', '0')]
        for args in bad:
            with self.subTest(args=args), self.assertRaises(CommandError):
                self.run_cmd(*args)


class TheEvalRunTests(_Slips):
    RUN = ('--run', '--limit', '60', '--max-cost-usd', '0.50')

    def test_writes_nothing_and_meters_a_platform_row(self):
        for _ in range(2):
            self.slip()
        before = list(ApplicantDocument.objects.order_by('pk').values())
        with patch('apps.scholarship.usage.usage_context', wraps=ev.usage.usage_context) as ctx:
            text, m, _ = self.run_cmd(*self.RUN, seam={'return_value': _answer([NO_EMPLOYER], ['employer_missing'])})
        self.assertEqual(list(ApplicantDocument.objects.order_by('pk').values()), before)
        self.assertFalse(ApplicantDocumentOcrText.objects.exists())
        self.assertEqual(m.call_count, 2)
        self.assertTrue(all(c.kwargs == {'source': ev.USAGE_SOURCE} for c in ctx.call_args_list))
        self.assertIn('read 2', text)

    def test_a_write_during_the_run_is_refused(self):
        d = self.slip()

        def seam(*a, **k):
            ApplicantDocument.objects.filter(pk=d.pk).update(vision_fields={})
            return _answer([], [])
        text, _, _ = self.run_cmd(*self.RUN, seam={'side_effect': seam})
        self.assertIn('read 0', text)
        self.assertEqual(ApplicantDocument.objects.get(pk=d.pk).vision_fields['capture'], 'ai')

    def test_the_counts_a_to_d(self):
        decl, payslip = self.slip(), self.slip(seen='private')
        odd = 'Company details could not be located anywhere on this page'
        answers = {decl.pk: _answer([odd, NO_PERIOD, 'No employer chop'],
                                    ['employer_missing', 'pay_period_missing', 'employer_missing'], name=''),
                   payslip.pk: _answer([HANDWRITTEN], ['nope'], gross_income='9999')}
        order = iter(sorted(answers, reverse=True))
        text, _, _ = self.run_cmd(*self.RUN, seam={'side_effect': lambda *a, **k: answers[next(order)]})
        for part in ('read 2', 'gross_income_same 1', 'gross_income_changed 1', 'name_lost 1',
                     'name_present_both 1', 'valid_topics 1', 'invalid_topics 1', 'declarations 1',
                     'declaration_warnings 3', 'hidden_by_topic 2', 'hidden_by_words 1'):
            self.assertIn(part, text)
        self.assertIn(f'keep_word_tagged_payslip_only ids: {decl.pk}', text)
        self.assertIn(f'topics_hide_more ids: {decl.pk}', text)
        for secret in (odd, NO_PERIOD, '9999', 'SOME OCR TEXT'):
            self.assertNotIn(secret, text)

    def test_stops_after_five_service_errors_in_a_row(self):
        for _ in range(7):
            self.slip()
        text, m, _ = self.run_cmd(*self.RUN, seam={'return_value': {'_error': 'cascade failed'}})
        self.assertIn('STOPPED: 5 service errors in a row', text)
        self.assertIn('service_error 5', text)

    def test_stops_after_five_failed_fetches_in_a_row(self):
        for _ in range(7):
            self.slip()
        text, m, _ = self.run_cmd(*self.RUN, fetch=None)
        self.assertIn('STOPPED: 5 fetches in a row failed', text)
        m.assert_not_called()

    def test_a_progress_line_every_twenty(self):
        for _ in range(21):
            self.slip()
        text, _, _ = self.run_cmd(*self.RUN)
        self.assertEqual(text.count('progress:'), 1)
        self.assertIn('progress: 20 documents', text)

    def test_stops_before_the_cap(self):
        for _ in range(3):
            self.slip()
        text, m, _ = self.run_cmd('--run', '--limit', '3', '--max-cost-usd', '0.015')
        self.assertIn('STOPPED: the next document could pass the cap', text)
        self.assertEqual(m.call_count, 1)
