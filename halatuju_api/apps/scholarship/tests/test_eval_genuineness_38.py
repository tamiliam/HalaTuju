"""OCR-16: the paid genuineness eval command. Gemini and Storage are mocked (no network); synthetic rows only
(IC 000000-00-0000). It must make no AI call in a dry run, write nothing, keep to its caps and stops, and print
counts and document ids only."""
from contextlib import ExitStack
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.scholarship.genuineness import ic
from apps.scholarship.management.commands import eval_genuineness_38 as ev
from apps.scholarship.models import ApplicantDocument, ApplicantDocumentOcrText
from apps.scholarship.read_errors import CASCADE_FAILED
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
