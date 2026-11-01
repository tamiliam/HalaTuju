"""An EMPTY pick is filled from the student's own offer letter (owner, 2026-11-01, #202).

Owner: *"That's not a decision at check 1. Its role is to get the facts as they are. The only
restrictions are imposed in the gift rules."* #202 held no course at all — ``chosen_programme`` was
``{}`` — while her genuine UNIMAS letter named one. Nothing filled it: the matcher could not read
degrees when she uploaded, the autofill stopped at a pathway "mismatch" made of her PAST pre-U college
("KM Labuan") against the letter's hostel, the realignment skipped her (profile saved after the
cut-off) and the link skipped her (no offer-sourced labels). An empty pick has nothing to protect, so
the letter's course is recorded — an intake year or the cut-off is never a reason to leave it out.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import FieldTaxonomy, Institution, StpmCourse, StpmRequirement
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.pathway_engine import student_offer_check
from apps.scholarship.services import autofill_pathway_from_offer
from apps.scholarship.services.offer_link import fill_empty_pick, plan_offer_link
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_offer_course_match import seed_realign_catalogue

#: #202's own letter.
LETTER_202 = {'programme': 'Sarjana Muda Sains Kimia dengan Kepujian - UW6442001',
              'institution': 'Kolej Allamanda', 'issuer': 'Universiti Malaysia Sarawak (UNIMAS)',
              'intake': 'Semester 1 Sesi 2023/2024'}
FILLED = {'course_id': 'UW6442001', 'course_name': 'Sarjana Muda Sains Kimia dengan Kepujian',
          'institution': 'Universiti Malaysia Sarawak', 'source': 'offer_letter_auto'}


def _offer(app, status='genuine', nric=None, **fields):
    prof = app.profile
    return ApplicantDocument.objects.create(
        application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x',
        vision_fields={'fields': {'candidate_name': prof.name,
                                  'candidate_nric': (nric or prof.nric).replace('-', ''),
                                  **LETTER_202, **fields},
                       'authenticity': {'status': status}, 'student_verdict': 'ok', 'warnings': [], 'error': ''},
        vision_run_at=timezone.now())


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()
        unimas = Institution.objects.get(institution_id='RA-UNIMAS')
        sc = StpmCourse.objects.create(course_id='UW6442001', course_name='Sarjana Muda Sains Kimia dengan Kepujian',
                                       university='Universiti Malaysia Sarawak', institution=unimas,
                                       field_key=FieldTaxonomy.objects.get(key='realign'))
        StpmRequirement.objects.create(course=sc)
        Institution.objects.create(institution_id='RA-KMLB', institution_name='Kolej Matrikulasi Labuan',
                                   acronym='KMLB', type='Kolej Matrikulasi', state='WP Labuan')

    def _app(self, stage='shortlisted', **over):
        over.setdefault('chosen_pathway', 'university')
        over.setdefault('chosen_programme', {})
        return make_application(stage, pre_u_track='perakaunan', pre_u_institution='KM Labuan',
                                pathway_certainty='uncertain', **over)


class Fill202Test(_Base):
    def test_202_the_autofill_records_the_letters_course(self):
        app = self._app()
        offer = _offer(app)
        self.assertEqual(student_offer_check(offer)['pathway'], 'mismatch')   # her past college vs a hostel
        with self.assertLogs('apps.scholarship.services', level='INFO') as logs:
            self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme, FILLED)
        self.assertEqual((app.chosen_pathway, app.pathway_certainty), ('university', 'sure'))
        self.assertTrue(any(f'AUDIT offer_course_link app_id={app.id} kind=fill course_id=UW6442001 '
                            'source=offer_letter_auto old_pick=- | - | - old_pathway=university' in x
                            for x in logs.output))
        # The verdict afterwards: the stored course is checked through the catalogue (the letterhead
        # names its campus), so her pre-U college no longer stands in for a declaration.
        self.assertEqual(student_offer_check(offer)['pathway'], 'match')

    def test_an_old_intake_is_a_fact_not_a_reason(self):
        app = self._app()
        self.assertEqual(plan_offer_link(app, _offer(app), student_offer_check(_offer(app)))[0], '')

    def test_a_blank_or_degree_pathway_takes_the_courses_and_a_picker_value_stays(self):
        # Round-6 review: ALWAYS the course's own pathway — a degree left on `poly` would be paid on the
        # polytechnic calendar (`contracts.pick_schedule_row`).
        for before, after in (('', 'university'), ('degree', 'university'), ('university', 'university'),
                              ('poly', 'university')):
            with self.subTest(before=before):
                app = self._app(chosen_pathway=before)
                offer = _offer(app)
                self.assertTrue(fill_empty_pick(app, offer, student_offer_check(offer)))
                app.refresh_from_db()
                self.assertEqual(app.chosen_pathway, after)

    def test_an_institution_label_with_no_course_is_still_an_empty_pick_and_the_audit_keeps_it(self):
        app = self._app(chosen_programme={'institution': 'Politeknik Ungku Omar'}, chosen_pathway='poly')
        offer = _offer(app)
        with self.assertLogs('apps.scholarship.services', level='INFO') as logs:
            self.assertTrue(fill_empty_pick(app, offer, student_offer_check(offer)))
        self.assertTrue(any('kind=fill course_id=UW6442001 source=offer_letter_auto '
                            'old_pick=- | - | Politeknik Ungku Omar old_pathway=poly new_pathway=university' in x
                            for x in logs.output))

    def test_a_suspect_letter_never_fills(self):
        app = self._app()
        offer = _offer(app, status='suspect')
        self.assertEqual(plan_offer_link(app, offer, student_offer_check(offer))[0], 'not_genuine')
        self.assertFalse(fill_empty_pick(app, offer, student_offer_check(offer)))

    def test_a_profile_plan_of_her_own_is_never_overwritten(self):
        from apps.scholarship.tests.factories import make_student
        own = {'course_id': 'RA-POLY-DPM', 'course_name': 'Diploma Pengurusan Muamalat',
               'institution': 'Politeknik Ungku Omar'}
        student = make_student(chosen_programme=dict(own), chosen_pathway='poly')
        app = self._app(student=student)
        offer = _offer(app)
        with self.assertLogs('apps.scholarship.services', level='INFO') as logs:
            self.assertTrue(fill_empty_pick(app, offer, student_offer_check(offer)))
        student.refresh_from_db()
        self.assertEqual((student.chosen_programme, student.chosen_pathway), (own, 'poly'))
        self.assertTrue(any('profile=kept_own_plan' in x for x in logs.output))

    def test_an_empty_profile_plan_follows(self):
        from apps.scholarship.tests.factories import make_student
        student = make_student(chosen_programme={}, chosen_pathway='')
        app = self._app(student=student)
        offer = _offer(app)
        fill_empty_pick(app, offer, student_offer_check(offer))
        student.refresh_from_db()
        self.assertEqual((student.chosen_programme['course_id'], student.chosen_pathway), ('UW6442001', 'university'))


class SkipTest(_Base):
    def _skip(self, app, offer, reason):
        self.assertEqual(plan_offer_link(app, offer, student_offer_check(offer))[0], reason)
        self.assertFalse(fill_empty_pick(app, offer, student_offer_check(offer)))

    def test_what_still_stops_it(self):
        app = self._app(status='interviewed')
        self._skip(app, _offer(app), 'decided')
        app = self._app()
        self._skip(app, _offer(app, nric='990101-01-9999'), 'not_own_letter')
        app = self._app()
        self._skip(app, _offer(app, status='not_offer_letter'), 'not_offer_letter')
        app = self._app(chosen_pathway='stpm')
        self._skip(app, _offer(app), 'pre_u')

    def test_a_named_pick_is_never_filled(self):
        app = self._app(chosen_programme={'course_name': 'Diploma Perakaunan'})
        offer = _offer(app)
        self._skip(app, offer, 'not_offer_sourced')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme, {'course_name': 'Diploma Perakaunan'})


class CommandTest(_Base):
    def test_the_link_command_reports_then_fills(self):
        app = self._app()
        _offer(app)
        out = StringIO()
        call_command('link_offer_courses', stdout=out)
        self.assertIn(f'#{app.id} [shortlisted] (empty_pick) FILL (would): - | - | -  ->  '
                      'UW6442001 | Sarjana Muda Sains Kimia dengan Kepujian | Universiti Malaysia Sarawak',
                      out.getvalue())
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme, {})
        call_command('link_offer_courses', '--apply', stdout=StringIO())
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme, FILLED)
