"""Deterministic SPM CERTIFICATE reader (`spm_cert_parse.parse_spm_cert`, 2026-10-28) + ensure_exam_year.

Synthetic twins only — no real name, IC or grade. The layout mirrors the live certificates: title,
name / IC / index no. / school, a "Mata Pelajaran … Gred" table read ROW BY ROW from word boxes,
the oral / CEFR lines, then "JUMLAH MATA PELAJARAN <word>" and "PEPERIKSAAN TAHUN <year>" at the
foot. The real corpus is scored by `eval/spm_cert_check.py` (local, PII)."""
import io

from django.test import SimpleTestCase, TestCase

from apps.scholarship.spm_cert_parse import ensure_exam_year, parse_spm_cert

H = 40                                  # word height (px)
GRADE_X = 1900                          # the grade column's left edge

SUBJECTS = [('BAHASA MELAYU', 'A- (CEMERLANG)'), ('BAHASA INGGERIS', 'B+ (KEPUJIAN TERTINGGI)'),
            ('MATEMATIK', 'A (CEMERLANG TINGGI)'), ('SEJARAH', 'A+ (CEMERLANG TERTINGGI)'),
            ('SAINS', 'B (KEPUJIAN TINGGI)')]
EXPECTED = [('Bahasa Melayu', 'A-'), ('Bahasa Inggeris', 'B+'), ('Matematik', 'A'),
            ('Sejarah', 'A+'), ('Sains', 'B')]


def _phrase(x, y, phrase):
    """Lay a phrase out left to right: ~0.8 h per letter, half a height between words."""
    out = []
    for tok in phrase.split():
        width = 0.8 * H * len(tok)
        out.append({'text': tok, 'cx': x + width / 2, 'cy': y, 'h': H, 'angle': 0.0})
        x += width + 0.5 * H
    return out


def cert(subjects=SUBJECTS, *, count='LIMA', top=None, extra=(), grade_dy=0.0):
    """Word boxes of a synthetic certificate. ``top``: the rows between the title and the table."""
    rows = [(100, [(100, 'KEMENTERIAN PENDIDIKAN MALAYSIA')]),
            (200, [(100, 'Calon yang namanya tercatat di bawah telah menduduki peperiksaan Sijil '
                         'Pelajaran Malaysia (SPM) dan')]),
            (260, [(100, 'layak dianugerahi')]),
            (360, [(100, 'SIJIL PELAJARAN MALAYSIA')])]
    for i, line in enumerate(top or ['AISYAH BINTI RAHMAN', '010101-01-0101', 'JH001A043',
                                     'SMK SAINS CONTOH']):
        rows.append((460 + 60 * i, [(100, line)]))
    rows += [(760, [(100, 'Mata Pelajaran'), (2000, 'Gred')]), (810, [(150, 'Subject'), (2000, 'Grade')])]
    words = []
    for i, (subject, grade) in enumerate(subjects):
        y = 900 + 60 * i
        if subject:
            words += _phrase(100, y, subject)
        if grade:
            words += _phrase(GRADE_X, y + grade_dy, grade)
    foot = 900 + 60 * len(subjects) + 100
    rows += [(foot, [(100, 'UJIAN LISAN BAHASA MELAYU: CEMERLANG')]),
             (foot + 50, [(100, 'TAHAP KESELURUHAN CEFR BAHASA INGGERIS: B2')])]
    if count is not None:
        rows.append((foot + 400, [(100, f'JUMLAH MATA PELAJARAN {count}')]))
    rows += [(foot + 450, [(100, 'PEPERIKSAAN TAHUN 2022')]), (foot + 500, [(100, '22011012345')])]
    for y, cells in rows:
        for x, phrase in cells:
            words += _phrase(x, y, phrase)
    words += list(extra)
    return words


def text_of(words):
    lines = {}
    for w in sorted(words, key=lambda w: (w['cy'], w['cx'])):
        lines.setdefault(w['cy'], []).append(w['text'])
    return '\n'.join(' '.join(v) for v in lines.values())


def read(words):
    return parse_spm_cert(text_of(words), words)


def grades(r):
    return [(x['subject'], x['grade']) for x in r['results']]


class TheCleanCertificate(SimpleTestCase):
    def test_reads_every_field(self):
        r = read(cert())
        self.assertEqual(r['candidate_name'], 'AISYAH BINTI RAHMAN')
        self.assertEqual(r['nric'], '010101-01-0101')
        self.assertEqual(r['exam'], 'SIJIL PELAJARAN MALAYSIA TAHUN 2022')
        self.assertEqual(grades(r), EXPECTED)
        self.assertEqual(r['results'][0]['band'], 'cemerlang')

    def test_a_school_named_sains_is_not_a_subject(self):
        # The old text reader counted "SMK SAINS CONTOH" as the subject Sains (one subject too many).
        self.assertEqual(len(read(cert())['results']), 5)

    def test_text_alone_has_no_positions(self):
        self.assertIsNone(parse_spm_cert(text_of(cert())))

    def test_a_results_slip_is_not_a_certificate(self):
        words = [w for w in cert() if w['text'].lower() not in ('layak', 'dianugerahi')]
        self.assertIsNone(read(words))

    def test_a_count_label_that_is_absent_is_allowed(self):
        self.assertEqual(grades(read(cert(count=None))), EXPECTED)

    def test_a_wrong_or_unreadable_printed_count_falls_back(self):
        self.assertIsNone(read(cert(count='ENAM')))
        self.assertIsNone(read(cert(count='LIMAA')))

    def test_a_grade_on_its_own_row_just_above_its_subject_is_joined(self):
        # A slight tilt splits the row in two (live a273): 0.5 h apart still pairs.
        self.assertEqual(grades(read(cert(grade_dy=-0.7 * H))), EXPECTED)

    def test_a_sideways_photo_reads_the_same(self):
        # Turned 90 degrees: the rows run down the image; `_group_rows` and the column test de-rotate.
        turned = [dict(w, cx=4000 - w['cy'], cy=w['cx'], angle=90.0) for w in cert()]
        self.assertEqual(grades(read(turned)), EXPECTED)

    def test_grades_one_row_out_of_step_fall_back(self):
        self.assertIsNone(read(cert(grade_dy=60)))
        self.assertIsNone(read(cert(grade_dy=-60)))


class TheGradeCell(SimpleTestCase):
    def _one(self, cell):
        subjects = list(SUBJECTS)
        subjects[2] = ('MATEMATIK', cell)
        r = read(cert(subjects))
        return r and r['results'][2]['grade']

    def test_an_unreadable_sign_is_taken_from_a_complete_band(self):
        self.assertEqual(self._one('A. (CEMERLANG)'), 'A-')
        self.assertEqual(self._one('B- (KEPUJIAN TERTINGGI)'), 'B+')      # B- is not an SPM grade
        self.assertEqual(self._one('A, (CEMERLANG TERTINGGI)'), 'A+')
        self.assertEqual(self._one('D. (LULUS ATAS)'), 'D')
        self.assertEqual(self._one('C + (KEPUJIAN ATAS)'), 'C+')          # the sign split off

    def test_an_unclear_sign_with_a_tinggi_band_falls_back(self):
        # "TINGGI" may be "TERTINGGI" with a faint "TER": A or A+, B or B+ — the band cannot say.
        for cell in ('A. (CEMERLANG TINGGI)', 'A, (CEMERLANG TINGGI)', 'B. (KEPUJIAN TINGGI)',
                     'B- (KEPUJIAN TINGGI)', 'B. (KEPUJIAN TINGGD', 'A- (CEMERLANG TINGGI)'):
            self.assertIsNone(self._one(cell), cell)

    def test_two_grade_cells_on_one_row_fall_back(self):
        self.assertIsNone(self._one('A- (CEMERLANG) A (CEMERLANG TINGGI)'))
        self.assertIsNone(self._one('B (KEPUJIAN TINGGI) SEJARAH A (CEMERLANG TINGGI)'))
        self.assertIsNone(self._one('A- (CEMERLANG) SEJARAH'))          # a second subject, no grade
        self.assertIsNone(self._one('A A- (CEMERLANG)'))                 # a stray second letter

    def test_a_clear_letter_that_disagrees_with_the_band_falls_back(self):
        self.assertIsNone(self._one('A (CEMERLANG)'))
        self.assertIsNone(self._one('B (KEPUJIAN TERTINGGI)'))
        self.assertIsNone(self._one('C (KEPUJIAN TINGGI)'))

    def test_an_unclear_sign_with_an_incomplete_band_falls_back(self):
        self.assertIsNone(self._one('A. (CEMERLANG'))

    def test_a_missing_or_unknown_grade_falls_back(self):
        self.assertIsNone(self._one(''))
        self.assertIsNone(self._one('A (EXCELLENT)'))


class TheSubjectColumn(SimpleTestCase):
    def test_an_unknown_subject_falls_back(self):
        subjects = list(SUBJECTS)
        subjects[4] = ('BAHASA KLINGON', 'B (KEPUJIAN TINGGI)')
        self.assertIsNone(read(cert(subjects)))

    def test_a_word_glued_to_a_known_subject_falls_back(self):
        # "SAINS ANGKASA" is not on the list: never read it as Sains.
        subjects = list(SUBJECTS)
        subjects[4] = ('SAINS ANGKASA', 'B (KEPUJIAN TINGGI)')
        self.assertIsNone(read(cert(subjects, count='LIMA')))

    def test_a_certifying_stamp_across_the_table_is_ignored(self):
        stamp = (_phrase(900, 960, 'Salinan disahkan benar') + _phrase(900, 1020, 'NAMA BIN PEGAWAI')
                 + _phrase(900, 1060, 'Penolong Kanan'))
        self.assertEqual(grades(read(cert(extra=stamp))), EXPECTED)

    def test_a_repeated_subject_falls_back(self):
        subjects = list(SUBJECTS)
        subjects[4] = ('SEJARAH', 'B (KEPUJIAN TINGGI)')
        self.assertIsNone(read(cert(subjects)))

    def test_fewer_than_three_subjects_falls_back(self):
        self.assertIsNone(read(cert(SUBJECTS[:2], count='DUA')))


class TheIdentity(SimpleTestCase):
    def test_a_second_ic_on_the_page_falls_back(self):
        self.assertIsNone(read(cert(extra=_phrase(900, 2400, '020202-02-0202'))))

    def test_the_same_ic_twice_is_still_one_ic(self):
        self.assertIsNotNone(read(cert(extra=_phrase(900, 2400, '010101010101'))))

    def test_a_name_on_two_rows_falls_back(self):
        top = ['AISYAH BINTI', 'RAHMAN', '010101-01-0101', 'JH001A043', 'SMK CONTOH']
        self.assertIsNone(read(cert(top=top)))

    def test_no_ic_row_falls_back(self):
        self.assertIsNone(read(cert(top=['AISYAH BINTI RAHMAN', 'JH001A043', 'SMK CONTOH'])))


class TheDigitalPdf(SimpleTestCase):
    """A text layer is read from its own character boxes, so lines stored out of order still pair."""

    def _pdf(self):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.setFont('Helvetica', 10)
        top = 800

        def line(x, y, s):
            c.drawString(x, top - y, s)
        # The GRADES first and the subjects in a shuffled order — the stored order a scanner's OCR
        # layer can have (the live a108 layer paired four subjects with the wrong grades).
        for i, (_, g) in reversed(list(enumerate(SUBJECTS))):
            line(400, 300 + 16 * i, g)
        for y, s in ((60, 'Calon yang namanya tercatat di bawah telah menduduki peperiksaan'),
                     (72, 'layak dianugerahi'), (100, 'SIJIL PELAJARAN MALAYSIA'),
                     (130, 'AISYAH BINTI RAHMAN'), (146, '010101-01-0101'), (162, 'JH001A043'),
                     (178, 'SMK CONTOH')):
            line(50, y, s)
        line(50, 260, 'Mata Pelajaran')
        line(410, 260, 'Gred')
        for i in (3, 0, 4, 1, 2):
            line(50, 300 + 16 * i, SUBJECTS[i][0])
        line(50, 420, 'UJIAN LISAN BAHASA MELAYU: CEMERLANG')
        line(50, 600, 'JUMLAH MATA PELAJARAN LIMA')
        line(50, 616, 'PEPERIKSAAN TAHUN 2022')
        c.showPage()
        c.save()
        return buf.getvalue()

    def test_pairs_by_position_not_by_stored_order(self):
        pdf = self._pdf()
        r = parse_spm_cert('', None, pdf)
        self.assertEqual(grades(r), EXPECTED)
        self.assertEqual(r['nric'], '010101-01-0101')
        self.assertIn('2022', r['exam'])

    def test_an_image_upload_without_words_falls_back(self):
        self.assertIsNone(parse_spm_cert('layak dianugerahi', None, b'\x89PNG....'))

    def test_a_damaged_pdf_falls_back(self):
        self.assertIsNone(parse_spm_cert('', None, b'%PDF-1.4 broken'))


class TestEnsureExamYear(SimpleTestCase):
    def test_backfills_from_text(self):
        self.assertEqual(
            ensure_exam_year('SIJIL PELAJARAN MALAYSIA', 'foo PEPERIKSAAN TAHUN 2022 bar'),
            'SIJIL PELAJARAN MALAYSIA TAHUN 2022')

    def test_idempotent(self):
        already = 'SIJIL PELAJARAN MALAYSIA TAHUN 2025'
        self.assertEqual(ensure_exam_year(already, 'PEPERIKSAAN TAHUN 2022'), already)

    def test_no_year_in_text(self):
        self.assertEqual(ensure_exam_year('SIJIL PELAJARAN MALAYSIA', 'no year here'),
                         'SIJIL PELAJARAN MALAYSIA')


class TheUploadSeam(TestCase):
    """`vision._run_field_extraction_impl` hands the reader the shared OCR's words and the bytes."""

    def test_the_certificate_is_read_from_the_shared_word_boxes(self):
        from unittest.mock import patch

        from apps.scholarship import vision
        from apps.scholarship.models import ApplicantDocument
        from apps.scholarship.tests.factories import make_application
        app = make_application('profile_complete')
        doc = ApplicantDocument.objects.create(application=app, doc_type='results_slip',
                                               storage_path=f'{app.id}/rs/c')
        words = cert()
        with patch('apps.scholarship.vision.extract_document_fields') as gemini, \
             patch('apps.scholarship.vision._call_gemini_json', return_value={'_error': 'test'}) as ai:
            vision.run_field_extraction_for_document(
                doc, names=[], ocr={'text': text_of(words), 'words': words, 'image': b'img', 'error': None})
        gemini.assert_not_called()
        ai.assert_not_called()
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields.get('capture'), 'deterministic')
        self.assertEqual([(x['subject'], x['grade']) for x in doc.vision_fields['fields']['results']], EXPECTED)
