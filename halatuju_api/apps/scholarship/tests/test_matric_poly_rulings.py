"""Matric/Diploma M4b — the owner's rulings (2026-10-29) on Matriculation / polytechnic pages in the
higher-results slot (`genuineness/matric_poly_doc.py`, MODEL_VERSION 1.22.0):
  A. only the FINAL result counts — the final academic transcript;
  B. a NON-FINAL document (a semester result slip, a polytechnic's portal, a transcript printing an
     in-progress status — POSITIVE evidence only, review B1) does not count: read as NOT YET UPLOADED —
     Academic capped at Probable, the final transcript asked for — never the −2 step;
  C. a PROVISIONAL transcript that prints its completion status and final CGPA counts as final;
  D. a Matriculation OFFER LETTER here is "not a results document" (the −2 step); no suspect band.
Synthetic twins of each page's fixed wording; a real final transcript is never asked to re-upload.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import vision
from apps.scholarship.genuineness import matric_poly_doc as m
from apps.scholarship.genuineness.bands import NOT_CHECKED, NOT_FINAL_SEEN
from apps.scholarship.genuineness.matric_poly_doc import matric_poly_higher_genuineness as score
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.tests.test_matric_parse import four_sem_pages
from apps.scholarship.tests.test_matric_poly_doc import KPM_LETTER, MATRIC, MATRIC_OFFER, POLY, PORTAL
from apps.scholarship.tests.test_poly_diploma_parse import NL, UITM
from apps.scholarship.tests.test_third_route_s3 import DEGREE, MATRIC_HELD, _app

#: A Matriculation semester result slip: the KPM header, ONE semester, the slip's title and disclaimer.
SLIP_HEAD = ['KEMENTERIAN PENDIDIKAN', 'BAHAGIAN MATRIKULASI', 'MATRICULATION DIVISION',
             'SLIP KEPUTUSAN PEPERIKSAAN / EXAMINATION RESULT SLIP', '{sem} SESI 2025/2026',
             'NAMA / NAME : SITI AMINAH BINTI ALI', 'KOLEJ / COLLEGE : KOLEJ MATRIKULASI PERAK',
             'SC025 COMPUTER SCIENCE 2 5 A 4.00', 'PNGS / GPA : 4.00', 'PNGK / CGPA : 4.00']
DISCLAIMER = ['Slip keputusan ini bukan transkrip akademik. Keputusan muktamad adalah seperti yang tercatat',
              'sebelum transkrip akademik sebenar dikeluarkan.',
              'This result slip is not an academic transcript. The final result is as appeared in the academic transcript.']


def matric_slip(sem='SEMESTER II', final=True):
    lines = [ln.format(sem=sem) for ln in SLIP_HEAD]
    if final:
        lines.append('STATUS : LULUS DAN TAMAT PROGRAM MATRIKULASI')
    return NL.join(lines + DISCLAIMER)


#: A polytechnic semester result slip (the shape of the two corpus slips).
POLY_SLIP = NL.join(['SLIP KEPUTUSAN PENILAIAN AKHIR', 'KEPUTUSAN PENILAIAN AKHIR SEMESTER', 'SESI I : 2025/2026',
                     'PROGRAM DIPLOMA PENGURUSAN LOGISTIK', 'POLITEKNIK CONTOH',
                     'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI', 'SEMESTER : TIGA', 'KELAS SEMASA : DLS3C',
                     'KOD NAMA KURSUS JAM KREDIT GRED NILAI MATA MATA KREDIT STATUS',
                     'DPB10063 PRINCIPLES OF MANAGEMENT 3.0 A 4.00 12.00', 'PNM : 3.53 HPNM : 3.16'])


def mine(text):
    """The page in the live-path student's own name and CGPA (so it reads clean: only finality differs)."""
    return text.replace('SITI AMINAH BINTI ALI', 'PRIYA').replace('CGPA : 3.29', 'CGPA : 3.50').replace(
        'CGPA : 4.00', 'CGPA : 3.50')


class TestTheRulings(SimpleTestCase):
    def assertRuled(self, text, seen, status):
        sg = score(text)
        self.assertEqual((sg.get('status'), sg.get('type')), (status, seen))
        self.assertIn('owner ruling', sg['reason'])
        self.assertIn('2026-10-29', sg['reason'])

    def test_b_a_matriculation_semester_result_slip_is_not_final(self):
        self.assertRuled(matric_slip(), m.MATRIC_SLIP, NOT_CHECKED)                  # final "Lulus dan Tamat" slip
        self.assertRuled(matric_slip('SEMESTER I', final=False), m.MATRIC_SLIP, NOT_CHECKED)
        self.assertRuled(matric_slip('SEMESTER IV'), m.MATRIC_SLIP, NOT_CHECKED)      # a 2-year programme's
        self.assertIn('final academic transcript is still owed', score(matric_slip())['reason'])

    def test_b_a_polytechnic_semester_result_slip_is_not_final(self):
        self.assertRuled(POLY_SLIP, m.POLY_SLIP, NOT_CHECKED)

    def test_b_the_polytechnic_student_portal_is_not_final(self):
        self.assertRuled(PORTAL, m.POLY_PORTAL, NOT_CHECKED)

    def test_b_a_transcript_printing_an_in_progress_status_is_not_final(self):
        """Positive evidence (review B1): the status itself says the programme is not finished."""
        for status in ('ACTIVE', 'AKTIF', 'DIGANTUNG', 'SEDANG BELAJAR'):
            self.assertRuled(POLY.replace('STATUS  : COMPLETED', f'STATUS  : {status}'), m.POLY_NOT_FINAL, NOT_CHECKED)
        self.assertRuled(POLY.replace('STATUS  : COMPLETED', ' : ACTIVESTATUS'), m.POLY_NOT_FINAL, NOT_CHECKED)
        in_progress = MATRIC.replace('STATUS : LULUS DAN TAMAT PROGRAM MATRIKULASI', 'STATUS : SEDANG BELAJAR').replace(
            'PASS AND COMPLETED MATRICULATION PROGRAMME', '')
        self.assertRuled(in_progress, m.MATRIC_NOT_FINAL, NOT_CHECKED)

    def test_b_a_completion_status_and_an_in_progress_one_is_not_settled(self):
        self.assertEqual(score(POLY + NL + 'STATUS : AKTIF'), {})
        self.assertEqual(score(MATRIC + NL + 'STATUS : AKTIF'), {})

    def test_a_transcript_is_genuine_only_with_its_completion_status(self):
        """No status at all: never genuine — and never ruled non-final either (B1): unsure, {}."""
        cut = MATRIC
        for line in ('STATUS : LULUS DAN TAMAT PROGRAM MATRIKULASI', 'PASS AND COMPLETED MATRICULATION PROGRAMME'):
            cut = cut.replace(line, '')
        self.assertEqual(score(cut), {})
        self.assertEqual(score(POLY.replace('STATUS  : COMPLETED', 'STATUS  :')), {})

    def test_b1_a_real_poly_transcript_printed_value_first_is_genuine(self):
        """A text layer can print the value before its label: " : COMPLETEDSTATUS"."""
        self.assertEqual(score(POLY.replace('STATUS  : COMPLETED', ' : COMPLETEDSTATUS'))['status'], 'genuine')
        self.assertEqual(score(POLY.replace('STATUS  : COMPLETED', 'COMPLETED  STATUS'))['status'], 'genuine')

    def test_b1_a_noisy_or_otherwise_worded_poly_status_is_unsure_never_non_final(self):
        for status in ('STATUS  : C0MPLETED', 'STATUS  : GRADUATED', 'STATUS  : LULUS', 'STATUS  : C0MPLETEDSTATUS',
                       ' : GRADUATEDSTATUS', 'STAT US : COMPLETED'):
            self.assertEqual(score(POLY.replace('STATUS  : COMPLETED', status)), {}, status)

    def test_sf1_a_matric_status_on_page_two_or_cut_or_damaged_is_unsure_never_non_final(self):
        # 2-semester transcript whose STATUS lines moved to page 2: page 1 alone.
        page1 = MATRIC.replace('STATUS : LULUS DAN TAMAT PROGRAM MATRIKULASI', '').replace(
            'PASS AND COMPLETED MATRICULATION PROGRAMME', '').replace('PENGARAH / DIRECTOR', '')
        self.assertEqual(score(page1), {})
        self.assertEqual(score(four_sem_pages()[0]), {})                      # a 4-semester one, cut at page 1
        damaged = MATRIC.replace('LULUS DAN TAMAT', 'LULUS DAN TAMAI').replace('PASS AND COMPLETED', 'PASS AND C0MPLETED')
        self.assertEqual(score(damaged), {})

    def test_rereview_a_final_transcript_bundled_with_a_slip_or_the_portal_is_never_non_final(self):
        """One upload, the text layer read whole: the transcript and a slip / the portal, either order."""
        for one, two in ((MATRIC, matric_slip()), (MATRIC, matric_slip('SEMESTER I', final=False)),
                         (POLY, POLY_SLIP), (POLY, PORTAL)):
            for text in (one + NL + two, two + NL + one):
                self.assertEqual(score(text).get('status'), 'genuine', text[:40])

    def test_final_review_a_bundle_never_borrows_the_slips_or_portals_completion_status(self):
        """In a bundle, the status and the whole-transcript block must sit in the transcript's OWN section."""
        no_status = MATRIC.replace('STATUS : LULUS DAN TAMAT PROGRAM MATRIKULASI', '').replace(
            'PASS AND COMPLETED MATRICULATION PROGRAMME', '')
        poly_no_status = POLY.replace('STATUS  : COMPLETED', 'STATUS  :')
        portal_done = PORTAL + NL + 'STATUS : COMPLETED'
        for one, two in ((four_sem_pages()[0], matric_slip('SEMESTER IV')),     # page 1 of a 2-year one
                         (no_status, matric_slip()),                           # its end, no status
                         (poly_no_status, portal_done), (poly_no_status, POLY_SLIP + NL + 'STATUS COMPLETED')):
            for text in (one + NL + two, two + NL + one):
                self.assertNotEqual(score(text).get('status'), 'genuine', text[:40])

    def test_final_review_a_bundle_needs_what_only_a_whole_transcript_prints(self):
        no_box = MATRIC.replace('PURATA GRED BAGI KURSUS TERAS DAN ENGLISH', '').replace(
            'AVERAGE GRADE FOR CORE COURSES AND ENGLISH', '')
        no_end = POLY.replace('~~~~~End of results~~~~~', '')
        for text in (no_box + NL + matric_slip(), no_end + NL + POLY_SLIP, PORTAL + NL + no_end):
            self.assertNotEqual(score(text).get('status'), 'genuine', text[:40])
        self.assertEqual(score(no_box)['status'], 'genuine')          # alone (no bundle) it is read whole

    def test_final_review_a_negated_heading_never_opens_a_transcript_section(self):
        negated = MATRIC.replace('TRANSKRIP AKADEMIK / ACADEMIC TRANSCRIPT', 'BUKAN TRANSKRIP AKADEMIK / ACADEMIC TRANSCRIPT')
        self.assertNotEqual(score(negated + NL + matric_slip()).get('status'), 'genuine')

    def test_rereview_two_slips_bundled_are_still_slips(self):
        """A slip's disclaimer mentions "the academic transcript": that is no transcript heading."""
        both = matric_slip('SEMESTER I', final=False) + NL + matric_slip('SEMESTER II')
        self.assertRuled(both, m.MATRIC_SLIP, NOT_CHECKED)
        self.assertRuled(POLY_SLIP + NL + PORTAL, m.POLY_PORTAL, NOT_CHECKED)

    def test_rereview_an_in_progress_word_counts_only_in_the_status_value_position(self):
        legend = POLY + NL + NL.join(['ABBREVIATION STATUS', '[W] - WITHDRAWN', 'GRADE STATUS WITHDRAWN COURSE',
                                      'REMARK : ACTIVE STATUS COURSE', 'STATUS LEGEND : [AK] AKTIF'])
        self.assertEqual(score(legend).get('status'), 'genuine')
        self.assertFalse(m._in_progress('DM STATUS ACTIVE GST ID'))          # the corpus salary slip's line
        self.assertTrue(m._in_progress('Status : Withdrawn'))
        self.assertTrue(m._in_progress(' : WITHDRAWNSTATUS'))

    def test_sf5_the_portal_rule_is_a_polytechnics_own_portal(self):
        for issuer in ('KOLEJ KOMUNITI CONTOH', 'UNIVERSITI TEKNOLOGI MARA', ''):
            page = PORTAL.replace('POLITEKNIK CONTOH', issuer)
            self.assertEqual(score(page), {}, issuer or 'no institution')
        two_ways = PORTAL + NL + 'KOLEJ MATRIKULASI PERAK'               # a page pointing two ways: no kind
        self.assertEqual(score(two_ways), {})

    def test_c_a_provisional_transcript_with_status_and_final_cgpa_counts_as_final(self):
        """3926's shape: "ACADEMIC TRANSCRIPT (PROVISIONAL)", STATUS COMPLETED, the final CGPA."""
        self.assertIn('ACADEMIC TRANSCRIPT (PROVISIONAL)', POLY)
        self.assertEqual(score(POLY)['status'], 'genuine')

    def test_d_a_matriculation_offer_letter(self):
        self.assertRuled(MATRIC_OFFER, m.MATRIC_OFFER, 'not_matric_result')
        self.assertIn('not a results document', score(MATRIC_OFFER)['reason'])

    def test_the_non_final_codes_have_one_home(self):
        self.assertEqual(NOT_FINAL_SEEN, {m.MATRIC_SLIP, m.POLY_SLIP, m.POLY_PORTAL, m.MATRIC_NOT_FINAL,
                                          m.POLY_NOT_FINAL})

    def test_a_real_transcript_is_never_asked_to_re_upload(self):
        """Even one that carries an offer letter's or a slip's word somewhere on it."""
        for text in (MATRIC, POLY, MATRIC + NL + 'TAHNIAH ATAS KEMASUKAN', POLY + NL + 'HPNM JAM KREDIT'):
            self.assertEqual(score(text).get('status'), 'genuine')
        self.assertEqual(score(four_sem_pages()[0]), {})                # page 1 of a 2-year transcript: unsure

    def test_a_transcript_is_never_ruled_whatever_else_it_prints(self):
        """The guard before every ruling: a page that passes a transcript's own gates is a transcript."""
        portal_words = NL.join(['KEPUTUSAN PEPERIKSAAN MENGIKUT SEMESTER', 'DAFTAR HHP', 'STATUS DAFTAR LATIHAN INDUSTRI'])
        self.assertEqual(score(MATRIC + NL + portal_words).get('status'), 'genuine')

    def test_an_offer_is_told_only_on_a_matric_page_with_no_transcript_grid(self):
        import re
        cropped = re.sub(r'SEMESTER II\n.*?PNGS / GPA : 3\.33\n', '', MATRIC, flags=re.S)
        self.assertEqual(score(cropped + NL + 'TAWARAN KEMASUKAN'), {})       # a grid: not an offer, unsure
        two_ways = NL.join(['BAHAGIAN MATRIKULASI', 'TAWARAN KEMASUKAN KE PROGRAM DIPLOMA'])
        self.assertEqual(score(two_ways), {})                                  # Matriculation AND Diploma: no kind

    def test_unsure_stays_not_checked(self):
        """One slip phrase only, one portal phrase, one offer word, a letter of no ruled kind."""
        one_phrase = NL.join([ln.format(sem='SEMESTER II') for ln in SLIP_HEAD]).replace(
            'SLIP KEPUTUSAN PEPERIKSAAN / EXAMINATION RESULT SLIP', 'SLIP KEPUTUSAN PEPERIKSAAN')
        for text in (one_phrase, NL.join(['POLITEKNIK CONTOH', 'SEMAKAN BUTIRAN PELAJAR', 'DIPLOMA X', 'HPNM 3.1']),
                     NL.join(['BAHAGIAN MATRIKULASI', 'TAWARAN PROGRAM MATRIKULASI']), KPM_LETTER):
            self.assertEqual(score(text), {})

    def test_the_rulings_stay_in_their_families(self):
        for text in (UITM, UITM + NL + 'SLIP KEPUTUSAN PEPERIKSAAN EXAMINATION RESULT SLIP',
                     'PUSAT ASASI SAINS ' + NL.join(DISCLAIMER), 'SIJIL PELAJARAN MALAYSIA 2024 BAHASA MELAYU A TAWARAN'):
            self.assertEqual(score(text), {}, text[:30])
        kk_slip = POLY_SLIP.replace('POLITEKNIK CONTOH', 'KOLEJ KOMUNITI CONTOH')
        self.assertEqual(score(kk_slip), {})                            # no polytechnic's own name

    def test_4_no_suspect_is_ever_stored(self):
        for text in (MATRIC, POLY, matric_slip(), POLY_SLIP, PORTAL, MATRIC_OFFER, KPM_LETTER, four_sem_pages()[0]):
            self.assertNotEqual(score(text).get('status'), 'suspect')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestTheLivePath(TestCase):
    READ = {'candidate_name': 'PRIYA', 'cgpa': '3.50', 'cgpa_label': 'PNGK'}

    def _upload(self, text, stage='shortlisted', app=None, results_kind='matric', request_code='', **kw):
        app = app or _app(MATRIC_HELD, DEGREE, stage=stage, **kw)
        doc = ApplicantDocument.objects.create(application=app, doc_type='higher_results', results_kind=results_kind,
                                               storage_path='test/hr-m4b', content_type='image/jpeg',
                                               request_code=request_code)
        with patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': dict(self.READ), 'warnings': [], 'error': ''}):
            vision.run_field_extraction_for_document(
                doc, names=['Priya'], ocr={'text': text, 'words': None, 'image': b'img', 'error': None})
        doc.refresh_from_db()
        return app, doc

    def _academic(self, app):
        from apps.scholarship.verdict_engine import build_verdict
        fresh = ScholarshipApplication.objects.get(pk=app.pk)
        return next(f for f in build_verdict(fresh) if f['fact'] == 'academic')

    def test_b_a_slip_reads_as_not_yet_uploaded_probable_and_asked_for(self):
        from apps.scholarship import higher_owed
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        app, doc = self._upload(matric_slip())
        auth = doc.vision_fields['authenticity']
        self.assertEqual((auth['status'], auth['doc_seen']), (NOT_CHECKED, m.MATRIC_SLIP))
        academic = self._academic(app)
        codes = {i['code'] for i in academic['unresolved']}
        self.assertIn('higher_results_not_final', codes)
        self.assertNotIn('document_not_genuine', codes)                     # never the -2 step
        self.assertEqual(academic['status'], 'review')                       # Probable, as "not yet uploaded"
        self.assertEqual(ApplicantDocumentSerializer(doc).data['authenticity']['status'], 'final_owed')
        self.assertEqual(higher_owed.ask_codes(ScholarshipApplication.objects.get(pk=app.pk)), set())  # not submitted

    def test_b_once_submitted_the_final_transcript_is_asked_for_until_a_final_one_answers(self):
        from apps.scholarship import higher_owed
        from apps.scholarship.tests.test_third_route_s4 import HIGHER_FROZEN
        # Frozen WITH the higher results required, so the #388 pre-S3 path does not fire: only ruling B asks.
        app, _doc = self._upload(matric_slip(), stage='profile_complete', requirements_snapshot=HIGHER_FROZEN)
        fresh = ScholarshipApplication.objects.get(pk=app.pk)
        self.assertEqual(higher_owed._owed(fresh), '')
        self.assertEqual(higher_owed.ask_codes(fresh), {higher_owed.ASK_CODE})
        self.assertEqual(higher_owed.ask_params(fresh, higher_owed.ASK_CODE), {'results_kind': 'matric'})
        self.assertFalse(higher_owed.answered(fresh))
        final_app, _final = self._upload(MATRIC, stage='profile_complete', requirements_snapshot=HIGHER_FROZEN)
        self.assertEqual(higher_owed.final_owed_kind(ScholarshipApplication.objects.get(pk=final_app.pk)), '')

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
    def test_b_a_non_final_upload_is_never_certain_even_with_the_check_off(self):
        """The TD-114 floor is inert with the check off: the not-final rule must hold the card itself."""
        app = _app(MATRIC_HELD, DEGREE)
        ApplicantDocument.objects.create(
            application=app, doc_type='higher_results', results_kind='matric', storage_path='test/hr-m4b-off',
            vision_fields={'fields': dict(self.READ, results_kind_detected='matric'), 'student_verdict': 'ok',
                           'error': '', 'authenticity': {'status': NOT_CHECKED, 'doc_seen': m.MATRIC_SLIP,
                                                         'reason': ''}})
        self.assertEqual(self._academic(app)['status'], 'review')

    def test_c_a_final_transcript_answers_and_reads_certain(self):
        app, doc = self._upload(MATRIC.replace('PNGK / CGPA : 3.29', 'PNGK / CGPA : 3.50'))
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'genuine')
        academic = self._academic(app)
        self.assertNotIn('higher_results_not_final', {i['code'] for i in academic['unresolved']})

    def test_d_an_offer_letter_still_takes_the_not_a_result_step(self):
        app, doc = self._upload(MATRIC_OFFER)
        from apps.scholarship.anomaly_engine import _detect_document_not_genuine
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'not_matric_result')
        academic = self._academic(app)
        codes = [i['code'] for i in academic['unresolved']]
        # Review nit: the reviewer reads "not a results document", never "may not be the genuine original".
        self.assertEqual(codes.count('higher_results_not_results'), 1)
        self.assertNotIn('document_not_genuine', codes)
        self.assertNotEqual(academic['status'], 'verified')                  # the -2 step still bites
        anomaly = _detect_document_not_genuine(ScholarshipApplication.objects.get(pk=app.pk))
        self.assertEqual((anomaly.code, anomaly.params), ('document_not_results', {'doc': 'Matriculation results'}))

    def _submitted(self, **kw):
        from apps.scholarship.tests.test_third_route_s4 import HIGHER_FROZEN
        return _app(MATRIC_HELD, DEGREE, stage='profile_complete', requirements_snapshot=HIGHER_FROZEN, **kw)

    def test_sf3_a_non_final_upload_never_closes_an_officers_results_request(self):
        from apps.scholarship.models import ResolutionItem
        from apps.scholarship.resolution import resolve_doc_items_for_upload
        app = self._submitted()
        item = ResolutionItem.objects.create(application=app, source='officer', code='officer_1', kind='doc',
                                             doc_type='higher_results', fact='academic',
                                             params={'results_kind': 'matric'})
        _app_, slip = self._upload(mine(matric_slip()), app=app, request_code='officer_1')
        self.assertEqual(resolve_doc_items_for_upload(ScholarshipApplication.objects.get(pk=app.pk), slip), 'ok')
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')                                # a slip is not the final result
        _app_, final = self._upload(mine(MATRIC), app=app, request_code='officer_1')
        resolve_doc_items_for_upload(ScholarshipApplication.objects.get(pk=app.pk), final)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')

    def test_sf3_a_non_final_upload_never_closes_check_2s_ask(self):
        from apps.scholarship import higher_owed, results_requests
        from apps.scholarship.models import ResolutionItem
        app = self._submitted()
        ask = ResolutionItem.objects.create(application=app, source='check2', code=higher_owed.ASK_CODE, kind='doc',
                                            doc_type='higher_results', fact='academic')
        _app_, slip = self._upload(POLY_SLIP, app=app, results_kind='diploma')
        self.assertFalse(results_requests.answers(slip, ask))
        self.assertFalse(higher_owed.answered(ScholarshipApplication.objects.get(pk=app.pk)))
        _app_, final = self._upload(mine(MATRIC), app=app)
        self.assertTrue(results_requests.answers(final, ask))

    def test_sf4_a_final_transcript_on_file_counts_whatever_came_after_it(self):
        from apps.scholarship import higher_owed
        from apps.scholarship.higher_results import higher_doc
        for first, second in ((mine(MATRIC), mine(matric_slip())), (mine(matric_slip()), mine(MATRIC))):
            app = self._submitted()
            _a, one = self._upload(first, app=app)
            _a, two = self._upload(second, app=app)
            fresh = ScholarshipApplication.objects.get(pk=app.pk)
            final = two if 'SLIP KEPUTUSAN' in first else one
            self.assertEqual(higher_doc(fresh).pk, final.pk)
            self.assertNotIn('higher_results_not_final', {i['code'] for i in self._academic(app)['unresolved']})
            self.assertEqual(higher_owed.final_owed_kind(fresh), '')
            self.assertEqual(higher_owed.ask_codes(fresh), set())

    def _junk(self, app, verdict='unreadable'):
        return ApplicantDocument.objects.create(
            application=app, doc_type='higher_results', results_kind='matric', storage_path='test/junk',
            vision_fields={'fields': {}, 'student_verdict': verdict, 'error': ''})

    def test_rereview_an_older_junk_upload_never_outranks_a_newer_slip(self):
        from apps.scholarship import higher_owed
        from apps.scholarship.higher_results import final_upload, higher_doc
        app = self._submitted()
        junk = self._junk(app)
        _a, slip = self._upload(mine(matric_slip()), app=app)
        fresh = ScholarshipApplication.objects.get(pk=app.pk)
        self.assertFalse(final_upload(junk))
        self.assertEqual(higher_doc(fresh).pk, slip.pk)                        # neither final: the newest
        self.assertEqual(higher_owed.final_owed_kind(fresh), 'matric')         # so the final one is still asked for
        _a, final = self._upload(mine(MATRIC), app=app)
        self._junk(app)                                                        # a newer junk upload after it
        self.assertEqual(higher_doc(ScholarshipApplication.objects.get(pk=app.pk)).pk, final.pk)

    def test_rereview_a_newer_unreadable_upload_never_blocks_while_a_final_transcript_is_live(self):
        from apps.scholarship.services.blockers import document_unreadable_blockers
        only_junk = _app(MATRIC_HELD, DEGREE)
        self._junk(only_junk)
        self.assertIn('higher_results_unreadable', document_unreadable_blockers(only_junk))   # it IS asked
        app = _app(MATRIC_HELD, DEGREE)
        self._upload(mine(MATRIC), app=app)
        self._junk(app)
        self.assertNotIn('higher_results_unreadable',
                         document_unreadable_blockers(ScholarshipApplication.objects.get(pk=app.pk)))

    def test_rereview_an_offer_letter_never_answers_a_results_ask(self):
        from apps.scholarship import higher_owed, results_requests
        from apps.scholarship.higher_results import answers_higher_ask
        from apps.scholarship.models import ResolutionItem
        app = self._submitted()
        ask = ResolutionItem.objects.create(application=app, source='check2', code=higher_owed.ASK_CODE, kind='doc',
                                            doc_type='higher_results', fact='academic')
        _a, offer = self._upload(MATRIC_OFFER, app=app)
        self.assertEqual(offer.vision_fields['authenticity']['status'], 'not_matric_result')
        self.assertFalse(answers_higher_ask(offer))
        self.assertFalse(results_requests.answers(offer, ask))

    def test_sf6_an_spm_only_intake_with_a_voluntary_slip_asks_nothing(self):
        from apps.scholarship import higher_owed
        from apps.scholarship.tests.factories import make_cohort
        app = self._submitted(cohort=make_cohort(min_stpm_pngk=None))
        self._upload(mine(matric_slip()), app=app)
        fresh = ScholarshipApplication.objects.get(pk=app.pk)
        self.assertEqual(higher_owed.final_owed_kind(fresh), '')
        self.assertEqual(higher_owed.ask_codes(fresh), set())

    def test_sf6_no_ask_when_the_academic_card_is_not_about_the_higher_results(self):
        from apps.scholarship import higher_owed
        app = _app(MATRIC_HELD, DEGREE, stage='profile_complete')        # frozen with no higher-results slot
        with patch('apps.scholarship.higher_results.anchors_on_higher', return_value=False):
            self._upload(mine(matric_slip()), app=app)
            self.assertEqual(higher_owed.final_owed_kind(ScholarshipApplication.objects.get(pk=app.pk)), '')

    def test_sf6_the_ask_names_the_kind_an_officer_asked_for(self):
        from apps.scholarship import higher_owed
        app = self._submitted()
        self._upload(POLY_SLIP, app=app, results_kind='diploma')              # an officer's Diploma request
        fresh = ScholarshipApplication.objects.get(pk=app.pk)
        self.assertEqual(higher_owed.final_owed_kind(fresh), 'diploma')
        self.assertEqual(higher_owed.ask_params(fresh, higher_owed.ASK_CODE), {'results_kind': 'diploma'})

    def test_the_versions_moved(self):
        import re
        from apps.scholarship.genuineness.results_doc import MODEL_VERSION
        from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION
        self.assertGreaterEqual(tuple(int(p) for p in MODEL_VERSION.split('.')), (1, 22, 0))
        self.assertGreaterEqual(tuple(int(p) for p in re.split(r'[-.]', VERDICT_ENGINE_VERSION)), (2026, 10, 29, 3))


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestTheM5ForcedOverwrite(TestCase):
    """Review SF7: a re-read under the new rule REPLACES a Matric / Diploma page's stored
    authenticity ({} included) only on the M5 pass's own flag; TD-407 holds everywhere else."""
    OLD = {'status': NOT_CHECKED, 'doc_seen': m.MATRIC_NOT_FINAL, 'reason': 'old rule'}
    READ = {'candidate_name': 'PRIYA', 'cgpa': '3.50', 'cgpa_label': 'PNGK'}

    def _doc(self, kind='matric'):
        app = _app(MATRIC_HELD, DEGREE)
        return ApplicantDocument.objects.create(
            application=app, doc_type='higher_results', results_kind=kind, storage_path='test/m5',
            content_type='image/jpeg', vision_fields={'fields': dict(self.READ), 'student_verdict': 'ok', 'error': '',
                                                      'authenticity': dict(self.OLD)})

    def _reread(self, doc):
        """The real extraction path, on a page whose status line is cut off (page 1 only): no signal."""
        page = mine(MATRIC).replace('STATUS : LULUS DAN TAMAT PROGRAM MATRIKULASI', '').replace(
            'PASS AND COMPLETED MATRICULATION PROGRAMME', '')
        with patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': dict(self.READ), 'warnings': [], 'error': ''}):
            vision.run_field_extraction_for_document(
                doc, names=['Priya'], ocr={'text': page, 'words': None, 'image': b'img', 'error': None})
        return True

    def _run(self, *args, **side):
        from django.core.management import call_command
        with patch('apps.scholarship.management.commands.reextract_documents.reextract_document',
                   side_effect=side.get('effect', self._reread)):
            call_command('reextract_documents', '--doc-type', 'higher_results', '--pass-marker', 'm5_test', *args)

    def test_without_the_flag_td_407_keeps_the_stored_block(self):
        doc = self._doc()
        self._run()
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['authenticity']['doc_seen'], m.MATRIC_NOT_FINAL)

    def test_the_flag_lets_the_fresh_empty_answer_replace_it(self):
        doc = self._doc()
        self._run('--fresh-higher-authenticity')
        doc.refresh_from_db()
        self.assertNotIn('authenticity', doc.vision_fields)                   # "not checked": no owed, no ask
        self.assertTrue(doc.vision_fields['m5_test'])

    def test_the_env_door_works_too_and_stpm_pages_keep_td_407(self):
        stpm, matric = self._doc('stpm'), self._doc()
        with patch.dict('os.environ', {'REEXTRACT_FRESH_HIGHER_AUTH': '1'}):
            self._run()
        stpm.refresh_from_db()
        matric.refresh_from_db()
        self.assertIn('authenticity', stpm.vision_fields)
        self.assertNotIn('authenticity', matric.vision_fields)

    def test_a_failed_re_read_keeps_the_stored_block(self):
        doc = self._doc()
        self._run('--fresh-higher-authenticity', effect=RuntimeError('storage outage'))
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['authenticity']['doc_seen'], m.MATRIC_NOT_FINAL)

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
    def test_the_flag_refuses_to_run_with_the_check_off(self):
        from django.core.management.base import CommandError
        self._doc()
        with self.assertRaises(CommandError):
            self._run('--fresh-higher-authenticity', '--allow-without-genuineness')
