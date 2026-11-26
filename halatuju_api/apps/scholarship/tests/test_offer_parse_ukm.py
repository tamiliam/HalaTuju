"""OCR-14 phase 4: the UKM rules lane (`offer_parse_ukm`). UKM PRINTS the IC, so it is read from its one labelled
row and checked as on UM and UiTM (`offer_exact.exact_read`'s IC guard; UKM is NOT in
`offer_exact.ISSUER_PRINTS_NO_IC`). Any other IC-like number refuses; the registration number is never stored; the
reporting date is read only from its labelled row, never guessed. Synthetic letters only (made-up names, numbers
and addresses)."""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_parse_ukm import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, is_ukm, read_ukm
from apps.scholarship.offer_parse_ukm import ukm_ic_elsewhere, ukm_ink_targets, ukm_later_pages
from apps.scholarship.offer_parse_ukm import ukm_letter_refusal, ukm_portal

NAME = 'ZORBEX QUENTARO BIN ALFEN'
IC = '990101145678'
NRIC = '990101-14-5678'
REG = 'A212345'
PROGRAMME = 'SARJANA MUDA SAINS DENGAN KEPUJIAN (KIMIA)'
INTAKE = 'SESI AKADEMIK 2027/2028'
OFFER_ON = '15/07/2027'
REPORT_ON = '12/09/2027'
HEAD = (' ' * 116 + 'Rujukan : UKM.AKA.800-1/2/3', ' ' * 129 + 'Tarikh : ' + OFFER_ON)
ADDRESS = ('NO 12, JALAN MAWAR 3', 'TAMAN BUNGA', '43600 BANGI', 'SELANGOR')
TITLE = 'TAWARAN KEMASUKAN ' + INTAKE
GREETING = ('Dengan sukacitanya saya bagi pihak Universiti Kebangsaan Malaysia mengucapkan tahniah kepada saudara/i dan '
            'seterusnya',
            'menawarkan tempat pengajian ijazah pertama bagi Sesi Akademik 2027/2028. Butir-butir tawaran adalah seperti '
            'berikut:')
ROWS = (('NO. KAD PENGENALAN', IC), ('NO. PENDAFTARAN', REG), ('FAKULTI', 'FAKULTI SAINS DAN TEKNOLOGI'),
        ('PUSAT PENGAJIAN', 'PUSAT PENGAJIAN SAINS KIMIA'), ('PROGRAM PENGAJIAN', PROGRAMME),
        ('TEMPOH PENGAJIAN', '4 TAHUN'), ('TAHUN PENGAJIAN', 'SATU'),
        ('TEMPAT LAPOR DIRI', 'KOLEJ ZABA (KZ), UKM, BANGI'),
        ('TARIKH LAPOR DIRI', REPORT_ON + ' ( 8:00 Pagi - 12:00 Tengah Hari )'),
        ('YURAN PENDAFTARAN', 'RM 1,234.50'), ('JENIS AMBILAN', 'AKADEMIK'))
PORTAL = ('Untuk maklumat lanjut, sila rujuk Panduan Pendaftaran Pelajar Baharu yang boleh dicetak di Portal Semakan '
          'Kemasukan ke', 'UKM dipautan http://appsmu.ukm.my/edaftar/.')
TEL = 'Tel: +603-89115555/8301/8402/8403/8404 E-mel: akad@ukm.edu.my Web: www.ukm.my/akademik'
BODY = ('Maklumat Yuran Pengajian adalah seperti berikut:', 'Yuran Pengajian Semester' + ' ' * 20 + 'RM 1,000.00',
        'Tawaran yang diberikan adalah MUKTAMAD dan tidak boleh dirayu.',
        'Sekiranya saudara/i tidak mendaftar sehingga tarikh tersebut, maka tawaran ini akan terbatal.', *PORTAL,
        'Sekian, terima kasih.', 'Yang benar,', 'QARIM VELTO BIN DURAN',
        'Pusat Pengurusan Akademik (Akademik UKM)' + ' ' * 40 + 'Tarikh Cetak : 16/07/2027')
FOOTER = ('UNIT PENGAMBILAN PRASISWAZAH DAN PASCASISWAZAH', 'PUSAT PENGURUSAN AKADEMIK (AKADEMIK UKM)',
          '43600 UKM Bangi, Selangor Darul Ehsan, Malaysia', TEL)


def row(name, value):
    return ' ' * 7 + name + ' ' * (28 - len(name)) + ':' + value


def rows_with(name, value):
    return tuple((n, value if n == name else v) for n, v in ROWS)


def layout(name_line=NAME, head=HEAD, address=ADDRESS, title=TITLE, greeting=GREETING, rows=ROWS, body=BODY,
           extra=(), footer=FOOTER):
    lines = [*head, name_line, *address, 'Saudara/i,', title, *greeting, *(row(n, v) for n, v in rows), *body,
             *extra, *footer]
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


class UkmLockTest(SimpleTestCase):
    def test_degree_letter_locks_with_its_ic_and_labelled_reporting_date(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane'], lock['_family']), ('ukm', LANE, 'ukm'))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), (NRIC, 'label'))
        self.assertEqual((lock['programme'], lock['programme_code']), (PROGRAMME, ''))
        self.assertEqual(lock['intake'], INTAKE)
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('12 Sep 2027', 'TARIKH LAPOR DIRI'))
        self.assertEqual((lock['reporting_venue'], lock['campus'], lock['stream']), ('', '', ''))
        self.assertEqual(lock['offer_date'], OFFER_ON)
        self.assertEqual(lock['institution'], 'UNIVERSITI KEBANGSAAN MALAYSIA')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_optional_school_row_and_value_shapes(self):
        no_school = tuple(r for r in ROWS if r[0] != 'PUSAT PENGAJIAN')
        self.assertIsNotNone(run(layout(rows=no_school))['locked'])
        for name, value in (('NO. KAD PENGENALAN', ' ' + IC),
                            ('TEMPOH PENGAJIAN', '3.5 TAHUN'), ('YURAN PENDAFTARAN', 'RM1,234.50'),
                            ('TARIKH LAPOR DIRI', REPORT_ON), ('PROGRAM PENGAJIAN', 'SARJANA MUDA SAINS DENGAN KEPUJIAN'),
                            ('TARIKH LAPOR DIRI', REPORT_ON + ' ( 12:00 Tengah Hari - 5:00 Petang )')):
            with self.subTest(name=name, value=value):
                d = run(layout(rows=rows_with(name, value)))
                self.assertIsNotNone(d['locked'], why(d))
                self.assertEqual(d['locked']['candidate_nric'], NRIC)

    def test_the_registration_number_is_never_stored(self):
        lock = run()['locked']
        self.assertFalse(any(REG in str(v) for v in lock.values()))
        self.assertFalse(any('UKM.AKA' in str(v) for v in lock.values()))

    def test_a_scan_refuses_no_layout(self):
        d = offer_parse.diagnose(plain(layout()), '', '', None)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('ukm', 'no_layout', None))


class UkmIcTest(SimpleTestCase):
    def test_ic_shapes_in_its_row_refuse(self):
        """The IC row's raw value must be 12 plain digits: a hyphen, an en dash, a minus, a slash, a space, a
        whitespace run or a line split refuses."""
        for ic in (NRIC, '990101 14 5678', '9901 0114 5678', '990101–14–5678', '990101−14−5678', '990101/14/5678', '990101   14   5678', '990101\t14\t5678',
                   '99010114567', '9901011456789', '990101-14-5678 990101-14-5678', 'TIDAK BERKAITAN'):
            with self.subTest(ic=ic):
                d = run(layout(rows=rows_with('NO. KAD PENGENALAN', ic)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('ic_shape', 'table_shape'))
        split = layout(rows=rows_with('NO. KAD PENGENALAN', '990101-14-')).replace(
            row('NO. PENDAFTARAN', REG), '5678\n' + row('NO. PENDAFTARAN', REG))
        self.assertIsNone(run(split)['locked'])
        self.assertIn(run(split)['guard'], ('ic_shape', 'table_shape'))

    def test_a_second_ic_anywhere_refuses(self):
        from apps.scholarship.tests.test_offer_parse_uum import IC_SHAPES
        for ic in IC_SHAPES + ('990102145678', '990102-14-5678', NRIC):
            with self.subTest(ic=ic):
                lay = layout(extra=('No. K/P waris :' + ' ' * 10 + ic,))
                self.assertIsNone(run(lay)['locked'])
                self.assertEqual(read_ukm(lay)[1], 'second_ic')
                self.assertEqual(ukm_letter_refusal(plain(layout()) + '\nWaris ' + ic, NRIC), 'second_ic')
                self.assertIn(run(page2='Universiti Kebangsaan Malaysia\nNo. K/P : ' + ic)['guard'],
                              ('second_ic', 'ic_printed'))
                p1 = plain(layout())
                d = offer_parse.diagnose(p1, p1 + '\nWaris ' + ic, layout(), [p1])
                self.assertIsNone(d['locked'])
        self.assertEqual(ukm_letter_refusal(plain(layout()), NRIC), '')

    def test_the_read_ic_must_stand_in_the_plain_layer(self):
        p1 = plain(layout())
        for page1 in (p1.replace(IC, ''), p1.replace(IC, IC + ' ' + IC)):
            with self.subTest(copies='none' if IC not in page1 else 'two'):
                d = offer_parse.diagnose(p1, page1, layout(), [page1])
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('ic_not_plain', 'identity_disagree', 'second_ic', 'ic_printed'))

    def test_a_registration_or_reference_is_never_the_ic(self):
        for reg in ('990101145678', '990101-14-5678', 'A2123', 'AB212345', '212345'):
            with self.subTest(reg=reg):
                d = run(layout(rows=rows_with('NO. PENDAFTARAN', reg)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('registration_shape', 'second_ic'))
        for ref in ('Rujukan : 990101145678', 'Rujukan : UKM.AKA.990101145678'):
            with self.subTest(ref=ref):
                self.assertIsNone(run(layout(head=(' ' * 116 + ref, HEAD[1])))['locked'])

    def test_the_ic_guard_runs_as_on_um(self):
        """The usual IC guard (`offer_ic`): the IC AS PRINTED is stored, never the profile's (a profile IC that
        differs is the verdict's mismatch to show, not the reader's to fix); an implausible IC is blanked, and a
        blank IC on this lane refuses."""
        self.assertNotIn(LANE, offer_exact.ISSUER_PRINTS_NO_IC)
        p1 = plain(layout())
        for profile in ('880505-10-1234', '990102-14-5678', ''):
            with self.subTest(profile=profile):
                ex = offer_exact.exact_read(p1, from_text_layer=True, page1_layer=p1, page1_layout=layout(),
                                            page_texts=[p1], profile_nric=profile)
                self.assertEqual((ex['fields']['candidate_nric'], ex['fields']['candidate_nric_source']),
                                 (NRIC, 'label'))
        lay = layout(rows=rows_with('NO. KAD PENGENALAN', '200102145678'))            # six years old
        why_ = {}
        self.assertIsNone(offer_exact.exact_read(plain(lay), from_text_layer=True, page1_layer=plain(lay),
                                                 page1_layout=lay, page_texts=[plain(lay)], why=why_))
        self.assertEqual(why_, {'lane': LANE, 'reason': 'read_nric_guard'})
        p1 = plain(layout())
        lock = {'family': 'ukm', 'guard': None, 'empty_required': [], 'portal': False,
                'locked': {'candidate_name': NAME, 'candidate_nric': '', 'candidate_nric_source': 'none',
                           'programme': PROGRAMME, 'institution': 'UNIVERSITI KEBANGSAAN MALAYSIA', 'rules_lane': LANE,
                           '_family': 'ukm'}}
        with mock.patch('apps.scholarship.offer_parse.diagnose', return_value=lock):
            why_ = {}
            self.assertIsNone(offer_exact.exact_read(p1, profile_nric=NRIC, why=why_))
        self.assertEqual(why_, {'lane': LANE, 'reason': 'read_nric_guard'})

    def test_the_matching_ic_locks_through_the_exact_read(self):
        p1 = plain(layout())
        ex = offer_exact.exact_read(p1, from_text_layer=True, page1_layer=p1, page1_layout=layout(), page_texts=[p1],
                                    profile_nric=NRIC)
        self.assertIsNotNone(ex)
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), (LANE, NRIC))
        self.assertFalse(ex['offer_reader_inputs'].get('nric_not_printed'))

    def test_the_footer_phone_excuse_is_narrow(self):
        """The footer's "Tel: +603-8911NNNN/8NNN" reads as an IC to the wide check; only the measured switchboard
        run (review r1), once, is taken out: any other phone-shaped run is not excused."""
        self.assertFalse(ukm_ic_elsewhere(TEL, NRIC))
        self.assertTrue(ukm_ic_elsewhere(TEL + '\n' + TEL, NRIC))
        for other in ('Tel: 89115555/8301', 'Faks: +603-89115555/8301', 'Tel: +603-89115555/8301/14-5678',
                      'Tel: +603-899010/14/5678', 'Tel: +603-88021234/5678', 'Tel: +603-89215555/8301',
                      'Tel: +603-89115555/5678', 'Tel: +604-89115555/8301'):
            with self.subTest(other=other):
                self.assertTrue(ukm_ic_elsewhere(other, NRIC))
                self.assertIsNone(run(layout(footer=FOOTER[:3] + (other,)))['locked'])
        self.assertIsNone(run(layout(footer=FOOTER + (TEL,)))['locked'])


class UkmNeverLocksTest(SimpleTestCase):
    def test_a_wrapped_name_never_locks_cut_short(self):
        """The line after the name must prove it ended (a digit, a comma or an address word opens it). NO'MAN and
        NO-MAN are a name's rest, not the address word NO; a lone place word may be a name's rest too."""
        for first, rest in (('ZORBEX QUENTARO', 'BIN ALFEN'), ('ZORBEX QUENTARO BIN', 'ALFEN'), ('ZORBEX', 'QUENTARO'),
                            ('ZORBEX QUENTARO', "NO'MAN"), ('ZORBEX QUENTARO', 'NO-MAN'), ('ZORBEX QUENTARO', 'BANGI'),
                            ('ZORBEX QUENTARO A/L', 'ALFEN'), ('ZORBEX QUENTARO BINTI', "NO'MAN")):
            with self.subTest(first=first, rest=rest):
                d = run(layout(name_line=first + '\n' + rest))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_not_ended', 'name_shape'))
        for addr in ('KAMPUNG MAWAR', 'B-1-12 TAMAN MAWAR', 'NO 9 ,', 'LOT 99 LORONG 1'):
            with self.subTest(addr=addr):
                d = run(layout(address=(addr, '43600 BANGI')))
                self.assertEqual(d['locked']['candidate_name'], NAME, why(d))

    def test_name_must_be_read_exactly(self):
        for name_line in ('Z9RBEX QUENTARO', NAME + '   EXTRA', ' ' * 14 + NAME, 'Zorbex Quentaro Bin Alfen'):
            with self.subTest(name_line=name_line):
                d = run(layout(name_line=name_line))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_shape', 'no_head'))

    def test_diploma_asasi_and_non_degree_refuse(self):
        for prog in ('DIPLOMA SAINS KIMIA', 'ASASI SAINS', 'SARJANA SAINS DENGAN KEPUJIAN', 'SARJANA MUDA SAINS',
                     'SARJANA MUDA DIPLOMA LANJUTAN DENGAN KEPUJIAN', 'SARJANA MUDA SAINS DENGAN KEPUJIAN (KIMIA) X'):
            with self.subTest(prog=prog):
                d = run(layout(rows=rows_with('PROGRAM PENGAJIAN', prog)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('programme_shape', 'not_degree', 'asasi_ai_read'))
        for name, value in (('FAKULTI', 'PUSAT PENGAJIAN ASASI'), ('FAKULTI', 'FAKULTI DIPLOMA SAINS'),
                            ('PUSAT PENGAJIAN', 'PUSAT PENGAJIAN DIPLOMA'), ('TAHUN PENGAJIAN', 'DUA'),
                            ('JENIS AMBILAN', 'DIPLOMA')):
            with self.subTest(name=name, value=value):
                d = run(layout(rows=rows_with(name, value)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('not_degree', 'programme_shape', 'table_shape'))
        for line in ('Program Diploma Sains', 'Pelajar Asasi Sains'):
            with self.subTest(line=line):
                self.assertIn(run(layout(extra=(line,)))['guard'], ('not_degree', 'asasi_ai_read'))

    def test_confirmation_and_fail_letters_refuse(self):
        confirm = '\n'.join(('KEPADA SESIAPA YANG BERKENAAN', 'NAMA : ' + NAME, 'NO. KP : ' + IC,
                             'Dengan ini disahkan bahawa penama di atas adalah pelajar tahun pertama',
                             'UNIVERSITI KEBANGSAAN MALAYSIA', 'PUSAT PENGURUSAN AKADEMIK', TEL))
        self.assertEqual(read_ukm(confirm), (None, 'no_title'))
        self.assertIsNone(run(confirm)['locked'])
        self.assertEqual(run(layout(extra=('SURAT PENGESAHAN',)))['guard'], 'status_letter')
        for line in ('Permohonan saudara/i TIDAK BERJAYA.', 'Tawaran ini telah DIBATALKAN.',
                     'Tawaran ini telah ditarik balik.'):
            with self.subTest(line=line):
                d = run(layout(extra=(line,)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('status_letter', 'not_an_offer'))

    def test_unknown_layouts_refuse(self):
        self.assertEqual(read_ukm(layout(title='TAWARAN KEMASUKAN SESI AKADEMIK /')), (None, 'no_title'))
        self.assertEqual(read_ukm(layout(title='TAWARAN KEMASUKAN SESI 2027/2028')), (None, 'no_title'))
        self.assertEqual(run(layout(title='OFFER OF ADMISSION'))['guard'], 'no_title')
        self.assertEqual(run(layout(extra=(TITLE,)))['guard'], 'no_title')                       # the title twice
        self.assertEqual(run(layout(head=(HEAD[1], HEAD[0])))['guard'], 'no_head')
        self.assertEqual(run(layout(head=HEAD[:1]))['guard'], 'no_head')
        self.assertEqual(run(layout(address=()))['guard'], 'no_head')
        self.assertEqual(run(layout().replace('Saudara/i,\n', ''))['guard'], 'no_head')
        swapped = (ROWS[1], ROWS[0]) + ROWS[2:]
        self.assertEqual(run(layout(rows=swapped))['guard'], 'no_table')
        self.assertEqual(run(layout(rows=ROWS[:-1]))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=ROWS[:4] + ROWS[5:]))['guard'], 'table_shape')          # no programme
        self.assertEqual(run(layout(rows=ROWS + (('CATATAN', 'TIADA'),)))['guard'], 'table_shape')
        no_greeting = layout(greeting=('Selamat datang ke UKM.',))
        self.assertIsNone(run(no_greeting)['locked'])
        self.assertEqual(read_ukm(no_greeting)[1], 'no_table')           # and no UKM name: no family at all
        wrong_year = (GREETING[0], GREETING[1].replace('2027/2028', '2028/2029'))
        self.assertEqual(run(layout(greeting=wrong_year))['guard'], 'no_table')
        self.assertFalse(is_ukm('UNIVERSITI KEBANGSAAN MALAYSIA BANGI'))
        self.assertFalse(is_ukm('UNIVERSITI MALAYSIA KELANTAN PUSAT PENGURUSAN AKADEMIK'))

    def test_reporting_date_read_only_when_labelled(self):
        for value in ('', '12 SEPTEMBER 2027', '12/09/2027 ISNIN', '31/09/2027', 'AKAN DIMAKLUMKAN',
                      '12/09/2027 ( 8:00 Pagi )', '12/09/2027 dan 13/09/2027'):
            with self.subTest(value=value):
                d = run(layout(rows=rows_with('TARIKH LAPOR DIRI', value)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('reporting_shape', 'table_shape', 'stray_date'))
        no_row = tuple(r for r in ROWS if r[0] != 'TARIKH LAPOR DIRI')
        self.assertEqual(run(layout(rows=no_row))['guard'], 'table_shape')                       # absent: never guessed

    def test_a_date_in_a_venue_or_note_is_never_taken(self):
        venue = 'KOLEJ ZABA (KZ), UKM, BANGI mulai 11/09/2027'
        self.assertEqual(run(layout(rows=rows_with('TEMPAT LAPOR DIRI', venue)))['guard'], 'stray_date')
        for note in ('Pendaftaran pada 12 September 2027 di Dewan Besar.', 'Sila hadir pada 12/09/2027.',
                     'Tarikh Cetak : 17/07/2027'):
            with self.subTest(note=note):
                d = run(layout(extra=(note,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'stray_date')

    def test_dates_and_session(self):
        self.assertEqual(run(layout(head=(HEAD[0], ' ' * 129 + 'Tarikh : 15/07/2030')))['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(head=(HEAD[0], ' ' * 129 + 'Tarikh : 31/09/2027')))['guard'], 'no_head')
        late = rows_with('TARIKH LAPOR DIRI', '12/09/2029')
        self.assertEqual(run(layout(rows=late))['guard'], 'dates_not_sane')
        early = rows_with('TARIKH LAPOR DIRI', '01/07/2027')
        self.assertEqual(run(layout(rows=early))['guard'], 'dates_not_sane')
        odd = (GREETING[0], GREETING[1].replace('2027/2028', '2027/2029'))
        self.assertEqual(run(layout(title='TAWARAN KEMASUKAN SESI AKADEMIK 2027/2029', greeting=odd))['guard'],
                         'dates_not_sane')

    def test_placeholder_refuses(self):
        self.assertEqual(run(layout(extra=('Tarikh tutup {tarikh_tutup}',)))['guard'], 'placeholder')

    def test_the_portal_excuse_is_one_exact_sentence(self):
        """`offer_parse._PORTAL_TELL` reads "Portal Semakan" as a portal page; only the one sentence every UKM letter
        prints is taken out, once. Any other tell, or the sentence twice, is a portal page."""
        self.assertFalse(run()['portal'])
        self.assertFalse(ukm_portal(plain(layout())))
        for line in ('Tahniah! Anda layak menerima tawaran', 'Sila cetak slip ini', 'SEMAKAN TAWARAN', *PORTAL,
                     'Sila semak di Portal Semakan Kemasukan.'):
            with self.subTest(line=line):
                d = run(layout(extra=(line,)) if line not in PORTAL else layout(extra=PORTAL))
                self.assertTrue(d['portal'])
                self.assertIsNone(d['locked'])

    def test_missing_owner_words_go_to_ai(self):
        self.assertEqual(run(layout().replace('MUKTAMAD', 'TERAKHIR'))['guard'], 'owner_words_missing')

    def test_any_later_page_goes_to_ai(self):
        self.assertEqual(ukm_later_pages(['Universiti Kebangsaan Malaysia\nLampiran A']), 'later_page')
        self.assertEqual(ukm_later_pages(['', '  ']), '')
        self.assertEqual(run(page2='Universiti Kebangsaan Malaysia\nLampiran A')['guard'], 'later_page')


class UkmWiringTest(SimpleTestCase):
    def test_ink_targets_hold_the_ic_and_date_as_printed(self):
        phrases, values = ukm_ink_targets(run()['locked'], layout())
        self.assertEqual(len(phrases), 9)
        got = dict(values)
        self.assertEqual((got['v:name'], got['v:nric'], got['v:intake']), (NAME, IC, INTAKE))
        self.assertEqual((got['v:date'], got['v:offer_date'], got['v:programme']), (REPORT_ON, OFFER_ON, PROGRAMME))
        self.assertFalse(any(REG in v for v in got.values()))
        self.assertEqual(set(read_ukm(layout())[0]), set(INK_LABELS) | set(NOT_PRINTED))
        self.assertTrue(set(INK_OPTIONAL) <= set(INK_LABELS))

    def test_family_and_lane_modules(self):
        text = plain(layout())
        self.assertEqual(offer_parse.family_of(text), 'ukm')
        self.assertEqual(offer_exact._rules_family(text), 'ukm')
        self.assertEqual(offer_exact._lane_module('ukm').LANE, 'ua:UKM')
        why_ = {}
        offer_exact._note_ums_refusal(why_, text, 'no_layout')
        self.assertEqual(why_, {'lane': 'ua:UKM', 'reason': 'read_no_layout'})

    def test_not_inked_dispatches_to_ukm(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), 'ua:UKM'), [])
            self.assertEqual(ink.call_args.kwargs['lane'], 'ua:UKM')

    @override_settings(OCR_FIRST_LANES=[])
    def test_lane_off_by_default(self):
        text = plain(layout())
        why_ = {}
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(text, text)):
            self.assertIsNone(offer_exact.exact_offer_read(text, image=b'%PDF', content_type='application/pdf',
                                                           why=why_))
        self.assertEqual(why_, {'lane': 'ua:UKM', 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=['ua:UKM'])
    def test_lane_on_reads_the_layout(self):
        lay = layout()
        p1 = plain(lay)
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(p1, p1)), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_page1_layout', return_value=lay), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_rules_page_texts', return_value=[p1]), \
                mock.patch.object(offer_exact, '_not_inked', return_value=[]):
            ex = offer_exact.exact_offer_read(p1, image=b'%PDF', content_type='application/pdf', profile_nric=NRIC)
        self.assertIsNotNone(ex)
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), ('ua:UKM', NRIC))
