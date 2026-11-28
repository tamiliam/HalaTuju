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
from apps.scholarship.income_engine.declaration_name import (has_keep_word, payslip_only_warning, shown_warnings,
                                                              tagged_hides)
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

    def test_an_empty_or_failed_read_keeps_no_topics(self):
        """Review round 2: an empty answer or an error read stores no warnings, so no topics either."""
        from apps.scholarship.vision.field_extraction import _build_read_result, _empty_answer_failed
        doc = SimpleNamespace(doc_type='salary_slip')
        empty = _empty_answer_failed({'fields': {'name': ''}, 'warnings': [NO_EMPLOYER], 'error': '',
                                      wt.KEY: ['employer_missing'], 'exam_year_read': '2024'})
        self.assertEqual(empty['warnings'], [])
        for ex in (empty, {**empty, 'error': 'boom'}):             # empty answer, then any error read
            failed = _build_read_result(doc, ex, names=[], postcode='', city='', street='', check_address=False)
            self.assertEqual(failed['warnings'], [])
            self.assertNotIn(wt.KEY, failed)
            self.assertEqual(failed['exam_year_read'], '2024')     # the other kept keys stay


class TheTaggedDisplayTests(SimpleTestCase):
    WS = [NO_EMPLOYER, NO_PERIOD, HANDWRITTEN]

    def test_payslip_only_topics_hide_on_a_declaration(self):
        doc = _doc(['employer_missing', 'pay_period_missing', 'other'])
        self.assertEqual(shown_warnings(doc, self.WS), [HANDWRITTEN])

    def test_new_wording_the_word_filter_misses_is_hidden_by_its_code(self):
        odd = 'Company details are missing from this page'
        self.assertFalse(payslip_only_warning(odd))
        self.assertEqual(shown_warnings(_doc(['employer_missing']), [odd]), [])

    def test_a_note_with_no_absence_word_shows_under_a_payslip_only_code(self):
        """Review round 1: a code alone never hides; the note must also name an absence."""
        for w in ('Company details could not be located anywhere on this page', 'The employer is a sole trader',
                  'Gaji dibayar secara tunai', 'The pay period looks unusual for this kind of job'):
            for code in sorted(wt.PAYSLIP_ONLY_TOPICS):
                self.assertEqual(shown_warnings(_doc([code]), [w]), [w], (w, code))

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
        signature note: the declaration's "signing date rather than a pay period" note hides."""
        w = 'The date shown is the declaration signing date rather than a specific pay period'
        self.assertTrue(has_keep_word(w))
        self.assertEqual(shown_warnings(_doc(['pay_period_missing']), [w]), [])
        for phrase in ('date of signing', 'date signed', 'signed date'):
            note = f'The {phrase} is given rather than a pay period'
            self.assertEqual(shown_warnings(_doc(['pay_period_missing']), [note]), [], phrase)

    def test_a_missing_signing_date_or_any_missing_date_shows(self):
        """Review round 1: the strip never runs beside an absence, and "signed on" is no date phrase."""
        for w in ('Signing date missing', 'Date signed: missing', 'Date of signing is not given',
                  'No signing date', 'Date of signing is missing and the pay period is not stated',
                  'Tiada maklumat majikan; tarikh tiada', 'Tiada tarikh', 'Date missing',
                  'The form was not signed on behalf of the employer', 'The date signed is not a pay period'):
            for code in sorted(wt.PAYSLIP_ONLY_TOPICS):
                self.assertEqual(shown_warnings(_doc([code]), [w]), [w], (w, code))

    def test_signature_notes_still_show_under_a_payslip_only_code(self):
        for w in ('The declaration is not signed', 'No signature or stamp', 'Signature missing',
                  'The signing date appears altered', 'Unsigned'):
            for code in ('pay_period_missing', 'employer_missing'):
                self.assertEqual(shown_warnings(_doc([code]), [w]), [w], (w, code))


class ReviewRound1KeepFamiliesTests(SimpleTestCase):
    """Review round 1 (2026-11-28): the tagged path must NEVER hide a note the reviewer needs. One wrong code
    plus a missing keep word used to hide it; now each family keeps it (English and Malay), whatever the code."""

    #: Owner phone check on case 1048: these synthetic declaration notes HIDE under their payslip-only code.
    CASE_1048 = (('No employer name is provided on this document.', 'employer_missing'),
                 ('A separate take-home pay amount is not shown.', 'take_home_missing'),
                 ('The document shows only a declaration signing date rather than a specific pay period.',
                  'pay_period_missing'),
                 ('No pay period is stated.', 'pay_period_missing'),
                 ('Gross pay is not shown.', 'gross_missing'))
    #: Each family, with an absence word in it, so the KEEP word is what shows it.
    FAMILIES = {
        'signature and stamp': ('Employer missing; no tanda tangan', 'Tiada tanda tangan majikan',
                                'Cap majikan tiada', 'Employer missing, t/t not given'),
        'alteration': ('Employer missing and the amount appears to have been edited',
                       'Pay period modified, none given', 'Amount amended; employer missing',
                       'Figures changed, no employer', 'Amount crossed out, no period',
                       'Whited out area, employer missing', 'Tipp-ex used, employer missing',
                       'Erased figure, no employer', 'Possibly manipulated; no employer',
                       'Amaun dipinda, tiada majikan', 'Angka dipadam, tiada majikan',
                       'Angka diconteng, tiada majikan', 'Angka ditindih, tiada majikan',
                       'Ditulis semula, tiada majikan'),
        'unreadable': ('Blurry image, employer missing', 'Dark scan, no employer', 'Gambar gelap, tiada majikan',
                       'Poor quality, no employer', 'Faint print, no employer', 'Tulisan pudar, tiada majikan',
                       'Gambar tidak terang', 'Gambar tidak terang, tiada majikan', 'Torn page, no employer',
                       'Kertas koyak, tiada majikan', 'Dokumen rosak, tiada majikan', 'Damaged page, no employer',
                       'Only a partial page, no employer', 'Hard to read, employer missing',
                       'Not readable; no employer', 'Illegible amount, no employer'),
        'mismatch': ('Amaun tidak sepadan', 'Amounts do not match, no employer',
                     'Jumlah tidak sama, tiada majikan', 'Cannot verify the employer, none given'),
        'fake and context': ('Looks like a template, no employer', 'Sample document, no employer',
                             'Contoh borang sahaja', 'Contoh borang, tiada majikan', 'Photocopy only, no employer',
                             'Salinan sahaja, tiada majikan', 'Computer generated, no employer',
                             'Not an official document, no employer', 'Figures may be invented, no employer',
                             'Written by a family member, no employer', 'The employer is the father',
                             'The employer is the mother, no pay period', 'Majikan ialah bapa, tiada tempoh gaji',
                             'Majikan ialah ibu, tiada tempoh gaji', 'Duplicate of another uploaded document',
                             'Income is above the B40 line', 'Income looks high, no employer',
                             'Outdated slip, no pay period', 'Slip lama, tiada tempoh gaji'),
    }

    def test_the_case_1048_notes_still_hide_under_their_code(self):
        for w, code in self.CASE_1048:
            self.assertTrue(tagged_hides(w), w)
            self.assertEqual(shown_warnings(_doc([code]), [w]), [], w)
        ws = [w for w, _ in self.CASE_1048] + [HANDWRITTEN]
        self.assertEqual(shown_warnings(_doc([c for _, c in self.CASE_1048] + ['other']), ws), [HANDWRITTEN])

    def test_every_family_shows_under_every_payslip_only_code(self):
        for family, notes in self.FAMILIES.items():
            for w in notes:
                self.assertTrue(has_keep_word(w), (family, w))
                for code in sorted(wt.PAYSLIP_ONLY_TOPICS):
                    self.assertEqual(shown_warnings(_doc([code]), [w]), [w], (family, w, code))

    def test_the_reviewers_cases_show_under_every_payslip_only_code(self):
        for w in ('The form was not signed on behalf of the employer', 'Signing date missing',
                  'Date of signing is missing and the pay period is not stated',
                  'Tiada maklumat majikan; tarikh tiada', 'Tiada tanda tangan majikan', 'Cap majikan tiada',
                  'appears to have been edited', 'Gambar tidak terang', 'Amaun tidak sepadan',
                  'Duplicate of another uploaded document', 'Income is above the B40 line',
                  'The employer is the father', 'Contoh borang sahaja'):
            for code in sorted(wt.PAYSLIP_ONLY_TOPICS):
                self.assertEqual(shown_warnings(_doc([code]), [w]), [w], (w, code))

    def test_the_word_start_and_whole_word_keeps_are_not_substrings(self):
        for w in ('Employer already missing', 'Alamat majikan tiada', 'Tiada keterangan majikan',
                  'Employer not stated; berapa amaun',
                  'It appears to be a declaration letter rather than an official pay-slip'):
            self.assertFalse(has_keep_word(w), w)
        for w in ('Unreadable', 'Readable only in part', 'Slip lama', 'Tidak sama', 'Cap tiada', 'Not official'):
            self.assertTrue(has_keep_word(w), w)

    def test_the_type_note_still_hides_under_not_a_payslip(self):
        for w in ('This is an income declaration, not a payslip',
                  'Dokumen ini ialah surat akuan pendapatan, bukan slip gaji',
                  'The document is a declaration rather than a payslip'):
            self.assertEqual(shown_warnings(_doc(['not_a_payslip']), [w]), [], w)


class ReviewRound2EveryPartTests(SimpleTestCase):
    """Review round 2 (2026-11-28): a keep list is never complete. Under a payslip-only code a note hides only
    when EVERY part names a payslip-only topic and an absence; else the word filter decides."""

    MUST_SHOW = {
        'missing date': ('The date of the declaration is not given.', 'Tarikh akuan tidak dinyatakan.',
                         'Undated, with no employer listed.', 'The month of the declaration is not stated.',
                         'No date or pay period given', 'Tidak bertarikh, tiada majikan'),
        'fake': ('may not be genuine; no employer stated', 'looks fabricated, with no pay period',
                 'Not authentic: no employer shown', 'Dokumen ini meragukan, tiada majikan',
                 'Possibly counterfeit; the employer is missing'),
        'family employer': ("The employer is the earner's husband; no pay period stated",
                            'Majikan ialah suami; tiada tempoh gaji', 'the brother of the earner, no pay period',
                            'The employer is the son; pay period missing'),
        'mismatch': ('The amounts do not agree; no take-home shown', 'does not add up and net pay is missing',
                     'Jumlah tidak tepat; tiada gaji bersih', 'does not tally; no net pay'),
        'income level': ('exceeds the eligibility threshold; no supporting payslip',
                         'Income looks too low; no employer given', 'Pendapatan melebihi had; tiada majikan'),
        'duplicate': ('The same document appears twice, without a pay period',
                      'also uploaded for another member; no employer shown',
                      'Dokumen yang serupa dimuat naik dua kali; tiada majikan'),
        'other': ('No employer; the declaration is by a neighbour, not the earner',
                  'Tiada majikan; pendapatan dinyatakan RM 8,000 sebulan', 'Missing employer; page 2 is absent',
                  'Shows only the top half of the page', 'No employer stated but the earner is a farmer'),
        'no absence at all': ('The figure is typed rather than a handwritten amount.',
                              'It is a screenshot rather than an original.',
                              'Shows only a total rather than a monthly amount.',
                              'The employer is a person rather than a company'),
    }
    #: Still hidden: the owner's case-1048 notes are in ReviewRound1KeepFamiliesTests; these are the forms
    #: the part rule must not lose.
    STILL_HIDE = ('Company details are missing from this page', 'No employer or pay period stated',
                  'The date of signing is given rather than a pay period', 'Month and year of salary not shown',
                  'Bulan gaji tidak dinyatakan', 'A separate take home pay amount is not shown; gross pay missing',
                  'The document shows only a declaration date rather than a pay period')

    def test_every_failure_wording_shows_under_every_payslip_only_code(self):
        for family, notes in self.MUST_SHOW.items():
            for w in notes:
                self.assertFalse(tagged_hides(w), (family, w))
                for code in sorted(wt.PAYSLIP_ONLY_TOPICS):
                    self.assertEqual(shown_warnings(_doc([code]), [w]), [w], (family, w, code))

    def test_the_pure_absence_forms_still_hide(self):
        for w in self.STILL_HIDE:
            self.assertTrue(tagged_hides(w), w)
            self.assertEqual(shown_warnings(_doc(['pay_period_missing']), [w]), [], w)

    def test_the_new_keep_words_never_touch_the_case_1048_notes(self):
        for w, _ in ReviewRound1KeepFamiliesTests.CASE_1048:      # the signing one holds only the old "sign"
            self.assertFalse(has_keep_word(w.replace('signing date', 'date')), w)
        for w in ('The reason for no employer', 'Income below RM 2,000, no employer', 'On behalf of: none',
                  'Personal employer missing', 'No employer on the page', 'Employer missing from the page'):
            self.assertFalse(has_keep_word(w), w)          # son, low, half, page: whole word or word start
        for w in ('The son is the employer', 'Gaji rendah', 'Anak menulis borang', 'Page 2 missing',
                  'Income is low'):
            self.assertTrue(has_keep_word(w), w)


class ReviewRound3NothingLeftOverTests(SimpleTestCase):
    """Review round 3 (2026-11-28): a hiding part may hold only topic, absence and filler words. Any other
    word (who wrote it, why it is missing, what it really is) shows the note under every payslip-only code."""

    MUST_SHOW = (
        "No employer is stated for an earner who is not the student's parent.",
        'No employer is stated on this declaration written by the student.',
        'No employer is stated on this form filled in by someone other than the earner.',
        'No employer is stated on this form which is identical to the one uploaded for the other parent.',
        'No employer is stated on what appears to be the same form uploaded for the other parent.',
        'No take-home pay is shown because the lower part of the form is missing.',
        'Employer details are missing because the lower part of the document was not captured.',
        'Gross income is not shown with the amount appearing corrected by hand.',
        'No employer is stated as the earner works for his uncle.',
        'No employer is stated as the earner works for an in-law.',
        "No employer is stated as the earner works in his grandparents' business.",
        'The form appears incomplete with no employer stated.',
        'The employer is not stated because the document is incomplete.',
        'No payslip was provided as the uploaded document is a bank statement.',
        'No pay period is given on this declaration which appears to be several years old.',
        'No employer is stated on this photo of a computer screen.',
        'Tiada majikan kerana pekerja bekerja dengan pakcik.',
        'Majikan tidak dinyatakan kerana borang tidak lengkap.',
        'Gaji kasar tidak dinyatakan pada borang yang diisi oleh orang lain.',
        'No employer stated the figure was corrected',
        'No pay slip the upload is unrelated',
        'Tiada majikan pendapatan tinggi',
        'No employer stated earner is a minor',
        'The employer is given as a shop with no address.',
        'The employer listed has no registration number.',
    )

    def test_a_left_over_word_shows_the_note_under_every_payslip_only_code(self):
        for w in self.MUST_SHOW:
            self.assertFalse(tagged_hides(w), w)
            for code in sorted(wt.PAYSLIP_ONLY_TOPICS):
                self.assertEqual(shown_warnings(_doc([code]), [w]), [w], (w, code))

    def test_the_case_1048_and_pure_absence_notes_still_hide(self):
        for w, code in ReviewRound1KeepFamiliesTests.CASE_1048:
            self.assertTrue(tagged_hides(w), w)
            self.assertEqual(shown_warnings(_doc([code]), [w]), [], w)
        for w in ReviewRound2EveryPartTests.STILL_HIDE:
            self.assertTrue(tagged_hides(w), w)

    def test_the_new_keep_stems(self):
        for w in ('Amount corrected, no employer', 'Incomplete form, no employer', 'Borang tidak lengkap',
                  'Identical to another form', 'Works for an uncle', 'Bekerja dengan pakcik'):
            self.assertTrue(has_keep_word(w), w)


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
        'halatuju_api/apps/scholarship/serializers/documents.py',   # DROPS the key from every served copy
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


class NoTopicCodeIsServedTests(_Slips):
    """Review round 1: the codes are for the display rule only; no payload (student or officer) carries them."""

    def test_the_student_and_the_admin_payloads_have_no_topic_key(self):
        from apps.scholarship.serializers.documents import ApplicantDocumentSerializer
        from apps.scholarship.sgd_conversion import AdminApplicantDocumentSerializer
        doc = self.slip()
        doc.vision_fields = {**doc.vision_fields, 'warnings': [NO_EMPLOYER, HANDWRITTEN],
                             wt.KEY: ['employer_missing', 'other']}
        doc.save()
        doc.refresh_from_db()
        for ser in (ApplicantDocumentSerializer, AdminApplicantDocumentSerializer):
            vf = ser(doc).data['vision_fields']
            self.assertNotIn(wt.KEY, vf, ser.__name__)
            self.assertEqual(vf['warnings'], [HANDWRITTEN], ser.__name__)     # still hidden by the stored code
        self.assertEqual(doc.vision_fields[wt.KEY], ['employer_missing', 'other'])   # the stored read is untouched


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
        odd = 'Company details are missing from this page'
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

    @staticmethod
    def _cascade(rows, tokens=(None, None)):
        """A fake seam that bills ``rows`` cascade models per call (one meter row each), as a fall-through does."""
        billed = []

        def seam(*a, **k):
            for i in range(rows):
                billed.append(i)        # the model answered (billed); its meter row follows
                ev.usage.record_usage(ev.usage.GEMINI, model=f'm{i}', input_tokens=tokens[0], output_tokens=tokens[1])
            return _answer([], [])
        return seam, billed

    def test_three_billed_rows_per_call_stop_the_run_before_the_cap(self):
        for _ in range(5):
            self.slip()
        seam, billed = self._cascade(3)
        text, m, _ = self.run_cmd('--run', '--limit', '5', '--max-cost-usd', '0.03', seam={'side_effect': seam})
        self.assertIn('STOPPED: the next document could pass the cap', text)
        self.assertEqual(m.call_count, 2)          # one cost per call would have run all 5 (15 rows, US$0.06)
        self.assertEqual(len(billed), 6)
        self.assertIn('charged up to US$0.0240', text)

    def test_the_cap_is_checked_after_each_row_mid_read(self):
        self.slip()
        seam, billed = self._cascade(3, tokens=(10_000, 10_000))     # about US$0.056 a row
        text, m, _ = self.run_cmd('--run', '--limit', '1', '--max-cost-usd', '0.06', seam={'side_effect': seam})
        self.assertIn('stopped mid-read', text)
        self.assertEqual(len(billed), 1)           # the 2nd and 3rd models are never called
        self.assertIn('read 0', text)

    def test_a_long_prompt_is_reserved_and_refused_before_it_is_billed(self):
        """Review round 2: one large row could pass the cap; the prompt's bytes bound its input, checked first."""
        self.slip()
        # The prompt keeps 6,000 characters of OCR text; 4-byte characters make it about 27k bytes, a reserve of
        # about US$0.016: over a US$0.015 cap that the flat US$0.004 bound (and the per-document check) let pass.
        long_text = '\U0001D417' * 6000
        text, m, _ = self.run_cmd('--run', '--limit', '1', '--max-cost-usd', '0.015',
                                  ocr={'text': long_text, 'error': None})
        m.assert_not_called()
        self.assertIn('stopped mid-read', text)
        self.assertIn('read 0', text)
        self.assertIn('charged up to US$0.0000', text)
        trace = {'peak': ev.USD_PER_GEMINI_CALL}
        self.assertEqual(ev.row_reserve(trace, 'short'), ev.USD_PER_GEMINI_CALL)
        self.assertEqual(ev.row_reserve(trace, 'X' * 200_000), ev.gemini_cost((200_000, None)))
        self.assertEqual(ev.row_reserve({'peak': ev.Decimal('0.5')}, 'short'), ev.Decimal('0.5'))

    def test_stops_before_the_cap(self):
        for _ in range(3):
            self.slip()
        text, m, _ = self.run_cmd('--run', '--limit', '3', '--max-cost-usd', '0.015')
        self.assertIn('STOPPED: the next document could pass the cap', text)
        self.assertEqual(m.call_count, 1)
