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
