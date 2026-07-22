"""Reviewer-query S3 — offer reporting-date: normalise + persist + the missing-date clarify."""
import datetime

from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship import pathway_engine as pe
from apps.scholarship.check2_queries import sync_check2_queries
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)


class TestParseReportingDate(TestCase):
    def test_formats(self):
        cases = {
            '8 JUN 2026': datetime.date(2026, 6, 8),
            '08 Jun 2026': datetime.date(2026, 6, 8),
            '08 Jun 2026 (Isnin)': datetime.date(2026, 6, 8),
            '8 HINGGA 9 JUN 2026': datetime.date(2026, 6, 8),
            '22 JUN 2026 (9.00 PAGI - 2.00 PETANG)': datetime.date(2026, 6, 22),
            '20 JULAI 2026': datetime.date(2026, 7, 20),
            '10 OGOS 2026': datetime.date(2026, 8, 10),
            '28 JULAI 2024 2:30 PETANG': datetime.date(2024, 7, 28),
            '10 August 2026': datetime.date(2026, 8, 10),
        }
        for raw, want in cases.items():
            self.assertEqual(pe.parse_reporting_date(raw), want, raw)

    def test_unparseable(self):
        for raw in ('', None, 'to be advised', 'June', '2026', 'soon'):
            self.assertIsNone(pe.parse_reporting_date(raw))


class _OfferBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, suffix='1', **kw):
        p = StudentProfile.objects.create(
            supabase_user_id=f'rd-{suffix}', name='Anbu A/L Raj', nric='030101-14-1234',
            household_income=1500, household_size=5)
        defaults = dict(cohort=self.cohort, profile=p, status='profile_complete',
                        profile_completed_at=timezone.now(),
                        father_occupation='gov', mother_occupation='homemaker')
        defaults.update(kw)
        return ScholarshipApplication.objects.create(**defaults)

    def _offer(self, app, reporting_date='8 JUN 2026', read=True, programme='Diploma Kejuruteraan'):
        fields = {'reporting_date': reporting_date, 'candidate_name': 'Anbu A/L Raj',
                  'programme': programme, 'institution': 'Politeknik Test'}
        vf = {'fields': fields}
        if read:
            vf['student_verdict'] = 'ok'           # extracted → name/ic not 'pending'
        return ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path='x/offer', vision_fields=vf)


class TestOfferReportingDate(_OfferBase):
    def test_offer_reporting_date_parsed(self):
        app = self._app('a')
        self._offer(app, '20 JULAI 2026')
        self.assertEqual(pe.offer_reporting_date(app), datetime.date(2026, 7, 20))

    def test_unknown_when_no_date_on_readable_offer(self):
        app = self._app('b')
        self._offer(app, reporting_date='')
        self.assertTrue(pe.offer_reporting_date_unknown(app))

    def test_not_unknown_when_date_present(self):
        app = self._app('c')
        self._offer(app, '8 JUN 2026')
        self.assertFalse(pe.offer_reporting_date_unknown(app))

    def test_not_unknown_when_offer_unread(self):
        app = self._app('d')
        self._offer(app, reporting_date='', read=False)   # not extracted yet
        self.assertFalse(pe.offer_reporting_date_unknown(app))

    def test_no_offer_not_unknown(self):
        app = self._app('e')
        self.assertFalse(pe.offer_reporting_date_unknown(app))


class TestAutofillStoresDate(_OfferBase):
    def test_autofill_persists_reporting_date(self):
        from apps.scholarship.services import autofill_pathway_from_offer
        app = self._app('f')
        self._offer(app, '22 JUN 2026')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.reporting_date, datetime.date(2026, 6, 22))

    def test_autofill_persists_date_even_when_pathway_locked(self):
        # Regression: a student who has LOCKED a precise pathway (course_id + certainty
        # 'sure') must still get reporting_date persisted — the date is a fact off the
        # offer, independent of the chosen pathway. Previously the locked early-return
        # skipped the reporting_date write, leaving the column NULL for confirmed students.
        from apps.scholarship.services import autofill_pathway_from_offer
        app = self._app('locked',
                        chosen_programme={'course_id': 'DKM-001', 'course_name': 'Diploma',
                                          'institution': 'Politeknik Test'},
                        pathway_certainty='sure')
        self._offer(app, '13 JUN 2026')
        changed = autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertTrue(changed)
        self.assertEqual(app.reporting_date, datetime.date(2026, 6, 13))
        # The locked pick is untouched.
        self.assertEqual(app.chosen_programme.get('course_id'), 'DKM-001')


class TestCheck2Clarify(_OfferBase):
    def _codes(self, app):
        return {r.code: r for r in app.resolution_items.filter(source='check2', status='open')}

    def test_missing_date_raises_clarify(self):
        app = self._app('g')
        self._offer(app, reporting_date='')
        sync_check2_queries(app)
        items = self._codes(app)
        self.assertIn('reporting_date_unknown', items)
        self.assertEqual(items['reporting_date_unknown'].kind, 'clarify')

    def test_no_clarify_when_date_present(self):
        app = self._app('h')
        self._offer(app, '8 JUN 2026')
        sync_check2_queries(app)
        self.assertNotIn('reporting_date_unknown', self._codes(app))


# -- The date as a MONEY fact (owner 2026-07-23) -------------------------------
#
# `reporting_date` drives three things: the bursary SIZE (a course begun before the cohort year
# = a continuing student, one year of funding left), payment eligibility, and the semester-result
# request. It was NULL for ~45% of applications whose pathway needed confirming, because the copy
# sat BELOW four guards about the PATHWAY -- a programme disagreement (exactly what raises the
# confirm query) abandoned the function and took the date with it.
#
# Note `test_autofill_persists_date_even_when_pathway_locked` above: the same class of bug was
# found and fixed once for the LOCK guard and tested -- but the four returns ABOVE it were never
# covered. These cases close that.

class _IntakeBase(_OfferBase):
    """An offer whose INTAKE line is set - the Form 6 shape carrying a range and no date."""

    def _intake_offer(self, app, intake='', reporting_date='', programme='Tingkatan Enam'):
        doc = self._offer(app, reporting_date=reporting_date, programme=programme)
        vf = dict(doc.vision_fields)
        vf['fields'] = {**vf['fields'], 'intake': intake}
        doc.vision_fields = vf
        doc.save(update_fields=['vision_fields'])
        return doc


class TestCourseStartYear(_IntakeBase):
    def test_prefers_the_intake_year_when_the_letter_has_no_date(self):
        # 123: a Form 6 letter carrying "6 / 2025 - 12 / 2026" and NO reporting date.
        app = self._app('csy-a', chosen_pathway='stpm')
        self._intake_offer(app, intake='6 / 2025 - 12 / 2026', reporting_date='')
        self.assertEqual(pe.course_start_year(app), 2025)
        self.assertTrue(pe.started_before_cohort(app))

    def test_a_current_year_intake_is_a_fresh_entrant(self):
        app = self._app('csy-b', chosen_pathway='stpm')
        self._intake_offer(app, intake='2026', reporting_date='08 Jun 2026')
        self.assertEqual(pe.course_start_year(app), 2026)
        self.assertFalse(pe.started_before_cohort(app))

    def test_unknown_when_the_letter_carries_neither(self):
        app = self._app('csy-c', chosen_pathway='stpm')
        self._intake_offer(app, intake='', reporting_date='')
        self.assertIsNone(pe.course_start_year(app))
        # not-known must NOT read as "continuing"
        self.assertFalse(pe.started_before_cohort(app))

    def test_falls_back_to_a_stored_date_when_the_letter_has_no_intake(self):
        app = self._app('csy-d', chosen_pathway='stpm',
                        reporting_date=datetime.date(2025, 6, 10))
        self._intake_offer(app, intake='', reporting_date='')
        self.assertEqual(pe.course_start_year(app), 2025)


class TestAwardSizeReadsTheStartYear(_IntakeBase):
    def test_a_continuing_stpm_student_gets_the_one_year_amount(self):
        from apps.scholarship import award
        app = self._app('amt-a', chosen_pathway='stpm')
        self._intake_offer(app, intake='6 / 2025 - 12 / 2026', reporting_date='')
        self.assertIsNone(app.reporting_date)        # the ONLY field the old rule read
        self.assertEqual(award.proposed_award_amount(app), award._STPM_CONTINUING_AMOUNT)

    def test_a_fresh_stpm_student_gets_the_full_amount(self):
        from apps.scholarship import award
        app = self._app('amt-b', chosen_pathway='stpm')
        self._intake_offer(app, intake='2026', reporting_date='08 Jun 2026')
        self.assertEqual(award.proposed_award_amount(app), award._STPM_AMOUNT)

    def test_course_start_unknown_flags_stpm_only(self):
        from apps.scholarship import award
        blind = self._app('amt-c', chosen_pathway='stpm')
        self._intake_offer(blind, intake='', reporting_date='')
        self.assertTrue(award.course_start_unknown(blind))
        other = self._app('amt-d', chosen_pathway='asasi')   # amount ignores the start year
        self._intake_offer(other, intake='', reporting_date='')
        self.assertFalse(award.course_start_unknown(other))


class TestSemesterResultSharesTheSameSignal(_IntakeBase):
    """The second consequence of the same NULL: 123 was never asked for his CGPA."""

    def test_a_continuing_student_is_asked(self):
        from apps.scholarship.income_engine import semester_result_gap
        app = self._app('sr-a', chosen_pathway='stpm')
        self._intake_offer(app, intake='6 / 2025 - 12 / 2026', reporting_date='')
        self.assertTrue(semester_result_gap(app))

    def test_a_fresh_entrant_is_not(self):
        from apps.scholarship.income_engine import semester_result_gap
        app = self._app('sr-b', chosen_pathway='stpm')
        self._intake_offer(app, intake='2026', reporting_date='08 Jun 2026')
        self.assertFalse(semester_result_gap(app))


class TestSyncSurvivesThePathwayGuards(_OfferBase):
    def test_the_date_lands_even_when_the_offer_programme_clashes(self):
        # THE BUG. A declared pathway that disagrees with the offer sends the case to the
        # confirm query -- and used to abandon the date write on the way.
        from apps.scholarship.services import autofill_pathway_from_offer
        app = self._app('guard-a', chosen_programme={
            'course_id': 'X-1', 'course_name': 'Diploma Kejuruteraan Awam',
            'institution': 'Politeknik Test'}, pathway_certainty='sure')
        self._offer(app, '10 JUN 2025', programme='Tingkatan Enam Semester 1')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.reporting_date, datetime.date(2025, 6, 10))

    def test_the_date_lands_even_when_the_letter_is_the_wrong_person(self):
        # An identity clash must never adopt the pathway -- but the date is still a fact.
        from apps.scholarship.services import (autofill_pathway_from_offer,
                                               sync_reporting_date_from_offer)
        app = self._app('guard-b')
        doc = self._offer(app, '10 JUN 2025')
        vf = dict(doc.vision_fields)
        vf['fields'] = {**vf['fields'], 'candidate_name': 'SOMEONE ELSE ENTIRELY'}
        doc.vision_fields = vf
        doc.save(update_fields=['vision_fields'])
        self.assertTrue(sync_reporting_date_from_offer(app))
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.reporting_date, datetime.date(2025, 6, 10))

    def test_sync_is_idempotent(self):
        from apps.scholarship.services import sync_reporting_date_from_offer
        app = self._app('guard-c')
        self._offer(app, '10 JUN 2025')
        self.assertTrue(sync_reporting_date_from_offer(app))
        self.assertFalse(sync_reporting_date_from_offer(app))


class TestOfficerEntry(_OfferBase):
    def _admin(self):
        from apps.courses.models import PartnerAdmin
        return PartnerAdmin.objects.create(
            supabase_user_id='rd-adm', role='org_admin', is_active=True,
            name='Super', email='su@x.com')

    def test_records_a_date_an_officer_established(self):
        from apps.scholarship.services import set_reporting_date_by_officer
        app = self._app('off-a')
        set_reporting_date_by_officer(app, self._admin(), '2025-06-10')
        app.refresh_from_db()
        self.assertEqual(app.reporting_date, datetime.date(2025, 6, 10))

    def test_refuses_a_blank_or_unparseable_value(self):
        from apps.scholarship.services import set_reporting_date_by_officer
        app, admin = self._app('off-b'), self._admin()
        for bad in ('', '   ', None, 'sometime in June'):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    set_reporting_date_by_officer(app, admin, bad)
        app.refresh_from_db()
        self.assertIsNone(app.reporting_date)

    def test_an_officer_date_sizes_the_bursary_like_a_documented_one(self):
        # 123's agreed correction -- 10 June 2025 makes him continuing -> RM1,000.
        from apps.scholarship import award
        from apps.scholarship.services import set_reporting_date_by_officer
        app = self._app('off-c', chosen_pathway='stpm')
        self._offer(app, reporting_date='')
        self.assertTrue(award.course_start_unknown(app))
        set_reporting_date_by_officer(app, self._admin(), '2025-06-10')
        app.refresh_from_db()
        self.assertFalse(award.course_start_unknown(app))
        self.assertEqual(award.proposed_award_amount(app), award._STPM_CONTINUING_AMOUNT)

    def test_a_readable_letter_later_overrides_an_officer_guess(self):
        # Deliberate precedence: a letter we can now read beats a human's inference. This is
        # why no 'officer' provenance column exists to protect the typed value.
        from apps.scholarship.services import (set_reporting_date_by_officer,
                                               sync_reporting_date_from_offer)
        app = self._app('off-d')
        self._offer(app, reporting_date='')
        set_reporting_date_by_officer(app, self._admin(), '2025-06-10')
        app.documents.all().delete()
        self._offer(app, '08 Jun 2026')
        self.assertTrue(sync_reporting_date_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.reporting_date, datetime.date(2026, 6, 8))


class TestStudentAnswerNeverSizesTheBursary(_IntakeBase):
    def test_a_misread_free_text_answer_cannot_drive_the_amount(self):
        # 123 answered the "when do you report?" clarify with "16 july 2026" -- the date he
        # collected a confirmation letter, NOT the date he started. Parsing student free text
        # into the field (the pattern used for Vircle IDs and pension claims) would have made
        # him a fresh entrant and committed RM3,000. The engine must read the letter's intake.
        from apps.scholarship import award
        app = self._app('ans-a', chosen_pathway='stpm')
        self._intake_offer(app, intake='6 / 2025 - 12 / 2026', reporting_date='')
        app.resolution_items.create(code='reporting_date_unknown', status='resolved',
                                    resolution_text='16 july 2026. i reported in my kolej')
        self.assertEqual(pe.course_start_year(app), 2025)
        self.assertEqual(award.proposed_award_amount(app), award._STPM_CONTINUING_AMOUNT)
