"""OCR-14 phase 5: the UTeM rules lane (`offer_parse_utem`). UTeM PRINTS the IC but with NO label, on the line after
the head's date, so it is read from that fixed place and stored with source 'other': CORROBORATE-ONLY under the usual
IC guard (`offer_exact.exact_read`; UTeM is NOT in `offer_exact.ISSUER_PRINTS_NO_IC`), kept only when it is exactly
the profile IC. Any other IC-like number refuses; the matric number, e-mail and reference are never stored; the
reporting date is read only from its labelled row, never guessed. Synthetic letters only (made-up names, numbers and
addresses)."""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_parse_utem import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, is_utem, read_utem
from apps.scholarship.offer_parse_utem import utem_ic_elsewhere, utem_ink_targets, utem_later_pages
from apps.scholarship.offer_parse_utem import utem_letter_refusal

NAME = 'ZORBEX QUENTARO BIN ALFEN'
IC = '990101145678'
NRIC = '990101-14-5678'
MATRIC = 'B012345678'
REF = 'UTeM.52.01.04/100-2/3/4'
PROGRAMME = 'SARJANA MUDA KEJURUTERAAN ELEKTRIK DENGAN KEPUJIAN'
INTAKE = 'SEMESTER I SESI AKADEMIK 2027/2028'
OFFER_ON = '15 Julai 2027'
REPORT_ON = '13 September 2027'                 # a Monday (Isnin)
RIGHT = ' ' * 69


def head(ref=REF, dated=OFFER_ON):
    return (' ' * 54 + 'PEJABAT PENDAFTAR', ' ' * 47 + 'Tel : +606 270 1000 | Faks : +606 270 1001',
            RIGHT + 'Rujukan Kami (Our Ref)' + ' ' * 10 + ':  ' + ref, RIGHT + 'Rujukan Tuan (Your Ref)' + ' ' * 9 + ':',
            RIGHT + 'Tarikh (Date)' + ' ' * 19 + ':  ' + dated)


HEAD = head()
ADDRESS = ('NO 12, JALAN MAWAR 3', 'TAMAN BUNGA', '75450 AYER KEROH', 'MELAKA')
TITLE = 'TAWARAN KEMASUKAN KE UNIVERSITI TEKNIKAL MALAYSIA MELAKA ' + INTAKE
GREETING = ('Tahniah, sukacita dimaklumkan bahawa anda telah ditawarkan tempat bagi mengikuti Program Pengajian seperti '
            'berikut : -',)
REGISTER = 'Sila datang mendaftar di : -'
REPORT_ROW = REPORT_ON + ' (Isnin)' + ' ' * 40 + 'Masa :  8.00 pagi- 12.00 tgh'
ROWS = (('Program Pengajian', PROGRAMME), ('Tahun', 'Satu (1)'), ('Mod Pengajian', 'SEPENUH MASA'),
        ('Fakulti', 'FAKULTI KEJURUTERAAN ELEKTRIK (FKE)'), (None, REGISTER),
        ('Tempat', 'DEWAN CANSELOR, UTeM Kampus Induk'), ('Tarikh', REPORT_ROW), ('Bayaran', 'RM 1,234.50'),
        ('Kemudahan Kolej Kediaman', 'Disediakan'), ('No. Matrik', MATRIC + ' ' * 50 + 'No. MHS  :  123'),
        ('E-mel Rasmi Pelajar', MATRIC + '@student.utem.edu.my' + ' ' * 30 + 'Kata Laluan Emel  :  1234@Abc'))
NOTE = 'Tawaran akan ditarik balik sekiranya UTeM mendapati maklumat yang anda beri tidak benar.'
BODY = ('Anda akan mengikut Program Pengajian Kejuruteraan selama Empat (4) tahun.',
        'Berikut merupakan maklumat kos pengajian yang berkaitan dengan anda :',
        ' ' * 10 + 'PROGRAM' + ' ' * 20 + 'TEMPOH' + ' ' * 20 + 'DITANGGUNG' + ' ' * 10 + 'KESELURUHAN',
        ' ' * 9 + 'KEJURUTERAAN' + ' ' * 12 + 'EMPAT (4) TAHUN' + ' ' * 12 + '10,000.00' + ' ' * 12 + '20,000.00',
        'PENTING :',
        ' ' * 7 + '1.     Anda dikehendaki mematuhi syarat-syarat tawaran seperti yang terdapat di halaman belakang.',
        ' ' * 7 + '2.     ' + NOTE,
        'Sekian, terima kasih.', 'Yang Benar,', 'QARIM VELTO BIN DURAN')
FOOTER = ('Bahagian Pengurusan Akademik', 'Pejabat Pendaftar', 'Universiti Teknikal Malaysia Melaka',
          '(Surat tawaran ini cetakan komputer, tanda tangan tidak diperlukan)')


def row(name, value):
    return value if name is None else name + ' ' * (26 - len(name)) + ': ' + value


def rows_with(name, value):
    return tuple((n, value if n == name else v) for n, v in ROWS)


def layout(name_line=NAME, head=HEAD, ic_line=IC, address=ADDRESS, salutation='Saudara/i', title=TITLE,
           greeting=GREETING, rows=ROWS, body=BODY, extra=(), footer=FOOTER):
    lines = [*head, ic_line, name_line, *address, salutation, title, *greeting, *(row(n, v) for n, v in rows), *body,
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


def exact(lay=None, profile=NRIC, why_=None):
    lay = lay if lay is not None else layout()
    p1 = plain(lay)
    return offer_exact.exact_read(p1, from_text_layer=True, page1_layer=p1, page1_layout=lay, page_texts=[p1],
                                  profile_nric=profile, why=why_)


class UtemLockTest(SimpleTestCase):
    def test_degree_letter_locks_with_its_ic_and_labelled_reporting_date(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane'], lock['_family']), ('utem', LANE, 'utem'))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), (NRIC, 'other'))
        self.assertEqual((lock['programme'], lock['programme_code']), (PROGRAMME, ''))
        self.assertEqual(lock['intake'], INTAKE)
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('13 Sep 2027', 'Tarikh'))
        self.assertEqual((lock['reporting_venue'], lock['campus'], lock['stream']), ('', '', ''))
        self.assertEqual(lock['offer_date'], OFFER_ON)
        self.assertEqual(lock['institution'], 'UNIVERSITI TEKNIKAL MALAYSIA MELAKA')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_value_shapes_that_still_lock(self):
        for name, value in (('Program Pengajian', 'IJAZAH ' + PROGRAMME), ('Bayaran', 'RM1,234.50'),
                            ('Kemudahan Kolej Kediaman', 'Tidak Disediakan'),
                            ('Tarikh', REPORT_ON + ' (Isnin) Masa : 2.00 petang - 5.00 petang')):
            with self.subTest(name=name, value=value):
                d = run(layout(rows=rows_with(name, value)))
                self.assertIsNotNone(d['locked'], why(d))
                self.assertEqual(d['locked']['candidate_nric'], NRIC)

    def test_a_wrapped_programme_is_joined_under_its_value(self):
        wrapped = layout().replace(row('Program Pengajian', PROGRAMME),
                                   row('Program Pengajian', 'SARJANA MUDA KEJURUTERAAN') + '\n' + ' ' * 28
                                   + 'ELEKTRIK DENGAN KEPUJIAN')
        d = run(wrapped)
        self.assertIsNotNone(d['locked'], why(d))
        self.assertEqual(d['locked']['programme'], PROGRAMME)
        three = layout().replace(row('Program Pengajian', PROGRAMME),
                                 row('Program Pengajian', 'SARJANA MUDA') + '\n' + ' ' * 28 + 'KEJURUTERAAN'
                                 + '\n' + ' ' * 28 + 'ELEKTRIK' + '\n' + ' ' * 28 + 'DENGAN KEPUJIAN')
        self.assertEqual(run(three)['guard'], 'programme_shape')
        column = layout().replace(row('Program Pengajian', PROGRAMME),
                                  row('Program Pengajian', 'SARJANA MUDA KEJURUTERAAN') + '\n' + ' ' * 28
                                  + 'ELEKTRIK' + ' ' * 20 + 'DENGAN KEPUJIAN')
        self.assertEqual(run(column)['guard'], 'programme_shape')

    def test_matric_email_and_reference_are_never_stored(self):
        lock = run()['locked']
        self.assertFalse(any(MATRIC in str(v) for v in lock.values()))
        self.assertFalse(any('UTeM.52' in str(v) for v in lock.values()))
        self.assertFalse(any('@' in str(v) for v in lock.values()))

    def test_a_scan_refuses_no_layout(self):
        d = offer_parse.diagnose(plain(layout()), '', '', None)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('utem', 'no_layout', None))


class UtemIcTest(SimpleTestCase):
    def test_ic_shapes_refuse(self):
        """The IC line must be the 12 plain digits alone at the left: a hyphen, an en dash, a minus, a slash, a space,
        a whitespace run, a short or long run, a label or a line split refuses."""
        for ic in (NRIC, '990101 14 5678', '990101–14–5678', '990101−14−5678', '990101/14/5678',
                   '990101   14   5678', '990101\t14\t5678', '99010114567', '9901011456789', 'No. K/P : ' + IC,
                   ' ' * 20 + IC, '990101\n145678', '990101-14-\n5678'):
            with self.subTest(ic=ic):
                d = run(layout(ic_line=ic))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('ic_shape', 'second_ic'))
        d = run(layout(ic_line=''))                     # no IC line at all: the name is read where the IC stands
        self.assertIsNone(d['locked'])

    def test_a_second_ic_anywhere_refuses(self):
        from apps.scholarship.tests.test_offer_parse_uum import IC_SHAPES
        for ic in IC_SHAPES + ('990102145678', '990102-14-5678', NRIC, IC):
            with self.subTest(ic=ic):
                lay = layout(extra=('No. K/P waris :' + ' ' * 10 + ic,))
                self.assertIsNone(run(lay)['locked'])
                self.assertEqual(read_utem(lay)[1], 'second_ic')
                self.assertEqual(utem_letter_refusal(plain(layout()) + '\nWaris ' + ic, NRIC), 'second_ic')
                self.assertIn(run(page2='Universiti Teknikal Malaysia Melaka\nNo. K/P : ' + ic)['guard'],
                              ('second_ic', 'ic_printed'))
                p1 = plain(layout())
                d = offer_parse.diagnose(p1, p1 + '\nWaris ' + ic, layout(), [p1])
                self.assertIsNone(d['locked'])
        self.assertEqual(utem_letter_refusal(plain(layout()), NRIC), '')
        self.assertFalse(utem_ic_elsewhere(plain(layout()), NRIC))
        self.assertTrue(utem_ic_elsewhere(plain(layout()), '990102-14-5678'))     # a different IC read: the page's counts

    def test_the_read_ic_must_stand_in_the_plain_layer(self):
        p1 = plain(layout())
        for page1 in (p1.replace(IC, ''), p1.replace(IC, IC + ' ' + IC)):
            with self.subTest(copies='none' if IC not in page1 else 'two'):
                d = offer_parse.diagnose(p1, page1, layout(), [page1])
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('ic_not_plain', 'identity_disagree', 'second_ic', 'ic_printed'))

    def test_a_matric_or_reference_is_never_the_ic(self):
        for matric in ('990101145678', 'B990101145678', '990101-14-5678'):
            with self.subTest(matric=matric):
                d = run(layout(rows=rows_with('No. Matrik', matric + ' ' * 50 + 'No. MHS  :  123')))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('table_shape', 'second_ic'))
        for ref in ('990101145678', 'UTeM.990101145678', 'UTeM.52.01.04/100-990101145678'):
            with self.subTest(ref=ref):
                d = run(layout(head=head(ref=ref)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('no_head', 'second_ic'))

    def test_the_ic_is_corroborate_only(self):
        """No label names the IC, so it is source 'other': the usual IC guard (`offer_ic.guard_nric`) keeps it only
        when it is EXACTLY the profile IC; a different or blank profile IC blanks it, and a blank IC on this lane
        refuses (UTeM prints the IC: not in ISSUER_PRINTS_NO_IC)."""
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


class UtemNeverLocksTest(SimpleTestCase):
    def test_a_wrapped_name_never_locks_cut_short(self):
        """The line after the name must prove it ended (a digit, a comma or an address word opens it). NO'MAN and
        NO-MAN are a name's rest, not the address word NO; a lone place word may be a name's rest too."""
        for first, rest in (('ZORBEX QUENTARO', 'BIN ALFEN'), ('ZORBEX QUENTARO BIN', 'ALFEN'), ('ZORBEX', 'QUENTARO'),
                            ('ZORBEX QUENTARO', "NO'MAN"), ('ZORBEX QUENTARO', 'NO-MAN'), ('ZORBEX QUENTARO', 'MELAKA'),
                            ('ZORBEX QUENTARO A/L', 'ALFEN'), ('ZORBEX QUENTARO BINTI', "NO'MAN")):
            with self.subTest(first=first, rest=rest):
                d = run(layout(name_line=first + '\n' + rest))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_not_ended', 'name_shape'))
        for addr in ('KAMPUNG MAWAR', 'B-1-12 TAMAN MAWAR', 'NO 9 ,', 'LOT 99 LORONG 1'):
            with self.subTest(addr=addr):
                d = run(layout(address=(addr, '75450 AYER KEROH')))
                self.assertEqual(d['locked']['candidate_name'], NAME, why(d))

    def test_name_must_be_read_exactly(self):
        for name_line in ('Z9RBEX QUENTARO', NAME + '   EXTRA', ' ' * 14 + NAME, 'Zorbex Quentaro Bin Alfen'):
            with self.subTest(name_line=name_line):
                d = run(layout(name_line=name_line))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_shape', 'no_head'))

    def test_diploma_asasi_and_non_degree_refuse(self):
        for prog in ('DIPLOMA KEJURUTERAAN ELEKTRIK', 'ASASI KEJURUTERAAN', 'SARJANA KEJURUTERAAN DENGAN KEPUJIAN',
                     'SARJANA MUDA KEJURUTERAAN', 'SARJANA MUDA DIPLOMA LANJUTAN DENGAN KEPUJIAN',
                     PROGRAMME + ' X'):
            with self.subTest(prog=prog):
                d = run(layout(rows=rows_with('Program Pengajian', prog)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('programme_shape', 'not_degree', 'asasi_ai_read'))
        for name, value in (('Fakulti', 'SEKOLAH ASASI TEKNIKAL DAN PENGAJIAN DIPLOMA'),
                            ('Fakulti', 'FAKULTI DIPLOMA KEJURUTERAAN'), ('Fakulti', 'FAKULTI ASASI SAINS'),
                            ('Tahun', 'Dua (2)'), ('Tahun', '1 (Satu)'), ('Mod Pengajian', 'SEPARUH MASA')):
            with self.subTest(name=name, value=value):
                d = run(layout(rows=rows_with(name, value)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('not_degree', 'programme_shape', 'table_shape', 'asasi_ai_read'))
        for line in ('Program Diploma Kejuruteraan', 'Pelajar Asasi Sains', 'Program Sarjana Muda Teknologi'):
            with self.subTest(line=line):
                self.assertIn(run(layout(extra=(line,)))['guard'], ('not_degree', 'asasi_ai_read'))

    def test_the_diploma_and_second_degree_templates_refuse(self):
        """The diploma letters' title ("SESI YYYY/YYYY") and the second degree template's ("SEMESTER I SESI
        YYYY/YYYY") are not this reader's: no title, no lock."""
        for title in ('TAWARAN KEMASUKAN KE UNIVERSITI TEKNIKAL MALAYSIA MELAKA SESI 2027/2028',
                      'TAWARAN KEMASUKAN KE UNIVERSITI TEKNIKAL MALAYSIA MELAKA SEMESTER I SESI 2027/2028',
                      'TAWARAN KEMASUKAN KE UNIVERSITI TEKNIKAL MALAYSIA MELAKA SEMESTER II SESI AKADEMIK 2027/2028'):
            with self.subTest(title=title):
                self.assertEqual(read_utem(layout(title=title)), (None, 'no_title'))
                self.assertIsNone(run(layout(title=title))['locked'])

    def test_confirmation_and_fail_letters_refuse(self):
        confirm = '\n'.join(('KEPADA SESIAPA YANG BERKENAAN', 'NAMA : ' + NAME, 'NO. KP : ' + IC,
                             'Dengan ini disahkan bahawa penama di atas adalah pelajar tahun pertama',
                             'UNIVERSITI TEKNIKAL MALAYSIA MELAKA', 'PEJABAT PENDAFTAR'))
        self.assertEqual(read_utem(confirm), (None, 'no_title'))
        self.assertIsNone(run(confirm)['locked'])
        self.assertEqual(run(layout(extra=('SURAT PENGESAHAN',)))['guard'], 'status_letter')
        for line in ('Permohonan saudara/i TIDAK BERJAYA.', 'Tawaran ini telah DIBATALKAN.',
                     'Tawaran ini telah ditarik balik.', 'Tawaran akan ditarik balik sekiranya anda tidak mendaftar.'):
            with self.subTest(line=line):
                d = run(layout(extra=(line,)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('status_letter', 'not_an_offer'))

    def test_the_note_excuse_is_one_exact_sentence_once(self):
        """Every genuine UTeM letter prints the conditional "Tawaran akan ditarik balik sekiranya UTeM mendapati
        maklumat yang anda beri tidak benar." in its notes; only that sentence, once, is taken out before the
        withdrawal check."""
        self.assertEqual(utem_letter_refusal(plain(layout()), NRIC), '')
        self.assertEqual(utem_letter_refusal(plain(layout(extra=(NOTE,))), NRIC), 'not_an_offer')
        self.assertEqual(run(layout(extra=(NOTE,)))['guard'], 'not_an_offer')
        for other in (NOTE.replace('tidak benar', 'palsu'), NOTE.replace('UTeM', 'universiti'),
                      'Tawaran ini ditarik balik.'):
            with self.subTest(other=other):
                lay = layout().replace(NOTE, other)
                self.assertEqual(utem_letter_refusal(plain(lay), NRIC), 'not_an_offer')
                self.assertIsNone(run(lay)['locked'])

    def test_unknown_layouts_refuse(self):
        self.assertEqual(read_utem(layout(title='TAWARAN KEMASUKAN KE UNIVERSITI TEKNIKAL MALAYSIA MELAKA')),
                         (None, 'no_title'))
        self.assertEqual(run(layout(title='OFFER OF ADMISSION'))['guard'], 'no_title')
        self.assertEqual(run(layout(extra=(TITLE,)))['guard'], 'no_title')                       # the title twice
        self.assertEqual(run(layout(head=(HEAD[1], HEAD[0]) + HEAD[2:]))['guard'], 'no_head')
        self.assertEqual(run(layout(head=HEAD[:4]))['guard'], 'no_head')
        self.assertEqual(run(layout(head=head(dated='31 September 2027')))['guard'], 'no_head')
        self.assertEqual(run(layout(head=HEAD[:3] + (RIGHT + 'Rujukan Tuan (Your Ref)  :  ABC/1',) + HEAD[4:]))['guard'],
                         'no_head')
        self.assertEqual(run(layout(address=()))['guard'], 'no_head')
        self.assertEqual(run(layout(address=ADDRESS * 2))['guard'], 'no_head')
        self.assertEqual(run(layout(salutation='Tuan/Puan'))['guard'], 'no_head')
        self.assertEqual(run(layout(rows=(ROWS[1], ROWS[0]) + ROWS[2:]))['guard'], 'no_table')
        self.assertEqual(run(layout(rows=ROWS[:1] + (ROWS[2], ROWS[1]) + ROWS[3:]))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=ROWS[:-1]))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=ROWS[:4] + ROWS[5:]))['guard'], 'table_shape')          # no register line
        self.assertEqual(run(layout(rows=ROWS + (('Catatan', 'Tiada'),)))['guard'], 'table_shape')
        no_greeting = layout(greeting=('Selamat datang ke UTeM.',))
        self.assertIsNone(run(no_greeting)['locked'])
        self.assertEqual(read_utem(no_greeting)[1], 'no_table')
        self.assertFalse(is_utem('UNIVERSITI TEKNIKAL MALAYSIA MELAKA BAHAGIAN PENGURUSAN AKADEMIK'))
        self.assertFalse(is_utem('UNIVERSITI TUN HUSSEIN ONN MALAYSIA PEJABAT PENDAFTAR'))

    def test_reporting_date_read_only_when_labelled(self):
        for value in ('', REPORT_ON, REPORT_ON + ' (Selasa)' + ' ' * 40 + 'Masa :  8.00 pagi- 12.00 tgh',
                      REPORT_ON + ' (Isnin)', '31 September 2027 (Isnin) Masa : 8.00 pagi - 12.00 tgh',
                      'AKAN DIMAKLUMKAN', '13/09/2027 (Isnin) Masa : 8.00 pagi - 12.00 tgh',
                      REPORT_ON + ' (Isnin) dan 14 September 2027 (Selasa)'):
            with self.subTest(value=value):
                d = run(layout(rows=rows_with('Tarikh', value)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('reporting_shape', 'table_shape'))
        no_row = tuple(r for r in ROWS if r[0] != 'Tarikh')
        self.assertEqual(run(layout(rows=no_row))['guard'], 'table_shape')                       # absent: never guessed

    def test_a_date_in_a_venue_or_note_is_never_taken(self):
        venue = 'DEWAN CANSELOR mulai 12 September 2027'
        self.assertEqual(run(layout(rows=rows_with('Tempat', venue)))['guard'], 'stray_date')
        for note in ('Pendaftaran pada 12 September 2027 di Dewan Canselor.', 'Sila hadir pada 12/09/2027.',
                     'Tarikh Cetak : 17/07/2027'):
            with self.subTest(note=note):
                d = run(layout(extra=(note,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'stray_date')

    def test_dates_and_session(self):
        self.assertEqual(run(layout(head=head(dated='15 Julai 2030')))['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(head=head(dated='15 Oktober 2027')))['guard'], 'dates_not_sane')
        late = rows_with('Tarikh', '11 September 2028 (Isnin) Masa : 8.00 pagi - 12.00 tgh')
        self.assertIsNotNone(run(layout(rows=late))['locked'])                       # the session's second year
        later = rows_with('Tarikh', '10 September 2029 (Isnin) Masa : 8.00 pagi - 12.00 tgh')
        self.assertEqual(run(layout(rows=later))['guard'], 'dates_not_sane')
        odd = layout(title='TAWARAN KEMASUKAN KE UNIVERSITI TEKNIKAL MALAYSIA MELAKA SEMESTER I SESI AKADEMIK 2027/2029')
        self.assertEqual(run(odd)['guard'], 'dates_not_sane')

    def test_placeholder_refuses(self):
        self.assertEqual(run(layout(extra=('Tarikh tutup {tarikh_tutup}',)))['guard'], 'placeholder')

    def test_a_portal_page_refuses_with_no_excuse(self):
        self.assertFalse(run()['portal'])
        d = run(layout(extra=('Sila semak di Portal Semakan Kemasukan.',)))
        self.assertTrue(d['portal'])
        self.assertIsNone(d['locked'])

    def test_missing_owner_words_go_to_ai(self):
        lay = layout(footer=FOOTER[1:])
        self.assertEqual(run(lay)['guard'], 'owner_words_missing')

    def test_any_later_page_goes_to_ai(self):
        self.assertEqual(utem_later_pages(['SYARAT-SYARAT TAWARAN KEMASUKAN']), 'later_page')
        self.assertEqual(utem_later_pages(['', '  ']), '')
        self.assertEqual(run(page2='SYARAT-SYARAT TAWARAN KEMASUKAN\n1. Syarat am.')['guard'], 'later_page')

    def test_a_page_that_draws_no_text_refuses(self):
        """No excuse for a blank page: a hidden or scanned page may hold a withdrawal, a status or a second offer
        (`offer_ums_refusal.page_texts_refusal`)."""
        self.assertEqual(run(page2='')['guard'], 'hidden_page')
        lay = layout()
        p1 = plain(lay)
        d = offer_parse.diagnose(p1, p1, lay, [p1, 'SYARAT-SYARAT TAWARAN KEMASUKAN', ''])
        self.assertEqual(d['guard'], 'hidden_page')


class UtemWiringTest(SimpleTestCase):
    def test_ink_targets_hold_the_ic_and_date_as_printed(self):
        phrases, values = utem_ink_targets(run()['locked'], layout())
        self.assertEqual(len(phrases), 7)
        got = dict(values)
        self.assertEqual((got['v:name'], got['v:nric'], got['v:intake']), (NAME, IC, INTAKE))
        self.assertEqual((got['v:date'], got['v:offer_date'], got['v:programme']), (REPORT_ON, OFFER_ON, PROGRAMME))
        self.assertFalse(any(MATRIC in v for v in got.values()))
        self.assertEqual(set(read_utem(layout())[0]), set(INK_LABELS) | set(NOT_PRINTED))
        self.assertTrue(set(INK_OPTIONAL) <= set(INK_LABELS))

    def test_family_and_lane_modules(self):
        text = plain(layout())
        self.assertEqual(offer_parse.family_of(text), 'utem')
        self.assertEqual(offer_exact._rules_family(text), 'utem')
        self.assertEqual(offer_exact._lane_module('utem').LANE, 'ua:UTeM')
        why_ = {}
        offer_exact._note_ums_refusal(why_, text, 'no_layout')
        self.assertEqual(why_, {'lane': 'ua:UTeM', 'reason': 'read_no_layout'})
        from apps.scholarship.eval.offer_read_check import RULES_LANES
        self.assertEqual(RULES_LANES['universiti teknikal malaysia melaka'], 'ua:UTeM')

    def test_family_of_claims_only_utem_letters(self):
        for other in ('UNIVERSITI TEKNIKAL MALAYSIA MELAKA\nSURAT AKUAN', 'UNIVERSITI TUN HUSSEIN ONN MALAYSIA\n'
                      'PEJABAT PENDAFTAR', 'UNIVERSITI KEBANGSAAN MALAYSIA\nPEJABAT PENDAFTAR'):
            with self.subTest(other=other.splitlines()[0]):
                self.assertNotEqual(offer_parse.family_of(other), 'utem')

    def test_not_inked_dispatches_to_utem(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), 'ua:UTeM'), [])
            self.assertEqual(ink.call_args.kwargs['lane'], 'ua:UTeM')

    @override_settings(OCR_FIRST_LANES=[])
    def test_lane_off_by_default(self):
        text = plain(layout())
        why_ = {}
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(text, text)):
            self.assertIsNone(offer_exact.exact_offer_read(text, image=b'%PDF', content_type='application/pdf',
                                                           why=why_))
        self.assertEqual(why_, {'lane': 'ua:UTeM', 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=['ua:UTeM'])
    def test_lane_on_reads_the_layout(self):
        lay = layout()
        p1 = plain(lay)
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(p1, p1)), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_page1_layout', return_value=lay), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_rules_page_texts', return_value=[p1]), \
                mock.patch.object(offer_exact, '_not_inked', return_value=[]):
            ex = offer_exact.exact_offer_read(p1, image=b'%PDF', content_type='application/pdf', profile_nric=NRIC)
        self.assertIsNotNone(ex)
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), ('ua:UTeM', NRIC))
