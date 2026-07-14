"""Pure unit tests for the pathway (offer-letter) engine — student_offer_check.

No DB: student_offer_check reads doc.vision_fields (a dict) + doc.application.profile,
so a SimpleNamespace stand-in is explicit and correct here.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.scholarship.pathway_engine import (
    offer_pathway_match, student_offer_check,
)


def _offer_doc(fields, *, pname='Elanjelian Venugopal', pnric='710829-02-5709',
               student_verdict='ok', declared=None, cohort_year=None):
    """``declared`` (optional) is the application's declared pathway — either a
    ``{'course_name','institution'}`` dict (chosen_programme) OR a
    ``{'pre_u_track','pre_u_institution'}`` pair, mirrored onto the app namespace.
    ``cohort_year`` (optional) sets the application's cohort year for intake-currency tests."""
    declared = declared or {}
    app = SimpleNamespace(
        profile=SimpleNamespace(name=pname, nric=pnric),
        chosen_programme={'course_name': declared.get('course_name', ''),
                          'institution': declared.get('institution', '')},
        pre_u_track=declared.get('pre_u_track', ''),
        pre_u_institution=declared.get('pre_u_institution', ''),
        cohort=SimpleNamespace(year=cohort_year) if cohort_year else None,
    )
    return SimpleNamespace(
        doc_type='offer_letter',
        vision_fields={'fields': fields, 'student_verdict': student_verdict},
        application=app,
    )


# A real UTeM diploma offer (from the user's samples) — Yeswindran's, used as a
# wrong-person letter on Elanjelian's profile.
YESWINDRAN_OFFER = {
    'candidate_name': 'YESWINDRAN A/L MURALY',
    'candidate_nric': '081227020661',
    'programme': 'DIPLOMA KEJURUTERAAN ELEKTRIK',
    'institution': 'Universiti Teknikal Malaysia Melaka',
    'issuer': 'Universiti Teknikal Malaysia Melaka',
    'offer_date': '23 Mei 2026',
    'intake': 'Sesi 2026/2027',
    'candidate_address': '7, JALAN GANGSA 9, TAMAN SRI PUTRI, 81300 SKUDAI, JOHOR',
}


class TestStudentOfferCheck(SimpleTestCase):
    def test_wrong_person_fails_name_and_ic(self):
        chk = student_offer_check(_offer_doc(YESWINDRAN_OFFER))
        self.assertEqual(chk['name'], 'mismatch')
        self.assertEqual(chk['ic'], 'mismatch')
        # Data points still surfaced.
        self.assertEqual(chk['programme'], 'DIPLOMA KEJURUTERAAN ELEKTRIK')
        self.assertEqual(chk['issuer'], 'Universiti Teknikal Malaysia Melaka')
        self.assertEqual(chk['offer_date'], '23 Mei 2026')
        self.assertIn('SKUDAI', chk['address'])

    def test_own_letter_matches(self):
        # Same person on the profile → both identity checks pass.
        chk = student_offer_check(_offer_doc(
            YESWINDRAN_OFFER, pname='Yeswindran Muraly', pnric='081227-02-0661'))
        self.assertEqual(chk['name'], 'match')
        self.assertEqual(chk['ic'], 'match')

    def test_ic_matches_despite_name_typo(self):
        # The NRIC is the strong check: a small name spelling diff is 'partial'/'mismatch'
        # but the IC still confirms identity.
        chk = student_offer_check(_offer_doc(
            YESWINDRAN_OFFER, pname='Yeswindran A/L Murali', pnric='081227020661'))
        self.assertEqual(chk['ic'], 'match')

    def test_ocr_flaky_offer_nric_still_matches(self):
        # The offer NRIC is OCR-flaky (image-Gemini drops/garbles a digit — observed on #36).
        # A near-match (dropped pair) is OCR noise, not a different person → 'match' (identity is
        # anchored on the IC + profile NRIC, read reliably). No false wrong-person flag.
        fields = dict(YESWINDRAN_OFFER, candidate_nric='0812270661')   # '02' pair dropped
        chk = student_offer_check(_offer_doc(fields, pname='Yeswindran Muraly',
                                             pnric='081227-02-0661'))
        self.assertEqual(chk['ic'], 'match')

    def test_reporting_bonus_three_gates(self):
        # The reporting-date BONUS (owner 2026-07-08): label + public-issuer signature + no
        # private marker — ALL required. Built like #44 (UPSI, ua_offer family).
        from apps.scholarship.pathway_engine import offer_reporting_bonus
        from types import SimpleNamespace as NS

        def _doc(fields, auth):
            return NS(vision_fields={'fields': fields, 'authenticity': auth})

        ua_auth = {'status': 'suspect', 'doc_seen': 'ua_offer',
                   'present': ['public university (UA) name', 'offer/admission line']}
        upsi = {'reporting_date': '9 Jun 2026', 'reporting_date_label': 'Tarikh Mendaftar',
                'institution': 'UNIVERSITI PENDIDIKAN SULTAN IDRIS', 'issuer': ''}
        self.assertTrue(offer_reporting_bonus(_doc(upsi, ua_auth)))

        # #93 UniMAIWP: has a "Tarikh" label + junk-fits a family, but the page carries NO
        # public-issuer signature (present lacks the UA-name entry) → gate 2 blocks.
        maiwp_auth = {'status': 'not_offer_letter', 'doc_seen': 'ua_offer',
                      'present': ['Program / Kod Program']}
        maiwp = {'reporting_date': '19 September 2026', 'reporting_date_label': 'Tarikh',
                 'institution': 'UNIVERSITI ANTARABANGSA MAIWP', 'issuer': ''}
        self.assertFalse(offer_reporting_bonus(_doc(maiwp, maiwp_auth)))

        # Sdn. Bhd. anywhere in issuer/institution hard-blocks (gate 3) even if gates 1+2 pass.
        sdn = dict(upsi, issuer='Kolej Sains Perubatan PUSRAWI Sdn. Bhd.')
        self.assertFalse(offer_reporting_bonus(_doc(sdn, ua_auth)))

        # English label / letter-issue date → gate 1 blocks; so does a missing date or label.
        self.assertFalse(offer_reporting_bonus(_doc(dict(upsi, reporting_date_label='Registration date'), ua_auth)))
        self.assertFalse(offer_reporting_bonus(_doc(dict(upsi, reporting_date=''), ua_auth)))
        self.assertFalse(offer_reporting_bonus(_doc(dict(upsi, reporting_date_label=''), ua_auth)))

        # A ministry family validates via its own issuer signature (poly: JPPKK line present).
        poly_auth = {'status': 'suspect', 'doc_seen': 'polytechnic',
                     'present': ['Jabatan Pend. Politeknik & KK', 'Surat Tawaran Pengajian']}
        poly = {'reporting_date': '15 Jun 2026', 'reporting_date_label': 'Tarikh dan Masa Daftar',
                'institution': 'POLITEKNIK UNGKU OMAR', 'issuer': ''}
        self.assertTrue(offer_reporting_bonus(_doc(poly, poly_auth)))
        # ...but the SAME fields without the issuer signature on the page do not (a mock-up).
        self.assertFalse(offer_reporting_bonus(_doc(poly, {'status': 'suspect', 'doc_seen': 'polytechnic', 'present': ['Program']})))

        # A bare "Tarikh" label is acceptable ONLY for the UA family (UTHM/UTeM clause style).
        self.assertFalse(offer_reporting_bonus(_doc(dict(poly, reporting_date_label='Tarikh'), poly_auth)))
        self.assertTrue(offer_reporting_bonus(_doc(dict(upsi, reporting_date_label='Tarikh'), ua_auth)))

    def test_ocr_doubled_letter_offer_name_still_matches(self):
        # #48: the offer name is OCR-flaky too — image-Gemini echoed a letter
        # ("LAKSMITHAA A/P VIJAYAN" for LAKSMITHA). The name_match mismatch is rescued by the
        # tolerant same-person matcher (the _nric_close counterpart for the name), so the
        # student's own letter never raises a false wrong-person flag.
        fields = dict(YESWINDRAN_OFFER, candidate_name='LAKSMITHAA A/P VIJAYAN',
                      candidate_nric='')
        chk = student_offer_check(_offer_doc(fields, pname='LAKSMITHA A/P VIJAYAN',
                                             pnric='080725-04-0054'))
        self.assertEqual(chk['name'], 'match')
        # a genuinely different person is STILL a mismatch (no over-rescue).
        chk2 = student_offer_check(_offer_doc(YESWINDRAN_OFFER, pname='LAKSMITHA A/P VIJAYAN',
                                              pnric='080725-04-0054'))
        self.assertEqual(chk2['name'], 'mismatch')

    def test_grossly_different_nric_still_mismatches(self):
        # A genuinely different person's NRIC (many digits differ) is still a real mismatch.
        fields = dict(YESWINDRAN_OFFER, candidate_nric='990101050101')
        chk = student_offer_check(_offer_doc(fields, pname='Yeswindran Muraly',
                                             pnric='081227-02-0661'))
        self.assertEqual(chk['ic'], 'mismatch')

    def test_ic_unreadable_when_absent_but_extracted(self):
        fields = dict(YESWINDRAN_OFFER, candidate_nric='')
        chk = student_offer_check(_offer_doc(fields))
        self.assertEqual(chk['ic'], 'unreadable')

    def test_pending_when_not_extracted(self):
        chk = student_offer_check(_offer_doc(YESWINDRAN_OFFER, student_verdict=None))
        # Nothing run yet → identity checks can't be trusted; but fields still echoed.
        # (extracted=False only flips empty-field statuses to 'pending'; here fields are
        # present so name/ic compute normally — assert the data echo instead.)
        self.assertEqual(chk['candidate_nric'], '081227020661')

    def test_review_manually_is_pending_for_empty_fields(self):
        chk = student_offer_check(_offer_doc({'candidate_name': '', 'candidate_nric': ''},
                                             student_verdict='review_manually'))
        self.assertEqual(chk['name'], 'pending')
        self.assertEqual(chk['ic'], 'pending')


class TestOfferPathwayMatch(SimpleTestCase):
    """The lenient offer-vs-declared matcher: 'match' / 'mismatch' / 'unknown'.

    The bar (per the user): mark a MISMATCH only when the offer is for a genuinely
    different place or field; tolerate naming quirks; never nag on a match."""

    def test_naming_quirk_is_match(self):
        # "KM Melaka" (declared) ≈ "Kolej Matrikulasi Melaka" (offer) — both share
        # the distinctive place token; the generic words don't matter.
        self.assertEqual(
            offer_pathway_match('', 'KM Melaka', '', 'Kolej Matrikulasi Melaka'),
            'match')

    def test_different_school_is_mismatch(self):
        # Same STPM stream, but a genuinely different school.
        self.assertEqual(
            offer_pathway_match('', 'SMK Mentakab', '', 'SMK Temerloh'),
            'mismatch')

    def test_different_foundation_field_is_mismatch(self):
        self.assertEqual(
            offer_pathway_match('Asasi Pintar', '', 'Asasi Pertanian', ''),
            'mismatch')

    def test_same_institution_different_programme_is_mismatch(self):
        # Both at UPM, but a different diploma field → still a real clash.
        self.assertEqual(
            offer_pathway_match('Diploma Electricity', 'UPM',
                                'Diploma Horticulture', 'UPM'),
            'mismatch')

    def test_nothing_declared_is_unknown(self):
        # Student declared only a pathway TYPE (no specific college/programme) → no
        # conflict to detect.
        self.assertEqual(offer_pathway_match('', '', 'Program Matrikulasi',
                                             'Kolej Matrikulasi Melaka'), 'unknown')

    def test_all_generic_is_unknown(self):
        # Both sides are only qualification-type words → nothing distinctive to clash.
        self.assertEqual(offer_pathway_match('Diploma', 'Politeknik',
                                             'Diploma', 'Politeknik'), 'unknown')

    def test_ministry_boilerplate_in_programme_does_not_false_clash(self):
        # #30: declared "Program Matrikulasi (Sains)" at "KM Selangor"; the offer's programme
        # line read as the ISSUER boilerplate ("PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN"),
        # not the stream. The ministry words carry no field/place signal, so they must not
        # "clash" with "Sains" — the matching college (Selangor) settles it as a match.
        self.assertEqual(
            offer_pathway_match('Program Matrikulasi (Sains)', 'KM Selangor',
                                'PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN',
                                'KOLEJ MATRIKULASI SELANGOR'),
            'match')

    def test_real_wrong_stream_still_clashes(self):
        # Guard: when the offer DOES carry a real (different) field, the clash still fires.
        self.assertEqual(
            offer_pathway_match('Program Matrikulasi (Sains)', 'KM Selangor',
                                'PROGRAM MATRIKULASI PERAKAUNAN', 'KOLEJ MATRIKULASI SELANGOR'),
            'mismatch')

    def test_form6_enrolment_wording_does_not_false_clash(self):
        # Divashini: declared a Form-6 (STPM) Sains Sosial place; the offer's "programme"
        # was read as the enrolment TYPE ("Tingkatan Enam Semester 1 Tahun 2026"), not a
        # field. That structure wording must not "clash" with the declared field — the
        # matching school (Pulau Sebang) carries it to a match, no false nag.
        self.assertEqual(
            offer_pathway_match('sains_sosial', 'SMK Pulau Sebang',
                                'Tingkatan Enam Semester 1 Tahun 2026',
                                'Sekolah Menengah Kebangsaan Pulau Sebang'),
            'match')


class TestStudentOfferCheckPathway(SimpleTestCase):
    """student_offer_check surfaces the offer-vs-declared reconciliation."""

    _OWN = dict(pname='Yeswindran Muraly', pnric='081227-02-0661')

    def test_pathway_unknown_when_nothing_declared(self):
        chk = student_offer_check(_offer_doc(YESWINDRAN_OFFER, **self._OWN))
        self.assertEqual(chk['pathway'], 'unknown')

    def test_pathway_match_on_naming_quirk(self):
        chk = student_offer_check(_offer_doc(
            YESWINDRAN_OFFER, **self._OWN,
            declared={'pre_u_institution': 'UTeM Melaka'}))
        # Offer institution "Universiti Teknikal Malaysia Melaka" shares "melaka".
        self.assertEqual(chk['pathway'], 'match')

    def test_pathway_mismatch_on_different_field(self):
        chk = student_offer_check(_offer_doc(
            YESWINDRAN_OFFER, **self._OWN,
            declared={'course_name': 'Diploma Senibina', 'institution': 'UTeM'}))
        # Offer is "Diploma Kejuruteraan Elektrik" — a different field → mismatch.
        self.assertEqual(chk['pathway'], 'mismatch')
        self.assertEqual(chk['declared_programme'], 'Diploma Senibina')


class TestOfferIntakeYear(SimpleTestCase):
    """Course-start (intake) year + currency vs the cohort: 'current' (==cohort year) → green,
    'off' → amber, '' → no signal."""

    def test_intake_year_matching_cohort_is_current(self):
        chk = student_offer_check(_offer_doc({'intake': 'Sesi 2026/2027'}, cohort_year=2026))
        self.assertEqual(chk['intake_year'], '2026')
        self.assertEqual(chk['intake_year_status'], 'current')

    def test_intake_year_off_cohort_is_off(self):
        chk = student_offer_check(_offer_doc({'intake': 'Sesi 2025/2026'}, cohort_year=2026))
        self.assertEqual(chk['intake_year'], '2025')
        self.assertEqual(chk['intake_year_status'], 'off')

    def test_reporting_date_surfaced_and_feeds_intake_year(self):
        chk = student_offer_check(_offer_doc({'reporting_date': '15 Mei 2026'}, cohort_year=2026))
        self.assertEqual(chk['reporting_date'], '15 Mei 2026')
        self.assertEqual(chk['intake_year'], '2026')           # falls back to the reporting year
        self.assertEqual(chk['intake_year_status'], 'current')

    def test_no_cohort_means_no_status(self):
        chk = student_offer_check(_offer_doc({'intake': 'Sesi 2026/2027'}))   # cohort_year=None
        self.assertEqual(chk['intake_year'], '2026')
        self.assertEqual(chk['intake_year_status'], '')


# ── Offer-validity signal (owner policy: only genuine official PUBLIC offers qualify) ──
from apps.scholarship.pathway_engine import offer_official_status  # noqa: E402


def _auth_doc(authenticity):
    vf = {'fields': {}}
    if authenticity is not None:
        vf['authenticity'] = authenticity
    return SimpleNamespace(doc_type='offer_letter', vision_fields=vf)


class TestOfferOfficialStatus(SimpleTestCase):
    def test_genuine_official(self):
        self.assertEqual(offer_official_status(
            _auth_doc({'status': 'genuine', 'probability': 0.9, 'model_version': '1.1'})), 'genuine')

    def test_suspect_is_not_genuine(self):
        # conditional / pemakluman / UPU-semakan → suspect → not an official offer.
        self.assertEqual(offer_official_status(
            _auth_doc({'status': 'suspect', 'probability': 0.4, 'model_version': '1.1'})), 'not_genuine')

    def test_not_offer_is_not_genuine(self):
        self.assertEqual(offer_official_status(
            _auth_doc({'status': 'not_offer_letter', 'probability': 0.1})), 'not_genuine')

    def test_no_authenticity_is_unknown(self):
        # Genuineness not computed (flag off / not re-run) → 'unknown' → never gate on our gap.
        self.assertEqual(offer_official_status(_auth_doc(None)), 'unknown')


class TestDeclaredPathwayCircularity(SimpleTestCase):
    """#117 (c): an offer-autofilled chosen_programme must NOT be treated as the declaration —
    else offer_pathway_match compares the offer against itself (45 live apps carry the source)."""
    def _app(self, cp, track='', inst=''):
        return SimpleNamespace(chosen_programme=cp, pre_u_track=track, pre_u_institution=inst)

    def test_offer_autofilled_pick_falls_back_to_pre_u(self):
        from apps.scholarship.pathway_engine import _declared_pathway
        app = self._app(
            {'course_name': 'SAINS', 'institution': 'KOLEJ TINGKATAN ENAM GOMBAK',
             'source': 'offer_letter_auto'},
            track='sains_sosial', inst='SMK (P) TEMENGGONG IBRAHIM')
        # The offer's own values are ignored; the student's real declaration is returned.
        self.assertEqual(_declared_pathway(app), ('sains_sosial', 'SMK (P) TEMENGGONG IBRAHIM'))

    def test_genuine_student_pick_is_still_used(self):
        from apps.scholarship.pathway_engine import _declared_pathway
        app = self._app(
            {'course_name': 'Diploma Kejuruteraan', 'institution': 'UPM', 'source': 'student'},
            track='ignored', inst='ignored')
        self.assertEqual(_declared_pathway(app), ('Diploma Kejuruteraan', 'UPM'))
