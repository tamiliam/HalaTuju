"""Help H2 (owner ruling 2026-11-15, ruling 4 WIDENED): a confirmation of studies from EVERY public institution
type is an acceptable alternative to the offer letter (genuine, never a course pick); one from a public university
that has a private wing reads suspect (a person checks); a private college or a university's private wing still
fails. And KPM's English matriculation offer is recognised like the Malay one. Synthetic twins only: every letter
is invented (`test_no_gitignored_corpus.py`), no real name or IC.
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
GENUINE = (
    ('matric (Malay)', f'KOLEJ MATRIKULASI CONTOH\nBAHAGIAN MATRIKULASI\n{KPM}', 'confirmation_matriculation'),
    ('matric (English)', 'MATRICULATION COLLEGE CONTOH\nMATRICULATION DIVISION\nMINISTRY OF EDUCATION MALAYSIA',
     'confirmation_matriculation'),
    ('IPG', f'INSTITUT PENDIDIKAN GURU KAMPUS CONTOH\n{KPM}', 'confirmation_ipg'),
    ('KV', f'KOLEJ VOKASIONAL CONTOH\n{KPM}', 'confirmation_kv'),
    ('community college', f'KOLEJ KOMUNITI CONTOH\n{KPT}', 'confirmation_kolej_komuniti'),
    ('IKBN', 'INSTITUT KEMAHIRAN BELIA NEGARA CONTOH\nKEMENTERIAN BELIA DAN SUKAN', 'confirmation_tvet'),
    ('polytechnic', f'POLITEKNIK CONTOH\n{KPT}', 'confirmation_polytechnic'),
    ('Form 6', f'KOLEJ TINGKATAN ENAM CONTOH\n{KPM}', 'confirmation_form6'),
    ('IPTA with no private wing (UMS)', 'UNIVERSITI MALAYSIA SABAH\nBahagian Perkhidmatan Akademik', 'confirmation_ums'),
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
    def test_reads_genuine_as_a_confirmation(self):
        for name, head, seen in GENUINE:
            with self.subTest(name):
                self.assertEqual(confirmation_kind(_confirm(head)), seen)
                out = _read(head)
                self.assertEqual((out['status'], out['type']), ('genuine', seen))
                self.assertEqual(ruling_of(out), 'confirmation')

    def test_every_code_is_a_confirmation_code(self):
        for _name, _head, seen in GENUINE:
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


class TheEnglishMatricOffer(SimpleTestCase):
    def test_reads_like_the_malay_one(self):
        en = signature_genuineness(MATRIC_EN, doc_type='offer_letter')
        ms = signature_genuineness(MATRIC_MS, doc_type='offer_letter')
        self.assertEqual((en['status'], en['type']), ('genuine', 'matriculation'))
        self.assertEqual((ms['status'], ms['type']), ('genuine', 'matriculation'))
        self.assertEqual(en['probability'], ms['probability'])

    def test_opens_only_with_the_division_and_the_ministry(self):
        no_ministry = MATRIC_EN.replace('MINISTRY OF EDUCATION MALAYSIA', 'CONTOH').replace(
            ', MINISTRY OF EDUCATION MALAYSIA', '')
        self.assertNotEqual(signature_genuineness(no_ministry, doc_type='offer_letter')['status'], 'genuine')

    def test_a_partner_or_a_private_body_never_opens_it(self):
        for text in (MATRIC_EN.replace('Director', 'In collaboration with Mercu College'),
                     MATRIC_EN.replace('Director', 'Mercu Education Sdn Bhd')):
            with self.subTest(text=text.splitlines()[-3]):
                self.assertNotEqual(signature_genuineness(text, doc_type='offer_letter')['status'], 'genuine')
