"""The intake year's stated window — `opens_on` / `closes_on` (gift setup flow, 2026-09-06).

⚠⚠ THE ONE THING EVERY TEST HERE EXISTS TO PROTECT: **THESE DATES DESCRIBE. THEY OPEN NOTHING.**

Owner ruling, 2026-09-06, taken against the alternative of a scheduled job that opens the round on
the start date. Two reasons, and the second is the durable one:

  1. `is_open` already means "real students can walk in" (`docs/decisions.md`, Sabah S2b). A date
     that ALSO opened would be a second switch that can disagree with the first.
  2. **A clock can fire before setup is finished.** Create a gift, type a start date, get
     interrupted, and on that date the round opens with no rules set and no questions configured.
     A person pressing Open cannot do that by accident.

If a timer is ever wanted it is a job built ON TOP of these columns, argued on its own merits then.
It is not a reinterpretation of them — and `test_a_past_opens_on_does_NOT_open_the_round` is what
would fail if somebody quietly made it one.
"""
from datetime import date

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.models import Programme, ScholarshipCohort
from apps.scholarship.tests.test_api import TEST_JWT_SECRET, _make_token


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestIntakeWindow(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(
            code='win-org', name='Win Org', is_active=True)
        cls.prog = Programme.objects.create(
            organisation=cls.org, code='win-gift', name_en='Win Gift', is_active=True)
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='win-admin', email='win-admin@example.com', name='Win Admin',
            role='org_admin', is_super_admin=False, is_active=True, owning_organisation=cls.org)

    def setUp(self):
        self.client = APIClient()

    def _auth(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {_make_token(self.admin.supabase_user_id)}')

    def _create(self, **extra):
        self._auth()
        body = {'code': 'win-2027', 'name': 'Win 2027', 'year': 2027}
        body.update(extra)
        return self.client.post(
            f'/api/v1/admin/scholarship/programmes/{self.prog.id}/years/',
            body, format='json')

    def _year(self, **kw):
        defaults = dict(programme=self.prog, owning_organisation=self.org, code='win-y',
                        name='Win Y', year=2027, is_active=True, is_open=False)
        defaults.update(kw)
        return ScholarshipCohort.objects.create(**defaults)

    def _patch(self, cohort, body):
        self._auth()
        return self.client.patch(
            f'/api/v1/admin/scholarship/intake-years/{cohort.id}/', body, format='json')

    # ── the ruling ───────────────────────────────────────────────────────────────────────────

    def test_a_past_opens_on_does_NOT_open_the_round(self):
        """⚠ THE LOAD-BEARING TEST. A window that has already begun still leaves the round CLOSED,
        because opening is a person's deliberate press and nothing else."""
        r = self._create(opens_on='2020-01-01', closes_on='2020-12-31')
        self.assertEqual(r.status_code, 201)
        c = ScholarshipCohort.objects.get(code='win-2027')
        self.assertFalse(c.is_open)
        self.assertEqual(c.opens_on, date(2020, 1, 1))

    def test_a_past_closes_on_does_NOT_close_an_open_round(self):
        """The same rule in the other direction — a lapsed window never shuts a live intake, or a
        forgotten date would silently stop real applications mid-round."""
        c = self._year(is_open=True, closes_on=date(2020, 1, 1))
        c.refresh_from_db()
        self.assertTrue(c.is_open)

    # ── NULL is a real answer ────────────────────────────────────────────────────────────────

    def test_a_round_with_no_window_is_normal_not_broken(self):
        """No backfill was run, so every row that predates these columns has NULL — the live 2026
        intake among them. Inventing dates for a round that already ran would be fiction on an
        audited row, so blank must read as "not stated", never as an error."""
        r = self._create()
        self.assertEqual(r.status_code, 201)
        c = ScholarshipCohort.objects.get(code='win-2027')
        self.assertIsNone(c.opens_on)
        self.assertIsNone(c.closes_on)
        self.assertIsNone(r.data['opens_on'])
        self.assertIsNone(r.data['closes_on'])

    def test_a_window_can_be_withdrawn_after_it_is_stated(self):
        """Three states per field, and the middle one is the point: absent leaves it alone, an
        empty value CLEARS it, a date sets it. Without an explicit clear there is no way to take
        back a window once stated, and a date somebody can only ever change is a trap."""
        c = self._year(opens_on=date(2027, 3, 1), closes_on=date(2027, 4, 30))
        self.assertEqual(self._patch(c, {'opens_on': None}).status_code, 200)
        c.refresh_from_db()
        self.assertIsNone(c.opens_on)
        self.assertEqual(c.closes_on, date(2027, 4, 30))   # untouched — absent means leave alone

    def test_a_patch_that_mentions_neither_date_changes_neither(self):
        c = self._year(opens_on=date(2027, 3, 1), closes_on=date(2027, 4, 30))
        self.assertEqual(self._patch(c, {'name': 'Renamed'}).status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.opens_on, date(2027, 3, 1))
        self.assertEqual(c.closes_on, date(2027, 4, 30))

    # ── it refuses, it does not swap ─────────────────────────────────────────────────────────

    def test_a_backwards_window_is_REFUSED_never_silently_swapped(self):
        """A silent swap turns a typo into a stated fact nobody was told about, on dates students
        are shown."""
        r = self._create(opens_on='2027-06-01', closes_on='2027-03-01')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'window_backwards')
        self.assertFalse(ScholarshipCohort.objects.filter(code='win-2027').exists())

    def test_the_order_check_reads_the_RESULT_not_just_the_payload(self):
        """⚠ PATCHING ONE DATE IS VALIDATED AGAINST THE ONE ALREADY STORED. Checking the payload
        alone would let two individually-valid edits arrive in sequence and leave the row
        backwards — the classic partial-update hole."""
        c = self._year(opens_on=date(2027, 6, 1))
        r = self._patch(c, {'closes_on': '2027-03-01'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'window_backwards')
        c.refresh_from_db()
        self.assertIsNone(c.closes_on)

    def test_clearing_the_start_lets_an_otherwise_backwards_end_through(self):
        """The same reading, proving it is the RESULT being judged: with no start date there is no
        order to violate."""
        c = self._year(opens_on=date(2027, 6, 1))
        r = self._patch(c, {'opens_on': None, 'closes_on': '2027-03-01'})
        self.assertEqual(r.status_code, 200)
        c.refresh_from_db()
        self.assertIsNone(c.opens_on)
        self.assertEqual(c.closes_on, date(2027, 3, 1))

    def test_the_same_day_is_a_valid_window(self):
        r = self._create(opens_on='2027-03-01', closes_on='2027-03-01')
        self.assertEqual(r.status_code, 201)

    def test_an_unreadable_date_is_refused_by_FIELD(self):
        """Named per field so the screen can point at the box that is wrong."""
        r = self._create(opens_on='the first of March')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'opens_on')

    # ── it is serialised beside `is_open`, never instead of it ───────────────────────────────

    def test_the_row_carries_the_window_AND_the_switch(self):
        c = self._year(is_open=True, opens_on=date(2027, 3, 1), closes_on=date(2027, 4, 30))
        self._auth()
        body = self.client.get(
            f'/api/v1/admin/scholarship/programmes/{self.prog.id}/years/').json()
        row = next(r for r in body['years'] if r['code'] == 'win-y')
        self.assertEqual(row['opens_on'], '2027-03-01')
        self.assertEqual(row['closes_on'], '2027-04-30')
        # `is_open` is what decides whether a student may apply; the dates only say when the round
        # is MEANT to run. Both travel, so no screen has to infer one from the other.
        self.assertTrue(row['is_open'])
