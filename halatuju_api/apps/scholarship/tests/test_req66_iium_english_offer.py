"""Request #66 (MODEL_VERSION 1.26.0): IIUM / UIAM writes its offer letters in ENGLISH.

Doc 5105's genuine IIUM letter read `not_offer_letter` ("1/10 polytechnic signatures") because the UA family
knew IIUM only by its Malay name and Malay wording. Every page below is SYNTHETIC, built from the REAL fixed
wording of that letter (its stored text layer, read by the review of fc7eef0b) and of IIUM's public admission
booklet: no name, IC, address or programme of any applicant. The real letter has NO title; its offer is the
sentence "... has accepted and approved your application for the following programme ...". The private and
non-offer pages are invented to prove the English reading opens only on IIUM's own unconditional offer.
"""
from django.test import SimpleTestCase, TestCase

from apps.scholarship.genuineness import assess, signature_genuineness
from apps.scholarship.genuineness.offer_reading import _folded_lines, private_proof
from apps.scholarship.genuineness.offer_signatures import UA_OFFER_SIGNATURES_EN, english_ua_lists
from apps.scholarship.genuineness.results_doc import (MODEL_VERSION, UA_OFFER_SIGNATURES, _OFFER_LISTS, _UA_NAMES,
                                                      _norm_fold_upper_alnum, _private_arm_offer)
from apps.scholarship.tests import test_corpus_gaps_c1 as c1
from apps.scholarship.tests import test_corpus_gaps_c2 as c2
from apps.scholarship.tests import test_doc_signatures as fixtures

# ── IIUM's offer, in its real wording (page 1: letterhead + offer; page 3: terms + registration) ──
_HEAD = """INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA
Academic Management and Admission Division
P.O. Box 10, 50728 Kuala Lumpur
Our Ref : IIUM/AMAD/0000
Date : 1 August 2024
"""
_P1 = """Name : CALON CONTOH
Dear Sir / Madam,
We are pleased to inform you that the International Islamic University Malaysia (IIUM) has accepted and approved \
your application for the following programme in Semester 1, 2024/2025:
PROGRAMME : BACHELOR OF CONTOH STUDIES (HONOURS)
KULLIYYAH : KULLIYYAH OF CONTOH
Tuition Fee : RM510.00 per semester
"""
_P3 = """TERMS AND CONDITIONS OF THE OFFER
1. This offer is valid for one (1) year only from the date of issuance.
2. This offer has to be read together with the Terms and Conditions of the Admission Offer and Registration.
3. The University reserves the right to revoke the Offer Letter.
Registration Date : 7 September 2024
We hope that you will accept this offer and join us.
Yours sincerely,
Director
Academic Management and Admission Division
"""
IIUM_OFFER = _HEAD + _P1 + _P3
IIUM_UNCONDITIONAL = _HEAD + 'UNCONDITIONAL OFFER OF ADMISSION\n' + _P1 + _P3
# IIUM's own Centre for Foundation Studies (its public foundation, a unit of the university).
IIUM_CFS = IIUM_OFFER.replace('Academic Management and Admission Division\nP.O.',
                              'Centre for Foundation Studies\nAcademic Management and Admission Division\nP.O.')

# ── IIUM's pages that are NOT its unconditional offer ─────────────────────────────────────
_SENTENCE = 'has accepted and approved your application for the following programme'
IIUM_CONDITIONAL = _HEAD + 'CONDITIONAL OFFER OF ADMISSION\n' + _P1 + _P3
IIUM_CONDITIONAL_BRACKET = _HEAD + 'OFFER OF ADMISSION (CONDITIONAL)\n' + _P1 + _P3
IIUM_CONDITIONAL_SPLIT = _HEAD + 'CONDITIONAL\nOFFER OF ADMISSION\n' + _P1 + _P3
IIUM_CONDITIONAL_NO_SENTENCE = (_HEAD + 'CONDITIONAL OFFER OF ADMISSION\nName : CALON CONTOH\n'
                                'PROGRAMME CODE : UY0000000\n' + _P3)
IIUM_PROVISIONAL = _HEAD + 'PROVISIONAL OFFER OF ADMISSION\n' + _P1 + _P3
IIUM_NOTIFICATION = _HEAD + 'NOTIFICATION OF ADMISSION\n' + _P1 + _P3
IIUM_REJECTION_FORM = _HEAD + """REJECTION OF OFFER OF ADMISSION TO IIUM
Name : CALON CONTOH
I hereby reject the offer of admission to the programme stated in the Offer Letter.
This offer is valid for one (1) year only from the date of issuance.
Registration Date : 7 September 2024
"""
IIUM_ACCEPTANCE_FORM = _HEAD + """ACCEPTANCE FORM
Name : CALON CONTOH
I accept the offer of admission to the programme and will register on the Registration Date stated.
This offer is valid for one (1) year only from the date of issuance.
"""
IIUM_UNSUCCESSFUL = _HEAD + """Name : CALON CONTOH
Dear Sir / Madam,
We regret to inform you that your application for offer of admission for Semester 1, 2024/2025 was unsuccessful.
This offer is valid for one (1) year only from the date of issuance.
Academic Management and Admission Division
"""
# IIUM's ADMISSION BOOKLET (sent with the offer): the name, AMAD and "offer of admission" in its sentences.
IIUM_BOOKLET = """STUDENT ADMISSION BOOKLET
UNDERGRADUATE PROGRAMME
Academic Management and Admission Division (AMAD)
International Islamic University Malaysia (IIUM)
Congratulations to all for being selected to join the International Islamic University Malaysia.
You are required to fill the ONLINE acceptance form within the stipulated date as stated in the ONLINE
OFFER LETTER webpage. Otherwise this offer of admission will be automatically revoked.
PLEASE PRINT THE OFFER LETTER AND KEEP IT SAFE.
"""

# ── Private letters that cite IIUM, its office, or its sentence ───────────────────────────
_PRIVATE_REF = 'Jalan Contoh, 43000 Kajang\nOur Ref : MUC/0000\nDate : 1 August 2024\n'
PRIVATE_COLLABORATION = ('MERCU UNIVERSITY COLLEGE\nIn collaboration with International Islamic University '
                         'Malaysia, Academic Management and Admission Division\n' + _PRIVATE_REF + _P1 + _P3)
PRIVATE_PROCESSED_BY_AMAD = ('MERCU UNIVERSITY COLLEGE\n' + _PRIVATE_REF + 'Name : CALON CONTOH\nDear Sir / Madam,\n'
                             'The International Islamic University Malaysia (IIUM) ' + _SENTENCE + ':\n'
                             'PROGRAMME : DIPLOMA IN CONTOH\nAdmission is processed with the Academic Management '
                             'and Admission Division of IIUM.\n' + _P3)
PRIVATE_SDN_BHD = 'MERCU EDUCATION SDN BHD\n' + _PRIVATE_REF + _P1 + _P3
# IIUM's fee-paying arms, on IIUM's own name, office and sentence.
IIUM_ACADEMY = IIUM_OFFER.replace('P.O. Box 10', 'IIUM Academy of Graduate & Professional Studies\nP.O. Box 10')
IIUM_CENPACE = IIUM_OFFER.replace('P.O. Box 10', 'Centre for Professional and Continuing Education (CENPACE)\n'
                                                 'P.O. Box 10')
IIUM_SDN_BHD = IIUM_OFFER.replace('P.O. Box 10', 'IIUM Contoh Services Sdn Bhd, P.O. Box 10')
IIUM_SATU = IIUM_OFFER.replace('Semester 1', 'Saluran Terbuka, Semester 1')

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

    def test_iiums_real_wording_is_genuine(self):
        """Name 3 + sentence 3 + office 1 + "This offer is valid for" 1 + "Registration Date" 1 = 9 of 10."""
        g = _g(IIUM_OFFER)
        self.assertEqual((g['status'], g['type'], g['probability'], g['model_version']),
                         ('genuine', 'ua_offer', 0.9, MODEL_VERSION))
        self.assertEqual(g['missing'], ['Program / Kod Program'])

    def test_an_unconditional_offer_is_not_a_conditional_one(self):
        self.assertEqual((_g(IIUM_UNCONDITIONAL)['status'], _g(IIUM_UNCONDITIONAL)['probability']), ('genuine', 0.9))

    def test_iiums_foundation_centre_is_iium(self):
        self.assertEqual(_g(IIUM_CFS)['status'], 'genuine')

    def test_through_assess_as_production_calls_it(self):
        self.assertEqual(assess('offer_letter', ocr_text=IIUM_OFFER)['status'], 'genuine')

    def test_the_model_version(self):
        self.assertEqual(MODEL_VERSION, '1.26.0')


class IIUMNonOffersKeepThe1250Call(SimpleTestCase):
    """The English reading stays CLOSED: each page scores exactly as under 1.25.0 (not_offer_letter)."""

    PAGES = {'conditional title': IIUM_CONDITIONAL, 'conditional in brackets': IIUM_CONDITIONAL_BRACKET,
             'conditional split over two lines': IIUM_CONDITIONAL_SPLIT,
             'conditional without the sentence': IIUM_CONDITIONAL_NO_SENTENCE, 'provisional': IIUM_PROVISIONAL,
             'notification': IIUM_NOTIFICATION, 'rejection form': IIUM_REJECTION_FORM,
             'acceptance form': IIUM_ACCEPTANCE_FORM, 'unsuccessful': IIUM_UNSUCCESSFUL, 'booklet': IIUM_BOOKLET}

    def test_none_is_genuine_and_none_reads_the_english_twins(self):
        for name, text in self.PAGES.items():
            with self.subTest(name):
                tn = _norm_fold_upper_alnum(text)
                self.assertEqual(english_ua_lists(_OFFER_LISTS, tn, text), (_OFFER_LISTS, tn))
                self.assertEqual(_g(text)['status'], 'not_offer_letter')


class PrivateLettersStillRefused(SimpleTestCase):

    def test_a_private_college_in_collaboration_with_iium_is_refused(self):
        g = _g(PRIVATE_COLLABORATION)
        self.assertNotIn('public university (UA) name', g['present'])
        self.assertEqual(g['status'], 'not_offer_letter')

    def test_collaboration_on_a_letterhead_is_tie_up_proof(self):
        self.assertEqual(private_proof(_folded_lines(PRIVATE_COLLABORATION)), 'tie-up wording')

    def test_a_private_college_whose_admission_amad_processes_is_refused(self):
        g = _g(PRIVATE_PROCESSED_BY_AMAD)
        self.assertNotIn('public university (UA) name', g['present'])
        self.assertEqual(g['status'], 'not_offer_letter')

    def test_a_private_company_with_iiums_sentence_is_vetoed(self):
        self.assertEqual(_g(PRIVATE_SDN_BHD)['status'], 'not_offer_letter')

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
                      'PRIVATE_COLLABORATION': PRIVATE_COLLABORATION,
                      'PRIVATE_PROCESSED_BY_AMAD': PRIVATE_PROCESSED_BY_AMAD,
                      **{f'probe {k}': v for k, v in c1.REVIEW_PROBES.items()}})
        for name, text in texts.items():
            with self.subTest(name):
                tn = _norm_fold_upper_alnum(text)
                self.assertEqual(english_ua_lists(_OFFER_LISTS, tn, text), (_OFFER_LISTS, tn))

    def test_a_private_english_letter_gains_nothing_from_english_wording(self):
        """Private colleges write English: the English twins score nothing on a page that is not IIUM's."""
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
