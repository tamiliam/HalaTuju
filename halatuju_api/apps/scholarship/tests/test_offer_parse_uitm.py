"""OCR-13 phase 2: the UiTM rules lane (`offer_parse_uitm`), synthetic letters only (made-up names and ICs)."""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_parse
from apps.scholarship.offer_parse_uitm import (INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, ink_targets,
                                               later_pages_refusal, letter_refusal, not_degree, read_uitm)

NAME = 'ZORBEX QUENTARO BIN ALFEN'
IC = '990101145678'
R = ' ' * 84                                      # the right-hand notes column

HEAD = [
    ' ' * 66 + 'www.uitm.edu.my',
    'SURAT TAWARAN',
    NAME + ' ' * 30 + 'No. Kad Pengenalan' + ' ' * 17 + IC,
    'NO 1 JALAN MAWAR' + ' ' * 50 + 'No. Pelajar',
    'TAMAN BUNGA' + ' ' * 80 + '2027000001',
]
BODY = [
    'Sukacita dimaklumkan bahawa anda ditawarkan tempat untuk mengikuti' + ' ' * 18 + 'MAKLUMAT PENTING',
    'program di UiTM:' + ' ' * 68 + '1. Program dan kampus yang',
    R + 'ditawarkan adalah MUKTAMAD.',
    'Program' + ' ' * 23 + '{code}' + ' ' * 50 + 'TIDAK DIBENARKAN.',
    ' ' * 30 + '{programme}',
    'Mod Pengajian' + ' ' * 17 + 'SEPENUH MASA',
    'Fakulti' + ' ' * 23 + 'FAKULTI SAINS KOMPUTER',
    'Tempoh Pengajian' + ' ' * 14 + '8 SEMESTER',
    'Sesi Kemasukan' + ' ' * 16 + 'SESI 1 2027/2028',
    'Kampus' + ' ' * 24 + 'B - UiTM KAMPUS SHAH ALAM',
    'Sila hadir mendaftar pada tarikh, masa dan tempat yang ditetapkan:',
    'Tarikh' + ' ' * 24 + '{date}',
    'Masa' + ' ' * 26 + '8:00 AM - 12:00 PM',
    'Bahagian Pengambilan Pelajar',
]
NOTE = ('2. Tawaran ini adalah terbatal sekiranya terdapat maklumat yang salah, tidak benar atau dipinda secara '
        'tidak sah pada borang permohonan atau surat tawaran.')
PAGE2 = '\n'.join([
    'Bahagian Pengambilan Pelajar', 'Kompleks Antarabangsa', 'Universiti Teknologi MARA',
    '40450 Shah Alam, Selangor, MALAYSIA', 'pengambilan.uitm.edu.my', 'Pra Diploma: (603) 5544 3000',
    'Asasi & Diploma: (603) 5544 3001 / 3002', 'Sarjana Muda: (603) 5544 3003',
    'https://online.uitm.edu.my/surat/papar.cfm?id=12345678 12/05/2027, 9:41 AM', 'Page 2 of 2'])


def layout(code='CS230', programme='SARJANA MUDA SAINS KOMPUTER (KEPUJIAN)', date='05/10/2027', head=None,
           extra=()):
    body = [ln.format(code=code, programme=programme, date=date) for ln in BODY]
    return '\n'.join(list(head or HEAD) + body + list(extra))


def plain(lay):
    return '\n'.join(' '.join(ln.split()) for ln in lay.splitlines() if ln.strip())


def run(lay=None, page2=PAGE2, pages=None):
    lay = lay if lay is not None else layout()
    p1 = plain(lay)
    page_list = pages if pages is not None else [p1] + ([page2] if page2 is not None else [])
    text = '\n'.join([p1, NOTE] + page_list[1:])
    return offer_parse.diagnose(text, p1, lay, page_list)


def why(d):
    return d['guard'] or ('empty:' + ','.join(d['empty_required']) if d['empty_required'] else None)


class UitmLockTest(SimpleTestCase):
    def test_full_degree_letter_locks(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual(d['family'], 'uitm')
        self.assertEqual(lock['rules_lane'], LANE)
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual(lock['candidate_nric'], '990101-14-5678')
        self.assertEqual(lock['programme'], 'SARJANA MUDA SAINS KOMPUTER (KEPUJIAN)')
        self.assertEqual(lock['programme_code'], 'CS230')
        self.assertEqual(lock['intake'], 'SESI 1 2027/2028')
        self.assertEqual(lock['reporting_date'], '5 Oct 2027')
        self.assertEqual(lock['institution'], 'UiTM')
        self.assertEqual(lock['offer_date'], '')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_one_page_letter_locks(self):
        self.assertIsNotNone(run(page2=None)['locked'])

    def test_wrapped_programme_and_kepujian_variants_lock(self):
        for prog in ('IJAZAH SARJANA MUDA SAINS (KEPUJIAN)', 'SARJANA MUDA SAINS KEPUJIAN',
                     'SARJANA MUDA PENDIDIKAN (KEPUJIAN) BIOLOGI', 'SARJANA MUDA SAINS DENGAN PENDIDIKAN'):
            with self.subTest(prog=prog):
                self.assertIsNotNone(run(layout(programme=prog))['locked'])
        lay = layout(programme='SARJANA MUDA SAINS KOMPUTER').replace(
            'SEPENUH MASA', 'SEPENUH MASA', 1).replace(
            '\nMod Pengajian', '\n' + ' ' * 30 + '(KEPUJIAN)\nMod Pengajian', 1)
        d = run(lay)
        self.assertEqual(d['locked']['programme'], 'SARJANA MUDA SAINS KOMPUTER (KEPUJIAN)')

    def test_a_scan_refuses_no_layout(self):
        lay = layout()
        d = offer_parse.diagnose('\n'.join([plain(lay), NOTE, PAGE2]), '', '', None)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('uitm', 'no_layout', None))


class UitmRefusalTest(SimpleTestCase):
    def test_each_missing_owner_word_goes_to_ai(self):
        cuts = {'Sukacita dimaklumkan': 'Dimaklumkan', 'Tempoh Pengajian': 'Lama Pengajian',
                'adalah MUKTAMAD': 'adalah TETAP', 'Bahagian Pengambilan Pelajar': 'Pejabat Pelajar'}
        for old, new in cuts.items():
            with self.subTest(old=old):
                d = run(layout().replace(old, new))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'owner_words_missing')

    def test_non_degree_programmes_go_to_ai(self):
        for prog in ('DIPLOMA SAINS KOMPUTER', 'ASASI SAINS', 'PRA DIPLOMA SAINS', 'SIJIL PERAKAUNAN',
                     'FOUNDATION IN SCIENCE', 'SARJANA MUDA SAINS (KEPUJIAN) DIPLOMA', 'SARJANA MUDA PRA SAINS',
                     'SARJANA MUDA SAINS (MATRIKULASI)', 'SARJANA MUDA PERSEDIAAN', 'CERTIFICATE IN LAW',
                     'SARJANA MUDA D.I.P.L.O.M.A', 'Sarjana Muda Sains', 'SARJANA SAINS'):
            with self.subTest(prog=prog):
                d = run(layout(programme=prog))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('not_degree', 'asasi_ai_read'))

    def test_code_third_character_must_be_two(self):
        for code in ('CS110', 'CS130', 'AS020', 'CS240'):
            with self.subTest(code=code):
                d = run(layout(code=code))
                if code[2] == '2':
                    self.assertIsNotNone(d['locked'])
                else:
                    self.assertEqual(d['guard'], 'not_degree')
        self.assertEqual(run(layout(code='CS23'))['guard'], 'no_code')

    def test_wrapped_name_goes_to_ai(self):
        wrapped = HEAD[:2] + ['ZORBEX', 'QUENTARO BIN ALFEN' + ' ' * 30 + 'No. Kad Pengenalan' + ' ' * 17 + IC] + HEAD[3:]
        self.assertEqual(run(layout(head=wrapped))['guard'], 'wrapped_name')
        cut = HEAD[:2] + ['ZORBEX QUENTARO BIN' + ' ' * 30 + 'No. Kad Pengenalan' + ' ' * 17 + IC] + HEAD[3:]
        self.assertEqual(run(layout(head=cut))['guard'], 'name_shape')

    def test_a_name_must_be_proven_to_end(self):
        """Review 1: the line after the name must prove it ended (a digit, a comma or an address word opens it); a
        name broken over two lines, after a whole word or after a linker, never locks cut short."""
        ic_line = ' ' * 30 + 'No. Kad Pengenalan' + ' ' * 17 + IC
        for first, rest in (('ZORBEX QUENTARO', 'BIN ALFEN'), ('ZORBEX QUENTARO', 'ALFEN'), ('ZORBEX A/L', 'QUENTARO'),
                            ('ZORBEX QUENTARO BIN', 'ALFEN'), ('ZORBEX QUENTARO BINTI', 'ALFEN')):
            with self.subTest(first=first, rest=rest):
                head = HEAD[:2] + [first + ic_line, rest + ' ' * 50 + 'No. Pelajar'] + HEAD[3:]
                d = run(layout(head=head))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_not_ended', 'name_shape'))
        for nxt in (' ' * 84 + 'MAKLUMAT PENTING', 'TAMBUN INDAH' + ' ' * 50 + 'No. Pelajar',
                    "NO'MAN ALFEN" + ' ' * 50 + 'No. Pelajar', 'NO’MAN' + ' ' * 50 + 'No. Pelajar',
                    'NO-MAN ALFEN', "KG'AN", 'LOT-ANI ALFEN'):     # review 2: a name, not an address word
            with self.subTest(nxt=nxt):
                head = HEAD[:3] + [nxt] + HEAD[4:]
                self.assertEqual(run(layout(head=head))['guard'], 'name_not_ended')
        for addr in ('KAMPUNG MAWAR', 'KG. MAWAR', 'PETI SURAT 12, JALAN MAWAR', 'D-1-2, TINGKAT 1, BLOK A',
                     'SG BUAH, KG MAWAR', 'TAMAN BUNGA LOT 12'):
            with self.subTest(addr=addr):
                head = HEAD[:3] + [addr + ' ' * 40 + 'No. Pelajar'] + HEAD[4:]
                d = run(layout(head=head))
                self.assertIsNotNone(d['locked'])
                self.assertEqual(d['locked']['candidate_name'], NAME)

    def test_title_must_stand_alone(self):
        for head in (['SURAT', 'TAWARAN'] + HEAD[2:], HEAD[:1] + ['SURAT TAWARAN   KEMASUKAN'] + HEAD[2:],
                     ['UNTUK MAKLUMAN'] + HEAD):
            with self.subTest(head=head[:2]):
                self.assertIsNone(run(layout(head=head))['locked'])

    def test_dates_and_session(self):
        self.assertEqual(run(layout(date='05/10/2030'))['guard'], 'dates_not_sane')
        self.assertEqual(why(run(layout(date='31/02/2027'))), 'empty:reporting_date')
        self.assertEqual(why(run(layout(date='5 OKT 2027'))), 'empty:reporting_date')
        self.assertIsNotNone(run(layout(date='5/9/2027'))['locked'])

    def test_second_program_line_on_page_one_refuses(self):
        d = run(layout(extra=['Program' + ' ' * 23 + 'CS240']))
        self.assertEqual(d['guard'], 'programme_twice')

    def test_withdrawal_and_status_refuse(self):
        self.assertEqual(letter_refusal('SURAT TAWARAN\n' + NOTE), '')
        self.assertEqual(letter_refusal('SURAT TAWARAN\nTawaran ini telah DIBATALKAN.'), 'not_an_offer')
        self.assertEqual(letter_refusal('SURAT TAWARAN\nTawaran ini adalah terbatal.'), 'not_an_offer')
        self.assertEqual(letter_refusal('SURAT TAWARAN\nTawaran ini tidak sah.'), 'not_an_offer')
        self.assertEqual(letter_refusal('SURAT PENGESAHAN\nSURAT TAWARAN'), 'status_letter')
        d = run(page2=PAGE2 + '\nTawaran anda telah ditarik balik.')
        self.assertEqual(d['guard'], 'not_an_offer')


class UitmLaterPagesTest(SimpleTestCase):
    def test_footer_words_only_still_lock(self):
        page = PAGE2 + '\nASASI DIPLOMA PRA SARJANA MUDA SURAT TAWARAN ' + IC
        self.assertEqual(later_pages_refusal([page], IC, '05/10/2027'), '')
        self.assertIsNotNone(run(page2=page)['locked'])

    def test_second_ic_programme_or_date_goes_to_ai(self):
        cases = {'990101-14-5679': 'second_ic', '9901011456781': 'second_ic', 'Program CS240': 'second_programme',
                 'CS 230': 'second_programme', 'Tarikh 06/10/2027': 'second_date', '6.10.2027': 'second_date'}
        for extra, want in cases.items():
            with self.subTest(extra=extra):
                self.assertEqual(later_pages_refusal([PAGE2 + '\n' + extra], IC, '05/10/2027'), want)
                self.assertEqual(run(page2=PAGE2 + '\n' + extra)['guard'], want)
        self.assertEqual(later_pages_refusal([PAGE2 + '\nTarikh 5/10/2027'], IC, '05/10/2027'), '')

    def test_unknown_page_goes_to_ai(self):
        self.assertEqual(later_pages_refusal(['Some other document'], IC, '05/10/2027'), 'unknown_page')
        self.assertEqual(run(page2='Resit Bayaran Yuran')['guard'], 'unknown_page')
        self.assertEqual(run(pages=[plain(layout()), ''])['guard'], 'hidden_page')
        self.assertEqual(run(pages=[plain(layout())] + [PAGE2] * 3)['guard'], 'too_many_pages')


class UitmAsasiAndLookalikeTest(SimpleTestCase):
    def test_asasi_excuse_interplay(self):
        phone = R + 'Asasi & Diploma: (603) 5544 3001 / 3002'
        self.assertIsNotNone(run(layout(extra=[phone]))['locked'])            # the one office line is excused
        self.assertEqual(run(layout(extra=[phone, phone]))['guard'], 'asasi_ai_read')   # two: nothing excused
        self.assertEqual(run(layout(extra=[R + 'Program ASASI ditawarkan']))['guard'], 'asasi_ai_read')
        self.assertEqual(run(layout(programme='ASASI SAINS'))['guard'], 'not_degree')

    def test_lookalike_letters(self):
        self.assertTrue(not_degree('SARJANA MUDA DІPLOMA'))                    # Cyrillic І
        self.assertTrue(not_degree('SARJANA MUDA АSASI'))                       # Cyrillic А
        d = run(layout(programme='SARJANA MUDA SАINS (KEPUJIAN)'))             # Cyrillic А, not a non-degree word
        self.assertIsNone(d['locked'])
        d = run(page2=PAGE2 + '\nTawaran ini DIBАTALKAN')                       # Cyrillic А in a withdrawal
        self.assertIsNone(d['locked'])


class UitmWiringTest(SimpleTestCase):
    def test_ink_targets_cover_every_printed_field(self):
        d = run()
        phrases, values = ink_targets(d['locked'], layout())
        self.assertEqual(len(phrases), 8)
        got = dict(values)
        self.assertEqual(got['v:nric'], IC)
        self.assertEqual(got['v:date'], '05/10/2027')
        self.assertEqual(got['v:name'], NAME)
        read = set(read_uitm(layout())[0])
        self.assertEqual(read, set(INK_LABELS) | set(NOT_PRINTED))
        self.assertTrue(set(INK_OPTIONAL) <= set(INK_LABELS))

    def test_family_and_lane_modules(self):
        from apps.scholarship import offer_exact
        lay = layout()
        text = '\n'.join([plain(lay), NOTE, PAGE2])
        self.assertEqual(offer_parse.family_of(text), 'uitm')
        self.assertEqual(offer_exact._rules_family(text), 'uitm')
        self.assertEqual(offer_exact._lane_module('uitm').LANE, 'ua:UiTM')
        self.assertIsNone(offer_exact._lane_module('stpm'))
        why_ = {}
        offer_exact._note_ums_refusal(why_, text, 'no_layout')
        self.assertEqual(why_, {'lane': 'ua:UiTM', 'reason': 'read_no_layout'})

    def test_not_inked_dispatches_per_lane(self):
        from apps.scholarship import offer_exact
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), 'ua:UiTM'), [])
            self.assertEqual(ink.call_args.kwargs['lane'], 'ua:UiTM')
            self.assertEqual(offer_exact._not_inked({'fields': {}}, b'', '', 'ua:UMK'), ['no_targets'])   # no reader (UKM has one since OCR-14 phase 4)

    @override_settings(OCR_FIRST_LANES=[])
    def test_lane_off_by_default(self):
        from apps.scholarship import offer_exact
        lay = layout()
        text = '\n'.join([plain(lay), NOTE, PAGE2])
        why_ = {}
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(text, plain(lay))):
            self.assertIsNone(offer_exact.exact_offer_read(text, image=b'%PDF', content_type='application/pdf',
                                                           why=why_))
        self.assertEqual(why_, {'lane': 'ua:UiTM', 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=['ua:UiTM'])
    def test_lane_on_reads_the_layout(self):
        from apps.scholarship import offer_exact
        lay = layout()
        p1 = plain(lay)
        text = '\n'.join([p1, NOTE, PAGE2])
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(text, p1)), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_page1_layout', return_value=lay), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_rules_page_texts', return_value=[p1, PAGE2]), \
                mock.patch.object(offer_exact, '_not_inked', return_value=[]):
            ex = offer_exact.exact_offer_read(text, image=b'%PDF', content_type='application/pdf',
                                              profile_nric='990101-14-5678')
        self.assertIsNotNone(ex)
        self.assertEqual(ex['rules_lane'], 'ua:UiTM')
