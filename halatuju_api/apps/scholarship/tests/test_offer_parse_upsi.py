"""OCR-13 phase 5: the UPSI rules lane (`offer_parse_upsi`) and its no-IC lock (`offer_exact.ISSUER_PRINTS_NO_IC`,
owner 26 Nov: "Same as UUM"). The matric number is not an IC and is never stored. Synthetic letters only (made-up
names, numbers and addresses)."""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_parse_upsi import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, is_upsi, read_upsi
from apps.scholarship.offer_parse_upsi import upsi_ink_targets as ink_targets
from apps.scholarship.offer_parse_upsi import upsi_later_pages as later_pages_refusal
from apps.scholarship.offer_parse_upsi import upsi_letter_refusal as letter_refusal

NAME = 'ZORBEX QUENTARO A/L ALFEN'
MATRIC = 'D20271234567'
L = '  '
R = ' ' * 70
TITLE = 'TAWARAN KEMASUKAN KE UNIVERSITI PENDIDIKAN SULTAN IDRIS (UPSI)'
CODE = 'AT20'
PROGRAMME = 'Ijazah Sarjana Muda Pendidikan (Matematik) dengan Kepujian'


def label(name, value, width=22):
    return L + name + ' ' * (width - len(name)) + ':   ' + value


def layout(name_line=None, title=TITLE, programme=CODE + ' - ' + PROGRAMME, intake='Semester 1 Sesi 2027/2028',
           report='14 September 2027 (Selasa)', offer='12 Julai 2027 / 7 Muharram 1449H', head_extra=(), extra=(),
           matric_line=None):
    lines = [
        R + 'Rujukan Tuan :', R + 'Rujukan Kami : UPSI/HEA/2027/123', R + 'Tarikh : ' + offer, R + MATRIC,
        matric_line if matric_line is not None else R + 'No. Matrik : ' + MATRIC,
        name_line if name_line is not None else L + NAME,
        L + 'NO 1 JALAN MAWAR', L + 'TAMAN BUNGA', *head_extra, L + '35900 TANJONG MALIM', L + 'PERAK',
        L + 'Saudara/i,', L + title,
        L + 'Sukacita dimaklumkan bahawa anda ditawarkan mengikuti program pengajian di UPSI seperti berikut:',
        label('Program', programme), label('Fakulti', 'Fakulti Sains dan Matematik'),
        label('Sesi Akademik', intake), label('Tempoh Pengajian', '8 Semester'),
        label('Tarikh Mendaftar', report), *extra,
        L + '2. Sekiranya saudara/i didapati memberi maklumat salah/tidak benar/memanipulasi maklumat dan tidak',
        L + 'memenuhi syarat kemasukan, pihak Universiti berhak menarik balik tawaran kemasukan saudara/i dengan',
        L + 'serta-merta.',
        L + '3. Tawaran ini adalah muktamad dan permohonan pertukaran program tidak akan dipertimbangkan.',
        L + 'Surat tawaran ini merupakan surat tawaran rasmi.',
        L + 'Sekian, terima kasih.', L + 'Ketua Timbalan Pendaftar', L + 'BAHAGIAN HAL EHWAL AKADEMIK',
        L + 'Universiti Pendidikan Sultan Idris',
    ]
    return '\n'.join(lines)


PAGE2 = '\n'.join(['MAKLUMAT PENDAFTARAN', 'Universiti Pendidikan Sultan Idris',
                   '1. Saudara/i hendaklah membawa dokumen asal.', 'www.upsi.edu.my'])
#: Page 2 as the samples print it: the programme repeated, wrapped, with fees, and a form link whose lower-case
#: path holds "sarjanamuda".
PAGE2_REPEAT = PAGE2 + '\n'.join(['', 'Yuran: AT20 - Ijazah Sarjana Muda Pendidikan', '(Matematik) dengan Kepujian',
                                  'RM 1,234.00', 'https://borang.upsi.edu.my/sarjanamuda/daftar2027'])


def plain(lay):
    return '\n'.join(' '.join(ln.split()) for ln in lay.splitlines() if ln.strip())


def run(lay=None, page2=None):
    lay = lay if lay is not None else layout()
    p1 = plain(lay)
    pages = [p1] + ([page2] if page2 is not None else [])
    return offer_parse.diagnose('\n'.join(pages), p1, lay, pages)


def why(d):
    return d['guard'] or ('empty:' + ','.join(d['empty_required']) if d['empty_required'] else None)


class UpsiLockTest(SimpleTestCase):
    def test_degree_letter_locks_with_no_ic(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane']), ('upsi', LANE))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), ('', 'none'))
        self.assertEqual((lock['programme'], lock['programme_code']), (PROGRAMME, CODE))
        self.assertEqual(lock['intake'], 'Semester 1 Sesi 2027/2028')
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('14 Sep 2027', 'Tarikh Mendaftar'))
        self.assertEqual(lock['offer_date'], '12 Julai 2027')
        self.assertEqual(lock['institution'], 'UNIVERSITI PENDIDIKAN SULTAN IDRIS')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_the_matric_is_never_stored(self):
        lock = run(page2=PAGE2_REPEAT)['locked']
        self.assertIsNotNone(lock)
        self.assertFalse(any(MATRIC in str(v) or MATRIC[1:] in str(v) for v in lock.values()))
        fields, _why = read_upsi(layout())
        self.assertFalse(any(MATRIC[1:] in str(v) for v in fields.values()))

    def test_offer_date_is_optional(self):
        lock = run(layout(offer='12 Julai 2027 / tarikh lain'))['locked']
        self.assertEqual(lock['offer_date'], '')

    def test_a_scan_refuses_no_layout(self):
        d = offer_parse.diagnose(plain(layout()), '', '', None)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('upsi', 'no_layout', None))


class UpsiNeverLocksTest(SimpleTestCase):
    def test_an_ic_shaped_number_refuses(self):
        for ic in ('990101145678', '990101-14-5678', '990101 - 14 - 5678', '990101.14.5678', '990101 14 5678'):
            with self.subTest(ic=ic):
                self.assertEqual(run(layout(head_extra=(L + 'No. K/P : ' + ic,)))['guard'], 'ic_printed')
                self.assertEqual(run(page2=PAGE2 + '\n' + ic)['guard'], 'ic_printed')
                self.assertEqual(letter_refusal(plain(layout()) + '\n' + ic), 'ic_printed')
                self.assertEqual(later_pages_refusal([PAGE2 + '\n' + ic], PROGRAMME, CODE, ''), 'ic_printed')
        self.assertEqual(run(layout(matric_line=R + 'No. Matrik : D202712345678'))['guard'], 'ic_printed')
        # the real matric (a letter and 11 digits), alone or with a year or a date after it, is not an IC
        self.assertIsNotNone(run(page2=PAGE2 + '\n' + MATRIC + ' 2027\nNo. Matrik : ' + MATRIC + ' 12.05.2027')['locked'])

    def test_every_ic_shape_refuses_raw_on_page_one_and_page_two(self):
        """Review 2: dash look-alikes, a slash, long white-space runs and an IC split over two lines refuse on page 1's
        raw layout and on a raw page 2; the matric before a date or a numbered line still locks."""
        from apps.scholarship.tests.test_offer_parse_uum import IC_SHAPES
        for ic in IC_SHAPES:
            with self.subTest(ic=ic):
                lay = layout(head_extra=(L + 'No. K/P :' + ' ' * 30 + ic,))
                self.assertEqual(read_upsi(lay), (None, 'ic_printed'))
                self.assertEqual(run(lay)['guard'], 'ic_printed')
                page2 = PAGE2 + '\n' + ' ' * 40 + 'No. K/P' + ' ' * 31 + ':' + ' ' * 7 + ic + ' ' * 20 + 'Tel'
                self.assertEqual(later_pages_refusal([page2], PROGRAMME, CODE, ''), 'ic_printed')
                self.assertEqual(run(page2=page2)['guard'], 'ic_printed')
        page2 = PAGE2 + '\n' + ' ' * 40 + 'No. Matrik :' + ' ' * 20 + MATRIC + '\n' + ' ' * 10 + '1. Bawa dokumen.'
        self.assertIsNotNone(run(page2=page2 + '\n' + MATRIC + '\n' + '12.05.2027')['locked'])

    def test_english_letter_refuses(self):
        lay = layout(title='OFFER OF ADMISSION TO UNIVERSITI PENDIDIKAN SULTAN IDRIS (UPSI)')
        d = run(lay)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('upsi', 'no_title', None))
        english = lay.replace('BAHAGIAN HAL EHWAL AKADEMIK', 'ACADEMIC AFFAIRS DIVISION')
        self.assertEqual(run(english)['guard'], 'no_title')

    def test_confirmation_and_status_letters_refuse(self):
        self.assertEqual(run(layout(extra=(L + 'SURAT PENGESAHAN',)))['guard'], 'status_letter')
        self.assertEqual(run(layout(title='PENGESAHAN TAWARAN KEMASUKAN'))['guard'], 'status_letter')
        self.assertEqual(letter_refusal('SURAT PENGESAHAN\nTAWARAN'), 'status_letter')

    def test_asasi_and_non_degree_refuse(self):
        for prog in ('AT20 - Asasi Sains', 'AT20 - Diploma Pendidikan', 'AT20 - Sarjana Pendidikan',
                     'AT20 - Sijil Pendidikan', 'AT20 - Ijazah Sarjana Muda Pendidikan (Persediaan)'):
            with self.subTest(prog=prog):
                d = run(layout(programme=prog))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('not_degree', 'asasi_ai_read'))

    def test_programme_shapes(self):
        self.assertEqual(run(layout(programme=PROGRAMME))['guard'], 'programme_shape')        # no code
        self.assertEqual(run(layout(extra=(label('Program', 'AT21 - Ijazah Sarjana Muda Sains'),)))['guard'],
                         'programme_twice')
        lay = layout().replace(label('Fakulti', 'Fakulti Sains dan Matematik') + '\n', '')
        self.assertEqual(run(lay)['guard'], 'programme_shape')
        self.assertIsNotNone(run(layout().replace('Program' + ' ' * 15 + ':   ', 'Program   :   '))['locked'])

    def test_name_must_be_read_exactly(self):
        for name_line in (L + 'ZORBEX QUENTARO A/L', L + 'Z9RBEX QUENTARO', L + NAME + '   EXTRA', ' ' * 14 + NAME):
            with self.subTest(name_line=name_line):
                d = run(layout(name_line=name_line))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_shape', 'no_head'))

    def test_a_name_must_be_proven_to_end(self):
        """Review 1: the line after the name must prove it ended (a digit, a comma or an address word opens it); a
        name broken over two lines, after a whole word or after a linker, never locks cut short. No IC is printed, so
        a lock here is the name alone: it must be whole."""
        for first, rest in (('ZORBEX QUENTARO', 'A/L ALFEN'), ('ZORBEX QUENTARO A/L', 'ALFEN'),
                            ('ZORBEX QUENTARO', 'ANAK ALFEN'), ('ZORBEX QUENTARO BIN', 'ALFEN'), ('ZORBEX', 'QUENTARO')):
            with self.subTest(first=first, rest=rest):
                d = run(layout(name_line=L + first + '\n' + L + rest))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_not_ended', 'name_shape'))
        for addr in ('KAMPUNG MAWAR', 'KG MAWAR', 'B-1-12 TAMAN MAWAR', 'A123B, JALAN 1/23', 'NO 9 ,', 'NO.12, JALAN 1/2'):
            with self.subTest(addr=addr):
                lay = layout().replace(L + 'NO 1 JALAN MAWAR', L + addr)
                self.assertEqual(run(lay)['locked']['candidate_name'], NAME)
        for nxt in ('MAWAR INDAH', 'SEKOLAH'):
            with self.subTest(nxt=nxt):
                self.assertEqual(run(layout().replace(L + 'NO 1 JALAN MAWAR', L + nxt))['guard'], 'name_not_ended')

    def test_head_must_hold(self):
        self.assertEqual(run(layout().replace('Rujukan Kami : UPSI/', 'Rujukan Kami : UUM/'))['guard'], 'no_head')
        self.assertEqual(run(layout(matric_line=R + 'No. Matrik :'))['guard'], 'no_head')
        self.assertEqual(run(layout().replace(L + 'Saudara/i,\n', ''))['guard'], 'no_head')

    def test_dates_and_session(self):
        self.assertEqual(run(layout(report='14 September 2030'))['guard'], 'dates_not_sane')
        self.assertEqual(why(run(layout(report='31 September 2027'))), 'empty:reporting_date')
        self.assertEqual(why(run(layout(report='14/09/2027'))), 'empty:reporting_date')
        self.assertEqual(run(layout(report='1 Ogos 2027', offer='12 September 2027'))['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(intake='Semester 1 Sesi 2027/2029'))['guard'], 'dates_not_sane')
        self.assertEqual(why(run(layout(intake='Sesi 2027/2028'))), 'empty:intake')

    def test_title_once(self):
        self.assertEqual(run(layout(extra=(L + TITLE,)))['guard'], 'no_title')
        self.assertEqual(run(layout(title=TITLE + ' SESI 2027/2028'))['guard'], 'no_title')

    def test_missing_owner_words_go_to_ai(self):
        for old, new in {'Tempoh Pengajian': 'Lama Pengajian', 'adalah muktamad': 'adalah tetap',
                         'Ketua Timbalan Pendaftar': 'Pendaftar'}.items():
            with self.subTest(old=old):
                self.assertEqual(run(layout().replace(old, new))['guard'], 'owner_words_missing')

    def test_the_genuine_note_is_excused_other_withdrawals_refuse(self):
        self.assertEqual(letter_refusal(plain(layout())), '')
        self.assertEqual(run(page2=PAGE2 + '\nTawaran ini telah DIBATALKAN.')['guard'], 'not_an_offer')
        self.assertEqual(run(page2=PAGE2 + '\nPihak Universiti telah menarik balik tawaran ini.')['guard'],
                         'not_an_offer')
        changed = layout().replace('dan tidak\n', 'dan\n')
        self.assertNotEqual(letter_refusal(plain(changed)), '')


class UpsiLaterPagesTest(SimpleTestCase):
    def test_the_repeat_with_fees_and_a_form_link_still_locks(self):
        self.assertEqual(later_pages_refusal([PAGE2_REPEAT], PROGRAMME, CODE, '14 September 2027'), '')
        self.assertIsNotNone(run(page2=PAGE2_REPEAT)['locked'])

    def test_conflicts_go_to_ai(self):
        cases = {'AT21 - Ijazah Sarjana Muda Sains': 'second_programme',
                 'Ijazah Sarjana Muda Sains Komputer': 'second_programme',
                 'Diploma Pendidikan': 'second_programme', 'Program Asasi': 'second_programme',
                 'https://BORANG.upsi.edu.my/SarjanaMuda/x': 'second_programme',
                 'Tarikh Mendaftar : 15 September 2027': 'second_date'}
        for extra, want in cases.items():
            with self.subTest(extra=extra):
                self.assertEqual(later_pages_refusal([PAGE2 + '\n' + extra], PROGRAMME, CODE, '14 September 2027'),
                                 want)
                self.assertEqual(run(page2=PAGE2 + '\n' + extra)['guard'], want)
        same = PAGE2 + '\nTarikh Mendaftar : 14 September 2027'
        self.assertEqual(later_pages_refusal([same], PROGRAMME, CODE, '14 September 2027'), '')

    def test_unknown_page_goes_to_ai(self):
        self.assertEqual(later_pages_refusal(['Resit Bayaran Yuran'], PROGRAMME, CODE, ''), 'unknown_page')
        self.assertEqual(run(page2='Resit Bayaran Yuran')['guard'], 'unknown_page')


class UpsiNoIcAndWiringTest(SimpleTestCase):
    def test_upsi_prints_no_ic_next_to_uum_only(self):
        self.assertEqual(offer_exact.ISSUER_PRINTS_NO_IC, frozenset({'ua:UUM', 'ua:UPSI', 'ua:UNIMAS', 'ua:UTHM'}))

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
        self.assertFalse(any(MATRIC[1:] in str(v) for v in ex['fields'].values()))

    def test_ink_targets_hold_no_ic_and_no_matric(self):
        phrases, values = ink_targets(run()['locked'], layout())
        self.assertEqual(len(phrases), 11)
        got = dict(values)
        self.assertNotIn('v:nric', got)
        self.assertFalse(any(MATRIC[1:] in v for v in got.values()))
        self.assertEqual((got['v:name'], got['v:code'], got['v:date']), (NAME, CODE, '14 September 2027'))
        self.assertEqual(got['v:offer_date'], '12 Julai 2027')
        self.assertEqual(set(read_upsi(layout())[0]), set(INK_LABELS) | set(NOT_PRINTED))
        self.assertTrue(set(INK_OPTIONAL) <= set(INK_LABELS))

    def test_family_and_lane_modules(self):
        text = plain(layout())
        self.assertEqual(offer_parse.family_of(text), 'upsi')
        self.assertEqual(offer_exact._rules_family(text), 'upsi')
        self.assertEqual(offer_exact._lane_module('upsi').LANE, 'ua:UPSI')
        why_ = {}
        offer_exact._note_ums_refusal(why_, text, 'no_layout')
        self.assertEqual(why_, {'lane': 'ua:UPSI', 'reason': 'read_no_layout'})
        self.assertFalse(is_upsi('UNIVERSITI PENDIDIKAN SULTAN IDRIS TANJONG MALIM'))
        self.assertFalse(is_upsi('UNIVERSITI UTARA MALAYSIA JABATAN HAL EHWAL AKADEMIK'))

    def test_not_inked_dispatches_to_upsi(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), 'ua:UPSI'), [])
            self.assertEqual(ink.call_args.kwargs['lane'], 'ua:UPSI')

    @override_settings(OCR_FIRST_LANES=[])
    def test_lane_off_by_default(self):
        text = plain(layout())
        why_ = {}
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(text, text)):
            self.assertIsNone(offer_exact.exact_offer_read(text, image=b'%PDF', content_type='application/pdf',
                                                           why=why_))
        self.assertEqual(why_, {'lane': 'ua:UPSI', 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=['ua:UPSI'])
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
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), ('ua:UPSI', ''))
