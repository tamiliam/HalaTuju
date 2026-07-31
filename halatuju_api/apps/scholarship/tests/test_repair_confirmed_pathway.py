"""The one-off repair behind requests #7 + #8.

Two students had an offer-CONFIRMED programme with no stream and no school beside it. The repair
re-runs the (now fixed) confirm against the offer letter already on file. What it must NOT do is
as important as what it must: it must not touch a tertiary pathway that legitimately has no pre-U
fields, must not move the day the student confirmed, and must do nothing at all on a second run.
"""
from datetime import UTC, datetime
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)


class TestRepairConfirmedPathway(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='rp', name='B40', year=2026)

    def _app(self, uid, **kwargs):
        profile = StudentProfile.objects.create(
            supabase_user_id=uid, name='RASEKA A/P MURUGESE', nric='080101-05-4321')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='shortlisted', **kwargs)

    def _offer(self, app, *, institution, programme, stream=''):
        return ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x',
            vision_fields={'fields': {'institution': institution, 'programme': programme,
                                      'stream': stream}, 'student_verdict': 'ok',
                           'authenticity': {'status': 'genuine', 'reason': 'x'}},
            vision_run_at=timezone.now())

    def _run(self, *args):
        out = StringIO()
        call_command('repair_confirmed_pathway', *args, stdout=out)
        return out.getvalue()

    def _confirmed(self, uid, **kwargs):
        """An application in the broken production shape: confirmed on a real date, with the
        offer's own text stored as the programme."""
        kwargs.setdefault('pathway_confirmed_at',
                          datetime(2026, 7, 17, 11, 11, tzinfo=UTC))
        return self._app(uid, **kwargs)

    def test_repairs_the_untyped_stpm_record(self):
        # #119: nothing declared, so the pathway type itself is blank too.
        app = self._confirmed(
            'rp-119', chosen_pathway='', pre_u_track='', pre_u_institution='',
            chosen_programme={'course_name': 'Tingkatan Enam',
                              'institution': 'Kolej Tingkatan Enam Sri Istana',
                              'source': 'offer_letter_confirmed'})
        self._offer(app, institution='KOLEJ TINGKATAN ENAM SRI ISTANA',
                    programme='Tingkatan Enam Semester 1', stream='SAINS SOSIAL')
        self.assertIn('1 repaired', self._run())
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'stpm')
        self.assertEqual(app.pre_u_track, 'sains_sosial')
        self.assertEqual(app.pre_u_institution, 'Kolej Tingkatan Enam Sri Istana')

    def test_repairs_the_matric_record_and_tidies_its_shouty_programme(self):
        # #32: typed matric, but the letter's raw text was stored and no track was read off it.
        app = self._confirmed(
            'rp-32', chosen_pathway='matric', pre_u_track='', pre_u_institution='',
            chosen_programme={'course_name': 'Program Matrikulasi (SAINS)',
                              'institution': 'KOLEJ MATRIKULASI SELANGOR',
                              'source': 'offer_letter_confirmed'})
        self._offer(app, institution='KOLEJ MATRIKULASI SELANGOR',
                    programme='Program Matrikulasi (SAINS)', stream='SAINS')
        self._run()
        app.refresh_from_db()
        self.assertEqual(app.pre_u_track, 'sains')
        self.assertIn('Selangor', app.pre_u_institution)
        self.assertEqual(app.chosen_programme['course_name'], 'Program Matrikulasi')
        self.assertNotEqual(app.chosen_programme['institution'], 'KOLEJ MATRIKULASI SELANGOR')

    def test_the_day_she_confirmed_is_not_moved_to_today(self):
        app = self._confirmed(
            'rp-date', chosen_pathway='', pre_u_track='', pre_u_institution='',
            chosen_programme={'course_name': 'Tingkatan Enam', 'source': 'offer_letter_confirmed'})
        self._offer(app, institution='KOLEJ TINGKATAN ENAM SRI ISTANA',
                    programme='Tingkatan Enam Semester 1', stream='SAINS SOSIAL')
        self._run()
        app.refresh_from_db()
        self.assertEqual(app.pathway_confirmed_at.date(), datetime(2026, 7, 17).date())

    def test_a_tertiary_pathway_is_left_alone(self):
        # #13/#107: a poly or PISMP pathway has no pre-U stream or school by design.
        app = self._confirmed(
            'rp-poly', chosen_pathway='poly', pre_u_track='', pre_u_institution='',
            chosen_programme={'course_name': 'Diploma Sains Komputer',
                              'institution': 'Politeknik X', 'source': 'offer_letter_confirmed'})
        self._offer(app, institution='POLITEKNIK X', programme='Diploma Sains Komputer')
        self.assertIn('0 repaired', self._run())
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'poly')
        self.assertEqual(app.chosen_programme['course_name'], 'Diploma Sains Komputer')

    def test_a_student_declared_programme_is_not_a_candidate(self):
        """Only an offer-CONFIRMED programme is in scope — a student's own pick is not a defect."""
        app = self._app('rp-own', chosen_pathway='', pre_u_track='',
                        chosen_programme={'course_name': 'Something', 'source': ''})
        self._offer(app, institution='KOLEJ TINGKATAN ENAM SRI ISTANA',
                    programme='Tingkatan Enam Semester 1')
        self.assertIn('0 repaired', self._run())
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, '')

    def test_a_second_run_changes_nothing(self):
        app = self._confirmed(
            'rp-twice', chosen_pathway='', pre_u_track='', pre_u_institution='',
            chosen_programme={'course_name': 'Tingkatan Enam', 'source': 'offer_letter_confirmed'})
        self._offer(app, institution='KOLEJ TINGKATAN ENAM SRI ISTANA',
                    programme='Tingkatan Enam Semester 1', stream='SAINS SOSIAL')
        self._run()
        self.assertIn('0 repaired', self._run())

    def test_dry_run_writes_nothing(self):
        app = self._confirmed(
            'rp-dry', chosen_pathway='', pre_u_track='', pre_u_institution='',
            chosen_programme={'course_name': 'Tingkatan Enam', 'source': 'offer_letter_confirmed'})
        self._offer(app, institution='KOLEJ TINGKATAN ENAM SRI ISTANA',
                    programme='Tingkatan Enam Semester 1', stream='SAINS SOSIAL')
        out = self._run('--dry-run')
        self.assertIn('would re-run', out)
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, '')       # untouched
        self.assertEqual(app.pre_u_track, '')

    def test_a_candidate_with_no_offer_letter_is_reported_not_crashed(self):
        self._confirmed(
            'rp-nooffer', chosen_pathway='', pre_u_track='', pre_u_institution='',
            chosen_programme={'course_name': 'Tingkatan Enam', 'source': 'offer_letter_confirmed'})
        out = self._run()
        self.assertIn('SKIPPED', out)
        self.assertIn('0 repaired', out)
