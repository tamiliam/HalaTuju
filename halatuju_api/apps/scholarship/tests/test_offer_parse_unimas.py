"""OCR-14 phase 2: the UNIMAS rules lane (`offer_parse_unimas`) and its no-IC lock (`offer_exact.ISSUER_PRINTS_NO_IC`,
owner 26 Nov: "Same as UUM"). The matric number is not an IC and is never stored; UNIMAS prints no reporting date and
none is guessed. Synthetic letters only (made-up names, numbers and addresses)."""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_parse_unimas import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, is_unimas, read_unimas
from apps.scholarship.offer_parse_unimas import unimas_ink_targets as ink_targets
from apps.scholarship.offer_parse_unimas import unimas_later_pages as later_pages_refusal
from apps.scholarship.offer_parse_unimas import unimas_letter_refusal as letter_refusal
from apps.scholarship.offer_parse_unimas import unimas_portal

NAME = 'ZORBEX QUENTARO ANAK ALFEN'
MATRIC = '271234'
L = '   '
V = ' ' * 39                                    # a wrapped value starts under its value
TITLE = 'Tawaran Kemasukan Ke Universiti Malaysia Sarawak'
INTAKE = 'Semester 1 Sesi 2027/2028'
CODE = 'UW6481001'
PROGRAMME = 'Sarjana Muda Sains Komputer dan Teknologi Maklumat dengan Kepujian'
GREETING = (L + 'Tahniah!    Saudara/saudari     adalah   ditawarkan    tempat    untuk   mengikuti    pengajian    '
            'Ijazah  Sarjana')


def label(name, value):
    return '     ' + name + ' ' * (32 - len(name)) + ': ' + value


def layout(name_line=None, first=L + 'Pejabat Timbalan Naib Canselor', title=TITLE + ' ' + INTAKE,
           programme=('Sarjana Muda Sains Komputer dan Teknologi Maklumat', V + 'dengan Kepujian - ' + CODE),
           offer='12 Ogos 2027', matric='No Matrik  : ' + MATRIC, head_extra=(), extra=(), venue=None,
           fee_code=CODE, greeting=GREETING):
    lines = [
        first, L + '(Akademik dan Antarabangsa)', L + "Deputy Vice-Chancellor's Office (Academic and International)",
        L + 'Pusat Pengajian Prasiswazah', L + 'Centre for Undergraduate Studies', L + offer,
        name_line if name_line is not None else L + NAME,
        L + 'C-9-9, TINGKAT 9, BLOK C', L + 'JALAN MAWAR, TAMAN BUNGA', *head_extra,
        L + '93400 KUCHING' + ' ' * 70 + matric, L + 'Saudara/Saudari', L + title, greeting,
        L + 'Muda di Universiti Malaysia Sarawak (UNIMAS) dalam Program/Fakulti seperti berikut:',
        label('Program', programme[0]), *programme[1:],
        label('Fakulti', 'Fakulti Sains Komputer dan Teknologi Maklumat'),
        label('Tempoh Pengajian', '8 Semester'), label('Mod Pengajian', 'Sepenuh Masa'),
        *(venue or (label('Lokasi Pendaftaran dan', 'Kolej Mawar'), '     Kolej Kediaman')),
        label('Yuran Semester  1 Sesi', 'RM1,234.00'), '     2027/2028', *extra,
        L + 'Tawaran kemasukan ini turut tertakluk kepada perkara seperti di lampiran.',
        '       Nama Program Pengajian             Kos yuran pengajian',
        '     Sarjana Muda Sains Komputer dan    RM1,234.00', '     Teknologi Maklumat dengan Kepujian -',
        '     ' + fee_code, L + 'Sekian, terima kasih.', L + 'Qarim Velto bin Duran', L + 'Pendaftar',
        ' ' * 95 + 'UNTUK SEMAKAN',
        L + '**Surat tawaran ini bukan merupakan surat tawaran rasmi dan hanya boleh digunakan sebagai rujukan sahaja.',
        L + '**Surat ini dijana oleh komputer, oleh itu tandatangan tidak diperlukan.',
        '94300 Kota Samarahan, Sarawak, MALAYSIA', 'Tel +60 82 581 000/1234', 'E-mel admisi@unimas.my',
    ]
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


class UnimasLockTest(SimpleTestCase):
    def test_degree_letter_locks_with_no_ic_and_no_reporting_date(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane']), ('unimas', LANE))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), ('', 'none'))
        self.assertEqual((lock['programme'], lock['programme_code']), (PROGRAMME, CODE))
        self.assertEqual(lock['intake'], INTAKE)
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('', ''))
        self.assertEqual(lock['offer_date'], '12 Ogos 2027')
        self.assertEqual(lock['institution'], 'UNIVERSITI MALAYSIA SARAWAK')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_programme_on_one_line_or_two_wraps(self):
        one = run(layout(programme=(PROGRAMME + ' - ' + CODE,)))['locked']
        self.assertEqual((one['programme'], one['programme_code']), (PROGRAMME, CODE))
        two = run(layout(programme=('Sarjana Muda Sains Komputer dan', V + 'Teknologi Maklumat',
                                    V + 'dengan Kepujian - ' + CODE)))['locked']
        self.assertEqual(two['programme'], PROGRAMME)

    def test_a_dated_note_in_the_venue_is_never_a_reporting_date(self):
        venue = (label('Lokasi Pendaftaran dan', 'Semakan kolej kediaman mulai 20 Ogos 2027 jam 10 pagi di'),
                 '     Kolej Kediaman' + ' ' * 20 + 'https://kolej.unimas.my/eKolej')
        lock = run(layout(venue=venue))['locked']
        self.assertIsNotNone(lock)
        self.assertEqual((lock['reporting_date'], lock['reporting_venue']), ('', ''))

    def test_the_matric_is_never_stored(self):
        lock = run()['locked']
        self.assertFalse(any(MATRIC in str(v) for v in lock.values()))
        fields, _why = read_unimas(layout())
        self.assertFalse(any(MATRIC in str(v) for v in fields.values()))

    def test_a_scan_refuses_no_layout(self):
        d = offer_parse.diagnose(plain(layout()), '', '', None)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('unimas', 'no_layout', None))


class UnimasNeverLocksTest(SimpleTestCase):
    def test_every_ic_shape_refuses_on_page_one_and_page_two(self):
        """Any 12-digit IC-like number refuses: raw spacing, an en dash, a minus sign, a slash, a split over a line
        break; on page 1's layout, on page 1's plain layer and on a page 2."""
        from apps.scholarship.tests.test_offer_parse_uum import IC_SHAPES
        for ic in IC_SHAPES + ('990101145678', '990101-14-5678', '990101 – 14 – 5678', '990101−14−5678'):
            with self.subTest(ic=ic):
                lay = layout(head_extra=(L + 'No. K/P :' + ' ' * 30 + ic,))
                self.assertEqual(read_unimas(lay), (None, 'ic_printed'))
                self.assertEqual(run(lay)['guard'], 'ic_printed')
                self.assertEqual(letter_refusal(plain(layout()) + '\n' + ic), 'ic_printed')
                page2 = 'Universiti Malaysia Sarawak\n' + ' ' * 40 + 'No. K/P' + ' ' * 31 + ':' + ' ' * 7 + ic
                self.assertEqual(run(page2=page2)['guard'], 'ic_printed')
                p1 = plain(layout())
                d = offer_parse.diagnose(p1, p1 + '\n' + ic, layout(), [p1])
                self.assertEqual(d['guard'], 'ic_printed')

    def test_a_matric_is_never_taken_for_an_ic(self):
        self.assertEqual(run(layout(matric='No Matrik  : 990101145678'))['guard'], 'ic_printed')
        for matric in ('No Matrik  : 27123', 'No Matrik  : 2712345', 'No Matrik  :', 'Matrik : ' + MATRIC):
            with self.subTest(matric=matric):
                self.assertEqual(run(layout(matric=matric))['guard'], 'no_head')
        lay = layout(head_extra=(L + 'No Matrik  : ' + MATRIC,))
        self.assertIn(run(lay)['guard'], ('no_head', 'name_not_ended'))

    def test_the_old_layout_refuses(self):
        old = layout(first=L + 'Pejabat Pendaftar', matric='No Matrik  : 27123').replace(
            L + '(Akademik dan Antarabangsa)\n', L + "Registrar's Office\n")
        self.assertEqual(read_unimas(old)[1], 'old_layout')
        self.assertEqual(run(old)['guard'], 'old_layout')
        self.assertEqual(run(layout(first=L + 'PEJABAT PENDAFTAR'))['guard'], 'old_layout')

    def test_diploma_asasi_and_non_degree_refuse(self):
        for prog in ('Diploma Sains Komputer - ' + CODE, 'Asasi Sains - ' + CODE, 'Sarjana Sains Komputer - ' + CODE,
                     'Sarjana Muda Sains (Persediaan) - ' + CODE, 'Sarjana Muda Diploma Lanjutan - ' + CODE):
            with self.subTest(prog=prog):
                d = run(layout(programme=(prog,)))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('programme_shape', 'not_degree', 'asasi_ai_read'))
        diploma = layout(programme=('Diploma Sains Komputer - ' + CODE,),
                         greeting=GREETING.replace('Ijazah  Sarjana', 'Diploma'))
        self.assertIsNone(run(diploma)['locked'])

    def test_confirmation_and_fail_letters_refuse(self):
        self.assertEqual(run(layout(extra=(L + 'SURAT PENGESAHAN',)))['guard'], 'status_letter')
        self.assertEqual(run(layout(extra=(L + 'PENGESAHAN PENDAFTARAN',)))['guard'], 'status_letter')
        for line in ('Permohonan saudara/saudari TIDAK BERJAYA.', 'Tawaran ini telah DIBATALKAN.',
                     'Tawaran ini telah ditarik balik.'):
            with self.subTest(line=line):
                self.assertEqual(run(layout(extra=(L + line,)))['guard'], 'not_an_offer')
        self.assertEqual(letter_refusal(plain(layout())), '')

    def test_any_other_portal_tell_refuses(self):
        self.assertFalse(unimas_portal(plain(layout())))
        self.assertTrue(unimas_portal(plain(layout()) + '\nSila cetak slip ini'))
        self.assertTrue(unimas_portal(plain(layout()) + '\nTahniah! Anda layak menerima tawaran'))
        self.assertTrue(unimas_portal(plain(layout()) + '\n' + plain(GREETING) + ' di Universiti Malaysia Sarawak'))
        self.assertIsNone(run(layout(extra=(L + 'SEMAKAN TAWARAN',)))['locked'])

    def test_programme_shapes(self):
        self.assertEqual(run(layout(programme=(PROGRAMME,)))['guard'], 'programme_shape')            # no code
        self.assertEqual(run(layout(programme=(PROGRAMME + ' - UW64810',)))['guard'], 'programme_shape')
        three = ('Sarjana Muda Sains', V + 'Komputer dan', V + 'Teknologi Maklumat', V + 'dengan Kepujian - ' + CODE)
        self.assertEqual(run(layout(programme=three))['guard'], 'programme_shape')            # three wraps
        self.assertEqual(run(layout(programme=('Sarjana Muda Sains Komputer dan Teknologi Maklumat',
                                               ' ' * 10 + 'dengan Kepujian - ' + CODE)))['guard'], 'programme_shape')
        lay = layout().replace(label('Fakulti', 'Fakulti Sains Komputer dan Teknologi Maklumat') + '\n', '')
        self.assertEqual(run(lay)['guard'], 'programme_shape')
        self.assertEqual(run(layout(extra=(label('Program', 'Sarjana Muda Sains - UW6481002'),)))['guard'],
                         'programme_twice')
        self.assertEqual(run(layout(fee_code='UW6481002'))['guard'], 'second_code')

    def test_name_must_be_read_exactly(self):
        for name_line in (L + 'ZORBEX QUENTARO ANAK', L + 'Z9RBEX QUENTARO', L + NAME + '   EXTRA', ' ' * 14 + NAME,
                          L + 'Zorbex Quentaro Anak Alfen'):
            with self.subTest(name_line=name_line):
                d = run(layout(name_line=name_line))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_shape', 'no_head'))

    def test_a_wrapped_name_never_locks_cut_short(self):
        """The line after the name must prove it ended (a digit, a comma or an address word opens it). NO'MAN and
        NO-MAN are a name's rest, not the address word NO."""
        for first, rest in (('ZORBEX QUENTARO', 'ANAK ALFEN'), ('ZORBEX QUENTARO ANAK', 'ALFEN'),
                            ('ZORBEX QUENTARO BINTI', 'ALFEN'), ('ZORBEX', 'QUENTARO'), ('ZORBEX QUENTARO', "NO'MAN"),
                            ('ZORBEX QUENTARO', 'NO-MAN'), ('ZORBEX QUENTARO A/L', 'ALFEN')):
            with self.subTest(first=first, rest=rest):
                d = run(layout(name_line=L + first + '\n' + L + rest))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_not_ended', 'name_shape'))
        for addr in ('KAMPUNG MAWAR', 'B-1-12 TAMAN MAWAR', 'NO 9 ,', 'NO.12, JALAN 1/2', 'LOT 99 LORONG 1'):
            with self.subTest(addr=addr):
                lay = layout().replace(L + 'C-9-9, TINGKAT 9, BLOK C', L + addr)
                self.assertEqual(run(lay)['locked']['candidate_name'], NAME)

    def test_head_must_hold(self):
        self.assertEqual(run(layout().replace(L + 'Saudara/Saudari\n', ''))['guard'], 'no_head')
        self.assertEqual(run(layout(head_extra=(L + '1 Mei 2027',)))['guard'], 'no_head')     # two dates

    def test_dates_and_session(self):
        self.assertEqual(run(layout(offer='12 Ogos 2030'))['guard'], 'dates_not_sane')
        self.assertEqual(run(layout(title=TITLE + ' Semester 1 Sesi 2027/2029'))['guard'], 'dates_not_sane')
        self.assertEqual(why(run(layout(offer='31 September 2027'))), 'empty:offer_date')

    def test_title_once_with_its_session(self):
        self.assertEqual(run(layout(extra=(L + TITLE + ' ' + INTAKE,)))['guard'], 'no_title')
        self.assertEqual(run(layout(title=TITLE))['guard'], 'no_title')
        self.assertEqual(run(layout(title=TITLE.upper() + ' ' + INTAKE))['guard'], 'no_title')
        self.assertEqual(read_unimas(layout(title='Offer of Admission ' + INTAKE)), (None, 'no_title'))

    def test_missing_owner_words_go_to_ai(self):
        for old, new in {'Tempoh Pengajian': 'Lama Pengajian', 'Pendaftar\n': 'Ketua\n'}.items():
            with self.subTest(old=old):
                self.assertEqual(run(layout().replace(old, new))['guard'], 'owner_words_missing')

    def test_any_later_page_goes_to_ai(self):
        self.assertEqual(later_pages_refusal(['Universiti Malaysia Sarawak\nLampiran']), 'later_page')
        self.assertEqual(later_pages_refusal(['', '  ']), '')
        self.assertEqual(run(page2='Universiti Malaysia Sarawak\nLampiran')['guard'], 'later_page')


class UnimasNoIcAndWiringTest(SimpleTestCase):
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

    def test_r1_lock_writes_a_blank_reporting_date_over_a_prior_ai_date(self):
        # OCR-14 review r1 (the reviewer's case): an earlier AI read took the hostel note's date as the reporting
        # date; the UNIMAS lock (which reads none) must blank it, never keep it under a deterministic capture.
        venue = (label('Lokasi Pendaftaran dan', 'Semakan kolej kediaman mulai 20 Ogos 2027 jam 10 pagi di'),
                 '     Kolej Kediaman' + ' ' * 20 + 'https://kolej.unimas.my/eKolej')
        lay = layout(venue=venue)
        p1 = plain(lay)
        prior = {'fields': {'reporting_date': '20 Aug 2027', 'reporting_date_label': 'Lokasi Pendaftaran',
                            'offer_date': '1 Jan 2027', 'candidate_nric': '990101-14-5678',
                            'candidate_nric_source': 'label'}}
        ex = offer_exact.exact_read(p1, from_text_layer=True, page1_layer=p1, prior=prior, profile_nric='',
                                    page1_layout=lay, page_texts=[p1])
        self.assertIsNotNone(ex)
        self.assertEqual(ex['capture'], 'deterministic')
        f = ex['fields']
        self.assertEqual((f['reporting_date'], f['reporting_date_label']), ('', ''))
        self.assertEqual(f['offer_date'], '12 Ogos 2027')                       # the lane's own read wins
        self.assertEqual((f['candidate_nric'], f['candidate_nric_source']), ('', 'none'))

    def test_ink_targets_hold_no_ic_no_matric_no_date(self):
        phrases, values = ink_targets(run()['locked'], layout())
        self.assertEqual(len(phrases), 6)
        got = dict(values)
        self.assertFalse({'v:nric', 'v:date'} & set(got))
        self.assertFalse(any(MATRIC in v for v in got.values()))
        self.assertEqual((got['v:name'], got['v:code'], got['v:intake']), (NAME, CODE, INTAKE))
        self.assertEqual(got['v:offer_date'], '12 Ogos 2027')
        self.assertEqual(set(read_unimas(layout())[0]), set(INK_LABELS) | set(NOT_PRINTED))
        self.assertTrue(set(INK_OPTIONAL) <= set(INK_LABELS))

    def test_family_and_lane_modules(self):
        text = plain(layout())
        self.assertEqual(offer_parse.family_of(text), 'unimas')
        self.assertEqual(offer_exact._rules_family(text), 'unimas')
        self.assertEqual(offer_exact._lane_module('unimas').LANE, 'ua:UNIMAS')
        why_ = {}
        offer_exact._note_ums_refusal(why_, text, 'no_layout')
        self.assertEqual(why_, {'lane': 'ua:UNIMAS', 'reason': 'read_no_layout'})
        self.assertFalse(is_unimas('UNIVERSITI MALAYSIA SARAWAK KOTA SAMARAHAN'))
        self.assertFalse(is_unimas('UNIVERSITI MALAYSIA SABAH PUSAT PENGAJIAN PRASISWAZAH'))

    def test_not_inked_dispatches_to_unimas(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), 'ua:UNIMAS'), [])
            self.assertEqual(ink.call_args.kwargs['lane'], 'ua:UNIMAS')

    @override_settings(OCR_FIRST_LANES=[])
    def test_lane_off_by_default(self):
        text = plain(layout())
        why_ = {}
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(text, text)):
            self.assertIsNone(offer_exact.exact_offer_read(text, image=b'%PDF', content_type='application/pdf',
                                                           why=why_))
        self.assertEqual(why_, {'lane': 'ua:UNIMAS', 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=['ua:UNIMAS'])
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
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), ('ua:UNIMAS', ''))
