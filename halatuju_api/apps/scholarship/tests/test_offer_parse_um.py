"""OCR-13 phase 4: the UM rules lane (`offer_parse_um`). UM prints the IC, so the IC guard applies as on every other
lane. Synthetic letters only (made-up names, numbers and addresses)."""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_parse_um import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, is_um, read_um
from apps.scholarship.offer_parse_um import um_ink_targets as ink_targets
from apps.scholarship.offer_parse_um import um_later_pages as later_pages_refusal
from apps.scholarship.offer_parse_um import um_letter_refusal as letter_refusal
from apps.scholarship.offer_parse_um import um_not_degree as not_degree

NAME = 'ZORBEX QUENTARO A/L ALFEN'
IC = '990101145678'
L = ' ' * 7
PROGRAMME = 'SARJANA MUDA SAINS KOMPUTER'


def label(name, value, width=54):
    return L + name + ' ' * (width - len(name)) + ':   ' + value


def layout(ic_line=None, name_line=None, title='TAWARAN KEMASUKAN KE UNIVERSITI MALAYA', programme=PROGRAMME,
           wrap=(), intake='SEMESTER 1, SESI AKADEMIK 2027/2028', report='RUJUK LAMPIRAN', offer='12 Julai 2027',
           extra=(), head_extra=()):
    lines = [
        L + 'No Pendaftaran : 27123456' + ' ' * 91 + 'Tarikh : ' + offer,
        ic_line if ic_line is not None else L + 'Nombor K/P' + ' ' * 7 + ': ' + IC,
        name_line if name_line is not None else L + NAME,
        L + 'NO 1 JALAN MAWAR', L + 'TAMAN BUNGA', L + '31000 BATU GAJAH', *head_extra, L + 'PERAK',
        L + 'MALAYSIA', '      Saudara/i,', '      ' + title,
        '      Tahniah saudara/i telah berjaya ditawarkan tempat untuk mengikuti program pengajian di Universiti '
        'Malaya seperti berikut:',
        label('SESI KEMASUKAN', intake), label('PROGRAM PENGAJIAN', programme), *wrap,
        label('FAKULTI', 'FAKULTI SAINS KOMPUTER'), label('MOD PENAWARAN PROGRAM', 'KERJA KURSUS'),
        label('TEMPOH PENGAJIAN', 'MINIMUM LAPAN (8) SEMESTER'), ' ' * 65 + 'MAKSIMUM DUA BELAS (12) SEMESTER',
        label('KAEDAH PENGAJIAN', 'SEPENUH MASA'), label('PENGINAPAN', 'RUJUK LAMPIRAN'),
        label('TARIKH LAPOR DIRI DI KOLEJ', report), label('YURAN PENGAJIAN', 'RUJUK LAMPIRAN'), *extra,
        '      Sehubungan itu, saudara/i diminta untuk mengambil perhatian kepada perkara berikut:',
        '          1. Tawaran ini adalah MUKTAMAD dan sebarang pertukaran program pengajian adalah tidak dibenarkan.',
        '      Sekian, terima kasih.', '      Yang benar,', L + 'PENGARAH EKSEKUTIF',
        L + 'Jabatan Perkhidmatan Akademik (ASD)', L + 'Universiti Malaya',
    ]
    return '\n'.join(lines)


PAGE2 = '\n'.join(['LAMPIRAN', 'MAKLUMAT PENDAFTARAN', 'Universiti Malaya',
                   '1. Saudara/i hendaklah membawa dokumen asal.', 'aasd.um.edu.my'])


def plain(lay):
    return '\n'.join(' '.join(ln.split()) for ln in lay.splitlines() if ln.strip())


def run(lay=None, page2=None):
    lay = lay if lay is not None else layout()
    p1 = plain(lay)
    pages = [p1] + ([page2] if page2 is not None else [])
    return offer_parse.diagnose('\n'.join(pages), p1, lay, pages)


def why(d):
    return d['guard'] or ('empty:' + ','.join(d['empty_required']) if d['empty_required'] else None)


class UmLockTest(SimpleTestCase):
    def test_degree_letter_locks(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane']), ('um', LANE))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), ('990101-14-5678', 'label'))
        self.assertEqual(lock['programme'], PROGRAMME)
        self.assertEqual(lock['intake'], 'SEMESTER 1, SESI AKADEMIK 2027/2028')
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('', ''))   # "RUJUK LAMPIRAN"
        self.assertEqual(lock['offer_date'], '12 Julai 2027')
        self.assertEqual(lock['institution'], 'UNIVERSITI MALAYA')
        self.assertFalse(any('27123456' in str(v) for v in lock.values()))        # the registration number
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_a_printed_reporting_date_is_read(self):
        lock = run(layout(report='14 September 2027'))['locked']
        self.assertEqual(lock['reporting_date'], '14 Sep 2027')
        self.assertEqual(lock['reporting_date_label'], 'TARIKH LAPOR DIRI DI KOLEJ')

    def test_programme_shapes(self):
        lock = run(layout(programme='SARJANA MUDA SAINS DENGAN', wrap=(' ' * 65 + 'KEPUJIAN (KIMIA)',)))['locked']
        self.assertEqual(lock['programme'], 'SARJANA MUDA SAINS DENGAN KEPUJIAN (KIMIA)')
        self.assertEqual(run(layout(wrap=('KEPUJIAN',)))['guard'], 'programme_shape')     # not indented
        self.assertEqual(run(layout(wrap=tuple(' ' * 65 + w for w in 'ABC')))['guard'], 'programme_shape')

    def test_a_scan_refuses_no_layout(self):
        d = offer_parse.diagnose(plain(layout()), '', '', None)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('um', 'no_layout', None))


class UmNeverLocksTest(SimpleTestCase):
    def test_um_without_an_ic_refuses(self):
        for ic_line, want in ((L + 'Nombor K/P' + ' ' * 7 + ': ', 'empty:candidate_nric'),
                              (L + 'Nombor K/P', 'no_ic_line'),
                              (L + 'Nombor K/P' + ' ' * 7 + ': 99010114567', 'empty:candidate_nric'),
                              (L + 'Nombor K/P' + ' ' * 7 + ': A1234567', 'empty:candidate_nric'),
                              (L + 'No Pasport' + ' ' * 7 + ': A1234567', 'no_ic_line')):
            with self.subTest(ic_line=ic_line):
                d = run(layout(ic_line=ic_line))
                self.assertIsNone(d['locked'])
                self.assertEqual(why(d), want)

    def test_um_lock_without_an_ic_is_refused_by_the_guard(self):
        self.assertNotIn(LANE, offer_exact.ISSUER_PRINTS_NO_IC)
        lock = {'family': 'um', 'guard': None, 'empty_required': [], 'portal': False,
                'locked': {'candidate_name': NAME, 'candidate_nric': '', 'candidate_nric_source': 'none',
                           'programme': PROGRAMME, 'institution': 'UNIVERSITI MALAYA', 'rules_lane': LANE,
                           '_family': 'um'}}
        with mock.patch('apps.scholarship.offer_parse.diagnose', return_value=lock):
            why_ = {}
            self.assertIsNone(offer_exact.exact_read(plain(layout()), profile_nric='990101-14-5678', why=why_))
        self.assertEqual(why_, {'lane': LANE, 'reason': 'read_nric_guard'})

    def test_um_asasi_refuses(self):
        for prog in ('ASASI SAINS HAYAT', 'ASASI SAINS FIZIKAL'):
            with self.subTest(prog=prog):
                d = run(layout(programme=prog))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('not_degree', 'asasi_ai_read'))

    def test_english_um_letter_refuses(self):
        lay = layout(title='OFFER OF ADMISSION TO UNIVERSITI MALAYA')
        d = run(lay)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('um', 'no_title', None))
        english = lay.replace('Jabatan Perkhidmatan Akademik', 'Academic Services Division')
        self.assertIsNone(run(english)['locked'])
        self.assertEqual(offer_parse.family_of(plain(english)), '')

    def test_non_degree_programmes_go_to_ai(self):
        for prog in ('DIPLOMA SAINS', 'PRA SISWAZAH', 'SIJIL SAINS', 'FOUNDATION IN SCIENCE', 'CERTIFICATE IN LAW',
                     'SARJANA MUDA SAINS DIPLOMA', 'SARJANA MUDA (MATRIKULASI)', 'SARJANA MUDA PERSEDIAAN',
                     'SARJANA MUDA PRA SAINS', 'Sarjana Muda Sains', 'SARJANA SAINS', 'BACHELOR OF SCIENCE'):
            with self.subTest(prog=prog):
                d = run(layout(programme=prog))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('not_degree', 'asasi_ai_read'))
        self.assertTrue(not_degree('SARJANA MUDA DІPLOMA'))                      # Cyrillic І
        self.assertIn(run(layout(wrap=(' ' * 65 + 'ASASI',)))['guard'], ('not_degree', 'asasi_ai_read'))
        self.assertFalse(not_degree('IJAZAH SARJANA MUDA KEJURUTERAAN (ELEKTRIK)'))

    def test_name_must_be_read_exactly(self):
        for name_line in (L + 'ZORBEX QUENTARO A/L', L + 'Z9RBEX QUENTARO', L + NAME + '   EXTRA',
                          ' ' * 14 + NAME, L + 'Saudara/i,'):
            with self.subTest(name_line=name_line):
                d = run(layout(name_line=name_line))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_shape', 'no_head'))

    def test_a_name_must_be_proven_to_end(self):
        """Review 1: the line after the name must prove it ended (a digit, a comma or an address word opens it); a
        name broken over two lines, after a whole word or after a linker, never locks cut short."""
        for first, rest in (('ZORBEX QUENTARO', 'A/L ALFEN'), ('ZORBEX QUENTARO A/L', 'ALFEN'),
                            ('ZORBEX QUENTARO', 'BIN ALFEN'), ('ZORBEX QUENTARO BINTI', 'ALFEN'), ('ZORBEX', 'QUENTARO')):
            with self.subTest(first=first, rest=rest):
                d = run(layout(name_line=L + first + '\n' + L + rest))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_not_ended', 'name_shape'))
        for addr in ('KG, MAWAR', 'SEKOLAH MENENGAH MAWAR,', 'NO12,JALAN MAWAR', 'LOT 5 KAMPUNG MAWAR'):
            with self.subTest(addr=addr):
                lay = layout().replace(L + 'NO 1 JALAN MAWAR', L + addr)
                self.assertEqual(run(lay)['locked']['candidate_name'], NAME)
        for nxt in ('SEKOLAH', 'MAWAR INDAH', ' ' * 70 + '12 Julai 2027'):
            with self.subTest(nxt=nxt):
                lay = layout().replace(L + 'NO 1 JALAN MAWAR', nxt if nxt.startswith(' ') else L + nxt)
                self.assertEqual(run(lay)['guard'], 'name_not_ended')

    def test_dates_and_session(self):
        self.assertEqual(run(layout(report='14 September 2030'))['guard'], 'dates_not_sane')
        self.assertEqual(why(run(layout(report='31 September 2027'))), 'empty:reporting_date')
        self.assertEqual(run(layout(report='14/09/2027'))['guard'], 'reporting_shape')
        self.assertEqual(run(layout(report='SILA HUBUNGI KOLEJ'))['guard'], 'reporting_shape')
        self.assertEqual(run(layout(report='1 Ogos 2027', offer='12 September 2027'))['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(offer='31 Februari 2027'))['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(intake='SEMESTER 1, SESI AKADEMIK 2027/2029'))['guard'], 'dates_not_sane')
        self.assertEqual(why(run(layout(intake='SESI 2027/2028'))), 'empty:intake')

    def test_title_and_labels_once(self):
        self.assertEqual(run(layout(extra=['      TAWARAN KEMASUKAN KE UNIVERSITI MALAYA']))['guard'], 'no_title')
        self.assertEqual(run(layout(extra=[label('PROGRAM PENGAJIAN', 'SARJANA MUDA UNDANG-UNDANG')]))['guard'],
                         'programme_twice')
        self.assertEqual(run(layout(extra=[label('SESI KEMASUKAN', 'SEMESTER 2, SESI AKADEMIK 2027/2028')]))['guard'],
                         'twice_sesi')
        self.assertEqual(run(layout(title='TAWARAN KEMASUKAN KE UNIVERSITI MALAYA SESI 2027/2028'))['guard'],
                         'no_title')

    def test_missing_owner_words_go_to_ai(self):
        for old, new in {'TEMPOH PENGAJIAN': 'LAMA PENGAJIAN', 'adalah MUKTAMAD': 'adalah TETAP'}.items():
            with self.subTest(old=old):
                self.assertEqual(run(layout().replace(old, new))['guard'], 'owner_words_missing')

    def test_status_and_withdrawal_refuse(self):
        self.assertEqual(run(page2=PAGE2 + '\nTawaran ini telah DIBATALKAN.')['guard'], 'not_an_offer')
        self.assertEqual(letter_refusal('SURAT PENGESAHAN\nTAWARAN'), 'status_letter')


class UmLaterPagesTest(SimpleTestCase):
    def test_footer_words_alone_still_lock(self):
        page = PAGE2 + '\nSekian, terima kasih. Jabatan Perkhidmatan Akademik. Pendaftaran pelajar baharu.'
        self.assertEqual(later_pages_refusal([page], IC, PROGRAMME, ''), '')
        self.assertIsNotNone(run(page2=page)['locked'])
        self.assertEqual(later_pages_refusal([PAGE2 + '\n' + PROGRAMME + '\n' + IC], IC, PROGRAMME, ''), '')

    def test_conflicts_go_to_ai(self):
        cases = {'SARJANA MUDA UNDANG-UNDANG': 'second_programme', 'ASASI SAINS': 'second_programme',
                 'Tarikh Lapor Diri : 15 September 2027': 'second_date', '990101-14-5679': 'second_ic',
                 '9901011456781': 'second_ic'}
        for extra, want in cases.items():
            with self.subTest(extra=extra):
                self.assertEqual(later_pages_refusal([PAGE2 + '\n' + extra], IC, PROGRAMME, ''), want)
                self.assertEqual(run(page2=PAGE2 + '\n' + extra)['guard'], want)
        same = PAGE2 + '\nTarikh Lapor Diri : 14 September 2027'
        self.assertEqual(later_pages_refusal([same], IC, PROGRAMME, '14 September 2027'), '')

    def test_unknown_page_goes_to_ai(self):
        self.assertEqual(later_pages_refusal(['Resit Bayaran Yuran'], IC, PROGRAMME, ''), 'unknown_page')
        self.assertEqual(run(page2='Resit Bayaran Yuran')['guard'], 'unknown_page')


class UmWiringTest(SimpleTestCase):
    def test_ink_targets(self):
        d = run()
        phrases, values = ink_targets(d['locked'], layout())
        self.assertEqual(len(phrases), 8)
        got = dict(values)
        self.assertEqual((got['v:nric'], got['v:name'], got['v:offer_date']), (IC, NAME, '12 Julai 2027'))
        self.assertNotIn('v:date', got)                                           # "RUJUK LAMPIRAN": not read
        self.assertEqual(dict(ink_targets(run(layout(report='14 September 2027'))['locked'],
                                          layout(report='14 September 2027'))[1])['v:date'], '14 September 2027')
        self.assertEqual(set(read_um(layout())[0]), set(INK_LABELS) | set(NOT_PRINTED))
        self.assertTrue(set(INK_OPTIONAL) <= set(INK_LABELS))

    def test_family_and_lane_modules(self):
        text = plain(layout())
        self.assertEqual(offer_parse.family_of(text), 'um')
        self.assertEqual(offer_exact._rules_family(text), 'um')
        self.assertEqual(offer_exact._lane_module('um').LANE, 'ua:UM')
        why_ = {}
        offer_exact._note_ums_refusal(why_, text, 'no_layout')
        self.assertEqual(why_, {'lane': 'ua:UM', 'reason': 'read_no_layout'})
        self.assertFalse(is_um('UNIVERSITI MALAYSIA SABAH JABATAN PERKHIDMATAN AKADEMIK'))
        self.assertFalse(is_um('UNIVERSITI MALAYA KUALA LUMPUR'))

    def test_not_inked_dispatches_to_um(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), 'ua:UM'), [])
            self.assertEqual(ink.call_args.kwargs['lane'], 'ua:UM')

    @override_settings(OCR_FIRST_LANES=[])
    def test_lane_off_by_default(self):
        text = plain(layout())
        why_ = {}
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(text, text)):
            self.assertIsNone(offer_exact.exact_offer_read(text, image=b'%PDF', content_type='application/pdf',
                                                           why=why_))
        self.assertEqual(why_, {'lane': 'ua:UM', 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=['ua:UM'])
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
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), ('ua:UM', '990101-14-5678'))
