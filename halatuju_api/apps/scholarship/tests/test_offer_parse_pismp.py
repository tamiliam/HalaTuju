"""OCR-19: the PISMP rules lane (`offer_parse_pismp`): a digital Institut Pendidikan Guru Malaysia offer letter for
the teacher-training degree, read from its page-1 layout on the owner's anchors only (name after NAMA, IC after NO.
KAD PENGENALAN, the PISMP title plus BIDANG PENGKHUSUSAN, the campus after TEMPAT PENGAJIAN, the reporting date after
TARIKH PENDAFTARAN). Any letter that does not fit refuses. The lane ships OFF. Synthetic letters only (made-up names,
numbers and addresses)."""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_owner_words import OWNER_WORDS, missing
from apps.scholarship.offer_parse_pismp import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, REPORT_LABEL, is_pismp
from apps.scholarship.offer_parse_pismp import pismp_ink_targets, pismp_later_pages, pismp_letter_refusal, read_pismp

BASE = ' ' * 10
NAME = 'ZORBEX QUENTARO A/L ALFEN'
IC = '000000-00-0000'
BIDANG = 'PENDIDIKAN MATEMATIK (SEKOLAH RENDAH)'
SESSION = '2026/2032'
CAMPUS_ROW = 'INSTITUT PENDIDIKAN GURU KAMPUS CONTOH'
ADDRESS = ('JALAN CONTOH 3,', '01000 KANGAR,', 'PERLIS')
REPORT = '8 OGOS 2026'
LETTERHEAD = ('KEMENTERIAN PENDIDIKAN MALAYSIA', 'INSTITUT PENDIDIKAN GURU MALAYSIA', 'ARAS 1, BLOK CONTOH',
              'LAMAN WEB : WWW.IPGM.EXAMPLE')
TITLE = ('TAWARAN RASMI MENGIKUTI PROGRAM IJAZAH SARJANA MUDA PERGURUAN (PISMP) AMBILAN 2026',)
INTRO = ('Dengan segala hormatnya saya merujuk perkara di atas.',
         '2. Sukacita dimaklumkan bahawa tuan/puan ditawarkan mengikuti program seperti butiran berikut:')
NOTES = ('3. Tuan/puan dikehendaki melapor diri pada tarikh yang ditetapkan.',
         '4. Tawaran ini akan TERBATAL dengan sendirinya sekiranya tuan/puan tidak melapor diri.',
         'Sekian, terima kasih.', '(QARIM VELTO BIN DURAN)', 'Bagi pihak Rektor')


def head(label, value):
    return BASE + label.ljust(20) + ': ' + value


def row(label, value):
    return ' ' * 14 + label.ljust(24) + ':  ' + value


def address_line(value):
    return ' ' * 14 + ' ' * 24 + '   ' + value


def table(bidang=BIDANG, session=SESSION, campus=CAMPUS_ROW, address=ADDRESS, report=REPORT, rows=None):
    rows = rows if rows is not None else (
        ('BIDANG PENGKHUSUSAN', bidang), ('MOD PENGAJIAN', 'SEPENUH MASA'), ('TEMPOH PENGAJIAN', '6 TAHUN'),
        ('AMBILAN/KELUARAN', session), ('TEMPAT PENGAJIAN', campus), ('TARIKH PENDAFTARAN', report))
    out = []
    for label, value in rows:
        out.append(row(label, value))
        if label == 'TEMPAT PENGAJIAN':
            out += [address_line(a) for a in address]
    return out


def layout(name=NAME, ic=IC, title=TITLE, tab=None, notes=NOTES, heads=None, letterhead=LETTERHEAD, extra=()):
    heads = heads if heads is not None else (('Ruj. Kami', 'IPGM.600-2/1/3 JLD.9 (12)'), ('Tarikh', '1 Julai 2026'),
                                             ('NAMA', name), ('NO. KAD PENGENALAN', ic))
    lines = [*(BASE + x for x in letterhead), *(head(k, v) for k, v in heads), BASE + 'Tuan/Puan,',
             *(BASE + x for x in title), *(BASE + x for x in INTRO), *(tab if tab is not None else table()),
             *(BASE + x for x in (*extra, *notes))]
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


class PismpLockTest(SimpleTestCase):
    def test_a_clean_letter_locks(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane'], lock['_family']), ('pismp', LANE, 'pismp'))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), (IC, 'label'))
        self.assertEqual((lock['programme'], lock['bidang_pengkhususan']), ('IJAZAH SARJANA MUDA PERGURUAN', BIDANG))
        self.assertEqual((lock['institution'], lock['campus']), ('INSTITUT PENDIDIKAN GURU', 'KAMPUS CONTOH'))
        self.assertEqual(lock['intake'], 'AMBILAN 2026')
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('8 Aug 2026', REPORT_LABEL))
        self.assertEqual((lock['offer_date'], lock['reporting_venue'], lock['stream']), ('', '', ''))
        self.assertEqual(lock['issuer'], 'Institut Pendidikan Guru Malaysia, Kementerian Pendidikan')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_measured_variants_still_lock(self):
        touching = table(rows=None)
        touching = [ln.replace(':  ', ':') for ln in touching]                 # the colon touches the value
        for lay in (layout(tab=table(address=ADDRESS[:2])), layout(tab=table(address=ADDRESS + ('MALAYSIA',))),
                    layout(tab=touching), layout(ic='000000000000'),
                    layout(tab=table(session='2026/2030'))):
            with self.subTest(lines=lay.count('\n'), size=len(lay)):
                self.assertIsNotNone(run(lay)['locked'], why(run(lay)))

    def test_is_pismp(self):
        self.assertTrue(is_pismp(layout().upper()))
        self.assertFalse(is_pismp('UNIVERSITI MALAYSIA PERLIS IJAZAH SARJANA MUDA'))
        self.assertFalse(is_pismp('INSTITUT PENDIDIKAN GURU KAMPUS CONTOH KURSUS PERSEDIAAN'))

    def test_the_monthly_dry_run_counts_the_lane(self):
        """The existing dry-run lane table (`ocr_first_dryrun`, via `rules_read`) counts PISMP letters as a rules
        lane: the monthly count line needs no new job."""
        from apps.scholarship.eval.offer_read_check import rules_read
        self.assertTrue(rules_read('pismp', {}))


class PismpRefusalTest(SimpleTestCase):
    def test_a_missing_anchor_refuses(self):
        cases = {
            'no_title': layout(title=('TAWARAN MENGIKUTI PROGRAM IJAZAH SARJANA MUDA PERGURUAN (PISMP) AMBILAN 2026',)),
            'no_row': layout(heads=(('Ruj. Kami', 'IPGM.600-2/1/3'), ('NAMA', NAME), ('NO. KAD PENGENALAN', IC))[1:]),
        }
        for reason, lay in cases.items():
            with self.subTest(reason=reason):
                d = run(lay)
                self.assertIsNone(d['locked'])
                self.assertEqual(read_pismp(lay)[1], reason)
        no_report = layout(tab=table()[:-1])
        self.assertIsNone(run(no_report)['locked'])
        self.assertEqual(read_pismp(no_report)[1], 'no_row')

    def test_a_missing_owner_phrase_refuses(self):
        self.assertEqual(missing(LANE, layout(), text_pdf=True), [])
        self.assertEqual(len(OWNER_WORDS[LANE]), 12)
        heads = (('Ruj. Kami', 'KPM.600-2/1/3'), ('NAMA', NAME), ('NO. KAD PENGENALAN', IC))
        lay = layout(letterhead=LETTERHEAD[:3], heads=heads)                     # no IPGM anywhere
        self.assertEqual(missing(LANE, lay, text_pdf=True), [1])
        d = run(lay)
        self.assertIsNone(d['locked'])
        self.assertEqual(d['guard'], 'owner_words_missing')

    def test_two_candidates_refuse(self):
        two_names = (('Ruj. Kami', 'IPGM.600-2/1/3'), ('NAMA', NAME), ('NO. KAD PENGENALAN', IC), ('NAMA', 'QARIM DURAN'))
        two_ics = (('Ruj. Kami', 'IPGM.600-2/1/3'), ('NAMA', NAME), ('NO. KAD PENGENALAN', IC),
                   ('NO. KAD PENGENALAN', '111111-11-1111'))
        two_campus = table() + [row('TEMPAT PENGAJIAN', 'INSTITUT PENDIDIKAN GURU KAMPUS LAIN')]
        for lay in (layout(heads=two_names), layout(heads=two_ics), layout(tab=two_campus)):
            with self.subTest(size=len(lay)):
                self.assertIsNone(run(lay)['locked'])
                self.assertEqual(read_pismp(lay)[1], 'second_row')
        stray = layout(extra=('No. rujukan pelajar 111111-11-1111',))
        self.assertIsNone(run(stray)['locked'])
        self.assertEqual(read_pismp(stray)[1], 'second_ic')

    def test_the_wrong_order_refuses(self):
        swapped = (('Ruj. Kami', 'IPGM.600-2/1/3'), ('NO. KAD PENGENALAN', IC), ('NAMA', NAME))
        gap = (('Ruj. Kami', 'IPGM.600-2/1/3'), ('NAMA', NAME), ('Tarikh', '1 Julai 2026'), ('NO. KAD PENGENALAN', IC))
        closing_early = layout(extra=())
        closing_early = closing_early.replace(INTRO[0], NOTES[1])
        twice = layout(extra=(NOTES[1],))
        for lay in (layout(heads=swapped), layout(heads=gap), closing_early, twice):
            with self.subTest(size=len(lay)):
                self.assertIsNone(run(lay)['locked'])
                self.assertEqual(read_pismp(lay)[1], 'wrong_order')

    def test_the_closing_words_missing_refuse(self):
        lay = layout(notes=(NOTES[0], *NOTES[2:]))
        d = run(lay)
        self.assertIsNone(d['locked'])
        self.assertEqual(read_pismp(lay)[1], 'wrong_order')

    def test_a_non_ipg_letter_is_not_this_lane(self):
        other = layout().replace('INSTITUT PENDIDIKAN GURU', 'KOLEJ CONTOH')
        d = run(other)
        self.assertNotEqual(d['family'], 'pismp')
        self.assertIsNone(d['locked'])

    def test_the_old_layout_refuses(self):
        """The older IPG layout (no TAWARAN RASMI title, no AMBILAN/KELUARAN row) is the lane's, but refuses."""
        old_rows = (('BIDANG PENGKHUSUSAN', BIDANG), ('MOD PENGAJIAN', 'SEPENUH MASA'), ('TEMPOH PENGAJIAN', '6 TAHUN'),
                    ('TEMPAT PENGAJIAN', CAMPUS_ROW), ('TARIKH PENDAFTARAN', REPORT))
        lay = layout(title=('TAWARAN MENGIKUTI PROGRAM IJAZAH SARJANA MUDA PERGURUAN (PISMP) AMBILAN 2026',),
                     tab=table(rows=old_rows))
        d = run(lay)
        self.assertEqual(d['family'], 'pismp')
        self.assertIsNone(d['locked'])

    def test_a_changed_table_refuses(self):
        extra_row = table()
        extra_row.insert(1, row('KOD PROGRAM', 'X1'))
        moved = table()
        moved[1] = moved[1].replace('MOD PENGAJIAN'.ljust(24), 'MOD PENGAJIAN'.ljust(26))
        far = table(address=ADDRESS)
        far = [ln if 'JALAN' not in ln else ' ' * 10 + ln for ln in far]
        cases = {'template_changed': (extra_row, moved), 'address_shape': (table(address=()), far,
                                                                           table(address=('JALAN CONTOH 3', 'PERLIS')))}
        for reason, tabs in cases.items():
            for tab in tabs:
                with self.subTest(reason=reason, size=len(tab)):
                    self.assertIsNone(run(layout(tab=tab))['locked'])
                    self.assertEqual(read_pismp(layout(tab=tab))[1], reason)

    def test_a_bad_value_refuses(self):
        for kw, field in ((dict(bidang='matematik'), 'bidang_pengkhususan'), (dict(session='2026'), 'intake'),
                          (dict(campus='KOLEJ CONTOH'), 'campus'), (dict(report='8/8/2026'), 'reporting_date')):
            with self.subTest(field=field):
                d = run(layout(tab=table(**kw)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['empty_required'], [field])
        d = run(layout(name='zorbex 123'))
        self.assertEqual(d['empty_required'], ['candidate_name'])

    def test_insane_dates_refuse(self):
        for kw in (dict(session='2027/2033'), dict(session='2026/2027'), dict(report='31 JUN 2026'),
                   dict(report='8 OGOS 2027')):
            with self.subTest(**kw):
                lay = layout(tab=table(**kw))
                self.assertIsNone(run(lay)['locked'])
                self.assertEqual(read_pismp(lay)[1], 'dates_not_sane')

    def test_a_status_letter_or_withdrawal_refuses(self):
        self.assertEqual(read_pismp(layout(extra=('SURAT PENGESAHAN',)))[1], 'status_letter')
        for line in ('Tawaran ini telah ditarik balik.', 'Tawaran ini dibatalkan.'):
            with self.subTest(line=line):
                d = run(layout(extra=(line,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(pismp_letter_refusal(plain(layout(extra=(line,))), IC), 'not_an_offer')
        self.assertEqual(pismp_letter_refusal(plain(layout()), IC), '')

    def test_the_conditions_list_refuses_with_no_excuse(self):
        """No excuse yet (owner fork, OCR-19): a condition of the offer printed with a shared withdrawal word (the
        IPG template's GAGAL) refuses as not_an_offer, as on every lane."""
        d = run(layout(extra=('gagal hadir melapor diri pada tarikh yang ditetapkan;',)))
        self.assertIsNone(d['locked'])
        self.assertEqual(d['guard'], 'not_an_offer')

    def test_the_one_pengesahan_clause_is_excused_once(self):
        clause = 'walaupun pengesahan tersebut diterima selepas melapor diri.'
        self.assertIsNotNone(run(layout(extra=(clause,)))['locked'])
        self.assertEqual(read_pismp(layout(extra=(clause, clause)))[1], 'status_letter')
        self.assertEqual(read_pismp(layout(extra=('Borang pengesahan',)))[1], 'status_letter')

    def test_a_scan_or_a_later_page_refuses(self):
        self.assertEqual(offer_parse.diagnose(plain(layout()), '', '', None)['guard'], 'no_layout')
        self.assertEqual(pismp_later_pages(['Lampiran A']), 'later_page')
        self.assertEqual(pismp_later_pages(['', ' ']), '')
        self.assertEqual(run(page2='Lampiran A')['guard'], 'later_page')

    def test_a_placeholder_refuses(self):
        self.assertEqual(read_pismp(layout(name='{NAMA}'))[1], 'placeholder')


class PismpInkAndLaneTest(SimpleTestCase):
    def test_ink_targets_cover_every_printed_value(self):
        lock = run()['locked']
        phrases, values = pismp_ink_targets(lock, layout())
        self.assertEqual([lab for lab, _ in phrases], [f'p{k}' for k in range(1, 13)])
        got = dict(values)
        self.assertEqual((got['v:nric'], got['v:date'], got['v:intake'], got['v:campus']),
                         (IC, REPORT, 'AMBILAN 2026', CAMPUS_ROW))
        self.assertEqual((got['v:name'], got['v:bidang']), (NAME, BIDANG))
        self.assertEqual(set(INK_LABELS) | set(NOT_PRINTED), set(lock) - {'_family', 'rules_lane',
                                                                            '_offer_parser_version'})
        self.assertEqual(INK_OPTIONAL, ())

    def test_not_inked_dispatches_to_pismp(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), LANE), [])
            self.assertEqual(ink.call_args.kwargs['lane'], LANE)

    def test_the_labelled_ic_must_be_the_profile_ic(self):
        self.assertNotIn(LANE, offer_exact.ISSUER_PRINTS_NO_IC)
        lay = layout()
        p1 = plain(lay)
        ex = offer_exact.exact_read(p1, from_text_layer=True, page1_layer=p1, page1_layout=lay, page_texts=[p1],
                                    profile_nric=IC)
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), (LANE, IC))
        why_ = {}
        self.assertIsNone(offer_exact.exact_read(p1, from_text_layer=True, page1_layer=p1, page1_layout=lay,
                                                 page_texts=[p1], profile_nric='111111-11-1111', why=why_))
        self.assertEqual(why_.get('lane'), LANE)

    def _offer_read(self, why_=None):
        lay = layout()
        p1 = plain(lay)
        with mock.patch.object(offer_exact, 'pdf_layers', return_value=(p1, p1)), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_page1_layout', return_value=lay), \
                mock.patch('apps.scholarship.pdf_rules_pages.pdf_rules_page_texts', return_value=[p1]), \
                mock.patch.object(offer_exact, '_not_inked', return_value=[]):
            return offer_exact.exact_offer_read(p1, image=b'%PDF', content_type='application/pdf',
                                                profile_nric=IC, why=why_)

    @override_settings(OCR_FIRST_LANES=[])
    def test_the_lane_is_off_by_default(self):
        why_ = {}
        self.assertIsNone(self._offer_read(why_))
        self.assertEqual(why_, {'lane': LANE, 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=[LANE])
    def test_the_lane_reads_when_on(self):
        ex = self._offer_read()
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_name']), (LANE, NAME))
