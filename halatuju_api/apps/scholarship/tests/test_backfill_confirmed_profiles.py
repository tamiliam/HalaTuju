"""TD-210 backfill: students who confirmed an offer BEFORE the fix keep their original declaration
on the profile. `backfill_confirmed_profiles` copies the confirmed pathway onto it — dry run by
default, `--apply` to write, idempotent."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.tests.factories import make_application, make_cohort, make_student

_CONFIRMED_PISMP = {
    'chosen_pathway': 'pismp', 'pre_u_track': '', 'pre_u_institution': '',
    'chosen_programme': {'course_name': 'Ijazah Sarjana Muda Perguruan',
                         'institution': 'IPG Kampus Tuanku Bainun',
                         'source': 'offer_letter_confirmed'},
}


class TestBackfillConfirmedProfiles(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='bf', name='B40', year=2026)

    def _run(self, *args):
        out = StringIO()
        call_command('backfill_confirmed_profiles', *args, stdout=out)
        return out.getvalue()

    def _the_43_shape(self, uid='bf-43', stage='awarded'):
        """Application confirmed PISMP before the fix; profile still on the STPM declaration."""
        prof = make_student(supabase_user_id=uid, chosen_pathway='stpm', pre_u_track='sains_sosial',
                            pre_u_institution='SMK X',
                            chosen_programme={'course_name': 'Tingkatan Enam', 'source': 'student'})
        app = make_application(stage, cohort=self.cohort, student=prof,
                               pathway_confirmed_at=timezone.now(), **_CONFIRMED_PISMP)
        return app, prof

    def test_dry_run_writes_nothing(self):
        app, prof = self._the_43_shape()
        out = self._run()
        self.assertIn(f'app {app.id}: profile would refresh: chosen_pathway', out)
        self.assertIn('[dry-run]', out)
        prof.refresh_from_db()
        self.assertEqual(prof.chosen_pathway, 'stpm')
        self.assertEqual(prof.pre_u_track, 'sains_sosial')

    def test_apply_fixes_the_43_shape_and_prints_no_values(self):
        app, prof = self._the_43_shape()
        out = self._run('--apply')
        prof.refresh_from_db()
        self.assertEqual(prof.chosen_pathway, 'pismp')
        self.assertEqual(prof.pre_u_track, '')            # the STPM stream is gone everywhere
        self.assertEqual(prof.pre_u_institution, '')
        self.assertEqual(prof.chosen_programme['source'], 'offer_letter_confirmed')
        self.assertIn(f'app {app.id}: profile refreshed: chosen_pathway, pre_u_track, '
                      f'pre_u_institution, chosen_programme', out)
        for value in ('pismp', 'SMK X', 'Bainun', 'sains_sosial'):
            self.assertNotIn(value, out)

    def test_a_second_apply_is_a_no_op(self):
        self._the_43_shape()
        self._run('--apply')
        out = self._run('--apply')
        self.assertIn('0 changed', out)
        self.assertNotIn('refreshed', out)

    def test_a_pre_u_blank_on_the_application_never_erases_the_profile(self):
        # A pre-U pathway with no stream on the application: the profile's stream is the
        # student's own answer and a blank carries no information (copy_pathway's rule).
        prof = make_student(supabase_user_id='bf-preu', chosen_pathway='stpm', pre_u_track='sains')
        make_application('profile_complete', cohort=self.cohort, student=prof,
                         pathway_confirmed_at=timezone.now(), chosen_pathway='stpm',
                         pre_u_track='', pre_u_institution='Kolej Tingkatan Enam Gombak')
        self._run('--apply')
        prof.refresh_from_db()
        self.assertEqual(prof.pre_u_track, 'sains')
        self.assertEqual(prof.pre_u_institution, 'Kolej Tingkatan Enam Gombak')

    def test_an_application_with_a_later_open_one_is_skipped(self):
        app, prof = self._the_43_shape(stage='rejected')
        make_application('submitted', cohort=make_cohort(code='bf2', name='B40', year=2027),
                         student=prof)
        self._run('--apply')
        prof.refresh_from_db()
        self.assertEqual(prof.chosen_pathway, 'stpm')      # the profile follows the open one

    def test_the_cron_door_applies_only_with_its_env_var(self):
        # The cron endpoint passes no flags; the env var is the only way it writes.
        from unittest import mock
        from apps.scholarship.views import CronRunView
        self.assertEqual(CronRunView.JOBS['backfill-confirmed-profiles'], 'backfill_confirmed_profiles')
        app, prof = self._the_43_shape()
        self._run()
        prof.refresh_from_db()
        self.assertEqual(prof.chosen_pathway, 'stpm')
        with mock.patch.dict('os.environ', {'BACKFILL_CONFIRMED_PROFILES_APPLY': '1'}):
            self._run()
        prof.refresh_from_db()
        self.assertEqual(prof.chosen_pathway, 'pismp')
