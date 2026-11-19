"""S1c review round 1 (2026-11-20): the UMS rules read's six findings — a name glued to a right-hand word
(MED-A), a wrapped name cut at an address (MED-B), withdrawal wording (MED-C), programme labels (D), a list
of reporting dates (E) and the line cap (F). Every new refusal was measured on the cached corpus first.

Synthetic twins only — invented names, ICs and places (`test_no_gitignored_corpus.py`)."""
from django.test import SimpleTestCase

from apps.scholarship.offer_parse import diagnose
from apps.scholarship.offer_parse_university import MAX_LINES, name_in_plain, read_ums
from apps.scholarship.tests.test_offer_parse_university import NAME, PROG, ums

OTHER = 'Diploma Sains Marin'


def _refused(test, text, field):
    f, reason = read_ums(text)
    test.assertIn(field, reason)
    test.assertEqual(f[field], '')


class TestMedAGluedName(SimpleTestCase):
    """pypdf 6's layout glues a word drawn under ~2pt to the right of the name onto it; the plain layer
    keeps them apart, so the layout's name must stand as its own words in the plain layer."""

    def test_a_name_glued_to_a_right_hand_word_refuses(self):
        for word in ('SULIT', 'BAHAGIAN AKADEMIK', 'PENDAFTAR'):
            with self.subTest(word=word):
                layout = ums(name=NAME + word)
                self.assertEqual(read_ums(layout)[1], '')          # the layout alone would lock the glued name
                plain = ums() + word + '\n'                        # the plain layer: the word on its own line
                d = diagnose(layout, page1_text=plain, page1_layout=layout)
                self.assertEqual(d['guard'], 'name_not_plain')
                self.assertIsNone(d['locked'])

    def test_a_plain_line_that_spaces_the_glued_word_refuses_too(self):
        layout = ums(name=NAME + 'SULIT')
        d = diagnose(layout, page1_text=ums(name=NAME + ' SULIT'), page1_layout=layout)
        self.assertEqual(d['guard'], 'name_not_plain')

    def test_a_layout_read_without_its_plain_layer_refuses(self):
        d = diagnose(ums(), page1_text='', page1_layout=ums())
        self.assertEqual(d['guard'], 'no_plain_layer')
        self.assertIsNone(d['locked'])

    def test_the_name_alone_on_its_plain_line_locks(self):
        d = diagnose(ums(), page1_text=ums(), page1_layout=ums())
        self.assertEqual(d['locked']['candidate_name'], NAME)

    def test_a_pypdf5_plain_layer_that_runs_the_name_into_the_next_line_still_locks(self):
        """pypdf 5's plain layer prints digits before the name and the next layout line's start after it."""
        plain = ums().replace(f'\n{NAME}\n', f'\n0102{NAME}')
        d = diagnose(ums(), page1_text=plain, page1_layout=ums())
        self.assertEqual(d['locked']['candidate_name'], NAME)

    def test_a_letter_glued_before_or_after_the_name_in_the_plain_line_refuses(self):
        layout = ums()
        self.assertFalse(name_in_plain(NAME, f'X{NAME}\n', layout))
        self.assertFalse(name_in_plain(NAME, f'{NAME}SULIT\n', layout))
        self.assertFalse(name_in_plain(NAME, f'{NAME}\n{NAME}\n', layout))          # two plain lines hold it
        self.assertFalse(name_in_plain(NAME, '', layout))
        self.assertTrue(name_in_plain(NAME, f'Tarikh : 15 Ogos 2031\n{NAME}\n', layout))


class TestMedBWrappedName(SimpleTestCase):
    def test_a_name_tail_before_a_street_word_a_separator_or_a_postcode_refuses(self):
        for nxt in ('HAKIM JALAN ZANTHARION 7', 'HAKIM LORONG MELATI 3', 'HAKIM TAMAN SERI', 'HAKIM LOT 5 KG X',
                    'HAKIM PETI SURAT 12', 'HAKIM; JALAN X', 'HAKIM - KG ZANTHARION', 'HAKIM – KG ZANTHARION',
                    'ABDULLAH 88000 KOTA KINABALU', 'ABDULLAH NO 12 JALAN X'):
            with self.subTest(nxt=nxt):
                _refused(self, ums(name=f'MUHAMMAD AMIRUL\n{nxt}'), 'candidate_name')

    def test_an_address_line_under_a_whole_name_still_locks(self):
        """Measured: a cut at ANY digit (a house number) cost one genuine scanned letter, whose address line
        starts with a word and a house number; only a postcode cuts. A house word ("NO", "UNIT") is the
        address's own."""
        for nxt in ('NO 12 JALAN ZANTHARION', 'UNIT 3, 88000 KOTA KINABALU', 'ZANTHA 1234 JALAN 12',
                    'Jalan Zantharion 7, 88000 Kota Kinabalu'):
            with self.subTest(nxt=nxt):
                f, reason = read_ums(ums(name=f'{NAME}\n{nxt}'))
                self.assertEqual((reason, f['candidate_name']), ('', NAME))


class TestMedCWithdrawal(SimpleTestCase):
    def test_withdrawal_words_in_any_spacing_refuse(self):
        for tail in ('S U R A T T I D A K B E R J A Y A', 'D-I-B-A-T-A-L-K-A-N', 'D.I.B.A.T.A.L.K.A.N',
                     'TIDAK  .  BERJAYA', 'P E N A R I K A N  B A L I K', 'Tawaran ini DITARIK-SEMULA.',
                     'TIDAK.LAGI.SAH', 'PEMBATALAN TAWARAN'):
            with self.subTest(tail=tail):
                self.assertEqual(read_ums(ums() + tail + '\n')[1], 'not_an_offer')

    def test_the_new_withdrawal_words_refuse(self):
        """Measured: none is on any page of the 58 cached UMS letters."""
        for tail in ('PENARIKAN BALIK TAWARAN', 'Tawaran ini tidak sah.', 'Tawaran ini telah digugurkan.',
                     'Tawaran ini dimansuhkan.', 'Tawaran ini telah luput.', 'STATUS : GAGAL'):
            with self.subTest(tail=tail):
                self.assertEqual(read_ums(ums() + tail + '\n')[1], 'not_an_offer')

    def test_terbatal_or_tarik_balik_said_without_a_condition_refuses(self):
        for tail in ('Tawaran ini telah terbatal.', 'Dengan ini tawaran saudara TERBATAL.', 'Status tawaran : TERBATAL',
                     'Tawaran ini adalah terbatal dengan serta-merta.', 'Universiti menarik balik tawaran ini.',
                     'TARIK  BALIK'):
            with self.subTest(tail=tail):
                self.assertEqual(read_ums(ums() + tail + '\n')[1], 'not_an_offer')
        for mid in ('TAWARAN TERBATAL', 'PERHATIAN: TAWARAN INI TERBATAL', 'STATUS : TIDAK BERJAYA'):
            with self.subTest(mid=mid):
                text = ums().replace('Program :', f'{mid}\nProgram :', 1)
                self.assertEqual(read_ums(text)[1], 'not_an_offer')

    def test_terbatal_or_tarik_balik_as_a_condition_still_locks(self):
        """Measured: all 36 cached letters that print TERBATAL say it as a condition."""
        for tail in ('Sekiranya saudara tidak mendaftar, tawaran ini adalah terbatal dengan sendirinya.',
                     'Tawaran ini akan TERBATAL sekiranya saudara tidak mendaftar.',
                     'Universiti berhak menarik balik tawaran ini jika maklumat saudara palsu.'):
            with self.subTest(tail=tail):
                self.assertEqual(read_ums(ums() + tail + '\n')[1], '')


class TestDProgrammeLabels(SimpleTestCase):
    LABELS = ('Programme :      {v}', 'Kursus :      {v}', 'Bidang Pengajian :      {v}', 'Butiran Program :      {v}',
              '1. Program :      {v}', 'Fakulti : Fakulti Sains      Program : {v}', 'PROGRAM:{v}', 'Program\t:\t{v}',
              'Nama  Program :      {v}', 'NamaProgram : {v}', 'Program Baru:\n{v}', 'Program      :      {v}')

    def test_every_label_that_names_another_programme_refuses(self):
        for label in self.LABELS:
            with self.subTest(label=label):
                _refused(self, ums() + label.format(v=OTHER) + '\n', 'programme')

    def test_every_label_that_names_the_sentence_programme_locks(self):
        for label in self.LABELS:
            with self.subTest(label=label):
                f, reason = read_ums(ums() + label.format(v=PROG) + '\n')
                self.assertEqual((reason, f['programme']), ('', PROG))

    def test_a_bare_label_whose_value_cannot_be_compared_refuses(self):
        _refused(self, ums() + 'Program Baru :\nSila rujuk lampiran\n', 'programme')

    def test_program_as_a_prose_word_is_not_a_label(self):
        text = ums() + 'Maklumat lanjut      program      boleh dilihat      di laman      web universiti\n'
        self.assertEqual(read_ums(text)[1], '')


class TestEReportingDateLists(SimpleTestCase):
    def test_a_second_date_in_the_window_is_a_list(self):
        for report in ('Kumpulan A : 28 September 2031\nKumpulan B : 29 September 2031',
                       '28 September 2031, 29 September 2031',
                       '29 September 2031 (Kumpulan B), 28 September 2031 (Kumpulan A)',
                       '27 September 2031 (pelajar antarabangsa)\n28 September 2031'):
            with self.subTest(report=report):
                _refused(self, ums(report=report), 'reporting_date')

    def test_a_range_of_two_whole_dates_still_reads_its_first_day(self):
        for report in ('28 September 2031 (Ahad) - 29 September 2031', '28 September 2031 sehingga 29 September 2031',
                       '28 SEPTEMBER 2031 (SABTU) – 29 SEPTEMBER 2031'):
            with self.subTest(report=report):
                f, reason = read_ums(ums(report=report))
                self.assertEqual((reason, f['reporting_date']), ('', '28 Sep 2031'))

    def test_a_joiner_starting_the_date_with_no_day_above_reads_no_date(self):
        """`_JOINER_START` on its own: nothing above the date holds a day number."""
        for report in ('\nhingga 29 September 2031', '- 29 September 2031', '‒ 29 September 2031',
                       '~ 29 September 2031', 'atau 29 September 2031', '\n/ 29 September 2031'):
            with self.subTest(report=report):
                _refused(self, ums(report=report), 'reporting_date')


class TestFLineCap(SimpleTestCase):
    def test_carriage_returns_count_as_lines(self):
        self.assertEqual(read_ums(ums() + '.\r' * MAX_LINES)[1], 'too_long')
        self.assertEqual(read_ums(ums() + '.\r\n' * MAX_LINES)[1], 'too_long')
