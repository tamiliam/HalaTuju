"""OCR-13 phase 3: the UUM rules lane (`offer_parse_uum`) and its no-IC lock (`offer_exact.ISSUER_PRINTS_NO_IC`).
Synthetic letters only (made-up names, numbers and addresses)."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_parse_uum import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, ic_printed, not_degree, read_uum
from apps.scholarship.offer_parse_uum import uum_ink_targets as ink_targets
from apps.scholarship.offer_parse_uum import uum_later_pages as later_pages_refusal
from apps.scholarship.offer_parse_uum import uum_letter_refusal as letter_refusal

NAME = 'ZORBEX QUENTARO BIN ALFEN'
BRACKET = '418273'                                # the 6-digit number UUM prints after the name: NOT an IC
L, R = ' ' * 26, ' ' * 91
PROGRAMME = 'SARJANA MUDA PERAKAUNAN DENGAN KEPUJIAN'


def layout(name_line=None, title=None, programme=':SARJANA MUDA PERAKAUNAN', wrap=(' ' * 40 + 'DENGAN KEPUJIAN',),
           date='14 September 2027', offer=' 2 Ogos 2027', extra=(), head_extra=()):
    lines = [
        L + 'JABATAN HAL EHWAL AKADEMIK', L + 'ACADEMIC AFFAIRS DEPARTMENT', L + 'Universiti Utara Malaysia',
        L + '06010 UUM SINTOK', L + 'KEDAH DARUL AMAN' + ' ' * 40 + 'Tel : 04-928 4000',
        L + 'MALAYSIA' + ' ' * 48 + 'Faks (Fax) : 04-928 4001',
        R + 'Laman Web (Web) : www.uum.edu.my', R + 'Tarikh :' + offer, R + 'Rujukan  : UUM/HEA/K-12',
        name_line if name_line is not None else NAME + ' (' + BRACKET + ')',
        'NO 1 JALAN MAWAR', 'TAMAN BUNGA, 06000 JITRA', 'KEDAH', *head_extra, 'Saudara/i,',
        title or 'TAWARAN KEMASUKAN KE UNIVERSITI UTARA MALAYSIA SEMESTER PERTAMA SESI 2027/2028',
        'Tahniah  kerana  saudara/i  berjaya  dipilih  untuk  mengikuti  program  pengajian  di  Universiti  Utara'
        '  Malaysia  (UUM)',
        'seperti berikut:',
        '     Program Pengajian' + ' ' * 16 + programme, *wrap,
        '     Pusat Pengajian / Kolej' + ' ' * 10 + ': PUSAT PENGAJIAN PERAKAUNAN',
        '     Tempoh Pengajian' + ' ' * 17 + ': 4 TAHUN',
        '     Syarat-Syarat Tawaran' + ' ' * 12 + ': Rujuk Lampiran A (PENTING)',
        'Saudara/i dipohon mengambil tindakan seperti berikut:',
        '     Proses Pendaftaran Atas Talian' + ' ' * 5 + ': 1 - 5 September 2027',
        '     Pautan Pendaftaran' + ' ' * 17 + ': admission.uum.edu.my',
        '     Penginapan' + ' ' * 25 + ': Disediakan',
        '     Tarikh Pendaftaran Fizikal (UUM)' + ' ' * 8 + ': ' + date,
        *extra,
        'Sekian, terima kasih.', 'Universiti Pengurusan Terkemuka',
    ]
    return '\n'.join(lines)


PAGE2 = '\n'.join(['LAMPIRAN A', 'SYARAT-SYARAT TAWARAN', 'Universiti Utara Malaysia',
                   '1. Saudara/i hendaklah mendaftar pada tarikh yang ditetapkan.', 'www.uum.edu.my'])


def plain(lay):
    return '\n'.join(' '.join(ln.split()) for ln in lay.splitlines() if ln.strip())


def run(lay=None, page2=None, pages=None):
    lay = lay if lay is not None else layout()
    p1 = plain(lay)
    page_list = pages if pages is not None else [p1] + ([page2] if page2 is not None else [])
    return offer_parse.diagnose('\n'.join([p1] + page_list[1:]), p1, lay, page_list)


def why(d):
    return d['guard'] or ('empty:' + ','.join(d['empty_required']) if d['empty_required'] else None)


class UumLockTest(SimpleTestCase):
    def test_degree_letter_locks_with_no_ic(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane']), ('uum', LANE))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), ('', 'none'))
        self.assertEqual(lock['programme'], PROGRAMME)
        self.assertEqual(lock['intake'], 'SEMESTER PERTAMA SESI 2027/2028')
        self.assertEqual(lock['reporting_date'], '14 Sep 2027')
        self.assertEqual(lock['offer_date'], '2 Ogos 2027')
        self.assertEqual(lock['institution'], 'UNIVERSITI UTARA MALAYSIA')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_the_bracket_number_is_never_stored(self):
        for name_line in (NAME + ' (' + BRACKET + ')', NAME + '(' + BRACKET + ')'):
            with self.subTest(name_line=name_line):
                lock = run(layout(name_line=name_line))['locked']
                self.assertEqual(lock['candidate_name'], NAME)
                self.assertFalse(any(BRACKET in str(v) for v in lock.values()))

    def test_programme_shapes(self):
        lock = run(layout(programme=': ' + PROGRAMME, wrap=()))['locked']
        self.assertEqual(lock['programme'], PROGRAMME)
        lock = run(layout(programme=':SARJANA MUDA SAINS DENGAN', wrap=(' ' * 39 + 'KEPUJIAN (TEKNOLOGI MAKLUMAT)',)))
        self.assertEqual(lock['locked']['programme'], 'SARJANA MUDA SAINS DENGAN KEPUJIAN (TEKNOLOGI MAKLUMAT)')
        self.assertEqual(run(layout(wrap=('DENGAN KEPUJIAN',)))['guard'], 'programme_shape')   # not indented
        self.assertEqual(run(layout(wrap=(' ' * 40 + 'A', ' ' * 40 + 'B', ' ' * 40 + 'C')))['guard'],
                         'programme_shape')

    def test_a_scan_refuses_no_layout(self):
        d = offer_parse.diagnose(plain(layout()), '', '', None)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('uum', 'no_layout', None))


class UumNeverLocksTest(SimpleTestCase):
    def test_english_admission_letter_never_locks(self):
        lay = layout(title='OFFER OF ADMISSION TO UNIVERSITI UTARA MALAYSIA FIRST SEMESTER SESSION 2027/2028')
        d = run(lay)
        self.assertEqual((d['family'], d['guard'], d['locked']), ('uum', 'no_title', None))

    def test_pengesahan_letter_never_locks(self):
        for lay in (layout(title='PENGESAHAN TAWARAN KEMASUKAN KE UNIVERSITI UTARA MALAYSIA SESI 2027/2028'),
                    layout(extra=['Surat ini adalah PENGESAHAN senat.']), layout(extra=['P E N G E S A H A N'])):
            with self.subTest(lay=lay[-80:]):
                d = run(lay)
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'status_letter')
        self.assertEqual(letter_refusal('SURAT PENGESAHAN\nTAWARAN'), 'status_letter')

    def test_non_degree_programmes_go_to_ai(self):
        for prog in ('DIPLOMA PERAKAUNAN', 'ASASI PENGURUSAN', 'PRA SISWAZAH', 'SIJIL PERAKAUNAN',
                     'FOUNDATION IN MANAGEMENT', 'SARJANA MUDA PERAKAUNAN DIPLOMA', 'SARJANA MUDA PRA PERAKAUNAN',
                     'SARJANA MUDA (MATRIKULASI)', 'SARJANA MUDA PERSEDIAAN', 'CERTIFICATE IN LAW',
                     'SARJANA MUDA D.I.P.L.O.M.A', 'Sarjana Muda Perakaunan', 'SARJANA PERAKAUNAN'):
            with self.subTest(prog=prog):
                d = run(layout(programme=':' + prog, wrap=()))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('not_degree', 'asasi_ai_read'))
        self.assertTrue(not_degree('SARJANA MUDA DІPLOMA'))                      # Cyrillic І
        d = run(layout(wrap=(' ' * 40 + 'DENGAN KEPUJIAN DIPLOMA',)))
        self.assertEqual(d['guard'], 'not_degree')                                # in the wrapped line too

    def test_any_ic_like_number_refuses(self):
        for ic in ('990101-14-5678', '990101145678', '990101 14 5678', '1234567890123', '990101 - 14 - 5678',
                   '990101.14.5678', '990101 . 14 . 5678', '990101-14 5678', '990101  14  5678'):
            with self.subTest(ic=ic):
                self.assertTrue(ic_printed('No. K/P: ' + ic))
                d = run(layout(head_extra=['No. K/P : ' + ic]))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'ic_printed')
                self.assertEqual(later_pages_refusal([PAGE2 + '\n' + ic], PROGRAMME, ''), 'ic_printed')
                self.assertEqual(letter_refusal(plain(layout()) + '\n' + ic), 'ic_printed')
        self.assertFalse(ic_printed(NAME + ' (' + BRACKET + ') 06010 Tel : 04-928 4000'))
        for not_ic in ('(' + BRACKET + ')', NAME + ' (' + BRACKET + ') 2027', 'No. Matrik : D20271234567',
                       'D20271234567 2027', '99010114567', '990101-14-567', '12.05.2027', '(603) 5544 3000'):
            with self.subTest(not_ic=not_ic):
                self.assertFalse(ic_printed(not_ic))

    def test_an_ic_in_the_plain_layer_only_refuses(self):
        lay = layout()
        p1 = plain(lay) + '\n990101-14-5678'
        d = offer_parse.diagnose(p1, p1, lay, [p1])
        self.assertIsNone(d['locked'])
        self.assertEqual(d['guard'], 'ic_printed')

    def test_name_must_be_read_exactly(self):
        for name_line in (NAME, NAME + ' (12345)', 'ZORBEX QUENTARO BIN (' + BRACKET + ')',
                          ' ' * 8 + NAME + ' (' + BRACKET + ')', NAME + ' (' + BRACKET + ')   EXTRA', 'Z9RBEX (418273)'):
            with self.subTest(name_line=name_line):
                d = run(layout(name_line=name_line))
                self.assertIsNone(d['locked'])
                self.assertIn(d['guard'], ('name_shape', 'no_head'))

    def test_a_wrapped_name_never_locks(self):
        """Review 1: the bracket number ends the name, so a name broken over two lines (after a whole word or after a
        linker) has no bracket on its first line and refuses."""
        for first, rest in (('ZORBEX QUENTARO', 'BIN ALFEN (' + BRACKET + ')'),
                            ('ZORBEX QUENTARO BIN', 'ALFEN (' + BRACKET + ')')):
            with self.subTest(first=first):
                lay = layout(name_line=first + '\n' + rest)
                self.assertIsNone(run(lay)['locked'])
                self.assertEqual(run(lay)['guard'], 'name_shape')

    def test_dates_and_session(self):
        self.assertEqual(run(layout(date='14 September 2030'))['guard'], 'dates_not_sane')
        self.assertEqual(why(run(layout(date='31 September 2027'))), 'empty:reporting_date')
        self.assertEqual(why(run(layout(date='14/09/2027'))), 'empty:reporting_date')
        self.assertEqual(run(layout(offer=' 2 Oktober 2027'))['guard'], 'dates_not_sane')   # offered after
        bad = 'TAWARAN KEMASUKAN KE UNIVERSITI UTARA MALAYSIA SESI 2027/2029'
        self.assertEqual(run(layout(title=bad))['guard'], 'dates_not_sane')
        self.assertEqual(why(run(layout(title='TAWARAN KEMASUKAN KE UNIVERSITI UTARA MALAYSIA'))), 'empty:intake')

    def test_title_and_labels_once(self):
        self.assertEqual(run(layout(extra=['TAWARAN KEMASUKAN KE UNIVERSITI UTARA MALAYSIA SESI 2027/2028']))['guard'],
                         'no_title')
        self.assertEqual(run(layout(extra=['     Program Pengajian    : SARJANA MUDA UNDANG-UNDANG']))['guard'],
                         'programme_twice')
        self.assertEqual(why(run(layout(extra=['     Tarikh Pendaftaran Fizikal (UUM)   : 15 September 2027']))),
                         'empty:reporting_date')

    def test_missing_owner_words_go_to_ai(self):
        for old, new in {'Tempoh Pengajian': 'Lama Pengajian', 'berjaya  dipilih': 'telah  dipilih'}.items():
            with self.subTest(old=old):
                self.assertEqual(run(layout().replace(old, new))['guard'], 'owner_words_missing')

    def test_withdrawal_refuses(self):
        self.assertEqual(run(page2=PAGE2 + '\nTawaran ini telah DIBATALKAN.')['guard'], 'not_an_offer')


class UumLaterPagesTest(SimpleTestCase):
    def test_footer_words_alone_still_lock(self):
        page = PAGE2 + '\nSekian, terima kasih. Universiti Pengurusan Terkemuka. Pendaftaran pelajar baharu.'
        self.assertEqual(later_pages_refusal([page], PROGRAMME, '14 September 2027'), '')
        self.assertIsNotNone(run(page2=page)['locked'])
        self.assertEqual(later_pages_refusal([PAGE2 + '\n' + PROGRAMME], PROGRAMME, '14 September 2027'), '')

    def test_conflicts_go_to_ai(self):
        cases = {'SARJANA MUDA UNDANG-UNDANG DENGAN KEPUJIAN': 'second_programme', 'DIPLOMA PERAKAUNAN': 'second_programme',
                 'Tarikh Pendaftaran Fizikal : 15 September 2027': 'second_date', '990101-14-5678': 'ic_printed'}
        for extra, want in cases.items():
            with self.subTest(extra=extra):
                self.assertEqual(later_pages_refusal([PAGE2 + '\n' + extra], PROGRAMME, '14 September 2027'), want)
                self.assertEqual(run(page2=PAGE2 + '\n' + extra)['guard'], want)
        same = PAGE2 + '\nTarikh Pendaftaran Fizikal : 14 September 2027'
        self.assertEqual(later_pages_refusal([same], PROGRAMME, '14 September 2027'), '')

    def test_unknown_page_goes_to_ai(self):
        self.assertEqual(later_pages_refusal(['Resit Bayaran Yuran'], PROGRAMME, '14 September 2027'), 'unknown_page')
        self.assertEqual(run(page2='Resit Bayaran Yuran')['guard'], 'unknown_page')


def _lock(lane, nric=''):
    """A diagnose result that locked on ``lane`` (the IC guard's input), for the exact_read IC tests."""
    return {'family': 'x', 'locked': {'candidate_name': NAME, 'candidate_nric': nric,
                                      'candidate_nric_source': 'label' if nric else 'none', 'programme': PROGRAMME,
                                      'institution': 'X', 'rules_lane': lane, '_family': 'x'},
            'guard': None, 'empty_required': [], 'portal': False}


class NoIcLockTest(SimpleTestCase):
    """Owner, 26 Nov: "Lock without IC" for ua:UUM ONLY; every other lane keeps "a blanked IC means NO lock"."""

    def test_only_uum_prints_no_ic(self):
        self.assertEqual(offer_exact.ISSUER_PRINTS_NO_IC, frozenset({'ua:UUM', 'ua:UPSI'}))

    def test_ums_and_uitm_still_refuse_without_an_ic(self):
        for lane in ('ua:UMS', 'ua:UiTM', ''):
            with self.subTest(lane=lane), mock.patch('apps.scholarship.offer_parse.diagnose', return_value=_lock(lane)):
                self.assertIsNone(offer_exact.exact_read('x', profile_nric='990101-14-5678'))

    def test_uum_with_an_ic_refuses(self):
        with mock.patch('apps.scholarship.offer_parse.diagnose', return_value=_lock('ua:UUM', '990101-14-5678')):
            self.assertIsNone(offer_exact.exact_read('x', profile_nric='990101-14-5678'))

    def test_uum_lock_stores_a_blank_ic_over_a_prior_ai_ic(self):
        lay = layout()
        p1 = plain(lay)
        prior = {'fields': {'candidate_nric': '990101-14-5678', 'candidate_nric_source': 'label'}}
        ex = offer_exact.exact_read(p1, from_text_layer=True, page1_layer=p1, prior=prior,
                                    profile_nric='990101-14-5678', page1_layout=lay, page_texts=[p1])
        self.assertIsNotNone(ex)
        self.assertEqual(ex['rules_lane'], LANE)
        self.assertEqual((ex['fields']['candidate_nric'], ex['fields']['candidate_nric_source']), ('', 'none'))
        self.assertTrue(ex['offer_reader_inputs']['nric_not_printed'])
        self.assertEqual(ex['offer_reader_inputs']['nric_check'], 'blank')

    def test_blank_uum_ic_is_never_an_ic_match(self):
        from apps.scholarship.pathway_engine import _ic_status, student_offer_check
        self.assertEqual(_ic_status('', '990101-14-5678', True), 'unreadable')
        lay = layout()
        p1 = plain(lay)
        ex = offer_exact.exact_read(p1, from_text_layer=True, page1_layer=p1, profile_nric='990101-14-5678',
                                    page1_layout=lay, page_texts=[p1])
        doc = SimpleNamespace(vision_fields={**ex, 'student_verdict': 'ok'}, doc_type='offer_letter',
                              application=SimpleNamespace(profile=SimpleNamespace(nric='990101-14-5678', name=NAME)))
        self.assertEqual(student_offer_check(doc)['ic'], 'not_printed')   # OCR-13: grey, never 'match'
        doc.vision_fields['fields']['institution'] = ''                  # the lock flag alone carries it
        self.assertEqual(student_offer_check(doc)['ic'], 'not_printed')


class UumWiringTest(SimpleTestCase):
    def test_ink_targets_hold_no_ic(self):
        d = run()
        phrases, values = ink_targets(d['locked'], layout())
        self.assertEqual(len(phrases), 7)
        got = dict(values)
        self.assertNotIn('v:nric', got)
        self.assertFalse(any(BRACKET in v for v in got.values()))
        self.assertEqual(got['v:date'], '14 September 2027')
        self.assertEqual(got['v:name'], NAME)
        self.assertEqual(set(read_uum(layout())[0]), set(INK_LABELS) | set(NOT_PRINTED))
        self.assertTrue(set(INK_OPTIONAL) <= set(INK_LABELS))

    def test_family_and_lane_modules(self):
        text = plain(layout())
        self.assertEqual(offer_parse.family_of(text), 'uum')
        self.assertEqual(offer_exact._rules_family(text), 'uum')
        self.assertEqual(offer_exact._lane_module('uum').LANE, 'ua:UUM')
        why_ = {}
        offer_exact._note_ums_refusal(why_, text, 'no_layout')
        self.assertEqual(why_, {'lane': 'ua:UUM', 'reason': 'read_no_layout'})

    def test_not_inked_dispatches_to_uum(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), 'ua:UUM'), [])
            self.assertEqual(ink.call_args.kwargs['lane'], 'ua:UUM')

    @override_settings(OCR_FIRST_LANES=[])
    def test_lane_off_by_default(self):
        text = plain(layout())
        why_ = {}
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(text, text)):
            self.assertIsNone(offer_exact.exact_offer_read(text, image=b'%PDF', content_type='application/pdf',
                                                           why=why_))
        self.assertEqual(why_, {'lane': 'ua:UUM', 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=['ua:UUM'])
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
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), ('ua:UUM', ''))
