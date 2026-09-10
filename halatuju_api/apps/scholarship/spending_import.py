"""Read a Vircle "Bursary Usage Report" and turn it into `BursarySpendTxn` rows.

The reports are exported from Vircle's Data Studio **by hand** by a BrightPath officer and dropped
into Drive `01 BrightPath/03 Payments, Vircle/06 Student Spending`. Everything hard about this
module comes from that sentence: the file shape has drifted four times in eight weeks, the upload
does not happen on a fixed day, and nothing about a bad file announces itself.

Plan + measurements: `docs/plans/2026-09-09-sponsor-spending-reports-brief.md` §0/§0b and
`docs/plans/2026-09-10-sponsor-spending-roadmap.md`.

────────────────────────────────────────────────────────────────────────────────────────────────
WHAT THE REAL CORPUS TAUGHT US (eight reports, 5 Jul – 30 Aug 2026, 1,368 unique transactions)

⚠ **FOUR THINGS HAVE ALREADY CHANGED MID-STREAM.** Not hypothetical drift — measured:
  1. The merchant column is `Receiver` in old files and `Merchant Name` in new ones.
  2. The student column is `BrightPath name` in the oldest two, `Wallet User` + `Child User` after.
  3. `amount` is a NUMBER in 1,280 rows and the STRING `"RM26.90"` in 88 — in the same corpus.
  4. `transaction_date` carries a TIME in the oldest two (`"5 Jul 2026, 15:14:59"`) and not after.

⚠ **A FIFTH: THE FILENAME IS NOT THE COVERAGE WINDOW.** The 26 July report covers FOURTEEN days
(13–26 Jul) while every other covers seven. So a missing FILE is not a missing WEEK, and coverage
is derived from `transaction_date` values — never from filenames or a file count.

⚠ **THE WEEKLY EXPORTS CAN OVERLAP.** 186 transaction ids appear twice: the 2 August export was
pulled with its date range a week early and re-included all of 26 July. Every repeated pair was
byte-identical, so first-copy-wins is safe — but a repeat that DISAGREES is a corrected figure and
must be surfaced, never silently dropped.

────────────────────────────────────────────────────────────────────────────────────────────────
THE RULES THIS MODULE EXISTS TO ENFORCE

⚠ **A MISSING REQUIRED COLUMN STOPS THE FILE.** It does not fall back to a position, a neighbouring
name, or a guess. Parsing on past a header we cannot read is how a payment gets attributed to the
wrong student — silently, on a real person's record. An UNKNOWN EXTRA column is different: it
cannot misattribute anything, so it is reported and the file still loads.

⚠ **NOTHING IS SILENTLY DROPPED, AND THE SKIPS ARE COUNTED.** An amount that will not parse is not
skipped quietly: it is counted and listed. This rule is written in blood — the first analysis of
this corpus summed only the values that were already numeric, silently lost the 88 string amounts,
and reported RM10,029.03 for a true RM10,650.22. **A sum that skips what it cannot parse reports a
smaller number that looks entirely plausible.**

⚠ **THE STUDENT'S NAME IN THE REPORT IS NEVER STORED.** It is read for one purpose — to cross-check
that the wallet we matched belongs to who we think — and then discarded. The join is
`wallet_id → ScholarshipApplication.vircle_id`.

⚠ **`Wallet User` IS NOT ALWAYS THE STUDENT.** Vircle will not let someone born after 2008 hold
their own account: a parent registers and the student is added as a CHILD (`STATUS_PARENT_ACCOUNT`
in `sheets.py`). On such a wallet the parent is `Wallet User` and the student is `Child User` —
populated on 28 of the 1,368 real rows, so this is live, not hypothetical.

⚠ **`Entry Type` READS `CREDIT` ON A SPEND.** It is the counterparty's view of the ledger. Gate on
`TX Type`, never on the word that sounds right.

⚠ **NON-SPEND ROWS ARE STORED, NOT DISCARDED.** Two rows in the corpus are `RECEIVED` (money into a
wallet from a person). Filtering them out at read time would make the store unable to answer a
question it was given the data for. Readers narrow; the importer does not.

────────────────────────────────────────────────────────────────────────────────────────────────
THE SEAM S2 WILL REUSE

`rows_from_values(header, value_rows, source)` is the whole parser and takes plain lists. The local
`.xlsx` path (`rows_from_xlsx`) and the Drive/Sheets path S2 adds are both thin adapters onto it,
so the drift rules above cannot end up implemented twice.

**openpyxl is imported LAZILY and is deliberately NOT in `requirements.txt`** — the same shape as
`sheets.py`'s Google client imports. Reading a local `.xlsx` is a laptop operation; the service
reads the Sheets API, which hands back values with no spreadsheet library at all.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

_CENTS = Decimal('0.01')

# ── column resolution ─────────────────────────────────────────────────────────
#
# Field name → every header Vircle has used for it, newest first. Matching is case-insensitive and
# whitespace-normalised, because a header row is typed by whoever built the Data Studio export.
#
# ⚠ ADD, NEVER REPLACE. An old report must keep loading after a rename: the archive is the history,
# and `--from-the-start` re-reads all of it. The day `Merchant Name` becomes something else, that
# name joins the front of the tuple and `Receiver` stays where it is.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    'txn_date': ('transaction_date',),
    'wallet_id': ('wallet_id',),
    'txn_id': ('transaction_id',),
    'merchant': ('merchant name', 'receiver'),
    'holder_name': ('wallet user', 'brightpath name'),
    'child_name': ('child user',),
    'duitnow_type': ('duitnow_type',),
    'entry_type': ('entry type',),
    'tx_type': ('tx type',),
    'amount': ('amount',),
    'status': ('status',),
}

#: Without ANY ONE of these a row cannot be filed safely, so the file stops.
#: `holder_name` is required because it is the cross-check on the wallet match; `child_name` is
#: NOT, because the two oldest reports predate the column and are still correct without it.
REQUIRED_FIELDS = ('txn_date', 'wallet_id', 'txn_id', 'merchant', 'holder_name',
                   'duitnow_type', 'tx_type', 'amount', 'status')

#: Headers we have seen, do not use, and do not want reported every single run.
#: `Sender` existed in the two oldest reports and was dropped by Vircle; `Entry Type` is read but
#: never gated on (see the module docstring).
KNOWN_UNUSED_HEADERS = frozenset({'sender'})

#: Accepted spellings of "this transaction succeeded".
STATUS_OK = '00'

#: `TX Type` for money leaving the wallet. The two other observed values are `RECEIVED`.
TX_SPEND = 'SPEND'

#: `duitnow_type` for a transfer to a PERSON rather than a shop. Measured, not guessed: it is the
#: only non-merchant value in the corpus, and both rows carrying it are money coming IN.
#: ⚠ This — never the shape of the merchant's name — is what decides "sent to a person". Half the
#: real merchants are registered under an individual's name (hawker stalls, sundry shops).
DUITNOW_P2P = 'STATIC_CUSTOMER_QR_CODE_DUITNOW_P2P'

_DATE_FORMATS = ('%d %b %Y', '%d %B %Y', '%Y-%m-%d', '%d/%m/%Y')
_MONEY_STRIP = re.compile(r'[Rr][Mm]|,|\s')
_DIGITS = re.compile(r'\D')


class UnreadableReport(Exception):
    """The header row cannot be resolved, so the file is refused whole.

    Deliberately loud and deliberately fatal to THAT FILE only: the caller keeps going with the
    others and reports this one. See the module docstring — a header we cannot read is the one
    failure that can misattribute money.
    """


def _norm_header(value) -> str:
    return ' '.join(str(value or '').strip().split()).casefold()


def norm_text(value) -> str:
    """Upper-cased, whitespace-collapsed text. Used for merchant names and code-like columns so
    `'99  Speedmart '` and `'99 SPEEDMART'` are one merchant rather than two."""
    return ' '.join(str(value or '').strip().split()).upper()


def norm_wallet(value) -> str:
    """Digits only. A wallet id is 13 digits; spreadsheets render it as a number, a string, or a
    string with a stray space, and our own stored `vircle_id` has been entered by hand more than
    once. Comparing digits is the only form both ends agree on."""
    return _DIGITS.sub('', str(value or ''))


def resolve_columns(header_row) -> tuple[dict[str, int], list[str]]:
    """Map field name → column index for THIS file's header row.

    Returns `(indexes, unknown_headers)`. Raises `UnreadableReport` naming every required field it
    could not find, together with the headers actually present — the message is the whole point,
    because the person reading it has to decide whether Vircle renamed a column or broke one.
    """
    seen = {_norm_header(h): i for i, h in enumerate(header_row) if _norm_header(h)}
    indexes: dict[str, int] = {}
    for field_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in seen:
                indexes[field_name] = seen[alias]
                break
    missing = [f for f in REQUIRED_FIELDS if f not in indexes]
    if missing:
        raise UnreadableReport(
            f'unreadable header: no column found for {sorted(missing)}; '
            f'headers present: {sorted(seen)}'
        )
    claimed = {i for i in indexes.values()}
    unknown = sorted(h for h, i in seen.items()
                     if i not in claimed and h not in KNOWN_UNUSED_HEADERS)
    return indexes, unknown


# ── value parsing ─────────────────────────────────────────────────────────────

def parse_amount(raw) -> Decimal | None:
    """`2` · `12.4` · `"RM26.90"` · `"RM1,234.50"` → `Decimal`. Anything else → `None`.

    ⚠ Returns `Decimal`, never `float`. This is money; it is summed, compared against a released
    total and shown to a sponsor. `payments._money` makes the same choice for the same reason.
    ⚠ `None` is a FINDING, not a shrug — every caller counts it. See the module docstring.
    """
    if isinstance(raw, bool):          # bool is an int subclass; never a valid amount
        return None
    if isinstance(raw, (int, float, Decimal)):
        try:
            return Decimal(str(raw)).quantize(_CENTS)
        except InvalidOperation:
            return None
    if isinstance(raw, str):
        cleaned = _MONEY_STRIP.sub('', raw)
        if not cleaned:
            return None
        try:
            return Decimal(cleaned).quantize(_CENTS)
        except InvalidOperation:
            return None
    return None


def parse_txn_date(raw) -> date | None:
    """`"30 Aug 2026"` · `"5 Jul 2026, 15:14:59"` · a real `datetime` → `date`. Else `None`.

    ⚠ **THE TIME OF DAY IS DISCARDED ON PURPOSE.** The newer reports no longer carry it, so storing
    it would be a column that is populated for two files out of eight and empty afterwards — a
    field whose emptiness means "old format" rather than anything about the student. Nothing in the
    product asks what hour somebody ate, and a sponsor must never be able to.
    """
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    text = str(raw or '').strip()
    if not text:
        return None
    text = text.split(',')[0].strip()          # drop the old format's trailing time
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


# ── one row ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SpendRow:
    """One parsed transaction, before it meets the database.

    ⚠ `holder_name` and `child_name` are carried ONLY to cross-check the wallet match and to tell
    a parent-held wallet from a student's own. Neither is ever written to a model field. See the
    module docstring.
    """
    txn_id: str
    txn_date: date | None
    wallet_id: str
    merchant: str
    duitnow_type: str
    entry_type: str
    tx_type: str
    status: str
    amount: Decimal | None
    holder_name: str
    child_name: str
    source_file: str
    row_number: int

    @property
    def spender_is_child(self) -> bool:
        """True when the wallet is held by a parent and the student rides on it as a child."""
        return bool(self.child_name)

    @property
    def is_person_transfer(self) -> bool:
        return self.duitnow_type == DUITNOW_P2P

    @property
    def is_spend(self) -> bool:
        return self.tx_type == TX_SPEND

    @property
    def succeeded(self) -> bool:
        return self.status == STATUS_OK


def _blank_to_empty(value) -> str:
    """Vircle writes an absent `Child User` as the literal string `null`, not as an empty cell."""
    text = ' '.join(str(value or '').strip().split())
    return '' if text.casefold() in ('', 'null', 'none', 'nil', '-') else text


def rows_from_values(header_row, value_rows, source_file: str) -> tuple[list[SpendRow], list[str]]:
    """Parse a whole report from plain values. **The one parser — see the module docstring.**

    Returns `(rows, unknown_headers)`. Raises `UnreadableReport` if the header cannot be resolved.
    Entirely blank rows are skipped (spreadsheet exports carry trailing ones); nothing else is.
    """
    indexes, unknown = resolve_columns(header_row)

    def cell(row, field_name):
        i = indexes.get(field_name)
        return row[i] if i is not None and i < len(row) else None

    rows: list[SpendRow] = []
    for number, row in enumerate(value_rows, start=2):     # row 1 is the header
        if not any(v is not None and str(v).strip() != '' for v in row):
            continue
        rows.append(SpendRow(
            txn_id=str(cell(row, 'txn_id') or '').strip(),
            txn_date=parse_txn_date(cell(row, 'txn_date')),
            wallet_id=norm_wallet(cell(row, 'wallet_id')),
            merchant=norm_text(cell(row, 'merchant')),
            duitnow_type=norm_text(cell(row, 'duitnow_type')),
            entry_type=norm_text(cell(row, 'entry_type')),
            tx_type=norm_text(cell(row, 'tx_type')),
            status=str(cell(row, 'status') or '').strip(),
            amount=parse_amount(cell(row, 'amount')),
            holder_name=_blank_to_empty(cell(row, 'holder_name')),
            child_name=_blank_to_empty(cell(row, 'child_name')),
            source_file=source_file,
            row_number=number,
        ))
    return rows, unknown


def rows_from_xlsx(path) -> tuple[list[SpendRow], list[str]]:
    """Adapter: a local `.xlsx` export → `rows_from_values`.

    ⚠ **openpyxl is imported here, not at module load, and is NOT a service dependency.** Reading a
    downloaded spreadsheet is a laptop operation; the live service reads the Sheets API. Same shape
    as `sheets.py`'s lazy Google imports, and for the same reason: this module must import cleanly
    on a machine that has neither library.
    """
    import os

    try:
        from openpyxl import load_workbook            # type: ignore
    except ImportError as exc:                        # pragma: no cover - environment-dependent
        raise UnreadableReport(
            'openpyxl is not installed; it is needed only to read a local .xlsx export '
            '(`pip install openpyxl`). The service reads the Sheets API instead.'
        ) from exc

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        stream = sheet.iter_rows(values_only=True)
        try:
            header = next(stream)
        except StopIteration:
            raise UnreadableReport(f'{os.path.basename(path)}: the file is empty')
        return rows_from_values(header, stream, os.path.basename(path))
    finally:
        workbook.close()


# ── storing it ────────────────────────────────────────────────────────────────

#: Statuses in which a student is expected to HOLD a wallet, so a blank `vircle_id` is a finding.
#:
#: ⚠ DELIBERATELY ITS OWN CONSTANT even though it currently equals `pool.RECENTLY_FUNDED_STATES`.
#: That one answers *"whose card lingers in the discovery pool?"*; this one answers *"who should
#: have somewhere for money to land?"*. Two filters that look identical and mean different things
#: is how one of them silently acquires the other's rule — so they are kept apart on purpose.
#: `closed` is absent: a finished student needs no wallet.
WALLET_EXPECTED_STATES = ('awarded', 'active', 'maintenance')

#: The fields a repeated `txn_id` must agree on for first-copy-wins to be safe.
_IDENTITY_FIELDS = ('txn_date', 'wallet_id', 'merchant', 'amount', 'tx_type', 'status')


def _identity(row) -> tuple:
    return tuple(getattr(row, f) for f in _IDENTITY_FIELDS)


@dataclass
class IngestReport:
    """What one run found. **Printed in full in report mode and read before `--apply`.**

    ⚠ Every "skip" here is a COUNTED, NAMED finding, never a quiet drop. See the module docstring:
    the first analysis of this corpus lost 88 rows to a silent skip and under-reported the total by
    RM621 without anything looking wrong.
    """
    files: list = field(default_factory=list)             # (name, parsed, new)
    unreadable_files: list = field(default_factory=list)  # (name, message)
    unknown_headers: set = field(default_factory=set)

    rows_seen: int = 0
    rows_stored: int = 0
    rows_already_stored: int = 0

    repeats_identical: int = 0
    repeats_conflicting: list = field(default_factory=list)   # (txn_id, kept, incoming)

    unparsed_amount: list = field(default_factory=list)       # (file, row_number, raw)
    unparsed_date: list = field(default_factory=list)

    unknown_wallets: dict = field(default_factory=dict)       # wallet -> row count
    ambiguous_wallets: dict = field(default_factory=dict)     # wallet -> [application ids]
    students_without_wallet: list = field(default_factory=list)

    coverage_from: date | None = None
    coverage_to: date | None = None
    spend_rows: int = 0
    spend_total: Decimal = Decimal('0.00')

    @property
    def needs_attention(self) -> bool:
        """Whether a human must look. **This — and only this — decides whether an email is sent.**

        ⚠ Silence must mean "nothing to report" (owner ruling). A run that found nothing sends
        nothing; a weekly all-clear is a message nobody opens, and the week it matters it gets
        skimmed with the rest.
        """
        return bool(self.unreadable_files or self.unknown_headers or self.repeats_conflicting
                    or self.unparsed_amount or self.unparsed_date or self.unknown_wallets
                    or self.ambiguous_wallets or self.students_without_wallet)

    def lines(self) -> list[str]:
        """Human-readable summary. Names wallets and application ids — never a student's name."""
        out = [
            f'files read           : {len(self.files)}',
            f'rows seen            : {self.rows_seen}',
            f'rows stored          : {self.rows_stored}',
            f'rows already stored  : {self.rows_already_stored}',
            f'repeats (identical)  : {self.repeats_identical}',
            f'coverage             : {self.coverage_from} -> {self.coverage_to}',
            f'SPEND rows           : {self.spend_rows}',
            f'SPEND total          : RM{self.spend_total}',
        ]
        for name, parsed, new in self.files:
            out.append(f'  {name}: parsed {parsed}, new {new}')
        if self.unreadable_files:
            out.append('UNREADABLE FILES (refused whole):')
            out += [f'  {n}: {m}' for n, m in self.unreadable_files]
        if self.unknown_headers:
            out.append(f'UNKNOWN COLUMNS (loaded anyway): {sorted(self.unknown_headers)}')
        if self.repeats_conflicting:
            out.append('REPEATED txn_id WITH DIFFERENT VALUES (a correction - resolve by hand):')
            out += [f'  {t}: kept {k} / incoming {i}' for t, k, i in self.repeats_conflicting]
        if self.unparsed_amount:
            out.append('AMOUNTS THAT WOULD NOT PARSE:')
            out += [f'  {f} row {r}: {v!r}' for f, r, v in self.unparsed_amount]
        if self.unparsed_date:
            out.append('DATES THAT WOULD NOT PARSE:')
            out += [f'  {f} row {r}: {v!r}' for f, r, v in self.unparsed_date]
        if self.unknown_wallets:
            out.append('WALLETS MATCHING NO STUDENT (rows skipped):')
            out += [f'  {w}: {n} rows' for w, n in sorted(self.unknown_wallets.items())]
        if self.ambiguous_wallets:
            out.append('WALLETS MATCHING MORE THAN ONE STUDENT (rows skipped):')
            out += [f'  {w}: applications {ids}' for w, ids in sorted(self.ambiguous_wallets.items())]
        if self.students_without_wallet:
            out.append(f'FUNDED STUDENTS WITH NO WALLET RECORDED: '
                       f'{sorted(self.students_without_wallet)}')
        return out


def _wallet_map() -> tuple[dict[str, int], dict[str, list]]:
    """`{wallet digits: application id}` plus any wallet claimed by more than one application.

    ⚠ A SHARED WALLET IS NOT AN ERROR TO GUESS PAST. Two siblings on one parent-held account would
    produce it, and picking either application would file one student's spending against the other.
    Ambiguous wallets are reported and their rows skipped.
    """
    from .models import ScholarshipApplication

    owners: dict[str, list] = {}
    rows = (ScholarshipApplication.objects
            .exclude(vircle_id='')
            .values_list('id', 'vircle_id'))
    for app_id, wallet in rows:
        key = norm_wallet(wallet)
        if key:
            owners.setdefault(key, []).append(app_id)
    unique = {w: ids[0] for w, ids in owners.items() if len(ids) == 1}
    ambiguous = {w: sorted(ids) for w, ids in owners.items() if len(ids) > 1}
    return unique, ambiguous


def _students_without_wallet() -> list:
    from .models import ScholarshipApplication

    return list(ScholarshipApplication.objects
                .filter(status__in=WALLET_EXPECTED_STATES, vircle_id='')
                .values_list('id', flat=True))


def ingest(sources, *, apply=False) -> IngestReport:
    """Read every source and (optionally) store what is new. **Report-first by default.**

    `sources` is an iterable of `(name, rows, unknown_headers)` — already parsed, so this function
    is identical whether the rows came from a local `.xlsx` or from the Sheets API in S2.

    ⚠ `apply=False` MUST BE UNABLE TO WRITE, not merely choose not to. There is exactly one
    `create` call and it sits behind the flag; a test asserts the row count is unchanged after a
    report run. "Read-only by intent" is how a reporting tool grows a write.
    """
    from django.db import transaction

    from .models import BursarySpendTxn

    report = IngestReport()
    wallets, ambiguous_map = _wallet_map()
    existing = {}
    for txn in BursarySpendTxn.objects.all().only(
            'txn_id', 'txn_date', 'wallet_id', 'merchant', 'amount', 'tx_type', 'status'):
        existing[txn.txn_id] = (txn.txn_date, txn.wallet_id, txn.merchant,
                                txn.amount, txn.tx_type, txn.status)

    seen_this_run: dict[str, tuple] = {}
    to_create: list = []

    for name, rows, unknown in sources:
        report.unknown_headers |= set(unknown)
        new_here = 0
        for row in rows:
            report.rows_seen += 1

            if row.amount is None:
                report.unparsed_amount.append((name, row.row_number, row.amount))
                continue
            if row.txn_date is None:
                report.unparsed_date.append((name, row.row_number, row.txn_date))
                continue

            identity = _identity(row)

            prior = seen_this_run.get(row.txn_id) or existing.get(row.txn_id)
            if prior is not None:
                if prior == identity:
                    report.repeats_identical += 1
                    if row.txn_id in existing and row.txn_id not in seen_this_run:
                        report.rows_already_stored += 1
                else:
                    # ⚠ A CORRECTION, NOT NOISE. Every repeat measured so far is byte-identical,
                    # so a disagreement means Vircle restated something. Keeping the first copy
                    # silently would freeze the wrong figure into a sponsor's chart.
                    report.repeats_conflicting.append((row.txn_id, prior, identity))
                continue

            if row.wallet_id in ambiguous_map:
                report.ambiguous_wallets[row.wallet_id] = ambiguous_map[row.wallet_id]
                continue
            app_id = wallets.get(row.wallet_id)
            if app_id is None:
                report.unknown_wallets[row.wallet_id] = \
                    report.unknown_wallets.get(row.wallet_id, 0) + 1
                continue

            seen_this_run[row.txn_id] = identity
            new_here += 1
            report.rows_stored += 1
            if row.is_spend:
                report.spend_rows += 1
                report.spend_total += row.amount
            if report.coverage_from is None or row.txn_date < report.coverage_from:
                report.coverage_from = row.txn_date
            if report.coverage_to is None or row.txn_date > report.coverage_to:
                report.coverage_to = row.txn_date

            to_create.append(BursarySpendTxn(
                application_id=app_id,
                txn_id=row.txn_id,
                txn_date=row.txn_date,
                wallet_id=row.wallet_id,
                merchant=row.merchant,
                amount=row.amount,
                duitnow_type=row.duitnow_type,
                entry_type=row.entry_type,
                tx_type=row.tx_type,
                status=row.status,
                is_person_transfer=row.is_person_transfer,
                spender_is_child=row.spender_is_child,
                source_file=row.source_file,
            ))
        report.files.append((name, len(rows), new_here))

    report.students_without_wallet = _students_without_wallet()

    if apply and to_create:
        with transaction.atomic():
            BursarySpendTxn.objects.bulk_create(to_create, batch_size=500)
    return report
