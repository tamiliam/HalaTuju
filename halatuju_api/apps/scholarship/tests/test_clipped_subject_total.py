"""TD-217 — a certificate/slip scanned with its left edge clipped keeps its under-read guard.

`academic_engine._declared_subject_count` reads the total the document prints about itself
("JUMLAH MATA PELAJARAN : SEBELAS" = 11), and `parse_spm_slip` discards a positional parse that
recovered fewer rows than that (#66/doc912). It anchored on the literal `JUMLAH`, so #140's
left-trimmed scan — `JMLAH MATA PELAJARAN SEBELAS` — returned None and the guard SILENTLY did not
run. The anchor is now clip-tolerant, the same shape as the exam-year `PERIKSAAN\\s+TAHUN`.

Production on 2026-09-30 (the lead's read-only count): 89 positionally-parsed slips, all 89
already read a total with the strict anchor, none clipped — so no live read changes today.
"""
from django.test import SimpleTestCase

from apps.scholarship.academic_engine import _declared_subject_count, parse_spm_slip
from apps.scholarship.tests import test_academic_engine as slip_fixtures

# Its HEADER / SHARMILA rows, as plain lists. ⚠ Never bind the TestCase class itself at module
# level: pytest collects any TestCase it finds in a module's namespace, whatever the name.
_HEADER = slip_fixtures.TestParseSpmSlip.HEADER
_SHARMILA = slip_fixtures.TestParseSpmSlip.SHARMILA


class ClippedDeclaredTotalTest(SimpleTestCase):
    def test_a_clipped_J_line_still_reads(self):
        self.assertEqual(_declared_subject_count('JMLAH MATA PELAJARAN SEBELAS'), 11)

    def test_a_clipped_JU_line_still_reads(self):
        self.assertEqual(_declared_subject_count('UMLAH MATA PELAJARAN : SEPULUH'), 10)

    def test_a_line_clipped_to_MLAH_still_reads(self):
        self.assertEqual(_declared_subject_count('MLAH MATA PELAJARAN : DUA BELAS'), 12)

    def test_the_full_word_is_unchanged(self):
        self.assertEqual(_declared_subject_count('JUMLAH MATA PELAJARAN : SEPULUH'), 10)
        self.assertEqual(_declared_subject_count('X JUMLAH MATA PELAJARAN SEMBILAN Y'), 9)

    def test_MATA_PELAJARAN_without_the_stem_yields_nothing(self):
        # The slip's own column header is "KOD NAMA MATA PELAJARAN GRED" — never a total.
        self.assertIsNone(_declared_subject_count('KOD NAMA MATA PELAJARAN SEBELAS GRED'))
        self.assertIsNone(_declared_subject_count('SENARAI MATA PELAJARAN : SEPULUH'))
        self.assertIsNone(_declared_subject_count('MATA PELAJARAN SEBELAS'))


class ClippedLineRestoresTheUnderReadGuardTest(SimpleTestCase):
    def _parse(self, total_line, rows):
        header = _HEADER + [(total_line, 350)]
        return parse_spm_slip(slip_fixtures._slip_words(header, rows))

    def test_a_clipped_line_with_FEWER_rows_than_declared_is_now_rejected(self):
        # Four rows recovered, the clipped line declares ten: before TD-217 the anchor missed,
        # the guard did not run and this half-read slip was emitted. Now → None → Gemini.
        self.assertIsNone(self._parse('JMLAH MATA PELAJARAN : SEPULUH', _SHARMILA[:4]))

    def test_a_clipped_line_that_the_rows_meet_still_parses(self):
        out = self._parse('JMLAH MATA PELAJARAN : SEMBILAN', _SHARMILA)
        self.assertIsNotNone(out)
        self.assertEqual(len(out['results']), 9)
