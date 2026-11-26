"""OCR-14 phase 7: the UMK rules lane (`offer_parse_umk`). UMK PRINTS the IC with its label ("NO. KAD PENGENALAN:")
in the head's right-hand column, so it is read from that one row (source 'label') under the usual IC guard
(`offer_exact.exact_read`; UMK is NOT in `offer_exact.ISSUER_PRINTS_NO_IC`), printed exactly once. Any other IC-like
number refuses; the matric number and the reference are never stored; the reporting date is read only from its
labelled row after the registration sentence, never guessed. Synthetic letters only (made-up names, numbers and
addresses)."""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_parse_umk import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, is_umk, read_umk
from apps.scholarship.offer_parse_umk import umk_ic_elsewhere, umk_ink_targets, umk_later_pages, umk_letter_refusal

NAME = 'ZORBEX QUENTARO BIN ALFEN'
IC = '990101145678'
NRIC = '990101-14-5678'
MATRIC = 'A26A1234'
PROGRAMME = 'SARJANA MUDA SAINS GUNAAN (BIOTEKNOLOGI) DENGAN KEPUJIAN'
FACULTY = 'FAKULTI BIOKEJURUTERAAN DAN TEKNOLOGI'
INTAKE = 'SEMESTER SEPTEMBER SESI AKADEMIK 2026/2027'
OFFER_ON = '20/07/2026'
REPORT_ON = '13 SEP 2026'
LH = ' ' * 20
LETTERHEAD = ('PUSAT PENGURUSAN AKADEMIK', 'PEJABAT TIMBALAN NAIB CANSELOR (AKADEMIK & ANTARABANGSA)',
              'UNIVERSITI MALAYSIA KELANTAN', '16300 BACHOK KELANTAN', 'TELEFON : 09-947 7000/7001',
              'TELEFAX : 09-947 7002')
ADDRESS = ('NO 12, JALAN MAWAR 3', '16100 KOTA BHARU, KELANTAN, MALAYSIA.')
IC_ROW = ' ' * 80 + 'NO. KAD PENGENALAN:' + IC
MATRIC_ROW = ' ' * 90 + 'NO. MATRIK:      ' + MATRIC
DATED_ROW = ' ' * 95 + 'TARIKH:    ' + OFFER_ON
TITLE = ('TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA KELANTAN SEMESTER SEPTEMBER SESI AKADEMIK', '2026/2027')
GREETING = ('Tahniah, sukacita dimaklumkan anda telah ditawarkan tempat bagi mengikuti program pengajian seperti',
            'berikut:-')
ROWS = (('Program', PROGRAMME), ('Tahun', 'PERTAMA'), ('Fakulti', FACULTY), ('Tempoh', '8 SEMESTER'))
REGISTER = 'Sila mendaftar pada tarikh, masa dan tempat seperti berikut:-'
REPORT = ('Tarikh : ' + REPORT_ON, 'Masa : 8:00AM hingga 12:00PM', 'Tempat : sila rujuk slip pendaftaran pelajar baharu',
          'Kampus : KAMPUS JELI')
NOTES = ('Bayaran dan Kemudahan', 'Yuran pengajian semester pertama adalah RM 1,234.00.', 'MUSTAHAK',
         '1. Tawaran ini adalah tertakluk kepada syarat-syarat tawaran kemasukan yang dilampirkan.',
         '2. Tawaran ini adalah MUKTAMAD.', '3. Sila bawa dokumen asal semasa pendaftaran.',
         '4. Sila semak e-mel pelajar anda secara berkala.')
FOOTER = ('Sekian, terima kasih.', 'BERKHIDMAT UNTUK NEGARA', 'Saya yang menjalankan amanah,',
          'QARIM VELTO BIN DURAN', 'Timbalan Pendaftar')


def row(name, value):
    return name + ' ' * (10 - len(name)) + ':' + value


def rows_with(name, value):
    return tuple((n, value if n == name else v) for n, v in ROWS)


def layout(name=NAME, address=ADDRESS, ic_row=IC_ROW, matric_row=MATRIC_ROW, dated_row=DATED_ROW,
           salutation='Saudara/i,', title=TITLE, greeting=GREETING, rows=ROWS, register=REGISTER, report=REPORT,
           notes=NOTES, extra=(), footer=FOOTER, letterhead=LETTERHEAD):
    lines = [*(LH + h for h in letterhead), *name.split('\n'), *address, ic_row, matric_row, dated_row, salutation,
             *title, *greeting, *(row(n, v) for n, v in rows), register, *report, *notes, *extra, *footer]
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


class UmkLockTest(SimpleTestCase):
    def test_degree_letter_locks_with_its_labelled_ic_and_reporting_date(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane'], lock['_family']), ('umk', LANE, 'umk'))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), (NRIC, 'label'))
        self.assertEqual((lock['programme'], lock['programme_code']), (PROGRAMME, ''))
        self.assertEqual(lock['intake'], INTAKE)
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('13 Sep 2026', 'Tarikh'))
        self.assertEqual((lock['reporting_venue'], lock['campus'], lock['stream']), ('', '', ''))
        self.assertEqual(lock['offer_date'], '')           # review r1: the head TARIKH is never stored
        self.assertEqual(lock['institution'], 'UNIVERSITI MALAYSIA KELANTAN')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_r1_the_head_date_is_never_stored_and_blanks_a_prior_ai_offer_date(self):
        # OCR-14 review r1: the head "TARIKH" may be the print date, so the lock writes the offer date BLANK over
        # an earlier AI value; the head date still gates the lock (dates_not_sane).
        lay = layout()
        p1 = plain(lay)
        ex = offer_exact.exact_read(p1, from_text_layer=True, page1_layer=p1, page1_layout=lay, page_texts=[p1],
                                    profile_nric=NRIC, prior={'fields': {'offer_date': '1 Jul 2026'}})
        self.assertIsNotNone(ex)
        self.assertEqual(ex['fields']['offer_date'], '')
        self.assertIsNone(run(layout(dated_row=' ' * 95 + 'TARIKH:    20/10/2026'))['locked'])   # after the report

    def test_value_shapes_that_still_lock(self):
        for name, value in (('Program', 'SARJANA MUDA PERNIAGAAN (PERUNCITAN) DENGAN KEPUJIAN'),
                            ('Fakulti', 'FAKULTI KEUSAHAWANAN DAN PERNIAGAAN'), ('Tempoh', '7 SEMESTER')):
            with self.subTest(name=name, value=value):
                d = run(layout(rows=rows_with(name, value)))
                self.assertIsNotNone(d['locked'], why(d))
                self.assertEqual(d['locked']['candidate_nric'], NRIC)
        for lay in (layout(title=(' '.join(TITLE),)), layout(greeting=(' '.join(GREETING),)),
                    layout().replace(row('Program', PROGRAMME), 'Program:' + PROGRAMME),
                    layout(address=ADDRESS + ('KELANTAN',)), layout(report=('Tarikh: 3 SEP 2026',) + REPORT[1:])):
            with self.subTest(lay=lay.count('\n')):
                self.assertIsNotNone(run(lay)['locked'], why(run(lay)))

    def test_matric_and_reference_are_never_stored(self):
        lock = run()['locked']
        self.assertFalse(any(MATRIC in str(v) for v in lock.values()))
        self.assertFalse(any('1234' in str(v) for k, v in lock.items() if k != 'candidate_nric'))

    def test_a_scan_refuses_no_layout(self):
        d = offer_parse.diagnose(plain(layout()), '', '', None)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('umk', 'no_layout', None))


class UmkProgrammeTest(SimpleTestCase):
    def test_the_table_must_hold_its_four_rows_in_order(self):
        self.assertEqual(run(layout(rows=(ROWS[1], ROWS[0]) + ROWS[2:]))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=ROWS[:3]))['guard'], 'table_shape')    # the 4th row read is the next line
        self.assertEqual(run(layout(rows=rows_with('Tahun', 'KEDUA')))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=rows_with('Tempoh', '4 TAHUN')))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=rows_with('Fakulti', 'PUSAT BAHASA')))['guard'], 'programme_shape')
        two_cols = rows_with('Program', 'SARJANA MUDA SAINS   DENGAN KEPUJIAN')
        self.assertEqual(run(layout(rows=two_cols))['guard'], 'table_shape')
        lower = tuple((n.upper() if n == 'Program' else n, v) for n, v in ROWS)
        self.assertEqual(run(layout(rows=lower))['guard'], 'no_table')
        self.assertEqual(run()['locked']['programme'], PROGRAMME)

    def test_a_second_programme_refuses(self):
        self.assertEqual(run(layout(extra=('Program alternatif: SARJANA MUDA SAINS DENGAN KEPUJIAN',)))['guard'],
                         'not_degree')

    def test_diploma_asasi_and_non_degree_refuse(self):
        for prog in ('DIPLOMA SAINS GUNAAN', 'ASASI SAINS', 'SARJANA SAINS GUNAAN DENGAN KEPUJIAN',
                     'SARJANA MUDA SAINS GUNAAN', 'SARJANA MUDA DIPLOMA LANJUTAN DENGAN KEPUJIAN',
                     'SARJANA MUDA ASASI SAINS DENGAN KEPUJIAN', PROGRAMME + ' X'):
            with self.subTest(prog=prog):
                d = run(layout(rows=rows_with('Program', prog)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('programme_shape', 'not_degree', 'asasi_ai_read'))
        for line in ('Program Diploma Sains Gunaan', 'Pelajar Asasi Sains', 'Sila bawa sijil asal.',
                     'Program Persediaan Bahasa'):
            with self.subTest(line=line):
                self.assertIn(run(layout(extra=(line,)))['guard'], ('not_degree', 'asasi_ai_read'))

    def test_diploma_asasi_titles_and_confirmations_refuse(self):
        for first in ('TAWARAN KEMASUKAN KE PROGRAM DIPLOMA UNIVERSITI MALAYSIA KELANTAN SEMESTER SEPTEMBER SESI '
                      'AKADEMIK', 'TAWARAN KEMASUKAN KE PROGRAM ASASI UNIVERSITI MALAYSIA KELANTAN SEMESTER '
                      'SEPTEMBER SESI AKADEMIK', 'TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA KELANTAN SEMESTER '
                      'FEBRUARI SESI AKADEMIK'):
            with self.subTest(first=first[:40]):
                self.assertEqual(read_umk(layout(title=(first, TITLE[1])))[1], 'no_title')
                self.assertIsNone(run(layout(title=(first, TITLE[1])))['locked'])
        confirm = '\n'.join(('SURAT PENGESAHAN PELAJAR', 'UNIVERSITI MALAYSIA KELANTAN', 'NAMA : ' + NAME,
                             'NO. KAD PENGENALAN : ' + IC, 'TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA KELANTAN'))
        self.assertIsNone(run(confirm)['locked'])
        self.assertEqual(read_umk(confirm), (None, 'status_letter'))
        self.assertEqual(run(layout(extra=('PENGESAHAN KEMASUKAN',)))['guard'], 'status_letter')
        for line in ('Permohonan anda TIDAK BERJAYA.', 'Tawaran ini telah DIBATALKAN.',
                     'Tawaran ini telah ditarik balik.', 'Pendaftaran ditangguhkan.'):
            with self.subTest(line=line):
                d = run(layout(extra=(line,)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('status_letter', 'not_an_offer'))


class UmkIcTest(SimpleTestCase):
    def test_ic_shapes_refuse(self):
        """The labelled row must hold the 12 plain digits: a hyphen, an en dash, a minus, a slash, a space, a
        whitespace run, a tab, a short or long run or a line split refuses; so does no IC at all (UMK prints it)."""
        for ic in (NRIC, '990101 14 5678', '990101–14–5678', '990101−14−5678', '990101/14/5678',
                   '990101   14   5678', '990101\t14\t5678', '99010114567', '9901011456789', '',
                   '990101\n145678', '990101-14-\n5678'):
            with self.subTest(ic=ic):
                d = run(layout(ic_row=' ' * 80 + 'NO. KAD PENGENALAN:' + ic))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('ic_shape', 'no_head', 'second_ic'))
        for ic_row in (' ' * 80 + 'NO. K/P:' + IC, ' ' * 80 + IC, ' ' * 30 + 'NO. KAD PENGENALAN:' + IC,
                       ' ' * 80 + 'NO. KAD PENGENALAN ' + IC):
            with self.subTest(ic_row=ic_row.strip()[:10]):
                d = run(layout(ic_row=ic_row))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('no_head', 'second_ic'))

    def test_a_second_ic_anywhere_refuses(self):
        from apps.scholarship.tests.test_offer_parse_uum import IC_SHAPES
        for ic in IC_SHAPES + ('990102145678', '990102-14-5678', NRIC, IC):
            with self.subTest(ic=ic):
                lay = layout(extra=('No. K/P waris :' + ' ' * 10 + ic,))
                self.assertIsNone(run(lay)['locked'])
                self.assertEqual(read_umk(lay)[1], 'second_ic')
                self.assertEqual(umk_letter_refusal(plain(layout()) + '\nWaris ' + ic, NRIC), 'second_ic')
                self.assertIn(run(page2='Universiti Malaysia Kelantan\nNo. K/P : ' + ic)['guard'],
                              ('second_ic', 'ic_printed'))
                p1 = plain(layout())
                d = offer_parse.diagnose(p1, p1 + '\nWaris ' + ic, layout(), [p1])
                self.assertIsNone(d['locked'])
        self.assertEqual(umk_letter_refusal(plain(layout()), NRIC), '')
        self.assertFalse(umk_ic_elsewhere(plain(layout()), NRIC))
        self.assertTrue(umk_ic_elsewhere(plain(layout()), '990102-14-5678'))

    def test_the_read_ic_must_stand_in_the_plain_layer(self):
        p1 = plain(layout())
        for page1 in (p1.replace(IC, ''), p1.replace(IC, IC + ' ' + IC)):
            with self.subTest(copies='none' if IC not in page1 else 'two'):
                d = offer_parse.diagnose(p1, page1, layout(), [page1])
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('ic_not_plain', 'identity_disagree', 'second_ic', 'ic_printed'))

    def test_a_matric_or_reference_is_never_the_ic(self):
        for matric in (IC, NRIC, 'A26A123', '1234567'):
            with self.subTest(matric=matric):
                d = run(layout(matric_row=' ' * 90 + 'NO. MATRIK:      ' + matric))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('no_head', 'second_ic'))
        for ref in ('UMK/PPA/' + IC, 'Rujukan : ' + IC, 'Rujukan : UMK.PPA/100-1/' + IC):
            with self.subTest(ref=ref):
                d = run(layout(extra=(ref,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'second_ic')

    def test_the_ic_guard_runs_as_on_ukm(self):
        """The usual IC guard: the IC AS PRINTED is stored, never the profile's (a profile IC that differs is the
        verdict's mismatch to show, not the reader's to fix); an implausible IC is blanked, and a blank IC on this
        lane refuses (UMK prints the IC: not in ISSUER_PRINTS_NO_IC)."""
        self.assertNotIn(LANE, offer_exact.ISSUER_PRINTS_NO_IC)
        for profile in (NRIC, '880505-10-1234', '990102-14-5678', ''):
            with self.subTest(profile=profile):
                ex = exact(profile=profile)
                self.assertIsNotNone(ex)
                self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric'],
                                  ex['fields']['candidate_nric_source']), (LANE, NRIC, 'label'))
                self.assertFalse(ex['offer_reader_inputs'].get('nric_not_printed'))
        lay = layout(ic_row=' ' * 80 + 'NO. KAD PENGENALAN:200102145678')             # six years old
        why_ = {}
        self.assertIsNone(exact(lay, why_=why_))
        self.assertEqual(why_, {'lane': LANE, 'reason': 'read_nric_guard'})


class UmkNeverLocksTest(SimpleTestCase):
    def test_a_wrapped_name_never_locks_cut_short(self):
        """The line after the name must prove it ended (a digit, a comma or an address word opens it). NO'MAN and
        NO-MAN are a name's rest, not the address word NO; a lone place word may be a name's rest too."""
        for name in ("ZORBEX QUENTARO\nNO'MAN", 'ZORBEX QUENTARO\nNO-MAN', 'ZORBEX QUENTARO\nPINANG',
                     'ZORBEX\nQUENTARO BIN ALFEN'):
            with self.subTest(name=name):
                d = run(layout(name=name))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_not_ended', 'name_shape', 'no_head'))
        for name in ('ZORBEX QUENTARO BIN\nALFEN', 'ZORBEX QUENTARO A/L\nALFEN', "ZORBEX QUENTARO BINTI\nNO'MAN"):
            with self.subTest(name=name):
                d = run(layout(name=name))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_not_ended', 'name_shape'))
        for addr in ('KAMPUNG MAWAR', 'B-1-12 TAMAN MAWAR', 'NO 9 ,', 'LOT 99 LORONG 1', 'AB12,JALAN C'):
            with self.subTest(addr=addr):
                d = run(layout(address=(addr, '16100 KOTA BHARU')))
                self.assertEqual(d['locked']['candidate_name'], NAME, why(d))

    def test_name_must_be_read_exactly(self):
        for name in ('Z9RBEX QUENTARO', 'Zorbex Quentaro Bin Alfen', NAME + '   ' + IC, ' ' * 14 + NAME):
            with self.subTest(name=name.strip()[:6]):
                d = run(layout(name=name))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_shape', 'no_head', 'second_ic'))

    def test_a_head_sharing_lines_with_the_right_column_refuses(self):
        lay = layout().replace(ADDRESS[1] + '\n' + IC_ROW, ADDRESS[1] + IC_ROW[len(ADDRESS[1]):])
        self.assertEqual(run(lay)['guard'], 'no_head')

    def test_unknown_layouts_refuse(self):
        self.assertEqual(read_umk(layout(title=('TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA KELANTAN',)))[1],
                         'no_title')
        self.assertEqual(read_umk(layout(title=('OFFER OF ADMISSION',)))[1], 'no_title')
        self.assertIsNone(run(layout(title=('OFFER OF ADMISSION',)))['locked'])
        self.assertEqual(run(layout(extra=(TITLE[0],)))['guard'], 'no_title')                 # the title twice
        self.assertEqual(run(layout(letterhead=LETTERHEAD[1:]))['guard'], 'no_head')
        self.assertEqual(run(layout(letterhead=(LETTERHEAD[1], LETTERHEAD[0]) + LETTERHEAD[2:]))['guard'], 'no_head')
        self.assertEqual(run(layout(matric_row=DATED_ROW, dated_row=MATRIC_ROW))['guard'], 'no_head')
        self.assertEqual(run(layout(dated_row=' ' * 95 + 'TARIKH: 31/09/2026'))['guard'], 'no_head')
        self.assertEqual(run(layout(dated_row=' ' * 95 + 'TARIKH: 20 Julai 2026'))['guard'], 'no_head')
        self.assertEqual(run(layout(salutation='Tuan/Puan,'))['guard'], 'no_head')
        self.assertIn(run(layout(address=()))['guard'], ('no_head', 'name_not_ended'))
        self.assertEqual(run(layout(address=ADDRESS * 3))['guard'], 'no_head')
        self.assertEqual(run(layout(greeting=('Selamat datang ke UMK.',)))['guard'], 'no_table')
        self.assertEqual(run(layout(register='Sila hadir mendaftar seperti berikut:-'))['guard'], 'reporting_shape')
        self.assertEqual(run(layout(report=(REPORT[1], REPORT[0]) + REPORT[2:]))['guard'], 'reporting_shape')
        self.assertEqual(run(layout(report=REPORT[:1] + REPORT[2:]))['guard'], 'reporting_shape')

    def test_reporting_date_read_only_when_labelled(self):
        """A labelled "Tarikh" row with an English month abbreviation straight after the registration sentence is
        the only reporting date read; any other shape, or none (one owner letter breaks page 1 after Tempoh),
        refuses: never guessed."""
        for value in ('31 SEP 2026', '13 September 2026', '13 SEPT 2026', '13/09/2026', '13 Sep 2026',
                      '13 SEP 2026 (AHAD)', 'AKAN DIMAKLUMKAN', '13 SEP 26', '13 SEP 2026 dan 14 SEP 2026'):
            with self.subTest(value=value):
                d = run(layout(report=('Tarikh : ' + value,) + REPORT[1:]))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('reporting_shape', 'not_an_offer', 'stray_date'))
        broken = layout(register='', report=(), notes=('MUSTAHAK',)).replace('\n\n', '\n')
        d = run(broken)
        self.assertIsNone(d['locked'])
        self.assertEqual(d['guard'], 'reporting_shape')                                     # absent: never guessed
        self.assertEqual(read_umk(broken)[0]['reporting_date'], '')

    def test_a_date_elsewhere_is_never_taken(self):
        for note in ('Pendaftaran pada 12 September 2026 di Dewan Utama.', 'Sila hadir pada 12/09/2026.',
                     'Tarikh Cetak : 17/07/2026', 'Hadir pada 12 SEP 2026.', 'Bayaran sebelum 1 Ogo. 2026'):
            with self.subTest(note=note):
                d = run(layout(extra=(note,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'stray_date')

    def test_dates_and_session(self):
        self.assertEqual(run(layout(dated_row=' ' * 95 + 'TARIKH: 20/07/2028'))['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(dated_row=' ' * 95 + 'TARIKH: 20/10/2026'))['guard'], 'dates_not_sane')
        self.assertIsNotNone(run(layout(dated_row=' ' * 95 + 'TARIKH: 20/12/2025'))['locked'])  # the year before
        late = layout(report=('Tarikh : 13 SEP 2027',) + REPORT[1:])
        self.assertIsNotNone(run(late)['locked'])                                   # the session's second year
        later = layout(report=('Tarikh : 13 SEP 2028',) + REPORT[1:])
        self.assertEqual(run(later)['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(title=(TITLE[0], '2026/2028')))['guard'], 'dates_not_sane')

    def test_placeholder_refuses(self):
        self.assertEqual(run(layout(extra=('Kampus {kampus}',)))['guard'], 'placeholder')

    def test_a_portal_page_refuses_with_no_excuse(self):
        self.assertFalse(run()['portal'])
        d = run(layout(extra=('Sila semak di Portal Semakan Kemasukan.',)))
        self.assertTrue(d['portal'])
        self.assertIsNone(d['locked'])

    def test_missing_owner_words_go_to_ai(self):
        self.assertEqual(run(layout(notes=NOTES[:3] + NOTES[4:]))['guard'], 'owner_words_missing')
        self.assertEqual(run(layout(notes=NOTES[:2] + NOTES[3:]))['guard'], 'owner_words_missing')

    def test_any_later_page_goes_to_ai_with_no_excuse(self):
        """Owner decision 26 Nov: no blank-page, later-page or conditions-page excuse."""
        self.assertEqual(umk_later_pages(['MUSTAHAK']), 'later_page')
        self.assertEqual(umk_later_pages(['', '  ']), '')
        self.assertEqual(run(page2='Sekian, terima kasih.\nTimbalan Pendaftar')['guard'], 'later_page')

    def test_a_page_that_draws_no_text_refuses(self):
        self.assertEqual(run(page2='')['guard'], 'hidden_page')


class UmkWiringTest(SimpleTestCase):
    def test_ink_targets_hold_the_ic_and_date_as_printed(self):
        phrases, values = umk_ink_targets(run()['locked'], layout())
        self.assertEqual(len(phrases), 10)
        got = dict(values)
        self.assertEqual((got['v:name'], got['v:nric'], got['v:intake']), (NAME, IC, INTAKE))
        self.assertEqual((got['v:date'], got['v:offer_date'], got['v:programme']), (REPORT_ON, OFFER_ON, PROGRAMME))
        self.assertFalse(any(MATRIC in v for v in got.values()))
        self.assertEqual(set(read_umk(layout())[0]), set(INK_LABELS) | set(NOT_PRINTED))
        self.assertTrue(set(INK_OPTIONAL) <= set(INK_LABELS))

    def test_family_and_lane_modules(self):
        text = plain(layout())
        self.assertEqual(offer_parse.family_of(text), 'umk')
        self.assertEqual(offer_exact._rules_family(text), 'umk')
        self.assertEqual(offer_exact._lane_module('umk').LANE, 'ua:UMK')
        why_ = {}
        offer_exact._note_ums_refusal(why_, text, 'no_layout')
        self.assertEqual(why_, {'lane': 'ua:UMK', 'reason': 'read_no_layout'})
        from apps.scholarship.eval.offer_read_check import RULES_LANES
        self.assertEqual(RULES_LANES['universiti malaysia kelantan'], 'ua:UMK')

    def test_family_of_claims_only_umk_letters(self):
        for other in ('UNIVERSITI MALAYSIA KELANTAN\nSURAT AKUAN', 'UNIVERSITI MALAYSIA SABAH\nTAWARAN KEMASUKAN',
                      'UNIVERSITI MALAYSIA KELANTAN\nTAWARAN KEMASUKAN PROGRAM DIPLOMA'):
            with self.subTest(other=other.splitlines()[1]):
                self.assertNotEqual(offer_parse.family_of(other), 'umk')
        self.assertFalse(is_umk('UNIVERSITI MALAYSIA KELANTAN PUSAT PENGURUSAN AKADEMIK'))

    def test_not_inked_dispatches_to_umk(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), 'ua:UMK'), [])
            self.assertEqual(ink.call_args.kwargs['lane'], 'ua:UMK')

    @override_settings(OCR_FIRST_LANES=[])
    def test_lane_off_by_default(self):
        text = plain(layout())
        why_ = {}
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(text, text)):
            self.assertIsNone(offer_exact.exact_offer_read(text, image=b'%PDF', content_type='application/pdf',
                                                           why=why_))
        self.assertEqual(why_, {'lane': 'ua:UMK', 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=['ua:UMK'])
    def test_lane_on_reads_the_layout(self):
        lay = layout()
        p1 = plain(lay)
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(p1, p1)), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_page1_layout', return_value=lay), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_rules_page_texts', return_value=[p1]), \
                mock.patch.object(offer_exact, '_not_inked', return_value=[]):
            ex = offer_exact.exact_offer_read(p1, image=b'%PDF', content_type='application/pdf', profile_nric=NRIC)
        self.assertIsNotNone(ex)
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), ('ua:UMK', NRIC))
