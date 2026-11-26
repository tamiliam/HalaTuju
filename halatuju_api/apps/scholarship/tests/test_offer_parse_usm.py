"""OCR-14 phase 6: the USM rules lane (`offer_parse_usm`). USM PRINTS the IC but with NO label, in brackets after the
name on the head's third line, so it is read from that fixed place and stored with source 'other': CORROBORATE-ONLY
under the usual IC guard (`offer_exact.exact_read`; USM is NOT in `offer_exact.ISSUER_PRINTS_NO_IC`), kept only when
it is exactly the profile IC. Any other IC-like number refuses; the matric number and the reference are never stored;
the programme is read only from the upper-case table row (its label also sits inside a note); the reporting date is
read only from its labelled row, never guessed. Synthetic letters only (made-up names, numbers and addresses)."""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_parse_usm import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, is_usm, read_usm
from apps.scholarship.offer_parse_usm import usm_ic_elsewhere, usm_ink_targets, usm_later_pages, usm_letter_refusal

NAME = 'ZORBEX QUENTARO BIN ALFEN'
IC = '990101145678'
NRIC = '990101-14-5678'
MATRIC = '12345678'
CODE = 'US6440001'
PROGRAMME = 'SARJANA MUDA KEJURUTERAAN ELEKTRIK DENGAN KEPUJIAN'
INTAKE = 'SIDANG AKADEMIK 2027/2028'
OFFER_ON = '15 JULAI 2027'
REPORT_ON = '13 SEPTEMBER 2027'                 # a Monday (Isnin)
M = '   '                                       # the left margin


def head(ref='12/' + CODE + '/2027', dated=OFFER_ON):
    return (M + 'No.Rujukan : ' + ref, M + 'Tarikh' + ' ' * 10 + ': ' + dated)


HEAD = head()
NAME_LINE = NAME + '  (' + IC + ')'
ADDRESS = ('NO 12, JALAN MAWAR 3', 'TAMAN BUNGA', '11800 GELUGOR', 'PULAU PINANG')
TITLE = ('TAWARAN KEMASUKAN PROGRAM IJAZAH SARJANA MUDA, UNIVERSITI SAINS MALAYSIA (UNIVERSITI BERSTATUS',
         'APEX), SIDANG AKADEMIK 2027/2028')
GREETING = ('Tahniah, saudara/i telah berjaya ditawarkan tempat untuk mengikuti program Ijazah Sarjana Muda (Penuh '
            'Masa) di Universiti Sains', 'Malaysia. Butir-butir lanjut tawaran adalah seperti berikut:')
REPORT_ROW = REPORT_ON + ' (ISNIN) / 8:00 PAGI - 12:00 TENGAH HARI'
ROWS = (('NAMA', NAME), ('NO MATRIK', MATRIC), ('PROGRAM PENGAJIAN', CODE + ' - ' + PROGRAMME),
        ('TEMPOH PENGAJIAN', '4 TAHUN'), ('YURAN PENGAJIAN', 'RM1,234.00 SETAHUN'),
        ('TARIKH LAPOR DIRI/MASA', REPORT_ROW), ('TEMPAT LAPOR DIRI', 'DEWAN UTAMA DESASISWA BAKTI'),
        ('PENGINAPAN', 'DESASISWA BAKTI'))
FEES = (' ' * 16 + 'Yuran Pengajian Setahun' + ' ' * 16 + 'Yuran dibiayai Kerajaan Setahun' + ' ' * 17
        + 'Yuran dibayar Pelajar Setahun', ' ' * 22 + 'RM 12,345.00' + ' ' * 31 + 'RM 11,111.00' + ' ' * 35
        + 'RM 1,234.00')
NOTE = ('Pihak universiti berhak menarik balik tawaran ini sekiranya terdapat keraguan terhadap keterangan atau '
        'salinan sijil-sijil yang dikemukakan oleh saudara/i semasa permohonan.')
NOTES = (M + '1.    Pihak universiti berhak menarik balik tawaran ini sekiranya terdapat keraguan terhadap keterangan '
         'atau salinan sijil-sijil yang', M + 'dikemukakan oleh saudara/i semasa permohonan.',
         M + '2.   Program pengajian yang ditawarkan kepada saudara/i ini adalah muktamad. Tahniah di atas kejayaan '
         'saudara/i dan selamat', M + 'datang ke Universiti Sains Malaysia.')
FOOTER = ('Sekian, terima kasih.', '“MALAYSIA MADANI”', '“BERKHIDMAT UNTUK NEGARA”',
          ' Saya yang menjalankan amanah,', ' QARIM VELTO BIN DURAN', ' Pendaftar')


def row(name, value):
    return ' ' * 22 + name + ' ' * (33 - len(name)) + ': ' + value


def rows_with(name, value):
    return tuple((n, value if n == name else v) for n, v in ROWS)


def layout(name_line=NAME_LINE, head=HEAD, address=ADDRESS, title=TITLE, greeting=GREETING, rows=ROWS, fees=FEES,
           notes=NOTES, extra=(), footer=FOOTER):
    lines = [*head, M + name_line, *(M + a for a in address), *(M + t for t in title), *(M + g for g in greeting),
             *(row(n, v) for n, v in rows), *fees, *notes, *extra, *(M + f for f in footer)]
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


class UsmLockTest(SimpleTestCase):
    def test_degree_letter_locks_with_its_ic_code_and_labelled_reporting_date(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane'], lock['_family']), ('usm', LANE, 'usm'))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), (NRIC, 'other'))
        self.assertEqual((lock['programme'], lock['programme_code']), (PROGRAMME, CODE))
        self.assertEqual(lock['intake'], INTAKE)
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('13 Sep 2027', 'TARIKH LAPOR DIRI/MASA'))
        self.assertEqual((lock['reporting_venue'], lock['campus'], lock['stream']), ('', '', ''))
        self.assertEqual(lock['offer_date'], OFFER_ON)
        self.assertEqual(lock['institution'], 'UNIVERSITI SAINS MALAYSIA')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_value_shapes_that_still_lock(self):
        for name, value in (('TARIKH LAPOR DIRI/MASA', REPORT_ON + ' (ISNIN) / 2:00 PETANG - 5:00 PETANG'),
                            ('PROGRAM PENGAJIAN', CODE + ' - SARJANA MUDA SAINS (KIMIA DAN FIZIK) DENGAN KEPUJIAN'),
                            ('TEMPOH PENGAJIAN', '3 TAHUN'), ('PENGINAPAN', 'TIDAK DISEDIAKAN')):
            with self.subTest(name=name, value=value):
                d = run(layout(rows=rows_with(name, value)))
                self.assertIsNotNone(d['locked'], why(d))
                self.assertEqual(d['locked']['candidate_nric'], NRIC)
        one_line_title = layout(title=(' '.join(TITLE),))
        self.assertIsNotNone(run(one_line_title)['locked'], why(run(one_line_title)))

    def test_a_wrapped_programme_and_venue_are_joined_under_their_values(self):
        wrapped = layout().replace(row('PROGRAM PENGAJIAN', CODE + ' - ' + PROGRAMME),
                                   row('PROGRAM PENGAJIAN', CODE + ' - SARJANA MUDA KEJURUTERAAN ELEKTRIK') + '\n'
                                   + ' ' * 57 + 'DENGAN KEPUJIAN')
        d = run(wrapped)
        self.assertIsNotNone(d['locked'], why(d))
        self.assertEqual(d['locked']['programme'], PROGRAMME)
        venue = layout().replace(row('TEMPAT LAPOR DIRI', 'DEWAN UTAMA DESASISWA BAKTI'),
                                 row('TEMPAT LAPOR DIRI', 'DEWAN UTAMA') + '\n' + ' ' * 57 + 'KAMPUS INDUK, USM'
                                 + '\n' + ' ' * 57 + 'GELUGOR, PULAU PINANG')
        self.assertIsNotNone(run(venue)['locked'], why(run(venue)))
        three = layout().replace(row('PROGRAM PENGAJIAN', CODE + ' - ' + PROGRAMME),
                                 row('PROGRAM PENGAJIAN', CODE + ' - SARJANA MUDA') + '\n' + ' ' * 57 + 'KEJURUTERAAN'
                                 + '\n' + ' ' * 57 + 'ELEKTRIK' + '\n' + ' ' * 57 + 'DENGAN KEPUJIAN')
        self.assertEqual(run(three)['guard'], 'table_shape')
        column = layout().replace(row('PROGRAM PENGAJIAN', CODE + ' - ' + PROGRAMME),
                                  row('PROGRAM PENGAJIAN', CODE + ' - SARJANA MUDA KEJURUTERAAN') + '\n' + ' ' * 57
                                  + 'ELEKTRIK' + ' ' * 20 + 'DENGAN KEPUJIAN')
        self.assertEqual(run(column)['guard'], 'table_shape')

    def test_matric_and_reference_are_never_stored(self):
        lock = run()['locked']
        self.assertFalse(any(MATRIC in str(v) for v in lock.values()))
        self.assertFalse(any('/2027' in str(v) and CODE in str(v) for v in lock.values()))

    def test_a_scan_refuses_no_layout(self):
        d = offer_parse.diagnose(plain(layout()), '', '', None)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('usm', 'no_layout', None))


class UsmProgrammeTest(SimpleTestCase):
    def test_the_programme_label_must_be_the_table_row(self):
        """"PROGRAM PENGAJIAN" also sits inside note 2 ("Program pengajian yang ditawarkan ..."): only the upper-case
        row at its place in the table is read."""
        lower = tuple((n.title() if n == 'PROGRAM PENGAJIAN' else n, v) for n, v in ROWS)
        self.assertEqual(run(layout(rows=lower))['guard'], 'table_shape')
        no_row = tuple(r for r in ROWS if r[0] != 'PROGRAM PENGAJIAN')
        self.assertEqual(run(layout(rows=no_row))['guard'], 'table_shape')
        moved = ROWS[:2] + ROWS[3:5] + ROWS[2:3] + ROWS[5:]
        self.assertEqual(run(layout(rows=moved))['guard'], 'table_shape')
        self.assertEqual(run(layout(notes=NOTES[:2]))['guard'], 'owner_words_missing')   # note 2 is an owner phrase
        self.assertEqual(run()['locked']['programme'], PROGRAMME)            # read from the row, not from note 2

    def test_a_second_programme_or_code_refuses(self):
        again = (row('PROGRAM PENGAJIAN', CODE + ' - SARJANA MUDA SAINS DENGAN KEPUJIAN'),)
        self.assertEqual(run(layout(extra=again))['guard'], 'not_degree')
        other = (row('PROGRAM PENGAJIAN', 'US6440002 - SARJANA MUDA SAINS DENGAN KEPUJIAN'),)
        self.assertEqual(run(layout(extra=other))['guard'], 'second_code')
        self.assertEqual(run(layout(extra=('Kod alternatif : UH6481001',)))['guard'], 'second_code')
        self.assertEqual(run(layout(head=head(ref='12/US6440002/2027')))['guard'], 'code_mismatch')

    def test_diploma_asasi_and_non_degree_refuse(self):
        for prog in ('DIPLOMA KEJURUTERAAN ELEKTRIK', 'ASASI SAINS', 'SARJANA KEJURUTERAAN DENGAN KEPUJIAN',
                     'SARJANA MUDA KEJURUTERAAN', 'SARJANA MUDA DIPLOMA LANJUTAN DENGAN KEPUJIAN',
                     'SARJANA MUDA ASASI SAINS DENGAN KEPUJIAN', PROGRAMME + ' X'):
            with self.subTest(prog=prog):
                d = run(layout(rows=rows_with('PROGRAM PENGAJIAN', CODE + ' - ' + prog)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('programme_shape', 'not_degree', 'asasi_ai_read'))
        self.assertEqual(run(layout(rows=rows_with('PROGRAM PENGAJIAN', PROGRAMME)))['guard'], 'programme_shape')
        for line in ('Program Diploma Kejuruteraan', 'Pelajar Asasi Sains', 'Sila bawa sijil asal.',
                     'Program Sarjana Muda Teknologi'):
            with self.subTest(line=line):
                self.assertIn(run(layout(extra=(line,)))['guard'], ('not_degree', 'asasi_ai_read'))

    def test_diploma_asasi_titles_and_confirmations_refuse(self):
        for first in ('TAWARAN KEMASUKAN PROGRAM DIPLOMA, UNIVERSITI SAINS MALAYSIA (UNIVERSITI BERSTATUS',
                      'TAWARAN KEMASUKAN PROGRAM ASASI, UNIVERSITI SAINS MALAYSIA (UNIVERSITI BERSTATUS',
                      'TAWARAN KEMASUKAN PROGRAM IJAZAH SARJANA, UNIVERSITI SAINS MALAYSIA (UNIVERSITI BERSTATUS'):
            with self.subTest(first=first):
                self.assertEqual(read_usm(layout(title=(first, TITLE[1]))), (None, 'no_title'))
                self.assertIsNone(run(layout(title=(first, TITLE[1])))['locked'])
        confirm = '\n'.join(('KEPADA SESIAPA YANG BERKENAAN', 'NAMA : ' + NAME, 'NO. KP : ' + IC,
                             'Dengan ini disahkan bahawa penama di atas adalah pelajar tahun pertama',
                             'UNIVERSITI SAINS MALAYSIA', 'TAWARAN KEMASUKAN PROGRAM IJAZAH SARJANA MUDA'))
        self.assertIsNone(run(confirm)['locked'])
        self.assertIsNone(read_usm(confirm)[0])
        self.assertIn(read_usm(confirm)[1], ('no_title', 'status_letter'))
        self.assertEqual(run(layout(extra=('SURAT PENGESAHAN',)))['guard'], 'status_letter')
        for line in ('Permohonan saudara/i TIDAK BERJAYA.', 'Tawaran ini telah DIBATALKAN.',
                     'Tawaran ini telah ditarik balik.', 'Pihak universiti telah menarik balik tawaran ini.'):
            with self.subTest(line=line):
                d = run(layout(extra=(line,)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('status_letter', 'not_an_offer'))


class UsmIcTest(SimpleTestCase):
    def test_ic_shapes_refuse(self):
        """The bracket must hold the 12 plain digits: a hyphen, an en dash, a minus, a slash, a space, a whitespace
        run, a short or long run, a label or a line split refuses; so does no IC at all (USM prints it)."""
        for ic in (NRIC, '990101 14 5678', '990101–14–5678', '990101−14−5678', '990101/14/5678',
                   '990101   14   5678', '990101\t14\t5678', '99010114567', '9901011456789', 'No. K/P : ' + IC,
                   '990101\n145678', '990101-14-\n5678'):
            with self.subTest(ic=ic):
                d = run(layout(name_line=NAME + '  (' + ic + ')'))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('ic_shape', 'name_shape', 'second_ic'))
        for line in (NAME, NAME + '  ' + IC, NAME + '   (' + IC + ')', NAME + ' (' + IC + ') X'):
            with self.subTest(line=line):
                d = run(layout(name_line=line))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_shape', 'ic_shape', 'second_ic'))

    def test_a_second_ic_anywhere_refuses(self):
        from apps.scholarship.tests.test_offer_parse_uum import IC_SHAPES
        for ic in IC_SHAPES + ('990102145678', '990102-14-5678', NRIC, IC):
            with self.subTest(ic=ic):
                lay = layout(extra=('No. K/P waris :' + ' ' * 10 + ic,))
                self.assertIsNone(run(lay)['locked'])
                self.assertEqual(read_usm(lay)[1], 'second_ic')
                self.assertEqual(usm_letter_refusal(plain(layout()) + '\nWaris ' + ic, NRIC), 'second_ic')
                self.assertIn(run(page2='Universiti Sains Malaysia\nNo. K/P : ' + ic)['guard'],
                              ('second_ic', 'ic_printed'))
                p1 = plain(layout())
                d = offer_parse.diagnose(p1, p1 + '\nWaris ' + ic, layout(), [p1])
                self.assertIsNone(d['locked'])
        self.assertEqual(usm_letter_refusal(plain(layout()), NRIC), '')
        self.assertFalse(usm_ic_elsewhere(plain(layout()), NRIC))
        self.assertTrue(usm_ic_elsewhere(plain(layout()), '990102-14-5678'))     # a different IC read: the page's counts

    def test_the_read_ic_must_stand_in_the_plain_layer(self):
        p1 = plain(layout())
        for page1 in (p1.replace(IC, ''), p1.replace(IC, IC + ' ' + IC)):
            with self.subTest(copies='none' if IC not in page1 else 'two'):
                d = offer_parse.diagnose(p1, page1, layout(), [page1])
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('ic_not_plain', 'identity_disagree', 'second_ic', 'ic_printed'))

    def test_a_matric_or_reference_is_never_the_ic(self):
        for matric in ('990101145678', '990101-14-5678', '1234567'):
            with self.subTest(matric=matric):
                d = run(layout(rows=rows_with('NO MATRIK', matric)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('table_shape', 'second_ic'))
        for ref in ('12/990101145678/2027', '990101145678', '12/' + CODE + '/990101145678'):
            with self.subTest(ref=ref):
                d = run(layout(head=head(ref=ref)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('no_head', 'second_ic'))

    def test_the_ic_is_corroborate_only(self):
        """No label names the IC, so it is source 'other': the usual IC guard keeps it only when it is EXACTLY the
        profile IC; a different or blank profile IC blanks it, and a blank IC on this lane refuses (USM prints the
        IC: not in ISSUER_PRINTS_NO_IC)."""
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


class UsmNeverLocksTest(SimpleTestCase):
    def test_a_wrapped_name_never_locks_cut_short(self):
        """The line after the name must prove it ended (a digit, a comma or an address word opens it). NO'MAN and
        NO-MAN are a name's rest, not the address word NO; a lone place word may be a name's rest too."""
        for first, rest in (('ZORBEX QUENTARO', "NO'MAN"), ('ZORBEX QUENTARO', 'NO-MAN'),
                            ('ZORBEX QUENTARO', 'PINANG'), ('ZORBEX', 'QUENTARO BIN ALFEN')):
            with self.subTest(first=first, rest=rest):
                d = run(layout(name_line=first + '  (' + IC + ')\n' + M + rest))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_not_ended', 'name_shape', 'no_head'))
        for first, rest in (('ZORBEX QUENTARO', 'BIN ALFEN'), ('ZORBEX QUENTARO BIN', 'ALFEN'),
                            ('ZORBEX QUENTARO A/L', 'ALFEN'), ('ZORBEX QUENTARO BINTI', "NO'MAN")):
            with self.subTest(first=first, rest=rest):
                d = run(layout(name_line=first + '\n' + M + rest + '  (' + IC + ')'))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_not_ended', 'name_shape'))
        self.assertEqual(run(layout(name_line='ZORBEX QUENTARO BIN  (' + IC + ')'))['guard'], 'name_shape')
        for addr in ('KAMPUNG MAWAR', 'B-1-12 TAMAN MAWAR', 'NO 9 ,', 'LOT 99 LORONG 1', 'AB12,JALAN C'):
            with self.subTest(addr=addr):
                d = run(layout(address=(addr, '11800 GELUGOR')))
                self.assertEqual(d['locked']['candidate_name'], NAME, why(d))

    def test_name_must_be_read_exactly(self):
        for name_line in ('Z9RBEX QUENTARO  (' + IC + ')', 'Zorbex Quentaro Bin Alfen  (' + IC + ')',
                          NAME + '   EXTRA  (' + IC + ')'):
            with self.subTest(name_line=name_line):
                d = run(layout(name_line=name_line))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_shape', 'no_head'))
        self.assertEqual(run(layout(rows=rows_with('NAMA', 'ZORBEX QUENTARO')))['guard'], 'table_shape')

    def test_the_name_glue_check_reads_the_head_copy(self):
        """USM prints the name twice (head and NAMA row): the glue check takes the ONE exact plain "NAMA :" row out;
        no such row, two of them, or a glued head copy refuses."""
        from apps.scholarship.offer_parse_usm import usm_head_plain
        lay, p1 = layout(), plain(layout())
        self.assertNotIn('NAMA : ' + NAME, usm_head_plain(p1, NAME))
        self.assertIn(NAME + ' (' + IC + ')', usm_head_plain(p1, NAME))
        for page1 in (p1.replace('NAMA : ' + NAME, 'NAMA : ' + NAME + ' X'), p1 + '\nNAMA : ' + NAME,
                      p1.replace(NAME + ' (', NAME + 'SULIT (')):
            with self.subTest(page1=page1.count('NAMA :')):
                d = offer_parse.diagnose(p1, page1, lay, [page1])
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_not_plain', 'not_degree', 'ic_not_plain'))
        self.assertEqual(usm_head_plain(p1, ''), '')

    def test_the_note_excuse_is_one_exact_sentence_once(self):
        """Every genuine USM letter prints the conditional "Pihak universiti berhak menarik balik tawaran ini
        sekiranya ..." note; only that sentence, once, is taken out before the withdrawal and not-a-degree checks."""
        self.assertEqual(usm_letter_refusal(plain(layout()), NRIC), '')
        self.assertEqual(usm_letter_refusal(plain(layout(extra=(NOTE,))), NRIC), 'not_an_offer')
        self.assertIsNone(run(layout(extra=(NOTE,)))['locked'])
        for other in (NOTE.replace('keraguan', 'kesilapan'), NOTE.replace('Pihak universiti', 'Universiti'),
                      'Pihak universiti telah menarik balik tawaran ini.'):
            with self.subTest(other=other):
                lay = layout(notes=(M + '1.    ' + other,) + NOTES[2:])
                self.assertEqual(usm_letter_refusal(plain(lay), NRIC), 'not_an_offer')
                self.assertIsNone(run(lay)['locked'])

    def test_unknown_layouts_refuse(self):
        self.assertEqual(read_usm(layout(title=('TAWARAN KEMASUKAN KE UNIVERSITI SAINS MALAYSIA',)))[1], 'no_title')
        self.assertEqual(read_usm(layout(title=('OFFER OF ADMISSION',)))[1], 'no_title')
        self.assertIsNone(run(layout(title=('OFFER OF ADMISSION',)))['locked'])
        self.assertEqual(run(layout(extra=(M + TITLE[0],)))['guard'], 'no_title')                 # the title twice
        self.assertEqual(run(layout(head=(HEAD[1], HEAD[0])))['guard'], 'no_head')
        self.assertEqual(run(layout(head=HEAD[:1]))['guard'], 'no_head')
        self.assertEqual(run(layout(head=head(dated='31 SEPTEMBER 2027')))['guard'], 'no_head')
        self.assertEqual(run(layout(head=head(dated='15 Julai 2027')))['guard'], 'no_head')
        self.assertIn(run(layout(address=()))['guard'], ('name_not_ended', 'no_head'))
        self.assertEqual(run(layout(address=ADDRESS * 2))['guard'], 'no_head')
        self.assertEqual(run(layout(rows=(ROWS[1], ROWS[0]) + ROWS[2:]))['guard'], 'no_table')
        self.assertEqual(run(layout(rows=ROWS[:-1]))['guard'], 'table_shape')
        self.assertEqual(run(layout(rows=ROWS + (('CATATAN', 'TIADA'),)))['guard'], 'table_shape')
        self.assertEqual(run(layout(fees=FEES[:1]))['guard'], 'table_shape')
        self.assertEqual(run(layout(fees=()))['guard'], 'table_shape')
        no_greeting = layout(greeting=('Selamat datang ke USM.',))
        self.assertIsNone(run(no_greeting)['locked'])
        self.assertEqual(read_usm(no_greeting)[1], 'no_table')

    def test_reporting_date_read_only_when_labelled(self):
        for value in (REPORT_ON, REPORT_ON + ' (SELASA) / 8:00 PAGI - 12:00 TENGAH HARI', REPORT_ON + ' (ISNIN)',
                      '31 SEPTEMBER 2027 (ISNIN) / 8:00 PAGI - 12:00 TENGAH HARI', 'AKAN DIMAKLUMKAN',
                      '13/09/2027 (ISNIN) / 8:00 PAGI - 12:00 TENGAH HARI',
                      '13 September 2027 (Isnin) / 8:00 PAGI - 12:00 TENGAH HARI',
                      REPORT_ON + ' (ISNIN) / 8:00 PAGI - 12:00 MALAM',
                      REPORT_ON + ' (ISNIN) DAN 14 SEPTEMBER 2027 (SELASA)'):
            with self.subTest(value=value):
                d = run(layout(rows=rows_with('TARIKH LAPOR DIRI/MASA', value)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('reporting_shape', 'table_shape'))
        no_row = tuple(r for r in ROWS if r[0] != 'TARIKH LAPOR DIRI/MASA')
        self.assertEqual(run(layout(rows=no_row))['guard'], 'table_shape')                       # absent: never guessed

    def test_a_date_in_a_venue_or_note_is_never_taken(self):
        venue = 'DEWAN UTAMA mulai 12 SEPTEMBER 2027'
        self.assertEqual(run(layout(rows=rows_with('TEMPAT LAPOR DIRI', venue)))['guard'], 'stray_date')
        for note in ('Pendaftaran pada 12 September 2027 di Dewan Utama.', 'Sila hadir pada 12/09/2027.',
                     'Tarikh Cetak : 17/07/2027'):
            with self.subTest(note=note):
                d = run(layout(extra=(note,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'stray_date')

    def test_dates_and_session(self):
        self.assertEqual(run(layout(head=head(dated='15 JULAI 2030')))['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(head=head(dated='15 OKTOBER 2027')))['guard'], 'dates_not_sane')
        late = rows_with('TARIKH LAPOR DIRI/MASA', '11 SEPTEMBER 2028 (ISNIN) / 8:00 PAGI - 12:00 TENGAH HARI')
        self.assertIsNotNone(run(layout(rows=late))['locked'])                       # the session's second year
        later = rows_with('TARIKH LAPOR DIRI/MASA', '10 SEPTEMBER 2029 (ISNIN) / 8:00 PAGI - 12:00 TENGAH HARI')
        self.assertEqual(run(layout(rows=later))['guard'], 'dates_not_sane')
        odd = layout(title=(TITLE[0], 'APEX), SIDANG AKADEMIK 2027/2029'))
        self.assertEqual(run(odd)['guard'], 'dates_not_sane')

    def test_placeholder_refuses(self):
        self.assertEqual(run(layout(extra=('Tarikh tutup {tarikh_tutup}',)))['guard'], 'placeholder')

    def test_a_portal_page_refuses_with_no_excuse(self):
        self.assertFalse(run()['portal'])
        d = run(layout(extra=('Sila semak di Portal Semakan Kemasukan.',)))
        self.assertTrue(d['portal'])
        self.assertIsNone(d['locked'])

    def test_missing_owner_words_go_to_ai(self):
        self.assertEqual(run(layout(footer=FOOTER[:-1]))['guard'], 'owner_words_missing')

    def test_any_later_page_goes_to_ai(self):
        self.assertEqual(usm_later_pages(['SYARAT-SYARAT TAWARAN']), 'later_page')
        self.assertEqual(usm_later_pages(['', '  ']), '')
        self.assertEqual(run(page2='SYARAT-SYARAT TAWARAN\n1. Syarat am.')['guard'], 'later_page')

    def test_a_page_that_draws_no_text_refuses(self):
        self.assertEqual(run(page2='')['guard'], 'hidden_page')


class UsmWiringTest(SimpleTestCase):
    def test_ink_targets_hold_the_ic_code_and_date_as_printed(self):
        phrases, values = usm_ink_targets(run()['locked'], layout())
        self.assertEqual(len(phrases), 8)                    # phrase 1 is in the letterhead picture
        got = dict(values)
        self.assertEqual((got['v:name'], got['v:nric'], got['v:intake'], got['v:code']), (NAME, IC, INTAKE, CODE))
        self.assertEqual((got['v:date'], got['v:offer_date'], got['v:programme']), (REPORT_ON, OFFER_ON, PROGRAMME))
        self.assertFalse(any(MATRIC in v for v in got.values()))
        self.assertEqual(set(read_usm(layout())[0]), set(INK_LABELS) | set(NOT_PRINTED))
        self.assertTrue(set(INK_OPTIONAL) <= set(INK_LABELS))

    def test_family_and_lane_modules(self):
        text = plain(layout())
        self.assertEqual(offer_parse.family_of(text), 'usm')
        self.assertEqual(offer_exact._rules_family(text), 'usm')
        self.assertEqual(offer_exact._lane_module('usm').LANE, 'ua:USM')
        why_ = {}
        offer_exact._note_ums_refusal(why_, text, 'no_layout')
        self.assertEqual(why_, {'lane': 'ua:USM', 'reason': 'read_no_layout'})
        from apps.scholarship.eval.offer_read_check import RULES_LANES
        self.assertEqual(RULES_LANES['universiti sains malaysia'], 'ua:USM')

    def test_family_of_claims_only_usm_letters(self):
        for other in ('UNIVERSITI SAINS MALAYSIA\nSURAT AKUAN', 'UNIVERSITI SAINS ISLAM MALAYSIA\n'
                      'TAWARAN KEMASUKAN PROGRAM IJAZAH SARJANA MUDA', 'UNIVERSITI MALAYSIA SABAH\nTAWARAN KEMASUKAN'):
            with self.subTest(other=other.splitlines()[0]):
                self.assertNotEqual(offer_parse.family_of(other), 'usm')
        self.assertFalse(is_usm('UNIVERSITI SAINS MALAYSIA JABATAN PENDAFTAR'))

    def test_not_inked_dispatches_to_usm(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), 'ua:USM'), [])
            self.assertEqual(ink.call_args.kwargs['lane'], 'ua:USM')

    @override_settings(OCR_FIRST_LANES=[])
    def test_lane_off_by_default(self):
        text = plain(layout())
        why_ = {}
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(text, text)):
            self.assertIsNone(offer_exact.exact_offer_read(text, image=b'%PDF', content_type='application/pdf',
                                                           why=why_))
        self.assertEqual(why_, {'lane': 'ua:USM', 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=['ua:USM'])
    def test_lane_on_reads_the_layout(self):
        lay = layout()
        p1 = plain(lay)
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(p1, p1)), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_page1_layout', return_value=lay), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_rules_page_texts', return_value=[p1]), \
                mock.patch.object(offer_exact, '_not_inked', return_value=[]):
            ex = offer_exact.exact_offer_read(p1, image=b'%PDF', content_type='application/pdf', profile_nric=NRIC)
        self.assertIsNotNone(ex)
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), ('ua:USM', NRIC))
