"""OCR-19: the PISMP rules lane (`offer_parse_pismp`): a digital Institut Pendidikan Guru Malaysia offer letter for
the teacher-training degree, read from its page-1 layout on the owner's anchors only (name after NAMA, IC after NO.
KAD PENGENALAN, the PISMP title plus BIDANG PENGKHUSUSAN, the campus after TEMPAT PENGAJIAN, the reporting date after
TARIKH PENDAFTARAN). Any letter that does not fit refuses. The lane ships OFF. Synthetic letters only (made-up names,
numbers and addresses)."""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import offer_exact, offer_parse
from apps.scholarship import offer_parse_pismp as pismp
from apps.scholarship.offer_owner_words import OWNER_WORDS, missing
from apps.scholarship.offer_parse_unimap import _pin_digest
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
CLOSING = '4. Tawaran ini akan TERBATAL dengan sendirinya sekiranya tuan/puan:'
#: The one PENGESAHAN clause the template prints, inside its conditions list (made-up words around it).
CLAUSE = '6. Yuran dibayar walaupun pengesahan tersebut diterima selepas melapor diri.'
#: A made-up conditions list in the template's shape (the closing words, GAGAL items, a right to withdraw): never
#: the real block. The module pins the MEASURED block by digest; these tests pin this one the same way.
COND = ('3. Tuan/puan dikehendaki melapor diri pada tarikh yang ditetapkan.', CLOSING,
        '  a) gagal melapor diri pada tarikh yang ditetapkan;', '  b) gagal mengemukakan dokumen asal.',
        '5. Pihak institut berhak menarik balik tawaran ini pada bila-bila masa.', CLAUSE)
SIGN = ('Sekian, terima kasih.', '(QARIM VELTO BIN DURAN)', 'Bagi pihak Rektor')
NOTES = COND + SIGN
#: The head and table values in the measured shapes (made up): the reference, the offer date, the candidate's
#: address row, the salutation, the two table values never read.
RUJ = 'ABC1234/56DE789F/01-23/(4567)'
OFFER_DATE = '01 Jul 2026'
HEADS = (('Ruj. Kami', RUJ), ('Tarikh', OFFER_DATE), ('NAMA', NAME), ('NO. KAD PENGENALAN', IC))
ADDRESS_LABEL = 'ALAMAT SURAT'
HOME = 'NO. 1, JALAN CONTOH, 02000 PEKAN CONTOH, PERLIS'
SALUTATION = 'Tuan/Puan,'
MOD = 'SEPENUH MASA CONTOH'
TEMPOH = '6 TAHUN ( 1 TAHUN AWAL DAN 5 TAHUN PROGRAM CONTOH PENUH )'
SYNTHETIC_PINS = frozenset({(len(COND), _pin_digest(COND))})
REAL_PINS = pismp.CONDITIONS_PINS
#: Review round 1: the synthetic template pinned the way the module pins the measured one.
SYNTHETIC_TEMPLATE = {
    'letterhead': frozenset({(len(LETTERHEAD), _pin_digest(LETTERHEAD))}),
    'address_label': frozenset({_pin_digest([ADDRESS_LABEL])}),
    'salutation': frozenset({_pin_digest([SALUTATION])}),
    'title': frozenset({_pin_digest(TITLE, '2026')}),
    'intro': frozenset({(len(INTRO), _pin_digest(INTRO))}),
    'mod': frozenset({_pin_digest([MOD])}),
    'tempoh': frozenset({_pin_digest([TEMPOH])}),
    'tail': frozenset({(len(NOTES), _pin_digest(NOTES))}),
}
REAL_TEMPLATE = pismp.TEMPLATE_PINS
_PINS = mock.patch.object(pismp, 'CONDITIONS_PINS', SYNTHETIC_PINS)
_TEMPLATE = mock.patch.object(pismp, 'TEMPLATE_PINS', SYNTHETIC_TEMPLATE)


def setUpModule():
    _PINS.start()
    _TEMPLATE.start()


def tearDownModule():
    _TEMPLATE.stop()
    _PINS.stop()


def head(label, value):
    return BASE + label.ljust(20) + ': ' + value


def row(label, value):
    return ' ' * 14 + label.ljust(24) + ':  ' + value


def address_line(value):
    return ' ' * 14 + ' ' * 24 + '   ' + value


def table(bidang=BIDANG, session=SESSION, campus=CAMPUS_ROW, address=ADDRESS, report=REPORT, rows=None):
    rows = rows if rows is not None else (
        ('BIDANG PENGKHUSUSAN', bidang), ('MOD PENGAJIAN', MOD), ('TEMPOH PENGAJIAN', TEMPOH),
        ('AMBILAN/KELUARAN', session), ('TEMPAT PENGAJIAN', campus), ('TARIKH PENDAFTARAN', report))
    out = []
    for label, value in rows:
        out.append(row(label, value))
        if label == 'TEMPAT PENGAJIAN':
            out += [address_line(a) for a in address]
    return out


def layout(name=NAME, ic=IC, title=TITLE, tab=None, notes=NOTES, heads=None, letterhead=LETTERHEAD, extra=(),
           after=(), home=HOME, intro=INTRO):
    """``extra``: lines between the table and the conditions block; ``after``: lines straight after the block;
    ``home``: the candidate's address row after the IC (None: no such row)."""
    heads = heads if heads is not None else (('Ruj. Kami', RUJ), ('Tarikh', OFFER_DATE), ('NAMA', name),
                                             ('NO. KAD PENGENALAN', ic))
    if after:
        notes = notes[:len(COND)] + tuple(after) + notes[len(COND):]
    lines = [*(BASE + x for x in letterhead), *(head(k, v) for k, v in heads),
             *([head(ADDRESS_LABEL, home)] if home is not None else []), BASE + SALUTATION,
             *(BASE + x for x in title), *(BASE + x for x in intro), *(tab if tab is not None else table()),
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
        lay = layout(letterhead=LETTERHEAD[:3])                                   # no IPGM anywhere
        self.assertEqual(missing(LANE, lay, text_pdf=True), [1])
        self.assertEqual(run(lay)['guard'], 'template_changed')                  # the letterhead pin first
        pins = {**SYNTHETIC_TEMPLATE, 'letterhead': frozenset({(3, _pin_digest(LETTERHEAD[:3]))})}
        with mock.patch.object(pismp, 'TEMPLATE_PINS', pins):
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
                d = run(layout(after=(line,)))
                self.assertIsNone(d['locked'])
                self.assertEqual(pismp_letter_refusal(plain(layout(after=(line,))), IC), 'not_an_offer')
        self.assertEqual(pismp_letter_refusal(plain(layout()), IC), '')

    def test_the_one_pengesahan_clause_is_excused_once(self):
        self.assertIn('walaupun pengesahan tersebut diterima selepas melapor diri', CLAUSE)
        self.assertIsNotNone(run()['locked'])                                    # the clause is in the block
        self.assertEqual(read_pismp(layout(after=(CLAUSE,)))[1], 'status_letter')
        self.assertEqual(read_pismp(layout(after=('Borang pengesahan',)))[1], 'status_letter')

    def test_a_scan_or_a_later_page_refuses(self):
        self.assertEqual(offer_parse.diagnose(plain(layout()), '', '', None)['guard'], 'no_layout')
        self.assertEqual(pismp_later_pages(['Lampiran A']), 'later_page')
        self.assertEqual(pismp_later_pages(['', ' ']), '')
        self.assertEqual(run(page2='Lampiran A')['guard'], 'later_page')

    def test_a_placeholder_refuses(self):
        self.assertEqual(read_pismp(layout(name='{NAMA}'))[1], 'placeholder')


class PismpConditionsBlockTest(SimpleTestCase):
    """Owner fork 1 (chose A): the template's conditions list is excused once, pinned by digest, in its place only."""

    def refuses(self, lay):
        d = run(lay)
        self.assertIsNone(d['locked'])
        return pismp_letter_refusal(plain(lay), IC)

    def test_the_pinned_block_locks(self):
        self.assertIsNotNone(run()['locked'], why(run()))
        self.assertEqual(pismp_letter_refusal(plain(layout()), IC), '')
        self.assertTrue(any(w in ' '.join(COND).upper() for w in ('GAGAL', 'TERBATAL', 'MENARIK BALIK')))

    def test_one_word_changed_refuses(self):
        for k, line in enumerate(COND):
            words = line.split()
            changed = ' '.join(words[:-1] + [words[-1].upper() + 'X'])
            notes = COND[:k] + (changed,) + COND[k + 1:] + SIGN
            with self.subTest(line=k):
                self.assertEqual(self.refuses(layout(notes=notes)), 'not_an_offer')

    def test_a_line_taken_out_or_added_inside_refuses(self):
        for notes in (COND[:-1] + SIGN, COND[:2] + COND[3:] + SIGN, COND[:2] + ('  c) lain-lain.',) + COND[2:] + SIGN):
            with self.subTest(lines=len(notes)):
                self.assertEqual(self.refuses(layout(notes=notes)), 'not_an_offer')

    def test_a_withdrawal_word_outside_the_block_refuses(self):
        outside = ('Tuan/puan gagal memenuhi syarat.', 'Tawaran ini telah TERBATAL.', 'Tawaran ini DIBATALKAN.',
                   'Surat ini DIGANTIKAN dengan surat baharu.', 'Surat ini menggantikan surat terdahulu.',
                   'D I G A N T I K A N')
        for line in outside:
            with self.subTest(line=line, where='after the block'):
                self.assertEqual(self.refuses(layout(after=(line,))), 'not_an_offer')
            with self.subTest(line=line, where='after the sign-off'):
                self.assertEqual(self.refuses(layout(notes=NOTES + (line,))), 'not_an_offer')
        lay = layout().replace(INTRO[0], 'Tawaran terdahulu telah dibatalkan.')         # above the table
        self.assertEqual(self.refuses(lay), 'not_an_offer')

    def test_a_duplicated_block_refuses(self):
        for notes in (COND + COND + SIGN, COND + SIGN + COND):
            with self.subTest(lines=len(notes)):
                self.assertEqual(self.refuses(layout(notes=notes)), 'not_an_offer')

    def test_a_block_in_the_wrong_place_refuses(self):
        gap = layout(extra=('Sila bawa dokumen asal.',))                    # a line between the table and the block
        self.assertEqual(self.refuses(gap), 'not_an_offer')
        early = layout(notes=SIGN).replace(INTRO[0], '\n'.join(BASE + x for x in COND))   # above the table
        self.assertEqual(self.refuses(early), 'not_an_offer')
        late = layout(notes=SIGN + COND)                                     # after the sign-off
        self.assertEqual(self.refuses(late), 'not_an_offer')

    def test_a_letter_with_no_block_and_no_withdrawal_word_is_a_changed_template(self):
        clean = ('3. Tuan/puan dikehendaki melapor diri.', CLOSING + ' tidak melapor diri.')
        self.assertEqual(self.refuses(layout(notes=clean + SIGN)), 'template_changed')

    def test_the_measured_pin_is_a_digest_and_refuses_the_synthetic_letter(self):
        """The module ships the MEASURED pin: (line count, one sha256), never text; the synthetic block is not it."""
        self.assertEqual(len(REAL_PINS), 1)
        (count, digest), = REAL_PINS
        self.assertTrue(count > 0 and len(digest) == 64 and set(digest) <= set('0123456789abcdef'))
        self.assertFalse(REAL_PINS & SYNTHETIC_PINS)
        with mock.patch.object(pismp, 'CONDITIONS_PINS', REAL_PINS):
            self.assertEqual(pismp_letter_refusal(plain(layout()), IC), 'not_an_offer')
            self.assertIsNone(run()['locked'])

    def test_no_other_lane_is_excused(self):
        """The shared withdrawal check is untouched: the same block refuses through `letter_refusal`."""
        from apps.scholarship.offer_ums_refusal import letter_refusal
        self.assertEqual(letter_refusal(plain(layout())), 'not_an_offer')


class PismpReviewRound1Test(SimpleTestCase):
    """Review round 1: every failing input of the reviewer's notes refuses (synthetic letters only)."""

    def refuses(self, lay, reason):
        d = run(lay)
        self.assertIsNone(d['locked'])
        self.assertEqual(read_pismp(lay)[1], reason)

    def test_a_campus_that_wraps_refuses(self):
        for campus, cont in (('INSTITUT PENDIDIKAN GURU KAMPUS SULTAN', 'MIZAN'),
                             ("INSTITUT PENDIDIKAN GURU KAMPUS DATO' RAZALI", 'ISMAIL,'),
                             ('INSTITUT PENDIDIKAN GURU KAMPUS PENDIDIKAN', 'TEKNIK')):
            with self.subTest(words=len(campus.split())):
                self.refuses(layout(tab=table(campus=campus, address=(cont,) + ADDRESS)), 'address_shape')
        # a campus line so long that the first address word could not have fitted on it
        long_campus = 'INSTITUT PENDIDIKAN GURU KAMPUS ABCDEFGHIJ KLMNOPQRST UVWXYZ'
        self.refuses(layout(tab=table(campus=long_campus)), 'address_shape')
        self.assertIsNotNone(run(layout(tab=table(campus='INSTITUT PENDIDIKAN GURU KAMPUS ABCDEF')))['locked'])

    def test_free_text_must_be_the_pinned_template(self):
        cases = {
            'intro: other date': layout(intro=(INTRO[0], 'Tarikh lapor diri: 9 OGOS 2026.')),
            'intro: other campus': layout(intro=(INTRO[0], '2. Tuan/puan ditawarkan ke IPG KAMPUS LAIN.')),
            'intro: other bidang': layout(intro=(INTRO[0], 'BIDANG PENGKHUSUSAN KEDUA PENDIDIKAN SEJARAH')),
            'sign-off: other date': layout(notes=NOTES + ('Tarikh lapor diri: 15 OGOS 2026',)),
            'sign-off: other campus': layout(notes=NOTES + ('Sila lapor diri di INSTITUT PENDIDIKAN GURU KAMPUS LAIN.',)),
            'sign-off: other bidang': layout(notes=NOTES + ('Bidang: PENDIDIKAN SEJARAH',)),
            'sign-off: spaced label': layout(notes=NOTES + ('N A M A : QARIM DURAN',)),
            'letterhead changed': layout(letterhead=LETTERHEAD[:3] + ('LAMAN WEB : WWW.LAIN.EXAMPLE',)),
            'title: two AMBILAN': layout(title=(TITLE[0] + ' AMBILAN 2027',)),
            'title: PINDAAN': layout(title=(TITLE[0] + ' (PINDAAN)',)),
            'salutation changed': layout().replace(SALUTATION, 'Tuan/Puan QARIM,'),
            'mod value changed': layout(tab=table(rows=(
                ('BIDANG PENGKHUSUSAN', BIDANG), ('MOD PENGAJIAN', 'SEPARUH MASA'), ('TEMPOH PENGAJIAN', TEMPOH),
                ('AMBILAN/KELUARAN', SESSION), ('TEMPAT PENGAJIAN', CAMPUS_ROW), ('TARIKH PENDAFTARAN', REPORT)))),
            'address label changed': layout().replace(ADDRESS_LABEL, 'ALAMAT LAIN '),
        }
        for tag, lay in cases.items():
            with self.subTest(tag=tag):
                self.refuses(lay, 'template_changed')

    def test_a_line_between_the_head_rows_or_before_the_title_refuses(self):
        to_other = layout().replace(BASE + SALUTATION, head('Kepada', 'QARIM DURAN') + '\n' + BASE + SALUTATION)
        self.refuses(to_other, 'head_shape')
        self.refuses(layout(home=None), 'head_shape')

    def test_the_head_values_have_the_measured_shapes(self):
        for tag, heads in (('ruj', (('Ruj. Kami', 'IPGM.600-2/1/3 JLD.9 (12)'),) + HEADS[1:]),
                           ('offer date after report', HEADS[:1] + (('Tarikh', '09 Ogo 2026'),) + HEADS[2:]),
                           ('offer date long month', HEADS[:1] + (('Tarikh', '1 Julai 2026'),) + HEADS[2:]),
                           ('offer date not a day', HEADS[:1] + (('Tarikh', '31 Jun 2026'),) + HEADS[2:]),
                           ('offer date unknown month', HEADS[:1] + (('Tarikh', '01 Xyz 2026'),) + HEADS[2:])):
            with self.subTest(tag=tag):
                self.refuses(layout(heads=heads), 'head_shape')
        for home in ('NO. 1, JALAN CONTOH, PEKAN CONTOH, PERLIS', 'NO. 1, JALAN 2026, 02000 PEKAN CONTOH',
                     'D/A QARIM DURAN, 02000 PEKAN CONTOH', 'no. 1, jalan contoh, 02000 pekan'):
            with self.subTest(home=len(home)):
                self.refuses(layout(home=home), 'address_shape')

    def test_no_other_date_outside_the_two_date_rows(self):
        for addr in (('JALAN 9 OGOS,', '01000 KANGAR,', 'PERLIS'), ('LOT 1/8/26,', '01000 KANGAR,', 'PERLIS')):
            with self.subTest(addr=len(addr[0])):
                self.refuses(layout(tab=table(address=addr)), 'second_date')
        self.refuses(layout(home='NO. 1, JALAN MEI, 02000 PEKAN CONTOH'), 'second_date')
        # the backstop holds even where a pin would not: an intro pinned with a date in it
        intro = (INTRO[0], 'Tarikh lapor diri: 9 OGOS 2026.')
        pins = {**SYNTHETIC_TEMPLATE, 'intro': frozenset({(2, _pin_digest(intro))})}
        with mock.patch.object(pismp, 'TEMPLATE_PINS', pins):
            self.refuses(layout(intro=intro), 'second_date')
        third = plain(layout(notes=NOTES + ('Tarikh lapor diri: 15 OGOS 2026',)))
        self.assertEqual(pismp_letter_refusal(third, IC), 'second_date')
        self.assertEqual(pismp_letter_refusal(plain(layout()), IC), '')

    def test_no_other_campus_outside_the_campus_row(self):
        for line in ('INSTITUT PENDIDIKAN GURU KAMPUS LAIN', 'IPG LAIN', 'K A M P U S LAIN'):
            with self.subTest(line=line):
                self.refuses(layout(tab=table(address=(line,) + ADDRESS[1:])), 'second_campus')
        self.refuses(layout(name='ZORBEX KAMPUS QUENTARO'), 'second_campus')

    def test_a_one_word_name_is_not_read(self):
        for name in ('ALI', 'BIN', 'ALI BIN', 'ALI A/L', '@ ALI'):
            with self.subTest(name=name):
                d = run(layout(name=name))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['empty_required'], ['candidate_name'])

    def test_a_specialism_with_no_distinctive_word_is_not_read(self):
        for bidang in ('PENDIDIKAN', 'PENDIDIKAN (SEKOLAH)'):
            with self.subTest(bidang=bidang):
                self.assertEqual(run(layout(tab=table(bidang=bidang)))['empty_required'], ['bidang_pengkhususan'])

    def test_a_specialism_that_says_none_is_not_read(self):
        # fork 2 (chose B): lane-local refusal until a catalogue-backed specialism list exists
        for bidang in ('TIADA', 'TIDAK BERKENAAN', 'TIDAK BERKAITAN', '-', 'N/A', 'N / A', 'TIADA (PENDIDIKAN MUZIK)'):
            with self.subTest(bidang=bidang):
                d = run(layout(tab=table(bidang=bidang)))
                self.assertIsNone(d['locked'])
                self.assertEqual(d['empty_required'], ['bidang_pengkhususan'])

    def test_the_lane_words_refuse_anywhere_outside_the_block(self):
        lines = ('Surat ini membatalkan surat terdahulu.', 'Penempatan tuan/puan dipinda.',
                 'Surat tawaran ini menggugurkan tawaran asal.', 'KEPUTUSAN RAYUAN', 'PENANGGUHAN', 'PENOLAKAN',
                 'MAKLUM BALAS', 'M A K L U M B A L A S')
        for line in lines:
            for where, lay in (('after the sign-off', layout(notes=NOTES + (line,))),
                               ('below the title', layout(intro=(line, INTRO[1]))),
                               ('above the title', layout(title=(line, *TITLE)))):
                with self.subTest(line=line, where=where):
                    self.assertIsNone(run(lay)['locked'])
                    self.assertEqual(pismp_letter_refusal(plain(lay), IC), 'not_an_offer')

    def test_the_measured_template_pins_are_digests_and_refuse_the_synthetic_letter(self):
        self.assertEqual(set(REAL_TEMPLATE), set(SYNTHETIC_TEMPLATE))
        for key, pins in REAL_TEMPLATE.items():
            with self.subTest(key=key):
                self.assertEqual(len(pins), 1)
                pin, = pins
                digest = pin[1] if isinstance(pin, tuple) else pin
                self.assertTrue(len(digest) == 64 and set(digest) <= set('0123456789abcdef'))
                self.assertFalse(pins & SYNTHETIC_TEMPLATE[key])
        with mock.patch.object(pismp, 'TEMPLATE_PINS', REAL_TEMPLATE):
            self.assertEqual(read_pismp(layout())[1], 'template_changed')
            self.assertIsNone(run()['locked'])


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
