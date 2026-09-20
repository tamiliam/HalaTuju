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
