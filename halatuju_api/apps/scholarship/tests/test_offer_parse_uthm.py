"""OCR-14 phase 3: the UTHM rules lane (`offer_parse_uthm`) and its no-IC lock (`offer_exact.ISSUER_PRINTS_NO_IC`,
owner 26 Nov: "Same as UUM"). The matric number is not an IC and is never stored; the reporting date is read only
from its labelled row under the registration sentence, never guessed. Synthetic letters only (made-up names,
numbers and addresses)."""
import datetime
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_parse_uthm import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, is_uthm, read_uthm
from apps.scholarship.offer_parse_uthm import uthm_ink_targets as ink_targets
from apps.scholarship.offer_parse_uthm import uthm_later_pages as later_pages_refusal
from apps.scholarship.offer_parse_uthm import uthm_letter_refusal as letter_refusal

NAME = 'ZORBEX QUENTARO BIN ALFEN'
MATRIC = 'CE270123'
PROGRAMME = 'SARJANA MUDA KEJURUTERAAN ELEKTRONIK DENGAN KEPUJIAN'
INTAKE_A = 'SESI AKADEMIK 20272028'
INTAKE_B = 'SEMESTER I SESI 20272028'
R = ' ' * 58
V = ' ' * 39                                    # a wrapped programme starts under its value (format A)
HEAD_A = (' ' * 87 + 'Pejabat Pengurusan Akademik', ' ' * 73 + 'Tel : 07-453 7000/7001/7002',
          ' ' * 102 + 'Faks : 07-453 6000', R + 'Rujukan Kami (Our Ref)     :', R + 'Rujukan Tuan (Your Ref)   :')
HEAD_B = (' ' * 120 + 'PEJABAT PENGURUSAN AKADEMIK', ' ' * 100 + 'Tel : 07-453 7000', ' ' * 100 + 'Faks : 07-453 6000',
          ' ' * 100 + 'Rujukan Kami(Our Ref.):', ' ' * 100 + 'Rujukan Tuan(Your Ref.):')
ADDRESS = ('NO.12, JALAN MAWAR 3, TAMAN BUNGA', '86400 PARIT RAJA', 'JOHOR')
TITLE_A = ('TAWARAN  KEMASUKAN  KE  UNIVERSITI  TUN  HUSSEIN  ONN  MALAYSIA  (UTHM)  SESI  AKADEMIK', '20272028')
TITLE_B = ('TAWARAN KEMASUKAN KE UNIVERSITI TUN HUSSEIN ONN MALAYSIA (UTHM)', INTAKE_B)
GREETING = ('Tahniah diucapkan kepada saudara/i kerana ditawarkan tempat bagi mengikuti program di UTHM seperti butiran',
            'berikut :')
ROWS = (('Tempoh Program (Tahun)', '4'), ('Peringkat Pengajian', 'SARJANA MUDA'),
        ('Mod Pengajian', 'KERJA KURSUS SEPENUH MASA'), ('Fakulti', 'FAKULTI KEJURUTERAAN ELEKTRIK DAN ELEKTRONIK'),
        ('Kampus', 'KAMPUS UTHM, PARIT RAJA'), ('No Matrik', MATRIC), ('Kolej Kediaman', 'TUN DR ISMAIL'),
        ('Alamat E-mel', MATRIC + '@student.uthm.edu.my'), ('Yuran Kemasukan', 'RM 1,234.00'),
        ('Syarat Tawaran', 'LAMPIRAN A'))
SENTENCE = '2. Saudara/i diminta datang untuk mendaftar pada tarikh, tempat dan masa seperti butiran berikut:'
FOOTER = ('3.  Tawaran  ini  adalah MUKTAMAD dan  hanya  sah  sehingga  tarikh  pendaftaran  yang  ditetapkan  sahaja',
          'dan tertakluk kepada kesahihan maklumat dalam dokumen permohonan.',
          '4. Seluruh warga Universiti mengalu-alukan kedatangan saudara/i ke Universiti Tun Hussein Onn Malaysia.',
          'Selamat maju jaya.', 'Yang benar,', 'QARIM VELTO BIN DURAN', 'PENGARAH', 'b.p: Naib Canselor',
          'UNIVERSITI TUN HUSSEIN ONN MALAYSIA', 's.k : Fail Pelajar',
          'Surat ini adalah janaan komputer dan tidak memerlukan tandatangan.')
_DAYS = ('ISNIN', 'SELASA', 'RABU', 'KHAMIS', 'JUMAAT', 'SABTU', 'AHAD')
_MONTHS = ('JANUARI', 'FEBRUARI', 'MAC', 'APRIL', 'MEI', 'JUN', 'JULAI', 'OGOS', 'SEPTEMBER', 'OKTOBER',
           'NOVEMBER', 'DISEMBER')


def printed(d, m, y):
    """A reporting date as UTHM prints it, with the right Malay day name."""
    return f'{d} {_MONTHS[m - 1]} {y} ({_DAYS[datetime.date(y, m, d).weekday()]})'


REPORT_ON = printed(12, 9, 2027)


def row(name, value, indent=1):
    return ' ' * indent + name + ' ' * (34 - len(name)) + ':   ' + value


def report(date=REPORT_ON, venue='KOLEJ KEDIAMAN TUN DR ISMAIL  - PEJABAT BLOK A1', sentence=SENTENCE):
    return (sentence, row('Tarikh', date), row('Tempat', venue), row('Masa', '8.00 pagi - 5.00 petang'))


def layout(fmt='A', name_line=None, offer='12 Ogos 2027', title=None, programme=None, rows=ROWS, reporting=None,
           extra=(), head=None, address=ADDRESS, greeting=GREETING):
    a = fmt == 'A'
    ind = 1 if a else 6
    dated = R + 'Tarikh' + ' ' * 33 + ': ' + offer if a else ' ' * 100 + 'Tarikh : ' + offer
    prog = programme or ((PROGRAMME,) if a else (PROGRAMME + ' (BEE)',))
    lines = [*(head if head is not None else HEAD_A if a else HEAD_B), dated,
             name_line if name_line is not None else NAME, *address, 'Saudara/i,',
             *(title if title is not None else TITLE_A if a else TITLE_B), *greeting,
             row('Program & Kod Program', prog[0], ind), *prog[1:], *(row(n, v, ind) for n, v in rows),
             *(reporting if reporting is not None else report()), *extra, *FOOTER]
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


def rows_with(name, value):
    return tuple((n, value if n == name else v) for n, v in ROWS)


class UthmLockTest(SimpleTestCase):
    def test_degree_letter_locks_with_no_ic_and_its_labelled_reporting_date(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane'], lock['_family']), ('uthm', LANE, 'uthm'))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), ('', 'none'))
        self.assertEqual((lock['programme'], lock['programme_code']), (PROGRAMME, ''))
        self.assertEqual(lock['intake'], INTAKE_A)
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('12 Sep 2027', 'Tarikh'))
        self.assertEqual((lock['reporting_venue'], lock['campus']), ('', ''))
        self.assertEqual(lock['offer_date'], '12 Ogos 2027')
        self.assertEqual(lock['institution'], 'UNIVERSITI TUN HUSSEIN ONN MALAYSIA')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_format_b_locks_with_its_code_and_session(self):
        d = run(layout('B', reporting=()))
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((lock['programme'], lock['programme_code'], lock['intake']), (PROGRAMME, 'BEE', INTAKE_B))
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('', ''))

    def test_programme_wraps_once_or_twice_under_its_value(self):
        one = run(layout(programme=('SARJANA   MUDA   KEJURUTERAAN   ELEKTRONIK', V + 'DENGAN KEPUJIAN')))
        self.assertEqual(one['locked']['programme'], PROGRAMME, why(one))
        two = run(layout(programme=('SARJANA MUDA', V + 'KEJURUTERAAN ELEKTRONIK', V + 'DENGAN KEPUJIAN')))
        self.assertEqual(two['locked']['programme'], PROGRAMME, why(two))

    def test_reporting_date_blank_when_no_sentence(self):
        lock = run(layout(reporting=()))['locked']
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('', ''))

    def test_the_matric_is_never_stored(self):
        lock = run()['locked']
        self.assertFalse(any(MATRIC.lower() in str(v).lower() for v in lock.values()))
        fields, _why = read_uthm(layout())
        self.assertFalse(any(MATRIC.lower() in str(v).lower() for v in fields.values()))

    def test_a_scan_refuses_no_layout(self):
        d = offer_parse.diagnose(plain(layout()), '', '', None)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('uthm', 'no_layout', None))


class UthmNeverLocksTest(SimpleTestCase):
    def test_every_ic_shape_refuses_on_page_one_and_page_two(self):
        """Any 12-digit IC-like number refuses: raw spacing, an en dash, a minus sign, a slash, whitespace runs, a
        split over a line break; on page 1's layout, on page 1's plain layer and on a page 2."""
        from apps.scholarship.tests.test_offer_parse_uum import IC_SHAPES
        for ic in IC_SHAPES + ('990101145678', '990101-14-5678', '990101 – 14 – 5678', '990101−14−5678'):
            with self.subTest(ic=ic):
                lay = layout(extra=('No. K/P :' + ' ' * 30 + ic,))
                self.assertEqual(read_uthm(lay), (None, 'ic_printed'))
                self.assertEqual(run(lay)['guard'], 'ic_printed')
                self.assertEqual(letter_refusal(plain(layout()) + '\n' + ic), 'ic_printed')
                page2 = 'Universiti Tun Hussein Onn Malaysia\n' + ' ' * 40 + 'No. K/P' + ' ' * 31 + ':' + ' ' * 7 + ic
                self.assertEqual(run(page2=page2)['guard'], 'ic_printed')
                p1 = plain(layout())
                d = offer_parse.diagnose(p1, p1 + '\n' + ic, layout(), [p1])
                self.assertEqual(d['guard'], 'ic_printed')

    def test_a_matric_or_reference_is_never_the_ic(self):
        self.assertEqual(run(layout(rows=rows_with('No Matrik', '990101145678')))['guard'], 'ic_printed')
        for matric in ('CE27012', 'CE2701234', '27012345', 'C1270123'):
            with self.subTest(matric=matric):
                self.assertEqual(run(layout(rows=rows_with('No Matrik', matric)))['guard'], 'no_matrik')
        for ref in ('UTHM.PPA/100-1/2 (12)', 'CE270123', '990101145678'):
            with self.subTest(ref=ref):
                head = HEAD_A[:3] + (R + 'Rujukan Kami (Our Ref)     : ' + ref, HEAD_A[4])
                self.assertIn(run(layout(head=head))['guard'], ('reference_printed', 'ic_printed'))
        head = HEAD_A[:4] + (R + 'Rujukan Tuan (Your Ref)   : 990101-14-5678',)
        self.assertEqual(run(layout(head=head))['guard'], 'ic_printed')

    def test_diploma_asasi_and_non_degree_refuse(self):
        for prog in ('DIPLOMA KEJURUTERAAN ELEKTRIK (DET)', 'ASASI KEJURUTERAAN', 'SARJANA KEJURUTERAAN ELEKTRONIK',
                     'SARJANA MUDA KEJURUTERAAN ELEKTRONIK', 'SARJANA MUDA DIPLOMA LANJUTAN DENGAN KEPUJIAN'):
            with self.subTest(prog=prog):
                d = run(layout(programme=(prog,)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('programme_shape', 'not_degree', 'asasi_ai_read'))
        for name, value in (('Peringkat Pengajian', 'DIPLOMA'), ('Peringkat Pengajian', 'ASASI'),
                            ('Fakulti', 'PUSAT PENGAJIAN DIPLOMA'), ('Fakulti', 'FAKULTI ASASI SAINS'),
                            ('Fakulti', 'PUSAT PENGAJIAN ASASI')):
            with self.subTest(name=name, value=value):
                self.assertEqual(run(layout(rows=rows_with(name, value)))['guard'], 'not_degree')
        for line in ('Program Diploma Kejuruteraan', 'Pelajar Asasi Sains'):
            with self.subTest(line=line):
                self.assertIn(run(layout(extra=(line,)))['guard'], ('not_degree', 'asasi_ai_read'))

    def test_confirmation_and_fail_letters_refuse(self):
        self.assertEqual(run(layout(extra=('SURAT PENGESAHAN',)))['guard'], 'status_letter')
        self.assertEqual(run(layout(extra=('PENGESAHAN PENDAFTARAN',)))['guard'], 'status_letter')
        for line in ('Permohonan saudara/i TIDAK BERJAYA.', 'Tawaran ini telah DIBATALKAN.',
                     'Tawaran ini telah ditarik balik.'):
            with self.subTest(line=line):
                d = run(layout(extra=(line,)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('status_letter', 'not_an_offer'))
        self.assertEqual(letter_refusal(plain(layout())), '')

    def test_unknown_layouts_refuse(self):
        self.assertEqual(read_uthm(layout(title=('TAWARAN KEMASUKAN KE UNIVERSITI TUN HUSSEIN ONN MALAYSIA (UTHM)',
                                                 'SESI 2027/2028'))), (None, 'no_title'))
        self.assertEqual(run(layout(title=('OFFER OF ADMISSION', '20272028')))['family'], 'uthm')
        self.assertEqual(run(layout(title=('OFFER OF ADMISSION', '20272028')))['guard'], 'no_title')
        self.assertEqual(run(layout(extra=TITLE_A))['guard'], 'no_title')                     # the title twice
        self.assertEqual(run(layout(head=(' ' * 87 + 'Pejabat Pendaftar',) + HEAD_A[1:]))['family'], '')
        self.assertEqual(run(layout(head=(' ' * 87 + 'PEJABAT PENGURUSAN AKADEMIK  PEJABAT PENDAFTAR',) + HEAD_A[1:]))
                         ['guard'], 'not_letterhead')
        self.assertEqual(run(layout(head=HEAD_A + (R + 'E-mel : ppa@uthm.edu.my',)))['guard'], 'no_head')
        self.assertEqual(run(layout(head=HEAD_A[:4]))['guard'], 'no_head')                    # no Rujukan Tuan
        swapped = (ROWS[1], ROWS[0]) + ROWS[2:]
        self.assertEqual(run(layout(rows=swapped))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=ROWS[:-1]))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=rows_with('Syarat Tawaran', 'LAMPIRAN B')))['guard'], 'conditions_shape')
        self.assertEqual(run(layout(greeting=('Selamat datang ke UTHM.',)))['guard'], 'no_table')

    def test_programme_shapes(self):
        three = ('SARJANA MUDA', V + 'KEJURUTERAAN', V + 'ELEKTRONIK', V + 'DENGAN KEPUJIAN')
        self.assertEqual(run(layout(programme=three))['guard'], 'programme_shape')            # three wraps
        self.assertEqual(run(layout(programme=('SARJANA MUDA KEJURUTERAAN ELEKTRONIK', ' ' * 10 + 'DENGAN KEPUJIAN')))
                         ['guard'], 'table_shape')                                            # not under its value
        self.assertEqual(run(layout(programme=('SARJANA MUDA KEJURUTERAAN' + ' ' * 14 + 'ELEKTRONIK DENGAN KEPUJIAN',)))
                         ['guard'], 'programme_shape')                                        # another column
        self.assertEqual(run(layout(programme=(PROGRAMME + ' (BEEEE)',)))['guard'], 'programme_shape')

    def test_name_must_be_read_exactly(self):
        for name_line in ('Z9RBEX QUENTARO', NAME + '   EXTRA', ' ' * 14 + NAME, 'Zorbex Quentaro Bin Alfen'):
            with self.subTest(name_line=name_line):
                d = run(layout(name_line=name_line))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_shape', 'no_head'))

    def test_a_wrapped_name_never_locks_cut_short(self):
        """The line after the name must prove it ended (a digit, a comma or an address word opens it). NO'MAN and
        NO-MAN are a name's rest, not the address word NO."""
        for first, rest in (('ZORBEX QUENTARO', 'BIN ALFEN'), ('ZORBEX QUENTARO BIN', 'ALFEN'), ('ZORBEX', 'QUENTARO'),
                            ('ZORBEX QUENTARO', "NO'MAN"), ('ZORBEX QUENTARO', 'NO-MAN'),
                            ('ZORBEX QUENTARO A/L', 'ALFEN'), ('ZORBEX QUENTARO BINTI', "NO'MAN")):
            with self.subTest(first=first, rest=rest):
                d = run(layout(name_line=first + '\n' + rest))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_not_ended', 'name_shape'))
        for addr in ('KAMPUNG MAWAR', 'B-1-12 TAMAN MAWAR', 'NO 9 ,', 'NO.12, JALAN 1/2', 'LOT 99 LORONG 1'):
            with self.subTest(addr=addr):
                lock = run(layout(address=(addr, '86400 PARIT RAJA')))['locked']
                self.assertEqual(lock['candidate_name'], NAME)

    def test_head_must_hold(self):
        self.assertEqual(run(layout().replace('Saudara/i,\n', ''))['guard'], 'no_head')
        self.assertEqual(run(layout(address=()))['guard'], 'no_head')
        self.assertEqual(run(layout(offer='12/08/2027'))['guard'], 'no_head')

    def test_reporting_date_read_only_when_labelled(self):
        self.assertEqual(run(layout(reporting=report(date='12 SEPTEMBER 2027 (ISNIN)')))['guard'], 'reporting_shape')
        self.assertEqual(run(layout(reporting=report(date='31 SEPTEMBER 2027 (AHAD)')))['guard'], 'reporting_shape')
        self.assertEqual(run(layout(reporting=report(date='12 SEPTEMBER 2027')))['guard'], 'reporting_shape')
        self.assertEqual(run(layout(reporting=report()[:1] + report()[2:]))['guard'], 'reporting_shape')   # no Tarikh
        self.assertEqual(run(layout(reporting=report(sentence='2. Saudara/i diminta hadir pada tarikh berikut:')))
                         ['guard'], 'reporting_shape')
        self.assertEqual(run(layout(reporting=(), extra=SENTENCE.split(' untuk ')[:1]))['guard'], 'reporting_shape')

    def test_a_date_in_a_venue_or_note_is_never_taken(self):
        venue = 'KOLEJ KEDIAMAN TUN DR ISMAIL mulai 11 September 2027'
        self.assertEqual(run(layout(reporting=report(venue=venue)))['guard'], 'stray_date')
        for note in ('Pendaftaran pada 12 September 2027 di Dewan Besar.', 'Sila hadir pada 12/09/2027.'):
            with self.subTest(note=note):
                d = run(layout(reporting=(), extra=(note,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'stray_date')

    def test_dates_and_session(self):
        self.assertEqual(run(layout(offer='12 Ogos 2030'))['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(title=(TITLE_A[0], '20272029')))['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(reporting=report(date=printed(1, 8, 2027))))['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(reporting=report(date=printed(12, 9, 2029))))['guard'], 'dates_not_sane')
        self.assertEqual(why(run(layout(offer='31 September 2027'))), 'empty:offer_date')

    def test_placeholder_refuses(self):
        self.assertEqual(run(layout(extra=('Tarikh tutup {tarikh_tutup}',)))['guard'], 'placeholder')

    def test_any_portal_tell_refuses_no_excuse(self):
        self.assertFalse(run()['portal'])
        for line in ('Tahniah! Anda layak menerima tawaran', 'Sila cetak slip ini', 'SEMAKAN TAWARAN'):
            with self.subTest(line=line):
                d = run(layout(extra=(line,)))
                self.assertTrue(d['portal'])
                self.assertIsNone(d['locked'])

    def test_missing_owner_words_go_to_ai(self):
        self.assertEqual(run(layout().replace('MUKTAMAD', 'TERAKHIR'))['guard'], 'owner_words_missing')
        self.assertIsNone(run(layout().replace('Tempoh Program (Tahun)', 'Lama Program (Tahun)'))['locked'])

    def test_any_later_page_goes_to_ai(self):
        self.assertEqual(later_pages_refusal(['Universiti Tun Hussein Onn Malaysia\nLampiran A']), 'later_page')
        self.assertEqual(later_pages_refusal(['', '  ']), '')
        self.assertEqual(run(page2='Universiti Tun Hussein Onn Malaysia\nLampiran A')['guard'], 'later_page')


class UthmNoIcAndWiringTest(SimpleTestCase):
    def test_lock_stores_a_blank_ic_over_a_prior_ai_ic(self):
        lay = layout()
        p1 = plain(lay)
        prior = {'fields': {'candidate_nric': '990101-14-5678', 'candidate_nric_source': 'label'}}
        ex = offer_exact.exact_read(p1, from_text_layer=True, page1_layer=p1, prior=prior,
                                    profile_nric='990101-14-5678', page1_layout=lay, page_texts=[p1])
        self.assertIsNotNone(ex)
        self.assertEqual(ex['rules_lane'], LANE)
        self.assertEqual((ex['fields']['candidate_nric'], ex['fields']['candidate_nric_source']), ('', 'none'))
        self.assertTrue(ex['offer_reader_inputs']['nric_not_printed'])
        self.assertFalse(any(MATRIC in str(v) for v in ex['fields'].values()))

    def test_ink_targets_hold_no_ic_no_matric_and_the_date_as_printed(self):
        phrases, values = ink_targets(run()['locked'], layout())
        self.assertEqual(len(phrases), 8)
        got = dict(values)
        self.assertNotIn('v:nric', got)
        self.assertFalse(any(MATRIC in v for v in got.values()))
        self.assertEqual((got['v:name'], got['v:intake'], got['v:date']), (NAME, INTAKE_A, REPORT_ON))
        self.assertEqual(got['v:offer_date'], '12 Ogos 2027')
        self.assertNotIn('v:code', got)
        got_b = dict(ink_targets(run(layout('B', reporting=()))['locked'], layout('B', reporting=()))[1])
        self.assertEqual(got_b['v:code'], 'BEE')
        self.assertNotIn('v:date', got_b)
        self.assertEqual(set(read_uthm(layout())[0]), set(INK_LABELS) | set(NOT_PRINTED))
        self.assertTrue(set(INK_OPTIONAL) <= set(INK_LABELS))

    def test_family_and_lane_modules(self):
        text = plain(layout())
        self.assertEqual(offer_parse.family_of(text), 'uthm')
        self.assertEqual(offer_exact._rules_family(text), 'uthm')
        self.assertEqual(offer_exact._lane_module('uthm').LANE, 'ua:UTHM')
        why_ = {}
        offer_exact._note_ums_refusal(why_, text, 'no_layout')
        self.assertEqual(why_, {'lane': 'ua:UTHM', 'reason': 'read_no_layout'})
        self.assertFalse(is_uthm('UNIVERSITI TUN HUSSEIN ONN MALAYSIA PARIT RAJA'))
        self.assertFalse(is_uthm('UNIVERSITI MALAYSIA PAHANG PEJABAT PENGURUSAN AKADEMIK'))

    def test_not_inked_dispatches_to_uthm(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), 'ua:UTHM'), [])
            self.assertEqual(ink.call_args.kwargs['lane'], 'ua:UTHM')

    @override_settings(OCR_FIRST_LANES=[])
    def test_lane_off_by_default(self):
        text = plain(layout())
        why_ = {}
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(text, text)):
            self.assertIsNone(offer_exact.exact_offer_read(text, image=b'%PDF', content_type='application/pdf',
                                                           why=why_))
        self.assertEqual(why_, {'lane': 'ua:UTHM', 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=['ua:UTHM'])
    def test_lane_on_reads_the_layout(self):
        lay = layout()
        p1 = plain(lay)
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(p1, p1)), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_page1_layout', return_value=lay), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_rules_page_texts', return_value=[p1]), \
                mock.patch.object(offer_exact, '_not_inked', return_value=[]):
            ex = offer_exact.exact_offer_read(p1, image=b'%PDF', content_type='application/pdf',
                                              profile_nric='990101-14-5678')
        self.assertIsNotNone(ex)
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), ('ua:UTHM', ''))
