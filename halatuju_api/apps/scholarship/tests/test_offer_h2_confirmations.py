"""Help H2, owner option B (2026-11-15, decisions.md ruling 4): a NEW confirmation of studies from a public
institution never reads genuine by itself. It reads SUSPECT (a person checks) and the student is not blocked; it
never writes a course pick. A private college or a university's private wing still fails. KPM's English
matriculation offer is recognised the same way: suspect at most, never a pick. CHANGED by help H2 owner 16 Nov:
all confirmations suspect - the polytechnic, UMS and Form-6 confirmations keep main's recognition rule but read
SUSPECT too (they were genuine on main).

The adversarial letters of the H2 review rounds (rounds 1-5) are kept below: none reads genuine (TD-633, the
Form-6 path, closed 16 Nov). Synthetic twins only: every letter is invented
(`test_no_gitignored_corpus.py`), no real name or IC.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.scholarship.genuineness.offer_confirmations import CONFIRMATION_SEEN, MATRIC_OFFER_EN
from apps.scholarship.genuineness.offer_issuers import officer_must_close
from apps.scholarship.genuineness.offer_reading import _folded_lines
from apps.scholarship.genuineness.offer_rulings import confirmation_kind, english_matric_offer, ruling_of
from apps.scholarship.genuineness.results_doc import signature_genuineness
from apps.scholarship.pathway_engine import is_confirmation_letter, student_offer_check
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_offer_rulings import _confirm
from apps.scholarship.tests.test_offer_s6_doors import _offer

KPM, KPT = 'KEMENTERIAN PENDIDIKAN MALAYSIA', 'KEMENTERIAN PENDIDIKAN TINGGI'
KK = 'KOLEJ KOMUNITI KLANG'

#: Main's live recognition rule, unchanged; CHANGED by help H2 owner 16 Nov: all confirmations suspect (they were
#: genuine, tag `confirmation`, on main; now suspect, tag `confirmation_check`).
MAIN_LIVE_GENUINE = (
    ('polytechnic', f'POLITEKNIK UNGKU OMAR\n{KPT}', 'confirmation_polytechnic'),
    ('polytechnic, another', f'POLITEKNIK SULTAN AZLAN SHAH\n{KPT}', 'confirmation_polytechnic'),
    ('UMS', 'UNIVERSITI MALAYSIA SABAH\nBahagian Perkhidmatan Akademik', 'confirmation_ums'),
    ('Form 6', f'KOLEJ TINGKATAN ENAM CONTOH\n{KPM}', 'confirmation_form6'),
)
#: Newly covered (option B): recognised, SUSPECT, tag `confirmation_check` - never genuine, never a block.
NEW_SUSPECT = (
    ('matric', f'KOLEJ MATRIKULASI PERAK\nBAHAGIAN MATRIKULASI\n{KPM}', 'confirmation_matriculation'),
    ('matric, the Division itself', f'BAHAGIAN MATRIKULASI\n{KPM}', 'confirmation_matriculation'),
    ('matric, English names', 'MATRICULATION COLLEGE CONTOH\nMATRICULATION DIVISION\nMINISTRY OF EDUCATION MALAYSIA',
     'confirmation_matriculation'),
    ('matric, a campus line', f'KOLEJ MATRIKULASI PERAK\nKAMPUS GOPENG\n{KPM}', 'confirmation_matriculation'),
    ('matric, a campus line naming a state', f'KOLEJ MATRIKULASI PERAK\nKAMPUS PERAK\n{KPM}',
     'confirmation_matriculation'),
    ('community college, its own campus', f'{KK}\nKAMPUS KLANG\n{KPT}', 'confirmation_kolej_komuniti'),
    ('matric, an unlisted college', f'KOLEJ MATRIKULASI CONTOH\nBAHAGIAN MATRIKULASI\n{KPM}',
     'confirmation_matriculation'),
    ('IPG', f'INSTITUT PENDIDIKAN GURU KAMPUS IPOH\n{KPM}', 'confirmation_ipg'),
    ('IPG, short form', f'IPG KAMPUS IPOH\n{KPM}', 'confirmation_ipg'),
    ('IPG under IPGM', f'INSTITUT PENDIDIKAN GURU MALAYSIA\nINSTITUT PENDIDIKAN GURU KAMPUS IPOH\n{KPM}',
     'confirmation_ipg'),
    ('KV', f'KOLEJ VOKASIONAL CONTOH\n{KPM}', 'confirmation_kv'),
    ('community college', f'KOLEJ KOMUNITI SELAYANG\n{KPT}', 'confirmation_kolej_komuniti'),
    ('community college, English ministry', 'KOLEJ KOMUNITI SELAYANG\nMINISTRY OF HIGHER EDUCATION',
     'confirmation_kolej_komuniti'),
    ('IKBN', 'INSTITUT KEMAHIRAN BELIA NEGARA CONTOH\nKEMENTERIAN BELIA DAN SUKAN', 'confirmation_tvet'),
)
#: Another public university (it has a private wing): SUSPECT, tag `confirmation_ua`.
UNIVERSITIES = ('UNIVERSITI PUTRA MALAYSIA\nBahagian Akademik', 'UNIVERSITI MALAYA\nJabatan Pendaftar',
                'UNIVERSITI TEKNOLOGI MALAYSIA\nPejabat Pendaftar')
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
    ('an organisation noun under a matric college', f'KOLEJ MATRIKULASI PERAK\nMERCU FOUNDATION CENTRE\n{KPM}'),
    ('a campus line naming a college', f'KOLEJ MATRIKULASI PERAK\nKAMPUS MERCU COLLEGE\n{KPM}'),
)


def _read(text, crest=False):
    return signature_genuineness(text, doc_type='offer_letter', has_crest=crest)


def _verdict(text, crest=False):
    out = _read(text, crest)
    return out['status'], out['type'], ruling_of(out)


def _confirm_en_title(head, title='CONFIRMATION OF STUDENT STATUS'):
    return _confirm(head).replace('PENGESAHAN PELAJAR', title)


def _form6(head):
    return _confirm(head).replace('PENGESAHAN PELAJAR', 'PENGESAHAN BELAJAR').replace('Bidang : Sains', 'Tingkatan 6 Atas')


class MainLiveConfirmationsAreUnchanged(SimpleTestCase):
    def test_read_suspect_on_mains_recognition_rule(self):
        # CHANGED by help H2 owner 16 Nov: all confirmations suspect (main read these genuine). Main's
        # recognition rule is unchanged (`confirmation_kind`); the crest lifts nothing
        for name, head, seen in MAIN_LIVE_GENUINE:
            for crest in (False, True):
                with self.subTest(name, crest=crest):
                    self.assertEqual(confirmation_kind(_confirm(head)), seen)
                    self.assertEqual(_verdict(_confirm(head), crest), ('suspect', seen, 'confirmation_check'))


class NewPublicConfirmationsReadSuspect(SimpleTestCase):
    def test_every_new_type_reads_suspect_never_genuine(self):
        for name, head, seen in NEW_SUSPECT:
            for crest in (False, True):                   # the crest lifts nothing
                with self.subTest(name, crest=crest):
                    self.assertEqual(confirmation_kind(_confirm(head)), '')       # never main's genuine rule
                    self.assertEqual(_verdict(_confirm(head), crest), ('suspect', seen, 'confirmation_check'))

    def test_another_public_university_reads_suspect(self):
        for head in UNIVERSITIES:
            with self.subTest(head=head.splitlines()[0]):
                self.assertEqual(_verdict(_confirm(head)), ('suspect', 'confirmation_ua', 'confirmation_ua'))

    def test_every_code_is_a_confirmation_code(self):
        for _name, _head, seen in MAIN_LIVE_GENUINE + NEW_SUSPECT:
            self.assertIn(seen, CONFIRMATION_SEEN)
        for seen in ('confirmation_ua', MATRIC_OFFER_EN):
            self.assertIn(seen, CONFIRMATION_SEEN)


class EnglishConfirmationTitles(SimpleTestCase):
    def test_an_english_title_reads_suspect_even_for_a_main_live_type(self):
        # main never read an English title; option B reads it on the suspect path only
        for head, seen in ((f'POLITEKNIK UNGKU OMAR\n{KPT}', 'confirmation_polytechnic'),
                           (f'KOLEJ MATRIKULASI PERAK\nBAHAGIAN MATRIKULASI\n{KPM}', 'confirmation_matriculation')):
            for title in ('CONFIRMATION OF STUDENT STATUS', 'CONFIRMATION OF STUDIES', 'LETTER OF CONFIRMATION'):
                with self.subTest(head=head.splitlines()[0], title=title):
                    self.assertEqual(_verdict(_confirm_en_title(head, title)), ('suspect', seen, 'confirmation_check'))

    def test_iium_by_its_english_name_reads_suspect(self):
        self.assertEqual(_verdict(_confirm_en_title('INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA')),
                         ('suspect', 'confirmation_ua', 'confirmation_ua'))

    def test_iiums_private_wing_still_fails(self):
        for head in ('IIUM ACADEMY\nINTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA',
                     'CENTRE FOR PROFESSIONAL AND CONTINUING EDUCATION (CENPACE)\n'
                     'INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA'):
            with self.subTest(head=head.splitlines()[0]):
                self.assertEqual(_read(_confirm_en_title(head))['status'], 'not_offer_letter')


class PrivateIssuersStillFail(SimpleTestCase):
    def test_a_private_college_or_a_private_wing_fails(self):
        for name, head in FAILS:
            for crest in (False, True):
                with self.subTest(name, crest=crest):
                    self.assertEqual(_read(_confirm(head), crest)['status'], 'not_offer_letter')

    def test_approval_wording_is_no_public_mark(self):
        # "Approved by KPT" names a private college's regulator: no confirmation, the baseline stands
        heads = ['MERCU COMMUNITY COLLEGE\nApproved by Kementerian Pendidikan Tinggi',
                 'MERCU COLLEGE\nRegistered with the Ministry of Higher Education']
        heads += [f'KOLEJ KOMUNITI MERCU\n{p} Kementerian Pendidikan Tinggi'
                  for p in ('Diluluskan oleh', 'Didaftar dengan', 'Dilesenkan oleh', 'Di bawah seliaan', 'Reg. No. 123 /',
                            'No. Pendaftaran :', 'Under the purview of the')]
        for head in heads:
            with self.subTest(head=head):
                self.assertEqual(_read(_confirm(head))['status'], 'not_offer_letter')

    def test_no_public_name_with_its_ministry_is_no_confirmation(self):
        for head in (f'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI\n{KPT}', 'KOLEJ MATRIKULASI CONTOH\nJalan Contoh',
                     'KOLEJ MATRIKULASI MERCU\nBAHAGIAN MATRIKULASI'):
            with self.subTest(head=head):
                status, seen, ruling = _verdict(_confirm(head))
                self.assertNotIn(seen, CONFIRMATION_SEEN)      # no confirmation: the family baseline stands
                self.assertEqual(ruling, '')
                self.assertNotEqual(status, 'genuine')

    def test_a_public_name_only_in_the_body_or_below_the_title_is_no_confirmation(self):
        for text in (_confirm(f'MERCU PRESTIGE\n{KPT}').replace('Institusi : Contoh', f'Institusi : {KK}'),
                     _confirm(KPT).replace('PENGESAHAN PELAJAR\n', f'PENGESAHAN PELAJAR\n{KK}\n')):
            with self.subTest(text=text.splitlines()[0]):
                self.assertEqual(_read(text)['status'], 'not_offer_letter')


class TheDoors(TestCase):
    """A confirmation never writes a course pick; the officer still closes her own request; a suspect never
    blocks the submission."""

    def _app(self):
        return make_application('shortlisted', chosen_pathway='matric', chosen_programme={})

    def test_never_a_pick_and_never_a_block(self):
        from apps.scholarship.services.blockers import _offer_blocks
        from apps.scholarship.services.offer_link import plan_offer_link
        from apps.scholarship.services.offer_sync import autofill_pathway_from_offer, plan_bumi_realign
        for seen in ('confirmation_matriculation', 'confirmation_ipg', 'confirmation_kv', 'confirmation_kolej_komuniti',
                     'confirmation_tvet', 'confirmation_ua', MATRIC_OFFER_EN):
            with self.subTest(seen=seen):
                app = self._app()
                doc = _offer(app, 'suspect', doc_seen=seen, institution='KOLEJ MATRIKULASI CONTOH',
                             programme='PROGRAM MATRIKULASI SAINS')
                self.assertTrue(is_confirmation_letter(doc))
                chk = student_offer_check(doc)
                self.assertEqual(plan_bumi_realign(app, doc, chk)[0], 'not_genuine')
                self.assertEqual(plan_offer_link(app, doc, chk)[0], 'confirmation_letter')
                autofill_pathway_from_offer(app)
                app.refresh_from_db()
                cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
                self.assertFalse((cp.get('course_name') or '').strip())
                self.assertFalse(_offer_blocks(app))

    def test_the_officer_closes_her_own_request(self):
        app = self._app()
        for seen in ('confirmation_matriculation', MATRIC_OFFER_EN):
            with self.subTest(seen=seen):
                doc = _offer(app, 'suspect', doc_seen=seen)
                self.assertTrue(officer_must_close(doc, SimpleNamespace(source='officer', doc_type='offer_letter')))


# ── KPM's English matriculation offer (option B: suspect, never a pick) ─────────────────────
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
#: A private university's English offer that only MENTIONS the Division and the ministry in its body.
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
_UNDER = 'MATRICULATION DIVISION\nRef'


def _en(old, new):
    return MATRIC_EN.replace(old, new)


class TheEnglishMatricOffer(SimpleTestCase):
    def test_is_recognised_but_reads_suspect_with_or_without_the_crest(self):
        self.assertTrue(english_matric_offer(_folded_lines(MATRIC_EN)))
        for crest in (False, True):
            with self.subTest(crest=crest):
                self.assertEqual(_verdict(MATRIC_EN, crest), ('suspect', MATRIC_OFFER_EN, 'matric_offer_en'))

    def test_the_malay_offer_is_unchanged(self):
        out = _read(MATRIC_MS)
        self.assertEqual((out['status'], out['type']), ('genuine', 'matriculation'))     # main's family read

    def test_an_extra_line_or_a_private_name_in_the_body_never_makes_it_genuine(self):
        for name, text in (
                ('a group after the ministry', _en('MINISTRY OF EDUCATION MALAYSIA\nMATRICULATION DIVISION',
                                                   'MINISTRY OF EDUCATION MALAYSIA MERCU EDUCATION GROUP\n'
                                                   'MATRICULATION DIVISION')),
                ('a brand after KPM', _en('KEMENTERIAN PENDIDIKAN MALAYSIA\n', 'KEMENTERIAN PENDIDIKAN MALAYSIA MERCU '
                                          'INTERNATIONAL\n')),
                ('a line between', _en(_UNDER, 'MATRICULATION DIVISION\nSTUDENT SERVICES MERCU GLOBAL\nRef')),
                ('a council line', _en(_UNDER, 'MATRICULATION DIVISION\nMAJLIS MERCU LEARNING\nRef')),
                ('a plain line', _en(_UNDER, 'MATRICULATION DIVISION\nMERCU ASIA PACIFIC\nRef')),
                ('a known college under', _en(_UNDER, 'MATRICULATION DIVISION\nKOLEJ MATRIKULASI PERAK\nRef')),
                ('a web address', _en(_UNDER, 'MATRICULATION DIVISION\nwww.mercu.com.my\nRef')),
                ('a campus line', _en(_UNDER, 'MATRICULATION DIVISION\nCAMPUS MERCU PRESTIGE\nRef')),
                ('a private college in the body', _en('College : Kolej Matrikulasi Contoh',
                                                      'College : MERCU INTERNATIONAL COLLEGE')),
                ('a private signature', _en('Director\nMatriculation Division', 'Director\nMERCU UNIVERSITY COLLEGE')),
                ('a brand on the reference', _en('Ref : KPM.600-1/2/3', 'Ref : KPM.600-1/2/3 MERCU UNIVERSITY'))):
            for crest in (False, True):
                with self.subTest(name, crest=crest):
                    self.assertEqual(_read(text, crest)['status'], 'suspect')

    def test_not_recognised_without_the_division_first_its_title_or_its_ministry(self):
        for name, text in (
                ('a private body first', 'MERCU UNIVERSITY\n' + MATRIC_EN),
                ('a two-word line above', 'MERCU GLOBAL\n' + MATRIC_EN),
                ('an unlisted "matric college" first', 'KOLEJ MATRIKULASI MERCU\n' + MATRIC_EN),
                ('a private college under the Division', _en(_UNDER, 'MATRICULATION DIVISION\nMERCU COLLEGE\nRef')),
                ('no ministry', _en('MINISTRY OF EDUCATION MALAYSIA', 'CONTOH')),
                ('a partner', _en('Director', 'In collaboration with Mercu College')),
                ('a company', _en('Director', 'Mercu Education Sdn Bhd')),
                ('an agent', _en('Director', 'Wakil Mercu')),
                ('no English matric title', _en('OFFER OF ADMISSION TO THE MATRICULATION PROGRAMME', 'OFFER OF ADMISSION'))):
            for crest in (False, True):
                with self.subTest(name, crest=crest):
                    self.assertEqual(_read(text, crest)['status'], 'not_offer_letter')


class TheForgedEnglishLetters(SimpleTestCase):
    """Round-1/2 safety: a results slip and a private university's offer that mentions the Division stay
    `not_offer_letter`; neither is read as a matric offer."""

    def test_stay_not_an_offer_letter_with_or_without_the_crest(self):
        for name, text in (('private university', FORGED_PRIVATE_EN), ('foundation', FORGED_FOUNDATION),
                           ('results slip', RESULTS_SLIP_EN)):
            self.assertFalse(english_matric_offer(_folded_lines(text)))
            for crest in (False, True):
                with self.subTest(name, crest=crest):
                    self.assertEqual(_read(text, crest)['status'], 'not_offer_letter')


class TheEnglishLettersWriteNoPick(TestCase):
    def test_the_matric_offer_writes_no_course_pick(self):
        from apps.scholarship.services.offer_link import plan_offer_link
        from apps.scholarship.services.offer_sync import autofill_pathway_from_offer
        out = _read(MATRIC_EN, True)
        app = make_application('shortlisted', chosen_pathway='matric', chosen_programme={})
        doc = _offer(app, out['status'], doc_seen=out['type'], institution='KOLEJ MATRIKULASI CONTOH',
                     programme='PROGRAM MATRIKULASI SAINS')
        self.assertEqual(plan_offer_link(app, doc, student_offer_check(doc))[0], 'confirmation_letter')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
        self.assertFalse((cp.get('course_name') or '').strip())

    def test_the_forged_letters_write_no_pick(self):
        from apps.scholarship.services.offer_link import plan_offer_link
        from apps.scholarship.services.offer_sync import plan_bumi_realign
        for text in (FORGED_PRIVATE_EN, FORGED_FOUNDATION):
            with self.subTest(text=text.splitlines()[0]):
                out = _read(text, True)
                app = make_application('shortlisted', chosen_pathway='degree', chosen_programme={})
                doc = _offer(app, out['status'], doc_seen=out['type'], institution='MERCU UNIVERSITY',
                             programme='IJAZAH SARJANA MUDA KEJURUTERAAN AWAM')
                chk = student_offer_check(doc)
                self.assertEqual(plan_offer_link(app, doc, chk)[:2], ('not_offer_letter', None))
                self.assertNotEqual(plan_bumi_realign(app, doc, chk)[0], '')


# ── The H2 review rounds' adversarial letters (rounds 1-5): none reads genuine ────────────────
ADVERSARIAL = (
    f'{KK}\n{KPT}', f'MERCU KOLEJ KOMUNITI KLANG\n{KPT}', f'BAHAGIAN MATRIKULASI\nPUSAT ASASI MERCU\n{KPM}',
    f'MERCU BAHAGIAN MATRIKULASI\n{KPM}', f'KOLEJ MATRIKULASI N.SEMBILAN\n{KPM}', f'KM MERCU\nBAHAGIAN MATRIKULASI\n{KPM}',
    f'KMK MERCU\nBAHAGIAN MATRIKULASI\n{KPM}', f'{KPM} KOLEJ MATRIKULASI LABUAN', f'KM P.PINANG\n{KPM}', f'KM PERAK\n{KPM}',
    f'KMK KEDAH\n{KPM}', f'KOLEJ MATRIKULASI PULAU PINANG (KMPP)\n{KPM}',
    f'{KK}\n{KPT} MERCU EDUCATION GROUP', f'{KK}\nMAJLIS MERCU EDUCATION\n{KPT}', f'{KK}\nKOLEJ VOKASIONAL MERCU\n{KPT}',
    f'{KK}\nKOLEJ KEJURURAWATAN MERCU\n{KPT}', f'{KK}\nSEKOLAH ANTARABANGSA MERCU\n{KPT}',
    f'{KK}\nSCHOOL OF MERCU BUSINESS\n{KPT}', f'{KK}\nSTUDENT SERVICES MERCU\n{KPT}', f'MERCU JAYA\n{KK}\n{KPT}',
    f'{KK}\nMERCU JAYA\n{KPT}', f'{KK} JALAN MERCU COLLEGE\n{KPT}', f'{KK} 2 MERCU\n{KPT}',
    f'{KK}\nGOVERNMENT LINKED MERCU TRAINING\n{KPT}', f'BAHAGIAN MATRIKULASI\n{KPM} MERCU EDU HUB',
    f'{KK}\nKOLEJ MATRIKULASI MERCU\n{KPT}', f'{KK} P MERCU HOLDINGS\n{KPT}', f'{KPT} MERCU INTERNATIONAL\n{KK}',
    f'{KK} UNIT PENDIDIKAN MALAYSIA\n{KPT}', f'{KK}\nPUSAT PENGAJIAN DAN PENGURUSAN\n{KPT}',
    f'{KK}\nCENTRE FOR ACADEMIC AFFAIRS\n{KPT}', f'{KK}\nMERCU COLLEGE, JALAN 1, 11900 PULAU PINANG\n{KPT}',
    f'{KK}\nJALAN 1, MERCU JAYA EDUCATION, 41050 KLANG\n{KPT}', f'{KK}\nKOMPLEKS MERCU PRESTIGE, 41050 SELANGOR\n{KPT}',
    f'{KK}\nTAMAN SEGI, 41050 SELANGOR\n{KPT}', f'{KK}\n{KPT}\nwww.mercu.edu.my', f'{KK}\n{KPT}\nwww.mercucollege.com.my',
    f'{KK}\n{KPT}\nwww.segi.com.my', f'{KK}\n{KPT}\nEmel: admin@mercu.com.my', f'{KK}\n{KPT}\nTel: 03-1234 5678 MERCU',
    f'{KK}\nKAMPUS MERCU PRESTIGE\n{KPT}', f'{KK}\nCAMPUS SEGI SUBANG\n{KPT}', f'{KK}\nSELANGOR JALAN MERCU PRESTIGE\n{KPT}',
    f'{KK}\nTARIKH MERCU\n{KPT}', f'{KK} (MERCU)\n{KPT}', f'{KK}\nP.O. BOX 12 MERCU PRESTIGE\n{KPT}',
    f'{KK}\nLOT 5 MERCU PRESTIGE\n{KPT}', f'{KK}\nMUKIM MERCU PRESTIGE\n{KPT}', f'{KK}\nBEG BERKUNCI 5 MERCU PRESTIGE\n{KPT}',
    f'{KPT} MERCU\n{KK}', f'KERAJAAN MALAYSIA MERCU\n{KK}\n{KPT}', f'{KK}\nKLANG\n{KPT}',
    f'IPGM\nINSTITUT PENDIDIKAN GURU KAMPUS IPOH\n{KPM}', f'INSTITUT PENDIDIKAN GURU KAMPUS P.PINANG\n{KPM}',
    f'INSTITUT PENDIDIKAN GURU MERCU\n{KPM}', f'KOLEJ MATRIKULASI MERCU\n{KPM}', f'KOLEJ MATRIKULASI PERAK MERCU\n{KPM}',
    f'KOLEJ KOMUNITI MERCU\n{KPT}', 'KOLEJ VOKASIONAL ANTARABANGSA MERCU',
    f'{KPT}\nJABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI\nKOLEJ KOMUNITI SELAYANG',
)
#: These read genuine on main through the live polytechnic / Form-6 path (the Form-6 ones were TD-633: genuine
#: before any letterhead check). CHANGED by help H2 owner 16 Nov: all confirmations suspect - TD-633 closed.
MAIN_LIVE_ADVERSARIAL = (
    (f'POLITEKNIK MERCU\n{KPT}', 'confirmation_polytechnic'),
    (f'POLITEKNIK UNGKU OMAR\nLEMBAGA MERCU SKILLS\n{KPT}', 'confirmation_polytechnic'),
    (f'POLITEKNIK UNGKU OMAR MERCU\n{KPT}', 'confirmation_polytechnic'),
    ('MERCU POLYTECHNIC\nMINISTRY OF HIGHER EDUCATION', 'confirmation_polytechnic'),
    (f'SMK MERCU JAYA\n{KPM} MERCU PRESTIGE', 'confirmation_form6'),
    (f'MERCU PRESTIGE\nSMK MERCU JAYA\n{KPM}', 'confirmation_form6'),
)


class TheAdversarialLetters(SimpleTestCase):
    def test_none_reads_genuine(self):
        for head in ADVERSARIAL:
            for text in (_confirm(head), _confirm_en_title(head),
                         _confirm(head).replace('Sekian', f'Kolej ini di bawah {KPM}.\nSekian')):
                for crest in (False, True):
                    with self.subTest(head=head, title=text.splitlines()[head.count('\n') + 2], crest=crest):
                        out = _read(text, crest)
                        self.assertNotEqual(out['status'], 'genuine')
                        if out['status'] == 'suspect' and ruling_of(out):
                            self.assertIn(ruling_of(out), ('confirmation_check', 'confirmation_ua'))

    def test_the_boundary_lines_read_suspect_never_genuine(self):
        base = _confirm(f'{KK}\n{KPT}')
        for old, new in (('Rujukan : CONTOH/600-1/2', 'Rujukan : CONTOH/600-1/2 MERCU INTERNATIONAL COLLEGE'),
                         ('Tarikh : 1 Jun 2026', 'Tarikh : 1 Jun 2026 MERCU INTERNATIONAL COLLEGE'),
                         ('Institusi : Contoh', 'Institusi : MERCU INTERNATIONAL COLLEGE'),
                         ('PENGARAH\n', 'PENGARAH\nMERCU UNIVERSITY COLLEGE\n'),
                         ('PENGESAHAN PELAJAR\n', 'PENGESAHAN PELAJAR\nMERCU UNIVERSITY COLLEGE\n'),
                         ('PENGESAHAN PELAJAR', 'PENGESAHAN PELAJAR MERCU COLLEGE')):
            for crest in (False, True):
                with self.subTest(new=new, crest=crest):
                    self.assertEqual(_read(base.replace(old, new), crest)['status'], 'suspect')

    def test_a_confirmation_that_mentions_its_offer_reads_suspect(self):
        for head in ('INSTITUT KEMAHIRAN BELIA NEGARA DUSUN TUA\nKEMENTERIAN BELIA DAN SUKAN', f'{KK}\n{KPT}'):
            text = _confirm(head).replace('sedang mengikuti pengajian.',
                                          'sedang mengikuti pengajian berdasarkan surat tawaran dan telah mendaftar.')
            with self.subTest(head=head.splitlines()[0]):
                self.assertEqual(_read(text)['status'], 'suspect')

    def test_main_live_cases_read_suspect(self):
        # CHANGED by help H2 owner 16 Nov: all confirmations suspect (genuine on main; this closes TD-633)
        for head, seen in MAIN_LIVE_ADVERSARIAL:
            text = _form6(head) if seen == 'confirmation_form6' else _confirm(head)
            for crest in (False, True):
                with self.subTest(head=head, crest=crest):
                    self.assertEqual(_verdict(text, crest), ('suspect', seen, 'confirmation_check'))

    def test_form6_without_the_proof_is_no_confirmation(self):
        for head in (f'SMK MERCU JAYA\nMERCU EDUCATION GROUP\n{KPM}', f'SEKOLAH MENENGAH PERSENDIRIAN CHONG HWA\n{KPM}',
                     f'SEKOLAH MENENGAH JENIS KEBANGSAAN CHONG HWA\n{KPM}', f'KOLEJ KOMUNITI MERCU\nSMK MERCU\n{KPM}'):
            with self.subTest(head=head):
                self.assertEqual(_read(_form6(head))['status'], 'not_offer_letter')
