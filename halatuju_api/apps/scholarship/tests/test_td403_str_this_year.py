"""TD-403 — an STR counts as income proof only if it is from THIS year (owner ruling 2026-10-26).

Before: a 2024 STR in the earner's own name, his card matching it, and nothing else passed the
submission gate on both routes — `str_not_breached` counted `stale` as not breached, so the cluster
completed, and the lenient `income_established` then skipped the cluster's reds although `stale` is
in `STR_RED_STATES`. And an STR read as a LATER year (a live 2027 'semakan_status' page — almost
certainly the family's 2027 APPLICATION status) read `current`, the strongest state there is.

The ruling, as built:
  * THIS year (the calendar year in Malaysia, `str_this_year`) — counts, as before.
  * an EARLIER year — `stale`, whether or not its status read: does not count; the gate blocks with
    its own plain ask, `str_stale:<year>` ("Your STR is from 2025. Please upload this year's STR.";
    review of 0d32b712 — it was `str_person_mismatch`, "doesn't match"), and the chip "needs this
    year's STR".
  * no year read — `unconfirmed`, as before: passes the gate, verdict Probable.
  * a LATER year — `future`: does not count, but is never called stale and never blames the family;
    the gate asks for this year's STR with its own neutral code, `str_not_this_year`.
  * proof shown another way (a valid payslip) still carries the household past an old STR.

The suite pins `str_this_year` to 2026 (conftest); the clock tests below opt out with
`real_str_clock` and freeze `timezone.now` instead.
"""
from datetime import datetime, timezone as dt_timezone
from unittest import mock

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student, matched_str_pair

STUDENT_NRIC = '060606-14-1234'
STUDENT = 'Anbu A/L Devaraj'
FATHER, FATHER_NRIC = 'Devaraj A/L Munusamy', '700707-14-5671'
MOTHER = 'Kamala A/P Suppiah'


def _family(route, *, year, status='Lulus', source_type='semakan_status'):
    # 'shortlisted': still in the wizard, so "this year" is TODAY (a submitted case keeps its
    # submission year — `ASubmittedCaseKeepsItsSubmissionYear` stamps one explicitly).
    app = make_application(
        'shortlisted', income_route=route, income_earner='father' if route == 'str' else '',
        income_working_members=['father'] if route == 'salary' else [], father_name=FATHER,
        mother_name=MOTHER, father_occupation='private', mother_occupation='homemaker',
        other_family_members=[], student=make_student(nric=STUDENT_NRIC, name=STUDENT))
    _ic, str_doc = matched_str_pair(app, name=FATHER.upper(), nric=FATHER_NRIC, member='father',
                                    year=year, status=status, source_type=source_type)
    return app, str_doc


def _income_gate(app):
    from apps.scholarship.services import document_red_blockers, income_doc_blockers
    return list(income_doc_blockers(app)) + list(document_red_blockers(app))


def _payslip(app):
    ApplicantDocument.objects.create(
        application=app, doc_type='salary_slip', storage_path='test/salary_slip', household_member='father',
        vision_fields={'fields': {'name': FATHER.upper(), 'nric': FATHER_NRIC, 'gross_income': '2500',
                                  'period': '09/2026'}, 'student_verdict': 'ok', 'error': ''})


def _income_fact(app):
    from apps.scholarship.verdict_engine import build_verdict
    return next(f for f in build_verdict(app) if f['fact'] == 'income')


ROUTES = ('str', 'salary')


class TheCurrencyLadder(TestCase):
    """`_str_currency` against THIS year (2026), every source the extractor emits."""

    def test_each_year_reads_as_the_ruling_says(self):
        from apps.scholarship.income_engine import _str_currency
        rows = [
            # status, year, source → state
            ('Lulus', '2026', 'semakan_status', 'current'),
            ('Lulus', '2026', 'letter', 'current'),
            ('Lulus', '2025', 'semakan_status', 'stale'),
            ('Lulus', '2025', 'letter', 'stale'),
            ('Lulus', '', 'semakan_status', 'unconfirmed'),
            ('Lulus', '2027', 'semakan_status', 'future'),
            ('berjaya', '2027', 'semakan_status', 'future'),   # the live application-status page
            ('Ditolak', '2027', 'semakan_status', 'future'),   # next year's news, not this year's
            # An EARLIER year's rejection is not news about this year (review of 5454063c) → stale.
            ('Ditolak', '2025', 'semakan_status', 'stale'),
            ('Tidak Layak', '2024', 'letter', 'stale'),
            ('Ditolak', '2026', 'semakan_status', 'rejected'),   # this year's rejection: as before
            ('Ditolak', '', 'semakan_status', 'rejected'),       # dateless rejection: as before
            # An earlier year never counts, whether or not its status read (review of 0d32b712).
            ('Dalam proses', '2025', 'semakan_status', 'stale'),
            ('', '2025', 'semakan_status', 'stale'),
            ('', '2025', 'letter', 'stale'),
            ('', '2026', 'semakan_status', 'unreadable'),      # this year, unread: as before
            ('', '', 'semakan_status', 'unreadable'),          # no year, unread: as before
            ('Dalam proses', '2026', 'semakan_status', 'unreadable'),
            # A dashboard still caps at unconfirmed this year — but its year is still read.
            ('Lulus', '2026', 'dashboard', 'unconfirmed'),
            ('Lulus', '', 'dashboard', 'unconfirmed'),
            ('Lulus', '2025', 'dashboard', 'stale'),
            ('Lulus', '2027', 'dashboard', 'future'),
            # Not an STR at all stays wrong_type whatever year it carries.
            ('Lulus', '2027', 'unknown', 'wrong_type'),
            ('Lulus', '2025', 'unknown', 'wrong_type'),
        ]
        for status, year, source, want in rows:
            with self.subTest(status=status, year=year, source=source):
                self.assertEqual(_str_currency(status, year, 2026, source), want)

    def test_the_document_reads_this_year_not_the_cohort_year(self):
        from apps.scholarship.income_engine import student_str_check
        _app, str_doc = _family('str', year='2025')
        self.assertEqual(student_str_check(str_doc)['current_status'], 'stale')


class AnEarlierYearsStrDoesNotCount(TestCase):
    def test_it_blocks_with_the_stale_ask_on_both_routes(self):
        from apps.scholarship.income_engine import salary_income_satisfied, str_not_breached
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        from apps.scholarship.services import consent_blockers
        for route in ROUTES:
            with self.subTest(route=route):
                app, str_doc = _family(route, year='2025')
                self.assertIs(str_not_breached(app), False)
                self.assertIs(salary_income_satisfied(app), False)
                gate = _income_gate(app)
                self.assertIn('str_stale:2025', gate)           # "Your STR is from 2025 …"
                self.assertNotIn('str_person_mismatch', gate)   # never "doesn't match"
                self.assertNotIn('str_not_this_year', gate)
                self.assertIn('str_stale:2025', consent_blockers(app))
                chip = ApplicantDocumentSerializer(str_doc).data['str_check']
                self.assertEqual(chip['current_status'], 'stale')   # "needs this year's STR"

    def test_an_earlier_year_with_an_unread_status_blocks_too(self):
        """Review of 0d32b712: a 2025 page whose status did not read was 'unreadable' — counted by
        `str_not_breached` — so it passed, and even resolved an STR request, where the same page
        saying "Lulus" was blocked. An earlier year never counts, read status or not."""
        from apps.scholarship.income_engine import str_not_breached
        from apps.scholarship.resolution import doc_match_verdict
        for status in ('', 'Dalam proses'):
            for route in ROUTES:
                with self.subTest(status=status, route=route):
                    app, str_doc = _family(route, year='2025', status=status)
                    self.assertIs(str_not_breached(app), False)
                    self.assertIn('str_stale:2025', _income_gate(app))
                    self.assertEqual(doc_match_verdict(str_doc), 'mismatch')   # closes no request

    def test_this_year_or_no_year_with_an_unread_status_is_as_before(self):
        """'unreadable' is now only ever this year's page or a dateless one — unchanged."""
        from apps.scholarship.income_engine import str_not_breached, student_str_check
        for year in ('2026', ''):
            for route in ROUTES:
                with self.subTest(year=year, route=route):
                    app, str_doc = _family(route, year=year, status='')
                    self.assertEqual(student_str_check(str_doc)['current_status'], 'unreadable')
                    self.assertIs(str_not_breached(app), True)
                    self.assertFalse([c for c in _income_gate(app) if c.startswith('str_')])

    def test_the_salary_route_also_asks_for_the_earners_income(self):
        app, _ = _family('salary', year='2025')
        self.assertIn('income_evidence_missing:father', _income_gate(app))

    def test_a_valid_payslip_still_carries_the_household(self):
        """Income shown another way: the old STR is a soft follow-up, as for a rejected one."""
        for route in ROUTES:
            with self.subTest(route=route):
                app, _ = _family(route, year='2025')
                _payslip(app)
                self.assertEqual(_income_gate(app), [])


class ThisYearsStrPasses(TestCase):
    def test_both_routes_pass_as_today(self):
        from apps.scholarship.verdict_narrative import _fact_band
        for route in ROUTES:
            with self.subTest(route=route):
                app, _ = _family(route, year='2026')
                self.assertEqual(_income_gate(app), [])
                if route == 'str':
                    self.assertEqual(_fact_band(_income_fact(app)), 'Certain')

    def test_a_year_that_did_not_read_passes_and_stays_probable(self):
        from apps.scholarship.verdict_narrative import _fact_band
        for route in ROUTES:
            with self.subTest(route=route):
                app, _ = _family(route, year='')
                self.assertEqual(_income_gate(app), [])
                if route == 'str':
                    self.assertEqual(_fact_band(_income_fact(app)), 'Probable')


class ALaterYearsPageDoesNotCountAndBlamesNobody(TestCase):
    """The live case: a 'semakan_status' page read as 2027, status 'berjaya' — next year's APPLICATION."""

    def test_it_is_not_counted_and_is_asked_for_neutrally_on_both_routes(self):
        from apps.scholarship.income_engine import (has_valid_str, household_str_status,
                                                    salary_income_satisfied, str_not_breached)
        from apps.scholarship.services import consent_blockers
        for status in ('berjaya', 'Lulus'):
            for route in ROUTES:
                with self.subTest(status=status, route=route):
                    app, _ = _family(route, year='2027', status=status)
                    self.assertIs(str_not_breached(app), False)
                    self.assertIs(has_valid_str(app), False)
                    self.assertEqual(household_str_status(app), (None, None))
                    self.assertIs(salary_income_satisfied(app), False)
                    gate = _income_gate(app)
                    self.assertIn('str_not_this_year', gate)
                    self.assertNotIn('str_person_mismatch', gate)     # never the stale / mismatch copy
                    self.assertIn('str_not_this_year', consent_blockers(app))

    def test_the_chip_coach_request_and_verdict_never_say_stale(self):
        from apps.scholarship.help_engine import verdict_for_document
        from apps.scholarship.resolution import doc_match_verdict
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        from apps.scholarship.verdict_narrative import _fact_band
        app, str_doc = _family('str', year='2027', status='Lulus')
        self.assertEqual(ApplicantDocumentSerializer(str_doc).data['str_check']['current_status'], 'future')
        self.assertEqual(verdict_for_document(str_doc), 'str_not_current')   # the neutral "show it's approved" coach
        self.assertEqual(doc_match_verdict(str_doc), 'insufficient')         # never closes an ask, never "mismatch"
        fact = _income_fact(app)
        self.assertEqual(_fact_band(fact), 'Unsure')                         # was Certain off a 2027 'Lulus'
        statuses = [i['params'].get('status') for i in fact['unresolved'] if i['code'] == 'str_not_current']
        self.assertEqual(statuses, ['future'])

    def test_a_payslip_still_carries_the_household(self):
        app, _ = _family('salary', year='2027', status='berjaya')
        _payslip(app)
        self.assertEqual(_income_gate(app), [])


def _upload_str(app, *, year, status, source_type='semakan_status'):
    """A re-upload of the household STR (the keep-better guard decides whether it takes the slot)."""
    return ApplicantDocument.objects.create(
        application=app, doc_type='str', storage_path=f'test/str/{ApplicantDocument.objects.count()}',
        vision_run_at=timezone.now(), vision_fields={'fields': {
            'recipient_name': FATHER.upper(), 'recipient_nric': FATHER_NRIC, 'status': status,
            'year': year, 'source_type': source_type}, 'student_verdict': 'ok', 'error': ''})


def _promotes(new_doc, live_doc):
    """The upload path's own decision (views → promotion.should_promote, usable = doc_match_verdict)."""
    from apps.scholarship.promotion import should_promote
    from apps.scholarship.resolution import doc_match_verdict
    return should_promote(new_doc, live_doc, usable=doc_match_verdict(new_doc) not in ('mismatch', 'unreadable'))


class TheKeepBetterGuardByYear(TestCase):
    """Review of 5454063c: the STR re-upload guard ranked by "stale ⇒ approved", no longer true."""

    def test_a_blurred_this_year_upload_replaces_a_live_earlier_year_str(self):
        """Probe: a live 2025 STR (blocked) + a new 2026 upload whose status is blurred (unreadable,
        which counts at the gate) used to be KEPT OUT, leaving the student blocked."""
        app, live = _family('str', year='2025')
        new = _upload_str(app, year='2026', status='')
        self.assertIs(_promotes(new, live), True)

    def test_another_years_page_never_replaces_a_current_or_unconfirmed_str(self):
        for live_year, live_source in (('2026', 'semakan_status'), ('', 'semakan_status')):
            for year, status in (('2025', 'Lulus'), ('2025', ''), ('2027', 'Lulus'), ('2027', 'berjaya')):
                with self.subTest(live_year=live_year, year=year, status=status):
                    app, live = _family('str', year=live_year, source_type=live_source)
                    self.assertIs(_promotes(_upload_str(app, year=year, status=status), live), False)

    def test_an_earlier_years_rejection_is_not_news(self):
        """A 2024 'Ditolak' read `rejected` (quality None: "news, always replace"), so it promoted
        over a live 2026 Lulus and blocked the family. It is now `stale` and stays out."""
        from apps.scholarship.income_engine import str_proof_quality, student_str_check
        app, live = _family('str', year='2026')
        old = _upload_str(app, year='2024', status='Ditolak')
        self.assertEqual(student_str_check(old)['current_status'], 'stale')
        self.assertIsNotNone(str_proof_quality(old))
        self.assertIs(_promotes(old, live), False)

    def test_this_years_rejection_is_still_news(self):
        app, live = _family('str', year='2026')
        self.assertIs(_promotes(_upload_str(app, year='2026', status='Ditolak'), live), True)


def _myt(y, mo, d, h=12, mi=0):
    """A Malaysian wall-clock instant as an aware UTC datetime (MYT = UTC+8)."""
    from datetime import timedelta
    return datetime(y, mo, d, h, mi, tzinfo=dt_timezone.utc) - timedelta(hours=8)


@pytest.mark.usefixtures('real_str_clock')
class ASubmittedCaseKeepsItsSubmissionYear(TestCase):
    """Owner ruling 2026-10-26 (second part): "If the STR was current at the point of submission, we
    let it be, even if by the time the student is considered the date has passed 1 Jan." Clock frozen
    at 2027-01-05 (MYT); the case was submitted on 2026-11-01 with a 2026 STR."""

    NOW = _myt(2027, 1, 5)
    SUBMITTED = _myt(2026, 11, 1)

    def _submitted(self, year='2026', **kw):
        app, str_doc = _family('str', year=year, **kw)
        app.status, app.profile_completed_at = 'profile_complete', self.SUBMITTED
        app.save(update_fields=['status', 'profile_completed_at'])
        return app, str_doc

    def _at_now(self):
        return mock.patch.object(timezone, 'now', return_value=self.NOW)

    def test_a_2026_str_stays_current_everywhere(self):
        from apps.scholarship.help_engine import verdict_for_document
        from apps.scholarship.income_engine import str_this_year
        from apps.scholarship.resolution import doc_match_verdict
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        from apps.scholarship.verdict_narrative import _fact_band
        app, str_doc = self._submitted()
        with self._at_now():
            self.assertEqual(timezone.localdate().year, 2027)          # the year HAS turned
            self.assertEqual(str_this_year(app), 2026)                 # …but this case keeps 2026
            self.assertEqual(ApplicantDocumentSerializer(str_doc).data['str_check']['current_status'],
                             'current')                                # student + officer chips
            self.assertEqual(_income_gate(app), [])
            self.assertEqual(verdict_for_document(str_doc), '')         # no coach
            self.assertEqual(doc_match_verdict(str_doc), 'ok')
            self.assertEqual(_fact_band(_income_fact(app)), 'Certain')  # band unchanged

    @override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
    def test_no_str_request_and_no_re_notify(self):
        from apps.scholarship.resolution import sync_resolution_items
        app, _ = self._submitted()
        with mock.patch.object(timezone, 'now', return_value=self.SUBMITTED):
            sync_resolution_items(app)              # the submission-day sync (the fixture's other asks)
        app.query_raised_notified_at = self.SUBMITTED          # …and the student was told
        app.save(update_fields=['query_raised_notified_at'])
        with self._at_now():
            sync_resolution_items(app)              # the first sync after the year turns
        app.refresh_from_db()
        self.assertFalse(app.resolution_items.filter(code='str_not_current').exists())
        self.assertIsNotNone(app.query_raised_notified_at)     # nothing new → no re-notify email

    @override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
    def test_control_an_str_stale_at_submission_still_raises_the_request(self):
        """The path above is live: a 2025 STR was ALREADY stale at a 2026 submission."""
        from apps.scholarship.resolution import sync_resolution_items
        app, _ = self._submitted(year='2025')
        app.query_raised_notified_at = self.SUBMITTED
        app.save(update_fields=['query_raised_notified_at'])
        with self._at_now():
            sync_resolution_items(app)
        app.refresh_from_db()
        self.assertTrue(app.resolution_items.filter(code='str_not_current').exists())
        self.assertIsNone(app.query_raised_notified_at)

    def test_an_unsubmitted_case_reads_today(self):
        from apps.scholarship.income_engine import student_str_check
        _app, str_doc = _family('str', year='2026')        # still in the wizard (no stamp)
        with self._at_now():
            self.assertEqual(student_str_check(str_doc)['current_status'], 'stale')
            self.assertIn('str_stale:2026', _income_gate(_app))

    def test_a_case_sent_back_to_the_wizard_reads_today_and_resubmission_restamps(self):
        from apps.scholarship.income_engine import str_this_year, student_str_check
        app, str_doc = self._submitted()
        app.status, app.profile_completed_at = 'shortlisted', None      # revert_if_profile_incomplete
        app.save(update_fields=['status', 'profile_completed_at'])
        with self._at_now():
            self.assertEqual(student_str_check(str_doc)['current_status'], 'stale')
            app.status, app.profile_completed_at = 'profile_complete', timezone.now()   # resubmitted
            app.save(update_fields=['status', 'profile_completed_at'])
            self.assertEqual(str_this_year(app), 2027)
            self.assertEqual(student_str_check(str_doc)['current_status'], 'stale')

    def test_an_str_uploaded_after_submission_is_judged_against_the_submission_year(self):
        from apps.scholarship.income_engine import student_str_check
        app, _ = self._submitted(year='2025')
        with self._at_now():
            later = _upload_str(app, year='2026', status='Lulus')       # answering a request
            self.assertEqual(student_str_check(later)['current_status'], 'current')
            newer = _upload_str(app, year='2027', status='Lulus')
            self.assertEqual(student_str_check(newer)['current_status'], 'future')

    def test_the_submission_stamp_wins_over_the_intake_year(self):
        """The stamp decides, not the cohort: an intake labelled 2025 submitted in Nov 2026 → 2026."""
        from apps.scholarship.income_engine import str_this_year
        app, _ = self._submitted()
        app.cohort.year = 2025
        app.cohort.save(update_fields=['year'])
        with self._at_now():
            self.assertEqual(str_this_year(app), 2026)

    def test_a_legacy_submitted_row_with_no_stamp_reads_its_intake_year(self):
        from apps.scholarship.income_engine import str_this_year
        app, _ = _family('str', year='2026')
        app.status = 'interviewing'
        app.save(update_fields=['status'])
        with self._at_now():
            self.assertEqual(str_this_year(app), app.cohort.year)


class TheSeam(TestCase):
    """Every reader of STR currency gets the application's reference year through ONE seam,
    `str_route.str_this_year(application)`, inside `_read_str_check`. No other module may compute
    the currency or the year itself — a reader that did would judge a submitted case by today."""

    def test_only_str_route_computes_str_currency_or_its_year(self):
        import pathlib
        import re
        root = pathlib.Path(__file__).resolve().parents[1]
        pattern = re.compile(r'\b(_str_currency|str_this_year)\(')
        offenders = []
        for path in root.rglob('*.py'):
            rel = path.relative_to(root).as_posix()
            if rel.startswith('tests/') or rel == 'income_engine/str_route.py':
                continue
            if pattern.search(path.read_text(encoding='utf-8')):
                offenders.append(rel)
        self.assertEqual(offenders, [])

    def test_the_seam_is_given_the_application(self):
        import inspect
        from apps.scholarship.income_engine import str_route
        src = inspect.getsource(str_route._read_str_check)
        self.assertIn('str_this_year(app)', src)
        self.assertEqual(len(re_findall(r'_str_currency\(', src)), 1)


def re_findall(pattern, text):
    import re
    return re.findall(pattern, text)


@pytest.mark.usefixtures('real_str_clock')
class TheYearTurnsAtMalaysianMidnight(TestCase):
    """Asia/Kuala_Lumpur is UTC+8: 31 Dec 23:59 MYT = 15:59 UTC; 1 Jan 00:01 MYT = 16:01 UTC."""

    LAST_MINUTE = datetime(2026, 12, 31, 15, 59, tzinfo=dt_timezone.utc)
    FIRST_MINUTE = datetime(2026, 12, 31, 16, 1, tzinfo=dt_timezone.utc)

    def test_this_year_follows_the_malaysian_calendar(self):
        from apps.scholarship.income_engine.str_route import str_this_year
        app, _ = _family('str', year='2026')             # not yet submitted → today
        with mock.patch.object(timezone, 'now', return_value=self.LAST_MINUTE):
            self.assertEqual(str_this_year(app), 2026)
        with mock.patch.object(timezone, 'now', return_value=self.FIRST_MINUTE):
            self.assertEqual(str_this_year(app), 2027)   # still 31 Dec in UTC

    def test_a_2026_str_counts_until_midnight_and_then_is_stale(self):
        app, _ = _family('str', year='2026')
        with mock.patch.object(timezone, 'now', return_value=self.LAST_MINUTE):
            self.assertEqual(_income_gate(app), [])
        with mock.patch.object(timezone, 'now', return_value=self.FIRST_MINUTE):
            self.assertIn('str_stale:2026', _income_gate(app))

    def test_a_2027_page_is_future_until_midnight_and_then_counts(self):
        app, _ = _family('str', year='2027')
        with mock.patch.object(timezone, 'now', return_value=self.LAST_MINUTE):
            self.assertIn('str_not_this_year', _income_gate(app))
        with mock.patch.object(timezone, 'now', return_value=self.FIRST_MINUTE):
            self.assertEqual(_income_gate(app), [])
