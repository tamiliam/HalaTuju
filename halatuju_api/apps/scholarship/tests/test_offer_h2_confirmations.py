"""Help H2 (owner ruling 2026-11-15, ruling 4 WIDENED): a confirmation of studies from EVERY public institution
type is an acceptable alternative to the offer letter (genuine, never a course pick); one from a public university
(UMS included, owner 2026-11-15) reads suspect (a person checks); a private college or a university's private wing
still fails. And KPM's English matriculation offer is recognised like the Malay one. The help H2 review
(2026-11-15) tightened the proof: genuine only on CLEAR proof (the ministry on the letterhead, a known public name),
else suspect. Synthetic twins only: every letter is invented (`test_no_gitignored_corpus.py`), no real name or IC.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.scholarship.genuineness.offer_confirmations import CONFIRMATION_SEEN
from apps.scholarship.genuineness.offer_issuers import officer_must_close
from apps.scholarship.genuineness.offer_rulings import confirmation_kind, ruling_of
from apps.scholarship.genuineness.results_doc import signature_genuineness
from apps.scholarship.pathway_engine import is_confirmation_letter, student_offer_check
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_offer_rulings import _confirm
from apps.scholarship.tests.test_offer_s6_doors import _offer

KPM, KPT = 'KEMENTERIAN PENDIDIKAN MALAYSIA', 'KEMENTERIAN PENDIDIKAN TINGGI'
#: Clear proof (help H2 review, 2026-11-15): the ministry on the letterhead and a KNOWN public name (the official
#: lists in `offer_confirmations._KNOWN_PUBLIC_NAMES`); the polytechnic by its name pattern and its ministry.
GENUINE = (
    ('matric (Malay)', f'KOLEJ MATRIKULASI PERAK\nBAHAGIAN MATRIKULASI\n{KPM}', 'confirmation_matriculation'),
    ('matric (the Division itself)', f'BAHAGIAN MATRIKULASI\n{KPM}', 'confirmation_matriculation'),
    ('IPG', f'INSTITUT PENDIDIKAN GURU KAMPUS IPOH\n{KPM}', 'confirmation_ipg'),
    ('IPG (short form)', f'IPG KAMPUS IPOH\n{KPM}', 'confirmation_ipg'),
    ('community college', f'KOLEJ KOMUNITI SELAYANG\n{KPT}', 'confirmation_kolej_komuniti'),
    ('polytechnic', f'POLITEKNIK CONTOH\n{KPT}', 'confirmation_polytechnic'),
    ('Form 6', f'KOLEJ TINGKATAN ENAM CONTOH\n{KPM}', 'confirmation_form6'),
)
#: Recognised as a public confirmation but WITHOUT clear proof: suspect (a person checks), never a fail. CHANGED
#: by the help H2 review (2026-11-15): matric / IPG / KK with an unlisted name, KV and IKBN (no complete list in
#: the repo) were genuine; UMS was genuine (owner 2026-11-15: UMS confirmations read suspect; a person checks).
SUSPECT = (
    ('matric, an unlisted college', f'KOLEJ MATRIKULASI CONTOH\nBAHAGIAN MATRIKULASI\n{KPM}',
     'confirmation_matriculation', 'confirmation_unclear'),
    ('matric (English), an unlisted college', 'MATRICULATION COLLEGE CONTOH\nMATRICULATION DIVISION\n'
     'MINISTRY OF EDUCATION MALAYSIA', 'confirmation_matriculation', 'confirmation_unclear'),
    ('IPG, an unlisted campus', f'INSTITUT PENDIDIKAN GURU KAMPUS CONTOH\n{KPM}', 'confirmation_ipg',
     'confirmation_unclear'),
    ('community college, unlisted', f'KOLEJ KOMUNITI CONTOH\n{KPT}', 'confirmation_kolej_komuniti',
     'confirmation_unclear'),
    ('KV (no list)', f'KOLEJ VOKASIONAL CONTOH\n{KPM}', 'confirmation_kv', 'confirmation_unclear'),
    ('IKBN (no list)', 'INSTITUT KEMAHIRAN BELIA NEGARA CONTOH\nKEMENTERIAN BELIA DAN SUKAN', 'confirmation_tvet',
     'confirmation_unclear'),
    ('UMS (owner 2026-11-15)', 'UNIVERSITI MALAYSIA SABAH\nBahagian Perkhidmatan Akademik', 'confirmation_ums',
     'confirmation_ua'),
)
#: Private colleges and the public universities' private wings: still a fail (no private veto loosened).
FAILS = (
    ('private college', 'KOLEJ CONTOH\nKampus Utama'),
    ('KPTM', 'KOLEJ POLY-TECH MARA CONTOH'),
    ('UniKL', 'UNIVERSITI KUALA LUMPUR\nKampus Contoh'),
    ('UTM SPACE', 'UTM SPACE\nUNIVERSITI TEKNOLOGI MALAYSIA'),
    ('Pendidikan Berterusan', 'PUSAT PENDIDIKAN BERTERUSAN\nUNIVERSITI MALAYA'),
    ('UMS PPPL', 'PUSAT PENDIDIKAN PROFESIONAL DAN LANJUTAN (PPPL)\nUNIVERSITI MALAYSIA SABAH'),
    ('UM SATU', 'SALURAN TERBUKA UNIVERSITI MALAYA (SATU)\nUNIVERSITI MALAYA'),
    ('a company on a KV letterhead', f'KOLEJ VOKASIONAL CONTOH\nMERCU HOLDINGS SDN BHD\n{KPM}'),
    ('a company-run "matric college"', 'KOLEJ MATRIKULASI CONTOH SDN BHD'),
)


def _read(head):
    return signature_genuineness(_confirm(head), doc_type='offer_letter')


class EveryPublicInstitutionsConfirmation(SimpleTestCase):
    def test_reads_genuine_as_a_confirmation_on_clear_proof(self):
        for name, head, seen in GENUINE:
            with self.subTest(name):
                self.assertEqual(confirmation_kind(_confirm(head)), seen)
                out = _read(head)
                self.assertEqual((out['status'], out['type']), ('genuine', seen))
                self.assertEqual(ruling_of(out), 'confirmation')

    def test_reads_suspect_without_clear_proof(self):
        for name, head, seen, tag in SUSPECT:
            with self.subTest(name):
                self.assertEqual(confirmation_kind(_confirm(head)), seen)
                out = _read(head)
                self.assertEqual((out['status'], out['type'], ruling_of(out)), ('suspect', seen, tag))

    def test_every_code_is_a_confirmation_code(self):
        for _name, _head, seen in GENUINE:
            self.assertIn(seen, CONFIRMATION_SEEN)
        for _name, _head, seen, _tag in SUSPECT:
            self.assertIn(seen, CONFIRMATION_SEEN)
        self.assertIn('confirmation_ua', CONFIRMATION_SEEN)


class AUniversityWithAPrivateWing(SimpleTestCase):
    def test_reads_suspect_never_genuine(self):
        for head in ('UNIVERSITI PUTRA MALAYSIA\nBahagian Akademik', 'UNIVERSITI MALAYA\nJabatan Pendaftar',
                     'UNIVERSITI TEKNOLOGI MALAYSIA\nPejabat Pendaftar'):
            with self.subTest(head=head.splitlines()[0]):
                out = _read(head)
                self.assertEqual((out['status'], out['type'], ruling_of(out)),
                                 ('suspect', 'confirmation_ua', 'confirmation_ua'))   # decisions.md tag


class PrivateIssuersStillFail(SimpleTestCase):
    def test_a_private_college_or_a_private_wing_fails(self):
        got = {name: (confirmation_kind(_confirm(head)), _read(head)['status']) for name, head in FAILS}
        want = {name: ('', 'not_offer_letter') for name, _head in FAILS}
        # "SPACE" is the pre-S6 private-arm veto's word (`results_doc._private_arm_offer`), not a page marker: the
        # page still names UTM, but the veto stops every lift (`offer_rulings._lift`), so it still fails.
        want['UTM SPACE'] = ('confirmation_ua', 'not_offer_letter')
        self.assertEqual(got, want)

    def test_the_department_alone_names_no_community_college(self):
        self.assertEqual(confirmation_kind(_confirm(f'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI\n{KPT}')), '')

    def test_a_matric_confirmation_without_a_ministry_mark_is_not_lifted(self):
        self.assertEqual(confirmation_kind(_confirm('KOLEJ MATRIKULASI CONTOH\nJalan Contoh')), '')


class TheDoors(TestCase):
    """A confirmation never writes a course pick; the officer still closes her own request; a suspect never
    blocks the submission."""

    def _app(self):
        return make_application('shortlisted', chosen_pathway='matric', chosen_programme={})

    def test_never_a_pick(self):
        from apps.scholarship.services.offer_link import plan_offer_link
        from apps.scholarship.services.offer_sync import autofill_pathway_from_offer, plan_bumi_realign
        for seen in ('confirmation_matriculation', 'confirmation_ipg', 'confirmation_kv',
                     'confirmation_kolej_komuniti', 'confirmation_tvet'):
            with self.subTest(seen=seen):
                app = self._app()
                doc = _offer(app, 'genuine', doc_seen=seen, institution='KOLEJ MATRIKULASI CONTOH')
                self.assertTrue(is_confirmation_letter(doc))
                chk = student_offer_check(doc)
                self.assertEqual(plan_bumi_realign(app, doc, chk)[0], 'not_genuine')
                self.assertEqual(plan_offer_link(app, doc, chk)[0], 'confirmation_letter')
                autofill_pathway_from_offer(app)
                app.refresh_from_db()
                cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
                self.assertFalse((cp.get('course_name') or '').strip())

    def test_a_university_confirmation_is_never_a_pick_and_never_blocks(self):
        from apps.scholarship.services.blockers import _offer_blocks
        app = make_application('shortlisted', chosen_pathway='degree')
        doc = _offer(app, 'suspect', doc_seen='confirmation_ua')
        self.assertTrue(is_confirmation_letter(doc))
        self.assertFalse(_offer_blocks(app))

    def test_the_officer_closes_her_own_request(self):
        app = self._app()
        doc = _offer(app, 'genuine', doc_seen='confirmation_matriculation')
        item = SimpleNamespace(source='officer', doc_type='offer_letter')
        self.assertTrue(officer_must_close(doc, item))


# ── KPM's English matriculation offer ───────────────────────────────────────────────────────
MATRIC_EN = """KEMENTERIAN PENDIDIKAN MALAYSIA
MINISTRY OF EDUCATION MALAYSIA
MATRICULATION DIVISION
Ref : KPM.600-1/2/3
Date : 1 June 2026
OFFER OF ADMISSION TO THE MATRICULATION PROGRAMME, MINISTRY OF EDUCATION MALAYSIA
Name : Ali bin Abu
Stream : Science
College : Kolej Matrikulasi Contoh
Date of registration : 3 August 2026
You must register on the date set by the college.
This offer will be cancelled immediately if you fail to register.
Director
Matriculation Division
"""
MATRIC_MS = """KEMENTERIAN PENDIDIKAN MALAYSIA
BAHAGIAN MATRIKULASI
TAWARAN KEMASUKAN PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN MALAYSIA
Nama : Ali bin Abu
Jurusan : Sains
Kolej : Kolej Matrikulasi Contoh
Tarikh Kemasukan ke Kolej : 3 Ogos 2026
Saudara perlu mendaftar pada tarikh yang ditetapkan oleh pihak kolej.
Tawaran ini terbatal serta merta jika saudara gagal mendaftar.
"""


def _offer_read(text, crest=True):
    return signature_genuineness(text, doc_type='offer_letter', has_crest=crest)


class TheEnglishMatricOffer(SimpleTestCase):
    def test_reads_genuine_with_the_crest_like_the_malay_one(self):
        # CHANGED by the help H2 review (2026-11-15): only distinctive English phrases score now (no bare
        # "STREAM" / "COLLEGE" twin), so the English letter needs the crest to reach genuine (was: equal to the
        # Malay one without it). Without the crest it reads suspect - fail safe (decisions.md S6 item 7).
        en, ms = _offer_read(MATRIC_EN), _offer_read(MATRIC_MS)
        self.assertEqual((en['status'], en['type']), ('genuine', 'matriculation'))
        self.assertEqual((ms['status'], ms['type']), ('genuine', 'matriculation'))
        self.assertEqual(_offer_read(MATRIC_EN, crest=False)['status'], 'suspect')

    def test_a_known_college_on_the_letterhead_still_opens_it(self):
        text = MATRIC_EN.replace('MATRICULATION DIVISION\nRef', 'MATRICULATION DIVISION\nKOLEJ MATRIKULASI PERAK\nRef')
        self.assertEqual(_offer_read(text)['status'], 'genuine')

    def test_opens_only_with_the_division_and_the_ministry(self):
        no_ministry = MATRIC_EN.replace('MINISTRY OF EDUCATION MALAYSIA', 'CONTOH').replace(
            ', MINISTRY OF EDUCATION MALAYSIA', '')
        self.assertNotEqual(_offer_read(no_ministry)['status'], 'genuine')

    def test_a_partner_or_a_private_body_never_opens_it(self):
        for text in (MATRIC_EN.replace('Director', 'In collaboration with Mercu College'),
                     MATRIC_EN.replace('Director', 'Mercu Education Sdn Bhd')):
            with self.subTest(text=text.splitlines()[-3]):
                self.assertNotEqual(_offer_read(text)['status'], 'genuine')

    def test_the_division_must_be_the_first_body_on_the_letterhead(self):
        for name, text in (
                ('a private body first', 'MERCU UNIVERSITY\n' + MATRIC_EN),
                ('an unlisted "matric college" first', 'KOLEJ MATRIKULASI MERCU\n' + MATRIC_EN),
                ('a private college under the Division', MATRIC_EN.replace(
                    'MATRICULATION DIVISION\nRef', 'MATRICULATION DIVISION\nMERCU COLLEGE\nRef'))):
            with self.subTest(name):
                self.assertNotEqual(_offer_read(text)['status'], 'genuine')

    def test_the_english_offer_title_is_needed(self):
        text = MATRIC_EN.replace('OFFER OF ADMISSION TO THE MATRICULATION PROGRAMME', 'OFFER OF ADMISSION')
        self.assertNotEqual(_offer_read(text)['status'], 'genuine')


# ── The adversarial review's forged letters (help H2 review, 2026-11-15) ─────────────────────
#: A private university's English offer that only MENTIONS the Division and the ministry in its body (read
#: genuine matriculation at 0.71 / 0.86 through the bare "STREAM" / "COLLEGE" twins before the fix).
FORGED_PRIVATE_EN = """MERCU UNIVERSITY
Jalan Contoh, 50000 Kuala Lumpur
Ref : MU/ADM/2026
Date : 1 June 2026
OFFER OF ADMISSION
Dear Ali bin Abu,
Based on your results from the Matriculation Division, Ministry of Education Malaysia, we are pleased to offer you a place.
Stream : Science
College : Mercu University
Date of registration : 3 August 2026
You must register on the date set by the university.
This offer will be cancelled immediately if you fail to register.
Registrar
"""
#: A private college's foundation offer "equivalent to" the Division's programme.
FORGED_FOUNDATION = """MERCU COLLEGE
Jalan Contoh, 50000 Kuala Lumpur
OFFER OF ADMISSION TO THE FOUNDATION IN SCIENCE
Dear Ali bin Abu,
The Foundation in Science, equivalent to the Matriculation programme of the Matriculation Division, Ministry of Education Malaysia.
Stream : Science
College : Mercu College
Date of registration : 3 August 2026
You must register on the date set by the college.
This offer will be cancelled immediately if you fail to register.
Director
"""
#: KPM's English matriculation RESULTS slip uploaded as an offer.
RESULTS_SLIP_EN = """MINISTRY OF EDUCATION MALAYSIA
MATRICULATION DIVISION
MATRICULATION PROGRAMME EXAMINATION RESULT SLIP
Session 2025/2026
Name : Ali bin Abu
College : Kolej Matrikulasi Perak
Stream : Science
Date of registration : 3 August 2025
CGPA : 3.75
Status : Pass
"""


class TheForgedEnglishLetters(SimpleTestCase):
    def test_stay_not_an_offer_letter_with_or_without_the_crest(self):
        for name, text in (('private university', FORGED_PRIVATE_EN), ('foundation', FORGED_FOUNDATION),
                           ('results slip', RESULTS_SLIP_EN)):
            for crest in (False, True):
                with self.subTest(name, crest=crest):
                    self.assertEqual(_offer_read(text, crest)['status'], 'not_offer_letter')


class TheForgedLettersWriteNoPick(TestCase):
    def test_no_course_pick(self):
        # The pick doors (the link and the realignment) both refuse the letter, as for any fake.
        from apps.scholarship.services.offer_link import plan_offer_link
        from apps.scholarship.services.offer_sync import plan_bumi_realign
        for text in (FORGED_PRIVATE_EN, FORGED_FOUNDATION):
            with self.subTest(text=text.splitlines()[0]):
                out = _offer_read(text)
                app = make_application('shortlisted', chosen_pathway='degree', chosen_programme={})
                doc = _offer(app, out['status'], doc_seen=out['type'], institution='MERCU UNIVERSITY',
                             programme='IJAZAH SARJANA MUDA KEJURUTERAAN AWAM')
                chk = student_offer_check(doc)
                self.assertEqual(plan_offer_link(app, doc, chk)[:2], ('not_offer_letter', None))
                self.assertNotEqual(plan_bumi_realign(app, doc, chk)[0], '')


# ── "MERCU" names: a public-looking name off the official lists is no proof (help H2 review) ──
class PublicLookingNamesNeedClearProof(SimpleTestCase):
    def test_an_unlisted_name_reads_suspect_never_genuine(self):
        for name, head, seen in (
                ('KV, the ministry only in the body', 'KOLEJ VOKASIONAL ANTARABANGSA MERCU', 'confirmation_kv'),
                ('Kolej Matrikulasi Mercu', f'KOLEJ MATRIKULASI MERCU\n{KPM}', 'confirmation_matriculation'),
                ('a listed college with an extra word', f'KOLEJ MATRIKULASI PERAK MERCU\n{KPM}',
                 'confirmation_matriculation'),
                ('IPG Mercu', f'INSTITUT PENDIDIKAN GURU MERCU\n{KPM}', 'confirmation_ipg'),
                ('Kolej Komuniti Mercu', f'KOLEJ KOMUNITI MERCU\n{KPT}', 'confirmation_kolej_komuniti')):
            text = _confirm(head)
            if 'body' in name:
                text = text.replace('Sekian', f'Kolej ini di bawah {KPM}.\nSekian')
            with self.subTest(name):
                out = signature_genuineness(text, doc_type='offer_letter')
                self.assertEqual((out['status'], out['type'], ruling_of(out)),
                                 ('suspect', seen, 'confirmation_unclear'))

    def test_approval_wording_is_no_public_mark(self):
        # "Approved by KPT" names a private college's regulator: no confirmation lift, the baseline stands.
        for head in ('MERCU COMMUNITY COLLEGE\nApproved by Kementerian Pendidikan Tinggi',
                     'KOLEJ KOMUNITI MERCU\nDiluluskan oleh Kementerian Pendidikan Tinggi',
                     'MERCU COLLEGE\nRegistered with the Ministry of Higher Education'):
            with self.subTest(head=head.splitlines()[0]):
                self.assertEqual(confirmation_kind(_confirm(head)), '')
                self.assertEqual(_read(head)['status'], 'not_offer_letter')

    def test_the_division_alone_beside_an_unlisted_college_is_no_mark(self):
        self.assertEqual(confirmation_kind(_confirm('KOLEJ MATRIKULASI MERCU\nBAHAGIAN MATRIKULASI')), '')

    def test_a_polytechnic_needs_its_ministry_on_the_letterhead(self):
        text = _confirm('POLITEKNIK CONTOH').replace('Sekian', f'Politeknik ini di bawah {KPT}.\nSekian')
        out = signature_genuineness(text, doc_type='offer_letter')
        self.assertEqual((out['status'], out['type'], ruling_of(out)),
                         ('suspect', 'confirmation_polytechnic', 'confirmation_unclear'))


# ── English confirmation titles and IIUM's English name (help H2 review) ─────────────────────
def _confirm_en_title(head, title='CONFIRMATION OF STUDENT STATUS'):
    return _confirm(head).replace('PENGESAHAN PELAJAR', title)


class EnglishConfirmations(SimpleTestCase):
    def test_a_public_polytechnic_or_matric_college_reads_genuine(self):
        for head, seen in ((f'POLITEKNIK UNGKU OMAR\n{KPT}', 'confirmation_polytechnic'),
                           (f'KOLEJ MATRIKULASI PERAK\nBAHAGIAN MATRIKULASI\n{KPM}', 'confirmation_matriculation')):
            for title in ('CONFIRMATION OF STUDENT STATUS', 'CONFIRMATION OF STUDIES', 'LETTER OF CONFIRMATION'):
                with self.subTest(head=head.splitlines()[0], title=title):
                    out = signature_genuineness(_confirm_en_title(head, title), doc_type='offer_letter')
                    self.assertEqual((out['status'], out['type'], ruling_of(out)), ('genuine', seen, 'confirmation'))

    def test_iium_by_its_english_name_reads_suspect(self):
        # IIUM has a private wing (IIUM Academy, CENPACE - decisions.md): a person checks.
        out = signature_genuineness(_confirm_en_title('INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA'),
                                    doc_type='offer_letter')
        self.assertEqual((out['status'], out['type'], ruling_of(out)),
                         ('suspect', 'confirmation_ua', 'confirmation_ua'))

    def test_iiums_private_wing_still_fails(self):
        for head in ('IIUM ACADEMY\nINTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA',
                     'CENTRE FOR PROFESSIONAL AND CONTINUING EDUCATION (CENPACE)\n'
                     'INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA'):
            with self.subTest(head=head.splitlines()[0]):
                self.assertEqual(signature_genuineness(_confirm_en_title(head), doc_type='offer_letter')['status'],
                                 'not_offer_letter')
