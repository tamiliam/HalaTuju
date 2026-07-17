"""confirm_pathway (the student's 'Yes, this is my pathway' Check-2 answer) must bring the
DISPLAYED pre-U fields into line with the confirmed offer — not just chosen_programme. Off #117:
the student confirmed a Sains offer at Kolej Tingkatan Enam Gombak, but pre_u_institution /
pre_u_track stayed on their original Sains-Sosial-at-SMK-P-Temenggong-Ibrahim declaration, so the
cockpit kept showing the old school and the offer's Pathway chip kept a red stream clash."""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.services import confirm_pathway


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, *, pathway, track, institution):
        profile = StudentProfile.objects.create(
            supabase_user_id=f'confirm-{self.id()}', name='NILA A/P RAJU', nric='080101-05-1234',
            household_income=1800, household_size=4, receives_str=False, receives_jkm=False,
        )
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='shortlisted',
            chosen_pathway=pathway, pre_u_track=track, pre_u_institution=institution,
        )

    def _offer(self, app, *, institution, programme, stream=''):
        return ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x',
            vision_fields={'fields': {'institution': institution, 'programme': programme,
                                      'stream': stream}, 'student_verdict': 'ok',
                           'authenticity': {'status': 'genuine', 'reason': 'x'}},
            vision_run_at=timezone.now(),
        )


class TestConfirmPathwayUpdatesPreU(_Base):
    def test_stpm_confirm_updates_institution_and_stream(self):
        # #117: declared Sains Sosial at SMK P Temenggong Ibrahim; confirms a Sains offer at Gombak.
        app = self._app(pathway='stpm', track='sains_sosial',
                        institution='SMK (P) TEMENGGONG IBRAHIM')
        self._offer(app, institution='KOLEJ TINGKATAN ENAM GOMBAK',
                    programme='Tingkatan Enam Semester 1', stream='SAINS')
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.pre_u_institution, 'Kolej Tingkatan Enam Gombak')  # cased, matches offer
        self.assertEqual(app.pre_u_track, 'sains')                              # clash resolved
        self.assertEqual(app.chosen_programme['source'], 'offer_letter_confirmed')
        self.assertIsNotNone(app.pathway_confirmed_at)
        # chosen_programme is STANDARDISED like the silent auto-settle — canonical course name +
        # cleaned institution, NOT the raw "Tingkatan Enam Semester 1" / ALL-CAPS the offer prints.
        self.assertEqual(app.chosen_programme['course_name'], 'Tingkatan Enam')
        self.assertEqual(app.chosen_programme['institution'], 'Kolej Tingkatan Enam Gombak')

    def test_matric_confirm_updates_track_and_institution(self):
        # Declared a genuinely different school; confirming the Selangor matric offer updates both
        # the track and the institution (to the catalogue's Selangor college — its exact spelling
        # comes from the catalogue, which the cockpit display then expands "KM"→"Kolej Matrikulasi").
        app = self._app(pathway='matric', track='', institution='SMK Salah (wrong)')
        self._offer(app, institution='KOLEJ MATRIKULASI SELANGOR',
                    programme='Program Matrikulasi (Perakaunan)')
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.pre_u_track, 'perakaunan')
        self.assertIn('Selangor', app.pre_u_institution)
        self.assertNotEqual(app.pre_u_institution, 'SMK Salah (wrong)')
        # chosen_programme standardised: canonical name + the same cleaned institution.
        self.assertEqual(app.chosen_programme['course_name'], 'Program Matrikulasi')
        self.assertEqual(app.chosen_programme['institution'], app.pre_u_institution)

    def test_no_offer_is_a_noop(self):
        app = self._app(pathway='stpm', track='sains_sosial', institution='SMK Asal')
        self.assertFalse(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.pre_u_institution, 'SMK Asal')   # untouched
        self.assertEqual(app.pre_u_track, 'sains_sosial')
