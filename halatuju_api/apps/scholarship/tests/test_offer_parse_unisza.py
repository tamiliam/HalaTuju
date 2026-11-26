"""OCR-14 phase 8: the UniSZA rules lane (`offer_parse_unisza`). UniSZA PRINTS the IC with NO label: the 12 digits in
brackets after the name on the "Nama :" row, so it is read from that one place and stored with source 'other':
CORROBORATE-ONLY under the usual IC guard (`offer_exact.exact_read`; UniSZA is NOT in
`offer_exact.ISSUER_PRINTS_NO_IC`), kept only when it is exactly the profile IC. Any other IC-like number refuses; the
reference and its bracketed number are never stored; the reporting date is read only from its labelled row after the
registration sentence, never guessed. NO note is excused (owner decision 26 Nov): the template's "berhak menarik
balik tawaran" note refuses (``not_an_offer``), so the default synthetic letter here leaves it out. Synthetic letters
only (made-up names, numbers and addresses)."""
import datetime
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_parse_unisza import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, is_unisza, read_unisza
from apps.scholarship.offer_parse_unisza import unisza_ic_elsewhere, unisza_ink_targets, unisza_later_pages
from apps.scholarship.offer_parse_unisza import unisza_letter_refusal

NAME = 'ZORBEX QUENTARO BIN ALFEN'
IC = '990101145678'
NRIC = '990101-14-5678'
CODE = 'UD6481001'
PROGRAMME = 'SARJANA MUDA SAINS KOMPUTER (TEKNOLOGI MAKLUMAT) DENGAN KEPUJIAN'
FACULTY = 'FAKULTI INFORMATIK DAN KOMPUTERAN'
INTAKE = 'SEM 1 SESI 2026/2027'
OFFER_ON = '15 Julai 2026'
R = ' ' * 84                                    # the right-hand column
W = ' ' * 15                                    # the address's wrapped lines
REF_ROW = R + 'Rujukan : UniSZA.100-1/2/3 (45)'
DATED_ROW = R + 'Tarikh : ' + OFFER_ON
ADDRESS = ('NO 12, JALAN MAWAR 3', 'TAMAN SERI MAWAR', '21300 KUALA TERENGGANU', 'TERENGGANU')
TITLE = ('TAWARAN KEMASUKAN KE UNIVERSITI SULTAN ZAINAL ABIDIN (UniSZA) ' + INTAKE,)
GREETING = ('Dengan sukacitanya dimaklumkan bahawa saudara/i ditawarkan mengikuti program pengajian di UniSZA '
            'seperti berikut:',)
ROWS = (('Program Pengajian', PROGRAMME), ('Kod Program Pengajian', CODE), ('Fakulti', FACULTY),
        ('Kampus', 'GONG BADAK'), ('Tempoh Pengajian', '4 TAHUN'))
REGISTER = '1. Sekiranya menerima tawaran ini, saudara/i dikehendaki mendaftar sebagaimana berikut:'
FEES = ('Makluman Yuran Pengajian :',
        '     KOS PENGAJIAN   YURAN PENGAJIAN   YURAN DITANGGUNG KERAJAAN   YURAN PENDAFTARAN',
        '       RM 25,000.00   RM 1,500.00   RM 23,500.00   RM 500.00')
NOTES = ('2. Tawaran ini adalah MUKTAMAD dan tidak boleh dirayu.', '3. Sila bawa dokumen asal semasa pendaftaran.')
FOOTER = ('Sekian, terima kasih.', 'Saya yang menjalankan amanah,', 'QARIM VELTO BIN DURAN', 'Pendaftar',
          'Universiti Sultan Zainal Abidin')
#: The template's own note: "menarik balik" with its condition AFTER it. No excuse is made for it (owner, 26 Nov).
WITHDRAW_NOTE = ('4. Adalah dimaklumkan bahawa Pengurusan Universiti berhak menarik balik tawaran kemasukan ini '
                 'sekiranya terdapat perkara yang tidak memenuhi syarat kelayakan.')
_DAYS = ('ISNIN', 'SELASA', 'RABU', 'KHAMIS', 'JUMAAT', 'SABTU', 'AHAD')
_MONTHS = ('JANUARI', 'FEBRUARI', 'MAC', 'APRIL', 'MEI', 'JUN', 'JULAI', 'OGOS', 'SEPTEMBER', 'OKTOBER',
           'NOVEMBER', 'DISEMBER')


def printed(d, m, y):
    """A reporting date as UniSZA prints it, with the right Malay day name."""
    return f'{d} {_MONTHS[m - 1]} {y} ({_DAYS[datetime.date(y, m, d).weekday()]})'


REPORT_ON = printed(13, 9, 2026)


def report_rows(value=REPORT_ON, place=('DEWAN SULTAN MIZAN, KAMPUS GONG BADAK',)):
    return ('     Tarikh : ' + value, '     Masa   : 8.00 PAGI - 5.00 PETANG', '     Tempat : ' + place[0],
            *(' ' * 22 + p for p in place[1:]))


def row(name, value):
    return name + ' ' * (23 - len(name)) + ': ' + value


def rows_with(name, value):
    return tuple((n, value if n == name else v) for n, v in ROWS)


def layout(name_value=NAME + ' (' + IC + ')', address=ADDRESS, ref_row=REF_ROW, dated_row=DATED_ROW,
           salutation='Saudara/i', title=TITLE, greeting=GREETING, rows=ROWS, mode=(), register=REGISTER,
           report=None, fees=FEES, notes=NOTES, extra=(), footer=FOOTER):
    report = report if report is not None else report_rows()
    lines = [ref_row, dated_row, row('Nama', name_value), *(row('Alamat', a) for a in address[:1]),
             *(W + a for a in address[1:]), salutation, *title, *greeting, *(row(n, v) for n, v in rows), *mode,
             register, *report, *fees, *notes, *extra, *footer]
    return '\n'.join(lines)


def plain(lay):
    return '\n'.join(' '.join(ln.split()) for ln in lay.splitlines() if ln.strip())


def run(lay=None, page2=None):
    lay = lay if lay is not None else layout()
    p1 = plain(lay)
    pages = [p1] + ([page2] if page2 is not None else [])
    return offer_parse.diagnose('\n'.join(pages), p1, lay, pages)


def why(d):
    return d['guard'] or ('empty:' + ','.join(d['empty_required']) if d['empty_required'] else None)


def exact(lay=None, profile=NRIC, why_=None):
    lay = lay if lay is not None else layout()
    p1 = plain(lay)
    return offer_exact.exact_read(p1, from_text_layer=True, page1_layer=p1, page1_layout=lay, page_texts=[p1],
                                  profile_nric=profile, why=why_)


class UniszaLockTest(SimpleTestCase):
    def test_degree_letter_locks_with_its_bracketed_ic_and_reporting_date(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane'], lock['_family']), ('unisza', LANE, 'unisza'))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), (NRIC, 'other'))
        self.assertEqual((lock['programme'], lock['programme_code']), (PROGRAMME, CODE))
        self.assertEqual(lock['intake'], INTAKE)
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('13 Sep 2026', 'Tarikh'))
        self.assertEqual((lock['reporting_venue'], lock['campus'], lock['stream']), ('', '', ''))
        self.assertEqual(lock['offer_date'], OFFER_ON)
        self.assertEqual(lock['institution'], 'UNIVERSITI SULTAN ZAINAL ABIDIN')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_value_shapes_that_still_lock(self):
        for name, value in (('Program Pengajian', 'IJAZAH SARJANA MUDA PERAKAUNAN DENGAN KEPUJIAN'),
                            ('Program Pengajian', 'SARJANA MUDA SAINS (KESIHATAN) SAINS PEMAKANAN'),
                            ('Fakulti', 'FAKULTI PERUBATAN DAN SAINS-KESIHATAN'), ('Kampus', 'TEMBILA'),
                            ('Tempoh Pengajian', '3 TAHUN')):
            with self.subTest(name=name, value=value):
                d = run(layout(rows=rows_with(name, value)))
                self.assertIsNotNone(d['locked'], why(d))
                self.assertEqual(d['locked']['candidate_nric'], NRIC)
        two_line_title = ('TAWARAN KEMASUKAN KE UNIVERSITI SULTAN ZAINAL ABIDIN (UniSZA)', INTAKE)
        semester = ('TAWARAN KEMASUKAN KE UNIVERSITI SULTAN ZAINAL ABIDIN (UniSZA) SEMESTER 1 SESI 2026/2027',)
        for lay in (layout(title=two_line_title), layout(title=semester), layout(address=ADDRESS[:2]),
                    layout(address=ADDRESS + ('MALAYSIA',)), layout(mode=(row('Mod Pengajian', 'SEPENUH MASA'),)),
                    layout(report=report_rows(place=('DEWAN SULTAN MIZAN,', 'KAMPUS GONG BADAK'))),
                    layout(fees=FEES[:2] + ('       RM 25000.00   RM 1500.00   RM 23500.00   RM 500.00',))):
            with self.subTest(lay=lay.count('\n')):
                self.assertIsNotNone(run(lay)['locked'], why(run(lay)))
        self.assertEqual(run(layout(title=semester))['locked']['intake'], 'SEMESTER 1 SESI 2026/2027')

    def test_the_templates_withdrawal_note_refuses_with_no_excuse(self):
        """Owner decision 26 Nov: no new excuses. Every measured UniSZA letter prints this note, so every one goes to
        the AI today, as before."""
        d = run(layout(extra=(WITHDRAW_NOTE,)))
        self.assertIsNone(d['locked'])
        self.assertEqual(d['guard'], 'not_an_offer')
        self.assertEqual(unisza_letter_refusal(plain(layout(extra=(WITHDRAW_NOTE,))), NRIC), 'not_an_offer')

    def test_reference_and_its_numbers_are_never_stored(self):
        lock = run()['locked']
        self.assertFalse(any('100-1/2/3' in str(v) or '(45)' in str(v) for v in lock.values()))
        self.assertFalse(any('1234' in str(v) for k, v in lock.items() if k != 'candidate_nric'))

    def test_a_scan_refuses_no_layout(self):
        d = offer_parse.diagnose(plain(layout()), '', '', None)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('unisza', 'no_layout', None))


class UniszaProgrammeTest(SimpleTestCase):
    def test_the_table_must_hold_its_rows_in_order(self):
        self.assertEqual(run(layout(rows=(ROWS[1], ROWS[0]) + ROWS[2:]))['guard'], 'no_table')
        self.assertEqual(run(layout(rows=(ROWS[0], ROWS[2], ROWS[1]) + ROWS[3:]))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=ROWS[:4]))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=rows_with('Tempoh Pengajian', '8 SEMESTER')))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=rows_with('Kampus', 'Gong Badak')))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=rows_with('Fakulti', 'PUSAT ASAS SAINS')))['guard'], 'programme_shape')
        two_cols = rows_with('Program Pengajian', 'SARJANA MUDA SAINS   DENGAN KEPUJIAN')
        self.assertEqual(run(layout(rows=two_cols))['guard'], 'no_table')         # not read as the first row
        two_cols = rows_with('Fakulti', 'FAKULTI INFORMATIK   DAN KOMPUTERAN')
        self.assertEqual(run(layout(rows=two_cols))['guard'], 'table_shape')
        self.assertEqual(run(layout(mode=(row('Mod Pengajian', 'SEPARUH MASA'),)))['guard'], 'reporting_shape')
        self.assertEqual(run(layout(mode=('Program Pengajian kedua',)))['guard'], 'reporting_shape')

    def test_the_code_must_be_the_one_measured_shape_and_the_only_code(self):
        for code in ('UD648100', 'UD64810011', 'UH6481001', 'ud6481001', CODE + ' X', ''):
            with self.subTest(code=code):
                d = run(layout(rows=rows_with('Kod Program Pengajian', code)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('programme_shape', 'table_shape'))
        for line in ('Kod lama: UD6481002', 'Rujukan program UH6481001', 'Kod: ' + CODE):
            with self.subTest(line=line):
                self.assertEqual(run(layout(extra=(line,)))['guard'], 'second_code')

    def test_a_second_programme_refuses(self):
        self.assertEqual(run(layout(extra=('Pilihan kedua: SARJANA MUDA SAINS DENGAN KEPUJIAN',)))['guard'],
                         'not_degree')

    def test_diploma_asasi_and_non_degree_refuse(self):
        for prog in ('DIPLOMA SAINS KOMPUTER', 'ASASI SAINS', 'SARJANA SAINS KOMPUTER', 'IJAZAH SARJANA SAINS',
                     'SARJANA MUDA DIPLOMA LANJUTAN DENGAN KEPUJIAN', 'SARJANA MUDA ASASI SAINS DENGAN KEPUJIAN',
                     'SARJANA MUDA sains komputer', 'PRA SARJANA MUDA SAINS'):
            with self.subTest(prog=prog):
                d = run(layout(rows=rows_with('Program Pengajian', prog)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('programme_shape', 'not_degree', 'asasi_ai_read'))
        for line in ('Program Diploma Sains Komputer', 'Pelajar Asasi Sains', 'Sila bawa sijil asal.',
                     'Program Persediaan Bahasa', 'Foundation in Science'):
            with self.subTest(line=line):
                self.assertIn(run(layout(extra=(line,)))['guard'], ('not_degree', 'asasi_ai_read'))
        for fac in ('FAKULTI PENGAJIAN DIPLOMA', 'FAKULTI ASASI SAINS'):
            with self.subTest(fac=fac):
                d = run(layout(rows=rows_with('Fakulti', fac)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('not_degree', 'asasi_ai_read'))

    def test_other_titles_and_confirmations_refuse(self):
        for first in ('TAWARAN KEMASUKAN KE PROGRAM DIPLOMA UNIVERSITI SULTAN ZAINAL ABIDIN (UniSZA) ' + INTAKE,
                      'TAWARAN KEMASUKAN KE UNIVERSITI SULTAN ZAINAL ABIDIN (UniSZA) SEM 1 SESI 2026/2027 ASASI',
                      'TAWARAN KEMASUKAN KE UNIVERSITI SULTAN ZAINAL ABIDIN (UniSZA) SEM 4 SESI 2026/2027',
                      'TAWARAN KEMASUKAN KE UNIVERSITI SULTAN ZAINAL ABIDIN SEM 1 SESI 2026/2027'):
            with self.subTest(first=first[-30:]):
                self.assertEqual(read_unisza(layout(title=(first,)))[1], 'no_title')
                self.assertIsNone(run(layout(title=(first,)))['locked'])
        confirm = '\n'.join(('SURAT PENGESAHAN PELAJAR', 'UNIVERSITI SULTAN ZAINAL ABIDIN', 'Nama : ' + NAME,
                             'TAWARAN KEMASUKAN KE UNIVERSITI SULTAN ZAINAL ABIDIN'))
        self.assertIsNone(run(confirm)['locked'])
        self.assertEqual(read_unisza(confirm), (None, 'status_letter'))
        self.assertEqual(run(layout(extra=('PENGESAHAN KEMASUKAN',)))['guard'], 'status_letter')
        for line in ('Permohonan anda TIDAK BERJAYA.', 'Tawaran ini telah DIBATALKAN.',
                     'Tawaran ini telah ditarik balik.', 'Pendaftaran ditangguhkan.'):
            with self.subTest(line=line):
                d = run(layout(extra=(line,)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('status_letter', 'not_an_offer'))


class UniszaIcTest(SimpleTestCase):
    def test_ic_shapes_refuse(self):
        """The bracket must hold the 12 plain digits: a hyphen, an en dash, a minus, a slash, a space, a tab, a short
        or long run, a line split or no bracket at all refuses (UniSZA prints the IC)."""
        for ic in (NRIC, '990101 14 5678', '990101–14–5678', '990101−14−5678', '990101/14/5678',
                   '990101\t14\t5678', '99010114567', '9901011456789', '', '990101\n145678', 'A1234567'):
            with self.subTest(ic=ic):
                d = run(layout(name_value=NAME + ' (' + ic + ')'))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('ic_shape', 'no_head', 'second_ic', 'name_shape'))
        for value in (NAME, NAME + ' ' + IC, NAME + '   (' + IC + ')', NAME + ' [' + IC + ']',
                      NAME + ' (' + IC + ') (' + IC + ')', '(' + IC + ')'):
            with self.subTest(value=value[-8:]):
                d = run(layout(name_value=value))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_shape', 'ic_shape', 'no_head', 'second_ic'))

    def test_a_second_ic_anywhere_refuses(self):
        from apps.scholarship.tests.test_offer_parse_uum import IC_SHAPES
        for ic in IC_SHAPES + ('990102145678', '990102-14-5678', NRIC, IC):
            with self.subTest(ic=ic):
                lay = layout(extra=('No. K/P waris :' + ' ' * 10 + ic,))
                self.assertIsNone(run(lay)['locked'])
                self.assertEqual(read_unisza(lay)[1], 'second_ic')
                self.assertEqual(unisza_letter_refusal(plain(layout()) + '\nWaris ' + ic, NRIC), 'second_ic')
                self.assertIn(run(page2='Universiti Sultan Zainal Abidin\nNo. K/P : ' + ic)['guard'],
                              ('second_ic', 'ic_printed'))
                p1 = plain(layout())
                d = offer_parse.diagnose(p1, p1 + '\nWaris ' + ic, layout(), [p1])
                self.assertIsNone(d['locked'])
        self.assertEqual(unisza_letter_refusal(plain(layout()), NRIC), '')
        self.assertFalse(unisza_ic_elsewhere(plain(layout()), NRIC))
        self.assertTrue(unisza_ic_elsewhere(plain(layout()), '990102-14-5678'))

    def test_the_read_ic_must_stand_in_the_plain_layer(self):
        p1 = plain(layout())
        for page1 in (p1.replace(IC, ''), p1.replace(IC, IC + ' ' + IC)):
            with self.subTest(copies='none' if IC not in page1 else 'two'):
                d = offer_parse.diagnose(p1, page1, layout(), [page1])
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('ic_not_plain', 'identity_disagree', 'second_ic', 'ic_printed'))

    def test_a_reference_or_bracket_number_is_never_the_ic(self):
        for ref in ('Rujukan : UniSZA.100-1/2/3 (' + IC + ')', 'Rujukan : ' + IC, 'Rujukan : UniSZA.' + IC):
            with self.subTest(ref=ref[-6:]):
                d = run(layout(ref_row=R + ref))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('no_head', 'second_ic'))
        for line in ('No. Matrik : (' + IC + ')', 'Rujukan : UniSZA/' + IC, '(' + NRIC + ')'):
            with self.subTest(line=line[:8]):
                d = run(layout(extra=(line,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'second_ic')

    def test_the_ic_is_corroborate_only(self):
        """No label names the IC, so it is source 'other': the usual IC guard keeps it only when it is EXACTLY the
        profile IC; a different or blank profile IC blanks it, and a blank IC on this lane refuses (UniSZA prints
        the IC: not in ISSUER_PRINTS_NO_IC)."""
        self.assertNotIn(LANE, offer_exact.ISSUER_PRINTS_NO_IC)
        ex = exact()
        self.assertIsNotNone(ex)
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric'], ex['fields']['candidate_nric_source']),
                         (LANE, NRIC, 'other'))
        self.assertFalse(ex['offer_reader_inputs'].get('nric_not_printed'))
        for profile in ('880505-10-1234', '990102-14-5678', '990101-14-5679', ''):
            with self.subTest(profile=profile):
                why_ = {}
                self.assertIsNone(exact(profile=profile, why_=why_))
                self.assertEqual(why_, {'lane': LANE, 'reason': 'read_nric_guard'})


class UniszaNeverLocksTest(SimpleTestCase):
    def test_the_address_must_prove_the_name_ended(self):
        """The "Alamat" value must open as an address (a digit, a comma or an address word)."""
        for addr in ('MAWAR INDAH', 'SERI MAWAR'):
            with self.subTest(addr=addr):
                d = run(layout(address=(addr,) + ADDRESS[1:]))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'name_not_ended')
        for addr in ('KAMPUNG MAWAR', 'B-1-12 TAMAN MAWAR', 'LOT 99 LORONG 1', 'NO.12, JALAN C', 'SERI MAWAR, 21300'):
            with self.subTest(addr=addr):
                d = run(layout(address=(addr,) + ADDRESS[1:]))
                self.assertEqual(d['locked']['candidate_name'], NAME, why(d))

    def test_name_must_be_read_exactly(self):
        """Upper case, no linker at its end, no address word inside it (strict: a refusal is safe)."""
        for name in ('Z9RBEX QUENTARO', 'Zorbex Quentaro Bin Alfen', 'ZORBEX QUENTARO BIN', 'ZORBEX A/L',
                     'ZORBEX KAMPUNG ALFEN', 'ZORBEX JALAN ALFEN', 'NO 12 ZORBEX', 'ZORBEX BT ALFEN', 'Z'):
            with self.subTest(name=name):
                d = run(layout(name_value=name + ' (' + IC + ')'))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_shape', 'no_head'))

    def test_unknown_heads_refuse(self):
        self.assertEqual(read_unisza(layout(title=('OFFER OF ADMISSION',)))[1], 'no_title')
        self.assertIsNone(run(layout(title=('OFFER OF ADMISSION',)))['locked'])
        self.assertEqual(run(layout(extra=(TITLE[0],)))['guard'], 'no_title')                 # the title twice
        self.assertEqual(run(layout(ref_row=DATED_ROW, dated_row=REF_ROW))['guard'], 'no_head')
        self.assertEqual(run(layout(ref_row=REF_ROW.strip()))['guard'], 'no_head')
        self.assertEqual(run(layout(ref_row=R + 'Rujukan : UMK.100-1/2/3 (45)'))['guard'], 'no_head')
        self.assertEqual(run(layout(dated_row=R + 'Tarikh : 31 September 2026'))['guard'], 'no_head')
        self.assertEqual(run(layout(dated_row=R + 'Tarikh : 15/07/2026'))['guard'], 'no_head')
        self.assertEqual(run(layout(salutation='Tuan/Puan,'))['guard'], 'no_head')
        self.assertEqual(run(layout(address=ADDRESS[:1]))['guard'], 'no_head')                 # no wrapped line
        self.assertEqual(run(layout(address=ADDRESS + ADDRESS[1:3]))['guard'], 'no_head')     # five
        self.assertEqual(run(layout(greeting=('Selamat datang ke UniSZA.',)))['guard'], 'no_table')
        lay = layout().replace(W + ADDRESS[1], W + ADDRESS[1] + '   ' + 'Rujukan')
        self.assertEqual(run(lay)['guard'], 'no_head')                                    # a second column

    def test_reporting_date_read_only_when_labelled(self):
        """The labelled "Tarikh" row straight after the registration sentence, with the right Malay day name, is the
        only reporting date read; any other shape, or none, refuses: never guessed."""
        for value in ('13 SEPTEMBER 2026 (ISNIN)', '13 SEPTEMBER 2026', '31 SEPTEMBER 2026 (AHAD)',
                      '13 September 2026 (Ahad)', '13/09/2026 (AHAD)', 'AKAN DIMAKLUMKAN', '13 SEP 2026 (AHAD)',
                      REPORT_ON + ' dan ' + printed(14, 9, 2026)):
            with self.subTest(value=value):
                d = run(layout(report=report_rows(value)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('reporting_shape', 'stray_date'))
        rows = report_rows()
        for report in ((rows[1], rows[0], rows[2]), rows[:1] + rows[2:], rows[:2],
                       ('     Tarikh Lapor Diri : ' + REPORT_ON,) + rows[1:],
                       (rows[0], '     Masa   : SEPANJANG HARI', rows[2])):
            with self.subTest(report=len(report)):
                self.assertEqual(run(layout(report=report))['guard'], 'reporting_shape')
        self.assertEqual(run(layout(register='1. Sila hadir mendaftar seperti berikut:'))['guard'], 'reporting_shape')
        self.assertEqual(read_unisza(layout(register='1. Sila hadir:'))[0]['reporting_date'], '')

    def test_the_fee_block_must_follow(self):
        for fees in (FEES[1:], FEES[:2], (FEES[0], FEES[2], FEES[1]),
                     FEES[:2] + ('       RM 25,000.00   RM 1,500.00   RM 23,500.00',)):
            with self.subTest(fees=len(fees)):
                self.assertEqual(run(layout(fees=fees))['guard'], 'table_shape')
        self.assertEqual(run(layout(report=report_rows(place=('A', 'B', 'C', 'D'))))['guard'], 'table_shape')

    def test_a_date_elsewhere_is_never_taken(self):
        for note in ('Pendaftaran pada 12 September 2026 di Dewan Utama.', 'Sila hadir pada 12/09/2026.',
                     'Tarikh Cetak : 17/07/2026', 'Hadir pada 12 SEP 2026.', 'Bayaran sebelum 1 Ogo. 2026'):
            with self.subTest(note=note):
                d = run(layout(extra=(note,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'stray_date')

    def test_dates_and_session(self):
        self.assertEqual(run(layout(dated_row=R + 'Tarikh : 15 Julai 2028'))['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(dated_row=R + 'Tarikh : 15 Oktober 2026'))['guard'], 'dates_not_sane')
        self.assertIsNotNone(run(layout(dated_row=R + 'Tarikh : 15 Disember 2025'))['locked'])   # the year before
        self.assertIsNotNone(run(layout(report=report_rows(printed(13, 2, 2027))))['locked'])  # the second year
        self.assertEqual(run(layout(report=report_rows(printed(13, 9, 2028))))['guard'], 'dates_not_sane')
        late_title = ('TAWARAN KEMASUKAN KE UNIVERSITI SULTAN ZAINAL ABIDIN (UniSZA) SEM 1 SESI 2026/2028',)
        self.assertEqual(run(layout(title=late_title))['guard'], 'dates_not_sane')

    def test_placeholder_refuses(self):
        self.assertEqual(run(layout(extra=('Kampus {kampus}',)))['guard'], 'placeholder')

    def test_a_portal_page_refuses_with_no_excuse(self):
        self.assertFalse(run()['portal'])
        d = run(layout(extra=('Sila semak di Portal Semakan Kemasukan.',)))
        self.assertTrue(d['portal'])
        self.assertIsNone(d['locked'])

    def test_missing_owner_words_go_to_ai(self):
        self.assertEqual(run(layout(notes=NOTES[1:]))['guard'], 'owner_words_missing')
        self.assertEqual(run(layout(footer=FOOTER[:3] + FOOTER[4:]))['guard'], 'owner_words_missing')

    def test_any_later_page_goes_to_ai_with_no_excuse(self):
        """Owner decision 26 Nov: no blank-page, later-page or conditions-page excuse."""
        self.assertEqual(unisza_later_pages(['Syarat-syarat tawaran']), 'later_page')
        self.assertEqual(unisza_later_pages(['', '  ']), '')
        self.assertEqual(run(page2='Sekian, terima kasih.\nPendaftar')['guard'], 'later_page')

    def test_a_page_that_draws_no_text_refuses(self):
        self.assertEqual(run(page2='')['guard'], 'hidden_page')


class UniszaWiringTest(SimpleTestCase):
    def test_ink_targets_hold_the_ic_and_date_as_printed(self):
        phrases, values = unisza_ink_targets(run()['locked'], layout())
        self.assertEqual(len(phrases), 8)
        got = dict(values)
        self.assertEqual((got['v:name'], got['v:nric'], got['v:intake'], got['v:code']), (NAME, IC, INTAKE, CODE))
        self.assertEqual((got['v:date'], got['v:offer_date'], got['v:programme']),
                         ('13 SEPTEMBER 2026', OFFER_ON, PROGRAMME))
        self.assertEqual(set(read_unisza(layout())[0]), set(INK_LABELS) | set(NOT_PRINTED))
        self.assertTrue(set(INK_OPTIONAL) <= set(INK_LABELS))

    def test_family_and_lane_modules(self):
        text = plain(layout())
        self.assertEqual(offer_parse.family_of(text), 'unisza')
        self.assertEqual(offer_exact._rules_family(text), 'unisza')
        self.assertEqual(offer_exact._lane_module('unisza').LANE, 'ua:UniSZA')
        why_ = {}
        offer_exact._note_ums_refusal(why_, text, 'no_layout')
        self.assertEqual(why_, {'lane': 'ua:UniSZA', 'reason': 'read_no_layout'})
        from apps.scholarship.eval.offer_read_check import RULES_LANES
        self.assertEqual(RULES_LANES['universiti sultan zainal abidin'], 'ua:UniSZA')

    def test_family_of_claims_only_unisza_letters(self):
        for other in ('UNIVERSITI SULTAN ZAINAL ABIDIN\nSURAT AKUAN',
                      'UNIVERSITI MALAYSIA KELANTAN\nTAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA KELANTAN',
                      'UNIVERSITI SULTAN ZAINAL ABIDIN\nSURAT TAWARAN\nBAHAGIAN PENGAMBILAN PELAJAR'):
            with self.subTest(other=other.splitlines()[1]):
                self.assertNotEqual(offer_parse.family_of(other), 'unisza')
        self.assertFalse(is_unisza('UNIVERSITI SULTAN ZAINAL ABIDIN PEJABAT PENDAFTAR'))
        self.assertTrue(is_unisza('TAWARAN KEMASUKAN KE UNIVERSITI SULTAN ZAINAL ABIDIN (UNISZA)'))

    def test_not_inked_dispatches_to_unisza(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), 'ua:UniSZA'), [])
            self.assertEqual(ink.call_args.kwargs['lane'], 'ua:UniSZA')

    @override_settings(OCR_FIRST_LANES=[])
    def test_lane_off_by_default(self):
        text = plain(layout())
        why_ = {}
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(text, text)):
            self.assertIsNone(offer_exact.exact_offer_read(text, image=b'%PDF', content_type='application/pdf',
                                                           why=why_))
        self.assertEqual(why_, {'lane': 'ua:UniSZA', 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=['ua:UniSZA'])
    def test_lane_on_reads_the_layout(self):
        lay = layout()
        p1 = plain(lay)
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(p1, p1)), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_page1_layout', return_value=lay), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_rules_page_texts', return_value=[p1]), \
                mock.patch.object(offer_exact, '_not_inked', return_value=[]):
            ex = offer_exact.exact_offer_read(p1, image=b'%PDF', content_type='application/pdf', profile_nric=NRIC)
        self.assertIsNotNone(ex)
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), ('ua:UniSZA', NRIC))
