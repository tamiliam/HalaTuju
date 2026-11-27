"""OCR-14b-2: the UniMAP rules lane (`offer_parse_unimap`). UniMAP prints the IC with NO label, alone on the line
under the name, so it is stored with source 'other': CORROBORATE-ONLY under the usual IC guard, kept only when it is
exactly the profile IC (UniMAP is NOT in `offer_exact.ISSUER_PRINTS_NO_IC`), as on UniSZA. The 2025/2026 layout
only; any other layout and a Diploma refuse. No excuse of any kind: a blank later page refuses as a hidden page (the
shared drawn-page check), a portal tell and a withdrawal refuse as on every lane. Synthetic letters only (made-up
names, numbers and addresses)."""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_owner_words import missing
from apps.scholarship.offer_parse_unimap import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, REPORT_LABEL, is_unimap
from apps.scholarship.offer_parse_unimap import read_unimap, unimap_ink_targets, unimap_later_pages
from apps.scholarship.offer_parse_unimap import TEMPLATE_PINS, _pin_digest, unimap_letter_refusal

BASE = ' ' * 42
NAME = 'ZORBEX QUENTARO A/L ALFEN'
IC = '990101145678'
NRIC = '990101-14-5678'
CODE = 'UR6599001'
REF = 'UniMAP/AMD/107/2/' + CODE + '/G/I/SEPT2026(1234)'
PROGRAMME = 'SARJANA MUDA KEJURUTERAAN ELEKTRIK DENGAN KEPUJIAN'
INTAKE = 'SIDANG AKADEMIK 2026/2027'
OFFER_ON = '6 September 2026'
ADDRESS = ('NO 12, JALAN MAWAR 3', 'TAMAN CONTOH', '01000  KANGAR', 'PERLIS')
TITLE = ('   '.join('TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA PERLIS (UniMAP) BAGI SIDANG AKADEMIK'.split()),
         '2026/2027')
GREETING = ('Sukacita saya bagi pihak Universiti Malaysia Perlis (UniMAP) mengucapkan tahniah dan memaklumkan bahawa',
            'saudara/i ditawarkan tempat untuk mengikuti program pengajian seperti berikut:')
PROGRAMME_ROW = ('SARJANA      MUDA      KEJURUTERAAN     ELEKTRIK      DENGAN', 'KEPUJIAN')
ROWS = (('Program Pengajian', PROGRAMME_ROW), ('Kod Program', (CODE,)),
        ('Fakulti', ('FAKULTI KEJURUTERAAN ELEKTRIK',)), ('No. Matrik', ('261201234',)),
        ('Tempoh Pengajian', ('EMPAT (4) TAHUN (8 SEMESTER)',)), ('Yuran Dikenakan', ('RM 2,200.00.00 (SEMESTER 1)',)))
REGISTER_INTRO = 'Di bawah adalah butiran berkaitan dengan proses pendaftaran diri :'
REPORT = '26 SEPTEMBER 2026 (SABTU)'
VENUE = ('DEWAN UTAMA, KAMPUS CONTOH', '(Rujuk  Panduan  Am  Pendaftaran  Pelajar', 'Baharu, Sidang 2026/2027)')
REGISTER = (('Tarikh Pendaftaran', (REPORT,)), ('Masa Pendaftaran', ('8.30 PAGI HINGGA 4.30 PETANG',)),
            ('Lokasi Pendaftaran', VENUE))
COSTS = ('Sebagai makluman, kos pengajian adalah seperti berikut:',
         ' ' * 81 + 'Kos Yang Ditanggung' + ' ' * 17 + 'Kos Yang',
         ' ' * 48 + 'Tempoh Pengajian' + ' ' * 20 + 'Oleh Pelajar (RM)' + ' ' * 14 + 'Ditanggung' + ' ' * 12
         + 'Kos Keseluruhan (RM)',
         ' ' * 113 + 'Oleh Kerajaan',
         ' ' * 50 + 'Satu (1) Tahun' + ' ' * 24 + 'RM 3,000.00' + ' ' * 16 + 'RM 19,000.00' + ' ' * 17 + 'RM 22,000.00',
         ' ' * 49 + '* Empat (4) Tahun' + ' ' * 21 + 'RM 12,000.00' + ' ' * 15 + 'RM 76,000.00' + ' ' * 17
         + 'RM 88,000.00',
         ' ' * 45 + '** jumlah kos pengajian yang sebenar bergantung kepada tempoh pengajian yang diikuti pelajar.')
NOTES = ('2. Sila rujuk Lampiran A, B, C, D dan E serta lengkapkan butiran berkaitan.',
         '3. Tawaran ini adalah muktamad dan sebarang pertukaran program adalah tidak dibenarkan.',
         'Sekian, terima kasih')
FOOTER = ("'MALAYSIA MADANI'", "'BERKHIDMAT UNTUK NEGARA'", ' ' * 4 + '(QARIM VELTO BIN DURAN)',
          ' ' * 7 + 'Timbalan Pendaftar Kanan', ' ' * 4 + 'Pusat Pengurusan Akademik')
#: Review round 2: the module pins the MEASURED footer and venue (`TEMPLATE_PINS`, digests only); these tests run
#: against the synthetic ones above, pinned the same way (`synthetic_pins`, started for the whole module).
SYNTHETIC_PINS = {'footer': frozenset({_pin_digest(FOOTER)}), 'venue': frozenset({_pin_digest(VENUE, '2026/2027')})}
REAL_PINS = dict(TEMPLATE_PINS)


def synthetic_pins():
    return mock.patch.dict(TEMPLATE_PINS, SYNTHETIC_PINS)


_PINS = synthetic_pins()


def setUpModule():
    _PINS.start()


def tearDownModule():
    _PINS.stop()


def head(label, value):
    return ' ' * 80 + label.ljust(22) + ': ' + value


def row(label, value):
    return ' ' * 45 + label.ljust(25) + ':' + ' ' * 5 + value


def block(rows):
    out = []
    for label, values in rows:
        out += [row(label, values[0]), *(' ' * 76 + v for v in values[1:])]
    return out


def rows_with(rows, label, values):
    return tuple((n, values if n == label else v) for n, v in rows)


def layout(ref=REF, dated=OFFER_ON, name=NAME, ic=IC, address=ADDRESS, phone='TEL : 01234567890', title=TITLE,
           greeting=GREETING, rows=ROWS, register=REGISTER, costs=COSTS, notes=NOTES, extra=(), footer=FOOTER):
    lines = [head('Rujukan Kami', ref), head('Tarikh', dated), *(BASE + x for x in (name, ic, *address)),
             *((BASE + phone,) if phone else ()), BASE + 'Saudara/i,', *(BASE + x for x in (*title, *greeting)),
             *block(rows), BASE + REGISTER_INTRO, *block(register), BASE + costs[0], *costs[1:],
             *(BASE + x for x in (*notes, *extra, *footer))]
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


class UnimapLockTest(SimpleTestCase):
    def test_degree_letter_locks_with_its_unlabelled_ic_and_reporting_date(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane'], lock['_family']), ('unimap', LANE, 'unimap'))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), (NRIC, 'other'))
        self.assertEqual((lock['programme'], lock['programme_code']), (PROGRAMME, CODE))
        self.assertEqual(lock['intake'], INTAKE)
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('26 Sep 2026', REPORT_LABEL))
        self.assertEqual((lock['reporting_venue'], lock['campus'], lock['stream']), ('', '', ''))
        self.assertEqual(lock['offer_date'], OFFER_ON)
        self.assertEqual(lock['institution'], 'UNIVERSITI MALAYSIA PERLIS')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_measured_variants_still_lock(self):
        one_line = rows_with(ROWS, 'Program Pengajian', ('SARJANA MUDA SAINS KOMPUTER',))
        two_wraps = rows_with(ROWS, 'Program Pengajian', ('SARJANA   MUDA   TEKNOLOGI', 'KEJURUTERAAN ELEKTRIK',
                                                          'DENGAN KEPUJIAN'))
        justified = rows_with(REGISTER, 'Lokasi Pendaftaran', (VENUE[0], VENUE[1].replace('  ', '   '), VENUE[2]))
        times = rows_with(REGISTER, 'Masa Pendaftaran', ('9.12 PAGI HINGGA 12.10 TENGAH HARI',))   # read, not a date
        shifted = ['\n'.join((' ' * 6 + ln) for ln in layout().splitlines()),            # base 48
                   '\n'.join(ln[6:] for ln in layout().splitlines())]                    # base 36
        for lay in (layout(address=ADDRESS[:2]), layout(address=ADDRESS + ('MALAYSIA',)), layout(rows=one_line),
                    layout(rows=two_wraps), layout(register=justified), layout(register=times), *shifted):
            with self.subTest(lines=lay.count('\n'), size=len(lay)):
                self.assertIsNotNone(run(lay)['locked'], why(run(lay)))

    def test_the_gate_names_the_lane_by_its_tidied_name(self):
        from apps.scholarship.eval.offer_read_check import RULES_LANES, tidy_institution
        name = tidy_institution('Universiti Malaysia Perlis (UniMAP)').lower()
        self.assertEqual(RULES_LANES.get(name), LANE)
        self.assertTrue(all(tidy_institution(k).lower() == k for k in RULES_LANES))

    def test_the_matric_reference_and_phone_are_never_stored(self):
        lock = run()['locked']
        self.assertFalse(any(s in str(v) for v in lock.values() for s in ('261201234', '1234)', '01234567890')))

    def test_is_unimap(self):
        self.assertTrue(is_unimap(plain(layout()).upper()))
        self.assertFalse(is_unimap('UNIVERSITI MALAYSIA PERLIS SLIP PENDAFTARAN'))


class UnimapRefusalTest(SimpleTestCase):
    def test_a_diploma_refuses(self):
        for lay in (layout(rows=rows_with(ROWS, 'Program Pengajian', ('DIPLOMA KEJURUTERAAN ELEKTRIK',))),
                    layout(rows=rows_with(ROWS, 'Program Pengajian', ('SARJANA MUDA', 'DIPLOMA LANJUTAN'))),
                    layout(extra=('Program Diploma ini ditawarkan oleh UniMAP.',))):
            with self.subTest(size=len(lay)):
                self.assertIsNone(run(lay)['locked'])

    def test_another_layout_refuses(self):
        flat = '\n'.join(ln.lstrip() for ln in layout().splitlines())         # the page at the left margin
        one_line = (TITLE[0] + ' ' + TITLE[1],)
        for lay in (flat, layout(title=one_line), layout(title=(TITLE[0].replace('   ', '     '), TITLE[1]))):
            with self.subTest(size=len(lay)):
                self.assertIsNone(run(lay)['locked'])
        self.assertEqual(read_unimap(flat)[1], 'no_title')        # review round 1: base 0 is below the margin

    def test_the_title_gaps_and_the_margin_are_as_measured(self):
        """Review round 1: every title gap exactly 3 (measured); the base indent 36-48 (measured 42), so a page at
        the left margin (0) or far in refuses before any field is read."""
        words = TITLE[0].split('   ')
        mixed = '   '.join(words[:3]) + '  ' + '   '.join(words[3:])
        for case, title in (('gap1', ' '.join(words)), ('gap2', '  '.join(words)), ('gap4', '    '.join(words)),
                            ('mixed', mixed)):
            with self.subTest(case=case):
                self.assertEqual(read_unimap(layout(title=(title, TITLE[1]))), (None, 'no_title'))
                self.assertIsNone(run(layout(title=(title, TITLE[1])))['locked'])
        for case, lay in (('margin0', '\n'.join(ln[42:] for ln in layout().splitlines())),
                          ('base35', '\n'.join(ln[7:] for ln in layout().splitlines())),
                          ('base49', '\n'.join(' ' * 7 + ln for ln in layout().splitlines()))):
            with self.subTest(case=case):
                self.assertEqual(read_unimap(lay), (None, 'no_title'))
                self.assertIsNone(run(lay)['locked'])

    def test_any_change_to_the_table_or_head_refuses(self):
        moved = '\n'.join(ln.replace(' ' * 45 + 'Fakulti', ' ' * 46 + 'Fakulti') for ln in layout().splitlines())
        late_wrap = '\n'.join(ln.replace(' ' * 76 + 'KEPUJIAN', ' ' * 77 + 'KEPUJIAN')
                              for ln in layout().splitlines())
        for lay in (layout(ref='UniMAP/107/2/' + CODE), layout(ref=REF.replace(CODE, 'UR6599002')),
                    layout(rows=rows_with(ROWS, 'Kod Program', ('UR6599002',))),
                    layout(dated='31 Februari 2026'), layout(dated='6 SEPTEMBER 2026'),
                    layout(address=ADDRESS[:1]), layout(address=ADDRESS + ('MALAYSIA', 'ASIA')), layout(phone=''),
                    layout(ic='990101-14-5678'), layout(name=NAME.title()), layout(rows=ROWS[1:] + ROWS[:1]),
                    layout(rows=rows_with(ROWS, 'Tempoh Pengajian', ('TIGA (4) TAHUN (8 SEMESTER)',))),
                    layout(rows=rows_with(ROWS, 'No. Matrik', ('BELUM ADA',))),
                    layout(rows=rows_with(ROWS, 'Yuran Dikenakan', ('PERCUMA',))),
                    layout(register=rows_with(REGISTER, 'Masa Pendaftaran', ('8.30 PAGI',))),
                    layout(costs=COSTS[:2] + COSTS[3:]), layout(notes=NOTES[1:]), moved, late_wrap,
                    layout(greeting=(GREETING[0], GREETING[1].replace('berikut', 'di bawah')))):
            with self.subTest(size=len(lay)):
                self.assertIsNone(run(lay)['locked'])

    def test_insane_dates_refuse(self):
        def report(value):
            return layout(register=rows_with(REGISTER, 'Tarikh Pendaftaran', (value,)))
        for lay in (layout(dated='6 September 2024', ref=REF.replace('SEPT2026', 'SEPT2024')),
                    report('26 SEPTEMBER 2028 (SELASA)'), report('25 SEPTEMBER 2026 (SABTU)'),
                    report('1 SEPTEMBER 2026 (SELASA)'), layout(title=(TITLE[0], '2026/2028')),
                    layout(ref=REF.replace('SEPT2026', 'SEPT2025')), report('31 SEPTEMBER 2026 (KHAMIS)')):
            with self.subTest(size=len(lay)):
                self.assertIsNone(run(lay)['locked'])

    def test_a_stray_date_changes_the_template(self):
        """Review round 2: there is no free text, so a date anywhere but its place changes the pinned template."""
        venue = rows_with(REGISTER, 'Lokasi Pendaftaran', ('DEWAN UTAMA', 'Taklimat 27 September 2026'))
        for lay in (layout(extra=('Taklimat pada 6 Oktober 2026.',)), layout(register=venue),
                    layout(footer=FOOTER + ('Kangar, 11 Okt.',))):
            with self.subTest(size=len(lay)):
                d = run(lay)
                self.assertIsNone(d['locked'])
                self.assertEqual(read_unimap(lay)[1], 'template_changed')

    def test_a_day_and_month_with_no_year_refuses(self):
        """Review rounds 1 and 2: a day and a month in any spelling, with no year, in the footer or the venue (as the
        whole venue or as a wrapped line) changes the pinned template."""
        for text in ('DEWAN UTAMA / PADA 27/9', 'PADA 27-9', 'PADA 27.9', 'PADA 27 / 09', 'PADA 27 SEPT',
                     'PADA 27 HB SEPTEMBER', 'pada 3 okt', 'PADA SEPT 27', 'Pada 1 Mac',
                     'PADA 27-SEPT', '27/SEP', 'SEPT-27', '27.SEP', '27TH OF SEPT', '9/27', '27_9', '27\\9', '27 9',
                     'DUA PULUH TUJUH SEPTEMBER'):
            for where, lay in (('venue', layout(register=rows_with(REGISTER, 'Lokasi Pendaftaran', (text,)))),
                               ('wrap', layout(register=rows_with(REGISTER, 'Lokasi Pendaftaran',
                                                                  (VENUE[0], text, *VENUE[1:])))),
                               ('footer', layout(footer=FOOTER + (text,))),
                               ('footer_mid', layout(footer=FOOTER[:2] + (text,) + FOOTER[2:]))):
                with self.subTest(text=text, where=where):
                    self.assertEqual(read_unimap(lay)[1], 'template_changed')
                    self.assertIsNone(run(lay)['locked'])

    def test_a_second_ic_or_code_refuses(self):
        for extra, reason in (('Penjaga: 750505-03-1234', 'second_ic'), (IC, 'second_ic'),
                              ('Kod lain UR6599002', 'second_code'), ('Kod ' + CODE, 'second_code')):
            with self.subTest(reason=reason, size=len(extra)):
                self.assertEqual(read_unimap(layout(extra=(extra,)))[1], reason)
                self.assertIsNone(run(layout(extra=(extra,)))['locked'])

    def test_a_code_in_any_spelling_refuses(self):
        """Review round 1: any case, any space, dash or dot inside, letters glued before it; the read code a third
        time refuses too."""
        for case, text in (('spaced', 'Kod Program : UR 6599002'), ('glued', 'XUR6599002'), ('lower', 'ur6599002'),
                           ('dash', 'UR-6599002'), ('dots', 'U.R. 659-9002'), ('same_spaced', 'UR 6599001'),
                           ('same_lower', 'ur6599001'), ('same_glued', 'XUR6599001'), ('eight', 'UR65990012')):
            with self.subTest(case=case):
                self.assertEqual(read_unimap(layout(footer=FOOTER + (text,)))[1], 'second_code')
                self.assertIsNone(run(layout(footer=FOOTER + (text,)))['locked'])
        self.assertEqual(read_unimap(layout(footer=FOOTER + ('UR659900',)))[1], 'template_changed')   # six digits

    def test_a_code_with_any_mark_inside_refuses_in_the_address_footer_or_venue(self):
        """Review round 2 backstop: every character but a letter or a digit taken out and O read as 0, a code-like
        run (two letters, seven digits) anywhere but its fixed places refuses, in the address, the footer and a
        wrapped Lokasi line alike, and split across two lines too."""
        for text in ('UR/6599002', 'UR_6599002', 'UR,6599002', 'UR+6599002', "UR'6599002", 'UR(6599002',
                     'UR–6599002', 'A' * 25 + 'UR6599002', 'UR6599OO2', 'UR 6599OO2'):
            for where, lay in (
                    ('address', layout(address=ADDRESS[:1] + ('TAMAN ' + text + ' INDAH',) + ADDRESS[2:])),
                    ('address_end', layout(address=ADDRESS[:3] + (text + ' PERLIS',))),
                    ('footer', layout(footer=FOOTER + (text,))),
                    ('wrap', layout(register=rows_with(REGISTER, 'Lokasi Pendaftaran', (VENUE[0], text, *VENUE[1:])))),
                    ('venue', layout(register=rows_with(REGISTER, 'Lokasi Pendaftaran', (text + ' ' + VENUE[0],
                                                                                         *VENUE[1:]))))):
                with self.subTest(text=text, where=where):
                    self.assertEqual(read_unimap(lay)[1], 'second_code')
                    self.assertIsNone(run(lay)['locked'])
        for where, lay in (('address', layout(address=ADDRESS[:1] + ('TAMAN UR', '6599002 JALAN') + ADDRESS[2:])),
                           ('footer', layout(footer=FOOTER + ('UR', '6599002'))),
                           ('wrap', layout(register=rows_with(REGISTER, 'Lokasi Pendaftaran',
                                                              (VENUE[0] + ' UR', '6599002', *VENUE[1:]))))):
            with self.subTest(where=where, split=True):
                self.assertEqual(read_unimap(lay)[1], 'second_code')

    def test_a_value_with_a_second_column_refuses(self):
        """Review round 1: gaps as measured (even, at most 6; a last line single-spaced), never a 9-space cut."""
        def programme(*parts):
            return layout(rows=rows_with(ROWS, 'Program Pengajian', parts))
        first = PROGRAMME_ROW[0]
        for case, lay in (('wrap8', programme(first, 'KEPUJIAN        AWAM')),
                          ('wrap6', programme(first, 'KEPUJIAN      AWAM')),
                          ('wrap2', programme(first, 'KEPUJIAN  AWAM')),
                          ('uneven', programme('SARJANA  MUDA      KEJURUTERAAN', 'KEPUJIAN')),
                          ('seven', programme('SARJANA       MUDA       KEJURUTERAAN', 'KEPUJIAN')),
                          ('one_line_wide', programme('SARJANA MUDA SAINS        AWAM')),
                          ('faculty', layout(rows=rows_with(ROWS, 'Fakulti', ('FAKULTI  KEJURUTERAAN ELEKTRIK',)))),
                          ('venue_colon', layout(register=rows_with(REGISTER, 'Lokasi Pendaftaran',
                                                                    ('DEWAN UTAMA', 'Nama : ALFEN BIN QORDA'))))):
            with self.subTest(case=case):
                self.assertIn(read_unimap(lay)[1], ('table_shape', 'reporting_shape'))
                self.assertIsNone(run(lay)['locked'])

    def test_a_field_outside_its_place_refuses(self):
        """Review rounds 1 and 2: nothing after the notes and no wrapped line may print anything but the pinned
        template; the address only upper-case words and numbers with no year and no other person."""
        def venue(*parts):
            return layout(register=rows_with(REGISTER, 'Lokasi Pendaftaran', parts))
        for case, lay, reason in (
                ('amended', layout(footer=FOOTER + ('Program Pengajian dipinda : KEJURUTERAAN AWAM',)),
                 'template_changed'),
                ('amended_no_colon', layout(footer=FOOTER + ('Program Pengajian dipinda KEJURUTERAAN AWAM',)),
                 'template_changed'),
                ('name_row', layout(footer=FOOTER + ('Nama : ALFEN BIN QORDA',)), 'template_changed'),
                ('name_line', layout(footer=FOOTER + ('ALFEN BIN QORDA',)), 'template_changed'),
                ('name_no_link', layout(footer=FOOTER + ('ALFEN QORDA',)), 'template_changed'),
                ('two_signers', layout(footer=FOOTER + ('(ALFEN BIN QORDA)',)), 'template_changed'),
                ('half_paren', layout(footer=FOOTER[:2] + ('(QARIM VELTO BIN DURAN',) + FOOTER[3:]),
                 'template_changed'),
                ('no_footer', layout(footer=()), 'template_changed'),
                ('ic_label', layout(footer=FOOTER + ('No. K/P pelajar',)), 'template_changed'),
                ('session', layout(footer=FOOTER + ('Sesi kemasukan baharu',)), 'template_changed'),
                ('long_footer', layout(footer=FOOTER + ('Perlis',) * 5), 'template_changed'),
                ('venue_date', venue(*VENUE[:2], 'Tarikh baharu SABTU depan'), 'template_changed'),
                ('venue_programme', venue(VENUE[0], 'PROGRAM DIGANTI KEJURUTERAAN AWAM', *VENUE[1:]),
                 'template_changed'),
                ('venue_name', venue(VENUE[0], 'ALFEN BIN QORDA', *VENUE[1:]), 'template_changed'),
                ('venue_short', venue(VENUE[0], VENUE[2]), 'template_changed'),
                ('venue_session', venue(*VENUE[:2], VENUE[2].replace('2026/2027', '2025/2026')), 'second_code'),
                ('venue_session_alone', venue(*VENUE[:2], VENUE[2] + ' 2026/2028'),
                 'template_changed'),
                ('address_colon', layout(address=ADDRESS[:3] + ('U/P : ENCIK QORDA',)), 'address_shape'),
                ('address_care_of', layout(address=ADDRESS[:3] + ('D/A AHMAD BIN ALI',)), 'address_shape'),
                ('address_care_of_spaced', layout(address=ADDRESS[:3] + ('D / A AHMAD',)), 'address_shape'),
                ('address_bin', layout(address=ADDRESS[:3] + ('AHMAD BIN ALI',)), 'address_shape'),
                ('address_year', layout(address=ADDRESS[:3] + ('27 SEPT 2026',)), 'address_shape'),
                ('address_lower', layout(address=ADDRESS[:3] + ('Taman Contoh',)), 'address_shape'),
                ('name_again', layout(address=ADDRESS + (NAME.replace(' A/L ', ' ').upper(),),
                                      name=NAME.replace(' A/L ', ' ')), 'second_name')):
            with self.subTest(case=case):
                self.assertEqual(read_unimap(lay)[1], reason)
                self.assertIsNone(run(lay)['locked'])

    def test_an_address_of_unit_numbers_and_field_words_still_locks(self):
        """Review round 2: the address is never read, so a unit number, a month-like word and a word that names a
        field elsewhere are all fine there, at any line, beside the postcode too; so is a cost with no comma."""
        for text in ('NO 12-3, JALAN MAWAR', 'JALAN 2/5', 'NO. 5-1 BLOK A', 'KAMPUNG MAC 3', 'BLOK 2/3', 'ARAS 1-2',
                     'TAMAN MASA', 'JALAN KAMPUS', 'LOT 123456'):
            for where, address in (('first', (text,) + ADDRESS[1:]), ('before_postcode', ADDRESS[:1] + (text,)
                                                                      + ADDRESS[2:])):
                with self.subTest(text=text, where=where):
                    lay = layout(address=address)
                    self.assertEqual(read_unimap(lay)[1], '')
                    self.assertIsNotNone(run(lay)['locked'], why(run(lay)))
        costs = COSTS[:4] + (COSTS[4].replace('RM 3,000.00', 'RM 3000.00'),) + COSTS[5:]
        self.assertIsNotNone(run(layout(costs=costs))['locked'], why(run(layout(costs=costs))))

    def test_the_pin_refuses_a_one_character_change_anywhere_in_the_fixed_text(self):
        """Review round 2: a synthetic copy of the pinned structure (the footer and the venue, pinned), and the fixed
        lines read as exact text (salutation, greeting, registration intro, cost block, notes): one character
        changed or taken out anywhere refuses."""
        def changed(text, k, cut):
            return text[:k] + ('' if cut else ('Q' if text[k] != 'Q' else 'Z')) + text[k + 1:]
        cases = []
        for n, line in enumerate(FOOTER):
            for k in (k for k, c in enumerate(line) if c != ' '):
                for cut in (False, True):
                    cases.append(('footer', layout(footer=FOOTER[:n] + (changed(line, k, cut),) + FOOTER[n + 1:])))
        for n, line in enumerate(VENUE):
            for k in (k for k, c in enumerate(line) if c != ' '):
                for cut in (False, True):
                    parts = VENUE[:n] + (changed(line, k, cut),) + VENUE[n + 1:]
                    cases.append(('venue', layout(register=rows_with(REGISTER, 'Lokasi Pendaftaran', parts))))
        for n, line in enumerate(GREETING):
            for k in (k for k, c in enumerate(line) if c != ' '):
                cases.append(('greeting', layout(greeting=GREETING[:n] + (changed(line, k, False),) + GREETING[n + 1:])))
        for n, line in enumerate(NOTES):
            for k in (k for k, c in enumerate(line) if c != ' '):
                cases.append(('notes', layout(notes=NOTES[:n] + (changed(line, k, False),) + NOTES[n + 1:])))
        for n in (0, 1, 2, 3, 6):
            for k in (k for k, c in enumerate(COSTS[n]) if c != ' '):
                cases.append(('costs', layout(costs=COSTS[:n] + (changed(COSTS[n], k, False),) + COSTS[n + 1:])))
        for k in range(len('Saudara/i,')):
            cases.append(('salutation', layout().replace('Saudara/i,', changed('Saudara/i,', k, False))))
        for k in (k for k, c in enumerate(REGISTER_INTRO) if c != ' '):
            cases.append(('intro', layout().replace(REGISTER_INTRO, changed(REGISTER_INTRO, k, False))))
        self.assertGreater(len(cases), 800)
        pinned = 0
        for where, lay in cases:
            reason = read_unimap(lay)[1]
            pinned += reason == 'template_changed'
            if reason == '':
                self.fail(f'{where}: a one-character change locked')
        self.assertGreater(pinned, 300)        # the footer and the venue refuse by the pin itself

    def test_the_measured_pins_are_digests_and_refuse_the_synthetic_letter(self):
        """The module ships the MEASURED pins: one sha256 each, never text; the synthetic letter is not them."""
        for key in ('footer', 'venue'):
            with self.subTest(key=key):
                self.assertEqual(len(REAL_PINS[key]), 1)
                self.assertTrue(all(len(d) == 64 and set(d) <= set('0123456789abcdef') for d in REAL_PINS[key]))
                self.assertFalse(REAL_PINS[key] & SYNTHETIC_PINS[key])
        with mock.patch.dict(TEMPLATE_PINS, REAL_PINS):
            self.assertEqual(read_unimap(layout())[1], 'template_changed')
            self.assertIsNone(run()['locked'])

    def test_a_later_page_refuses_even_when_blank(self):
        """No excuse: a page 2 with text refuses ``later_page``; a BLANK page 2 refuses ``hidden_page`` by the shared
        drawn-page check, as on every lane."""
        self.assertEqual(unimap_later_pages(['Lampiran A']), 'later_page')
        self.assertEqual(unimap_later_pages(['', '  ']), '')
        self.assertEqual(run(page2='Lampiran A')['guard'], 'later_page')
        self.assertEqual(run(page2='')['guard'], 'hidden_page')

    def test_a_scan_refuses_no_layout(self):
        self.assertEqual(offer_parse.diagnose(plain(layout()), '', '', None)['guard'], 'no_layout')

    def test_a_status_letter_refuses(self):
        self.assertEqual(read_unimap(layout(extra=('PENGESAHAN PENDAFTARAN',)))[1], 'status_letter')

    def test_a_portal_tell_or_withdrawal_refuses_with_no_excuse(self):
        for line in ('Sila cetak slip ini', 'SEMAKAN TAWARAN'):
            with self.subTest(line=line):
                self.assertTrue(run(layout(extra=(line,)))['portal'])
        for line in ('Tawaran ini telah ditarik balik.', 'Tawaran ini dibatalkan.', 'Anda tidak layak.'):
            with self.subTest(line=line), mock.patch.dict(TEMPLATE_PINS, {'footer': {_pin_digest((line, *FOOTER))}}):
                d = run(layout(extra=(line,)))        # pinned as if measured: the guard itself must refuse
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'not_an_offer')
                self.assertEqual(unimap_letter_refusal(plain(layout(extra=(line,))), NRIC), 'not_an_offer')
        self.assertEqual(unimap_letter_refusal(plain(layout()), NRIC), '')


class UnimapOwnerWordsTest(SimpleTestCase):
    def test_the_owner_words_hold_on_the_layout(self):
        self.assertEqual(missing(LANE, layout(), text_pdf=True), [])

    def test_a_missing_owner_phrase_refuses(self):
        self.assertEqual(read_unimap(layout(footer=FOOTER[:-1]))[1], 'template_changed')
        with mock.patch.dict(TEMPLATE_PINS, {'footer': {_pin_digest(FOOTER[:-1])}}):   # the owner words refuse too
            d = run(layout(footer=FOOTER[:-1]))
        self.assertIsNone(d['locked'])
        self.assertEqual(d['guard'], 'owner_words_missing')


class UnimapInkTest(SimpleTestCase):
    def test_ink_targets_cover_every_printed_value(self):
        lock = run()['locked']
        phrases, values = unimap_ink_targets(lock, layout())
        self.assertEqual([lab for lab, _ in phrases], [f'p{k}' for k in range(1, 9)])
        got = dict(values)
        self.assertEqual((got['v:nric'], got['v:date'], got['v:code']), (IC, '26 SEPTEMBER 2026', CODE))
        self.assertEqual(got['v:name'], NAME)
        self.assertEqual(set(INK_LABELS) | set(NOT_PRINTED), set(lock) - {'_family', 'rules_lane',
                                                                            '_offer_parser_version'})
        self.assertEqual(INK_OPTIONAL, ())

    def test_not_inked_dispatches_to_unimap(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), LANE), [])
            self.assertEqual(ink.call_args.kwargs['lane'], LANE)

    def test_the_unlabelled_ic_is_kept_only_when_it_is_the_profile_ic(self):
        """No label names the IC, so it is source 'other': the usual IC guard keeps it only when it is EXACTLY the
        profile IC; a different or blank profile IC refuses (UniMAP prints the IC: not in ISSUER_PRINTS_NO_IC)."""
        self.assertNotIn(LANE, offer_exact.ISSUER_PRINTS_NO_IC)
        ex = exact()
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric'], ex['fields']['candidate_nric_source']),
                         (LANE, NRIC, 'other'))
        for profile in ('880505-10-1234', '990101-14-5679', ''):
            with self.subTest(profile=profile):
                why_ = {}
                self.assertIsNone(exact(profile=profile, why_=why_))
                self.assertEqual(why_, {'lane': LANE, 'reason': 'read_nric_guard'})

    def _offer_read(self, why_=None):
        lay = layout()
        p1 = plain(lay)
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(p1, p1)), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_page1_layout', return_value=lay), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_rules_page_texts', return_value=[p1]), \
                mock.patch.object(offer_exact, '_not_inked', return_value=[]):
            return offer_exact.exact_offer_read(p1, image=b'%PDF', content_type='application/pdf',
                                                profile_nric=NRIC, why=why_)

    @override_settings(OCR_FIRST_LANES=[])
    def test_the_lane_is_off_by_default(self):
        why_ = {}
        self.assertIsNone(self._offer_read(why_))
        self.assertEqual(why_, {'lane': LANE, 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=[LANE])
    def test_the_lane_reads_when_on(self):
        ex = self._offer_read()
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_name']), (LANE, NAME))
