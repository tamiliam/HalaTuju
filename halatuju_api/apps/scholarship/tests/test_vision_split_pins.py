"""Audit sprint A3.1 (TD-361 part): pins written BEFORE ``vision.py`` became the ``vision/`` package.

The split moved code and changed none, so every test here was green on the single file and must
stay green on the package. They pin the paths the move touched hardest and the older suites
reach least: each branch of the field-extraction read (``_run_field_extraction_impl``, which the
split broke into helpers), each genuineness branch it stores, the outage / clobber handling,
the PDF intake paths and the student-facing judge. Plus one guard: every name the old module
defined still resolves on ``apps.scholarship.vision``, and a patch of a seam there still reaches
every caller.

⚠ NO MODEL IS EVER CALLED. Storage (``_fetch_image_bytes``), Cloud Vision (``_vision_words`` /
``_vision_document_text``) and Gemini (``_call_gemini_json`` / ``extract_document_fields``) are
patched on the package in every test that could reach them.
"""
from contextlib import ExitStack
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import vision
from apps.scholarship.read_errors import OCR_SERVICE_FAILED
from apps.scholarship.tests.factories import create_document, make_application, make_student

V = 'apps.scholarship.vision.'
NAME = 'MUTHU A/L RAMAN'
NRIC = '030101-14-1234'
OUTAGE = 'All AI models failed: 503 overloaded'

#: Every top-level name ``apps/scholarship/vision.py`` defined or imported on 2026-11-09 (8e8c77b),
#: before the split. Each must still resolve on the package — importers and patch targets use them.
OLD_NAMES = (
    'GEMINI_EXTRACT_DOC_TYPES', 'IC_SECOND_OPINION_ERROR', 'IC_SECOND_OPINION_UNTIL', 'MY_STATES',
    'OCR_SERVICE_FAILED', 'OFFER_SCHEMA', 'UNPARSEABLE_RESPONSE', '_ADDRESS_LABEL_TOKENS',
    '_ADDRESS_PREFIX_NOISE', '_ADDR_ABBREV', '_ADDR_GENERIC', '_DOC_HINTS', '_DOC_NAME_LABEL_RE',
    '_EX_KEPT', '_FIELD_SCHEMAS', '_GENUINENESS_DOCS', '_GLUED_HEADER_FRAGMENTS', '_GLUED_MARKER_AFTER',
    '_GLUED_MARKER_BEFORE', '_HIGHER_HINT', '_HIGHER_SCHEMA', '_IC_GEMINI_PROMPT', '_IC_GEMINI_SCHEMA',
    '_LEADING_PARENTAGE', '_MANGLED_MARKERS', '_MIN_PDF_TEXT', '_MONTHS', '_MYKAD_HEADER_TOKENS',
    '_MY_POSTCODE', '_NAME_FIELD', '_NAME_NOISE', '_NON_NAME_MARKERS', '_NRIC_REGEX', '_PARENTAGE_MARKER',
    '_PDF_MAGIC', '_RD_MONTHS', '_RD_MONTH_NUM', '_RD_TIME', '_RD_WEEKDAY', '_ROAD_HEAD', '_STR',
    '_STR_SOURCE', '_TRAILING_PARENTAGE', '_WARNING_VOICE', '_addr_norm', '_any_field_filled',
    '_as_image_for_gemini', '_bank_verdict', '_call_gemini_json', '_canonical_name_seq', '_canonical_nric',
    '_continuation_surname', '_doc_schema', '_doc_usage_ctx', '_drop_expected_warnings', '_extract_address',
    '_extract_name', '_extract_nric', '_extract_slip_deterministic', '_fetch_image_bytes', '_fold_name_token',
    '_gemini_ic_second_opinion', '_glued_equal', '_guard_garbled', '_higher_extract', '_house_numbers',
    '_is_card_label_line', '_is_likely_state', '_is_name_line', '_is_pdf', '_levenshtein',
    '_lock_nric_if_confirmed', '_looks_like_non_name', '_merge_ic_reads', '_name_looks_garbled',
    '_norm_house_no', '_normalise_reporting_date', '_offer_context', '_parse_dob', '_pdf_first_page_png',
    '_pdf_text_layer', '_preceding_givenname', '_read_approval', '_replace_trailing_marker',
    '_run_field_extraction_impl', '_sanitize_extracted_fields', '_should_gemini_ic', '_split_glued_markers',
    '_street_name_tokens', '_strip_name_label', '_tokens_close', '_trailing_marker_canonical',
    '_usable_text_layer', '_vision_document_text', '_vision_words', '_with_broken_name_parts',
    '_with_trailing_surname', 'address_match', 'address_present', 'canonical_name_tokens', 'cascade_failure',
    'doc_genuineness', 'doc_student_verdict', 'document_failure', 'extract_document_fields', 'extract_mykad',
    'extract_text', 'ic_genuineness', 'is_ai_service_error', 'is_ocr_service_error',
    'keep_stored_authenticity', 'model_rejected_document', 'name_match', 'name_present', 'nric_close',
    'nric_dob_agrees', 'nric_match', 'ocr_document', 'ocr_document_full', 'patronymic_reversed',
    'read_deferred', 'read_text_document', 'reference_names', 'relationship_name_match',
    'run_field_extraction_for_document', 'run_vision_for_document', 'run_vision_match_for_document',
)


class TestEveryOldNameStillResolves(SimpleTestCase):
    def test_the_package_answers_for_every_name_the_module_had(self):
        missing = [n for n in OLD_NAMES if not hasattr(vision, n)]
        self.assertEqual(missing, [], 'apps.scholarship.vision lost these names in the split')


def _ex(fields=None, **kw):
    """A read in the shape `extract_document_fields` returns."""
    return {'fields': dict(fields or {}), 'warnings': [], 'error': '', **kw}


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.app = make_application(student=make_student(name=NAME, nric=NRIC))

    def doc(self, doc_type, **kw):
        kw.setdefault('storage_path', 'blob')
        kw.setdefault('content_type', 'image/jpeg')
        return create_document(application=self.app, doc_type=doc_type, **kw)

    def run_impl(self, doc, ocr=None, **kw):
        return vision.run_field_extraction_for_document(doc, names=[NAME], ocr=ocr, **kw)

    def seams(self, stack, *, image=b'IMG', text='SOME TEXT', ocr_error=None, extract=None):
        """Patch Storage, OCR and Gemini on the package; return the mocks by name."""
        m = {
            'fetch': stack.enter_context(mock.patch(V + '_fetch_image_bytes', return_value=image)),
            'ocr': stack.enter_context(mock.patch(V + 'ocr_document',
                                                  return_value={'text': text, 'error': ocr_error})),
            'extract': stack.enter_context(mock.patch(V + 'extract_document_fields',
                                                      side_effect=extract or (lambda *a, **k: _ex({'name': NAME})))),
            'words': stack.enter_context(mock.patch(V + '_vision_words',
                                                    return_value={'words': [], 'text': '', 'error': 'no image'})),
            'gemini': stack.enter_context(mock.patch(V + '_call_gemini_json',
                                                     side_effect=AssertionError('no model call in a pin'))),
        }
        return m


# ── 1. The read, branch by branch (genuineness off) ────────────────────────────────────────────


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TestGenericLabelBranch(_Base):
    def test_no_label_parse_goes_to_gemini_on_the_text_and_keeps_listed_keys(self):
        with ExitStack() as s:
            m = self.seams(s, text='BIL ELEKTRIK', extract=lambda *a, **k: _ex(
                {'name': NAME}, parser_version='p1', not_kept='x'))
            s.enter_context(mock.patch('apps.scholarship.doc_parse.parse_by_labels', return_value=None))
            doc = self.doc('epf')
            r = self.run_impl(doc)
        m['extract'].assert_called_once_with('BIL ELEKTRIK', 'epf')
        self.assertEqual(r, {'fields': {'name': NAME}, 'warnings': [], 'parser_version': 'p1',
                             'student_verdict': 'ok', 'capture': 'ai', 'error': ''})
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields, r)
        self.assertIsNotNone(doc.vision_fields_run_at)

    def test_a_label_parse_goes_through_the_epf_fallback(self):
        with ExitStack() as s:
            m = self.seams(s, text='KWSP PENYATA')
            s.enter_context(mock.patch('apps.scholarship.doc_parse.parse_by_labels',
                                       return_value={'name': NAME}))
            fb = s.enter_context(mock.patch(
                'apps.scholarship.epf_contribution_fallback.deterministic_or_epf_fallback',
                return_value=_ex({'name': NAME}, capture='deterministic')))
            r = self.run_impl(self.doc('epf'))
        self.assertEqual(fb.call_args.args[:3], ('epf', {'name': NAME}, 'KWSP PENYATA'))
        self.assertIs(fb.call_args.args[3], m['extract'])        # the package seam is what is handed on
        m['extract'].assert_not_called()
        self.assertEqual(r['capture'], 'deterministic')
        self.assertEqual(r['student_verdict'], 'ok')

    def test_ocr_outage_is_ours_and_named_so(self):
        with ExitStack() as s:
            self.seams(s, text='', ocr_error='503 Service Unavailable')
            r = self.run_impl(self.doc('epf'))
        self.assertTrue(r['error'].startswith(f'{OCR_SERVICE_FAILED}: 503'))
        self.assertEqual(r['fields'], {})
        self.assertEqual(r['student_verdict'], 'review_manually')
        self.assertTrue(r['service_error'])

    def test_empty_text_is_unreadable(self):
        with ExitStack() as s:
            m = self.seams(s, text='   ')
            r = self.run_impl(self.doc('epf'))
        m['extract'].assert_not_called()
        self.assertEqual(r, {'fields': {}, 'warnings': [], 'student_verdict': 'unreadable',
                             'capture': 'ai', 'error': 'no text read', 'service_error': False})

    def test_ai_outage_is_a_deferred_read_not_unreadable(self):
        with ExitStack() as s:
            self.seams(s, extract=lambda *a, **k: {'fields': {}, 'warnings': [], 'error': OUTAGE})
            s.enter_context(mock.patch('apps.scholarship.doc_parse.parse_by_labels', return_value=None))
            doc = self.doc('epf')
            r = self.run_impl(doc)
        self.assertEqual(r['student_verdict'], 'review_manually')
        self.assertTrue(r['service_error'])
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['error'], OUTAGE)      # first read: stored

    def test_ai_outage_never_replaces_a_real_stored_verdict(self):
        prior = {'fields': {}, 'warnings': [], 'student_verdict': 'unreadable', 'error': 'no text read'}
        with ExitStack() as s:
            self.seams(s, extract=lambda *a, **k: {'fields': {}, 'warnings': [], 'error': OUTAGE})
            s.enter_context(mock.patch('apps.scholarship.doc_parse.parse_by_labels', return_value=None))
            doc = self.doc('epf', vision_fields=dict(prior))
            r = self.run_impl(doc)
        self.assertTrue(r['stale_kept'])
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields, prior)
        self.assertIsNone(doc.vision_fields_run_at)


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TestResultsSlipBranch(_Base):
    def test_a_certificate_reads_first(self):
        with ExitStack() as s:
            m = self.seams(s, text='LAYAK DIANUGERAHI')
            cert = s.enter_context(mock.patch('apps.scholarship.spm_cert_parse.parse_spm_cert',
                                              return_value={'name': NAME}))
            slip = s.enter_context(mock.patch(V + '_extract_slip_deterministic'))
            r = self.run_impl(self.doc('results_slip'))
        cert.assert_called_once_with('LAYAK DIANUGERAHI', None, b'IMG')
        slip.assert_not_called()
        m['extract'].assert_not_called()
        self.assertEqual((r['fields'], r['capture'], r['student_verdict']), ({'name': NAME}, 'deterministic', 'ok'))

    def test_the_slip_reads_deterministically_next(self):
        with ExitStack() as s:
            self.seams(s)
            s.enter_context(mock.patch('apps.scholarship.spm_cert_parse.parse_spm_cert', return_value=None))
            slip = s.enter_context(mock.patch(V + '_extract_slip_deterministic',
                                              return_value=(_ex({'slip_name': NAME}), {'reason': 'ok'})))
            words = [{'text': 'A'}]
            r = self.run_impl(self.doc('results_slip'),
                              ocr={'text': 'T', 'words': words, 'image': b'OCRIMG', 'error': None})
        self.assertEqual(slip.call_args.args[1], b'OCRIMG')           # the ocr dict's bytes, not a refetch
        self.assertEqual(slip.call_args.kwargs, {'words': words})
        self.assertEqual(r['capture'], 'deterministic')

    def test_no_lock_falls_back_to_gemini_on_the_image_with_the_diag_and_the_year(self):
        with ExitStack() as s:
            m = self.seams(s, text='SPM 2024', extract=lambda *a, **k: _ex({'name': NAME, 'exam': 'SPM'}))
            s.enter_context(mock.patch('apps.scholarship.spm_cert_parse.parse_spm_cert', return_value=None))
            s.enter_context(mock.patch(V + '_extract_slip_deterministic',
                                       return_value=(None, {'reason': 'parse_none'})))
            year = s.enter_context(mock.patch('apps.scholarship.spm_cert_parse.ensure_exam_year',
                                              return_value='SPM 2024'))
            r = self.run_impl(self.doc('results_slip'))
        m['extract'].assert_called_once_with('', 'results_slip', image=b'IMG', content_type='image/jpeg')
        year.assert_called_once_with('SPM', 'SPM 2024')
        self.assertEqual(r['fields'], {'name': NAME, 'exam': 'SPM 2024', '_slip_ocr_diag': {'reason': 'parse_none'}})
        self.assertEqual(r['capture'], 'ai')

    def test_no_image_falls_back_to_gemini_on_the_text(self):
        with ExitStack() as s:
            m = self.seams(s, image=None, text='SLIP TEXT')
            s.enter_context(mock.patch('apps.scholarship.spm_cert_parse.parse_spm_cert', return_value=None))
            r = self.run_impl(self.doc('results_slip'))
        m['extract'].assert_called_once_with('SLIP TEXT', 'results_slip')
        self.assertEqual(r['fields']['_slip_ocr_diag'], {'reason': 'no_image'})


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TestOfferBranch(_Base):
    def test_an_exact_read_wins(self):
        with ExitStack() as s:
            m = self.seams(s, text='SURAT TAWARAN')
            exact = s.enter_context(mock.patch('apps.scholarship.offer_exact.exact_offer_read',
                                               return_value=_ex({'name': NAME}, capture='deterministic',
                                                                offer_reader_version='x1')))
            doc = self.doc('offer_letter', vision_fields={'fields': {'old': 1}})
            r = self.run_impl(doc)
        exact.assert_called_once_with('SURAT TAWARAN', prior={'fields': {'old': 1}}, image=b'IMG',
                                      content_type='image/jpeg', profile_nric=NRIC, page1_ocr='SURAT TAWARAN')
        m['extract'].assert_not_called()
        self.assertEqual((r['capture'], r['offer_reader_version']), ('deterministic', 'x1'))

    def test_no_exact_read_goes_to_the_image_reader_with_the_ic_context(self):
        with ExitStack() as s:
            m = self.seams(s, text='OFFER')
            s.enter_context(mock.patch('apps.scholarship.offer_exact.exact_offer_read', return_value=None))
            r = self.run_impl(self.doc('offer_letter'), ocr={'text': 'FROM OCR', 'image': b'OI', 'error': None})
        m['extract'].assert_called_once_with('', 'offer_letter', image=b'OI', content_type='image/jpeg',
                                             profile_nric=NRIC, page1_ocr='FROM OCR')
        m['ocr'].assert_not_called()
        self.assertEqual(r['capture'], 'ai')

    def test_no_image_reads_the_text(self):
        with ExitStack() as s:
            m = self.seams(s, image=None, text='OFFER TEXT')
            s.enter_context(mock.patch('apps.scholarship.offer_exact.exact_offer_read', return_value=None))
            self.run_impl(self.doc('offer_letter'))
        m['extract'].assert_called_once_with('OFFER TEXT', 'offer_letter', profile_nric=NRIC,
                                             page1_ocr='OFFER TEXT')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TestBirthCertificateBranch(_Base):
    def test_word_boxes_from_the_shared_read_parse_without_a_vision_call(self):
        with ExitStack() as s:
            m = self.seams(s)
            bc = s.enter_context(mock.patch('apps.scholarship.bc_parse.parse_bc', return_value={'name': NAME}))
            words = [{'text': 'NAMA'}]
            r = self.run_impl(self.doc('birth_certificate'),
                              ocr={'text': 'T', 'words': words, 'image': b'I', 'error': None})
        bc.assert_called_once_with(words)
        m['words'].assert_not_called()
        self.assertEqual(r['capture'], 'deterministic')

    def test_no_parse_falls_back_to_gemini_on_the_image(self):
        with ExitStack() as s:
            m = self.seams(s)
            m['words'].return_value = {'words': [{'text': 'X'}], 'error': None}
            s.enter_context(mock.patch('apps.scholarship.bc_parse.parse_bc', return_value=None))
            r = self.run_impl(self.doc('birth_certificate'))
        m['words'].assert_called_once_with(b'IMG', 'image/jpeg')
        m['extract'].assert_called_once_with('', 'birth_certificate', image=b'IMG', content_type='image/jpeg')
        self.assertEqual(r['capture'], 'ai')

    def test_no_image_reads_the_ocr_text(self):
        with ExitStack() as s:
            m = self.seams(s, image=None, text='SIJIL KELAHIRAN')
            bc = s.enter_context(mock.patch('apps.scholarship.bc_parse.parse_bc'))
            r = self.run_impl(self.doc('birth_certificate'))
        bc.assert_not_called()                                     # 'no image' is an error: no parse
        m['words'].assert_not_called()
        m['extract'].assert_called_once_with('SIJIL KELAHIRAN', 'birth_certificate')
        self.assertEqual(r['capture'], 'ai')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TestHigherResultsBranch(_Base):
    def test_the_package_seam_is_the_reader_it_is_handed(self):
        with ExitStack() as s:
            m = self.seams(s)
            s.enter_context(mock.patch('apps.scholarship.higher_results._exact_read', return_value=(None, '')))
            r = self.run_impl(self.doc('higher_results'), ocr={'text': '', 'error': None})
        m['extract'].assert_called_once_with('', 'higher_results', image=b'IMG', content_type='image/jpeg')
        self.assertEqual(r['capture'], 'ai')


# ── 2. The genuineness fingerprint, branch by branch (genuineness on) ──────────────────────────

_SIG = {'status': 'genuine', 'reason': 'r', 'type': 't', 'probability': 0.9, 'present': ['a'],
        'missing': ['b'], 'model_version': '9.9'}
_SIG_STORED = {'status': 'genuine', 'reason': 'r', 'doc_seen': 't', 'probability': 0.9, 'present': ['a'],
               'missing': ['b'], 'model_version': '9.9'}
_FAM = {'status': 'genuine', 'reason': 'r', 'family': 'tnb', 'probability': 0.8, 'model_version': '1.0.0',
        'markers': {'m': 1}}
_FAM_STORED = {'status': 'genuine', 'reason': 'r', 'doc_seen': 'tnb', 'probability': 0.8,
               'model_version': '1.0.0', 'markers': {'m': 1}}
G = 'apps.scholarship.genuineness.'


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestGenuinenessBranches(_Base):
    def read(self, doc_type, *, text='DOC TEXT', ocr_error=None, patches=(), ocr=None, **doc_kw):
        with ExitStack() as s:
            m = self.seams(s, text=text, ocr_error=ocr_error)
            s.enter_context(mock.patch('apps.scholarship.doc_parse.parse_by_labels', return_value=None))
            s.enter_context(mock.patch('apps.scholarship.spm_cert_parse.parse_spm_cert',
                                       return_value={'name': NAME}))
            s.enter_context(mock.patch('apps.scholarship.offer_exact.exact_offer_read',
                                       return_value=_ex({'name': NAME}, capture='deterministic')))
            s.enter_context(mock.patch('apps.scholarship.bc_parse.parse_bc', return_value={'name': NAME}))
            s.enter_context(mock.patch('apps.scholarship.higher_results._exact_read', return_value=(None, '')))
            for target, kw in patches:
                m[target.rsplit('.', 1)[-1]] = s.enter_context(mock.patch(target, **kw))
            doc = self.doc(doc_type, **doc_kw)
            r = self.run_impl(doc, ocr=ocr)
        doc.refresh_from_db()
        return r, m, doc

    def test_results_slip_signature_plus_the_visual_markers(self):
        r, m, doc = self.read('results_slip', patches=(
            (G + 'results_doc.signature_genuineness', {'return_value': dict(_SIG)}),
            (G + 'results_doc.results_visual_markers', {'return_value': {'has_qr': True, 'has_crest': False}}),
        ))
        m['results_visual_markers'].assert_called_once_with(b'IMG', 'image/jpeg')
        m['signature_genuineness'].assert_called_once_with('DOC TEXT', has_qr=True, has_crest=False)
        self.assertEqual(r['authenticity'], _SIG_STORED)
        self.assertEqual(doc.vision_fields['authenticity'], _SIG_STORED)

    def test_results_slip_with_a_failed_ocr_gives_no_signal(self):
        r, m, _ = self.read('results_slip', ocr_error='boom', patches=(
            (G + 'results_doc.signature_genuineness', {'return_value': dict(_SIG)}),))
        m['signature_genuineness'].assert_not_called()
        self.assertNotIn('authenticity', r)

    def test_offer_folds_a_legacy_unrecognised_to_suspect(self):
        r, m, _ = self.read('offer_letter', patches=(
            (G + 'assess', {'return_value': {'status': 'unrecognised', 'reason': 'x', 'doc_seen': 'd'}}),))
        m['assess'].assert_called_once_with('offer_letter', image=b'IMG', content_type='image/jpeg',
                                            ocr_text='DOC TEXT')
        self.assertEqual(r['authenticity'], {'status': 'suspect', 'reason': 'x', 'doc_seen': 'd'})

    def test_offer_keeps_the_scored_keys(self):
        r, _, _ = self.read('offer_letter', patches=((G + 'assess', {'return_value': dict(_SIG)}),))
        self.assertEqual(r['authenticity'], _SIG_STORED)

    def test_offer_with_no_text_is_not_scored(self):
        r, m, _ = self.read('offer_letter', text='  ', patches=((G + 'assess', {'return_value': dict(_SIG)}),))
        m['assess'].assert_not_called()
        self.assertNotIn('authenticity', r)

    def test_birth_certificate_and_epf_use_the_signature_scorer_by_type(self):
        for doc_type in ('birth_certificate', 'epf'):
            with self.subTest(doc_type=doc_type):
                r, m, _ = self.read(doc_type, patches=(
                    (G + 'results_doc.signature_genuineness', {'return_value': dict(_SIG)}),))
                m['signature_genuineness'].assert_called_once_with('DOC TEXT', doc_type=doc_type)
                self.assertEqual(r['authenticity'], _SIG_STORED)

    def test_semester_and_higher_results_use_the_stpm_slot_scorer(self):
        for doc_type in ('semester_result', 'higher_results'):
            with self.subTest(doc_type=doc_type):
                r, m, doc = self.read(doc_type, patches=(
                    (G + 'stpm_doc.stpm_slot_genuineness', {'return_value': dict(_SIG)}),))
                self.assertEqual(m['stpm_slot_genuineness'].call_args.args[1], 'DOC TEXT')
                self.assertEqual(m['stpm_slot_genuineness'].call_args.args[0].pk, doc.pk)
                self.assertEqual(r['authenticity'], _SIG_STORED)

    def test_an_unscored_stpm_slot_stores_nothing(self):
        r, _, _ = self.read('semester_result', patches=(
            (G + 'stpm_doc.stpm_slot_genuineness', {'return_value': {}}),))
        self.assertNotIn('authenticity', r)

    def test_str_is_assessed_even_without_text(self):
        r, m, _ = self.read('str', text='', patches=(
            (G + 'assess', {'return_value': {'status': 'genuine', 'reason': 'ok', 'type': 'mystr'}}),))
        m['assess'].assert_called_once_with('str', image=b'IMG', content_type='image/jpeg', ocr_text='')
        self.assertEqual(r['authenticity'], {'status': 'genuine', 'reason': 'ok', 'doc_seen': 'mystr'})

    def test_salary_and_support_docs_use_the_income_doc_scorer(self):
        for doc_type in ('salary_slip', 'income_support_doc'):
            with self.subTest(doc_type=doc_type):
                fam = dict(_FAM, family='private')
                # read_approval asks the same scorer for the family first; a formal payslip ends there,
                # and a support doc read as a bank statement needs no approval call (no image call here).
                r, m, _ = self.read(doc_type, patches=(
                    (G + 'declaration_doc.income_doc_genuineness', {'return_value': fam}),
                    ('apps.scholarship.income_declaration._bank_statement', {'return_value': True}),
                ))
                m['income_doc_genuineness'].assert_called_with('DOC TEXT', doc_type)
                self.assertEqual(r['authenticity'], dict(_FAM_STORED, doc_seen='private'))

    def test_utility_bills_and_the_leaving_cert_use_their_own_scorers(self):
        for doc_type, target in (('electricity_bill', 'electricity_doc.electricity_genuineness'),
                                 ('water_bill', 'water_doc.water_genuineness'),
                                 ('school_leaving_cert', 'school_leaving_doc.school_leaving_genuineness')):
            with self.subTest(doc_type=doc_type):
                r, m, _ = self.read(doc_type, patches=((G + target, {'return_value': dict(_FAM)}),))
                m[target.rsplit('.', 1)[-1]].assert_called_once_with('DOC TEXT')
                self.assertEqual(r['authenticity'], _FAM_STORED)

    def test_a_utility_bill_with_a_failed_ocr_gives_no_signal(self):
        r, m, _ = self.read('water_bill', ocr_error='boom', text='', patches=(
            (G + 'water_doc.water_genuineness', {'return_value': dict(_FAM)}),))
        m['water_genuineness'].assert_not_called()
        self.assertNotIn('authenticity', r)

    def test_a_type_with_no_scorer_stores_nothing(self):
        r, _, _ = self.read('bank_statement')
        self.assertNotIn('authenticity', r)


# ── 3. The IC read: the second-opinion outage marks (TD-390) ───────────────────────────────────


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, IC_GEMINI_FALLBACK_ENABLED=True)
class TestIcSecondOpinionOutage(_Base):
    def test_a_failed_second_opinion_on_our_side_marks_the_read(self):
        from apps.scholarship.read_errors import IC_SECOND_OPINION_ERROR, IC_SECOND_OPINION_UNTIL
        with ExitStack() as s:
            s.enter_context(mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'))
            s.enter_context(mock.patch(V + 'extract_mykad', return_value={
                'nric': '', 'name': NAME, 'address': '', 'error': None}))
            second = s.enter_context(mock.patch(V + '_gemini_ic_second_opinion', return_value={'_error': OUTAGE}))
            doc = self.doc('ic')
            r = vision.run_vision_for_document(doc)
        second.assert_called_once_with(b'IMG', 'image/jpeg')
        self.assertEqual(r['name'], NAME)
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['capture'], 'deterministic')
        self.assertEqual(doc.vision_fields['ic_second_opinion'], 'ours')
        self.assertEqual(doc.vision_fields[IC_SECOND_OPINION_ERROR], OUTAGE)
        self.assertIn(IC_SECOND_OPINION_UNTIL, doc.vision_fields)

    def test_a_merged_second_opinion_is_tagged_ai(self):
        with ExitStack() as s:
            s.enter_context(mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'))
            s.enter_context(mock.patch(V + 'extract_mykad', return_value={
                'nric': '', 'name': NAME, 'address': '', 'error': None}))
            s.enter_context(mock.patch(V + '_gemini_ic_second_opinion', return_value={
                'nric': NRIC, 'name': NAME, 'address': 'NO 1 JALAN X'}))
            doc = self.doc('ic')
            r = vision.run_vision_for_document(doc)
        self.assertEqual((r['nric'], r['address']), (NRIC, 'NO 1 JALAN X'))
        doc.refresh_from_db()
        self.assertEqual((doc.vision_fields['capture'], doc.vision_fields['ic_second_opinion']), ('ai', 'ok'))


# ── 4. PDF intake paths ────────────────────────────────────────────────────────────────────────


class TestPdfPaths(SimpleTestCase):
    def test_a_digital_pdf_reads_its_text_layer_and_never_calls_vision(self):
        with mock.patch(V + '_pdf_text_layer', return_value='T' * 400), \
                mock.patch(V + '_vision_document_text') as ocr:
            r = vision.extract_text(b'%PDF-1.7', 'application/pdf')
        ocr.assert_not_called()
        self.assertEqual(r, {'text': 'T' * 400, 'error': None})

    def test_a_scanned_pdf_is_rasterised_then_read(self):
        with mock.patch(V + '_pdf_text_layer', return_value=''), \
                mock.patch(V + '_pdf_first_page_png', return_value=b'PNG'), \
                mock.patch(V + '_vision_document_text', return_value={'text': 'SCAN', 'error': None}) as ocr:
            r = vision.extract_text(b'%PDF-1.7', 'application/pdf')
        ocr.assert_called_once_with(b'PNG')
        self.assertEqual(r['text'], 'SCAN')

    def test_an_unrasterisable_pdf_is_bad_image_data(self):
        with mock.patch(V + '_pdf_text_layer', return_value=''), \
                mock.patch(V + '_pdf_first_page_png', return_value=None), \
                mock.patch(V + '_vision_document_text') as ocr:
            self.assertEqual(vision.extract_text(b'%PDF-1.7', ''), {'text': '', 'error': 'Bad image data.'})
            self.assertEqual(vision.extract_mykad(b'%PDF-1.7', 'application/pdf'),
                             {'nric': '', 'name': '', 'address': '', 'error': 'Bad image data.'})
        ocr.assert_not_called()

    def test_a_mykad_pdf_is_rasterised_then_parsed(self):
        with mock.patch(V + '_pdf_first_page_png', return_value=b'PNG'), \
                mock.patch(V + '_vision_document_text',
                           return_value={'text': 'KAD PENGENALAN\n030101-14-1234\nMUTHU A/L RAMAN\n', 'error': None}) as ocr:
            r = vision.extract_mykad(b'%PDF-1.7', 'application/pdf')
        ocr.assert_called_once_with(b'PNG')
        self.assertEqual(r['nric'], NRIC)
        self.assertIsNone(r['error'])

    def test_empty_bytes(self):
        self.assertEqual(vision.extract_text(b''), {'text': '', 'error': 'empty image'})
        self.assertEqual(vision.extract_mykad(b''), {'nric': '', 'name': '', 'address': '', 'error': 'empty image'})


class TestOcrDocumentPdf(_Base):
    def test_a_scanned_pdf_with_a_thin_layer_pays_for_one_vision_call(self):
        with mock.patch(V + '_fetch_image_bytes', return_value=b'%PDF-1.7'), \
                mock.patch(V + '_pdf_text_layer', return_value='CamScanner'), \
                mock.patch(V + '_vision_words', return_value={'words': [{'t': 1}], 'text': 'READ',
                                                              'error': None}) as words:
            r = vision.ocr_document_full(self.doc('epf', content_type='application/pdf'))
        words.assert_called_once_with(b'%PDF-1.7', 'application/pdf')
        self.assertEqual(r, {'text': 'READ', 'words': [{'t': 1}], 'image': b'%PDF-1.7', 'error': None})

    def test_ocr_document_reads_through_extract_text(self):
        with mock.patch(V + '_fetch_image_bytes', return_value=b'IMG'), \
                mock.patch(V + 'extract_text', return_value={'text': 'X', 'error': None}) as ext:
            r = vision.ocr_document(self.doc('epf'))
        ext.assert_called_once_with(b'IMG', 'image/jpeg')
        self.assertEqual(r, {'text': 'X', 'error': None})


# ── 5. The judge: the student-facing verdict on extracted fields ───────────────────────────────


class TestJudge(SimpleTestCase):
    def v(self, doc_type, fields, **kw):
        return vision.doc_student_verdict(doc_type, fields, names=kw.pop('names', [NAME]), **kw)

    def test_bank_statement(self):
        full = {'bank_name': 'MAYBANK', 'account_number': '1234', 'account_holder': 'NAMA : ' + NAME}
        self.assertEqual(self.v('bank_statement', full), 'ok')
        self.assertEqual(self.v('bank_statement', dict(full, account_holder='SITI BINTI ALI')), 'name_mismatch')
        self.assertEqual(self.v('bank_statement', dict(full, account_number='')), 'incomplete')
        self.assertEqual(self.v('bank_statement', {}), 'wrong_doc')
        self.assertEqual(self.v('bank_statement', full, names=[]), 'name_mismatch')

    def test_support_doc_is_never_name_checked(self):
        self.assertEqual(self.v('income_support_doc', {'name': 'SITI BINTI ALI'}), 'ok')
        self.assertEqual(self.v('income_support_doc', {'name': ' '}), 'wrong_doc')

    def test_parent_held_docs_are_never_name_checked(self):
        for doc_type in ('water_bill', 'electricity_bill', 'str'):
            with self.subTest(doc_type=doc_type):
                self.assertEqual(self.v(doc_type, {'name': 'SITI BINTI ALI'}), 'ok')

    def test_name_and_address(self):
        self.assertEqual(self.v('epf', {'name': 'SITI BINTI ALI'}), 'name_mismatch')
        self.assertEqual(self.v('epf', {'name': 'NAMA : ' + NAME}), 'ok')
        self.assertEqual(self.v('epf', {'name': '', 'x': 1}), 'ok')
        self.assertEqual(self.v('epf', {'name': None}), 'wrong_doc')
        self.assertEqual(self.v('epf', {'name': NAME, 'address': 'NO 9 JALAN LAIN, 01000 KANGAR, PERLIS'},
                                check_address=True, postcode='62100', city='Putrajaya', street='Jalan Test'),
                         'address_mismatch')
