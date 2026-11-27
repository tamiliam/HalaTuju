"""OCR-14b-1: the UMPSA rules lane (`offer_parse_umpsa`). UMPSA PRINTS the IC with a label ("NAME (NO. K/P: IC)"),
so it is stored with source 'label' under the usual IC guard (UMPSA is NOT in `offer_exact.ISSUER_PRINTS_NO_IC`). The
2026/27 layout only; the 2024 layout and a Diploma refuse. The owner phrase "TARIKH PENDAFTARAN KOLEJ KEDIAMAN" is
split by the layout and joined back only when the exact pair is there. Two narrow excuses, each one exact text taken
out once: the MAKLUMAT PENTING note (owner, 27 Nov) and the page-1 print note. Synthetic letters only (made-up names,
numbers and addresses)."""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship.offer_owner_words import missing
from apps.scholarship.offer_parse_umpsa import INK_LABELS, INK_OPTIONAL, LANE, NOT_PRINTED, REPORT_LABEL, is_umpsa
from apps.scholarship.offer_parse_umpsa import read_umpsa, umpsa_ink_targets, umpsa_later_pages
from apps.scholarship.offer_parse_umpsa import umpsa_letter_refusal, umpsa_owner_text, umpsa_portal

NAME = 'ZORBEX QUENTARO BIN ALFEN'
IC = '990101145678'
NRIC = '990101-14-5678'
PROGRAMME = 'SARJANA MUDA SAINS KOMPUTER (RANGKAIAN KOMPUTER) DENGAN KEPUJIAN'
FACULTY = 'FAKULTI KOMPUTERAN'
INTAKE = 'SEMESTER I, SESI AKADEMIK 2026/2027'
OFFER_ON = '25 OGOS 2026'
ADDRESS = ('NO 12, JALAN MAWAR 3', '26300 KUANTAN', 'PAHANG')
TITLE = ('TAWARAN KEMASUKAN KE PROGRAM SARJANA MUDA UNIVERSITI MALAYSIA PAHANG AL-SULTAN ABDULLAH SEMESTER I,',
         'SESI AKADEMIK 2026/2027')
GREETING = ('Dimaklumkan bahawa Universiti Malaysia Pahang Al-Sultan Abdullah (UMPSA) mengucapkan tahniah kepada '
            'saudara/i dan',
            'seterusnya menawarkan kemasukan ke program Sarjana Muda UMPSA Semester I, Sesi Akademik 2026/2027 seperti '
            'berikut :')
RANGE = ('12 SEPTEMBER 2026 - 20 SEPTEMBER 2026 (CALON WAJIB MEMBUAT PRA -',
         ' ' * 46 + 'PENDAFTARAN SECARA DALAM TALIAN MENGIKUT TARIKH YANG TELAH DITETAPKAN)')
ROWS = (('PROGRAM PENGAJIAN', PROGRAMME), ('FAKULTI / PUSAT', FACULTY), ('NO. MATRIK', 'CB26001'),
        ('TAHUN PENGAJIAN', 'TAHUN 1'), ('TEMPOH PENGAJIAN', '4 TAHUN'), ('MOD PENGAJIAN', 'SEPENUH MASA'),
        ('YURAN PENGAJIAN', 'BAYARAN YURAN Sila Klik'))
CAMPUS = 'UNIVERSITI MALAYSIA PAHANG AL-SULTAN ABDULLAH, KAMPUS GAMBANG'
REPORT = '4 OKTOBER 2026 (8.00 PAGI - 12.00 PETANG) KEHADIRAN FIZIKAL KE KAMPUS'
SUBSIDY = ('Maklumat Subsidi Kerajaan:',
           '   Kos Sebenar Pengajian Setahun (RM)               Kos Pengajian Dibayar Pelajar Setahun                '
           'Kos Dibiayai Kerajaan Setahun (RM)',
           ' ' * 72 + '(RM)',
           ' ' * 19 + '30,000.00' + ' ' * 42 + '2,000.00' + ' ' * 42 + '28,000.00',
           'Nota:')
NOTA = ('i. Maklumat subsidi ini adalah untuk makluman kos sebenar pengajian dan yuran yang dibayar pelajar setahun.',
        'ii. Bagi bayaran yuran, pelajar hendaklah membayar yuran per semester.')
#: The MAKLUMAT PENTING paragraph as measured (its excused sentences in the middle, wrapped, double spaces).
IMPORTANT = ('MAKLUMAT PENTING',
             'Program  yang  ditawarkan  adalah       MUKTAMAD  dan  sebarang  pertukaran  program  adalah TIDAK  '
             'DIBENARKAN.  Tawaran  ini  akan',
             'terbatal  sekiranya  terdapat  sebarang  maklumat  yang  tidak  tepat,  tidak  benar,  atau  telah  '
             'dipinda  secara  tidak  sah  dalam',
             'permohonan atau surat tawaran. Tawaran ini juga terbatal sekiranya calon tidak hadir mendaftar pada '
             'tarikh yang ditetapkan.',
             'Calon hanya diterima sebagai pelajar UMPSA setelah membuat Pra-Pendaftaran di atas talian.')
FOOTER = ('Sekian, terima kasih.', '"MALAYSIA MADANI"', '"BERKHIDMAT UNTUK NEGARA"', 'Saya yang menjalankan amanah,',
          'QARIM VELTO BIN DURAN', 'Pengarah', 'Pusat Pemasaran dan Kemasukan',
          'Universiti Malaysia Pahang Al-Sultan Abdullah',
          ' ' * 43 + 'Nota: Sila cetak dan bawa Surat Tawaran ini semasa hadir ke Kampus.',
          ' ' * 43 + 'Surat Tawaran ini adalah cetakan komputer dan tandatangan tidak diperlukan.')


def row(name, value):
    return name + ' ' * (40 - len(name)) + ': ' + value


def rows_with(name, value):
    return tuple((n, value if n == name else v) for n, v in ROWS)


def layout(name_line=NAME + ' (NO. K/P: ' + IC + ')', ref='UMPSA 12.34/567-8/9/1', dated=OFFER_ON, address=ADDRESS,
           title=TITLE, greeting=GREETING, rows=ROWS, rng=RANGE, campus=CAMPUS, report=REPORT,
           tail=('KEDIAMAN',), subsidy=SUBSIDY, nota=NOTA, important=IMPORTANT, extra=(), footer=FOOTER):
    lines = [row('RUJ. KAMI (OUR REF)', ref), row('TARIKH', dated), name_line, *address, 'Saudara/i,', *title,
             *greeting, *(row(n, v) for n, v in rows), row('TARIKH PRA-PENDAFTARAN', rng[0]), *rng[1:],
             row('KAMPUS', campus), row('TARIKH PENDAFTARAN KOLEJ', report), *tail, *subsidy, *nota, *important,
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


class UmpsaLockTest(SimpleTestCase):
    def test_degree_letter_locks_with_its_labelled_ic_and_reporting_date(self):
        d = run()
        self.assertIsNotNone(d['locked'], why(d))
        lock = d['locked']
        self.assertEqual((d['family'], lock['rules_lane'], lock['_family']), ('umpsa', LANE, 'umpsa'))
        self.assertEqual(lock['candidate_name'], NAME)
        self.assertEqual((lock['candidate_nric'], lock['candidate_nric_source']), (NRIC, 'label'))
        self.assertEqual((lock['programme'], lock['programme_code']), (PROGRAMME, ''))
        self.assertEqual(lock['intake'], INTAKE)
        self.assertEqual((lock['reporting_date'], lock['reporting_date_label']), ('4 Oct 2026', REPORT_LABEL))
        self.assertEqual((lock['reporting_venue'], lock['campus'], lock['stream']), ('', '', ''))
        self.assertEqual(lock['offer_date'], OFFER_ON)
        self.assertEqual(lock['institution'], 'UNIVERSITI MALAYSIA PAHANG AL-SULTAN ABDULLAH')
        self.assertEqual(lock['_offer_parser_version'], offer_parse.PARSER_VERSION)

    def test_measured_variants_still_lock(self):
        short_range = ('12 SEPTEMBER -20 SEPTEMBER 2026 (CALON WAJIB MEMBUAT PRA - PENDAFTARAN SECARA DALAM',
                       ' ' * 46 + 'TALIAN MENGIKUT TARIKH YANG TELAH DITETAPKAN)')
        for lay in (layout(rng=short_range), layout(address=ADDRESS[:2]), layout(address=ADDRESS + ('MALAYSIA',)),
                    layout(rows=rows_with('TAHUN PENGAJIAN', 'TAHUN 2')),
                    layout(campus='UNIVERSITI MALAYSIA PAHANG AL-SULTAN ABDULLAH, KAMPUS PEKAN')):
            with self.subTest(lines=lay.count('\n')):
                self.assertIsNotNone(run(lay)['locked'], why(run(lay)))

    def test_the_gate_names_the_lane_by_its_tidied_name(self):
        """The dry run's lane name is the TIDIED institution (the hyphen becomes a space); a key that keeps the
        hyphen never matches, and the lane reads "no rules yet"."""
        from apps.scholarship.eval.offer_read_check import RULES_LANES, tidy_institution
        name = tidy_institution('Universiti Malaysia Pahang Al-Sultan Abdullah (UMPSA)').lower()
        self.assertEqual(RULES_LANES.get(name), LANE)
        self.assertTrue(all(tidy_institution(k).lower() == k for k in RULES_LANES))

    def test_the_matric_and_reference_are_never_stored(self):
        lock = run()['locked']
        self.assertFalse(any('CB26001' in str(v) or '567-8' in str(v) for v in lock.values()))

    def test_is_umpsa(self):
        self.assertTrue(is_umpsa(plain(layout()).upper()))
        self.assertFalse(is_umpsa('UNIVERSITI MALAYSIA PAHANG AL-SULTAN ABDULLAH SLIP PENDAFTARAN'))


class UmpsaRefusalTest(SimpleTestCase):
    def test_the_2024_layout_refuses(self):
        old_title = ('TAWARAN KEMASUKAN KE PROGRAM SARJANA MUDA UNIVERSITI MALAYSIA PAHANG AL-SULTAN ABDULLAH',
                     'SESI AKADEMIK 2026/2027')
        old_rows = (('PROGRAM PENGAJIAN', PROGRAMME), ('KOLEJ / FAKULTI', FACULTY)) + ROWS[2:]
        for lay in (layout(title=old_title), layout(rows=old_rows)):
            with self.subTest(lines=lay.count('\n')):
                self.assertIsNone(run(lay)['locked'])

    def test_a_diploma_refuses(self):
        for lay in (layout(rows=rows_with('PROGRAM PENGAJIAN', 'DIPLOMA KEJURUTERAAN AWAM')),
                    layout(title=(TITLE[0].replace('SARJANA MUDA', 'DIPLOMA'), TITLE[1])),
                    layout(extra=('Program Diploma ini ditawarkan oleh UMPSA.',))):
            with self.subTest(lines=lay.count('\n')):
                self.assertIsNone(run(lay)['locked'])

    def test_any_change_to_the_table_or_head_refuses(self):
        for lay in (layout(ref='UMPSA 12.34'), layout(dated='31 FEBRUARI 2026'), layout(address=ADDRESS[:1]),
                    layout(address=ADDRESS + ('MALAYSIA', 'ASIA')),
                    layout(name_line=NAME + ' (NO. K/P: 990101-14-5678)'), layout(name_line=NAME),
                    layout(rows=rows_with('MOD PENGAJIAN', 'SEPARUH MASA')),
                    layout(rows=rows_with('NO. MATRIK', 'BELUM ADA')),
                    layout(rows=ROWS[:3] + ROWS[4:]), layout(campus='KAMPUS LAIN'),
                    layout(report='4 OKTOBER 2026'), layout(tail=()),
                    layout(subsidy=SUBSIDY[:1] + SUBSIDY[4:]),
                    layout(greeting=(GREETING[0], GREETING[1].replace('2026/2027', '2025/2026')))):
            with self.subTest(lines=lay.count('\n'), size=len(lay)):
                self.assertIsNone(run(lay)['locked'])

    def test_insane_dates_refuse(self):
        for lay in (layout(dated='25 OGOS 2024'), layout(report='4 OKTOBER 2028 (8.00 PAGI - 12.00 PETANG) '
                                                                 'KEHADIRAN FIZIKAL KE KAMPUS'),
                    layout(dated='25 OKTOBER 2026'),
                    layout(report='1 SEPTEMBER 2026 (8.00 PAGI - 12.00 PETANG) KEHADIRAN FIZIKAL KE KAMPUS'),
                    layout(title=(TITLE[0], 'SESI AKADEMIK 2026/2028'))):
            with self.subTest(size=len(lay)):
                self.assertIsNone(run(lay)['locked'])

    def test_a_stray_date_refuses(self):
        d = run(layout(extra=('Taklimat pada 6 Oktober 2026.',)))
        self.assertEqual(d['guard'], 'stray_date')

    def test_a_second_pre_registration_label_hides_no_date(self):
        """Fix 1 (review r1 blocker): only the table's own pre-registration row and its wrapped lines are skipped,
        at their fixed places; a second line that starts the same way, and the lines after it, are checked."""
        for extra in (('TARIKH PRA-PENDAFTARAN BAHARU :', 'TARIKH PENDAFTARAN KOLEJ KEDIAMAN : 11 OKTOBER 2026'),
                      ('TARIKH PRA-PENDAFTARAN DIPINDA', 'Tarikh pendaftaran baharu ialah 11 Oktober 2026.'),
                      (row('TARIKH PRA-PENDAFTARAN', '1 OKTOBER 2026 - 2 OKTOBER 2026'),)):
            with self.subTest(extra=extra[0][:30]):
                d = run(layout(extra=extra))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'stray_date')
                self.assertEqual(read_umpsa(layout(extra=extra))[1], 'stray_date')

    def test_every_written_date_form_is_a_stray_date(self):
        """Fix 5(b): the shared stray-date patterns also see "11hb", a month and year, a day and month, year
        first, and the month abbreviations in those forms."""
        for line in ('Pendaftaran pada 11hb Oktober 2026.', 'Pendaftaran pada 11 haribulan Oktober 2026.',
                     'Pendaftaran diubah ke Oktober 2026.', 'Pendaftaran diubah ke 11 Oktober.',
                     'Pendaftaran 2026-10-11.', 'Pendaftaran 2026/10/11.', 'Pendaftaran 11hb Okt.',
                     'Pendaftaran Okt 2026.', 'Pendaftaran 11 Okt.', 'Pendaftaran 11 OKT 2026.'):
            with self.subTest(line=line):
                d = run(layout(extra=(line,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'stray_date')

    def test_a_second_ic_refuses(self):
        for extra in ('Penjaga: 750505-03-1234', 'NO. K/P: ' + IC):
            with self.subTest(extra=extra[:8]):
                self.assertIsNone(run(layout(extra=(extra,)))['locked'])

    def test_a_later_page_with_text_refuses(self):
        self.assertEqual(umpsa_later_pages(['Syarat-syarat tawaran']), 'later_page')
        self.assertEqual(umpsa_later_pages(['', '  ']), '')
        self.assertEqual(run(page2='Sekian, terima kasih.')['guard'], 'later_page')

    def test_a_scan_refuses_no_layout(self):
        d = offer_parse.diagnose(plain(layout()), '', '', None)
        self.assertEqual(d['guard'], 'no_layout')

    def test_a_status_letter_refuses(self):
        self.assertEqual(read_umpsa(layout(extra=('PENGESAHAN PENDAFTARAN',)))[1], 'status_letter')


class UmpsaExcuseTest(SimpleTestCase):
    def test_the_important_note_is_excused_once(self):
        self.assertIsNotNone(run()['locked'])
        self.assertEqual(umpsa_letter_refusal(plain(layout()), NRIC), '')

    def test_the_note_plus_a_real_withdrawal_refuses(self):
        """Owner, 27 Nov: only the exact paragraph, only once; any other cancel or withdraw wording refuses."""
        for extra in ('Tawaran ini telah ditarik balik.', 'Tawaran ini dibatalkan.', 'Tawaran ini tidak sah.',
                      'Tawaran ini juga terbatal sekiranya calon tidak hadir mendaftar pada tarikh yang ditetapkan.',
                      ' '.join(' '.join(IMPORTANT[2:4]).split())):
            with self.subTest(extra=extra[:20]):
                d = run(layout(extra=(extra,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'not_an_offer')
                self.assertEqual(umpsa_letter_refusal(plain(layout(extra=(extra,))), NRIC), 'not_an_offer')

    def test_a_second_full_copy_of_the_paragraph_refuses(self):
        """Fix 4(a): the paragraph is taken out once; a second full copy, on one line or wrapped as measured,
        refuses."""
        full = ' '.join(' '.join(IMPORTANT[1:4]).split())
        for extra in ((full,), IMPORTANT[1:4], IMPORTANT):
            with self.subTest(lines=len(extra)):
                d = run(layout(extra=extra))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'not_an_offer')

    def test_tidak_layak_refuses(self):
        """Fix 5(a): "tidak layak" is a withdrawal word on every lane, in any spacing."""
        for extra in ('Anda tidak layak.', 'Status: TIDAK LAYAK', 'T I D A K  L A Y A K', 'tidak.layak'):
            with self.subTest(extra=extra):
                d = run(layout(extra=(extra,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['guard'], 'not_an_offer')

    def test_a_changed_note_refuses(self):
        changed = (IMPORTANT[0], IMPORTANT[1], IMPORTANT[2].replace('tidak  tepat', 'salah'), *IMPORTANT[3:])
        self.assertEqual(run(layout(important=changed))['guard'], 'not_an_offer')

    def test_the_print_note_is_excused_once_from_the_portal_tell(self):
        lay = layout()
        text = plain(lay)
        self.assertFalse(umpsa_portal(text, lay))
        self.assertTrue(umpsa_portal(text + '\nNota: Sila cetak dan bawa Surat Tawaran ini semasa hadir ke Kampus.',
                                     lay))
        self.assertTrue(umpsa_portal(text + '\nSila cetak slip ini', lay))
        self.assertFalse(umpsa_portal(text, ''))        # a scan: refuses as no_layout right after
        for line in ('Sila cetak slip ini', 'SEMAKAN TAWARAN', 'Tahniah! Anda layak menerima tawaran'):
            with self.subTest(line=line):
                d = run(layout(extra=(line,)))
                self.assertIsNone(d['locked'])
                self.assertTrue(d['portal'])

    def test_the_print_note_is_excused_only_in_its_own_place(self):
        """Fix 4(b): only at its measured place, the last-but-one line of page 1, alone on its line, the
        computer-print line after it. The same note anywhere else (and none at its place) refuses as a portal."""
        note = FOOTER[-2]
        without = tuple(f for f in FOOTER if f != note)
        moved = {'in_the_nota_block': layout(nota=NOTA + (note.strip(),), footer=without),
                 'above_the_signature': layout(footer=(note,) + without),
                 'after_the_last_line': layout(footer=without + (note,)),
                 'in_the_body': layout(extra=(note.strip(),), footer=without),
                 'at_the_margin': layout(footer=without[:-1] + (note.strip(), without[-1])),
                 'on_a_line_with_more': layout(footer=without[:-1] + (note + ' Terima kasih.', without[-1])),
                 'too_far_in': layout(footer=without[:-1] + (' ' * 60 + note.strip(), without[-1])),
                 'no_computer_line_after': layout(footer=without[:-1] + (note, without[-1].replace('komputer', 'mesin'))),
                 'not_after_the_signature': layout(footer=without[:-2] + (without[-2] + ' Kuantan', note, without[-1]))}
        for name, lay in moved.items():
            with self.subTest(name):
                d = run(lay)
                self.assertIsNone(d['locked'])
                self.assertTrue(d['portal'])
        self.assertIsNotNone(run()['locked'])


class SharedChecksTest(SimpleTestCase):
    """Fix 5: the shared withdrawal and stray-date checks, stricter on every lane that uses them."""

    def test_tidak_layak_is_a_withdrawal_on_every_lane(self):
        from apps.scholarship.offer_ums_refusal import _withdrawn_one
        for s in ('Anda tidak layak.', 'TIDAK  LAYAK', 'T I D A K  L A Y A K', 'tidak-layak'):
            with self.subTest(s=s):
                self.assertTrue(_withdrawn_one(s, []))
        self.assertFalse(_withdrawn_one('Anda layak menerima tawaran ini.', []))

    def test_unisza_note_plus_tidak_layak_refuses(self):
        from apps.scholarship.tests import test_offer_parse_unisza as unisza
        self.assertIsNotNone(unisza.run(unisza.layout(extra=(unisza.NOTE,)))['locked'])
        d = unisza.run(unisza.layout(extra=(unisza.NOTE, '5. Anda tidak layak.')))
        self.assertIsNone(d['locked'])
        self.assertEqual(d['guard'], 'not_an_offer')

    def test_the_stray_date_patterns_see_every_written_form(self):
        from apps.scholarship.offer_parse_umk import _SHORT_DATE
        from apps.scholarship.offer_parse_uthm import _ANY_DATE
        for s in ('11hb Oktober 2026', '11 hb. Oktober 2026', '11 haribulan Oktober 2026', 'Oktober 2026',
                  'OKTOBER, 2026', '11 Oktober', '11 OKTOBER', '2026-10-11', '2026/10/11', '2026.10.11',
                  '11 October', 'October 2026', '11/10/2026', '11 Oktober 2026'):
            with self.subTest(s=s):
                self.assertTrue(_ANY_DATE.search(s))
        for s in ('11hb Okt', '11 Okt', 'Okt 2026', 'OGOS 2026', '3 Ogo.', '11 OKT 2026', 'Sept 2026'):
            with self.subTest(s=s):
                self.assertTrue(_SHORT_DATE.search(s))
        for s in ('SEPENUH MASA', 'TAHUN 1', '4 TAHUN', 'SESI AKADEMIK 2026/2027', 'NO 12, JALAN MAWAR 3',
                  '26300 KUANTAN', 'UMPSA 12.34/567-8/9/1', 'MARKAH 2026', 'Sepanjang 2026', '30,000.00',
                  '12 MARKAH', '8.00 PAGI - 12.00 PETANG'):
            with self.subTest(s=s):
                self.assertFalse(_ANY_DATE.search(s) or _SHORT_DATE.search(s))


class UmpsaOwnerWordsTest(SimpleTestCase):
    def test_the_split_label_is_joined_back_only_when_exact(self):
        lay = layout()
        self.assertEqual(missing(LANE, lay, text_pdf=True), [7])
        self.assertEqual(missing(LANE, umpsa_owner_text(lay), text_pdf=True), [])
        self.assertIn(REPORT_LABEL + ' : ' + REPORT, umpsa_owner_text(lay))
        for bad in (layout(tail=()), layout(tail=('   KEDIAMAN BARU',)), layout(extra=(row('TARIKH PENDAFTARAN KOLEJ',
                                                                                          REPORT), 'KEDIAMAN'))):
            with self.subTest(size=len(bad)):
                self.assertEqual(missing(LANE, umpsa_owner_text(bad), text_pdf=True), [7])

    def test_a_missing_owner_phrase_refuses(self):
        lay = layout(footer=tuple(f for f in FOOTER if f != 'Pusat Pemasaran dan Kemasukan'))
        self.assertIsNone(run(lay)['locked'])


class UmpsaInkTest(SimpleTestCase):
    def test_ink_targets_cover_every_printed_value(self):
        lock = run()['locked']
        phrases, values = umpsa_ink_targets(lock, layout())
        self.assertEqual([lab for lab, _ in phrases], [f'p{k}' for k in range(1, 10)])
        got = dict(values)
        self.assertEqual(got['v:nric'], IC)
        self.assertEqual(got['v:date'], '4 OKTOBER 2026')
        self.assertEqual(got['v:name'], NAME)
        self.assertEqual(set(INK_LABELS) | set(NOT_PRINTED), set(lock) - {'_family', 'rules_lane',
                                                                            '_offer_parser_version'})
        self.assertEqual(INK_OPTIONAL, ())

    def test_not_inked_dispatches_to_umpsa(self):
        with mock.patch('apps.scholarship.pdf_ink.page1_ink', return_value=object()), \
                mock.patch('apps.scholarship.pdf_ink.ink_missing', return_value=[]) as ink:
            self.assertEqual(offer_exact._not_inked({'fields': run()['locked']}, b'', layout(), LANE), [])
            self.assertEqual(ink.call_args.kwargs['lane'], LANE)

    def test_exact_read_takes_the_label_ic(self):
        ex = exact()
        self.assertEqual((ex['rules_lane'], ex['fields']['candidate_nric']), (LANE, NRIC))
        other = exact(profile='880808-08-8888')       # the printed IC is kept, never swapped for the profile's
        self.assertEqual(other['fields']['candidate_nric'], NRIC)
        self.assertEqual(other['offer_reader_inputs']['nric_check'], 'kept_well_formed')

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
