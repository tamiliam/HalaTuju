"""TD-718 part 2 — a MySTR "application details" page is not an STR proof (owner 2026-11-24).

"Anyone can apply; so received application is a failed STR route. The student must submit salary
route." The application details page (Maklumat Pemohon with age, sex, marital status, phone and
address, and no status) used to fall to the STR parser's catch-all 'semakan_status' and read amber
'unreadable', which `str_not_breached` lets pass, so no salary papers were asked for. Now it reads
`source_type='unknown'` → 'wrong_type' → red, on every door: the rules read, and the guard after the
Gemini read (upload, the cockpit Re-run, the bulk re-read, the hourly sweep all pass through it).

Unchanged: a cropped Semakan (amber), an approval letter with an address, a dashboard, SALINAN, SARA,
every approved page, and an application page that carries an approved word.

All data is invented.
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.scholarship.doc_parse import parse_by_labels
from apps.scholarship.str_application_page import guard_str_source, is_application_details
from apps.scholarship.tests.test_doc_parse import (
    _DASHBOARD, _LETTER, _SALINAN, _SARA_ONLY, _SEMAKAN, _SEMAKAN_COLUMNS, _currency)

_NAME, _NRIC = 'DEVARAJ A/L MUNUSAMY', '700707145671'
_PAIRS = [('No. MyKad', _NRIC), ('Nama', _NAME), ('Umur', '56'), ('Jantina', 'Lelaki'),
          ('Status Perkahwinan', 'Berkahwin'), ('No. Telefon Bimbit', '0120000000'),
          ('Alamat', '1 JALAN CONTOH, TAMAN UJIAN'), ('Poskod', '00000'), ('Bandar', 'BANDAR UJIAN'),
          ('Negeri', 'NEGERI UJIAN')]


def _application(*, head=('MySTR',), pairs=_PAIRS, layout='rows', extra=()):
    """A synthetic application details page: 'rows' = label, then its value on the next line (the real
    shape); 'colon' = "Label : value"; 'columns' = every label first, then every value."""
    if layout == 'colon':
        body = [f'{label} : {value}' for label, value in pairs]
    elif layout == 'columns':
        body = [label for label, _ in pairs] + [value for _, value in pairs]
    else:
        body = [line for pair in pairs for line in pair]
    return '\n'.join([*head, 'Maklumat Pemohon', *body, *extra]) + '\n'


# A cropped Semakan Status: the header block only, no status line (STR-marked by its title bar).
_CROPPED_SEMAKAN = '\n'.join(['MySTR', 'Semakan Status', 'Maklumat Pemohon', 'Nama', _NAME, 'No. MyKad', _NRIC,
                              'Status Pedalaman', 'Tidak', 'Maklumat Pembayaran', 'Alasan Permohonan',
                              'Maklumat Anak', 'Kembali']) + '\n'

# An approval letter whose address block is printed with labels (the letter keeps its own markers).
_LETTER_WITH_ADDRESS = _LETTER + 'Alamat : 1 JALAN CONTOH\nPoskod : 00000\nBandar : BANDAR UJIAN\nNegeri : SELANGOR\n'


class TheSignature(SimpleTestCase):
    def test_an_application_details_page_is_not_an_str_proof(self):
        for layout in ('rows', 'colon', 'columns'):
            for head in (('MySTR',), ('SUMBANGAN TUNAI RAHMAH (STR)',)):
                with self.subTest(layout=layout, head=head):
                    page = _application(head=head, layout=layout)
                    self.assertTrue(is_application_details(page))
                    r = parse_by_labels('str', page)
                    self.assertEqual(r['source_type'], 'unknown')
                    self.assertEqual(_currency(r), 'wrong_type')

    def test_labels_tolerate_case_and_spacing(self):
        page = 'MySTR\nMAKLUMAT PEMOHON\n  UMUR  \n56\nstatus   perkahwinan\nBujang\nNo.Telefon  Bimbit:\n012\n'
        self.assertTrue(is_application_details(page))

    def test_three_labels_are_needed(self):
        two = _application(pairs=[('Nama', _NAME), ('No. MyKad', _NRIC), ('Umur', '56'), ('Jantina', 'Lelaki')])
        three = _application(pairs=[('Nama', _NAME), ('Umur', '56'), ('Jantina', 'Lelaki'), ('Poskod', '00000')])
        self.assertFalse(is_application_details(two))
        self.assertEqual(parse_by_labels('str', two)['source_type'], 'semakan_status')   # as before
        self.assertTrue(is_application_details(three))

    def test_a_word_inside_a_line_is_not_a_label(self):
        # "NEGERI SEMBILAN", "Alamat surat-menyurat …" and "Bandar Baru …" are values or prose, not labels.
        page = 'MySTR\nNEGERI SEMBILAN\nAlamat surat-menyurat anda\nBandar Baru Ujian\nUmur\n56\n'
        self.assertFalse(is_application_details(page))

    def test_an_approved_or_rejected_word_keeps_the_page_out(self):
        for word in ('Lulus', 'Diluluskan', 'Ditolak', 'Tidak Layak'):
            with self.subTest(word=word):
                page = _application(extra=(word,))
                self.assertFalse(is_application_details(page))
                self.assertEqual(parse_by_labels('str', page)['source_type'], 'semakan_status')   # unchanged

    def test_a_status_line_keeps_the_page_out(self):
        for line in ('Status Permohonan Semasa', 'Status Permohonan STR'):
            with self.subTest(line=line):
                self.assertFalse(is_application_details(_application(extra=(line,))))

    def test_a_pending_word_does_not_keep_the_page_out(self):
        # Chosen: either way the STR fails and the salary route applies; red as not an STR proof.
        for word in ('Permohonan Diterima', 'Dalam Proses'):
            with self.subTest(word=word):
                r = parse_by_labels('str', _application(extra=(word,)))
                self.assertEqual(r['source_type'], 'unknown')
                self.assertEqual(_currency(r), 'wrong_type')


class WhatDoesNotChange(SimpleTestCase):
    def test_every_other_surface_reads_as_before(self):
        rows = [(_LETTER, 'letter', 'current'), (_LETTER_WITH_ADDRESS, 'letter', 'current'),
                (_SEMAKAN, 'semakan_status', 'unconfirmed'), (_SEMAKAN_COLUMNS, 'semakan_status', 'unconfirmed'),
                (_DASHBOARD, 'dashboard', 'unconfirmed'), (_SALINAN, 'unknown', 'wrong_type'),
                (_CROPPED_SEMAKAN, 'semakan_status', 'unreadable')]
        for text, source, currency in rows:
            with self.subTest(source=source, currency=currency, head=text.splitlines()[0]):
                self.assertFalse(is_application_details(text))
                r = parse_by_labels('str', text)
                self.assertEqual(r['source_type'], source)
                self.assertEqual(_currency(r), currency)
        self.assertEqual(parse_by_labels('str', _SARA_ONLY)['source_type'], 'unknown')


def _read(doc_type, text, ai=None):
    """The labelled-doc read (`_read_labelled_doc`) on OCR ``text``; ``ai`` is the stubbed Gemini answer.
    No network: Gemini is a mock, and a rules read must not call it at all."""
    from apps.scholarship.vision import field_extraction as fe
    stub = mock.Mock(return_value=ai) if ai is not None else mock.Mock(side_effect=AssertionError('no AI call'))
    with mock.patch.object(fe._v, 'extract_document_fields', stub), \
            mock.patch.object(fe, '_read_approval', side_effect=lambda d, ex, t, f: ex):
        return fe._read_labelled_doc(SimpleNamespace(doc_type=doc_type), {'error': '', 'text': text}, None)


def _ai(source_type, status=''):
    return {'fields': {'recipient_name': _NAME, 'recipient_nric': _NRIC, 'status': status, 'year': '',
                       'amount': '', 'source_type': source_type}, 'warnings': [], 'error': ''}


class TheReadDoor(SimpleTestCase):
    def test_the_rules_read_stores_unknown_without_gemini(self):
        ex = _read('str', _application())
        self.assertEqual(ex['fields']['source_type'], 'unknown')
        self.assertEqual(ex['capture'], 'deterministic')

    def test_the_gemini_read_is_guarded_on_the_same_text(self):
        # No STR marker in the OCR text → the rules reader passes → Gemini; whatever it calls the page, the
        # guard on the OCR text stores 'unknown'.
        page = _application(head=())
        self.assertIsNone(parse_by_labels('str', page))
        for said in ('semakan_status', 'dashboard', 'letter', ''):
            with self.subTest(said=said):
                ex = _read('str', page, ai=_ai(said))
                self.assertEqual(ex['fields']['source_type'], 'unknown')
                self.assertEqual(ex['capture'], 'ai')

    def test_the_guard_leaves_every_other_read_alone(self):
        cropped = 'Semakan Status\nMaklumat Pemohon\nNama\nX\nNo. MyKad\nY\nStatus Pedalaman\nTidak\n'
        self.assertEqual(_read('str', cropped, ai=_ai('semakan_status'))['fields']['source_type'], 'semakan_status')
        self.assertEqual(_read('str', _LETTER_WITH_ADDRESS)['fields']['source_type'], 'letter')
        approved = _application(head=(), extra=('Lulus',))
        self.assertEqual(_read('str', approved, ai=_ai('semakan_status', 'Lulus'))['fields']['source_type'],
                         'semakan_status')
        # another document type carrying the same labels: never touched
        other = {'fields': {'name': _NAME}, 'warnings': [], 'error': ''}
        self.assertNotIn('source_type', _read('income_support_doc', _application(head=()), ai=other)['fields'])
        # a failed read is left as it is
        failed = {'fields': {}, 'warnings': [], 'error': 'boom'}
        self.assertEqual(guard_str_source('str', failed, _application()), failed)


class AnOfficerReRunStoresRed(TestCase):
    """The cockpit Re-run (`reextract.reextract_document`, shared with the bulk re-read, the hourly sweep
    and the blockers re-read) on a page stored as an amber 'semakan_status': it stores 'unknown' → red."""

    def test_rerun_turns_the_stored_amber_read_red_and_asks_for_salary_papers(self):
        from apps.scholarship import vision
        from apps.scholarship.income_engine import salary_income_satisfied, str_not_breached, student_str_check
        from apps.scholarship.reextract import reextract_document
        from apps.scholarship.tests.test_td403_str_this_year import _family
        for route in ('str', 'salary'):
            with self.subTest(route=route):
                app, doc = _family(route, year='', status='', source_type='semakan_status')
                self.assertEqual(student_str_check(doc)['current_status'], 'unreadable')   # the hole
                ocr = {'error': '', 'text': _application(), 'image': b'not-an-image', 'words': []}
                with mock.patch.object(vision, 'ocr_document_full', return_value=ocr), \
                        mock.patch.object(vision, 'run_vision_match_for_document'), \
                        mock.patch.object(vision, 'extract_document_fields', side_effect=AssertionError('no AI')), \
                        mock.patch('apps.scholarship.vision.field_extraction.add_read_authenticity'):
                    self.assertTrue(reextract_document(doc))
                doc.refresh_from_db()
                self.assertEqual(doc.vision_fields['fields']['source_type'], 'unknown')
                self.assertEqual(student_str_check(doc)['current_status'], 'wrong_type')
                self.assertIs(str_not_breached(app), False)
                self.assertIs(salary_income_satisfied(app), False)
