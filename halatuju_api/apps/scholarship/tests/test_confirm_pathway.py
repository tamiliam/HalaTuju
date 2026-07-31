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

    def _pismp_offer(self, app, *, identity=False):
        f = {'institution': 'INSTITUT PENDIDIKAN GURU KAMPUS TUANKU BAINUN',
             'programme': 'Program Ijazah Sarjana Muda Perguruan (PISMP)', 'stream': ''}
        if identity:                       # match the profile so the verdict clears identity
            f['candidate_name'] = app.profile.name
            f['candidate_nric'] = app.profile.nric
        return ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/pismp',
            vision_fields={'fields': f, 'student_verdict': 'ok',
                           'authenticity': {'status': 'genuine', 'reason': 'x'}},
            vision_run_at=timezone.now())

    def test_type_switch_confirm_adopts_offer_type_and_clears_stale_preu(self):
        # TD-161 (#43): declared STPM (Sains Sosial), genuine PISMP offer → confirm switches the TYPE
        # and drops the now-irrelevant STPM stream + school.
        app = self._app(pathway='stpm', track='sains_sosial', institution='SMK X')
        self._pismp_offer(app)
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'pismp')
        self.assertEqual(app.pre_u_track, '')
        self.assertEqual(app.pre_u_institution, '')

    def test_same_type_confirm_leaves_pathway_unchanged(self):
        # A within-type confirm (STPM offer) never rewrites the pathway type.
        app = self._app(pathway='stpm', track='sains_sosial', institution='SMK X')
        self._offer(app, institution='KOLEJ TINGKATAN ENAM GOMBAK',
                    programme='Tingkatan Enam Semester 1', stream='SAINS')
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'stpm')

    def test_verdict_raises_type_switch_even_when_confirmed(self):
        # After an offer-confirm the type mismatch is otherwise invisible; TD-161 re-raises it.
        from apps.scholarship.verdict_engine import build_verdict
        app = self._app(pathway='stpm', track='sains_sosial', institution='SMK X')
        self._pismp_offer(app, identity=True)
        app.pathway_confirmed_at = timezone.now()
        app.save(update_fields=['pathway_confirmed_at'])
        pathway = next(f for f in build_verdict(app) if f['fact'] == 'pathway')
        item = next((it for it in pathway['unresolved'] if it['code'] == 'pathway_type_switch'), None)
        self.assertIsNotNone(item)
        self.assertEqual(item['params']['declared_pathway'], 'stpm')
        self.assertEqual(item['params']['offer_pathway'], 'pismp')
        self.assertEqual(item['params']['aliran_hint'], 'sk')   # no vernacular subject on file (lowercase code)

    def test_pismp_bidang_resolves_and_pins_course(self):
        # Owner 2026-07-18 (#43): a PISMP offer stating a vernacular bidang (Bahasa Tamil) resolves to
        # the UNIQUE SJKT course → the switch carries bidang + course, and confirm PINS the course_id
        # (so the cockpit links the right PISMP course, not a stale STPM one) + reconciles the type.
        from apps.courses.models import Course, CourseRequirement, FieldTaxonomy
        from apps.scholarship.verdict_engine import build_verdict
        ft = FieldTaxonomy.objects.create(key='edu', name_en='Education', name_ms='Pendidikan',
                                          name_ta='x', image_slug='edu')
        c = Course.objects.create(course_id='50PD04TA', course='Bahasa Tamil Pendidikan Rendah (SJKT)',
                                  level='Ijazah Sarjana Muda', department='Edu', field='Education', field_key=ft)
        CourseRequirement.objects.create(course=c, source_type='pismp')
        app = self._app(pathway='stpm', track='sains_sosial', institution='SMK X')
        ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/p',
            vision_fields={'fields': {
                'candidate_name': app.profile.name, 'candidate_nric': app.profile.nric,
                'programme': 'Program Ijazah Sarjana Muda Perguruan (PISMP)',
                'institution': 'Institut Pendidikan Guru Kampus Tuanku Bainun',
                'bidang_pengkhususan': 'BAHASA TAMIL PENDIDIKAN RENDAH', 'stream': ''},
                'student_verdict': 'ok', 'authenticity': {'status': 'genuine', 'reason': 'x'}},
            vision_run_at=timezone.now())
        app.pathway_confirmed_at = timezone.now(); app.save(update_fields=['pathway_confirmed_at'])
        item = next(i for i in next(f for f in build_verdict(app) if f['fact'] == 'pathway')['unresolved']
                    if i['code'] == 'pathway_type_switch')
        self.assertEqual(item['params']['bidang'], 'BAHASA TAMIL PENDIDIKAN RENDAH')
        self.assertEqual(item['params']['course_id'], '50PD04TA')
        self.assertEqual(item['params']['aliran'], 'sjkt')
        self.assertNotIn('aliran_hint', item['params'])          # unique bidang → no picker hint
        confirm_pathway(app); app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'pismp')
        self.assertEqual(app.chosen_programme['course_id'], '50PD04TA')
        self.assertEqual(app.pre_u_track, '')                    # stale STPM stream dropped

    def test_pismp_confirm_aligns_institution_to_catalogue(self):
        # Owner 2026-07-18 (#43/#115): the offer prints the IPG ALL-CAPS and confirm_pathway stored
        # that raw text; now it aligns the institution to the recommender CATALOGUE's clean
        # title-case name (the single source of truth the course selector shows), disambiguating
        # the one IPG among the many the course is offered at.
        from apps.courses.models import (Course, CourseInstitution, CourseRequirement,
                                         FieldTaxonomy, Institution)
        ft = FieldTaxonomy.objects.create(key='edu2', name_en='Education', name_ms='Pendidikan',
                                          name_ta='x', image_slug='edu')
        c = Course.objects.create(course_id='50PD04TA', course='Bahasa Tamil Pendidikan Rendah (SJKT)',
                                  level='Ijazah Sarjana Muda', department='Edu', field='Education', field_key=ft)
        CourseRequirement.objects.create(course=c, source_type='pismp')
        bainun = Institution.objects.create(
            institution_id='IPG01', type='IPG', state='Perak',
            institution_name='Institut Pendidikan Guru Kampus Tuanku Bainun')
        ipoh = Institution.objects.create(          # a sibling campus — the matcher must NOT pick it
            institution_id='IPG02', type='IPG', state='Perak',
            institution_name='Institut Pendidikan Guru Kampus Ipoh')
        CourseInstitution.objects.create(course=c, institution=bainun)
        CourseInstitution.objects.create(course=c, institution=ipoh)
        app = self._app(pathway='stpm', track='sains_sosial', institution='SMK X')
        ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/pi',
            vision_fields={'fields': {
                'candidate_name': app.profile.name, 'candidate_nric': app.profile.nric,
                'programme': 'Program Ijazah Sarjana Muda Perguruan (PISMP)',
                'institution': 'INSTITUT PENDIDIKAN GURU KAMPUS TUANKU BAINUN',   # ALL-CAPS, as printed
                'bidang_pengkhususan': 'BAHASA TAMIL PENDIDIKAN RENDAH', 'stream': ''},
                'student_verdict': 'ok', 'authenticity': {'status': 'genuine', 'reason': 'x'}},
            vision_run_at=timezone.now())
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], '50PD04TA')
        self.assertEqual(app.chosen_programme['institution'],
                         'Institut Pendidikan Guru Kampus Tuanku Bainun')   # aligned, not raw caps

    def test_no_offer_is_a_noop(self):
        app = self._app(pathway='stpm', track='sains_sosial', institution='SMK Asal')
        self.assertFalse(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.pre_u_institution, 'SMK Asal')   # untouched
        self.assertEqual(app.pre_u_track, 'sains_sosial')


class TestConfirmWithNothingDeclared(_Base):
    """Request #7/#8 — the pre-U tidy-up is gated on the pathway TYPE, and the type is reconciled
    from the offer letter. Those two steps used to run in the wrong order, so a student who never
    declared a pathway (``chosen_pathway=''`` — the normal state of anyone who applied
    ``pathway_certainty='uncertain'``) had the whole block skipped against her empty declaration,
    and the type was then corrected too late to be of any use. She ended up reading `matric` beside
    a raw ALL-CAPS college, no stream and no school (#32), or the same with `stpm` (#119)."""

    def test_matric_offer_with_nothing_declared_fills_track_school_and_name(self):
        app = self._app(pathway='', track='', institution='')       # #32: declared nothing
        self._offer(app, institution='KOLEJ MATRIKULASI SELANGOR',
                    programme='Program Matrikulasi (SAINS)', stream='SAINS')
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'matric')              # adopted from the letter
        self.assertEqual(app.pre_u_track, 'sains')                  # was '' — the reported gap
        self.assertIn('Selangor', app.pre_u_institution)            # was '' — the reported gap
        # …and the programme reads like an auto-settled one, not like the letter.
        self.assertEqual(app.chosen_programme['course_name'], 'Program Matrikulasi')
        self.assertEqual(app.chosen_programme['institution'], app.pre_u_institution)
        self.assertNotEqual(app.chosen_programme['institution'], 'KOLEJ MATRIKULASI SELANGOR')

    def test_stpm_offer_with_nothing_declared_fills_stream_and_college(self):
        app = self._app(pathway='', track='', institution='')       # #119: declared nothing
        self._offer(app, institution='KOLEJ TINGKATAN ENAM SRI ISTANA',
                    programme='Tingkatan Enam Semester 1', stream='SAINS SOSIAL')
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'stpm')
        self.assertEqual(app.pre_u_track, 'sains_sosial')
        self.assertEqual(app.pre_u_institution, 'Kolej Tingkatan Enam Sri Istana')
        self.assertEqual(app.chosen_programme['course_name'], 'Tingkatan Enam')

    def test_filling_the_blanks_does_not_turn_the_pathway_chip_red(self):
        """Filling a field that has only ever been blank changes every reader of it — in July
        exactly this repair flipped #48's Pathway chip to a clash and docked her band. The chip
        must read the same before and after, because both values come from the same letter."""
        from apps.scholarship.pathway_engine import student_offer_check
        app = self._app(pathway='', track='', institution='')
        offer = self._offer(app, institution='KOLEJ TINGKATAN ENAM SRI ISTANA',
                            programme='Tingkatan Enam Semester 1', stream='SAINS SOSIAL')
        self.assertEqual(student_offer_check(offer)['pathway'], 'unknown')   # nothing to compare
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        offer.refresh_from_db()
        offer.application = app                      # re-read against the now-filled record
        # 'unknown' → 'match' is the whole point (there is now something to agree with). The
        # forbidden move is the one that bit #48: blank → red.
        self.assertEqual(student_offer_check(offer)['pathway'], 'match')

    def test_an_untypeable_offer_leaves_a_declared_pathway_alone(self):
        """The reconciliation only moves on an offer we can actually type. A letter with no
        keyword we recognise must not blank or overwrite what the student declared."""
        app = self._app(pathway='stpm', track='sains_sosial', institution='SMK Asal')
        self._offer(app, institution='Pusat X', programme='Kursus Persediaan')
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'stpm')     # not moved
        self.assertEqual(app.pre_u_track, 'sains_sosial')     # not blanked
        # The SCHOOL does follow the confirmed letter — that is the #117 rule and predates this
        # change (she confirmed this offer, so its school is the current one).
        self.assertEqual(app.pre_u_institution, 'Pusat X')
        # …and an untypeable letter never gets forced into the canonical pre-U name.
        self.assertEqual(app.chosen_programme['course_name'], 'Kursus Persediaan')
