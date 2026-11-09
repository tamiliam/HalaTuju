"""A2.7a (2026-11-09) — offer reader live gaps: lines.

* TD-451: a short campus line ("KK BAGAN DATUK") named a campus of ANOTHER institution type (the
  polytechnic of the same town). A leading type form is now a filter on the campus type.
* TD-452: the short type forms "KK" / "POLY" / "METRO" are read as the type they stand for, so
  "KK KLANG" and "METRO KUANTAN" name their campus by its whole name, whatever the town-word list holds.
* TD-474: a one-word TOWN line straight above the postcode line is the address, not the end of a
  wrapped school name.
* TD-447: the offer confirm reads the hostel line against the LETTER's course, so a stale stored
  course id can no longer leave a hostel as the sponsor-facing institution.

Synthetic text only — invented schools and towns for the parser twin; the campus rows are catalogue
institution names, no student data."""
from django.test import SimpleTestCase, TestCase

from apps.courses.models import Institution
from apps.scholarship.offer_course_match import CampusReader, _institutions, letter_place
from apps.scholarship.offer_parse import parse_govt_offer
from apps.scholarship.tests.test_offer_parse_s5 import STPM_SIX
from apps.scholarship.tests.test_offer_realign import UM_PICK, _Base, _offer


def _inst(iid, name, acr='', typ='x'):
    return Institution.objects.create(institution_id=iid, institution_name=name, acronym=acr, type=typ,
                                      state='x')


class ShortLineCrossesNoTypeTest(TestCase):
    """TD-451: the four lines the round-4 review found, each naming a polytechnic from a KK / POLY line."""

    @classmethod
    def setUpTestData(cls):
        _inst('A27-PBD', 'Politeknik Bagan Datuk', 'PBD', 'Politeknik')
        _inst('A27-PMBG', 'Politeknik METrO Betong', 'PMBG', 'Politeknik')
        _inst('A27-PMTG', 'Politeknik METrO Tasek Gelugor', 'PMTG', 'Politeknik')
        _inst('A27-PMS', 'Politeknik Muadzam Shah', 'PMS', 'Politeknik')
        _inst('A27-POLIMAS', "Politeknik Sultan Abdul Halim Mu'adzam Shah", 'POLIMAS', 'Politeknik')

    def test_a_kk_line_never_names_a_polytechnic(self):
        for line, poly in (('KK BAGAN DATUK', 'Politeknik Bagan Datuk'),
                           ('KK BETONG', 'Politeknik METrO Betong'),
                           ('KK TASEK GELUGOR', 'Politeknik METrO Tasek Gelugor'),
                           ('KOLEJ KOMUNITI BAGAN DATUK', 'Politeknik Bagan Datuk')):
            with self.subTest(line=line):
                self.assertFalse(CampusReader(line).names(poly, ''))

    def test_the_matcher_finds_no_polytechnic_from_a_kk_line(self):
        named, worded = _institutions('KK BAGAN DATUK')
        self.assertEqual((named, worded), ([], []))

    def test_the_poly_short_form_names_its_own_campus_not_the_other_muadzam(self):
        reader = CampusReader('POLY SULTAN ABDUL HALIM MUADZAM SHAH')
        self.assertTrue(reader.names("Politeknik Sultan Abdul Halim Mu'adzam Shah", 'POLIMAS'))
        self.assertFalse(reader.names('Politeknik Muadzam Shah', 'PMS'))

    def test_a_polytechnic_line_still_names_its_campus(self):
        self.assertTrue(CampusReader('POLITEKNIK BAGAN DATUK').names('Politeknik Bagan Datuk', 'PBD'))
        self.assertTrue(CampusReader('POLITEKNIK METRO BETONG').names('Politeknik METrO Betong', 'PMBG'))
        self.assertTrue(CampusReader('POLY BAGAN DATUK').names('Politeknik Bagan Datuk', 'PBD'))


class ShortTypeFormsTest(TestCase):
    """TD-452: "KK" / "METRO" read as the type, so a campus a letter names only by type + town is named
    by its whole name — "KK KLANG" no longer depends on "klang" being missing from the town list."""

    @classmethod
    def setUpTestData(cls):
        _inst('A27-KKK', 'Kolej Komuniti Klang', '', 'Kolej Komuniti')
        _inst('A27-KKA', 'Kolej Komuniti Ampang', '', 'Kolej Komuniti')
        _inst('A27-KKS', 'Kolej Komuniti Selayang', '', 'Kolej Komuniti')
        _inst('A27-PMKU', 'Politeknik METrO Kuantan', 'PMKU', 'Politeknik')
        _inst('A27-PKU', 'Politeknik Kuantan', '', 'Politeknik')          # counterfactual row

    def test_each_kk_short_form_names_its_campus(self):
        for line, campus in (('KK KLANG', 'Kolej Komuniti Klang'), ('KK AMPANG', 'Kolej Komuniti Ampang'),
                             ('KK SELAYANG', 'Kolej Komuniti Selayang'), ('KK. KLANG', 'Kolej Komuniti Klang')):
            with self.subTest(line=line):
                self.assertTrue(CampusReader(line).names(campus, ''))

    def test_a_kk_short_form_names_no_other_campus(self):
        self.assertFalse(CampusReader('KK KLANG').names('Kolej Komuniti Ampang', ''))
        self.assertFalse(CampusReader('KK AMPANG').names('Kolej Komuniti Selayang', ''))

    def test_the_metro_short_form_names_the_metro_campus_only(self):
        reader = CampusReader('METRO KUANTAN')
        self.assertTrue(reader.names('Politeknik METrO Kuantan', 'PMKU'))
        self.assertFalse(reader.names('Politeknik Kuantan', ''))
        self.assertFalse(CampusReader('POLY KUANTAN').names('Politeknik METrO Kuantan', 'PMKU'))
        self.assertTrue(CampusReader('POLY KUANTAN').names('Politeknik Kuantan', ''))

    def test_a_town_alone_or_a_longer_word_names_nothing(self):
        self.assertFalse(CampusReader('KLANG').names('Kolej Komuniti Klang', ''))
        self.assertFalse(CampusReader('METROPOLITAN KUANTAN').names('Politeknik METrO Kuantan', 'PMKU'))
        self.assertFalse(CampusReader('KKLANG').names('Kolej Komuniti Klang', ''))


class TownAbovePostcodeTest(SimpleTestCase):
    """TD-474: the town line straight above the postcode is the address; a real wrap still joins."""

    def test_a_town_line_above_the_postcode_is_not_joined(self):
        text = STPM_SIX.replace('SEKOLAH MENENGAH KEBANGSAAN TINGGI ZELVORA\nUTARA\nJALAN QUERIN\n12345 ZELVORA\n',
                                'SEKOLAH MENENGAH KEBANGSAAN ZELVORA\nQELANG\n12345 QELANG\n')
        self.assertNotEqual(text, STPM_SIX)
        r = parse_govt_offer(text)
        self.assertEqual(r['institution'], 'SEKOLAH MENENGAH KEBANGSAAN ZELVORA')

    def test_a_real_wrap_still_joins(self):
        self.assertEqual(parse_govt_offer(STPM_SIX)['institution'],
                         'SEKOLAH MENENGAH KEBANGSAAN TINGGI ZELVORA UTARA')


class ConfirmReadsTheLettersCourseTest(_Base):
    """TD-447: a stale stored course (UM) and a hostel line for a UPM diploma: the confirm stores UPM."""

    def test_a_stale_course_id_never_leaves_the_hostel_as_the_institution(self):
        from apps.scholarship.services.confirmation import confirm_pathway
        app = self._app(pick=dict(UM_PICK))
        _offer(app, ('DIPLOMA PEMBANGUNAN MANUSIA', 'KOLEJ SRI RAJANG', 'Universiti Putra Malaysia'))
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'], 'Universiti Putra Malaysia')

    def test_a_kk_hostel_line_still_yields_to_the_university(self):
        # "KK" also means Kolej Kediaman (a hostel): reading it as Kolej Komuniti must not keep the line.
        self.assertEqual(letter_place('UP4310001', 'KK SRI RAJANG', 'Universiti Putra Malaysia'),
                         'Universiti Putra Malaysia')

    def test_a_kk_hostel_line_still_names_the_university_after_it(self):
        # Review of A2.7a (Medium): the type filter must reject only a campus of the OTHER type, never a
        # university named after a "KK <hostel>," prefix (no issuer).
        from apps.scholarship import offer_pathway as op
        from apps.scholarship.offer_course_match import match_offer_course
        line = 'KK PERWIRA, UNIVERSITI TUN HUSSEIN ONN'
        self.assertTrue(CampusReader(line).names('Universiti Tun Hussein Onn Malaysia', 'UTHM'))
        self.assertFalse(op.offer_contradicts_course_institution('UB6523001', line))
        self.assertEqual(match_offer_course('SARJANA MUDA KEJURUTERAAN ELEKTRONIK DENGAN KEPUJIAN', line)['course_id'],
                         'UB6523001')

    def test_no_issuer_keeps_the_line(self):
        from apps.scholarship.services.confirmation import confirm_pathway
        app = self._app(pick={'course_id': 'UP4310001', 'course_name': 'Diploma Pembangunan Manusia'})
        _offer(app, ('DIPLOMA PEMBANGUNAN MANUSIA', 'Universiti Putra Malaysia', ''))
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'], 'Universiti Putra Malaysia')


class ModelVersionTest(SimpleTestCase):
    def test_the_doc_recognition_version_is_bumped(self):
        from apps.scholarship.genuineness.results_doc import MODEL_VERSION
        self.assertEqual(MODEL_VERSION, '1.27.0')
