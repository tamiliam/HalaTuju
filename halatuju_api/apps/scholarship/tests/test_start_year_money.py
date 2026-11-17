"""H3a rebuild (2026-11-15): the MONEY's start year is exactly main's.

An adversarial review failed the branch that made one start-year reading serve both the gift's
start-year rule and the money. The lead's ruling: the money reading (`pathway_engine.course_start_year`,
read by the STPM award size, `award.course_start_unknown` at QC and the funding estimate) stays
EXACTLY main's; any change is a defect. `_main_money_year` is main's reader, frozen here as an
oracle (main at ed884c543: `student_offer_check` takes the first 20xx on the intake line, else on
the letter's reporting date; `course_start_year` then falls back to the stored reporting date).
Every row also carries its expected year written out, so the oracle itself cannot drift.

The rows run on an intake WITH the start-year rule on, so the gift's own reading runs beside them.
"""
import datetime
import re

from django.test import TestCase

from apps.scholarship import award, funding_estimate, start_year
from apps.scholarship import pathway_engine as pe
from apps.scholarship.models import ApplicantDocument, ScholarshipCohort
from apps.scholarship.tests.factories import make_application, make_student


def _main_money_year(intake, reporting_date, stored):
    """Main's money reading, frozen (do not "fix" it here: a bug in it is a TD note)."""
    intake, reporting_date = (intake or '').strip(), (reporting_date or '').strip()
    m = re.search(r'\b(20\d{2})\b', intake) or re.search(r'\b(20\d{2})\b', reporting_date)
    if m:
        return int(m.group(1))
    return stored.year if stored else None


_D = datetime.date
# (intake line, the letter's reporting date, the stored reporting date, main's year)
ROWS = (
    ('Tahun 2 Sesi 2025/2026', '', None, 2025),
    ('Tahun 2 Sesi 2025/2026', '7 September 2025', _D(2025, 9, 7), 2025),
    ('Semester 2 Sesi 2024/2025', '', None, 2024),
    ('Semester II Sesi 2024/2025', '', None, 2024),
    ('Sesi 2024/2025 Semester II', '', None, 2024),
    ('Semester 3 Sesi 2024/2025', '3 Mac 2025', _D(2025, 3, 3), 2024),
    ('Semester 3 Sesi 2024/2025', '', _D(2025, 3, 3), 2024),
    ('Sesi : 2026/2027 Semester : 3', '', None, 2026),
    ('Semester 1 / 2 Sesi 2025/2026', '', None, 2025),
    ('Sesi Akademik 2025/2026', '', None, 2025),
    ('Sesi 2024/2025', '', None, 2024),
    ('Sesi 2024/2025', '17 Februari 2025', _D(2025, 2, 17), 2024),
    ('Sesi 2024/2025', '5 Jan 2023', None, 2024),
    ('Sesi II 2024/2025', '', None, 2024),
    ('Sesi II 2024/2025', '2 Disember 2024', _D(2024, 12, 2), 2024),
    ('Sesi II 2024/2025', '6 Januari 2025', _D(2025, 1, 6), 2024),
    ('Sesi 2024/25', '', None, 2024),
    ('Julai 2025 - 26 Februari 2026', '', None, 2025),
    ('Jun 2024 - 25 Mei 2025', '', None, 2024),
    ('6 / 2025 – 12 / 2026', '', None, 2025),
    ('Ambilan Disember 2024/2025', '', None, 2024),
    ('Intake Jan 2025 (Session 2024/2025)', '', None, 2025),
    ('Session 2024/2025 January intake', '', None, 2024),
    ('Intake: February 2025, Session 2024/2025', '', None, 2025),
    ('Session 2024/25 February intake', '', None, 2024),
    ('Sesi 2024/2025 Semester I', '25 Februari 2025', _D(2025, 2, 25), 2024),
    ('Penggal 2 Sesi 2024/2025', '', None, 2024),
    ('Tingkatan 6 Atas 2024/2025', '', None, 2024),
    ('Sesi 2024/2025, Sesi 2025/2026', '', None, 2024),
    ('Mac 2025', '', None, 2025),
    ('2024', '10 JUN 2024', _D(2024, 6, 10), 2024),
    ('', '8 Jun 2025', _D(2025, 6, 8), 2025),
    ('', '', _D(2025, 7, 1), 2025),
    ('', '', None, None),
    ('Semester 3', '', _D(2024, 9, 1), 2024),
)


class MoneyIsMainsReading(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='money', name='Degree', year=2026,
                                                      allowed_start_years=[2025, 2026])

    def _case(self, n, intake, rd, stored, suffix):
        student = make_student(supabase_user_id=f'money-{suffix}-{n}', name='Anbu A/L Raj',
                               household_income=1500, household_size=5)
        app = make_application('profile_complete', cohort=self.cohort, student=student,
                               chosen_pathway='stpm', father_occupation='gov',
                               mother_occupation='homemaker', reporting_date=stored)
        ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path='x/offer',
            vision_fields={'fields': {'intake': intake, 'reporting_date': rd, 'candidate_name': 'Anbu A/L Raj',
                                      'programme': 'Tingkatan 6'}, 'student_verdict': 'ok'})
        return app

    def test_no_money_module_reads_the_gifts_reading(self):
        import inspect
        for module in (pe, award, funding_estimate):
            with self.subTest(module=module.__name__):
                self.assertNotIn('session_year', inspect.getsource(module))
                self.assertNotIn('start_year.', inspect.getsource(module).replace('course_start_year', ''))

    def test_the_oracle_matches_the_written_years(self):
        for intake, rd, stored, expected in ROWS:
            with self.subTest(intake=intake, rd=rd):
                self.assertEqual(_main_money_year(intake, rd, stored), expected)

    def test_every_money_reader_gives_mains_year(self):
        for n, (intake, rd, stored, expected) in enumerate(ROWS):
            # str(): xdist cannot send a datetime.date in a subTest label between workers.
            with self.subTest(intake=intake, rd=rd, stored=str(stored)):
                app = self._case(n, intake, rd, stored, 'row')
                self.assertEqual(pe.course_start_year(app), expected)
                self.assertEqual(pe.course_start_year(app), _main_money_year(intake, rd, stored))
                offer = ApplicantDocument.objects.get(application=app, doc_type='offer_letter')
                letter_year = _main_money_year(intake, rd, None)
                self.assertEqual(pe.student_offer_check(offer)['intake_year'],
                                 str(letter_year) if letter_year else '')
                self.assertEqual(award.course_start_unknown(app), expected is None)
                start_year.reading(app)                     # the gift's reading runs beside it
                if expected is None:
                    continue
                # The award and the funding estimate equal a plain-year twin's (main's sizing).
                twin = self._case(n, str(expected), '', None, 'twin')
                self.assertEqual(award.proposed_award_amount(app), award.proposed_award_amount(twin))
                self.assertEqual(funding_estimate._years_done(app), funding_estimate._years_done(twin))
