"""The BigQuery query behind the GCP half of the cost ledger (2026-09-11).

⚠ **THIS FILE EXISTS BECAUSE THE LEDGER OVERSTATED THE BILL BY 29% FOR SIX WEEKS.**

`sync_gcp_costs` shipped on 2026-07-26 and was run exactly once, on June. It recorded RM88.44.
Google actually charged RM68.36. Nothing caught it, because nobody had ever compared the pull to
a statement — and the only reason it surfaced at all is that the owner supplied the July and
August PDFs on 2026-09-11 and they were read line by line.

Two separate mistakes, each of which inflates the figure on its own:

1. **`DATE(usage_start_time)` instead of `invoice.month`.** Google decides which invoice a usage
   record belongs to and stamps it on the row. Re-deciding it from the usage timestamp splits
   usage that straddles the last midnight of the month into the wrong invoice. It produced
   RM106.76 for a July bill of RM106.49 — close enough to look right and equal to nothing Google
   ever sent.
2. **`SUM(cost)` instead of `cost + credits`.** `cost` is list price. Free-tier allowances and
   committed-use discounts arrive as NEGATIVE entries in the `credits` array, and they are a
   fifth to a quarter of this bill every single month.

There is no BigQuery in a test run, so what is pinned here is the SQL itself — the two clauses
whose absence caused the overstatement — plus the three months of arithmetic that were verified
against the real statements by hand:

    invoice month   gross     credits    net      statement
    202606          89.07     -20.71     68.36    68.36
    202607         106.49     -21.34     85.15    85.15
    202608          28.95      -5.03     23.92    23.92
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.scholarship.management.commands import sync_gcp_costs

# The real figures, checked against the real Google Cloud statements on 2026-09-11.
VERIFIED = [
    # (invoice month, gross, credits, statement's "total new activity")
    ('2026-06', Decimal('89.07'), Decimal('-20.71'), Decimal('68.36')),
    ('2026-07', Decimal('106.49'), Decimal('-21.34'), Decimal('85.15')),
    ('2026-08', Decimal('28.95'), Decimal('-5.03'), Decimal('23.92')),
]


class TestTheFormulaMatchesTheStatements(SimpleTestCase):
    def test_cost_plus_credits_reproduces_every_statement(self):
        for month, gross, credits, stated in VERIFIED:
            with self.subTest(month=month):
                self.assertEqual(gross + credits, stated)

    def test_ignoring_credits_overstates_every_one_of_them(self):
        """The shape of the old bug: never smaller, always larger, always plausible."""
        for month, gross, _credits, stated in VERIFIED:
            with self.subTest(month=month):
                self.assertGreater(gross, stated)

    def test_june_the_only_month_ever_synced_was_out_by_a_quarter(self):
        """RM88.44 was sitting in the production ledger. Google charged RM68.36."""
        _m, gross, credits, stated = VERIFIED[0]
        overstatement = (gross - stated) / stated
        self.assertGreater(overstatement, Decimal('0.25'))
        self.assertEqual(gross + credits, stated)


class TestTheQueryItself(SimpleTestCase):
    """Pinning the two clauses whose absence caused the overstatement. There is no BigQuery in a
    test run, so the SQL text is the only thing that can carry this."""

    def _source(self):
        import inspect
        return inspect.getsource(sync_gcp_costs.Command._query)

    def _sql(self):
        """Just the SQL, not the comments around it.

        The comments deliberately NAME the old column so the next reader knows what was wrong,
        so a plain source search would find `usage_start_time` in the explanation of why it is
        gone. The assertion has to be about the query the database actually receives.
        """
        src = self._source()
        start = src.index('sql = f"""') + len('sql = f"""')
        return src[start:src.index('"""', start)]

    def test_it_groups_by_googles_own_invoice_month(self):
        self.assertIn('invoice.month', self._source())
        # ⚠ And explicitly NOT the thing it used to do. Named so that reverting to the usage
        # timestamp fails here rather than six weeks later against a statement.
        self.assertNotIn('usage_start_time', self._sql())

    def test_it_nets_off_credits(self):
        sql = self._sql()
        self.assertIn('UNNEST(credits)', sql)
        self.assertIn('SUM(cost)', sql)

    def test_it_still_scopes_to_the_halatuju_project_by_default(self):
        """The billing account carries sibling products. The filter is what keeps 'HalaTuju is
        ~99.7% of GCP' true if one of them ever grows."""
        self.assertEqual(sync_gcp_costs.DEFAULT_PROJECT, 'gen-lang-client-0871147736')
        # Built into `where` rather than written inside the SQL literal, so this reads the source.
        self.assertIn('project.id = @project', self._source())
