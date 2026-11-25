"""TD-718 repair 3 (Fault B) — a one-line "Tidak Lulus" must not turn an approved STR page red.

Every Semakan page has a "Status Pedalaman" field whose value is "Ya" or "Tidak". When OCR puts that
"Tidak" and the status "Lulus" on one line, round 2's one-line tokens read an approved page as a
rejection. The repair (``str_status_read``):
  B1  one line means a real space, TAB or NBSP; ``\\r`` / ``\\u2028`` and friends are line breaks;
  B2  a grid row (Status Pedalaman label, then the status label, on one line) drops the value's first
      "Ya" / "Tidak";
  B3  a body-scan "Tidak Lulus" on a page with a Status Pedalaman label is ambiguous → no status (amber);
  B4  a label-anchored "Tidak Lulus" on a line holding only the status label stays a rejection;
  B5  (round 5) unless the line above the status label is a bare "Status Pedalaman" label: an exact
      "Tidak Lulus" / "Tidak Diluluskan" there is ambiguous → no status (amber).

All names and numbers are invented.
"""
from django.test import SimpleTestCase, TestCase

from apps.scholarship.doc_parse import parse_by_labels
from apps.scholarship.tests.test_td718_str_not_approved import _desktop_columns, _desktop_rows, _mobile

_NAME, _NRIC = 'MEENA A/P TESTKUMAR', '850505105432'
_TAIL = ['Maklumat Pembayaran', 'Alasan Permohonan', 'Maklumat Anak', 'Kembali']


def _page(*rows):
    return '\n'.join(['Semakan Status', 'Maklumat Pemohon', f'Nama {_NAME}', f'No. MyKad {_NRIC}', *rows,
                      *_TAIL]) + '\n'


def _grid(values, sep=' '):
    """Both labels on one row, both values on the next (the reviewer's side-by-side probe)."""
    return _page(f'Status Pedalaman{sep}Status Permohonan Semasa', values)


def _read(text):
    from apps.scholarship.income_engine import _str_currency
    f = parse_by_labels('str', text)
    return f.get('status'), _str_currency(f.get('status'), '2026', 2026, f.get('source_type'))


# The reviewer's probes: each read 'rejected' at 5e0327279 and must read approved now.
PROBES = {
    'grid, spaces': _grid('Tidak Lulus'),
    'grid, tabs': _grid('Tidak\tLulus', sep='\t'),
    'grid, nbsp': _grid('Tidak\xa0Lulus', sep='\xa0'),
    'grid, bare CR': _grid('Tidak\rLulus'),
    'grid, U+2028': _grid('Tidak Lulus'),
    'mobile, bare CR': _mobile('Tidak\rLulus'),
    'mobile, U+2028': _mobile('Tidak Lulus'),
    'mobile, U+2029': _mobile('Tidak Lulus'),
    'rows, bare CR': _desktop_rows('Tidak\rLulus'),
    'rows, U+2028': _desktop_rows('Tidak Lulus'),
    'rows, vertical tab': _desktop_rows('Tidak\x0bLulus'),
    'rows, form feed': _desktop_rows('Tidak\x0cLulus'),
}


class TheProbesReadApproved(SimpleTestCase):
    def test_every_probe_reads_current_not_rejected(self):
        for name, text in PROBES.items():
            with self.subTest(probe=name):
                status, state = _read(text)
                self.assertEqual(state, 'current', status)
                self.assertNotIn('tidak', ' '.join((status or '').lower().split()))


class B1ALineIsASpaceTabOrNbsp(SimpleTestCase):
    def test_the_tokens_never_cross_a_line_break(self):
        from apps.scholarship.doc_parse import _STR_STATUS_RE
        for sep in ('\n', '\r', '\r\n', ' ', ' ', '\x0b', '\x0c', '\x85'):
            with self.subTest(sep=repr(sep)):
                self.assertEqual(_STR_STATUS_RE.search(f'Tidak{sep}Lulus').group(0), 'Lulus')
                self.assertEqual(_STR_STATUS_RE.search(f'Tidak{sep}Diluluskan').group(0), 'Diluluskan')
        for sep in (' ', '\t', '\xa0', ' \t '):
            with self.subTest(sep=repr(sep)):
                self.assertEqual(_STR_STATUS_RE.search(f'Tidak{sep}Lulus').group(0), f'Tidak{sep}Lulus')

    def test_every_line_break_becomes_a_newline(self):
        from apps.scholarship.str_status_read import one_line_per_break
        self.assertEqual(one_line_per_break('a\rb c d\x0be\x0cf\x85g\r\nh'), 'a\nb\nc\nd\ne\nf\ng\nh')
        self.assertEqual(one_line_per_break(None), '')


class B2TheGridRowDropsThePedalamanWord(SimpleTestCase):
    def test_the_four_value_lines(self):
        for values, stored, want in (('Tidak Lulus', 'Lulus', 'current'),
                                     ('Tidak Tidak Lulus', 'Tidak Lulus', 'rejected'),
                                     ('Ya Tidak Lulus', 'Tidak Lulus', 'rejected'),
                                     ('Ya Lulus', 'Lulus', 'current'),
                                     ('Ya (Sabah) Lulus', 'Lulus', 'current'),
                                     ('Tidak Ditolak', 'Ditolak', 'rejected'),
                                     ('Tidak Tidak Diluluskan', 'Tidak Diluluskan', 'rejected')):
            for sep in (' ', '\t'):
                with self.subTest(values=values, sep=repr(sep)):
                    status, state = _read(_grid(values.replace(' ', sep), sep=sep))
                    self.assertEqual(' '.join(status.split()), stored)
                    self.assertEqual(state, want)

    def test_the_values_on_the_label_line_itself(self):
        self.assertEqual(_read(_page('Status Pedalaman Status Permohonan Semasa Tidak Lulus')), ('Lulus', 'current'))

    def test_a_pedalaman_label_with_its_own_value_before_the_status_label_is_not_a_grid(self):
        # "Status Pedalaman Tidak Status Permohonan Semasa Tidak Lulus": Pedalaman's value is already read
        self.assertEqual(_read(_page('Status Pedalaman Tidak Status Permohonan Semasa Tidak Lulus'))[1], 'rejected')

    def test_status_value_unit(self):
        from apps.scholarship.str_status_read import status_value
        label = r'status\s+permohonan(?:\s+str|\s+semasa)?'
        self.assertEqual(status_value('Status Pedalaman Status Permohonan Semasa\nTidak Lulus\n', label), 'Lulus')
        self.assertEqual(status_value('Status Permohonan Semasa\nTidak Lulus\n', label), 'Tidak Lulus')
        self.assertEqual(status_value('', label), '')
        self.assertEqual(status_value(None, label), '')
        self.assertEqual(status_value('Status Pedalaman Status Permohonan Semasa\nTidak\n', label), '')


class B3AnAmbiguousBodyScanStoresNoStatus(SimpleTestCase):
    def test_with_a_pedalaman_label_the_body_scan_tidak_lulus_is_unread(self):
        for word in ('Tidak Lulus', 'Tidak Diluluskan', 'TIDAK\tLULUS', 'tidak\xa0diluluskan'):
            with self.subTest(word=word):
                self.assertEqual(_read(_desktop_columns(word)), ('', 'unreadable'))

    def test_without_a_pedalaman_label_it_still_reads_rejected(self):
        for word in ('Tidak Lulus', 'Tidak Diluluskan'):
            with self.subTest(word=word):
                text = '\n'.join(['Semakan Status', 'Maklumat Pemohon', 'Nama', 'No. MyKad',
                                  'Status Permohonan Semasa ⓘ', _NAME, _NRIC, word] + _TAIL) + '\n'
                self.assertEqual(_read(text), (word, 'rejected'))

    def test_a_clear_pending_status_wins_over_an_ambiguous_body_phrase(self):
        # The label-anchored value is clear ("Dalam Proses" / "Permohonan Diterima"): the page stays red
        # (not_approved) — an ambiguous "Tidak Lulus" elsewhere on the page never turns it amber.
        for pending in ('Dalam Proses', 'Permohonan Diterima'):
            with self.subTest(pending=pending):
                text = _page('Status Permohonan Semasa', pending, 'Status Pedalaman Catatan', 'Tidak Lulus')
                self.assertEqual(_read(text), (pending, 'not_approved'))

    def test_other_body_tokens_are_not_ambiguous(self):
        for word, want in (('Lulus', 'current'), ('Ditolak', 'rejected'), ('Tidak Layak', 'rejected'),
                           ('Diluluskan', 'current')):
            with self.subTest(word=word):
                self.assertEqual(_read(_desktop_columns(word))[1], want)

    def test_the_unit(self):
        from apps.scholarship.str_status_read import ambiguous_tidak_lulus
        page = 'Status Pedalaman\nTidak\n'
        self.assertIs(ambiguous_tidak_lulus('Tidak Lulus', page), True)
        self.assertIs(ambiguous_tidak_lulus('tidak\tdiluluskan', page), True)
        self.assertIs(ambiguous_tidak_lulus('Tidak Lulus', 'Semakan Status\n'), False)
        self.assertIs(ambiguous_tidak_lulus('Lulus', page), False)
        self.assertIs(ambiguous_tidak_lulus('Tidak Layak', page), False)
        self.assertIs(ambiguous_tidak_lulus(None, None), False)


class B4ALabelAnchoredRejectionStaysRed(SimpleTestCase):
    def test_a_status_label_alone_on_its_line(self):
        for layout in (_mobile, _desktop_rows):
            for word in ('Tidak Lulus', 'Tidak Diluluskan'):
                with self.subTest(layout=layout.__name__, word=word):
                    status, state = _read(layout(word))
                    self.assertEqual(' '.join(status.replace('ⓘ', '').split()), word)
                    self.assertEqual(state, 'rejected')

    def test_the_mobile_labels_then_values_layout_reads_approved(self):
        text = _page('Status Pedalaman', 'Status Permohonan Semasa', 'Tidak', 'Lulus')
        self.assertEqual(_read(text), ('Lulus', 'current'))


class B5StackedLabelsAndOneMergedValueLine(SimpleTestCase):
    """Round 5 (class B): "Status Pedalaman" / "Status Permohonan Semasa" / "Tidak Lulus" — two bare labels
    stacked, then the two values merged on one line. The "Tidak" is most likely Pedalaman's, so the
    exact phrase is ambiguous: no status, amber (as B3). The round-5 review found base f0631426a read
    this page approved and round 4 read it rejected."""

    def _stacked(self, value, *after, pedalaman='Status Pedalaman'):
        return _page(pedalaman, 'Status Permohonan Semasa', value, *after)

    def test_the_exact_phrase_is_unread(self):
        for word in ('Tidak Lulus', 'Tidak Diluluskan'):
            for sep in (' ', '\t', '\xa0', '  '):
                for pedalaman in ('Status Pedalaman', 'Status Pedalaman ⓘ', 'Status Pedalaman  '):
                    with self.subTest(word=word, sep=repr(sep), pedalaman=pedalaman):
                        text = self._stacked(word.replace(' ', sep), pedalaman=pedalaman)
                        self.assertEqual(_read(text), ('', 'unreadable'))

    def test_a_payment_row_after_it_is_still_unread(self):
        text = self._stacked('Tidak Lulus', 'Maklumat Pembayaran', 'Fasa 1 RM500.00 15/03/2026')
        self.assertEqual(_read(text), ('', 'unreadable'))

    def test_the_exact_phrase_on_the_status_labels_own_line_is_unread_too(self):
        # Round-6 diff review: B5 does not ask the status label to be alone on its line. With a bare
        # Pedalaman label above (its value is nowhere), the "Tidak" may be Pedalaman's here as well.
        for word in ('Tidak Lulus', 'Tidak Diluluskan'):
            for line in (f'Status Permohonan Semasa {word}', f'Status Permohonan Semasa: {word}'):
                with self.subTest(line=line):
                    self.assertEqual(_read(_page('Status Pedalaman', line)), ('', 'unreadable'))
        # ...and with Pedalaman's own value above, the inline phrase stays a rejection (B4).
        self.assertEqual(_read(_page('Status Pedalaman Tidak', 'Status Permohonan Semasa Tidak Lulus'))[1],
                         'rejected')

    def test_other_value_lines_read_as_before(self):
        for value, want in (('Ya Lulus', 'current'), ('Tidak Tidak Lulus', 'rejected'),
                            ('Ya Tidak Lulus', 'rejected'),
                            # "Tidak Ditolak" is not the exact phrase: the label-anchored value stays
                            # whole and the ladder finds the rejection word "Ditolak" → rejected (today's
                            # behaviour, pinned).
                            ('Tidak Ditolak', 'rejected')):
            with self.subTest(value=value):
                status, state = _read(self._stacked(value))
                self.assertEqual(' '.join(status.split()), value)
                self.assertEqual(state, want)

    def test_a_pedalaman_label_with_its_value_above_is_not_bare(self):
        for above in ('Status Pedalaman Tidak', 'Status Pedalaman Ya (Sabah)', 'Tidak'):
            with self.subTest(above=above):
                text = _page('Status Pedalaman', above, 'Status Permohonan Semasa', 'Tidak Lulus') \
                    if above == 'Tidak' else _page(above, 'Status Permohonan Semasa', 'Tidak Lulus')
                self.assertEqual(_read(text), ('Tidak Lulus', 'rejected'))

    def test_the_unit(self):
        from apps.scholarship.str_status_read import status_value
        label = r'status\s+permohonan(?:\s+str|\s+semasa)?'
        self.assertEqual(status_value('Status Pedalaman\nStatus Permohonan Semasa\nTidak Lulus\n', label), '')
        self.assertEqual(status_value('Status Pedalaman\n\nStatus Permohonan Semasa\nTidak Lulus\n', label), '')
        self.assertEqual(status_value('Status Pedalaman\nStatus Permohonan Semasa\nYa Lulus\n', label),
                         'Ya Lulus')
        self.assertEqual(status_value('Status Pedalaman Tidak\nStatus Permohonan Semasa\nTidak Lulus\n', label),
                         'Tidak Lulus')
        self.assertEqual(status_value('Status Permohonan Semasa\nTidak Lulus\n', label), 'Tidak Lulus')


class TheProbesEndToEnd(TestCase):
    """Through ``student_str_check`` on a stored read: the probes are ``current``, never ``rejected``."""

    def test_student_str_check(self):
        from apps.scholarship.income_engine import student_str_check
        from apps.scholarship.models import ApplicantDocument
        from apps.scholarship.tests.test_td718_str_household_keep import _app
        app = _app()
        for name, text in PROBES.items():
            with self.subTest(probe=name):
                f = dict(parse_by_labels('str', text), year='2026')
                doc = ApplicantDocument(application=app, doc_type='str', household_member='father',
                                        vision_fields={'fields': f, 'student_verdict': 'ok', 'error': ''})
                self.assertEqual(student_str_check(doc)['current_status'], 'current')
