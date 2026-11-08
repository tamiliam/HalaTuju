"""Request #66 (MODEL_VERSION 1.26.0): IIUM / UIAM writes its offer letters in ENGLISH.

Doc 5105's genuine IIUM letter read `not_offer_letter` ("1/10 polytechnic signatures") because the UA family
knew IIUM only by its Malay name and Malay wording. Every letter below is SYNTHETIC, written in the standard
English wording of an IIUM offer and of IIUM's public admission booklet: no name, IC, address or programme of
any applicant. The private-arm and private-college letters are invented to prove the blocks still hold.
"""
from django.test import SimpleTestCase, TestCase

from apps.scholarship.genuineness import assess, signature_genuineness
from apps.scholarship.genuineness.offer_signatures import UA_OFFER_SIGNATURES_EN, english_ua_lists
from apps.scholarship.genuineness.results_doc import (MODEL_VERSION, UA_OFFER_SIGNATURES, _OFFER_LISTS, _UA_NAMES,
                                                      _norm_fold_upper_alnum, _private_arm_offer)
from apps.scholarship.tests import test_corpus_gaps_c1 as c1
from apps.scholarship.tests import test_corpus_gaps_c2 as c2
from apps.scholarship.tests import test_doc_signatures as fixtures

_HEAD = """INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA
ACADEMIC MANAGEMENT AND ADMISSION DIVISION (AMAD)
Jalan Gombak, 53100 Kuala Lumpur
Our Ref : AMAD/UG/2024/0000
Date : 1 August 2024
"""
_BODY = """Name : CALON CONTOH
Assalamualaikum warahmatullahi wabarakatuh
We are pleased to inform you that you have been offered a place in the following programme:
Programme : BACHELOR OF HUMAN SCIENCES (HONOURS)
Kulliyyah : Kulliyyah of Contoh Studies
Mode of Study : Full Time
Registration Date : 7 September 2024
Registration Venue : IIUM GOMBAK
Tuition Fee : RM510.00 per semester
This offer is valid for one (1) year from the date of issuance.
Yours sincerely,
Director
Academic Management and Admission Division
"""
IIUM_OFFER = _HEAD + 'OFFER OF ADMISSION TO THE BACHELOR DEGREE PROGRAMME FOR SEMESTER 1, 2024/2025\n' + _BODY
# The title alone on its line, the programme on the next (the fold joins them: "OFFER OF ADMISSION BACHELOR …").
IIUM_BARE_TITLE = _HEAD + 'OFFER OF ADMISSION\n' + _BODY
# The SMALLEST English letter that clears the band — what doc 5105's stored read is known to hold: the name,
# AMAD (its stored issuer) and the offer title. 3 + 1 + 3 = 7 of 10.
IIUM_MINIMAL = ('INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA\nACADEMIC MANAGEMENT AND ADMISSION DIVISION\n'
                'OFFER OF ADMISSION FOR SEMESTER 1, 2024/2025\nProgramme : BACHELOR OF CONTOH (HONOURS)\n')
# IIUM's own Centre for Foundation Studies (its public foundation, a unit of the university).
IIUM_CFS = IIUM_OFFER.replace('ACADEMIC MANAGEMENT AND ADMISSION DIVISION (AMAD)',
                              'CENTRE FOR FOUNDATION STUDIES\nACADEMIC MANAGEMENT AND ADMISSION DIVISION (AMAD)')

# ── Not offers ────────────────────────────────────────────────────────────────────────────
# IIUM's ADMISSION BOOKLET (sent with the offer): the name, AMAD and "offer of admission" in its sentences.
IIUM_BOOKLET = """STUDENT ADMISSION BOOKLET
UNDERGRADUATE PROGRAMME
Academic Management and Admission Division (AMAD)
International Islamic University Malaysia (IIUM)
Congratulations to all for being selected to join the International Islamic University Malaysia.
You are required to fill the ONLINE acceptance form within the stipulated date as stated in the ONLINE
OFFER LETTER webpage. Otherwise this offer of admission will be automatically revoked.
PLEASE PRINT THE OFFER LETTER AND KEEP IT SAFE.
Please refer to your offer letter to check the registration venue.
"""
IIUM_CONDITIONAL = IIUM_OFFER.replace('OFFER OF ADMISSION TO', 'CONDITIONAL OFFER OF ADMISSION TO')
IIUM_PROVISIONAL = IIUM_BARE_TITLE.replace('OFFER OF ADMISSION\n', 'PROVISIONAL OFFER OF ADMISSION\n')
IIUM_NOTIFICATION = IIUM_OFFER.replace('OFFER OF ADMISSION TO THE BACHELOR DEGREE PROGRAMME',
                                       'NOTIFICATION OF ADMISSION RESULT FOR THE BACHELOR DEGREE PROGRAMME')

# ── Private letters that merely MENTION IIUM ──────────────────────────────────────────────
_PRIVATE_BODY = """Our Ref : MC/ADM/2024/01
Date : 1 August 2024
Name : CALON CONTOH
OFFER OF ADMISSION TO DIPLOMA IN BUSINESS STUDIES
We are pleased to offer you a place. The programme is validated by International Islamic University Malaysia.
Registration Date : 7 September 2024
Programme Code : DBS01
This offer is valid for one (1) year from the date of issuance.
Yours sincerely,
Registrar
"""
PRIVATE_MENTIONS_IIUM = 'MERCU INTERNATIONAL COLLEGE\nJalan Contoh, 43000 Kajang\n' + _PRIVATE_BODY
PRIVATE_SDN_BHD = 'MERCU EDUCATION SDN BHD\nJalan Contoh, 43000 Kajang\n' + _PRIVATE_BODY
PRIVATE_PARTNER = ('MERCU COLLEGE\nPartner of International Islamic University Malaysia\nJalan Contoh, 43000 Kajang\n'
                   + _PRIVATE_BODY)
# IIUM's fee-paying arms, on IIUM's own name and office.
IIUM_ACADEMY = IIUM_OFFER.replace('ACADEMIC MANAGEMENT AND ADMISSION DIVISION (AMAD)\n',
                                  'IIUM ACADEMY OF GRADUATE & PROFESSIONAL STUDIES\n'
                                  'ACADEMIC MANAGEMENT AND ADMISSION DIVISION (AMAD)\n')
IIUM_CENPACE = IIUM_OFFER.replace('ACADEMIC MANAGEMENT AND ADMISSION DIVISION (AMAD)\n',
                                  'CENTRE FOR PROFESSIONAL AND CONTINUING EDUCATION (CENPACE)\n'
                                  'ACADEMIC MANAGEMENT AND ADMISSION DIVISION (AMAD)\n')
IIUM_SDN_BHD = IIUM_OFFER.replace('Jalan Gombak', 'IIUM Contoh Services Sdn Bhd, Jalan Gombak')
IIUM_SATU = IIUM_OFFER.replace('OFFER OF ADMISSION TO', 'SALURAN TERBUKA OFFER OF ADMISSION TO')

# The 1.25.0 UA family, frozen here, so "every Malay letter scores as before" is a diff, not a re-typed number.
_UA_1_25_0 = [
    ('public university (UA) name', list(_UA_NAMES) + ['PELAJAR UITM SETELAH MEMBUAT PENDAFTARAN',
                                                       'UITM BERHAK MENUKARKAN CALON'], 3, 'text'),
    ('offer/admission line', ['TAWARAN KEMASUKAN', 'ANDA DITAWARKAN TEMPAT UNTUK MENGIKUTI PROGRAM DI UITM'], 3, 'text'),
    ('academic office', ['PEJABAT PENGURUSAN AKADEMIK', 'PUSAT PENGURUSAN AKADEMIK', 'BAHAGIAN HAL EHWAL AKADEMIK',
                         'PEJABAT PENDAFTAR', 'PUSAT PEMASARAN DAN KEMASUKAN', 'BAHAGIAN PENGAMBILAN PELAJAR'], 1, 'text'),
    ('finality / no-change clause', ['PERTUKARAN PROGRAM ADALAH TIDAK DIBENARKAN', 'SEBARANG PERTUKARAN',
                                     'TIDAK DIBENARKAN MENUKAR PROGRAM', 'TAWARAN AKAN DITARIK BALIK',
                                     'ADALAH MUKTAMAD'], 1, 'text'),
    ('Program / Kod Program', ['PROGRAM PENGAJIAN', 'PROGRAM KOD'], 1, 'text'),
    ('registration date', ['TARIKH PENDAFTARAN', 'TARIKH MENDAFTAR', 'TARIKH LAPOR DIRI',
                           'HADIR MENDAFTAR PADA TARIKH'], 1, 'text'),
]


def _g(text):
    return signature_genuineness(text, doc_type='offer_letter')


class IIUMEnglishOfferIsGenuine(SimpleTestCase):

    def test_an_english_iium_offer_is_genuine(self):
        g = _g(IIUM_OFFER)
        self.assertEqual((g['status'], g['type'], g['probability'], g['model_version']),
                         ('genuine', 'ua_offer', 0.9, MODEL_VERSION))
        self.assertEqual(set(g['missing']), {'Program / Kod Program'})

    def test_a_bare_title_line_still_reads_as_the_offer_line(self):
        self.assertIn('offer/admission line', _g(IIUM_BARE_TITLE)['present'])
        self.assertEqual(_g(IIUM_BARE_TITLE)['status'], 'genuine')

    def test_the_smallest_english_letter_clears_the_band(self):
        g = _g(IIUM_MINIMAL)
        self.assertEqual((g['status'], g['probability']), ('genuine', 0.7))

    def test_iiums_foundation_centre_is_iium(self):
        self.assertEqual(_g(IIUM_CFS)['status'], 'genuine')

    def test_through_assess_as_production_calls_it(self):
        self.assertEqual(assess('offer_letter', ocr_text=IIUM_OFFER)['status'], 'genuine')

    def test_the_model_version(self):
        self.assertEqual(MODEL_VERSION, '1.26.0')


class EnglishNonOffersAreNotGenuine(SimpleTestCase):

    def test_the_admission_booklet_is_not_the_offer(self):
        g = _g(IIUM_BOOKLET)
        self.assertNotIn('offer/admission line', g['present'])
        self.assertEqual((g['status'], g['probability']), ('suspect', 0.4))

    def test_a_conditional_or_provisional_offer_is_not_the_offer_line(self):
        for name, text in (('conditional', IIUM_CONDITIONAL), ('provisional', IIUM_PROVISIONAL)):
            with self.subTest(name):
                g = _g(text)
                self.assertNotIn('offer/admission line', g['present'])
                self.assertNotEqual(g['status'], 'genuine')

    def test_a_notification_is_not_the_offer_line(self):
        self.assertNotIn('offer/admission line', _g(IIUM_NOTIFICATION)['present'])
        self.assertNotEqual(_g(IIUM_NOTIFICATION)['status'], 'genuine')


class PrivateLettersStillRefused(SimpleTestCase):

    def test_a_private_college_that_cites_iium_does_not_gain_its_name(self):
        g = _g(PRIVATE_MENTIONS_IIUM)
        self.assertNotIn('public university (UA) name', g['present'])
        self.assertNotEqual(g['status'], 'genuine')

    def test_a_private_company_letter_naming_iium_is_vetoed(self):
        g = _g(PRIVATE_SDN_BHD)
        self.assertEqual(g['status'], 'not_offer_letter')

    def test_a_private_partner_letterhead_is_blocked(self):
        g = _g(PRIVATE_PARTNER)
        self.assertNotEqual(g['status'], 'genuine')

    def test_iiums_fee_paying_arms_stay_not_an_offer(self):
        for name, text in (('IIUM Academy', IIUM_ACADEMY), ('CENPACE', IIUM_CENPACE),
                           ('Sdn Bhd', IIUM_SDN_BHD), ('Saluran Terbuka', IIUM_SATU)):
            with self.subTest(name):
                self.assertTrue(_private_arm_offer(text))
                self.assertEqual(_g(text)['status'], 'not_offer_letter')

    def test_the_veto_reads_the_extracted_issuer_too(self):
        """`pathway_engine` gate 3b and `catalogue_levels.private_arm_letter` read the same veto."""
        self.assertTrue(_private_arm_offer('IIUM Academy of Graduate & Professional Studies'))
        self.assertFalse(_private_arm_offer('ACADEMIC MANAGEMENT AND ADMISSION DIVISION (AMAD), '
                                            'International Islamic University Malaysia'))


class EveryOtherLetterScoresAsUnder1250(SimpleTestCase):

    def test_the_malay_family_and_the_ua_names_are_untouched(self):
        self.assertEqual(UA_OFFER_SIGNATURES, _UA_1_25_0)
        self.assertEqual(len(_UA_NAMES), 20)
        self.assertNotIn('INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA', _UA_NAMES)

    def test_the_english_reading_is_the_same_rows_and_weights(self):
        self.assertEqual([(lb, w, k) for lb, _p, w, k in UA_OFFER_SIGNATURES_EN],
                         [(lb, w, k) for lb, _p, w, k in UA_OFFER_SIGNATURES])
        for (_l, en, _w, _k), (_l2, ms, _w2, _k2) in zip(UA_OFFER_SIGNATURES_EN, UA_OFFER_SIGNATURES):
            self.assertEqual(en[:len(ms)], ms)                  # each Malay row, its English twins after it

    def test_the_english_reading_is_closed_on_every_other_letter(self):
        texts = {n: getattr(fixtures, n) for n in (
            'GENUINE_STPM_OFFER', 'GENUINE_MATRIC_OFFER', 'GENUINE_POLY_OFFER', 'CROPPED_STPM_OFFER',
            'UNIVERSITY_OFFER', 'GENUINE_PISMP_OFFER', 'PISMP_ANNOUNCEMENT', 'GENUINE_UTHM_OFFER',
            'GENUINE_UPNM_OFFER', 'PRIVATE_UNIV_OFFER')}
        texts.update({'ILKBS_OFFER': c1.ILKBS_OFFER, 'FORGED_UNNAMED': c1.FORGED_UNNAMED,
                      'UITM_TEXT_LAYER': c1.UITM_TEXT_LAYER, 'KPTM': c1.KPTM, 'UNIKL': c1.UNIKL,
                      'UITM_OFFER': c2.UITM_OFFER, 'UM_PEMAKLUMAN': c2.UM_PEMAKLUMAN,
                      'PRIVATE_MENTIONS_IIUM': PRIVATE_MENTIONS_IIUM, 'PRIVATE_PARTNER': PRIVATE_PARTNER,
                      **{f'probe {k}': v for k, v in c1.REVIEW_PROBES.items()}})
        for name, text in texts.items():
            with self.subTest(name):
                tn = _norm_fold_upper_alnum(text)
                self.assertEqual(english_ua_lists(_OFFER_LISTS, tn), (_OFFER_LISTS, tn))

    def test_a_private_english_letter_gains_nothing_from_english_wording(self):
        """Private colleges write English: the English offer title / registration / finality words score
        nothing on a page that is not IIUM's, so a private letter stays not_offer_letter (Swinburne)."""
        from apps.scholarship.genuineness.results_doc import score_signatures
        self.assertEqual(_g(fixtures.PRIVATE_UNIV_OFFER)['status'], 'not_offer_letter')
        r = score_signatures(fixtures.PRIVATE_UNIV_OFFER, doc_type='offer_letter')
        self.assertEqual(r['scores']['ua_offer']['probability'], 0.0)


class TD145EnglishNameMatchesTheCatalogue(TestCase):
    """The letter's English name against the catalogue's UNIV-006 ("Universiti Islam Antarabangsa Malaysia",
    acronym UIAM) — a one-campus course, as app 523's STPM degree is. Before the alias it read 'unknown'."""

    @classmethod
    def setUpTestData(cls):
        from apps.scholarship.tests.test_offer_course_match import seed_realign_catalogue
        seed_realign_catalogue()            # UY6380001 is offered at ONE campus: RA-UIAM (UIAM)

    def _agree(self, inst, issuer=''):
        from apps.scholarship.offer_pathway import institution_agreement
        return institution_agreement('UY6380001', 'Universiti Islam Antarabangsa Malaysia', inst, issuer)

    def test_the_english_name_is_a_match(self):
        self.assertEqual(self._agree('International Islamic University Malaysia',
                                     'ACADEMIC MANAGEMENT AND ADMISSION DIVISION (AMAD), International Islamic '
                                     'University Malaysia'), 'match')

    def test_the_english_acronym_is_a_match(self):
        self.assertEqual(self._agree('IIUM GOMBAK'), 'match')

    def test_the_malay_name_still_matches_and_another_university_still_clashes(self):
        self.assertEqual(self._agree('Universiti Islam Antarabangsa Malaysia'), 'match')
        self.assertEqual(self._agree('Universiti Malaya'), 'clash')
