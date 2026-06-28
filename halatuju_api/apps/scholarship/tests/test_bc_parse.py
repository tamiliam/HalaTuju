"""Deterministic geometry-based birth-certificate parser (`bc_parse.parse_bc`).

Synthetic, PII-FREE word-geometry fixtures (fictional names) for both genuine versions —
monolingual (`KANAK-KANAK` / `Nama`) and bilingual (`KANAK-KANAK / CHILD` / `Nama Penuh`) —
plus the cropped-upload and informant/address traps. Real certs are validated locally; these
prove the parsing logic without committing PII.
"""
from django.test import SimpleTestCase

from apps.scholarship.bc_parse import parse_bc


def _words(rows):
    """Build Vision-style word boxes from (cy, 'tok1 tok2 …') rows — incrementing cx per token."""
    out = []
    for cy, line in rows:
        for j, t in enumerate(line.split(' ')):
            if t:
                out.append({'text': t, 'cx': 100 + j * 60, 'cy': cy, 'h': 30})
    return out


# Monolingual: 'KANAK-KANAK' header, child label 'Nama', child a mononym (the #10 shape).
_MONO = _words([
    (120, '080101-10-5678'),                       # child IC, top-right (born-date encoded)
    (220, 'KERAJAAN MALAYSIA'),
    (300, 'SIJIL KELAHIRAN'),
    (440, 'Kawasan Pendaftaran'),
    (560, 'KANAK - KANAK'),
    (640, 'Nama'),
    (720, 'AISYAH'),                               # child (mononym)
    (840, 'Tarikh dan Waktu Kelahiran Jantina'),
    (920, '01 JAN 2008 LELAKI'),
    (1060, 'BAPA'),
    (1140, 'Nama'),
    (1220, 'AHMAD A / L BAKAR'),                   # father
    (1320, 'No. Kad Pengenalan Umur'),
    (1400, '700101-10-1111 38 TAHUN'),             # father IC (value on next row)
    (1520, 'IBU'),
    (1600, 'Nama'),
    (1680, 'SITI A / P RAHIM'),                    # mother
    (1780, 'No. Kad Pengenalan Umur'),
    (1860, '750202-10-2222 33 TAHUN'),             # mother IC
    (1980, 'No. Daftar AB 12345'),
    (2200, 'PENDAFTAR BESAR'),
])

# Bilingual: 'KANAK-KANAK / CHILD' + 'Nama Penuh'; child IC on the SIJIL row; the bilingual
# 'No. Kad Pengenalan' is OCR-jumbled with its English co-label; informant = father; address present.
_BILINGUAL = _words([
    (120, 'SIJIL KELAHIRAN 080202-10-9999'),       # child IC on the title row
    (180, 'BIRTH CERTIFICATE'),
    (320, 'KANAK - KANAK / CHILD'),
    (400, 'Nama Penuh RAJESH A / L KUMAR'),        # child name on the SAME row as the label
    (460, 'Full Name'),
    (560, 'Tarikh dan Waktu Kelahiran 02 FEB 2008 Tempat Kelahiran'),
    (680, 'BAPA / FATHER'),
    (760, 'Nama'),
    (820, 'KUMAR A / L SAMY'),                     # father
    (920, 'No. Identity Kad Card No. Pengenalan 700303-10-3333 Age Umur 38'),   # jumbled label
    (1040, 'IBU / MOTHER'),
    (1120, 'DEVI A / P RAMAN'),                    # mother — directly after IBU (no 'Nama' row)
    (1220, 'No. Identity Kad Card No. Pengenalan 750404-10-4444 Age Umur 33'),
    (1320, 'Alamat Tempat Tinggal NO 5 JALAN MAWAR TAMAN INDAH SELANGOR'),       # address (all-caps trap)
    (1440, 'PEMBERITAHU / INFORMANT'),
    (1520, 'Nama KUMAR A / L SAMY'),               # informant = the father (must NOT be read as mother)
    (1600, 'No. Kad Pengenalan 700303-10-3333'),
    (1720, 'PENDAFTAR BESAR'),
])

# Interleaved DOB-in-label (the OCR scrambles 'Tarikh dan Waktu Kelahiran' with the date, app36)
# + a letterhead blob glued onto the mother name across a page break (app64). Both must be bounded.
_INTERLEAVED = _words([
    (100, 'SIJIL KELAHIRAN'),
    (140, '080620-10-1578'),                       # child IC, top
    (240, 'KANAK - KANAK'),
    (300, 'Nama'),
    (360, 'THAVASRI'),                             # child — must NOT absorb the date/place below
    (420, 'Tarikh 20 dan JUN 2008 Waktu Kelahiran 02:31 PM Jantina PEREMPUAN'),   # interleaved DOB
    (480, 'Tempat Kelahiran Taraf Kewarganegaraan'),
    (540, 'HOSPITAL BESAR TENGKU AMPUAN KLANG WARGANEGARA'),                       # all-caps place
    (640, 'BAPA'),
    (700, 'RUMARASAMY A / L NARAYANAN'),
    (760, 'No. Kad Pengenalan 740111-08-5195 Umur 40 TAHUN'),
    (860, 'IBU'),
    (920, 'RANEGARAMALAYSIAJABATANPE RADHA A / P KRISHNA SAMY'),                   # glued letterhead blob
    (980, 'No. Kad Pengenalan 791230-05-5116 Umur 38 TAHUN'),
    (1080, 'PENDAFTAR BESAR'),
])

# Cropped: a BC missing its KANAK-KANAK + BAPA blocks (#27 shape) — only the mother survives.
_CROPPED = _words([
    (120, 'SIJIL KELAHIRAN'),
    (300, 'IBU / MOTHER'),
    (380, 'THAMARAI A / P VEERA'),
    (480, 'No. Kad Pengenalan 800101-10-5555'),
    (600, 'PEMBERITAHU / INFORMANT'),
    (680, 'THAMARAI A / P VEERA'),
    (800, 'Disahkan bahawa maklumat'),
])


class TestBcParse(SimpleTestCase):
    def test_monolingual(self):
        r = parse_bc(_MONO)
        self.assertEqual(r['_bc_version'], 'mono')
        self.assertEqual(r['bc_child_name'], 'AISYAH')
        self.assertEqual(r['bc_child_nric'], '080101-10-5678')      # top-right child IC
        self.assertEqual(r['bc_father_name'], 'AHMAD A/L BAKAR')
        self.assertEqual(r['bc_father_nric'], '700101-10-1111')
        self.assertEqual(r['bc_mother_name'], 'SITI A/P RAHIM')
        self.assertEqual(r['bc_mother_nric'], '750202-10-2222')
        self.assertEqual(r['bc_number'], 'AB 12345')

    def test_bilingual(self):
        r = parse_bc(_BILINGUAL)
        self.assertEqual(r['_bc_version'], 'bilingual')
        self.assertEqual(r['bc_child_name'], 'RAJESH A/L KUMAR')
        self.assertEqual(r['bc_child_nric'], '080202-10-9999')
        self.assertEqual(r['bc_father_name'], 'KUMAR A/L SAMY')
        self.assertEqual(r['bc_father_nric'], '700303-10-3333')
        # The decisive case: the mother is DEVI — NOT the address, NOT the father-as-informant.
        self.assertEqual(r['bc_mother_name'], 'DEVI A/P RAMAN')
        self.assertEqual(r['bc_mother_nric'], '750404-10-4444')

    def test_interleaved_dob_and_letterhead_blob_are_bounded(self):
        r = parse_bc(_INTERLEAVED)
        # The child name stops at the DOB digit row — not 'THAVASRI JUN PM ... KLANG'.
        self.assertEqual(r['bc_child_name'], 'THAVASRI')
        self.assertEqual(r['bc_child_nric'], '080620-10-1578')
        self.assertEqual(r['bc_father_name'], 'RUMARASAMY A/L NARAYANAN')
        # The glued 'RANEGARAMALAYSIAJABATANPE' blob is rejected (contains MALAYSIA/JABATAN).
        self.assertEqual(r['bc_mother_name'], 'RADHA A/P KRISHNA SAMY')
        self.assertEqual(r['bc_mother_nric'], '791230-05-5116')

    def test_cropped_returns_none_never_invents(self):
        # No KANAK-KANAK / BAPA → can't resolve child+father → None (defer to gated Gemini).
        self.assertIsNone(parse_bc(_CROPPED))

    def test_not_a_birth_certificate(self):
        self.assertIsNone(parse_bc(_words([(100, 'PENYATA KWSP CARUMAN'), (200, 'AHLI 123')])))

    def test_empty(self):
        self.assertIsNone(parse_bc([]))
