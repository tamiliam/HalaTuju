"""TD-145 (owner 2026-10-04): a different university on the offer is FLAGGED and the student asked.

The owner's words: *"Student declares UMK but uploads, say, UTHM. This should be flagged and student
asked to confirm. When confirmed, the pathway values be updated to reflect the new value."* And,
amended the same day (option 1): a public university's own self-funded channel — UM's Saluran
Terbuka (SATU), #31 — is an IPTS option, red at once, with NO question.

Four units, each pinned here:

* ``offer_pathway.institution_agreement`` rule 1 — a one-campus course now COMPARES the letter with
  its campus. A positive identification of another catalogue institution is a clash; a spelling we
  cannot place is 'unknown', never a clash (the Pagoh safety rule — #48 must stay green).
* ``pathway_engine._declared_pathway`` — the declared side of a course_id-only pick is the
  catalogue's campus, so the student's query names what they actually picked.
* ``services.confirm_pathway`` — a confirm to a different place drops (or re-pins) the stale
  ``course_id``, so the sponsor card cannot show UMK's course beside "UTHM".
* ``genuineness.results_doc`` — 'SALURAN TERBUKA' / 'SALURAN SATU' are private-arm tells.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import Course, CourseInstitution, FieldTaxonomy, Institution
from apps.scholarship import offer_pathway as op
from apps.scholarship.genuineness.results_doc import MODEL_VERSION, signature_genuineness
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.pathway_engine import offer_reporting_bonus, student_offer_check
from apps.scholarship.services import confirm_pathway
from apps.scholarship.tests.factories import make_application
from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION, build_verdict

UTHM = 'Universiti Tun Hussein Onn Malaysia'
UMK = 'Universiti Malaysia Kelantan'
UM = 'Universiti Malaya'
UKM = 'Universiti Kebangsaan Malaysia'
UTM, UITM = 'Universiti Teknologi Malaysia', 'Universiti Teknologi MARA'
USM, USIM = 'Universiti Sains Malaysia', 'Universiti Sains Islam Malaysia'
UPNM = 'Universiti Pertahanan Nasional Malaysia'


class _Catalogue(TestCase):
    """Three universities. The test database is already seeded with the ~580 secondary schools
    the production catalogue holds — among them "Sekolah Menengah Kebangsaan Bandar Tun Hussein Onn
    2", which shares every distinctive token of UTHM's name and is linked to the pre-U virtual
    course stpm-sains. Both made a naive search wrong; the tests below run against them."""

    @classmethod
    def setUpTestData(cls):
        ft = FieldTaxonomy.objects.create(key='td145w', name_en='Science', name_ms='Sains',
                                          name_ta='x', image_slug='td145w')

        def inst(iid, name, acronym):
            return Institution.objects.create(institution_id=iid, institution_name=name,
                                              acronym=acronym, type='UA', state='Johor')

        def course(cid, name, campus):
            c = Course.objects.create(course_id=cid, course=name, level='Ijazah Sarjana Muda',
                                      department='x', field='x', field_key=ft)
            CourseInstitution.objects.create(course=c, institution=campus)
            return c

        cls.uthm = inst('td-uthm', UTHM, 'UTHM')
        cls.umk = inst('td-umk', UMK, 'UMK')
        cls.um = inst('td-um', UM, 'UM')
        course('TD-UTHM-ANIM', 'Ijazah Sarjana Muda Teknologi Animasi', cls.uthm)
        course('TD-UMK-SAINS', 'Ijazah Sarjana Muda Perniagaan Tani', cls.umk)
        course('TD-UM-SAINS', 'Ijazah Sarjana Muda Perniagaan Tani', cls.um)
        # The UTHM programme a UMK→UTHM confirm can be re-pinned to (unique at UTHM).
        course('TD-UTHM-SIVIL', 'Ijazah Sarjana Muda Kejuruteraan Awam', cls.uthm)
        # Review round (FIX-FIRST): a university whose every name word is generic, three pairs whose
        # names nest inside each other, and a place that holds only the DIPLOMA of a programme.
        course('TD-UKM-ASASI', 'Asasi Sains', inst('td-ukm', UKM, 'UKM'))
        for iid, name, acr in (('td-utm', UTM, 'UTM'), ('td-uitm', UITM, 'UiTM'),
                               ('td-usm', USM, 'USM'), ('td-usim', USIM, 'USIM')):
            course(f'TD-{acr.upper()}-DEG', 'Ijazah Sarjana Muda Pengurusan', inst(iid, name, acr))
        upnm = inst('td-upnm', UPNM, 'UPNM')
        c = Course.objects.create(course_id='TD-UPNM-DIP', course='Diploma Kejuruteraan Awam',
                                  level='Diploma', department='x', field='x', field_key=ft)
        CourseInstitution.objects.create(course=c, institution=upnm)

    def _app(self, course_id, course_name, pathway='university', **cp):
        return make_application(
            'profile_complete', chosen_pathway=pathway,
            chosen_programme={'course_id': course_id, 'course_name': course_name, **cp})

    def _offer(self, app, programme, institution, *, status='genuine'):
        return ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/td145',
            vision_fields={'fields': {'candidate_name': app.profile.name,
                                      'candidate_nric': app.profile.nric.replace('-', ''),
                                      'programme': programme, 'institution': institution},
                           'student_verdict': 'ok', 'warnings': [], 'error': '',
                           'authenticity': {'status': status, 'reason': 'x'}},
            vision_run_at=timezone.now())


class OneCampusAgreementTest(_Catalogue):
    """``institution_agreement`` rule 1, narrowed."""

    def test_the_pagoh_variant_still_matches(self):
        # #48: no distinctive token in common — the acronym is what makes it the same place.
        self.assertEqual(op.institution_agreement(
            'TD-UTHM-ANIM', '', 'UTHM - KAMPUS (CAWANGAN PAGOH)'), 'match')

    def test_a_different_named_university_clashes(self):
        # The owner's own example: picked a UMK course, the letter is UTHM's. The schools that
        # share UTHM's name tokens must not make the real university "ambiguous".
        self.assertEqual(op.institution_agreement('TD-UMK-SAINS', '', UTHM), 'clash')
        self.assertEqual(op.institution_agreement('TD-UMK-SAINS', '', UTHM.upper()), 'clash')

    def test_um_is_not_umk_either_way(self):
        # Acronyms are WHOLE tokens: 'um' never matches 'umk'.
        self.assertEqual(op.institution_agreement('TD-UMK-SAINS', '', UM), 'clash')
        self.assertEqual(op.institution_agreement('TD-UM-SAINS', '', 'UMK'), 'clash')

    def test_a_name_we_cannot_place_is_unknown_never_a_clash(self):
        # The Pagoh safety rule: an unreadable variant must not re-open the #48 false alarm.
        for letter in ('KAMPUS CAWANGAN XYZ', 'Pusat Pengajian Luar'):
            with self.subTest(letter=letter):
                self.assertEqual(op.institution_agreement('TD-UMK-SAINS', '', letter), 'unknown')

    def test_a_blank_letter_is_unknown(self):
        self.assertEqual(op.institution_agreement('TD-UMK-SAINS', '', ''), 'unknown')
        self.assertEqual(op.institution_agreement('TD-UMK-SAINS', '', '   '), 'unknown')


class ReviewRoundAgreementTest(_Catalogue):
    """The adversarial review's failing inputs (2026-10-04, FIX-FIRST)."""

    def test_a_ukm_letter_with_an_address_tail_never_clashes(self):
        # Every word of UKM's name is generic, so a SHARED-WORD search once found one seeded row
        # ("KM Selangor") and called it a clash. Only an exact name or a whole acronym counts now.
        for letter in ('UNIVERSITI KEBANGSAAN MALAYSIA, BANGI, SELANGOR',
                       'UNIVERSITI KEBANGSAAN MALAYSIA, MACHANG',
                       'UNIVERSITI KEBANGSAAN MALAYSIA KAMPUS SKUDAI'):
            with self.subTest(letter=letter):
                self.assertEqual(op.institution_agreement('TD-UKM-ASASI', '', letter), 'unknown')
        self.assertEqual(op.institution_agreement('TD-UKM-ASASI', '', 'UKM, BANGI'), 'match')

    def test_a_name_inside_another_name_is_still_a_different_university(self):
        # UTM's words sit inside UiTM's (and USM's inside USIM's), so the campus test alone read
        # 'match'. The letter EXACTLY naming another catalogue row is a clash — both ways.
        for course_id, letter in (('TD-UTM-DEG', UITM), ('TD-UITM-DEG', UTM),
                                  ('TD-USM-DEG', USIM), ('TD-USIM-DEG', USM)):
            with self.subTest(course=course_id, letter=letter):
                self.assertEqual(op.institution_agreement(course_id, '', letter.upper()), 'clash')
        for course_id, letter in (('TD-UTM-DEG', UTM), ('TD-UITM-DEG', UITM),
                                  ('TD-USM-DEG', USM), ('TD-USIM-DEG', USIM)):
            with self.subTest(own=course_id):
                self.assertEqual(op.institution_agreement(course_id, '', letter.upper()), 'match')

    def test_the_lookup_is_filtered_not_a_table_scan(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            op._names_another_institution(UMK, 'UMK', UTHM)
        sql = ' '.join(q['sql'] for q in ctx.captured_queries)
        self.assertEqual(len(ctx.captured_queries), 1)
        self.assertIn('WHERE', sql.upper())


class WrongUniversityVerdictTest(_Catalogue):
    """The clash reaches the existing plumbing: a red Pathway chip and the one-tap query."""

    def _pathway(self, app):
        return next(f for f in build_verdict(app) if f['fact'] == 'pathway')

    def test_umk_pick_with_a_uthm_offer_raises_pathway_confirm_then_settles(self):
        # Same programme name, so the PROGRAMME axis cannot decide it (UTHM has no such course →
        # 'unknown'): the mismatch below is the institution axis alone.
        app = self._app('TD-UMK-SAINS', 'Ijazah Sarjana Muda Perniagaan Tani')
        offer = self._offer(app, 'IJAZAH SARJANA MUDA PERNIAGAAN TANI', UTHM.upper())
        self.assertEqual(op.programme_agreement('TD-UMK-SAINS', 'IJAZAH SARJANA MUDA PERNIAGAAN TANI',
                                                UTHM.upper()), 'unknown')
        self.assertEqual(student_offer_check(offer)['pathway'], 'mismatch')   # the red chip
        item = next((it for it in self._pathway(app)['unresolved']
                     if it['code'] == 'pathway_confirm'), None)
        self.assertIsNotNone(item, 'a different university must ask the student')
        # "You told us X" names what the student PICKED — the catalogue's campus, not a blank.
        self.assertEqual(item['params']['declared_institution'], UMK)
        self.assertEqual(item['params']['institution'], UTHM.upper())

        self.assertTrue(confirm_pathway(app))                                 # the student's Yes
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'], UTHM.upper())
        self.assertNotIn('course_id', app.chosen_programme)    # UMK's id did not survive
        self.assertFalse(any(it['code'] == 'pathway_confirm'
                             for it in self._pathway(app)['unresolved']))

    def test_the_pagoh_offer_on_a_uthm_pick_asks_nothing(self):
        app = self._app('TD-UTHM-ANIM', 'Ijazah Sarjana Muda Teknologi Animasi')
        offer = self._offer(app, 'IJAZAH SARJANA MUDA TEKNOLOGI ANIMASI',
                            'UTHM - KAMPUS (CAWANGAN PAGOH)')
        self.assertEqual(student_offer_check(offer)['pathway'], 'match')
        self.assertFalse(any(it['code'] == 'pathway_confirm'
                             for it in self._pathway(app)['unresolved']))

    def test_the_engine_version_moved(self):
        self.assertEqual(VERDICT_ENGINE_VERSION, '2026-10-04.1')


class ConfirmDropsStaleCourseIdTest(_Catalogue):
    def test_no_unique_course_at_the_new_place_drops_the_id_and_logs_ids_only(self):
        app = self._app('TD-UMK-SAINS', 'Ijazah Sarjana Muda Perniagaan Tani')
        offer = self._offer(app, 'IJAZAH SARJANA MUDA SENI BINA', UTHM.upper())
        with self.assertLogs('apps.scholarship.services', 'WARNING') as logs:
            self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertNotIn('course_id', app.chosen_programme)
        self.assertEqual(app.chosen_programme['institution'], UTHM.upper())
        line = next(m for m in logs.output if 'stale course_id' in m)
        self.assertIn(f'doc {offer.id}', line)
        self.assertIn(f'application {app.id}', line)
        self.assertNotIn(app.profile.name, line)

    def test_the_sponsor_card_follows_the_confirm(self):
        from apps.scholarship.card_display import course_href, programme_split
        app = self._app('TD-UMK-SAINS', 'Ijazah Sarjana Muda Perniagaan Tani')
        self._offer(app, 'IJAZAH SARJANA MUDA SENI BINA', UTHM.upper())
        confirm_pathway(app)
        app.refresh_from_db()
        self.assertEqual(programme_split(app)['title'], 'Ijazah Sarjana Muda Seni Bina')
        self.assertNotEqual(course_href(app), '/course/TD-UMK-SAINS')

    def test_a_unique_course_at_the_new_place_is_re_pinned(self):
        app = self._app('TD-UMK-SAINS', 'Ijazah Sarjana Muda Perniagaan Tani')
        self._offer(app, 'IJAZAH SARJANA MUDA KEJURUTERAAN AWAM', UTHM.upper())
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'TD-UTHM-SIVIL')
        self.assertEqual(app.chosen_programme['institution'], UTHM)    # catalogue spelling

    def test_a_sains_degree_is_never_re_pinned_to_a_pre_u_course(self):
        # Found while building this: 'IJAZAH SARJANA MUDA SAINS GUNAAN' at UTHM "resolves" to stpm-sains
        # at SMK Bandar Tun Hussein Onn 2 (token overlap). A tertiary confirm must drop instead.
        app = self._app('TD-UMK-SAINS', 'Ijazah Sarjana Muda Perniagaan Tani')
        self._offer(app, 'IJAZAH SARJANA MUDA SAINS GUNAAN', UTHM.upper())
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertNotIn('course_id', app.chosen_programme)

    def test_a_degree_letter_never_re_pins_to_a_diploma(self):
        # UPNM holds only the DIPLOMA of this programme: the resolver finds it, the level differs.
        self.assertEqual(op.resolve_catalogue_course('IJAZAH SARJANA MUDA KEJURUTERAAN AWAM',
                                                     UPNM.upper())['course_id'], 'TD-UPNM-DIP')
        app = self._app('TD-UMK-SAINS', 'Ijazah Sarjana Muda Perniagaan Tani')
        self._offer(app, 'IJAZAH SARJANA MUDA KEJURUTERAAN AWAM', UPNM.upper())
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertNotIn('course_id', app.chosen_programme)

    def test_a_pre_u_id_is_stale_after_a_tertiary_confirm(self):
        # Declared STPM (stpm-sains); confirms a UTHM degree. Left in place, the catalogue alignment
        # would pick one of stpm-sains's schools ("…Bandar Tun Hussein Onn 2") as the institution.
        app = self._app('stpm-sains', 'Tingkatan Enam', pathway='stpm')
        self._offer(app, 'IJAZAH SARJANA MUDA TEKNOLOGI ANIMASI', UTHM.upper())
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'degree')
        self.assertIn(app.chosen_programme.get('course_id'), (None, 'TD-UTHM-ANIM'))
        self.assertNotIn('sekolah', app.chosen_programme['institution'].lower())
        self.assertIn('hussein', app.chosen_programme['institution'].lower())

    def test_a_place_the_verdict_cannot_read_keeps_its_course_id(self):
        # The confirm asks the verdict's own question: 'unknown' is not a different place.
        app = self._app('TD-UKM-ASASI', 'Asasi Sains', pathway='asasi')
        self._offer(app, 'ASASI SAINS', 'UNIVERSITI KEBANGSAAN MALAYSIA, 43600 BANGI')
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'TD-UKM-ASASI')

    def _poly_pick(self):
        # A course taught at TWO polytechnics: with nothing recorded, the verdict reads 'unknown'.
        pkb = Institution.objects.create(institution_id='td-pkb', institution_name='Politeknik Kota Bharu',
                                         acronym='PKB', type='Politeknik', state='Kelantan')
        pm = Institution.objects.create(institution_id='td-pm', institution_name='Politeknik Mersing',
                                        acronym='PMS', type='Politeknik', state='Johor')
        c = Course.objects.create(course_id='TD-POLY-AWAM', course='Diploma Kejuruteraan Awam',
                                  level='Diploma', department='x', field='x',
                                  field_key=FieldTaxonomy.objects.get(key='td145w'))
        for campus in (pkb, pm):
            CourseInstitution.objects.create(course=c, institution=campus)
        return self._app('TD-POLY-AWAM', 'Diploma Kejuruteraan Awam', pathway='poly')

    def test_a_multi_campus_pick_confirmed_elsewhere_drops_its_course_id(self):
        # Second review: a poly diploma pick, a UTHM letter → the poly id must not stay beside UTHM.
        app = self._poly_pick()
        self._offer(app, 'DIPLOMA KEJURUTERAAN AWAM', UTHM.upper())
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertNotIn('course_id', app.chosen_programme)

    def test_a_multi_campus_pick_confirmed_at_its_other_campus_keeps_its_course_id(self):
        app = self._poly_pick()
        self._offer(app, 'DIPLOMA KEJURUTERAAN AWAM', 'POLITEKNIK MERSING')
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'TD-POLY-AWAM')

    def test_a_same_place_confirm_keeps_its_course_id(self):
        # The Pagoh variant IS the catalogue campus: nothing stale to drop.
        app = self._app('TD-UTHM-ANIM', 'Ijazah Sarjana Muda Teknologi Animasi')
        self._offer(app, 'IJAZAH SARJANA MUDA TEKNOLOGI ANIMASI', 'UTHM - KAMPUS (CAWANGAN PAGOH)')
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'TD-UTHM-ANIM')


# #31's letter, as far as the ruling quotes it: a UM PEMAKLUMAN on its open channel, which says the
# official offer via SATU follows only after the UPU appeal results.
SATU_31_TEXT = """UNIVERSITI MALAYA
PEMAKLUMAN KEMASUKAN KE UNIVERSITI MALAYA [SALURAN TERBUKA UNIVERSITI MALAYA (SATU)]
Program : Ijazah Sarjana Muda Sains
Surat tawaran rasmi melalui SATU hanya akan dikeluarkan selepas keputusan rayuan UPU.
Pengarah Eksekutif, Jabatan Pemasaran dan Pengambilan, Universiti Malaya
"""

GENUINE_UA_TEXT = """UNIVERSITI MALAYA
PUSAT PENGURUSAN AKADEMIK
TAWARAN KEMASUKAN PROGRAM ASASI SAINS SOSIAL
Program Pengajian : Asasi Sains Sosial
Tarikh Pendaftaran : 5 Julai 2026
Pertukaran program adalah tidak dibenarkan.
"""


class SaluranTerbukaVetoTest(TestCase):
    def test_31s_saluran_terbuka_letter_reads_not_offer_letter(self):
        g = signature_genuineness(SATU_31_TEXT, doc_type='offer_letter')
        self.assertEqual(g['status'], 'not_offer_letter')
        self.assertIn('Saluran Terbuka (SATU)', g['reason'])
        self.assertEqual(g['model_version'], '1.7.0')
        self.assertEqual(MODEL_VERSION, '1.7.0')

    def test_saluran_satu_is_vetoed_too(self):
        g = signature_genuineness(GENUINE_UA_TEXT + '\nMelalui Saluran Satu UM',
                                  doc_type='offer_letter')
        self.assertEqual(g['status'], 'not_offer_letter')

    def test_the_lone_word_satu_is_not_a_tell(self):
        # Malay "one" — on ordinary letters ("Semester Satu"); it must never veto.
        g = signature_genuineness(GENUINE_UA_TEXT + '\nPendaftaran Semester Satu',
                                  doc_type='offer_letter')
        self.assertEqual(g['status'], 'genuine')

    def test_the_reporting_bonus_cannot_lift_it_back(self):
        # Gate 3b reads the scorer's own list, so the new tell blocks the +1 date bonus too.
        app = make_application('profile_complete')
        offer = ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/satu',
            vision_fields={'fields': {'reporting_date': '6 Jul 2026', 'reporting_date_label': 'Tarikh',
                                      'institution': UM,
                                      'issuer': 'Saluran Terbuka Universiti Malaya (SATU)'},
                           'authenticity': {'status': 'genuine', 'doc_seen': 'ua_offer',
                                            'present': ['public university (UA) name']},
                           'student_verdict': 'ok', 'warnings': [], 'error': ''},
            vision_run_at=timezone.now())
        self.assertFalse(offer_reporting_bonus(offer))
