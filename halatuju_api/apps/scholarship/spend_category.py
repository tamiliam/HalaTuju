"""Give every `BursarySpendTxn` one of the ten categories. **The four-rung ladder.**

Vircle tells us the shop's name and the amount. It never tells us what was bought. Everything in
this module is the consequence of that one sentence.

Requirements: `docs/plans/2026-09-09-sponsor-spending-reports-brief.md` §4c (the ladder) and §4d
(the assumptions note the sponsor card must carry because of rung 3).

────────────────────────────────────────────────────────────────────────────────────────────────
THE LADDER. Each rung sees ONLY what the rung above it could not place.

  1  `duitnow_type`   → `transfer`    the bank's own code, per TRANSACTION
  2  keyword rules    → `rule`        the shop's name says what it sells
  3  spend pattern    → `inferred`    small amounts, visited often → food, per TRANSACTION
  4  the model        → `ai`          merchant NAME STRINGS only, asked once, stored for ever

⚠ **`owner` OUTRANKS ALL FOUR AND IS NEVER OVERWRITTEN.** A person correcting a category is the
top of the ladder; losing that to the next sweep would make the correction screen a lie.

────────────────────────────────────────────────────────────────────────────────────────────────
THE FOUR RULES THIS MODULE EXISTS TO ENFORCE

⚠ **"SENT TO A PERSON" COMES FROM `duitnow_type`, NEVER FROM THE NAME.** Half the real merchants
are registered under an individual's name — `SYAHIR AZHAR` is a stall visited 40 times for RM2.00.
`transfer` is unreachable from rungs 2, 3 and 4 by construction: it is not in `AI_VOCABULARY` and
no keyword rule may name it (`test_spend_category` asserts both).

⚠⚠ **RUNG 3 CLASSIFIES THE TRANSACTION, NOT THE SHOP — AND THE PER-ROW CEILING IS WHY.** A
merchant-level verdict would sweep every row along with it. `AL HUDHA ENTERPRISE` is RM7.20 nine
times **and once RM200**. `TEGUH ENIGMA (MATRIK 1)` is RM0.80 five times **and RM97.70 once**. A
median hides an outlier by design, so without `ROW_CEILING` more than RM300 of large one-off
purchases would have been filed as campus meals and nobody would ever have found out. Both cases
are pinned by name in the tests.

⚠ **THE MODEL NEVER SEES MONEY, A STUDENT, A WALLET OR A DATE.** `ask_model` takes a list of
merchant name strings and nothing else, and a signature test asserts exactly that. This is a
structural wall, not a prompt asking the model to behave — the data is ABSENT rather than merely
unmentioned (`help_engine`'s admin↔student wall, same shape, same reason).

⚠ **A NAME IS ASKED ABOUT ONCE, THEN STORED FOR EVER.** `MerchantCategory` is why the cost falls to
almost nothing: 288 shops produced 1,366 payments in two months, and the shop list grows slowly. A
test asserts the CALL COUNT of the seam, not just the stored value — a stored answer that is still
re-asked is a silent bill.

────────────────────────────────────────────────────────────────────────────────────────────────
TWO STATES THAT LOOK ALIKE AND ARE NOT

  `category=''`          the sorter has never run on this row
  `category='unsorted'`  it ran and honestly could not place it

Never collapse them. `unsorted` is what stops the other nine categories reading as complete when
they are not, and `decided_by=''` beside it is what makes the row eligible for a later re-run when
a new keyword rule lands.
"""
from __future__ import annotations

import logging
import re
import statistics
from dataclasses import dataclass, field
from decimal import Decimal

from .spending_import import DUITNOW_P2P, TX_SPEND, norm_text

logger = logging.getLogger(__name__)

# ── the vocabulary ────────────────────────────────────────────────────────────
#
# ⚠ Held here as plain strings so this module imports without Django. `test_spend_category`
# asserts it is EXACTLY `models.SPEND_CATEGORY_CHOICES`, so the two cannot drift apart.
CATEGORY_CODES: tuple[str, ...] = (
    'food', 'groceries', 'transport', 'study', 'phone', 'hostel', 'health', 'clothing',
    'transfer', 'unsorted',
)

#: What the model may answer. **`transfer` is deliberately absent** (see the docstring) and so is
#: nothing else: `unsorted` is a legitimate answer meaning "I do not know", and storing it is what
#: stops us paying to ask the same unanswerable name every week.
AI_VOCABULARY: frozenset[str] = frozenset(CATEGORY_CODES) - {'transfer'}

BY_DUITNOW = 'duitnow'
BY_RULE = 'rule'
BY_INFERENCE = 'inferred'
BY_MODEL = 'ai'
BY_OWNER = 'owner'

#: Bump on ANY change to `_build_prompt` or `AI_VOCABULARY`. Stamped into `MerchantCategory.reason`
#: so the officer view can tell which answers came from which prompt, and a redesign is visible
#: rather than silently mixed in with the old ones.
PROMPT_VERSION = 'spend-cat-v1'

#: Names per model call. Small enough that one bad batch loses little, large enough that the first
#: run over 288 merchants is a handful of calls.
AI_BATCH_SIZE = 40


# ── rung 2: the merchant's own name ───────────────────────────────────────────
#
# ⚠ **ORDER IS LOAD-BEARING — FIRST MATCH WINS, AND FOOD IS FIRST ON PURPOSE.** `DUNKIN' - BHP
# KARAK` is a doughnut counter inside a petrol station: read as transport it becomes a bus fare.
# `KEDAI RUNCIT KOOP KMP` is a campus co-op, and the brief rules a campus co-op `study`, so the
# co-op keywords sit above the grocery ones.
#
# ⚠ **MATCHING IS WHOLE-WORD, NEVER SUBSTRING.** `GTB - QR POS SMART-ACC SOLUTIONS SDN BHD`
# contains the letters of `MART`, and a substring rule would file an accounting firm as groceries.
#
# ⚠ **ADD FREELY; THIS IS CODE, NOT A GUESS.** A rule is readable in a diff, costs nothing, and is
# re-applied to every already-sorted row on the next `--all` run. Rules marked "not yet in the
# corpus" are forward-looking and covered by their own tests.
KEYWORD_RULES: tuple[tuple[str, str], ...] = (
    # --- food: prepared meals and drinks -------------------------------------
    ('food', 'RESTORAN'), ('food', 'RESTAURANT'),
    ('food', 'CAFE'), ('food', 'KAFE'), ('food', 'KAFETERIA'), ('food', 'CAFETERIA'),
    ('food', 'KITCHEN'), ('food', 'DAPUR'), ('food', 'KOPITIAM'), ('food', 'KEDAI KOPI'),
    ('food', 'BURGER'), ('food', 'PIZZA'), ('food', 'SATAY'), ('food', 'NASI'),
    ('food', 'MAKAN'), ('food', 'SELERA'), ('food', 'CURRY HOUSE'), ('food', 'UNAVAGAM'),
    ('food', 'SAAPADU'), ('food', 'KATERING'), ('food', 'CATERING'), ('food', 'BAKERI'),
    ('food', 'BAKERY'), ('food', 'BAKE'), ('food', 'AISKRIM'), ('food', 'ICE CREAM'),
    ('food', 'YOGURT'), ('food', 'SUSHI'), ('food', 'WAFFLE'), ('food', 'TOAST'),
    ('food', 'COFFEE'), ('food', 'ROAST'), ('food', 'SEAFOOD'), ('food', 'CHICKEN RICE'),
    ('food', 'WESTERN'), ('food', 'AYAM'), ('food', 'PULUT'), ('food', 'APAM BALIK'),
    ('food', 'CHAR KOAY'), ('food', 'FOOD'), ('food', 'GERAI'), ('food', 'PELITA'),
    ('food', 'DUNKIN'), ('food', 'MIXUE'), ('food', 'TEALIVE'), ('food', 'COOLBLOG'),
    ('food', 'BINGXUE'), ('food', 'TAO BIN'), ('food', 'QSR'), ('food', 'VEGETARIAN'),
    ('food', 'FRUITS'), ('food', 'FRUITY'),
    # --- study: the campus co-op, books, printing ----------------------------
    # The brief's two non-obvious rules live here: a co-op plus a campus name is the campus shop.
    ('study', 'KOPERASI'), ('study', 'KOOP'), ('study', 'KOP'), ('study', 'KOPLIBRARY'),
    ('study', 'BUKU'), ('study', 'BOOKSTORE'), ('study', 'STATIONERY'), ('study', 'STATIONEY'),
    ('study', 'ALAT TULIS'), ('study', 'FOTOKOPI'), ('study', 'PERCETAKAN'), ('study', 'CETAK'),
    # --- groceries: sundry shops and supermarkets ----------------------------
    ('groceries', 'SPEEDMART'), ('groceries', 'MART'), ('groceries', 'MINIMART'),
    ('groceries', 'MYDIN'), ('groceries', 'ECONSAVE'), ('groceries', 'PASARAYA'),
    ('groceries', 'PASAR MINI'), ('groceries', 'ECO-SHOP'), ('groceries', 'ECOSHOP'),
    ('groceries', 'KEDAI RUNCIT'), ('groceries', 'RUNCHIT'), ('groceries', 'CONVENIENCE'),
    ('groceries', 'GROCER'), ('groceries', 'SUNDRY'),
    # --- transport -----------------------------------------------------------
    # `KTMB` is the national railway; nothing in the name says so, which is why it is a rule.
    ('transport', 'KTMB'), ('transport', 'RAPID PENANG'), ('transport', 'RAPIDKL'),
    ('transport', 'RAPID KL'), ('transport', 'PRASARANA'), ('transport', 'GRAB'),
    ('transport', 'REDBUS'), ('transport', 'TRANSNASIONAL'), ('transport', 'EKSPRES'),
    ('transport', 'PETRONAS'), ('transport', 'PETRON'), ('transport', 'SHELL'),
    ('transport', 'CALTEX'), ('transport', 'BHP'), ('transport', 'TOUCH N GO'),
    # --- health --------------------------------------------------------------
    ('health', 'FARMASI'), ('health', 'PHARMACY'), ('health', 'WATSON'), ('health', 'GUARDIAN'),
    ('health', 'KLINIK'), ('health', 'CLINIC'), ('health', 'HOSPITAL'), ('health', 'CARING'),
    # --- phone: not yet in the corpus, and the day it appears it must not be food
    ('phone', 'CELCOM'), ('phone', 'MAXIS'), ('phone', 'HOTLINK'), ('phone', 'DIGI'),
    ('phone', 'UMOBILE'), ('phone', 'U MOBILE'), ('phone', 'TUNE TALK'), ('phone', 'TUNETALK'),
    ('phone', 'UNIFI'), ('phone', 'YOODO'), ('phone', 'PREPAID'), ('phone', 'TOPUP'),
    # --- clothing ------------------------------------------------------------
    ('clothing', 'APPAREL'), ('clothing', 'BOUTIQUE'), ('clothing', 'FASHION'),
    ('clothing', 'TUDUNG'), ('clothing', 'KASUT'), ('clothing', 'TEXTILE'),
    # --- hostel: not yet in the corpus ---------------------------------------
    ('hostel', 'ASRAMA'), ('hostel', 'HOSTEL'), ('hostel', 'KOLEJ KEDIAMAN'),
    ('hostel', 'SEWA'), ('hostel', 'TENAGA NASIONAL'), ('hostel', 'SYABAS'),
    ('hostel', 'AIR SELANGOR'), ('hostel', 'INDAH WATER'),
)

_COMPILED_RULES: tuple[tuple[str, re.Pattern], ...] = tuple(
    (category, re.compile(rf'\b{re.escape(keyword)}\b'))
    for category, keyword in KEYWORD_RULES
)


def rule_category(merchant: str) -> str | None:
    """Rung 2. The first keyword rule whose whole word appears in the name, or `None`.

    ⚠ Expects the merchant already normalised by `spending_import.norm_text` (upper-cased,
    whitespace-collapsed) — the same form `BursarySpendTxn.merchant` is stored in.
    """
    name = norm_text(merchant)
    for category, pattern in _COMPILED_RULES:
        if pattern.search(name):
            return category
    return None


# ── rung 3: the spending pattern ──────────────────────────────────────────────

#: A shop must have been visited this many times before its pattern means anything. Two visits is
#: a coincidence.
MIN_VISITS = 3

#: A typical visit at or under this is a meal, not a shop. Measured: the corpus median is RM5.00.
MEDIAN_CEILING = Decimal('8.00')

#: ⚠⚠ **THE LOAD-BEARING NUMBER.** No SINGLE payment above this is a meal, however cheap the shop
#: usually is. See the module docstring — this is what keeps `AL HUDHA ENTERPRISE`'s RM200 and
#: `TEGUH ENIGMA (MATRIK 1)`'s RM97.70 out of the food slice.
ROW_CEILING = Decimal('20.00')


@dataclass(frozen=True)
class MerchantStats:
    """How a shop is used, across every SPEND row we hold for it."""
    visits: int
    median: Decimal


def merchant_stats(pairs) -> dict[str, MerchantStats]:
    """`[(merchant, amount)]` → `{merchant: MerchantStats}`. Pure, so it is testable without a DB."""
    amounts: dict[str, list] = {}
    for merchant, amount in pairs:
        if amount is None:
            continue
        amounts.setdefault(norm_text(merchant), []).append(Decimal(amount))
    return {
        name: MerchantStats(visits=len(values), median=statistics.median(sorted(values)))
        for name, values in amounts.items()
    }


def merchant_looks_like_food(stats: MerchantStats | None) -> bool:
    """Rung 3, the shop half: visited often, and a typical visit is small."""
    return bool(stats and stats.visits >= MIN_VISITS and stats.median <= MEDIAN_CEILING)


def inferred_category(stats: MerchantStats | None, amount) -> str | None:
    """Rung 3, the whole rule — **per TRANSACTION**.

    `food` when the shop looks like a food stall AND this particular payment is at or under
    `ROW_CEILING`. `None` otherwise, which for an over-ceiling row at a food-looking shop means
    the row is honestly `unsorted` rather than wrongly `food`.
    """
    if not merchant_looks_like_food(stats):
        return None
    if amount is None or Decimal(amount) > ROW_CEILING:
        return None
    return 'food'


# ── rung 4: the model ─────────────────────────────────────────────────────────

_AI_SCHEMA = {
    'type': 'object',
    'properties': {
        'merchants': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'category': {'type': 'string', 'enum': sorted(AI_VOCABULARY)},
                },
                'required': ['name', 'category'],
            },
        },
    },
    'required': ['merchants'],
}


def _build_prompt(names) -> str:
    """The rung-4 prompt. **Names only — there is nothing else in scope to leak.**"""
    listed = '\n'.join(f'- {n}' for n in names)
    return (
        'You are sorting Malaysian shop names into spending categories for a student bursary '
        'report. Each name below is a merchant as it appears on a bank statement.\n\n'
        'Answer with exactly one category for each name, from this closed list:\n'
        '  food      - prepared meals, drinks, cafes, stalls, restaurants\n'
        '  groceries - supermarkets, sundry shops, convenience stores, raw food\n'
        '  transport - buses, trains, ride-hailing, petrol, tolls\n'
        '  study     - books, stationery, printing, campus co-operative shops\n'
        '  phone     - mobile top-ups, prepaid, internet\n'
        '  hostel    - rent, utilities, accommodation\n'
        '  health    - pharmacies, clinics, opticians, medicine\n'
        '  clothing  - clothes, shoes, bags, tailoring\n'
        '  unsorted  - you genuinely cannot tell\n\n'
        'Rules:\n'
        '1. Answer "unsorted" rather than guessing. An honest "unsorted" is more useful than a '
        'wrong category.\n'
        '2. Many Malaysian traders register under a personal name. A personal name alone tells '
        'you nothing about what is sold - answer "unsorted".\n'
        '3. Use no category outside the list above.\n\n'
        f'Prompt version: {PROMPT_VERSION}\n\n'
        f'Names:\n{listed}'
    )


def _chunks(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def ask_model(names):
    """Rung 4. `['SHOPEE MARKETPLACE', ...]` → `{'SHOPEE MARKETPLACE': 'groceries', ...}`.

    ⚠⚠ **THIS FUNCTION TAKES A LIST OF NAME STRINGS AND NOTHING ELSE, AND THAT IS THE PRIVACY
    GUARANTEE.** No amount, no student, no wallet id, no date, no application. A signature test
    asserts the parameter list, because a wall the code cannot cross beats a prompt asking it not
    to (`help_engine`, 2026-05-31).

    ⚠ **THE VOCABULARY IS ENFORCED IN PYTHON, AFTER THE ANSWER RETURNS.** Anything outside
    `AI_VOCABULARY`, and any name we did not ask about, is discarded — never re-prompted. A
    deterministic post-processor is testable and cannot perturb the rest of the output
    (Check-1 Academic, 2026-05-31).

    ⚠ Reached through `vision._call_gemini_json`, the ONE Gemini seam, so every test in the repo
    mocks the whole AI surface by patching a single function and CI makes no billable call.
    """
    from . import usage
    from .vision import _call_gemini_json

    wanted = [n for n in (norm_text(x) for x in names) if n]
    out: dict[str, str] = {}
    for chunk in _chunks(wanted, AI_BATCH_SIZE):
        asked = set(chunk)
        with usage.usage_context(source='spend_category'):
            data = _call_gemini_json(_build_prompt(chunk), _AI_SCHEMA)
        if not isinstance(data, dict) or '_error' in data:
            # ⚠ A model failure is NOT a category. The names stay undecided and are asked again
            # next run; filing them as `unsorted` would store the outage as an answer for ever.
            logger.warning('spend_category: model call failed for %d names: %s',
                           len(chunk), (data or {}).get('_error') if isinstance(data, dict) else data)
            continue
        for item in data.get('merchants') or []:
            if not isinstance(item, dict):
                continue
            name = norm_text(item.get('name'))
            category = str(item.get('category') or '').strip().lower()
            if name in asked and category in AI_VOCABULARY:
                out[name] = category
    return out


# ── the whole ladder, over the stored transactions ────────────────────────────

@dataclass
class SortReport:
    """What one sorting run decided. **Every rung is counted and the counts must add up.**

    ⚠ The totals are printed in full and read before `--apply`. An aggregate over messy input that
    does not print what it could not place reports a smaller, entirely plausible number — this
    corpus already cost us RM621 that way once.
    """
    rows_considered: int = 0
    by_rung: dict = field(default_factory=dict)          # decided_by -> row count
    rows_unsorted: int = 0
    rows_over_ceiling: int = 0                           # food-looking shop, payment too large

    merchants_seen: int = 0
    merchants_by_rung: dict = field(default_factory=dict)
    merchants_asked: int = 0                             # names actually sent to the model
    merchants_answered: int = 0

    owner_rows_untouched: int = 0
    applied: bool = False

    def note_row(self, decided_by: str) -> None:
        self.by_rung[decided_by] = self.by_rung.get(decided_by, 0) + 1

    def note_merchant(self, decided_by: str) -> None:
        self.merchants_by_rung[decided_by] = self.merchants_by_rung.get(decided_by, 0) + 1

    def lines(self) -> list[str]:
        """Human-readable. Names merchants — never a student, a wallet or an amount."""
        out = [
            f'applied              : {self.applied}',
            f'rows considered      : {self.rows_considered}',
            f'rows left unsorted   : {self.rows_unsorted}',
            f'  of which over the RM{ROW_CEILING} ceiling at a food-looking shop: '
            f'{self.rows_over_ceiling}',
            f'owner rows untouched : {self.owner_rows_untouched}',
            'rows by rung:',
        ]
        out += [f'  {k or "(undecided)"}: {v}' for k, v in sorted(self.by_rung.items())]
        out += [
            f'merchants seen       : {self.merchants_seen}',
            'merchants by rung:',
        ]
        out += [f'  {k or "(undecided)"}: {v}' for k, v in sorted(self.merchants_by_rung.items())]
        out += [
            f'merchants asked      : {self.merchants_asked}',
            f'merchants answered   : {self.merchants_answered}',
        ]
        return out


def _stored_verdicts():
    from .models import MerchantCategory

    return {
        m: (c, d) for m, c, d in
        MerchantCategory.objects.values_list('merchant', 'category', 'decided_by')
    }


def merchant_verdicts(merchants, stats, stored, *, use_ai=True, report=None):
    """Decide each merchant's category, one rung at a time. Pure apart from the model call.

    Returns `{merchant: (category, decided_by)}` for every merchant that any rung could place.
    A merchant absent from the result was placed by nothing, and its rows become `unsorted`.

    ⚠ **RUNG ORDER, AND WHY EACH SITS WHERE IT DOES:**
      * a stored `owner` verdict is returned untouched and nothing below it runs;
      * a keyword rule is RE-DERIVED every run, deliberately — it is deterministic and free, so a
        newly added rule reaches merchants that an earlier run had already stored;
      * rung 3 outranks a stored `ai` verdict, because a shop that has since accumulated a food
        pattern is better evidence than a guess made from its name alone;
      * a stored `ai` verdict is USED AND NEVER RE-ASKED. That is the whole cost design.
    """
    verdicts: dict[str, tuple[str, str]] = {}
    unplaced: list[str] = []

    for merchant in merchants:
        prior = stored.get(merchant)
        if prior and prior[1] == BY_OWNER:
            verdicts[merchant] = prior
            continue
        by_rule = rule_category(merchant)
        if by_rule:
            verdicts[merchant] = (by_rule, BY_RULE)
            continue
        if merchant_looks_like_food(stats.get(merchant)):
            # ⚠ Recorded at merchant level so rung 4 never pays to ask about it. The CEILING is
            # applied per transaction, later, in `sort_transactions`.
            verdicts[merchant] = ('food', BY_INFERENCE)
            continue
        if prior:
            verdicts[merchant] = prior
            continue
        unplaced.append(merchant)

    if report is not None:
        report.merchants_seen = len(merchants)
        for category, decided_by in verdicts.values():
            report.note_merchant(decided_by)

    if unplaced and use_ai:
        if report is not None:
            report.merchants_asked = len(unplaced)
        answers = ask_model(unplaced)
        if report is not None:
            report.merchants_answered = len(answers)
        for merchant, category in answers.items():
            verdicts[merchant] = (category, BY_MODEL)
            if report is not None:
                report.note_merchant(BY_MODEL)
    return verdicts


def sort_transactions(*, apply=False, resort=False, use_ai=True) -> SortReport:
    """Run the ladder over the stored transactions. **Report-first by default.**

    `resort=False` (the default) considers only rows nothing has decided yet — `decided_by=''`,
    which covers both a never-sorted row and one an earlier run left honestly unplaced.
    `resort=True` re-considers every row **except** an `owner` one.

    ⚠ `apply=False` MUST BE UNABLE TO WRITE, not merely choose not to. There is exactly one
    `bulk_update` and one `update_or_create` loop, both behind the flag, and a test asserts nothing
    changed after a report run.
    """
    from django.db import transaction as db_transaction

    from .models import BursarySpendTxn, MerchantCategory

    report = SortReport(applied=bool(apply))
    stored = _stored_verdicts()

    # Stats come from EVERY successful spend row we hold, not from the rows being sorted — a
    # merchant's pattern is a property of the merchant, and narrowing to this batch would make the
    # third visit look like a first one.
    # Deliberately platform-wide: this is the nightly SORTER, not an admin surface. A
    # merchant category is a fact about a shop, decided once for everyone; the fence
    # lives on the screens that read the result. ⚠ The pragma is the LAST line before
    # the query - the guard looks 200 characters.
    # org-fence: NONE, by design (the nightly sorter).
    stats = merchant_stats(
        BursarySpendTxn.objects.filter(tx_type=TX_SPEND).values_list('merchant', 'amount')
    )

    # Deliberately platform-wide: this is the nightly SORTER, not an admin surface. A
    # merchant category is a fact about a shop, decided once for everyone; the fence
    # lives on the screens that read the result. ⚠ The pragma is the LAST line before
    # the query - the guard looks 200 characters.
    # org-fence: NONE, by design (the nightly sorter).
    rows = BursarySpendTxn.objects.exclude(decided_by=BY_OWNER)
    if not resort:
        rows = rows.filter(decided_by='')
    rows = list(rows.only('id', 'merchant', 'amount', 'duitnow_type', 'category', 'decided_by'))
    # org-fence: NONE, deliberately - the sorter counts across the platform (see above).
    report.owner_rows_untouched = BursarySpendTxn.objects.filter(decided_by=BY_OWNER).count()

    # ⚠ Rung 1 is per ROW, so a person-transfer row never contributes its merchant to rung 4 — we
    # must not pay to ask the model about somebody's name.
    merchants = sorted({r.merchant for r in rows if r.duitnow_type != DUITNOW_P2P and r.merchant})
    verdicts = merchant_verdicts(merchants, stats, stored, use_ai=use_ai, report=report)

    changed = []
    for row in rows:
        report.rows_considered += 1
        if row.duitnow_type == DUITNOW_P2P:
            category, decided_by = 'transfer', BY_DUITNOW
        else:
            verdict = verdicts.get(row.merchant)
            if verdict and verdict[1] == BY_INFERENCE:
                # The ceiling lives HERE, on the transaction, and nowhere else.
                if inferred_category(stats.get(row.merchant), row.amount):
                    category, decided_by = 'food', BY_INFERENCE
                else:
                    category, decided_by = 'unsorted', ''
                    report.rows_over_ceiling += 1
            elif verdict:
                category, decided_by = verdict
            else:
                category, decided_by = 'unsorted', ''
        if category == 'unsorted' and decided_by == '':
            report.rows_unsorted += 1
        report.note_row(decided_by)
        if (row.category, row.decided_by) != (category, decided_by):
            row.category, row.decided_by = category, decided_by
            changed.append(row)

    if apply:
        with db_transaction.atomic():
            if changed:
                # org-fence: NONE, deliberately - the sorter writes across the platform.
                BursarySpendTxn.objects.bulk_update(
                    changed, ['category', 'decided_by'], batch_size=500)
            for merchant, (category, decided_by) in verdicts.items():
                if decided_by == BY_OWNER:
                    continue
                MerchantCategory.objects.update_or_create(
                    merchant=merchant,
                    defaults={
                        'category': category,
                        'decided_by': decided_by,
                        'reason': PROMPT_VERSION if decided_by == BY_MODEL else '',
                    },
                )
    return report
