"""The STPM Exact reader (`stpm_parse`, STPM exact-read S2) on SYNTHETIC twins of each layout.

⚠ COMMITTED DATA, SO NOTHING REAL. The layouts (label wording, row order, the slip's paper rows,
the certificate's bilingual subtitles and notes page, the transcript's English-then-Malay pages)
were copied from the real corpus in `eval/snapshots/`, which is gitignored PII. Every name, IC,
index number, serial and grade here is INVENTED. The real-corpus score is the hand-run
`eval/stpm_parse_check.py`, never a test.
"""
from django.test import SimpleTestCase

from apps.scholarship import stpm_parse
from apps.scholarship.stpm_parse import GRADE_POINTS, PARSER_VERSION, parse

# ── A text-layer results slip (a digital PDF, 2022-2025) ──────────────────────────────────────

_PAPERS = {'PENGAJIAN AM': 4, 'BAHASA MELAYU': 5, 'SEJARAH': 4, 'GEOGRAFI': 4, 'EKONOMI': 4,
           'SENI VISUAL': 3}


def slip_text(subjects, *, name='NUR ALYA BINTI KAMAL', ic='050101-10-1234', pngk='3.17',
              count=None, title='Slip Keputusan Peperiksaan STPM 2024', released='18 Jun 2025'):
    """`subjects` = [(code, name, grade, point)] → the slip's text layer, one cell per line."""
    lines = ['MAJLIS PEPERIKSAAN MALAYSIA', 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA (STPM)', title,
             f'Nama : {name}', f'No. Kad Pengenalan : {ic}', 'Angka Giliran : SA0001/1001',
             'No. Siri : 1234567',
             f'Bil. Mata Pelajaran Didaftarkan : {len(subjects) if count is None else count}',
             f'Purata Nilai Gred Keseluruhan (PNGK) : {pngk}',
             'KOD MATA PELAJARAN WAJARAN', '(%)', 'GRED', 'KERTAS', 'GRED MATA', 'PELAJARAN',
             'NILAI GRED MATA', 'PELAJARAN']
    for code, subject, grade, point in subjects:
        n = _PAPERS.get(subject, 4)
        lines.append(f'{code}  {subject}')
        lines += [f'    {subject} {k}' for k in range(1, n + 1)]
        lines += ['  25.0'] * n + ['  A-', '  C+', '  B', '  A', '  B'][:n]   # paper grades differ
        lines.append(f'{grade} {point}')
    lines += ['  Nota: Keputusan gred kertas yang dicatatkan ialah keputusan yang terbaik.',
              'Ketua Eksekutif', f'Majlis Peperiksaan Malaysia Tarikh Keputusan Dikeluarkan : {released}',
              'Nota Penting:', '1. Slip keputusan ini bukan sijil STPM. Majlis Peperiksaan Malaysia '
              'berhak meminda butiran pada slip keputusan ini sebelum sijil dikeluarkan.']
    return '\n'.join(lines)


FOUR = [('900', 'PENGAJIAN AM', 'A-', '3.67'), ('910', 'BAHASA MELAYU', 'B', '3.00'),
        ('940', 'SEJARAH', 'B+', '3.33'), ('942', 'GEOGRAFI', 'B-', '2.67')]     # PNGK 3.17

# ── Word boxes (a scan / photo): rows of (text, x) laid out top to bottom ─────────────────────


def words_of(rows):
    out = []
    for i, row in enumerate(rows):
        for text, x in row:
            out.append({'text': text, 'cx': float(x), 'cy': 100.0 + 40 * i, 'h': 20, 'angle': 0.0})
    return out


def _r(*cells):
    """'900@60 PENGAJIAN@110' → [('900', 60), ('PENGAJIAN', 110)]."""
    return [(c.rsplit('@', 1)[0], int(c.rsplit('@', 1)[1])) for c in cells]


def slip_words(subject_rows, *, count='5', pngk='2.83'):
    head = [
        _r('MAJLIS@280', 'PEPERIKSAAN@370', 'MALAYSIA@480'),
        _r('MPM@180', 'SIJIL@270', 'TINGGI@330', 'PERSEKOLAHAN@430', 'MALAYSIA@540', '(STPM)@600'),
        _r('Slip@260', 'Keputusan@330', 'Peperiksaan@420', 'STPM@500', '2025@550'),
        _r('Nama@60', ':@360', 'ARJUN@420', 'A@470', '/@480', 'L@490', 'KUMAR@540'),
        _r('No.@55', 'Kad@85', 'Pengenalan@140', ':@360', '060202-14-5678@430'),
        _r('Angka@60', 'Giliran@110', ':@360', 'SB0002@400', '/@430', '2002@455'),
        _r('No.@55', 'Siri@80', ':@360', '7654321@400'),
        _r('Bil@50', '.@60', 'Mata@85', 'Pelajaran@140', 'Didaftarkan@210', ':@360', f'{count}@375'),
        _r('Purata@65', 'Nilai@105', 'Gred@140', 'Keseluruhan@205', '(@255', 'PNGK@275', ')@300',
           ':@355', f'{pngk}@385'),
        _r('WAJARAN@420', 'GRED@500', 'GRED@565', 'MATA@600', 'NILAI@665', 'GRED@700'),
        _r('KOD@60', 'MATA@200', 'PELAJARAN@250'),
    ]
    tail = [
        _r('Nota@320', ':@345', 'Keputusan@390', 'gred@450', 'kertas@500', 'terbaik@840'),
        _r('Ketua@65', 'Eksekutif@130'),
        _r('Majlis@66', 'Peperiksaan@144', 'Malaysia@234', 'Tarikh@818', 'Keputusan@886',
           'Dikeluarkan@976', ':@1024', '18@1040', 'Jun@1067', '2026@1105'),
        _r('Nota@60', 'Penting@115', ':@150'),
        _r('1.@50', 'Slip@80', 'keputusan@140', 'ini@190', 'bukan@230', 'sijil@275', 'STPM@315'),
    ]
    return words_of(head + subject_rows + tail)


def _paper(name, k, grade):
    return _r(*[f'{w}@{120 + 50 * j}' for j, w in enumerate(name.split())], f'{k}@260',
              '25.0@425', f'{grade}@497')


# A 2025 scanned slip: five subjects, one absent (X), one sign split into its own box ('C' '+'),
# and OCR debris rows between the papers.
SCAN_ROWS = [
    _r('900@60', 'PENGAJIAN@115', 'AM@160', 'A-@585', '3.67@700'),
    _paper('PENGAJIAN AM', 1, 'A'), _paper('PENGAJIAN AM', 2, 'B'),
    _r('910@60', 'BAHASA@110', 'MELAYU@160', 'X@585'),
    _r('940@60', 'SEJARAH@110', 'C@580', '+@588', '2.33@700'),
    _paper('SEJARAH', 1, 'C-'), _r('FFFA@671'),
    _r('944@60', 'EKONOMI@110', 'C@585', '2.00@700'),
    _paper('EKONOMI', 1, 'D+'),
    _r('970@60', 'SENI@90', 'VISUAL@120', 'B@580', '+@588', '3.33@700'),
]

# ── A 2025 bilingual certificate, as word boxes ───────────────────────────────────────────────

CERT_TOP = [
    _r('MAJLIS@900', 'PEPERIKSAAN@1070', 'MALAYSIA@1260'),
    _r('(@840', 'MALAYSIAN@920', 'EXAMINATIONS@1100', 'COUNCIL@1280', ')@1350'),
    _r('SIJIL@785', 'TINGGI@900', 'PERSEKOLAHAN@1110', 'MALAYSIA@1350'),
    _r('(@770', 'MALAYSIA@850', 'HIGHER@1000', 'SCHOOL@1130', 'CERTIFICATE@1310', ')@1415'),
    _r('Dengan@217', 'ini@285', 'disahkan@364', 'bahawa@473', 'MEI@622', 'LING@700', 'TAN@760'),
    _r('(@177', 'This@206', 'is@247', 'to@276', 'certify@333', 'that@400'),
    _r('No.@195', 'Kad@245', 'Pengenalan@347', '060303080123@658', 'telah@1147', 'menduduki@1254'),
    _r('Identity@219', 'Card@299', 'No.@352', 'sat@1379', 'for@1419', 'the@1460'),
    _r('Angka@210', 'Giliran@297', ':@344', 'SC0003@419', '/@472', '3003@505', 'Tahun@1188',
       'Peperiksaan@1309', ':@1389', '2025@1450'),
    _r('(@180', 'Index@216', 'No.@275', ')@300', 'SMK@397', 'CONTOH@486', '(@1157', 'Year@1188',
       'of@1234', 'Examination@1324', ')@1404'),
    _r('Mata@204', 'Pelajaran@300', 'Gred@794', 'Nilai@992', 'Gred@1056'),
    _r('(@179', 'Subject@226', ')@275', '(@771', 'Grade@811', ')@851', '(@968', 'Grade@1008',
       'Point@1082', ')@1118'),
]


def cert_subject(name, english, grade, point, status='LULUS PENUH'):
    status_words = status.split()
    return [_r(*[f'{w}@{240 + 90 * j}' for j, w in enumerate(name.split())],
               *([f'{grade}@794'] if grade else []), f'{point}@1034', '(@1291',
               f'{status_words[0]}@1336', f'{status_words[1]}@1427', ')@1475'),
            _r('(@178', *[f'{w}@{230 + 90 * j}' for j, w in enumerate(english.split())],
               ')@600', '(@1355', 'FULL@1384', 'PASS@1444', ')@1474')]


def cert_words(subjects, *, passed='4', pngk='3.50', label='Keseluruhan', top=None):
    rows = list(top or CERT_TOP)
    for s in subjects:
        rows += cert_subject(*s)
    rows += [
        _r('Bilangan@227', 'Mata@318', 'Pelajaran@414', 'Lulus@513', ':@549', f'{passed}@593',
           'Purata@1028', 'Nilai@1105', 'Gred@1170', f'{label}@1283', ':@1363', f'{pngk}@1451'),
        _r('(@180', 'Number@230', 'of@296', 'Subjects@362', 'Passed@461', ')@507', '(@994',
           'Cumulative@1065', 'Grade@1173', 'Point@1248', 'Average@1332', ')@1386'),
        _r('Ketua@1186', 'Eksekutif@1287'),
        _r('Tarikh@1099', 'keputusan@1209', 'diumumkan@1351', ':@1428'),
        _r('18@1183', 'Jun@1227', '2026@1287'),          # the release date: never the exam year
        _r('1111111/25@1396'),
    ]
    return words_of(rows)


CERT_FOUR = [('PENGAJIAN AM', 'GENERAL STUDIES', 'B', '3.00'), ('BAHASA MELAYU', 'MALAY', 'A', '4.00'),
             ('EKONOMI', 'ECONOMICS', 'A', '4.00'), ('GEOGRAFI', 'GEOGRAPHY', 'B', '3.00')]  # 3.50

NOTES_PAGE = """PENERANGAN
(EXPLANATORY NOTES)
Gred Mata Pelajaran (Subject Grade) NGMP (SGP) Catatan (Notes)
A 4.00 Lulus Penuh (Full Pass)
A- 3.67 Lulus Penuh (Full Pass)
C- 1.67 Lulus Sebahagian (Partial Pass)
F 0.00 Gagal (Fail)"""


def cert_text(subjects, *, passed='4', pngk='3.50', ic='050505-12-0555'):
    """A 2023/24 paper certificate as a clean text layer: 'Kumulatif', dashed IC, no English
    subtitles — followed by its explanatory-notes page (which carries a grade table)."""
    lines = ['MAJLIS PEPERIKSAAN MALAYSIA', '(MALAYSIAN EXAMINATIONS COUNCIL)',
             'SIJIL TINGGI PERSEKOLAHAN MALAYSIA', '(MALAYSIA HIGHER SCHOOL CERTIFICATE)',
             'Dengan ini disahkan bahawa HANA BINTI OMAR', '(This is to certify that',
             f'No. Kad Pengenalan {ic} telah menduduki peperiksaan', 'Identity Card No. sat for the',
             'Angka Giliran: SD0004/4004 Tahun Peperiksaan: 2023', '(Index No.) (Year of Examination)',
             'Mata Pelajaran Gred Nilai Gred', '(Subject) (Grade) (Grade Point)']
    lines += [f'{n} {g} {p} (LULUS PENUH)' for n, _e, g, p in subjects]
    lines += [f'Bilangan Mata Pelajaran Lulus: {passed} Purata Nilai Gred Kumulatif: {pngk}',
              '(Number of Subjects Passed) (Cumulative Grade Point Average)',
              'Tarikh keputusan diumumkan: 23 Julai 2024', NOTES_PAGE]
    return '\n'.join(lines)


TRANSCRIPT = """MAJLIS PEPERIKSAAN MALAYSIA
(MALAYSIAN EXAMINATIONS COUNCIL)
Date : 08 July 2026
SIJIL TINGGI PERSEKOLAHAN MALAYSIA (STPM)
TRANSKRIP 2025
Name : RAVI A/L MUTHU
Identity Card No : 060606100606
Index No. : SE0005/5005
Serial No. : 5555555
Number of Subjects Registered : 4
Cumulative Grade Point Average : 3.17
900 GENERAL STUDIES
A- 3.67
910 MALAY
B 3.00
Note: The paper grade results stated are the best results.
MAJLIS PEPERIKSAAN MALAYSIA
TRANSKRIP 2025
Nama : RAVI A/L MUTHU
No. Kad Pengenalan : 060606100606
Angka Giliran : SE0005/5005
No. Siri : 5555555
Bil. Mata Pelajaran Didaftarkan : 4
Purata Nilai Gred Keseluruhan (PNGK) : 3.17
KOD MATA PELAJARAN WAJARAN % GRED
KERTAS
900 PENGAJIAN AM
PENGAJIAN AM 1
  29.00
  B-
A- 3.67
910 BAHASA MELAYU
BAHASA MELAYU 1
  33.00
  A
B 3.00
940 SEJARAH
SEJARAH 1
  29.00
  A
B+ 3.33
942 GEOGRAFI
GEOGRAFI 1
  32.00
  C+
B- 2.67
Nota: Keputusan gred kertas yang dicatatkan ialah keputusan yang terbaik."""


class TheSlip(SimpleTestCase):

    def test_a_text_layer_slip_reads_exact(self):
        r = parse(slip_text(FOUR))
        self.assertEqual(r['candidate_name'], 'NUR ALYA BINTI KAMAL')
        self.assertEqual((r['nric'], r['index_no']), ('050101101234', 'SA0001/1001'))
        self.assertEqual((r['exam_year'], r['cgpa'], r['cgpa_label']), ('2024', '3.17', 'PNGK'))
        self.assertEqual(r['results'], [{'subject': 'PENGAJIAN AM', 'grade': 'A-'},
                                        {'subject': 'BAHASA MELAYU', 'grade': 'B'},
                                        {'subject': 'SEJARAH', 'grade': 'B+'},
                                        {'subject': 'GEOGRAFI', 'grade': 'B-'}])
        self.assertEqual([k for k in r if k.startswith('_')], ['_rows_from_entry', '_rows_sign_from_point'])  # moved out

    def test_paper_rows_are_never_subjects(self):
        r = parse(slip_text(FOUR))
        self.assertEqual(len(r['results']), 4)          # not the 17 paper rows
        self.assertNotIn('PENGAJIAN AM 1', [x['subject'] for x in r['results']])

    def test_the_layout_is_never_returned(self):
        r = parse(slip_text(FOUR))
        self.assertFalse({'layout', '_layout', 'form', 'serial'} & set(r))
        self.assertEqual(r['exam'], 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2024')
        self.assertEqual(parse('', cert_words(CERT_FOUR))['exam'], 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025')

    def test_the_year_is_the_title_never_the_release_date(self):
        r = parse(slip_text(FOUR, title='Slip Keputusan Peperiksaan STPM 2025', released='18 Jun 2025'))
        self.assertEqual(r['exam_year'], '2025')

    def test_an_online_portal_print_is_a_slip(self):
        text = slip_text(FOUR) + '\nhttps://stpm.mpm.edu.my/stpmK/result.php 6/20/26, 14:19\nPage 1 of 1'
        self.assertIsNotNone(parse(text))

    def test_a_scanned_slip_reads_from_word_boxes(self):
        r = parse('', slip_words(SCAN_ROWS))
        self.assertEqual(r['candidate_name'], 'ARJUN A/L KUMAR')
        self.assertEqual(r['nric'], '060202145678')
        self.assertEqual([x['grade'] for x in r['results']], ['A-', 'X', 'C+', 'C', 'B+'])

    def test_grade_x_is_kept_as_printed(self):
        r = parse('', slip_words(SCAN_ROWS))
        self.assertEqual(r['results'][1], {'subject': 'BAHASA MELAYU', 'grade': 'X'})

    def test_a_missing_letter_is_never_inferred_from_its_point(self):
        # Owner ruling: the grade LETTER must be read from the document.
        for row in (_r('944@60', 'EKONOMI@110', '2.00@700'),              # letter lost
                    _r('944@60', 'EKONOMI@110', '0@585', '2.00@700')):    # debris for the letter
            rows = list(SCAN_ROWS)
            rows[7] = row
            self.assertIsNone(parse('', slip_words(rows)))

    def _scan_ekonomi(self, *cells, entered=None):
        rows = list(SCAN_ROWS)
        rows[7] = _r('944@60', 'EKONOMI@110', *cells)
        mine = (lambda subject: entered if subject == 'EKONOMI' else None) if entered else None
        return parse('', slip_words(rows), entered=mine)

    def test_a_noisy_point_snaps_to_the_fixed_scale(self):
        for noisy in ('3.66', '3.7', '367', '3,67', '3.670'):
            r = parse(slip_text(FOUR).replace('\nA- 3.67\n', f'\nA- {noisy}\n', 1))
            self.assertEqual(r['results'][0]['grade'], 'A-', noisy)
        for noisy in ('2.01', '1.99', '2.0', '200'):
            self.assertIsNotNone(self._scan_ekonomi('C@585', f'{noisy}@700'), noisy)

    def test_a_point_far_from_the_scale_falls_back(self):
        self.assertIsNone(parse(slip_text(FOUR).replace('\nA- 3.67\n', '\nA- 3.50\n', 1)))
        self.assertIsNone(self._scan_ekonomi('C@585', '2.10@700'))         # 0.10 from 2.00
        subjects = [('PENGAJIAN AM', 'GENERAL STUDIES', 'B', '3.50')] + CERT_FOUR[1:]
        self.assertIsNone(parse('', cert_words(subjects)))

    def test_a_snapped_point_that_disagrees_with_the_letter_falls_back(self):
        self.assertIsNone(parse(slip_text(FOUR).replace('\nA- 3.67\n', '\nA- 3.34\n', 1)))   # → 3.33 = B+
        self.assertIsNone(self._scan_ekonomi('C@585', '2.31@700'))                          # → 2.33 = C+


    def test_a_name_wrapped_onto_one_row_reads_whole(self):
        text = slip_text(FOUR, name='AWANG AHMAD BIN').replace(
            'No. Kad Pengenalan', '            YUSOF\nNo. Kad Pengenalan', 1)
        self.assertEqual(parse(text)['candidate_name'], 'AWANG AHMAD BIN YUSOF')

    def test_a_school_row_before_the_ic_is_never_part_of_the_name(self):
        text = slip_text(FOUR).replace('No. Kad Pengenalan', 'SMK SERI INDAH\nNo. Kad Pengenalan', 1)
        self.assertIsNone(parse(text))

    def test_two_rows_before_the_ic_fall_back(self):
        text = slip_text(FOUR, name='AWANG AHMAD').replace(
            'No. Kad Pengenalan', 'BIN\nYUSOF\nNo. Kad Pengenalan', 1)
        self.assertIsNone(parse(text))

    def test_a_stamp_word_on_the_name_line_falls_back(self):
        for stamp in ('SALINAN', 'COPY', 'SAH', 'DIAKUI', 'BENAR', 'SPECIMEN'):
            self.assertIsNone(parse(slip_text(FOUR, name=f'NUR ALYA BINTI KAMAL {stamp}')), stamp)

    def test_the_grade_pair_must_close_its_block(self):
        text = slip_text(FOUR)
        moved = text.replace('900  PENGAJIAN AM\n', '900  PENGAJIAN AM\nA- 3.67\n', 1).replace(
            '\nA- 3.67\n910', '\n910', 1)
        self.assertNotEqual(moved, text)
        self.assertIsNone(parse(moved))

    def test_a_transcript_reads_from_its_malay_page(self):
        r = parse(TRANSCRIPT)
        self.assertEqual(r['candidate_name'], 'RAVI A/L MUTHU')
        self.assertEqual([x['subject'] for x in r['results']],
                         ['PENGAJIAN AM', 'BAHASA MELAYU', 'SEJARAH', 'GEOGRAFI'])
        self.assertEqual((r['exam_year'], r['cgpa']), ('2025', '3.17'))


class TheCertificate(SimpleTestCase):

    def test_a_2025_certificate_reads_exact(self):
        r = parse('', cert_words(CERT_FOUR))
        self.assertEqual(r['candidate_name'], 'MEI LING TAN')
        self.assertEqual((r['nric'], r['index_no'], r['exam_year']), ('060303080123', 'SC0003/3003', '2025'))
        self.assertEqual(r['cgpa'], '3.50')
        self.assertEqual([x['subject'] for x in r['results']],
                         ['PENGAJIAN AM', 'BAHASA MELAYU', 'EKONOMI', 'GEOGRAFI'])

    def test_a_2023_paper_certificate_and_its_notes_page(self):
        subjects = [('PENGAJIAN AM', '', 'A-', '3.67'), ('BAHASA MELAYU', '', 'B', '3.00'),
                    ('GEOGRAFI', '', 'C+', '2.33'), ('EKONOMI', '', 'B', '3.00')]
        r = parse(cert_text(subjects, pngk='3.00'))
        self.assertEqual(r['nric'], '050505120555')
        self.assertEqual(r['exam_year'], '2023')
        self.assertEqual([x['grade'] for x in r['results']], ['A-', 'B', 'C+', 'B'])   # notes ignored

    def test_a_partial_pass_counts_as_passed(self):
        subjects = [('PENGAJIAN AM', 'GENERAL STUDIES', 'B', '3.00'),
                    ('BAHASA MELAYU', 'MALAY', 'C-', '1.67', 'LULUS SEBAHAGIAN'),
                    ('SEJARAH', 'HISTORY', 'C+', '2.33'), ('EKONOMI', 'ECONOMICS', 'C+', '2.33')]
        self.assertEqual(parse('', cert_words(subjects, pngk='2.33'))['results'][1]['grade'], 'C-')

    def test_a_greek_lookalike_subject_still_reads(self):
        subjects = [('PENGAJIAN AM', 'GENERAL STUDIES', 'B', '3.00'), ('BAHASA MELAYU', 'MALAY', 'A', '4.00'),
                    ('ΕΚΟΝΟΜΙ', 'ECONOMICS', 'A', '4.00'),
                    ('GEOGRAFI', 'GEOGRAPHY', 'B', '3.00')]
        self.assertEqual(parse('', cert_words(subjects))['results'][2]['subject'], 'EKONOMI')

    def test_a_stamp_word_on_the_certificate_name_falls_back(self):
        top = list(CERT_TOP)
        top[4] = _r('Dengan@217', 'ini@285', 'disahkan@364', 'bahawa@473', 'MEI@622', 'LING@700',
                    'TAN@760', 'DIAKUI@900')
        self.assertIsNone(parse('', cert_words(CERT_FOUR, top=top)))

    def test_a_wrapped_name_falls_back(self):
        top = list(CERT_TOP)
        top.insert(5, _r('WEI@622', 'JIE@700'))
        self.assertIsNone(parse('', cert_words(CERT_FOUR, top=top)))

    def test_a_skewed_photo_falls_back(self):
        words = cert_words([('PENGAJIAN AM', 'GENERAL STUDIES', '', '3.00')] + CERT_FOUR[1:])
        words.append({'text': 'B', 'cx': 794.0, 'cy': 100.0 + 40 * 11.5, 'h': 20, 'angle': 0.0})
        self.assertIsNone(parse('', words))


class ThePassedCountMayBeAbsent(SimpleTestCase):
    """Parser 1.2.0: "Bilangan Mata Pelajaran Lulus" printed with NO number read (the live a265 scan)
    is allowed when every other gate passes and the printed PNGK equals the recomputed one; a number
    that IS read must match, and a stray token where the number belongs is a mis-read → None."""

    @staticmethod
    def _entered(n):
        def entered(subject):
            return None
        entered.count = n            # the number of STPM subjects the student entered
        return entered

    def _with_count(self, token, **kw):
        words = cert_words(CERT_FOUR, passed='9', **kw)
        if token is None:
            return [w for w in words if w['text'] != '9']
        return [dict(w, text=token) if w['text'] == '9' else w for w in words]

    def test_an_absent_count_reads_exact_when_the_rows_match_the_entered_subjects(self):
        r = parse('', self._with_count(None), entered=self._entered(4))
        self.assertEqual(r['cgpa'], '3.50')
        self.assertEqual([x['grade'] for x in r['results']], ['B', 'A', 'A', 'B'])

    def test_an_absent_count_on_a_scan_needs_the_entered_subjects(self):
        self.assertIsNone(parse('', self._with_count(None)))                         # no entry
        self.assertIsNone(parse('', self._with_count(None), entered=self._entered(5)))  # 4 read, 5 entered

    def test_an_absent_count_on_a_text_layer_needs_no_entry(self):
        text = cert_text(CERT_FOUR).replace('Lulus: 4 Purata', 'Lulus: Purata')
        self.assertEqual(parse(text)['cgpa'], '3.50')
        self.assertIsNone(parse(text, entered=self._entered(3)))                     # entry disagrees

    def test_an_absent_count_still_needs_the_pngk_to_add_up(self):
        self.assertIsNone(parse('', self._with_count(None, pngk='3.67'), entered=self._entered(4)))

    def test_a_read_count_must_still_match(self):
        self.assertIsNotNone(parse('', self._with_count('4')))
        self.assertIsNone(parse('', self._with_count('3')))

    def test_a_misread_count_is_not_an_absent_one(self):
        for token in ('S', '4.', 'l', 'A', '(4)', '(5)'):
            self.assertIsNone(parse('', self._with_count(token), entered=self._entered(4)), token)


# ── A 2023/24 certificate whose text layer is stored COLUMN BY COLUMN (parser 1.1.0) ─────────────

COL_FIVE = [('PENGAJIAN AM', 'A-', '3.67'), ('BAHASA MELAYU', 'B', '3.00'), ('SEJARAH', 'B+', '3.33'),
            ('EKONOMI', 'C+', '2.33'), ('PENGAJIAN PERNIAGAAN', 'A', '4.00')]          # PNGK 3.50


def cert_columns_text(subjects, *, grades=None, points=None, passed=None, pngk='3.50', year='2024',
                      name='DEVI A/P RAMAN', ic='050707-07-0707'):
    """The column-ordered text layer as a digital paper certificate stores it: the subject names
    (with prose and the index number between them), the passed count far away, then every grade
    letter under "Gred", then every point with its status, the year a few lines after its label."""
    grades = [g for _n, g, _p in subjects] if grades is None else grades
    points = [p for _n, _g, p in subjects] if points is None else points
    lines = [f'No. Kad Pengenalan {ic} Identity Card No.',
             f'Dengan ini disahkan bahawa {name} (This is to certify that',
             'SI)IL TINGGI', 'Angka Giliran:', '(Index No.)',
             'PERSEKOLAHAN MALAYSIA dan telah memperoleh gred', 'MALAYSIA HIGHER SCHOOL CERTIFICATE '
             'examination and obtained the following', 'Mata Pelajaran', '(Subject)', 'MPM',
             'dalam mata pelajaran seperti yang berikut', 'grades in the subjects below']
    names = [n for n, _g, _p in subjects]
    lines += names[:3] + ['SD0007/7007'] + names[3:]
    lines += ['Bilangan Mata Pelajaran Lulus:', '(Number of Subjects Passed)', 'Peperiksaan',
              'Pengenalan', '12345/24', 'AS1234567', 'MAJLIS PEPERIKSAAN MALAYSIA',
              '(MALAYSIAN EXAMINATIONS COUNCIL)', 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA',
              '(MALAYSIA HIGHER SCHOOL CERTIFICATE)',
              str(len(subjects) if passed is None else passed),
              'Majlis Peperiksaan Malaysia', 'Gred', '(Grade)']
    lines += grades
    lines += ['telah menduduki peperiksaan', 'Nilai Gred', '(Grade Point)', 'berikut',
              'Tahun Peperiksaan:', '(Year of Examination)', year]
    lines += [f'{p} (LULUS PENUH)' for p in points]
    lines += ['Purata Nilai Gred Kumulatif:', '(Cumulative Grade Point Average)', pngk,
              'Ketua Eksekutif', '(Chief Executive )', 'Majlis Peperiksaan Malaysia',
              'Tarikh keputusan diumumkan:', '(Results announced on)', '23 Julai 2025', '12345']
    return '\n'.join(lines)


class TheColumnOrderedCertificate(SimpleTestCase):
    """Names, then letters, then points — paired by order only from bounded, equal-length lists;
    every gate of the row-ordered read then applies unchanged."""

    def test_it_reads_exact(self):
        r = parse(cert_columns_text(COL_FIVE))
        self.assertEqual((r['candidate_name'], r['nric'], r['exam_year'], r['cgpa']),
                         ('DEVI A/P RAMAN', '050707070707', '2024', '3.50'))
        self.assertEqual([(x['subject'], x['grade']) for x in r['results']],
                         [(n, g) for n, g, _p in COL_FIVE])
        self.assertEqual(r['_rows_from_entry'], [])

    def test_lists_of_different_lengths_fall_back(self):
        self.assertIsNone(parse(cert_columns_text(COL_FIVE, grades=['A-', 'B', 'B+', 'C+'])))
        self.assertIsNone(parse(cert_columns_text(COL_FIVE, points=['3.67', '3.00', '3.33', '2.33'])))
        self.assertIsNone(parse(cert_columns_text(COL_FIVE[:4], grades=[g for _n, g, _p in COL_FIVE],
                                                  points=[p for _n, _g, p in COL_FIVE])))

    def test_a_dropped_sign_is_taken_from_the_point_on_counted_rows(self):
        # Owner ruling B (2026-10-28) — the real-corpus case: the text layer printed "A" for A-.
        r = parse(cert_columns_text(COL_FIVE, grades=['A', 'B', 'B+', 'C+', 'A']))
        self.assertEqual(r['results'][0]['grade'], 'A-')
        self.assertEqual((r['_rows_sign_from_point'], r['_rows_from_entry']), (['PENGAJIAN AM'], []))

    def test_a_dropped_sign_on_an_uncounted_row_falls_back(self):
        self.assertIsNone(parse(cert_columns_text(COL_FIVE, grades=['A-', 'B', 'B+', 'C', 'A'])))

    def test_the_year_is_never_the_release_date(self):
        text = cert_columns_text(COL_FIVE).replace('(Year of Examination)\n2024\n', '(Year of Examination)\n')
        self.assertIsNone(parse(text))
        far = cert_columns_text(COL_FIVE).replace('(Year of Examination)\n',
                                                  '(Year of Examination)\nx\ny\nz\nw\n')
        self.assertIsNone(parse(far))                       # outside the small window

    def test_every_existing_gate_still_applies(self):
        self.assertIsNone(parse(cert_columns_text(COL_FIVE, pngk='3.58')))           # PNGK
        self.assertIsNone(parse(cert_columns_text(COL_FIVE, passed='4')))            # count
        self.assertIsNone(parse(cert_columns_text(COL_FIVE, points=['3.67', '3.00', '3.50', '2.33',
                                                                    '4.00'])))       # off-scale
        self.assertIsNone(parse(cert_columns_text(COL_FIVE, name='DEVI DIAKUI')))    # one name
        self.assertIsNone(parse(cert_columns_text(COL_FIVE) + '\n040404-04-0404'))   # one IC
        unknown = [('PENGAJIAN AMX', 'A-', '3.67')] + COL_FIVE[1:]
        self.assertIsNone(parse(cert_columns_text(unknown)))                         # vocabulary

    def test_an_unknown_subject_is_never_skipped(self):
        text = cert_columns_text(COL_FIVE).replace('SD0007/7007', 'SD0007/7007\nKESUSASTERAAN INGGERIS')
        self.assertIsNone(parse(text))

    def test_an_ambiguous_count_or_stray_point_falls_back(self):
        self.assertIsNone(parse(cert_columns_text(COL_FIVE).replace('12345/24', '12345/24\n7')))
        self.assertIsNone(parse(cert_columns_text(COL_FIVE).replace('berikut', '3.00 (LULUS PENUH)')))

    def test_a_bilingual_subtitle_in_the_subject_column_is_passed_over(self):
        text = cert_columns_text(COL_FIVE).replace('\nBAHASA MELAYU\n', '\n(GENERAL STUDIES)\nBAHASA MELAYU\n')
        self.assertIsNotNone(parse(text))

    def test_the_count_is_read_only_between_its_label_and_the_grade_column(self):
        self.assertIsNotNone(parse(cert_columns_text(COL_FIVE) + '\n7'))     # a stray digit elsewhere
        moved = cert_columns_text(COL_FIVE).replace('(MALAYSIA HIGHER SCHOOL CERTIFICATE)\n5\n',
                                                    '(MALAYSIA HIGHER SCHOOL CERTIFICATE)\n') + '\n5'
        self.assertIsNone(parse(moved))

    def test_only_a_text_layer_reads_this_way(self):
        rows = stpm_parse._rows_of(cert_columns_text(COL_FIVE), None)
        self.assertIsNotNone(stpm_parse._parse_cert(rows))
        self.assertIsNone(stpm_parse._parse_cert(rows, words_given=True))       # a scan's rows


# ── The SAME certificate as pypdf 5.9.0 (production's locked library) lays it out (parser 1.3.0) ──
# Subject names run together on two lines, every letter on the "Gred (Grade)" line, every point on
# one line, and the year / PNGK END their label lines after the English subtitle.

def cert_merged_text(subjects, *, grades=None, points=None, passed=None, pngk='3.50', year='2024',
                     name='DEVI A/P RAMAN', ic='050707-07-0707', cut=5, status='(LULUS PENUH)',
                     year_subtitle='(Year of Examination)', pngk_subtitle='(Cumulative Grade Point Average)'):
    """The merged-line text layer: the subject words are broken after word `cut` (by the index
    number), wherever that falls — even inside a subject name."""
    grades = [g for _n, g, _p in subjects] if grades is None else grades
    points = [p for _n, _g, p in subjects] if points is None else points
    words = ' '.join(n for n, _g, _p in subjects).split()
    lines = [f'No. Kad Pengenalan {ic} Identity Card No.',
             f'Dengan ini disahkan bahawa {name} (This is to certify that', 'SI)IL TINGGI',
             'Angka Giliran: (Index No.)',
             'PERSEKOLAHAN MALAYSIA dan telah memperoleh gred MALAYSIA HIGHER SCHOOL CERTIFICATE '
             'examination and obtained the following', 'Mata Pelajaran (Subject)', 'MPM',
             'seperti yang berikut dalam mata pelajaran grades in the subjects below:)',
             ' '.join(words[:cut]), 'SD0007/7007', ' '.join(words[cut:]),
             'Bilangan Mata Pelajaran Lulus: (Number of Subjects Passed)', 'Peperiksaan (Pengenalan)',
             '12345/24 AS1234567', 'MAJLIS PEPERIKSAAN MALAYSIA (MALAYSIAN EXAMINATIONS COUNCIL) SIJIL TINGGI '
             'PERSEKOLAHAN MALAYSIA (MALAYSIA HIGHER SCHOOL CERTIFICATE)',
             str(len(subjects) if passed is None else passed),
             'Sijil ini sah. Majlis Peperiksaan Malaysia (Malaysian Examinations Council )',
             'Gred (Grade) ' + ' '.join(grades), 'telah menduduki peperiksaan', 'Kod Pusat (No.)',
             'sat for the', 'Nilai Gred (Grade Point)', 'berikut',
             f'Tahun Peperiksaan: {year_subtitle} {year}'.rstrip(),
             ' '.join(f'{p} {status}' for p in points),
             f'Purata Nilai Gred Kumulatif: {pngk_subtitle} {pngk}'.rstrip(),
             'Ketua Eksekutif (Chief Executive ) Majlis Peperiksaan Malaysia (Malaysian Examinations '
             'Council ) Tarikh keputusan diumumkan: (Results announced on) 23 Julai 2025 S', '12345']
    return '\n'.join(lines)


class TheMergedLineCertificate(SimpleTestCase):
    """pypdf 5.9.0's merged lines of the column-ordered certificate: the same bounded, equal-length
    lists, the same gates — tokenised from the merged lines."""

    def test_it_reads_exact(self):
        r = parse(cert_merged_text(COL_FIVE))
        self.assertEqual((r['candidate_name'], r['nric'], r['exam_year'], r['cgpa']),
                         ('DEVI A/P RAMAN', '050707070707', '2024', '3.50'))
        self.assertEqual([(x['subject'], x['grade']) for x in r['results']],
                         [(n, g) for n, g, _p in COL_FIVE])

    def test_a_subject_name_broken_across_the_lines_is_rejoined(self):
        for cut in (1, 3, 6, 7):                       # inside PENGAJIAN AM, BAHASA MELAYU, PERNIAGAAN
            r = parse(cert_merged_text(COL_FIVE, cut=cut))
            self.assertEqual([x['subject'] for x in r['results']], [n for n, _g, _p in COL_FIVE], cut)

    def test_the_one_item_per_line_twin_reads_the_same(self):
        merged, lines = parse(cert_merged_text(COL_FIVE)), parse(cert_columns_text(COL_FIVE))
        self.assertEqual(merged['results'], lines['results'])

    def test_multi_word_and_bracketed_subjects(self):
        subjects = [('PENGAJIAN AM', 'A-', '3.67'), ('MATEMATIK LANJUTAN (T)', 'B', '3.00'),
                    ('MATEMATIK (T)', 'B+', '3.33'), ('TAHFIZ AL-QURAN', 'A', '4.00')]   # PNGK 3.50
        r = parse(cert_merged_text(subjects, cut=4))
        self.assertEqual([x['subject'] for x in r['results']], [n for n, _g, _p in subjects])

    def test_a_dropped_sign_is_taken_from_the_point_on_counted_rows(self):
        r = parse(cert_merged_text(COL_FIVE, grades=['A', 'B', 'B+', 'C+', 'A']))
        self.assertEqual(r['results'][0]['grade'], 'A-')
        self.assertEqual(r['_rows_sign_from_point'], ['PENGAJIAN AM'])
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, grades=['A-', 'B', 'B+', 'C', 'A'])))
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, grades=['B', 'B', 'B+', 'C+', 'A'])))

    def test_lists_of_different_lengths_fall_back(self):
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, grades=['A-', 'B', 'B+', 'C+'])))
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, points=['3.67', '3.00', '3.33', '2.33'])))
        self.assertIsNone(parse(cert_merged_text(COL_FIVE[:4], grades=[g for _n, g, _p in COL_FIVE],
                                                 points=[p for _n, _g, p in COL_FIVE])))

    def test_every_existing_gate_still_applies(self):
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, pngk='3.58')))            # PNGK
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, passed='4')))             # count
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, points=['3.67', '3.00', '3.50', '2.33',
                                                                   '4.00'])))        # off-scale
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, name='DEVI DIAKUI')))     # one name
        self.assertIsNone(parse(cert_merged_text(COL_FIVE) + '\n040404-04-0404'))    # one IC
        unknown = [('PENGAJIAN AMX', 'A-', '3.67')] + COL_FIVE[1:]
        self.assertIsNone(parse(cert_merged_text(unknown)))                          # vocabulary

    def test_an_unknown_word_among_the_subjects_is_never_skipped(self):
        text = cert_merged_text(COL_FIVE).replace('EKONOMI PENGAJIAN', 'EKONOMI INGGERIS PENGAJIAN')
        self.assertIsNone(parse(text))
        self.assertIsNone(parse(cert_merged_text(COL_FIVE).replace('SD0007/7007', 'KESUSASTERAAN INGGERIS')))

    def test_a_cut_that_is_not_the_only_one_falls_back(self):
        from unittest import mock
        from apps.scholarship import stpm_columns
        extra = {'PENGAJIAN': 'PENGAJIAN', 'AM': 'AM'}           # makes "PENGAJIAN AM" cut two ways
        with mock.patch.dict(stpm_columns._SUBJECT_BY_KEY, extra):
            self.assertIsNone(stpm_columns._split_names(['PENGAJIAN', 'AM', 'SEJARAH']))
        self.assertEqual(stpm_columns._split_names(['PENGAJIAN', 'AM', 'SEJARAH']), ['PENGAJIAN AM', 'SEJARAH'])
        self.assertIsNone(stpm_columns._split_names(['PENGAJIAN', 'SEJARAH']))

    def test_the_year_and_pngk_need_their_exact_subtitle_and_one_value(self):
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, year='')))
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, year='2024 2025')))
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, year_subtitle='(Date of Results)')))
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, year_subtitle='')))     # no subtitle
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, pngk='')))
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, pngk_subtitle='(Overall Average)')))
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, pngk='3.50 3.50')))

    def test_the_grade_line_holds_letters_only(self):
        self.assertIsNone(parse(cert_merged_text(COL_FIVE).replace('Gred (Grade) A-', 'Gred (Grade) A- 9')))
        twice = cert_merged_text(COL_FIVE).replace('berikut', 'Gred (Grade) A')
        self.assertIsNone(parse(twice))                                              # two headers

    def test_the_point_line_is_strict(self):
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, status='(LULUS PENUH')))   # not closed
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, status='(LULUS) X')))       # debris
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, status='LULUS PENUH')))     # no bracket
        stray = cert_merged_text(COL_FIVE).replace('berikut', '3.00 (LULUS PENUH)')
        self.assertIsNone(parse(stray))                                              # a point elsewhere

    def test_a_status_must_be_exactly_a_known_status(self):
        tail = cert_merged_text(COL_FIVE).replace('4.00 (LULUS PENUH)', '4.00 (LULUS PENUH) Nota: (x)')
        self.assertIsNone(parse(tail))
        self.assertIsNone(parse(cert_merged_text(COL_FIVE, status='(LULUS) (X)')))
        self.assertIsNone(parse(cert_columns_text(COL_FIVE).replace('4.00 (LULUS PENUH)',
                                                                    '4.00 (LULUS PENUH) Nota: (x)')))
        self.assertIsNotNone(parse(cert_merged_text(COL_FIVE, status='(LULUS)')))

    def test_a_subject_word_with_debris_is_never_skipped(self):
        self.assertIsNone(parse(cert_merged_text(COL_FIVE).replace('SD0007/7007', 'SEJARAH,')))
        self.assertIsNone(parse(cert_columns_text(COL_FIVE).replace('SD0007/7007', 'SEJARAH,')))

    def test_only_a_text_layer_reads_this_way(self):
        rows = stpm_parse._rows_of(cert_merged_text(COL_FIVE), None)
        self.assertIsNotNone(stpm_parse._parse_cert(rows))
        self.assertIsNone(stpm_parse._parse_cert(rows, words_given=True))


class RulingB(SimpleTestCase):
    """Owner ruling B (2026-10-28): a missing +/- sign may be taken from the clearly read point, when
    the point is the SAME base letter with a sign, on a row the PNGK counts, the PNGK still adding up."""

    def test_the_row_reader_completes_a_lost_sign(self):
        r = parse(slip_text([('900', 'PENGAJIAN AM', 'A', '3.67')] + FOUR[1:]))
        self.assertEqual(r['results'][0]['grade'], 'A-')
        self.assertEqual(r['_rows_sign_from_point'], ['PENGAJIAN AM'])
        r = parse(slip_text([FOUR[0], ('910', 'BAHASA MELAYU', 'B', '3.33'), FOUR[2],
                             ('942', 'GEOGRAFI', 'B', '2.67')], pngk='3.25'))
        self.assertEqual([x['grade'] for x in r['results']], ['A-', 'B+', 'B+', 'B-'])

    def test_a_clean_read_records_nothing(self):
        self.assertEqual(parse(slip_text(FOUR))['_rows_sign_from_point'], [])

    def test_a_different_base_letter_is_a_disagreement(self):
        self.assertIsNone(parse(slip_text([('900', 'PENGAJIAN AM', 'B', '3.67')] + FOUR[1:])))
        self.assertIsNone(parse(cert_columns_text(COL_FIVE, grades=['B', 'B', 'B+', 'C+', 'A'])))
        self.assertIsNone(parse(slip_text([('900', 'PENGAJIAN AM', 'A', '3.33')] + FOUR[1:])))

    def test_an_uncounted_row_is_refused(self):
        five = FOUR + [('944', 'EKONOMI', 'C', '1.67')]                 # C- is the fifth: not counted
        self.assertIsNone(parse(slip_text(five)))
        self.assertIsNotNone(parse(slip_text(FOUR + [('944', 'EKONOMI', 'C-', '1.67')])))

    def test_a_tie_at_the_counting_boundary_proves_nothing(self):
        # Review probe: a true B whose point is misread 3.33 beside genuine B+ 3.33 rows — whichever
        # 3.33 is counted, the PNGK is the same, so the completed B+ is not proven → None.
        five = [('900', 'PENGAJIAN AM', 'A-', '3.67'), ('910', 'BAHASA MELAYU', 'B+', '3.33'),
                ('940', 'SEJARAH', 'B+', '3.33'), ('942', 'GEOGRAFI', 'B', '3.33'),
                ('944', 'EKONOMI', 'B+', '3.33')]
        self.assertIsNone(parse(slip_text(five, pngk='3.42')))
        clean = five[:3] + [('942', 'GEOGRAFI', 'B+', '3.33')] + five[4:]
        self.assertIsNotNone(parse(slip_text(clean, pngk='3.42')))     # read cleanly: no completion

    def test_the_alternative_reading_must_not_also_add_up(self):
        rows = [{'subject': 'SEJARAH', 'grade': 'B+', 'point': '3.33', 'sign_from_point': True,
                 'base': 'B'}, {'subject': 'EKONOMI', 'grade': 'B', 'point': '3.00'}]
        self.assertFalse(stpm_parse._completions_proven(rows, {0, 1}, '3.00'))    # base fits too
        self.assertTrue(stpm_parse._completions_proven(rows, {0, 1}, '3.17'))

    def test_the_pngk_must_still_add_up(self):
        self.assertIsNone(parse(slip_text([('900', 'PENGAJIAN AM', 'A', '3.67')] + FOUR[1:], pngk='3.33')))
        self.assertIsNone(parse(cert_columns_text(COL_FIVE, grades=['A', 'B', 'B+', 'C+', 'A'],
                                                  pngk='3.67')))


class ItFallsBack(SimpleTestCase):
    """Every unsure read is None — the caller then runs today's Gemini read."""

    def test_a_checker_page(self):
        text = slip_text(FOUR).replace('Slip Keputusan Peperiksaan STPM 2024',
                                       'Halaman Keputusan\nKEPUTUSAN PEPERIKSAAN STPM 2024')
        self.assertIsNone(parse(text))
        self.assertIsNone(parse(slip_text(FOUR) + '\nKembali ke Carian STPM\nCetak'))

    def test_a_garbled_text_layer(self):
        garbled = ('MAJLIS PEPERIKSAAN MALAYSIA\nSIJIL TINGGI PERSEKOLAHAN MALAYSIA\n'
                   '(MALAYSIA HIGHER SCHOOL CERTIFICATE)\n7;3.;9;212?.41.;/.8.C.\n#$.%./* -/&!2/#/\n'
                   '050101011234 @17.3:9;2B2B41=7=7>19?..;\nE\n4.00\nE\n3.67\n3.92')
        self.assertIsNone(parse(garbled))

    def test_an_unknown_layout(self):
        spm = ('LEMBAGA PEPERIKSAAN\nSIJIL PELAJARAN MALAYSIA\nNAMA : SITI AMINAH\n'
               '1103 BAHASA MELAYU A\n1119 BAHASA INGGERIS B+')
        self.assertIsNone(parse(spm))
        self.assertIsNone(parse(''))
        self.assertIsNone(parse(None, []))

    def test_a_cropped_table_with_no_title(self):
        self.assertIsNone(parse(slip_text(FOUR).replace('Slip Keputusan Peperiksaan STPM 2024', '')))

    def test_a_term_result(self):
        self.assertIsNone(parse(slip_text(FOUR, title='Slip Keputusan Peperiksaan STPM 2024 Penggal 1')))

    def test_a_pngk_that_does_not_add_up(self):
        self.assertIsNone(parse(slip_text(FOUR, pngk='3.42')))

    def test_a_grade_that_disagrees_with_its_point(self):
        self.assertIsNone(parse(slip_text([FOUR[0], ('910', 'BAHASA MELAYU', 'B', '3.33')] + FOUR[2:])))

    def test_a_subject_count_that_does_not_match(self):
        self.assertIsNone(parse(slip_text(FOUR, count=5)))
        self.assertIsNone(parse('', cert_words(CERT_FOUR, passed='5')))

    def test_an_unknown_subject(self):
        self.assertIsNone(parse(slip_text([('901', 'PENGAJIAN AMX', 'A-', '3.67')] + FOUR[1:])))

    def test_a_grade_off_the_stpm_scale(self):
        self.assertIsNone(parse(slip_text([('900', 'PENGAJIAN AM', 'A+', '4.00')] + FOUR[1:])))

    def test_a_pngk_out_of_range_or_not_two_decimals(self):
        self.assertIsNone(parse(slip_text(FOUR, pngk='3.2')))
        self.assertIsNone(parse(slip_text(FOUR, pngk='5.00')))

    def test_no_name(self):
        self.assertIsNone(parse(slip_text(FOUR, name='')))
        self.assertIsNone(parse(slip_text(FOUR, name='12345 67')))

    def test_another_persons_ic_on_the_page(self):
        self.assertIsNone(parse(slip_text(FOUR) + '\nNo. Kad Pengenalan : 040404-04-0404'))

    def test_a_name_that_ran_onto_the_ic_row(self):
        self.assertIsNone(parse(slip_text(FOUR, ic='050101-10-1234 SUHAIMI')))

    def test_two_slips_in_one_upload(self):
        self.assertIsNone(parse(slip_text(FOUR) + '\n' + slip_text(FOUR)))

    def test_a_reader_error_is_a_fallback_not_a_crash(self):
        self.assertIsNone(parse('', [{'text': 'MAJLIS'}]))     # a word box with no position


class TheScale(SimpleTestCase):

    def test_the_grade_points(self):
        self.assertEqual(len(GRADE_POINTS), 11)
        self.assertEqual(stpm_parse.STPM_SCALE, frozenset(GRADE_POINTS) | {'X'})

    def test_the_pngk_is_general_studies_plus_the_best_three(self):
        rows = [{'subject': s, 'grade': g, 'point': GRADE_POINTS[g]} for s, g in
                (('PENGAJIAN AM', 'B'), ('EKONOMI', 'C+'), ('SEJARAH', 'B+'), ('GEOGRAFI', 'A-'),
                 ('BIOLOGI', 'F'))]
        self.assertEqual(stpm_parse._pngk(rows)[0], '3.08')    # (3.00 + 3.67 + 3.33 + 2.33) / 4

    def test_the_layout_router(self):
        flat = stpm_parse._letters
        for text, layout in ((slip_text(FOUR), 'slip'), (TRANSCRIPT, 'transcript'),
                             (cert_text(CERT_FOUR), 'certificate')):
            rows = stpm_parse._rows_of(text, None)
            self.assertEqual(stpm_parse._layout(flat(text), rows)[0], layout)

    def test_the_parser_version(self):
        self.assertEqual(PARSER_VERSION, '1.3.0')


# ── The owner's grade rule (2026-10-27): letter and point agree; an unclear one is completed from
# the scale ONLY when the value that was read matches the student's own entry ──────────────────


class TheGradeRule(SimpleTestCase):
    _scan = TheSlip._scan_ekonomi

    def _ok(self, *cells, entered=None):
        r = self._scan(*cells, entered=entered)
        return r and r['results'][3]

    def test_rule_1_both_read_and_agreeing_needs_no_entry(self):
        self.assertEqual(self._ok('C@585', '2.00@700'), {'subject': 'EKONOMI', 'grade': 'C'})

    def test_rule_2_a_missing_point_is_completed_when_the_letter_is_the_students(self):
        self.assertEqual(self._ok('C@585', entered='C'), {'subject': 'EKONOMI', 'grade': 'C'})
        r = self._scan('C@585', entered='C')
        self.assertEqual(r['_rows_from_entry'], ['EKONOMI'])          # the audit list
        self.assertEqual(self._scan('C@585', '2.00@700')['_rows_from_entry'], [])

    def test_a_point_read_clearly_off_the_scale_is_never_completed(self):
        self.assertIsNone(self._scan('C@585', '2.10@700', entered='C'))
        self.assertIsNone(self._scan('C@585', '3.50@700', entered='C'))

    def test_rule_2_only_on_a_row_the_pngk_counts(self):
        rows = list(SCAN_ROWS)
        rows[3] = _r('910@60', 'BAHASA@110', 'MELAYU@160', 'A@585', '4.00@700')
        rows[7] = _r('944@60', 'EKONOMI@110', 'C@585')                # 2.00: outside the best three
        def mine(subject):
            return 'C' if subject == 'EKONOMI' else None
        self.assertIsNone(parse('', slip_words(rows, pngk='3.33'), entered=mine))
        rows[7] = _r('944@60', 'EKONOMI@110', 'C@585', '2.00@700')     # read cleanly: rule 1
        self.assertIsNotNone(parse('', slip_words(rows, pngk='3.33'), entered=mine))

    def test_rule_2_a_lost_letter_is_completed_when_the_point_is_the_students_grade(self):
        self.assertEqual(self._ok('2.00@700', entered='C')['grade'], 'C')
        self.assertEqual(self._ok('0@585', '2.00@700', entered='C')['grade'], 'C')   # debris letter
        self.assertEqual(self._ok('201@700', entered='C')['grade'], 'C')             # snapped point

    def test_rule_3_a_read_value_that_differs_from_the_entry(self):
        self.assertIsNone(self._scan('C@585', entered='B'))
        self.assertIsNone(self._scan('2.00@700', entered='C+'))

    def test_rule_3_no_student_entry_accepts_only_clean_rows(self):
        self.assertIsNone(self._scan('C@585'))
        self.assertIsNone(self._scan('2.00@700'))
        self.assertIsNone(self._scan('C@585', '2.10@700'))

    def test_rule_3_neither_read_or_a_disagreement(self):
        self.assertIsNone(self._scan(entered='C'))
        self.assertIsNone(self._scan('C@585', '2.33@700', entered='C'))
        self.assertIsNone(self._scan('C@585', '2.31@700', entered='C'))     # snaps to C+'s 2.33

    def test_rule_4_the_pngk_still_guards_a_completed_row(self):
        self.assertIsNone(self._scan('B@585', entered='B'))        # B breaks the printed 2.83

    def test_the_students_grade_never_overrides_a_clean_read(self):
        self.assertEqual(self._ok('C@585', '2.00@700', entered='A')['grade'], 'C')
