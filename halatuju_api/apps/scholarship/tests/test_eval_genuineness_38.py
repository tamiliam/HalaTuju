"""OCR-16: the paid genuineness eval command. Gemini and Storage are mocked (no network); synthetic rows only
(IC 000000-00-0000). It must make no AI call in a dry run, write nothing, keep to its caps and stops, and print
counts and document ids only."""
from contextlib import ExitStack
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.scholarship.genuineness import ic
from apps.scholarship.management.commands import eval_genuineness_38 as ev
from apps.scholarship.models import ApplicantDocument, ApplicantDocumentOcrText
from apps.scholarship.read_errors import CASCADE_FAILED, DOCUMENT_FAILED, UNPARSEABLE_RESPONSE
from apps.scholarship.tests.factories import make_application, make_cohort, make_student

SEAM = 'apps.scholarship.vision._call_gemini_json'
IMG = 'apps.scholarship.vision._as_image_for_gemini'
FETCH = 'apps.scholarship.vision._fetch_image_bytes'
SECRET_REASON = 'MODEL-FREE-TEXT-NEVER-PRINTED'
IC_NUMBER = '000000-00-0000'
STORED_REASON = 'STORED-REASON-NEVER-PRINTED'


def _ic_answer(verdict='genuine'):
    return {**{m: True for m in ic._IC_GENUINENESS_MARKERS}, 'verdict': verdict, 'reason': SECRET_REASON}


class _Docs(TestCase):
    def setUp(self):
        self.cohort = make_cohort()

    def doc(self, doc_type='ic', status='genuine', verification='pending', **vf_extra):
        app = make_application(cohort=self.cohort, student=make_student())
        vf = {'authenticity': {'status': status, 'reason': STORED_REASON, 'markers': {}}, 'fields': {'nric': IC_NUMBER},
              **vf_extra}
        return ApplicantDocument.objects.create(
            application=app, doc_type=doc_type, storage_path=f'test/{doc_type}', content_type='image/jpeg',
            verification_status=verification, vision_fields=vf)

    def run_cmd(self, *args, seam=None, fetch=b'img'):
        out = StringIO()
        with ExitStack() as stack:
            m = stack.enter_context(patch(SEAM, **(seam or {'return_value': _ic_answer()})))
            f = stack.enter_context(patch(FETCH, return_value=fetch))
            stack.enter_context(patch(IMG, return_value=(b'i', 'image/jpeg')))
            call_command('eval_genuineness_38', *args, stdout=out)
        return out.getvalue(), m, f


class TestTheDryRun(_Docs):
    def test_counts_only_no_fetch_no_ai_call(self):
        for _ in range(3):
            self.doc('ic')
        text, seam, fetch = self.run_cmd('--checks', 'ic')
        seam.assert_not_called()
        fetch.assert_not_called()
        self.assertIn('DRY RUN', text)
        self.assertIn('ic: 3 to read', text)
        self.assertIn('estimated cost: up to US$0.05', text)


class TestTheArguments(_Docs):
    def test_run_needs_limit_and_cap_within_the_ceiling(self):
        bad = [('--run',), ('--run', '--limit', '5'), ('--run', '--max-cost-usd', '1'),
               ('--run', '--limit', '5', '--max-cost-usd', '5.01'), ('--run', '--limit', '5', '--max-cost-usd', '0'),
               ('--run', '--limit', '5', '--max-cost-usd', 'x'), ('--limit', str(ev.MAX_LIMIT + 1)),
               ('--model', 'gemini-2.5-flash'), ('--checks', 'ic,nope'), ('--fake-ids', 'a,b')]
        for args in bad:
            with self.subTest(args=args), self.assertRaises(CommandError):
                self.run_cmd(*args)


class TestTheRun(_Docs):
    def test_writes_nothing_and_meters_a_platform_row(self):
        docs = [self.doc('ic'), self.doc('str'), self.doc('results_slip', status='genuine')]
        docs[2].vision_fields['authenticity'].update({'probability': 0.9, 'present': ['QR CODE'], 'missing': []})
        ApplicantDocument.objects.filter(pk=docs[2].pk).update(vision_fields=docs[2].vision_fields)
        before = list(ApplicantDocument.objects.order_by('pk').values())
        answers = {'ic': _ic_answer(), 'str': {'is_official': True, 'is_expected_type': True, 'doc_seen': 'x',
                                               'verdict': 'genuine', 'reason': SECRET_REASON}}

        def seam(prompt, schema, **k):
            props = schema['properties']
            if 'has_qr_code' in props:
                return {'has_qr_code': True, 'has_jata_negara_crest': True}
            if 'is_sample' in props:
                return {'is_sample': False, 'reason': SECRET_REASON}
            return answers['str'] if 'is_official' in props else answers['ic']

        with patch('apps.scholarship.usage.usage_context', wraps=ev.usage.usage_context) as ctx:
            text, m, _ = self.run_cmd('--run', '--limit', '50', '--max-cost-usd', '1.00', seam={'side_effect': seam})
        self.assertEqual(list(ApplicantDocument.objects.order_by('pk').values()), before)
        self.assertFalse(ApplicantDocumentOcrText.objects.exists())
        self.assertTrue(m.called)
        for call in ctx.call_args_list:
            self.assertEqual(call.kwargs, {'source': ev.USAGE_SOURCE})     # no application, no organisation
        for check in ('ic', 'supporting', 'results_slip'):
            self.assertIn(f'[{check}] docs 1', text)
        self.assertEqual(text.count(', error 0,'), 4)            # the write guard never tripped
        self.assertIn('[ic] docs 1, calls 1, answered 1', text)
        self.assertIn('marker_agree 1', text)

    def test_the_cap_stops_before_the_document_that_could_pass_it(self):
        for _ in range(4):
            self.doc('ic')
        text, m, _ = self.run_cmd('--run', '--checks', 'ic', '--limit', '4', '--max-cost-usd', '0.02')
        self.assertEqual(m.call_count, 1)
        self.assertIn('STOPPED: the next document could pass the cap', text)

    def test_five_service_errors_in_a_row_stop_the_run(self):
        for _ in range(7):
            self.doc('ic')
        text, m, _ = self.run_cmd('--run', '--checks', 'ic', '--limit', '7', '--max-cost-usd', '1.00',
                                  seam={'return_value': {'_error': CASCADE_FAILED + ': 429'}})
        self.assertEqual(m.call_count, ev.FAIL_FAST)
        self.assertIn('STOPPED: 5 AI service errors in a row', text)
        self.assertIn('service_error 5', text)

    def test_five_failed_fetches_stop_the_run(self):
        for _ in range(6):
            self.doc('ic')
        text, m, _ = self.run_cmd('--run', '--checks', 'ic', '--limit', '6', '--max-cost-usd', '1.00', fetch=None)
        m.assert_not_called()
        self.assertIn('fetches in a row failed', text)

    def test_the_gates_and_malformed_answers_are_counted_by_id(self):
        accepted = self.doc('ic', verification='verified')
        fake = self.doc('ic', status='suspect')
        broken = self.doc('ic', verification='verified')
        replies = {accepted.pk: _ic_answer('suspect'), fake.pk: _ic_answer('genuine'),
                   broken.pk: {**_ic_answer(), 'verdict': 'perhaps'}}
        order = []

        def seam(prompt, schema, **k):
            return replies[order[-1]]

        real_one = ev.Command._one

        def one(self_, tally, trace, streak, check, pk, *a):
            order.append(pk)
            return real_one(self_, tally, trace, streak, check, pk, *a)

        with patch.object(ev.Command, '_one', one):
            text, m, _ = self.run_cmd('--run', '--checks', 'ic', '--limit', '3', '--max-cost-usd', '1.00',
                                      '--fake-ids', str(fake.pk), seam={'side_effect': seam})
        self.assertEqual(order[0], fake.pk)                                   # known fakes first
        self.assertIn(f'[ic] new_not_genuine_on_accepted ids: {accepted.pk}', text)
        self.assertIn(f'[ic] genuine_on_known_fake ids: {fake.pk}', text)
        self.assertIn(f'[ic] malformed_after_retry ids: {broken.pk}', text)
        self.assertIn('new_not_genuine_on_accepted 1, genuine_on_known_fake 1', text)
        self.assertEqual(m.call_count, 4)                                     # the malformed one retried once

    def test_the_output_carries_no_content(self):
        self.doc('ic')
        text, _m, _ = self.run_cmd('--run', '--checks', 'ic', '--limit', '1', '--max-cost-usd', '1.00')
        for secret in (SECRET_REASON, STORED_REASON, IC_NUMBER, 'GEMINI_API_KEY'):
            self.assertNotIn(secret, text)


def _by_schema(ic_answer=None, sample=None, visual=None, doc=None):
    """A seam that answers by the schema it is asked with (each check has its own keys)."""
    def seam(prompt, schema, **k):
        props = schema['properties']
        if 'has_qr_code' in props:
            return visual if visual is not None else {'has_qr_code': True, 'has_jata_negara_crest': True}
        if 'is_sample' in props:
            return sample if sample is not None else {'is_sample': False, 'reason': SECRET_REASON}
        if 'is_official' in props:
            return doc or {'is_official': True, 'is_expected_type': True, 'doc_seen': 'x', 'verdict': 'genuine',
                           'reason': SECRET_REASON}
        return ic_answer or _ic_answer()
    return {'side_effect': seam}


class TestReviewRound1(_Docs):
    """Review r1: fakes read only by their own check, the slip scored as live, the gates, refusals, cost."""
    RUN = ('--run', '--limit', '50', '--max-cost-usd', '1.00')

    def test_a_typed_fake_ic_is_never_read_by_the_sample_check(self):
        fake = self.doc('ic', status='suspect', verification='rejected')
        text, _m, _ = self.run_cmd(*self.RUN, '--checks', 'ic,sample', '--fake-ids', str(fake.pk),
                                   seam=_by_schema(ic_answer=_ic_answer('suspect')))
        self.assertIn('sample: 0 to read', text)
        self.assertIn('sample new_not_genuine_on_accepted 0, genuine_on_known_fake 0', text)
        self.assertIn('ic new_not_genuine_on_accepted 0, genuine_on_known_fake 0', text)

    def test_sample_fakes_go_to_the_sample_check_only(self):
        fake = self.doc('str', sample_check_version='1.0.0')
        text, _m, _ = self.run_cmd(*self.RUN, '--checks', 'supporting,sample', '--sample-fake-ids', str(fake.pk),
                                   seam=_by_schema())
        self.assertIn(f'[sample] genuine_on_known_fake ids: {fake.pk}', text)
        self.assertIn('supporting new_not_genuine_on_accepted 0, genuine_on_known_fake 0', text)

    def test_a_fake_no_chosen_check_reads_is_listed(self):
        stray = self.doc('offer_letter')
        text, _m, _ = self.run_cmd('--checks', 'ic', '--fake-ids', str(stray.pk))
        self.assertIn(f'known fakes no chosen check reads: {stray.pk}', text)

    def _slip(self, verification='verified', text=None):
        d = self.doc('results_slip', verification=verification)
        d.vision_fields['authenticity'].update({'probability': 0.9, 'present': ['QR CODE', 'JATA NEGARA'],
                                                'missing': []})
        ApplicantDocument.objects.filter(pk=d.pk).update(vision_fields=d.vision_fields)
        if text:
            ApplicantDocumentOcrText.objects.create(document=d, text=text, source='vision_ocr', reader='test',
                                                    stored_at=d.uploaded_at)
        return d

    def test_a_slip_with_no_markers_is_scored_as_live_with_both_absent(self):
        self._slip(text='SIJIL PELAJARAN MALAYSIA 000000-00-0000')
        bad = {'has_qr_code': 'yes', 'has_jata_negara_crest': True}          # malformed twice: no markers
        with patch('apps.scholarship.genuineness.results_doc.signature_genuineness',
                   return_value={'status': 'suspect', 'probability': 0.4}) as sg:
            text, m, _ = self.run_cmd(*self.RUN, '--checks', 'results_slip', seam=_by_schema(visual=bad))
        self.assertEqual(m.call_count, 2)
        self.assertEqual((sg.call_args.kwargs['has_qr'], sg.call_args.kwargs['has_crest']), (False, False))
        self.assertIn('rescored_from_text 1, not_gated_no_text 0', text)
        self.assertIn('[results_slip] new_not_genuine_on_accepted ids:', text)

    def test_a_slip_without_stored_text_is_counted_not_gated_and_its_markers_compared(self):
        slip = self._slip()
        text, _m, _ = self.run_cmd(*self.RUN, '--checks', 'results_slip',
                                   seam=_by_schema(visual={'has_qr_code': False, 'has_jata_negara_crest': True}))
        self.assertIn(f'[results_slip] not_gated_no_text ids: {slip.pk}', text)
        self.assertIn('marker_agree 1, marker_disagree 1, marker_lost_on_accepted 1', text)
        self.assertIn('results_slip new_not_genuine_on_accepted 0, genuine_on_known_fake 0, '
                      'marker_lost_on_accepted 1', text)

    def test_every_accepted_document_flagged_counts_whatever_its_stored_value(self):
        was_suspect = self.doc('ic', status='suspect', verification='verified')
        was_genuine = self.doc('ic', verification='verified')
        text, _m, _ = self.run_cmd(*self.RUN, '--checks', 'ic', seam=_by_schema(ic_answer=_ic_answer('suspect')))
        self.assertIn('new_not_genuine_on_accepted 2, new_not_genuine_on_accepted_stored_genuine 1', text)
        self.assertIn(f'[ic] new_not_genuine_on_accepted ids: {was_suspect.pk},{was_genuine.pk}', text)

    def test_malformed_on_fakes_and_on_rejected_is_on_the_gates_line(self):
        fake, rejected = self.doc('ic'), self.doc('ic', verification='rejected')
        text, _m, _ = self.run_cmd(*self.RUN, '--checks', 'ic', '--fake-ids', str(fake.pk),
                                   seam=_by_schema(ic_answer={**_ic_answer(), 'verdict': 'perhaps'}))
        self.assertIn('(also: malformed_on_known_fake 1, malformed_on_rejected 1)', text)
        self.assertIn(f'[ic] malformed_on_rejected ids: {rejected.pk}', text)

    def test_two_refusals_count_as_document_refused(self):
        self.doc('ic')
        text, m, _ = self.run_cmd(*self.RUN, '--checks', 'ic', seam={'return_value': {'_error': DOCUMENT_FAILED + ': x'}})
        self.assertEqual(m.call_count, 2)
        self.assertIn('malformed_after_retry 0, document_refused 1', text)

    def test_reported_tokens_meter_the_cap_with_the_flat_price_as_floor(self):
        from apps.scholarship import usage
        for _ in range(3):
            self.doc('ic')

        def costly(prompt, schema, **k):
            usage.record_usage(usage.GEMINI, model=k['models'][0], input_tokens=10, output_tokens=200_000)
            return _ic_answer()
        text, m, _ = self.run_cmd(*self.RUN, '--checks', 'ic', seam={'side_effect': costly})
        self.assertEqual(m.call_count, 1)                    # US$1.00 of tokens: the next one could pass the cap
        self.assertIn('charged up to US$1.0000', text)
        self.assertIn('STOPPED: the next document could pass the cap', text)
        self.assertEqual(ev.call_cost((10, 20)), ev.USD_PER_CALL_38)       # tiny token counts: the floor
        self.assertEqual(ev.call_cost(None), ev.USD_PER_CALL_38)

    def test_the_forced_model_is_sent_lower_case(self):
        self.doc('ic')
        _t, m, _ = self.run_cmd(*self.RUN, '--checks', 'ic', '--model', 'Gemini-3.8-Flash')
        self.assertEqual(m.call_args.kwargs['models'], ['gemini-3.8-flash'])

    def test_the_runbook_suggests_two_dollars_and_names_the_assumed_price(self):
        help_text = ev.Command().create_parser('manage.py', 'eval_genuineness_38').format_help()
        self.assertIn('--max-cost-usd 2.00', ' '.join(help_text.split()))
        self.assertIn('ASSUMED upper bound of US$0.008', ' '.join(help_text.split()))
        self.assertEqual(ev.MAX_COST_USD, Decimal('5.00'))


class TestReviewRound2(_Docs):
    """Review r2: a known fake with no verdict fails the gates; unreadable JSON twice is malformed, not refused."""
    RUN = ('--run', '--limit', '50', '--max-cost-usd', '1.00')
    UNREADABLE = {'_error': f'{DOCUMENT_FAILED}: gemini-3.8-flash: {UNPARSEABLE_RESPONSE}: Expecting value'}

    def test_a_known_fake_refused_twice_is_unanswered_and_fails_the_gates(self):
        fake = self.doc('ic', status='suspect')
        text, m, _ = self.run_cmd(*self.RUN, '--checks', 'ic', '--fake-ids', str(fake.pk),
                                  seam={'return_value': {'_error': DOCUMENT_FAILED + ': x'}})
        self.assertEqual(m.call_count, 2)
        self.assertIn(f'genuine_on_known_fake 0, unanswered_known_fake 1 [{fake.pk}]', text)
        self.assertIn(f'[ic] unanswered_known_fake ids: {fake.pk}', text)
        self.assertIn('GATES NOT MET: ic unanswered_known_fake', text)

    def test_a_known_fake_whose_fetch_failed_is_unanswered(self):
        fake = self.doc('ic')
        text, m, _ = self.run_cmd(*self.RUN, '--checks', 'ic', '--fake-ids', str(fake.pk), fetch=None)
        m.assert_not_called()
        self.assertIn(f'unanswered_known_fake 1 [{fake.pk}]', text)
        self.assertIn('GATES NOT MET', text)

    def test_unanswered_counts_every_reason_and_answered_fakes_do_not(self):
        refused, malformed, erred, answered = (self.doc('ic') for _ in range(4))
        replies = {refused.pk: {'_error': DOCUMENT_FAILED + ': x'}, malformed.pk: {**_ic_answer(), 'verdict': 'x'},
                   erred.pk: {'_error': CASCADE_FAILED + ': 500'}, answered.pk: _ic_answer('suspect')}
        order = []
        real_one = ev.Command._one

        def one(self_, tally, trace, streak, check, pk, *a):
            order.append(pk)
            return real_one(self_, tally, trace, streak, check, pk, *a)

        ids = ','.join(str(d.pk) for d in (refused, malformed, erred, answered))
        with patch.object(ev.Command, '_one', one):
            text, _m, _ = self.run_cmd(*self.RUN, '--checks', 'ic', '--fake-ids', ids,
                                       seam={'side_effect': lambda *a, **k: replies[order[-1]]})
        got = text.split('[ic] unanswered_known_fake ids: ')[1].split('\n')[0]
        self.assertEqual(sorted(int(x) for x in got.split(',')), sorted([refused.pk, malformed.pk, erred.pk]))
        self.assertIn('unanswered_known_fake 3 [', text)
        self.assertIn('genuine_on_known_fake 0', text)

    def test_all_fakes_answered_not_genuine_meets_the_gates(self):
        fake = self.doc('ic', status='suspect')
        text, _m, _ = self.run_cmd(*self.RUN, '--checks', 'ic', '--fake-ids', str(fake.pk),
                                   seam=_by_schema(ic_answer=_ic_answer('suspect')))
        self.assertIn('genuine_on_known_fake 0, unanswered_known_fake 0 (also:', text)
        self.assertIn('known_fake_no_check_reads 0', text)
        self.assertTrue(text.rstrip().endswith('GATES MET'))

    def test_a_known_fake_no_chosen_check_reads_fails_the_gates(self):
        stray = self.doc('offer_letter')
        self.doc('ic')
        text, _m, _ = self.run_cmd(*self.RUN, '--checks', 'ic', '--fake-ids', str(stray.pk))
        self.assertIn(f'known_fake_no_check_reads 1 [{stray.pk}]', text)
        self.assertIn('GATES NOT MET: known_fake_no_check_reads', text)

    def test_unreadable_json_twice_is_malformed_on_the_fake_and_the_rejected_row(self):
        fake, rejected = self.doc('ic'), self.doc('ic', verification='rejected')
        text, m, _ = self.run_cmd(*self.RUN, '--checks', 'ic', '--fake-ids', str(fake.pk),
                                  seam={'return_value': self.UNREADABLE})
        self.assertEqual(m.call_count, 4)                     # each retried once
        self.assertIn('malformed_after_retry 2, document_refused 0', text)
        self.assertIn('(also: malformed_on_known_fake 1, malformed_on_rejected 1)', text)

    def test_the_outcome_labels(self):
        from apps.scholarship.genuineness import ai_model
        self.assertEqual(ev.outcome_of(self.UNREADABLE), 'malformed_after_retry')
        self.assertEqual(ev.outcome_of({'_error': f'{DOCUMENT_FAILED}: m: {ai_model.MALFORMED}: verdict'}),
                         'malformed_after_retry')
        self.assertEqual(ev.outcome_of({'_error': DOCUMENT_FAILED + ': m: blocked'}), 'document_refused')
        self.assertEqual(ev.outcome_of({'_error': CASCADE_FAILED + ': m: 429'}), 'service_error')
        self.assertEqual(ev.outcome_of({'verdict': 'genuine'}), '')


class TestTheSamplePlan(_Docs):
    def test_fakes_then_rejected_then_flagged_then_newest(self):
        newest = self.doc('ic')
        flagged = self.doc('ic', status='suspect')
        rejected = self.doc('ic', verification='rejected')
        fake = self.doc('ic')
        unscored = self.doc('ic', status='')
        got = ev.genuineness_sample(['ic'], {fake.pk})['ic']
        self.assertEqual(got, [fake.pk, rejected.pk, flagged.pk, newest.pk])
        self.assertNotIn(unscored.pk, got)

    def test_interleave_keeps_every_check(self):
        self.assertEqual(ev.interleave({'ic': [1, 2], 'sample': [3]}), [('ic', 1), ('sample', 3), ('ic', 2)])
