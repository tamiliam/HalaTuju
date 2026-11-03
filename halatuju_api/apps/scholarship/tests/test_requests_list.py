"""Requests list R1 (2026-11-03): the paged, tabbed, filtered Requests list.

`GET admin/scholarship/requests/` serves a page of LIGHT rows in the shared pagination envelope
(`requests`, `count`, `page`, ...), the four tab counts in `summary`, and the page's ordered `ids`
for the detail page's Previous / Next. `?group=action|progress|closed|all` picks a tab,
`?kind=bug|feature` the EFFECTIVE kind, `?q=` a title or a request number; `?org=` (TD-228) still
narrows inside the fence.

The tabs PARTITION the list (owner, option A): every request sits in exactly one of Needs action /
In progress / Closed, and All is their sum. Needs action is the SAME rule as the nav badge —
`org_requests_queue.needs_action_q` — and a test here holds the badge and the tab to one number.
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.models import OrgRequest, OrgRequestAnalysis, OrgRequestComment
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org,
)

URL = '/api/v1/admin/scholarship/requests/'
COUNT_URL = '/api/v1/admin/scholarship/requests/count/'

ORG_ROW_KEYS = {'id', 'title', 'kind', 'status', 'submitted_by_name', 'created_at', 'tags'}
OWNER_ROW_KEYS = ORG_ROW_KEYS | {'filed_kind', 'organisation_name'}
ENVELOPE_KEYS = {'count', 'total_pages', 'page', 'page_size', 'next', 'previous', 'requests',
                 'summary', 'ids'}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True)
class _Fixture(TestCase):
    """One organisation's requests in every position a tab can put them, plus one request of a
    second organisation that the first must never see."""

    @classmethod
    def setUpTestData(cls):
        cls.org_a = make_org(code='r1-a', name='Org A')
        cls.org_b = make_org(code='r1-b', name='Org B')
        cls.oa = make_admin('org_admin', owning_org=cls.org_a, name='Asha')
        cls.ob = make_admin('org_admin', owning_org=cls.org_b, name='Bala')
        cls.sup = make_admin('super', super_admin=True, name='Owner')
        base = timezone.now() - timedelta(days=30)
        cls.r = {}

        def req(name, org, by, *, kind='feature', status='submitted', triaged_kind='', title=None):
            row = OrgRequest.objects.create(
                organisation=org, submitted_by=by, kind=kind, status=status,
                triaged_kind=triaged_kind, title=title or f'Request {name}', description='x')
            # Distinct, known creation times: the list's order is newest first.
            OrgRequest.objects.filter(pk=row.pk).update(created_at=base + timedelta(hours=len(cls.r)))
            cls.r[name] = row
            return row

        def question(row):
            OrgRequestComment.objects.create(org_request=row, author_kind='owner',
                                             author_admin=cls.sup, body='Which page?',
                                             visibility='shared', awaiting_reply=True)

        def analysis(row, *, approved=False, superseded=False):
            now = timezone.now()
            OrgRequestAnalysis.objects.create(
                org_request=row, body='read', cited_files=['a.py'],
                approved_at=now if approved else None, approved_by=cls.sup if approved else None,
                superseded_at=now if superseded else None)

        a, oa = cls.org_a, cls.oa
        req('plain', a, oa, kind='bug')                          # untriaged, nobody's question
        req('quoted', a, oa, status='quoted', triaged_kind='feature')
        question(req('asked', a, oa, status='triaged', triaged_kind='feature', title='Export page'))
        question(req('accepted_q', a, oa, status='approved', triaged_kind='feature'))
        req('rebadged', a, oa, kind='feature', status='triaged', triaged_kind='bug')
        analysis(req('feat_ok', a, oa, status='triaged', triaged_kind='feature'), approved=True)
        analysis(req('drafted', a, oa))                          # submitted + a live draft
        analysis(req('analysed', a, oa), approved=True)          # submitted + approved
        analysis(req('withdrawn', a, oa), superseded=True)       # submitted + a withdrawn draft
        req('done', a, oa, status='done', triaged_kind='feature')
        req('declined', a, oa, status='declined')
        req('elsewhere', cls.org_b, cls.ob, kind='bug', title='B secret')

    def get(self, who, query=''):
        r = authed_client(who).get(f'{URL}{query}')
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.json()

    def ids(self, who, query=''):
        return set(self.get(who, query)['ids'])

    def named(self, *names):
        return {self.r[n].id for n in names}


class TestTheEnvelope(_Fixture):
    def test_a_page_is_the_shared_envelope_with_summary_and_ids(self):
        body = self.get(self.oa)
        self.assertEqual(set(body), ENVELOPE_KEYS)
        self.assertEqual(body['ids'], [row['id'] for row in body['requests']])
        self.assertEqual(body['page'], 1)
        self.assertEqual(body['page_size'], 25)

    def test_newest_first_and_no_group_means_everything_the_fence_allows(self):
        body = self.get(self.oa)
        a_rows = [r for n, r in self.r.items() if r.organisation_id == self.org_a.id]
        expected = [r.id for r in sorted(a_rows, key=lambda r: OrgRequest.objects.get(pk=r.pk)
                                         .created_at, reverse=True)]
        self.assertEqual(body['ids'], expected)
        self.assertEqual(body['count'], len(a_rows))

    def test_the_rows_are_light_and_their_keys_are_pinned_per_role(self):
        org_row = self.get(self.oa)['requests'][0]
        owner_row = self.get(self.sup)['requests'][0]
        self.assertEqual(set(org_row), ORG_ROW_KEYS)
        self.assertEqual(set(owner_row), OWNER_ROW_KEYS)

    def test_paging_walks_the_same_order(self):
        whole = self.get(self.oa)['ids']
        first = self.get(self.oa, '?page_size=4')
        second = self.get(self.oa, '?page_size=4&page=2')
        self.assertEqual(first['total_pages'], 3)
        self.assertEqual(first['ids'] + second['ids'], whole[:8])
        # The tab counts are of the whole list, whatever page is open.
        self.assertEqual(first['summary'], second['summary'])

    def test_a_page_past_the_end_is_404(self):
        self.assertEqual(authed_client(self.oa).get(f'{URL}?page=99').status_code, 404)

    def test_dark_the_list_is_404(self):
        with self.settings(REQUESTS_ENABLED=False):
            self.assertEqual(authed_client(self.sup).get(f'{URL}?group=action').status_code, 404)


class TestTheTabsPartitionTheList(_Fixture):
    def test_each_request_sits_in_exactly_one_working_tab_and_all_is_the_sum(self):
        for who in (self.oa, self.sup):
            with self.subTest(role='super' if who is self.sup else 'org_admin'):
                tabs = {g: self.ids(who, f'?group={g}') for g in ('action', 'progress', 'closed')}
                everything = self.ids(who, '?group=all')
                self.assertEqual(tabs['action'] | tabs['progress'] | tabs['closed'], everything)
                self.assertFalse(tabs['action'] & tabs['progress'])
                self.assertFalse(tabs['action'] & tabs['closed'])
                self.assertFalse(tabs['progress'] & tabs['closed'])
                summary = self.get(who)['summary']
                self.assertEqual({g: len(v) for g, v in tabs.items()},
                                 {g: summary[g] for g in tabs})
                self.assertEqual(summary['all'], len(everything))

    def test_needs_action_is_never_a_closed_request(self):
        for who in (self.oa, self.sup):
            with self.subTest(role='super' if who is self.sup else 'org_admin'):
                self.assertFalse(self.ids(who, '?group=action') & self.named('done', 'declined'))

    def test_an_organisation_sees_its_own_untriaged_request_in_progress(self):
        """D1: not waiting on them, not closed — so In progress, never in no tab but All."""
        self.assertIn(self.r['plain'].id, self.ids(self.oa, '?group=progress'))

    def test_the_organisation_needs_to_act_on_a_quote_or_a_question(self):
        self.assertEqual(self.ids(self.oa, '?group=action'),
                         self.named('quoted', 'asked', 'accepted_q'))

    def test_the_owner_needs_to_act_on_untriaged_and_unanalysed_features_never_a_triaged_bug(self):
        """TD-205, read through the list."""
        action = self.ids(self.sup, '?group=action')
        self.assertEqual(action & self.named(*self.r) - self.named('elsewhere'),
                         self.named('plain', 'asked', 'drafted', 'analysed', 'withdrawn'))
        self.assertIn(self.r['elsewhere'].id, action)           # global, and untriaged
        progress = self.ids(self.sup, '?group=progress')
        self.assertIn(self.r['rebadged'].id, progress)          # a triaged BUG waits on nobody
        self.assertIn(self.r['feat_ok'].id, progress)           # analysed: ready to quote

    def test_closed_is_done_and_declined(self):
        self.assertEqual(self.ids(self.oa, '?group=closed'), self.named('done', 'declined'))


class TestTheBadgeAndTheTabAgree(_Fixture):
    """The number on the nav badge is the number on the tab it brings you to — one predicate."""

    def test_the_count_endpoint_equals_the_needs_action_tab_for_both_roles(self):
        for who in (self.oa, self.ob, self.sup):
            with self.subTest(admin=who.name):
                badge = authed_client(who).get(COUNT_URL).json()['count']
                self.assertEqual(badge, self.get(who)['summary']['action'])
                self.assertEqual(badge, len(self.ids(who, '?group=action')))


class TestServedTags(_Fixture):
    def _row(self, who, name, query=''):
        return next(r for r in self.get(who, query)['requests'] if r['id'] == self.r[name].id)

    def test_answer_needed_is_the_organisations_and_follows_the_answer_box(self):
        self.assertEqual(self._row(self.oa, 'asked')['tags'], ['answer_needed'])
        self.assertEqual(self._row(self.oa, 'quoted')['tags'], [])

    def test_an_accepted_request_with_an_open_question_needs_action_but_carries_no_tag(self):
        """Two affordances, two windows (TD-201): it is waiting on the requester — a comment
        settles it — but it has no answer box, so it is in Needs action WITHOUT the tag."""
        self.assertIn(self.r['accepted_q'].id, self.ids(self.oa, '?group=action'))
        self.assertEqual(self._row(self.oa, 'accepted_q')['tags'], [])

    def test_the_owner_sees_the_analysis_tag_on_submitted_requests_only(self):
        self.assertEqual(self._row(self.sup, 'drafted')['tags'], ['analysis_draft'])
        self.assertEqual(self._row(self.sup, 'analysed')['tags'], ['analysed'])
        self.assertEqual(self._row(self.sup, 'withdrawn')['tags'], [])
        self.assertEqual(self._row(self.sup, 'feat_ok')['tags'], [])     # past submitted
        self.assertEqual(self._row(self.sup, 'asked')['tags'], [])       # never the org's tag

    def test_the_organisation_never_receives_an_analysis_tag(self):
        served = {t for r in self.get(self.oa)['requests'] for t in r['tags']}
        self.assertEqual(served, {'answer_needed'})                      # positive: tags flow


class TestKindIsTheFinalClassification(_Fixture):
    def test_the_row_kind_is_the_triage_ruling_and_only_the_owner_sees_what_was_filed(self):
        org_row = next(r for r in self.get(self.oa)['requests'] if r['id'] == self.r['rebadged'].id)
        owner_row = next(r for r in self.get(self.sup)['requests']
                         if r['id'] == self.r['rebadged'].id)
        self.assertEqual(org_row['kind'], 'bug')
        self.assertNotIn('filed_kind', org_row)
        self.assertEqual((owner_row['kind'], owner_row['filed_kind']), ('bug', 'feature'))
        plain = next(r for r in self.get(self.sup)['requests'] if r['id'] == self.r['plain'].id)
        self.assertEqual(plain['filed_kind'], '')

    def test_the_kind_filter_reads_the_effective_kind(self):
        bugs = self.ids(self.oa, '?kind=bug')
        self.assertEqual(bugs, self.named('plain', 'rebadged'))
        self.assertNotIn(self.r['rebadged'].id, self.ids(self.oa, '?kind=feature'))

    def test_the_tab_counts_ignore_kind_and_search_and_count_is_the_filtered_total(self):
        whole = self.get(self.oa)['summary']
        narrowed = self.get(self.oa, '?group=all&kind=bug&q=Request')
        self.assertEqual(narrowed['summary'], whole)
        self.assertEqual(narrowed['count'], len(narrowed['ids']))
        self.assertLess(narrowed['count'], whole['all'])


class TestSearch(_Fixture):
    def test_a_title_matches_in_any_case(self):
        self.assertEqual(self.ids(self.oa, '?q=export'), self.named('asked'))

    def test_a_request_number_matches_with_or_without_the_hash(self):
        rid = self.r['quoted'].id
        self.assertIn(rid, self.ids(self.oa, f'?q={rid}'))
        self.assertIn(rid, self.ids(self.oa, f'?q=%23{rid}'))

    def test_another_organisations_number_finds_nothing_for_an_organisation(self):
        """TD-241: narrowing tested from the widening side."""
        rid = self.r['elsewhere'].id
        self.assertEqual(self.ids(self.oa, f'?q={rid}'), set())
        self.assertEqual(self.ids(self.oa, '?q=B%20secret'), set())
        self.assertEqual(self.ids(self.sup, f'?q={rid}'), {rid})


class TestFiltersAreRefusedNotGuessed(_Fixture):
    def test_an_unknown_group_or_kind_is_400(self):
        for q in ('?group=open', '?kind=chore', '?group=ACTION'):
            with self.subTest(q=q):
                r = authed_client(self.oa).get(f'{URL}{q}')
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.json()['code'], 'bad_filter')


class TestTheCrumbStillNarrowsInsideTheFence(_Fixture):
    def test_a_super_naming_an_organisation_gets_its_list_and_its_counts(self):
        body = self.get(self.sup, '?org=r1-b')
        self.assertEqual(body['ids'], [self.r['elsewhere'].id])
        self.assertEqual(body['summary'], {'action': 1, 'progress': 0, 'closed': 0, 'all': 1})

    def test_an_organisation_naming_another_is_404(self):
        r = authed_client(self.oa).get(f'{URL}?org=r1-b&group=all')
        self.assertEqual(r.status_code, 404)
        self.assertNotIn('B secret', r.content.decode())
