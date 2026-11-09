"""Request #66 (MODEL_VERSION 1.26.0): IIUM / UIAM writes its offer letters in ENGLISH.

Doc 5105's genuine IIUM letter read `not_offer_letter` ("1/10 polytechnic signatures") because the UA family
knew IIUM only by its Malay name and Malay wording. Every page below is SYNTHETIC, in the REAL layout and fixed
wording of that letter (its stored text layer, read by review rounds 1 and 2) and of IIUM's public admission
booklet: no name, IC, address or programme of any applicant. The real letterhead is an IMAGE, so the text opens
with four lines (reference, date, the candidate's name and address), "Dear …", then the offer sentence with IIUM
as its subject; the office is only in the signature block and the acceptance form; there is no title. The
private and non-offer pages are invented to prove the English reading opens only on IIUM's own unconditional
offer, issued by IIUM itself.
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

# ── IIUM's offer, in the real layout ──────────────────────────────────────────────────────
_TOP = 'Our Ref : IIUM/AMAD/0000\nDate : 1 August 2024\nCALON CONTOH\nNo. 1, Jalan Contoh, 43000 Kajang\n'
_DEAR = 'Dear Sir / Madam,\n'
_SENTENCE = ('We are pleased to inform you that the International Islamic University Malaysia (IIUM) has accepted and '
             'approved your application for the following programme in Semester 1, 2024/2025:\n')
_REST = """PROGRAMME : BACHELOR OF CONTOH STUDIES (HONOURS)
KULLIYYAH : KULLIYYAH OF CONTOH
Tuition Fee : RM510.00 per semester
Yours sincerely,
Director
Academic Management and Admission Division
TERMS AND CONDITIONS OF THE OFFER
1. This offer is valid for one (1) year only from the date of issuance.
2. This offer has to be read together with the Terms and Conditions of the Admission Offer and Registration.
3. The University reserves the right to revoke the Offer Letter.
Registration Date : 7 September 2024
We hope that you will accept this offer and join us.
ACCEPTANCE FORM
To: Director, Academic Management and Admission Division
"""
IIUM_OFFER = _TOP + _DEAR + _SENTENCE + _REST
# A text letterhead naming only IIUM and its office (a scan or another print of the same letter).
_IIUM_HEAD = 'INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA\nAcademic Management and Admission Division\n'
_ADDR = 'Jalan Contoh, 43000 Kajang\n'
IIUM_TEXT_LETTERHEAD = _IIUM_HEAD + _ADDR + IIUM_OFFER
# 5105's own close: "Wassalam", then "Director", then the office (no "Yours sincerely"), the signatory's name
# between them.
IIUM_WASSALAM = IIUM_OFFER.replace('Yours sincerely,\nDirector\n', 'Wassalam\n"Knowledge and Virtue"\n'
                                   'DR. CONTOH BIN CONTOH\nDirector\n')
IIUM_UNCONDITIONAL = _TOP + 'UNCONDITIONAL OFFER OF ADMISSION\n' + _DEAR + _SENTENCE + _REST
IIUM_CONDITIONAL_UPON = IIUM_OFFER.replace('3. The University', '3. Registration is conditional upon the original '
                                           'documents.\n4. The University')

# ── IIUM's pages that are NOT its unconditional offer ─────────────────────────────────────
NON_OFFERS = {
    'conditional title': _TOP + 'CONDITIONAL OFFER OF ADMISSION\n' + _DEAR + _SENTENCE + _REST,
    'conditional in brackets': _TOP + 'OFFER OF ADMISSION (CONDITIONAL)\n' + _DEAR + _SENTENCE + _REST,
    'conditional split over two lines': _TOP + 'CONDITIONAL\nOFFER OF ADMISSION\n' + _DEAR + _SENTENCE + _REST,
    'conditional in the sentence': _TOP + _DEAR + _SENTENCE.replace(':\n', ' on a conditional basis:\n') + _REST,
    'provisional': _TOP + 'PROVISIONAL OFFER OF ADMISSION\n' + _DEAR + _SENTENCE + _REST,
    'notification': _TOP + 'NOTIFICATION OF ADMISSION\n' + _DEAR + _SENTENCE + _REST,
    'rejection form': _TOP + 'REJECTION OF OFFER OF ADMISSION TO IIUM\nI hereby reject the offer of admission to '
                             'the programme.\n' + _REST,
    'acceptance form': _TOP + 'ACCEPTANCE FORM\nI accept the offer of admission to the programme.\n' + _REST,
    'unsuccessful': _TOP + _DEAR + 'We regret to inform you that your application for offer of admission for '
                                   'Semester 1, 2024/2025 to the International Islamic University Malaysia was '
                                   'unsuccessful.\n' + _REST,
    'booklet': 'STUDENT ADMISSION BOOKLET\nAcademic Management and Admission Division (AMAD)\nInternational '
               'Islamic University Malaysia (IIUM)\nOtherwise this offer of admission will be automatically revoked.\n',
}

# ── Private letters riding on IIUM's sentence, name or office (review rounds 1-2) ─────────
ATTACKS = {
    'another college after IIUM, before the address': _IIUM_HEAD + 'MERCU COLLEGE\n' + _ADDR + IIUM_OFFER,
    'another college after the address': _IIUM_HEAD + _ADDR + 'MERCU COLLEGE\n' + IIUM_OFFER,
    'affiliated college': _IIUM_HEAD + 'AFFILIATED COLLEGE: MERCU COLLEGE\n' + _ADDR + IIUM_OFFER,
    'in association with, above IIUM': 'IN ASSOCIATION WITH MERCU UNIVERSITY COLLEGE\n' + _IIUM_HEAD + _ADDR
                                       + IIUM_OFFER,
    'in association with, below IIUM': _IIUM_HEAD + 'IN ASSOCIATION WITH MERCU UNIVERSITY COLLEGE\n' + _ADDR
                                       + IIUM_OFFER,
    'franchise programme': _IIUM_HEAD + 'FRANCHISE PROGRAMME\n' + _ADDR + IIUM_OFFER,
    'validated by IIUM': 'Programme validated by INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA\n' + _ADDR + IIUM_OFFER,
    'a partner as the subject': _TOP + _DEAR + _SENTENCE.replace('that the International', 'that Mercu Academy, a '
                                                                 'partner of the International').replace(
                                    '(IIUM) has', '(IIUM), has') + _REST,
    'relayed by an agent': 'MERCU COLLEGE\n' + _ADDR + IIUM_OFFER,
    'IIUM Holdings Berhad after the postcode': _IIUM_HEAD + _ADDR + 'IIUM HOLDINGS BERHAD\n' + IIUM_OFFER,
    'in collaboration with': 'MERCU UNIVERSITY COLLEGE\nIn collaboration with International Islamic University '
                             'Malaysia, Academic Management and Admission Division\n' + _ADDR + IIUM_OFFER,
    'processed by AMAD': 'MERCU UNIVERSITY COLLEGE\n' + _ADDR + _TOP + _DEAR
                         + _SENTENCE.replace('We are pleased', 'Mercu University College is pleased')
                         + 'Admission is processed with the Academic Management and Admission Division of IIUM.\n'
                         + _REST,
    'a private company': 'MERCU EDUCATION SDN BHD\n' + _ADDR + IIUM_OFFER,
    # Final review: a tie-up word AFTER the sentence, a private signatory, a campus above "Dear".
    'a teaching partner after the sentence': IIUM_OFFER.replace(
        'in Semester 1, 2024/2025:', 'in Semester 1, 2024/2025 at Mercu College, our teaching partner campus:'),
    'a private signatory': IIUM_OFFER.replace('Director\nAcademic Management and Admission Division\nTERMS',
                                              'Registrar\nMERCU UNIVERSITY COLLEGE\nTERMS'),
    'a private signatory above the office': IIUM_OFFER.replace(
        'Director\nAcademic', 'Registrar, MERCU UNIVERSITY COLLEGE\nfor Academic'),
    'a campus above Dear': _TOP + 'MERCU CAMPUS\n' + _DEAR + _SENTENCE + _REST,
    # Last round: IIUM closes with "Wassalam" (no "Yours …"); the signature check is anchored on the office.
    'no closing, a private signatory': IIUM_WASSALAM.replace(
        'Wassalam\n"Knowledge and Virtue"\nDR. CONTOH BIN CONTOH\nDirector\n', 'Registrar\nMERCU UNIVERSITY COLLEGE\n'),
    'Wassalam, a private signatory': IIUM_WASSALAM.replace('Director\n', 'Registrar\nMERCU UNIVERSITY COLLEGE\n'),
    'a private line after the office': IIUM_WASSALAM.replace(
        'Academic Management and Admission Division\nTERMS',
        'Academic Management and Admission Division\nfor MERCU UNIVERSITY COLLEGE\nTERMS'),
    # Final review (2026-11-08): a signatory naming a private GROUP carries no college/company noun.
    'a private education group signs': IIUM_WASSALAM.replace('Director\n', 'Registrar\nMERCU EDUCATION GROUP\n'),
}
# IIUM's fee-paying arms, on IIUM's own sentence and office.
IIUM_ACADEMY = IIUM_OFFER.replace('Director\n', 'Director\nIIUM Academy of Graduate & Professional Studies\n')
IIUM_CENPACE = IIUM_OFFER.replace('Director\n', 'Director\nCentre for Professional and Continuing Education '
                                                '(CENPACE)\n')
IIUM_SDN_BHD = IIUM_OFFER.replace('Tuition Fee', 'IIUM Contoh Services Sdn Bhd\nTuition Fee')
IIUM_SATU = IIUM_OFFER.replace('Semester 1', 'Saluran Terbuka, Semester 1')
PRIVATE_COLLABORATION = ATTACKS['in collaboration with']

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

    def test_iiums_real_layout_is_genuine(self):
        """Name 3 + sentence 3 + office 1 + "This offer is valid for" 1 + "Registration Date" 1 = 9 of 10."""
        g = _g(IIUM_OFFER)
        self.assertEqual((g['status'], g['type'], g['probability'], g['model_version']),
                         ('genuine', 'ua_offer', 0.9, MODEL_VERSION))
        self.assertEqual(g['missing'], ['Program / Kod Program'])

    def test_a_text_letterhead_naming_only_iium_is_genuine_too(self):
        self.assertEqual((_g(IIUM_TEXT_LETTERHEAD)['status'], _g(IIUM_TEXT_LETTERHEAD)['probability']),
                         ('genuine', 0.9))

    def test_unconditional_and_conditional_upon_in_the_terms_are_fine(self):
        for name, text in (('unconditional title', IIUM_UNCONDITIONAL), ('terms', IIUM_CONDITIONAL_UPON)):
            with self.subTest(name):
                self.assertEqual(_g(text)['status'], 'genuine')

    def test_the_real_signature_block_and_lower_pages_are_fine(self):
        """5105's signature is "Director / Academic Management and Admission Division"; its lower pages name the
        university, kulliyyahs and banks — no rule reads organisations below the signature block."""
        text = IIUM_OFFER.replace('ACCEPTANCE FORM', 'Payment to Bank Islam Malaysia Berhad, Mahallah Contoh, '
                                  'Kulliyyah of Contoh, Gombak Campus\nACCEPTANCE FORM')
        self.assertEqual(_g(text)['status'], 'genuine')

    def test_iiums_own_wassalam_close_is_genuine(self):
        self.assertIn('Wassalam', IIUM_WASSALAM)
        self.assertNotIn('Yours', IIUM_WASSALAM)
        self.assertNotIn('Wassalam', ATTACKS['no closing, a private signatory'])
        self.assertEqual((_g(IIUM_WASSALAM)['status'], _g(IIUM_WASSALAM)['probability']), ('genuine', 0.9))

    def test_through_assess_as_production_calls_it(self):
        self.assertEqual(assess('offer_letter', ocr_text=IIUM_OFFER)['status'], 'genuine')

    def test_the_model_version(self):
        self.assertGreaterEqual(tuple(map(int, MODEL_VERSION.split('.'))), (1, 26, 0))


def _closed(case, text):
    tn = _norm_fold_upper_alnum(text)
    case.assertEqual(english_ua_lists(_OFFER_LISTS, tn, text), (_OFFER_LISTS, tn))
    case.assertEqual(_g(text)['status'], 'not_offer_letter')


class IIUMNonOffersKeepThe1250Call(SimpleTestCase):
    """The English reading stays CLOSED: each page scores exactly as under 1.25.0 (not_offer_letter)."""

    def test_none_is_genuine_and_none_reads_the_english_twins(self):
        for name, text in NON_OFFERS.items():
            with self.subTest(name):
                _closed(self, text)


class PrivateLettersStillRefused(SimpleTestCase):

    def test_no_private_letter_on_iiums_sentence_opens_the_english_reading(self):
        for name, text in ATTACKS.items():
            with self.subTest(name):
                _closed(self, text)

    def test_collaboration_on_a_letterhead_is_tie_up_proof(self):
        """`offer_reading._TIE_UP` gained "collaboration" (beside an institution noun on the letterhead block)."""
        self.assertEqual(private_proof(_folded_lines(PRIVATE_COLLABORATION)), 'tie-up wording')

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
                      **{f'attack {k}': v for k, v in ATTACKS.items()},
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
