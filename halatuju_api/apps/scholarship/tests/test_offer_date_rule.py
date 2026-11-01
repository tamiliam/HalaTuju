"""Two owner items of 2026-11-01 on the offer realignment.

1. **The date rule.** The scholarship picker was complete only from ``PICKER_COMPLETE_AT`` (MARA
   under MARA went live 2026-10-31 13:10 MYT). A pick made before it was made on an incomplete list,
   so the student's own genuine offer replaces it for ANY catalogue course, not only a
   Bumiputera-only one. No per-pick timestamp exists: an OLD pick is one submitted before the cut-off
   whose profile has not been saved since; a profile saved since is skipped (``may_have_repicked``).
2. **#168's false Institution tick.** Politeknik Kota Kinabalu (a campus of the picked poly course)
   was "referred to" by the hostel line "Kolej Kediaman Tun Pengiran Ahmad Raffae, UMS Kota
   Kinabalu" through its town words, so the Institution field ticked against a UMS letter. One
   campus test now (``offer_course_match.CampusReader``): a name or a unique acronym first; a line
   naming ANOTHER institution outright never names this one; words only when the campus's own words
   include one no other row carries — never a town.
"""
from datetime import timedelta

from django.test import TestCase

from apps.courses.models import (
    Course, CourseInstitution, CourseRequirement, FieldTaxonomy, Institution, StpmCourse, StpmRequirement)
from apps.courses.models import StudentProfile
from apps.scholarship import offer_pathway as op
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.offer_course_match import CampusReader, letter_place
from apps.scholarship.pathway_engine import student_offer_check
from apps.scholarship.services.offer_sync import (
    PICKER_COMPLETE_AT, plan_bumi_realign, realign_basis, realign_bumi_only_pick)
from apps.scholarship.tests.factories import make_application, make_student
from apps.scholarship.tests.test_offer_course_match import seed_realign_catalogue
from apps.scholarship.tests.test_offer_realign import _offer

#: #168's own strings (programme and issuer as the letter prints them).
LETTER_168 = ('Ijazah Sarjana Muda Kejuruteraan Mekanikal Dengan Kepujian',
              'Kolej Kediaman Tun Pengiran Ahmad Raffae, UMS Kota Kinabalu', 'Universiti Malaysia Sabah')
PICK_168 = {'course_id': 'POLY-DIP-019', 'course_name': 'Diploma Kejuruteraan Mekanikal',
            'institution': 'Politeknik Kota Kinabalu'}
BEFORE = PICKER_COMPLETE_AT - timedelta(days=5)


def seed_168():
    """#168's catalogue: the UMS degree, and a poly diploma at polytechnics in towns that host a
    university (Kota Kinabalu, Kuching, Kuantan, Arau, Batu Pahat — the last three counterfactual
    names), plus the other rows that carry those towns' words, as the live catalogue does."""
    seed_realign_catalogue()
    ft = FieldTaxonomy.objects.get(key='realign')
    ums = Institution.objects.get(institution_id='RA-UMS')
    sc = StpmCourse.objects.create(course_id='UH6521001', field_key=ft, institution=ums,
                                   course_name='Ijazah Sarjana Muda Kejuruteraan Mekanikal dengan Kepujian',
                                   university='Universiti Malaysia Sabah')
    StpmRequirement.objects.create(course=sc, req_bumiputera=False)
    poly = Course.objects.create(course_id='POLY-DIP-019', course='Diploma Kejuruteraan Mekanikal',
                                 level='Diploma', department='x', field='x', field_key=ft)
    CourseRequirement.objects.create(course=poly, source_type='poly')
    for iid, name, acr in (('RA-PKK', 'Politeknik Kota Kinabalu', 'PKK'),
                           ('RA-PKS', 'Politeknik Kuching Sarawak', 'PKS'),
                           ('RA-PKN', 'Politeknik Kuantan', 'PKN'),                 # counterfactual
                           ('RA-PAR', 'Politeknik Arau', 'PAR'),                    # counterfactual
                           ('RA-PBP', 'Politeknik Batu Pahat', 'PBP'),              # counterfactual
                           ('RA-PTSS', 'Politeknik Tuanku Syed Sirajuddin', 'PTSS')):
        i = Institution.objects.create(institution_id=iid, institution_name=name, acronym=acr,
                                       type='Politeknik', state='Sabah')
        CourseInstitution.objects.create(course=poly, institution=i)
    for iid, name, acr in (('RA-GMKK', 'GIATMARA Kota Kinabalu', 'GIATMARA'),
                           ('RA-IKMKK', 'Institut Kemahiran MARA Kota Kinabalu', 'IKM'),
                           ('RA-KKBP', 'Kolej Komuniti Batu Pahat', 'KKBP'),
                           ('RA-KKKN', 'Kolej Kemahiran Tinggi MARA Kuantan', 'KKTM'),
                           ('RA-UNIMAS2', 'Universiti Malaysia Sarawak Kuching', 'UNIMASK'),
                           ('RA-UMPSA', 'Universiti Malaysia Pahang Al-Sultan Abdullah', 'UMPSA')):
        Institution.objects.create(institution_id=iid, institution_name=name, acronym=acr, type='x', state='x')


class TheFalseTick168Test(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_168()

    def test_the_cause_town_words_named_the_poly(self):
        # Proven on the old rule's own terms: Politeknik Kota Kinabalu's distinctive words sit inside
        # the hostel line. The shared reader refuses them: the line names UMS outright, and "Kota
        # Kinabalu" is also two other rows' words.
        from apps.scholarship.pathway_engine import distinctive_tokens
        self.assertLessEqual(distinctive_tokens('Politeknik Kota Kinabalu'), distinctive_tokens(LETTER_168[1]))
        self.assertFalse(CampusReader(LETTER_168[1]).names('Politeknik Kota Kinabalu', 'PKK'))

    def test_168_institution_reads_unknown_never_match(self):
        self.assertNotEqual(op.institution_agreement('POLY-DIP-019', 'Politeknik Kota Kinabalu',
                                                     LETTER_168[1], LETTER_168[2]), 'match')

    def test_168_the_letter_place_is_never_the_poly(self):
        self.assertTrue(op.offer_contradicts_course_institution('POLY-DIP-019', LETTER_168[1], LETTER_168[2]))
        self.assertNotIn(letter_place('POLY-DIP-019', LETTER_168[1], LETTER_168[2]), ('Politeknik Kota Kinabalu',))

    def test_168_the_served_tick_field(self):
        app = make_application('profile_complete', chosen_pathway='poly', chosen_programme=dict(PICK_168))
        chk = student_offer_check(_offer(app, LETTER_168))
        self.assertNotEqual(chk['chosen_institution_status'], 'match')    # what the web tick reads

    def test_a_town_hosting_a_university_never_names_its_poly(self):
        for line, poly in (('KOLEJ KEDIAMAN, UMS KOTA KINABALU', 'Politeknik Kota Kinabalu'),
                           ('Kolej Kediaman, Universiti Malaysia Sarawak, Kuching', 'Politeknik Kuching Sarawak'),
                           ('UMPSA, KUANTAN', 'Politeknik Kuantan'),
                           ('UniMAP, ARAU', 'Politeknik Arau'),
                           ('KOLEJ KEDIAMAN PERWIRA, UTHM BATU PAHAT', 'Politeknik Batu Pahat'),
                           ('KOLEJ KEDIAMAN, KOTA KINABALU', 'Politeknik Kota Kinabalu'),   # town only
                           ('ASRAMA BATU PAHAT', 'Politeknik Batu Pahat')):                # town only
            with self.subTest(line=line):
                self.assertFalse(CampusReader(line).names(poly, ''))

    def test_a_line_naming_a_university_outright_never_names_a_poly_by_words(self):
        # A hostel named after the same person as the polytechnic: every one of the poly's own words
        # (one of them its alone) sits in the line, but the line names UniMAP outright.
        self.assertFalse(CampusReader('KOLEJ KEDIAMAN TUANKU SYED SIRAJUDDIN, UniMAP').names(
            'Politeknik Tuanku Syed Sirajuddin', 'PTSS'))

    def test_a_poly_is_still_named_by_its_name_its_acronym_or_its_own_words(self):
        self.assertTrue(CampusReader('POLITEKNIK KOTA KINABALU').names('Politeknik Kota Kinabalu', 'PKK'))
        self.assertTrue(CampusReader('PKK, SABAH').names('Politeknik Kota Kinabalu', 'PKK'))
        # Its own words, one of them no other row's ("Sirajuddin"), with no institution named outright.
        self.assertTrue(CampusReader('TUANKU SYED SIRAJUDDIN POLYTECHNIC, ARAU').names(
            'Politeknik Tuanku Syed Sirajuddin', 'PTSS'))
        self.assertEqual(op.institution_agreement('POLY-DIP-019', 'Politeknik Kota Kinabalu',
                                                  'POLITEKNIK KOTA KINABALU'), 'match')


class TheDateRuleTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_168()

    def _old(self, app, profile_saved=BEFORE):
        ScholarshipApplication.objects.filter(id=app.id).update(submitted_at=BEFORE)
        StudentProfile.objects.filter(pk=app.profile_id).update(updated_at=profile_saved)
        app.refresh_from_db()
        app.profile.refresh_from_db()
        return app

    def _app(self, **over):
        over.setdefault('chosen_pathway', 'poly')
        over.setdefault('chosen_programme', dict(PICK_168))
        return make_application('profile_complete', student=make_student(), pathway_certainty='sure', **over)

    def test_168_an_old_pick_gives_way_to_its_genuine_offer(self):
        app = self._old(self._app())
        offer = _offer(app, LETTER_168)
        self.assertEqual(realign_basis(app, 'UH6521001'), 'old_pick')
        self.assertTrue(realign_bumi_only_pick(app, offer, student_offer_check(offer)))
        app.refresh_from_db()
        self.assertEqual((app.chosen_programme['course_id'], app.chosen_programme['institution'],
                          app.chosen_pathway), ('UH6521001', 'Universiti Malaysia Sabah', 'university'))

    def test_a_pick_submitted_since_the_cut_off_is_a_real_choice(self):
        app = self._app()
        offer = _offer(app, LETTER_168)
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'new_pick')

    def test_a_profile_saved_since_the_cut_off_may_hold_a_new_pick(self):
        app = self._old(self._app(), profile_saved=PICKER_COMPLETE_AT + timedelta(hours=1))
        offer = _offer(app, LETTER_168)
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'may_have_repicked')

    def test_the_cut_off_is_exclusive_on_both_stamps(self):
        app = self._old(self._app())
        ScholarshipApplication.objects.filter(id=app.id).update(submitted_at=PICKER_COMPLETE_AT)
        app.refresh_from_db()
        self.assertEqual(realign_basis(app, 'UH6521001'), 'new_pick')

    def test_every_other_guard_still_holds_for_an_old_pick(self):
        cases = ((dict(chosen_programme={**PICK_168, 'source': 'offer_letter_confirmed'}), {}, 'confirmed_source'),
                 (dict(chosen_pathway='stpm'), {}, 'pre_u'),
                 (dict(status='interviewed'), {}, 'decided'),
                 ({}, dict(status='suspect'), 'not_genuine'),
                 ({}, dict(nric='990101-01-9999'), 'not_own_letter'))
        for over, letter_over, reason in cases:
            with self.subTest(reason=reason):
                app = self._old(self._app(**over))
                offer = _offer(app, LETTER_168, **letter_over)
                self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], reason)

    def test_the_realign_does_not_move_the_profile_stamp(self):
        # The realign's own profile refresh writes named fields only, so it never makes its own
        # record read "may have re-picked" on a re-run.
        app = self._old(self._app())
        offer = _offer(app, LETTER_168)
        realign_bumi_only_pick(app, offer, student_offer_check(offer))
        self.assertLess(StudentProfile.objects.get(pk=app.profile_id).updated_at, PICKER_COMPLETE_AT)

    def test_the_command_prints_the_basis(self):
        from io import StringIO
        from django.core.management import call_command
        app = self._old(self._app())
        _offer(app, LETTER_168)
        out = StringIO()
        call_command('realign_bumi_offers', stdout=out)
        self.assertIn(f'#{app.id} [profile_complete] REALIGN old_pick (would): POLY-DIP-019', out.getvalue())


class Round3CampusTest(TestCase):
    """Round-3 review (2026-11-01): a whole-table "word nobody else has" rule lost true matches and let
    a new school row flip a tick. The campus test is now judged against the course's own campus only;
    the reviewer's four strings read match, #168 stays unknown, a school row changes nothing."""

    @classmethod
    def setUpTestData(cls):
        seed_168()
        ft = FieldTaxonomy.objects.get(key='realign')
        poly = Course.objects.get(course_id='POLY-DIP-019')
        for iid, name, acr in (('RA-POLISAS', 'Politeknik Sultan Haji Ahmad Shah', 'POLISAS'),
                               ('RA-PSAS', 'Politeknik Sultan Azlan Shah', 'PSAS')):
            CourseInstitution.objects.create(course=poly, institution=Institution.objects.create(
                institution_id=iid, institution_name=name, acronym=acr, type='Politeknik', state='Pahang'))
        umpsa = Institution.objects.get(institution_id='RA-UMPSA')
        sc = StpmCourse.objects.create(course_id='UJ6481004', field_key=ft, institution=umpsa,
                                       course_name='Sarjana Muda Sains Komputer (Keselamatan Siber) dengan Kepujian',
                                       university='Universiti Malaysia Pahang Al-Sultan Abdullah')
        StpmRequirement.objects.create(course=sc)
        Institution.objects.create(institution_id='RA-SMK-THO', institution_name='SMK Bandar Tun Hussein Onn 2',
                                   type='Sekolah Menengah', state='Johor')

    def test_the_reviewers_four_strings_read_match(self):
        self.assertEqual(op.institution_agreement('UB6523001', '', 'UNIVERSITI TUN HUSSEIN ONN'), 'match')
        self.assertEqual(op.institution_agreement('UJ6481004', '', 'UNIVERSITI MALAYSIA PAHANG'), 'match')
        self.assertEqual(op.institution_agreement('RA-POLY-DPM', '', 'POLITEKNIK PREMIER UNGKU OMAR'), 'match')
        self.assertTrue(CampusReader('POLITEKNIK SULTAN HJ AHMAD SHAH').names('Politeknik Sultan Haji Ahmad Shah',
                                                                             'POLISAS'))
        for cid, line in (('UB6523001', 'UNIVERSITI TUN HUSSEIN ONN'), ('UJ6481004', 'UNIVERSITI MALAYSIA PAHANG'),
                          ('RA-POLY-DPM', 'POLITEKNIK PREMIER UNGKU OMAR'),
                          ('POLY-DIP-019', 'POLITEKNIK SULTAN HJ AHMAD SHAH')):
            with self.subTest(line=line):
                self.assertFalse(op.offer_contradicts_course_institution(cid, line))

    def test_the_former_name_alias(self):
        self.assertEqual(op.institution_agreement('UJ6481004', '', 'UMP, GAMBANG'), 'match')

    def test_168_stays_unknown(self):
        self.assertNotEqual(op.institution_agreement('POLY-DIP-019', 'Politeknik Kota Kinabalu',
                                                     LETTER_168[1], LETTER_168[2]), 'match')

    def test_a_new_school_row_changes_nothing(self):
        line = 'POLITEKNIK PREMIER SULTAN AZLAN SHAH'
        before = (CampusReader(line).names('Politeknik Sultan Azlan Shah', 'PSAS'),
                  op.offer_contradicts_course_institution('POLY-DIP-019', line))
        Institution.objects.create(institution_id='RA-SMK-SAS', institution_name='SMK Sultan Azlan Shah',
                                   type='Sekolah Menengah', state='Perak')
        after = (CampusReader(line).names('Politeknik Sultan Azlan Shah', 'PSAS'),
                 op.offer_contradicts_course_institution('POLY-DIP-019', line))
        self.assertEqual(before, (True, False))
        self.assertEqual(after, before)

    def test_one_read_of_the_institution_table_per_check(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as q:
            op.institution_agreement('POLY-DIP-019', 'Politeknik Kota Kinabalu', LETTER_168[1], LETTER_168[2])
        full = [x for x in q.captured_queries if '"institutions"' in x['sql'] and 'WHERE' not in x['sql']]
        self.assertEqual(len(full), 1)


class Round3RealignLevelTest(TestCase):
    """Round-3 review: the date-rule realign uses the link's own test — no pre-U virtual course, a
    level the letter STATES, one campus."""

    @classmethod
    def setUpTestData(cls):
        seed_168()
        ft = FieldTaxonomy.objects.get(key='realign')
        smk = Institution.objects.create(institution_id='RA-SMK-DO', institution_name='SMK Dato Omar',
                                         type='Sekolah Menengah', state='Kedah')
        stpm, _ = Course.objects.get_or_create(course_id='stpm-sains', defaults={
            'course': 'STPM Sains', 'level': 'Pra-U', 'department': 'x', 'field': 'x', 'field_key': ft})
        CourseInstitution.objects.get_or_create(course=stpm, institution=smk)
        ums = Institution.objects.get(institution_id='RA-UMS')
        for cid, name in (('RA-UMS-DSS', 'Diploma Sains Sukan'), ('RA-UMS-DPS', 'Diploma Pengurusan Sukan')):
            dip = Course.objects.create(course_id=cid, course=name, level='Diploma', department='x', field='x',
                                        field_key=ft)
            CourseInstitution.objects.create(course=dip, institution=ums)
            CourseRequirement.objects.create(course=dip, source_type='ua')

    def _old_app(self):
        app = make_application('profile_complete', student=make_student(), pathway_certainty='sure',
                               chosen_pathway='poly', chosen_programme=dict(PICK_168))
        ScholarshipApplication.objects.filter(id=app.id).update(submitted_at=BEFORE)
        StudentProfile.objects.filter(pk=app.profile_id).update(updated_at=BEFORE)
        app.refresh_from_db()
        app.profile.refresh_from_db()
        return app

    def test_a_school_letter_never_realigns_to_a_pre_u_virtual_course(self):
        app = self._old_app()
        offer = _offer(app, ('SAINS', 'SMK DATO OMAR', ''))
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'unresolved')
        # The shared test refuses the virtual course itself, even when the letter's level is its own.
        from apps.scholarship.offer_course_match import pinned_match
        self.assertEqual(pinned_match('STPM SAINS', 'SMK DATO OMAR'), ('unresolved', None))

    def test_a_letter_with_no_level_word_never_realigns(self):
        app = self._old_app()
        offer = _offer(app, ('SAINS SUKAN', 'Universiti Malaysia Sabah', 'Universiti Malaysia Sabah'))
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'unresolved')
        # The same shape with no other course to blur it: still no level word, still no realign.
        offer = _offer(app, ('PENGURUSAN SUKAN', 'Universiti Malaysia Sabah', 'Universiti Malaysia Sabah'))
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'unresolved')
        self.assertFalse(realign_bumi_only_pick(app, offer, student_offer_check(offer)))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'POLY-DIP-019')


class Round4LevelAndTypeWordsTest(TestCase):
    """Round-4 review (2026-11-01): the level is EXACT (the course's own level field), and a line of
    shared type words names no campus."""

    @classmethod
    def setUpTestData(cls):
        seed_168()
        ft = FieldTaxonomy.objects.get(key='realign')

        def inst(iid, name, acr, typ='x'):
            return Institution.objects.create(institution_id=iid, institution_name=name, acronym=acr, type=typ,
                                              state='x')

        def course(cid, name, level, *campuses, st='poly'):
            c = Course.objects.create(course_id=cid, course=name, level=level, department='x', field='x',
                                      field_key=ft)
            for campus in campuses:
                CourseInstitution.objects.create(course=c, institution=campus)
            CourseRequirement.objects.create(course=c, source_type=st)

        mukah = inst('RA-PMU', 'Politeknik Mukah Sarawak', 'PMU')
        course('RA-SIJIL-MEK', 'Sijil Kejuruteraan Mekanikal', 'Sijil', mukah)
        ikbn = inst('RA-IKBN-MIRI', 'Institut Kemahiran Belia Negara Miri', 'IKBN')
        inst('RA-IKBN-X', 'Institut Kemahiran Belia Negara Dusun Tua', 'IKBN')
        course('IKBN-CET-015', 'Sijil Lanjutan Teknologi Hospitaliti (Penyediaan Pastri)', 'Sijil Lanjutan', ikbn,
               st='tvet')
        course('RA-SIJIL-KUL', 'Sijil Kulinari', 'Sijil', ikbn, st='tvet')
        kangar = Institution.objects.get(institution_id='RA-KK-KANGAR')
        course('RA-KK-SOLO', 'Diploma Kulinari', 'Diploma', kangar, st='kkom')
        inst('RA-IPG-IPOH', 'Institut Pendidikan Guru Kampus Ipoh', '')
        inst('RA-IPG-KB', 'Institut Pendidikan Guru Kampus Kota Bharu', '')
        inst('RA-MET-JB', 'Politeknik METrO Johor Bahru', 'PMJB')
        inst('RA-MET-KL', 'Politeknik METrO Kuala Lumpur', 'PMKL')

    # ── 1. the exact level ────────────────────────────────────────────────────────────────────
    def test_a_certificate_letter_never_pins_the_diploma(self):
        from apps.scholarship.offer_course_match import pinned_match
        self.assertEqual(pinned_match('SIJIL KEJURUTERAAN MEKANIKAL', 'POLITEKNIK KOTA KINABALU'),
                         ('unresolved', None))
        self.assertEqual(pinned_match('DIPLOMA LANJUTAN KEJURUTERAAN MEKANIKAL', 'POLITEKNIK KOTA KINABALU'),
                         ('unresolved', None))
        reason, match = pinned_match('DIPLOMA KEJURUTERAAN MEKANIKAL', 'POLITEKNIK KOTA KINABALU')
        self.assertEqual((reason, match['course_id']), ('', 'POLY-DIP-019'))

    def test_a_sijil_lanjutan_pins_only_its_own_level(self):
        from apps.scholarship.offer_course_match import letter_level, pinned_match
        self.assertEqual(letter_level('SIJIL LANJUTAN TEKNOLOGI HOSPITALITI (PENYEDIAAN PASTRI)'), 'sijil lanjutan')
        reason, match = pinned_match('SIJIL LANJUTAN TEKNOLOGI HOSPITALITI (PENYEDIAAN PASTRI)',
                                     'INSTITUT KEMAHIRAN BELIA NEGARA MIRI')
        self.assertEqual((reason, match['course_id']), ('', 'IKBN-CET-015'))
        self.assertEqual(pinned_match('SIJIL TEKNOLOGI HOSPITALITI (PENYEDIAAN PASTRI)',
                                      'INSTITUT KEMAHIRAN BELIA NEGARA MIRI'), ('unresolved', None))
        # A Sijil Lanjutan letter where the campus holds only the Sijil: another level, so no pin.
        self.assertEqual(pinned_match('SIJIL LANJUTAN KULINARI', 'INSTITUT KEMAHIRAN BELIA NEGARA MIRI'),
                         ('unresolved', None))
        # #228's own line: "IKBN" is shared by every IKBN and "Miri" is a town, so it names no campus.
        self.assertEqual(pinned_match('SIJIL LANJUTAN TEKNOLOGI HOSPITALITI (PENYEDIAAN PASTRI)', 'IKBN MIRI')[0],
                         'unresolved')

    # ── 2. type words ─────────────────────────────────────────────────────────────────────────
    def test_a_line_of_type_words_names_no_campus(self):
        for line, campus in (('KOLEJ KOMUNITI', 'Kolej Komuniti Arau'),
                             ('JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI', 'Kolej Komuniti Kangar'),
                             ('INSTITUT PENDIDIKAN GURU', 'Institut Pendidikan Guru Kampus Ipoh'),
                             ('POLITEKNIK METRO KL', 'Politeknik METrO Johor Bahru')):
            with self.subTest(line=line):
                self.assertFalse(CampusReader(line).names(campus, ''))

    def test_the_ministry_letterhead_never_ticks_a_single_campus_kk_course(self):
        issuer = 'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI'
        self.assertEqual(letter_place('RA-KK-SOLO', '', issuer), '')
        self.assertEqual(op.institution_agreement('RA-KK-SOLO', '', '', issuer), 'unknown')
        self.assertEqual(op.institution_agreement('RA-KK-SOLO', '', 'KOLEJ KEDIAMAN', issuer), 'unknown')
        # The campus's own name still names it.
        self.assertEqual(op.institution_agreement('RA-KK-SOLO', '', 'KOLEJ KOMUNITI KANGAR'), 'match')
