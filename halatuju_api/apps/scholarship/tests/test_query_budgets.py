"""Code health H18 — HOW MANY DATABASE QUERIES IT COSTS TO OPEN ONE APPLICANT.

**Why this file exists.** The owner's ruling that started this arc was *"bugs **or
inefficiencies**"*. Slowness creeps in exactly the way bugs do — one reasonable change at a time,
with nothing counting. Every other standard in this repository counts something about the SOURCE;
this one counts something about a REQUEST, which is the only way to see an N+1 at all.

**THE READING, TAKEN 2026-09-20, AND IT IS NOT A HAPPY ONE.** Opening one applicant on the
officer cockpit costs **315 queries** before the applicant has uploaded a single document, and
**385** with three. Roughly **twenty more queries per document**, so a real case with a dozen is
well past six hundred. The bulk of it is one query — ``SELECT … FROM applicant_documents WHERE
application_id = …`` — issued **265 times in the bare case**, from `_latest_doc` helpers deep
inside `verdict_engine`, `income_engine` and `anomaly_engine`, each of which builds a fresh
queryset every time it is asked a question. The verdict engine itself runs more than once per
request (`get_anomalies`, `get_interview_agenda` and `submission_review` each reach it).

**⚠ THIS FILE DOES NOT FIX THAT, ON PURPOSE.** H18's brief allowed a fix only if it were a
one-line `select_related`/`prefetch_related` that changed no behaviour and no response bytes. It
is not: `prefetch_related('documents')` on the view's queryset would be ignored by every one of
those `.filter(...)` calls, because a filtered queryset does not use a prefetched cache. The real
fix is a per-request document cache threaded through the engines — a behaviour-shaped change with
its own risk, its own sprint and its own tests. See TD-282.

**What a budget buys in the meantime.** It stops the number growing while nobody is looking, and
it makes the eventual fix VISIBLE: when the cache lands, these tests fail with "LOWER it to 41",
which is the ratchet catching up with an improvement rather than a number nobody re-measured.

**WHERE THE NUMBERS LIVE.** `halatuju_api/code-standards.json`, in the `query_budgets` ledger of
both `baseline` (frozen) and `budget` (live, and only ever lower). `test_code_standards.py` owns
the RATCHET ARITHMETIC for that ledger — budget may not exceed baseline, the ledger may not gain
a member, a declared `_moved` may relabel a key and buy nothing. This file owns the READING,
because the reading needs a database and `test_code_standards.py` is a `SimpleTestCase`. Neither
half is enough alone and both run in the deploy gate.

**⚠ THE KEY IS A ROUTE PATTERN, NOT A FILE PATH** — `api/v1/admin/…/<int:pk>/::GET::<fixture>`.
That is TD-272's problem in a new dress: rename the route and the entry orphans. `query_budgets`
is therefore a full member of `_moved` (a rename is DECLARED and relabels the frozen entry), but
it is deliberately NOT in `PATH_KEYED_LEDGERS`, because "is `to` a real file?" is the wrong
question for a URL. The right question — "does this pattern still resolve?" — is asked below,
where Django's resolver is available.

**⚠ WHAT THE NUMBER CANNOT SEE.** It is one fixture, on SQLite, through the test client:
  * **the fixture is the floor, not a typical case.** The factory builds no documents, no
    `FundingNeed` and no quiz signals; a live applicant has all three and costs more. That is why
    a SECOND budget is recorded with three documents — the gap between the two IS the N+1, and a
    change that makes documents cheaper or dearer moves it.
  * **it counts queries, not time.** 315 fast queries on one connection is not 315 round trips to
    Cloud SQL, and the production cost is dominated by latency this test cannot measure.
  * **`_fetch_auth_data` (serializers_admin, the profile's Supabase `auth.users` row) is a
    Postgres-only statement.** It raises on SQLite and is swallowed, so it is counted here but its
    result is not what production gets. One query either way.
"""
import json
import os

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
    make_org, make_programme, make_shortlistable_student,
)

#: `…/halatuju_api`. Four levels up from `apps/scholarship/tests/this_file.py`. Derived, never
#: hard-coded — `test_code_standards.py` does the same, for the same reason: a file that changes
#: depth must fail loudly rather than read the wrong JSON.
API_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
BUDGET_PATH = os.path.join(API_ROOT, 'code-standards.json')

#: The Django ROUTE PATTERN, exactly as `resolve()` reports it, and the key stem in the ledger.
APPLICANT_DETAIL_ROUTE = 'api/v1/admin/scholarship/applications/<int:pk>/'
#: One key per (route, method, fixture). The fixture is part of the key because the answer depends
#: on it, and a budget whose fixture is unnamed is a number nobody can reproduce.
BARE = f'{APPLICANT_DETAIL_ROUTE}::GET::no-documents'
WITH_DOCS = f'{APPLICANT_DETAIL_ROUTE}::GET::three-documents'

#: The three documents the second fixture carries — one identity, one academic, one income. Named
#: rather than counted: doc TYPE decides which engine branches run, so "three documents" is only
#: reproducible if it says WHICH three.
THREE_DOCUMENTS = ('ic', 'results_slip', 'str')

#: How far a budget may sit ABOVE the reading before the ratchet demands it be lowered. ZERO, on
#: purpose, and this is stricter than `COUNT_SLACK` in `test_code_standards.py`. A source count
#: drifts with ordinary editing; this number is deterministic — the same fixture through the same
#: endpoint issues the same statements every run — so any slack at all is just room for a
#: regression to hide in after an unrelated improvement.
SHRINK_SLACK = 0


def _budgets():
    with open(BUDGET_PATH, encoding='utf-8') as fh:
        return json.load(fh)['budget']['query_budgets']


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheOfficerApplicantViewQueryBudget(TestCase):
    """One officer, one applicant, one GET — counted."""

    @classmethod
    def setUpTestData(cls):
        cls.budgets = _budgets()

    def _case(self, documents=()):
        """An applicant an officer would actually be reading: an org, its gift, a cohort under it,
        a student the real engine shortlists, and the case at `interviewing` — the stage the
        cockpit is open on. The officer is an `org_admin` fenced to that organisation."""
        org = make_org()
        cohort = make_cohort(programme=make_programme(organisation=org), owning_organisation=org)
        app = make_application('interviewing', cohort=cohort,
                               student=make_shortlistable_student())
        for i, doc_type in enumerate(documents):
            ApplicantDocument.objects.create(
                application=app, doc_type=doc_type,
                storage_path=f'test/{app.id}/{doc_type}-{i}.pdf',
                original_filename=f'test-{doc_type}.pdf')
        client = authed_client(make_admin('org_admin', owning_org=org))
        return client, f'/api/v1/admin/scholarship/applications/{app.id}/'

    def _queries_to_open(self, documents=()):
        client, url = self._case(documents)
        # One warm-up request first. Django's test client and the auth layer each read a row the
        # FIRST time they are used in a test, and counting those would make the budget depend on
        # what ran before it rather than on what this endpoint does.
        self.assertEqual(client.get(url).status_code, 200)
        with CaptureQueriesContext(connection) as captured:
            response = client.get(url)
        self.assertEqual(response.status_code, 200, response.content[:200])
        return len(captured.captured_queries)

    # ── the reading ────────────────────────────────────────────────────────────────────────
    def test_opening_a_bare_applicant_stays_inside_its_budget(self):
        now, limit = self._queries_to_open(), self.budgets[BARE]
        self.assertLessEqual(
            now, limit,
            f'Opening one applicant now costs {now} database queries; the budget is {limit}. '
            f'Something you changed asks the database more often than it used to. ⚠ DO NOT RAISE '
            f'THE BUDGET — it may only go down (and `test_code_standards.py` refuses to let it go '
            f'up). Find the extra read: the usual cause is a helper that builds a fresh queryset '
            f'inside a loop or inside a function the serializer calls once per field.')

    def test_three_documents_stay_inside_their_budget(self):
        now, limit = self._queries_to_open(THREE_DOCUMENTS), self.budgets[WITH_DOCS]
        self.assertLessEqual(
            now, limit,
            f'Opening one applicant WITH {len(THREE_DOCUMENTS)} documents now costs {now} '
            f'queries; the budget is {limit}. This pair of budgets exists to separate a fixed '
            f'cost from a PER-DOCUMENT one: if this fails while the bare reading holds, the new '
            f'work is inside the per-document N+1 and every real applicant pays for it several '
            f'times over.')

    # ── the ratchet, in the direction people forget ────────────────────────────────────────
    def test_a_budget_that_now_sits_above_the_code_is_lowered(self):
        """TIGHTNESS. When the N+1 is fixed these fail, saying by how much — which is the whole
        point. A budget left loose above reality silently re-permits what was just removed."""
        loose = []
        for key, measured in ((BARE, self._queries_to_open()),
                              (WITH_DOCS, self._queries_to_open(THREE_DOCUMENTS))):
            limit = self.budgets[key]
            if limit > measured + SHRINK_SLACK:
                loose.append(f'query_budgets["{key}"]: budget {limit}, code {measured} — '
                             f'LOWER it to {measured}')
        self.assertEqual(
            loose, [],
            'A query budget sits above what the endpoint now costs. Edit "budget" in '
            'halatuju_api/code-standards.json exactly as each line says — this is the ratchet '
            'catching up with your improvement, and leaving it loose gives the next change room '
            'to put the queries back.\n' + '\n'.join(loose))

    # ── the floor ──────────────────────────────────────────────────────────────────────────
    def test_the_budgeted_keys_name_a_route_that_still_resolves(self):
        """The analogue of "a declared move must land on a file that EXISTS" (TD-272). A ledger
        keyed on a route pattern describes nothing the day the route is renamed, and would then
        pass for ever while watching a URL that no longer exists."""
        for key in (BARE, WITH_DOCS):
            route = key.split('::')[0]
            with self.subTest(key=key):
                self.assertEqual(
                    resolve('/' + route.replace('<int:pk>', '1')).route, route,
                    f'"{key}" names the route "{route}", which no longer resolves to itself. '
                    f'Either the route was renamed — DECLARE THE MOVE in the "_moved" array of '
                    f'code-standards.json, which relabels the frozen entry and grants exactly the '
                    f'room it had — or the endpoint is gone and the entry must be removed.')

    def test_the_ledger_holds_the_keys_this_file_measures(self):
        """Without this, deleting a key from `budget` would delete the standard, not the debt:
        `self.budgets[BARE]` would raise a bare KeyError that reads like a broken test."""
        missing = [k for k in (BARE, WITH_DOCS) if k not in self.budgets]
        self.assertEqual(
            missing, [],
            'halatuju_api/code-standards.json has lost a "query_budgets" entry this test '
            'measures. The ledger may only SHRINK when the endpoint it names is gone — removing a '
            'line to silence a failure removes the only thing counting these queries.\n'
            + '\n'.join(missing))


#: The STUDENT's own application read, `GET /api/v1/scholarship/applications/`.
#:
#: ⚠ THE NUMBERS LIVE HERE AND NOT IN `code-standards.json`, AND THAT IS A RULE, NOT A SHORTCUT.
#: `query_budgets` is a frozen H4-era ledger, and `test_code_standards.py` refuses a ledger that
#: GAINS a member — adding a key means editing the frozen `baseline` and re-pinning
#: `BASELINE_SHA256` by hand, which H11 did once and its own retrospective called the way a guard
#: stops being read. So this pair is an ordinary constant with the same two assertions on it: a
#: ceiling that may not be exceeded and a tightness check that fails when the code improves. It
#: is a smaller instrument than the ledger and it says so; raising it to the ledger is TD-286.
STUDENT_READ_ROUTE = 'api/v1/scholarship/applications/'
#: Measured 2026-09-21, after the audit narrowed `income_shown` to the members the web asks about.
#: Before that it was 22 / 25 / 29 — all five of `_MEMBER_ORDER` on every read, at three queries
#: each, on the very call that feeds the student's Documents tab.
STUDENT_READ_BUDGETS = {
    'str-route-no-working-members': 7,
    'salary-route-one-member': 13,
    'salary-route-two-members': 20,
}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheStudentApplicationReadQueryBudget(TestCase):
    """One student, her own application, one GET — counted at three household shapes.

    **Why three shapes and not one.** The cost of this endpoint is dominated by work done PER
    DECLARED EARNER, so a single fixture would pin a number without pinning the slope. The three
    below are the shapes production actually holds: an STR-route family who ticked no working
    member, a salary-route family with one, and one with two. A change that re-broadens the
    per-earner work fails the second and third while the first holds — which is the reading that
    says WHERE it went.

    ⚠ THE LIST ENDPOINT, DELIBERATELY. `ApplicationReadSerializer` runs `many=True` here, and
    this is the call the student's own Documents tab is built from
    (`getMyScholarshipApplications` → `ScholarshipNextSteps` → `ScholarshipDocuments`). A budget
    on a detail route would have missed the multiplier entirely.
    """

    def _read(self, **overrides):
        student = make_shortlistable_student()
        make_application('profile_complete', cohort=make_cohort(), student=student, **overrides)
        client = authed_client(student)
        url = f'/{STUDENT_READ_ROUTE}'
        # One warm-up, for the reason given on the officer budget above.
        self.assertEqual(client.get(url).status_code, 200)
        with CaptureQueriesContext(connection) as captured:
            response = client.get(url)
        self.assertEqual(response.status_code, 200, response.content[:200])
        return len(captured.captured_queries), response.json()

    #: `shape -> the application fields that make it`.
    SHAPES = {
        'str-route-no-working-members': {'income_route': 'str', 'income_earner': 'father',
                                         'income_working_members': []},
        'salary-route-one-member': {'income_route': 'salary',
                                    'income_working_members': ['father']},
        'salary-route-two-members': {'income_route': 'salary',
                                     'income_working_members': ['father', 'mother']},
    }

    def test_each_shape_stays_inside_its_budget(self):
        for shape, overrides in self.SHAPES.items():
            with self.subTest(shape=shape):
                now, limit = self._read(**overrides)[0], STUDENT_READ_BUDGETS[shape]
                self.assertLessEqual(
                    now, limit,
                    f'The student reading her own application ({shape}) now costs {now} database '
                    f'queries; the budget is {limit}. ⚠ DO NOT RAISE IT. The usual cause is a '
                    f'serializer field that derives something per household member — this '
                    f'endpoint serves a LIST, so every such read is paid once per application.')

    def test_a_budget_that_now_sits_above_the_code_is_lowered(self):
        """TIGHTNESS, the direction people forget. A budget left loose above reality silently
        re-permits what was just removed."""
        loose = []
        for shape, overrides in self.SHAPES.items():
            measured, limit = self._read(**overrides)[0], STUDENT_READ_BUDGETS[shape]
            if limit > measured:
                loose.append(f'STUDENT_READ_BUDGETS["{shape}"]: budget {limit}, '
                             f'code {measured} — LOWER it to {measured}')
        self.assertEqual(
            loose, [],
            'A student-read budget sits above what the endpoint now costs. Edit '
            'STUDENT_READ_BUDGETS in this file exactly as each line says — the ratchet catching '
            'up with your improvement.\n' + '\n'.join(loose))

    def test_the_narrowed_field_still_answers_the_members_the_web_asks_about(self):
        """⚠ THE HALF A QUERY COUNT CANNOT SEE. Serving NOTHING would pass every assertion above
        and break the student's income wizard, which reads `income_shown[member]` for each block
        of `salaryMemberBlocks(income_working_members)`. So: the keys are exactly those members,
        and each answer still carries the full documented shape."""
        _n, body = self._read(income_route='salary',
                              income_working_members=['father', 'mother'])
        served = body['applications'][0]['income_shown']
        self.assertEqual(sorted(served), ['father', 'mother'])
        for member, answer in served.items():
            with self.subTest(member=member):
                self.assertEqual(sorted(answer), ['documents', 'shown', 'unusable', 'way'])

    def test_the_budgeted_route_still_resolves(self):
        """The same floor the officer budget carries: a key naming a route that no longer exists
        describes nothing and would pass for ever."""
        self.assertEqual(resolve('/' + STUDENT_READ_ROUTE).route, STUDENT_READ_ROUTE)


#: `verdict_engine._verdict_income` on an STR-route household whose STR did not settle it.
#: Measured 2026-09-21, on the fixture built below.
#:   `discarded` — nothing in the household shows an income, so the fall-through's gate refuses
#:                 and the salary reading is never taken. It used to be COMPUTED first and thrown
#:                 away: 42 queries. Asking the cheap half of the gate first makes it 27.
#:   `taken`     — a readable payslip, so the reading IS the answer. 39 either way: the reorder
#:                 buys nothing here, and that is the proof it is a reorder and not a shortcut.
FALL_THROUGH_BUDGETS = {'discarded': 27, 'taken': 39}


class TestTheStrFallThroughDoesNotPayForAReadingItDiscards(TestCase):
    """How much the "stronger proof is preferred" fall-through costs when it cannot help.

    **The shape of the waste.** `_stronger_income_fact` used to build the ENTIRE salary reading —
    every member's IC, relationship, documents and headroom — and then, most of the time, throw
    it away because the gate refused it. The gate is a conjunction of two pure predicates, so
    asking the cheap one first is a reorder, not a behaviour change; `test_income_evidence_homes`
    §8/§9/§11 are the proof that no answer moved, and this is the proof that the cost did.

    ⚠ A PERFORMANCE FIX IS NOT DONE UNTIL THE MEASUREMENT MOVED (the arc's rule 7). Hence a pair
    of readings rather than one: if a future change makes `discarded` cheap by making `taken`
    wrong, the second number says so.

    ⚠ WHAT THIS DOES NOT FIX. Both numbers are still dominated by `_latest_doc`-shaped helpers
    rebuilding a queryset per member per document type — the same N+1 the officer budget above
    records. That is TD-282 and it needs the per-request document cache, not another reorder.
    """

    def _household(self, payslip=False):
        """An STR-route family whose STR is last year's: the father's IC reads and links him, and
        `income_headroom` can compute because the household has a size. With no payslip nothing
        shows an income, so the fall-through's gate refuses — the discarded case."""
        from apps.scholarship.tests.test_income_evidence_homes import (
            FATHER_NAME, FATHER_NRIC, STUDENT_NAME, _doc, _str_doc)
        from apps.scholarship.tests.factories import make_student
        app = make_application(
            'submitted', cohort=make_cohort(year=2026),
            student=make_student(name=STUDENT_NAME),
            income_route='str', income_earner='father', income_working_members=[],
            father_name=FATHER_NAME, father_occupation='private',
            mother_name='Kamala A/P Suppiah', mother_occupation='homemaker',
            siblings_in_school=0, siblings_in_tertiary=0)
        app.profile.household_size = 5
        app.profile.save(update_fields=['household_size'])
        _doc(app, 'parent_ic', 'father', name=FATHER_NAME, nric=FATHER_NRIC)
        _str_doc(app, status='Lulus', year='2024',
                 recipient_name=FATHER_NAME, recipient_nric=FATHER_NRIC)
        if payslip:
            _doc(app, 'salary_slip', 'father',
                 fields={'gross_income': 'RM 1,800.00', 'net_income': 'RM 1,800.00',
                         'period': '08/2026'})
        return app

    def _cost(self, payslip):
        from apps.scholarship import verdict_engine
        app = self._household(payslip=payslip)
        verdict_engine._verdict_income(app)          # warm the lazy imports
        with CaptureQueriesContext(connection) as captured:
            fact = verdict_engine._verdict_income(app)
        return len(captured.captured_queries), fact['status']

    def test_each_case_stays_inside_its_budget(self):
        for case, payslip in (('discarded', False), ('taken', True)):
            with self.subTest(case=case):
                now, status = self._cost(payslip)
                self.assertEqual(status, 'recommend' if case == 'discarded' else 'verified',
                                 'the fixture stopped exercising the case it is named for')
                self.assertLessEqual(
                    now, FALL_THROUGH_BUDGETS[case],
                    f'The STR fall-through ({case}) now costs {now} queries; the budget is '
                    f'{FALL_THROUGH_BUDGETS[case]}. ⚠ DO NOT RAISE IT. The likely cause is work '
                    f'moved back AHEAD of the gate in `_stronger_income_fact`, so a reading that '
                    f'will be discarded is computed anyway.')

    def test_a_budget_that_now_sits_above_the_code_is_lowered(self):
        loose = []
        for case, payslip in (('discarded', False), ('taken', True)):
            measured = self._cost(payslip)[0]
            if FALL_THROUGH_BUDGETS[case] > measured:
                loose.append(f'FALL_THROUGH_BUDGETS["{case}"]: budget '
                             f'{FALL_THROUGH_BUDGETS[case]}, code {measured} — '
                             f'LOWER it to {measured}')
        self.assertEqual(
            loose, [],
            'A fall-through budget sits above what the engine now costs — the ratchet catching '
            'up with an improvement. If TD-282 has landed, expect both.\n' + '\n'.join(loose))
