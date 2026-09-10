"""File a written summary of an import back into Drive, beside the file it describes.

An **alert is PUSH** and a **summary is PULL**, and they do different jobs. Nobody discovers a
broken import by opening a folder, so a fault still emails (S2). Nobody wants an email every week
saying everything is fine, so the routine picture goes where the data lives, for whoever goes
looking. Neither replaces the other — owner, 2026-09-10.

────────────────────────────────────────────────────────────────────────────────────────────────
⚠⚠ **WE COMPUTE EVERY FIGURE; THE MODEL ONLY WRITES THE PROSE AROUND THEM.** This is the house
pattern proven in `verdict_narrative.py`, whose own docstring says the LLM *"NEVER computes or
changes the verdict"*. Every number in the filed document — totals, category splits, coverage
dates, counts — is computed in Python by `build_facts` and rendered by `figures_block`. The model
is handed those facts and asked for two or three sentences of plain English around them.

⚠⚠ **AND THE PROMPT IS NOT THE GUARD — `_numbers_agree` IS.** A prompt instruction is a request; a
deterministic post-check is a rule. The generated prose is scanned for every number it contains,
and if ANY of them is not among the computed facts the prose is **discarded** and the figures are
filed alone. A summary with no prose is a small disappointment. A summary that invents a total is
a document somebody will quote in a meeting. This is the STR payment guard's lesson applied to the
money-adjacent output rather than the money-adjacent input.

────────────────────────────────────────────────────────────────────────────────────────────────
⚠⚠ **NEVER WRITE OUR OWN OUTPUT WHERE THE READER WILL PICK IT UP AS AN INPUT.** A summary dropped
beside the Vircle exports is a file the next ingest would try to parse as a report — and it would
fail on the header, refuse the file, and email a fault every single day. **Two independent guards,
both required:**

  1. it is written into a **SUBFOLDER** (`…/06 Student Spending/Summaries`), and
  2. its filename cannot match `sheets._SPENDING_FILENAME_RE`, the pattern the reader accepts.

One guard is a convention; two is a design. `test_spend_summary` asserts the second directly
against the reader's own regex rather than against a copy of it.

────────────────────────────────────────────────────────────────────────────────────────────────
⚠ **THE SUMMARY IS INTERNAL, SO IT MAY NAME MERCHANTS — and it must still never leave that
folder.** It is written for the officer and the owner: which shops, which wallets need fixing,
what the model decided this week. **It is not the sponsor's document and no part of it is reused
on the sponsor card**, which sees categories and totals only.

⚠ **IT NAMES NO STUDENT.** We never stored one (`spending_import`), and per-student lines would
turn an operational note into a file about people. Wallets and application ids only — the two
things needed to fix something — exactly as the alert email does.

⚠ **SCOPE IS THE IMPORT RUN, NOT A TENANT.** `VIRCLE_SPENDING_FOLDER` is a single configured
folder in one organisation's Drive, so the ingest is already single-folder by configuration and a
report that lands in that folder describes that folder's import. **If a second tenant ever gets its
own spending folder, the summary follows the FOLDER** — one report per folder — and that is the
moment to revisit this.

⚠ **BEST-EFFORT, LIKE EVERY OTHER DRIVE CALL.** A Drive hiccup must break nothing: the summary is
the last thing a run does, it never raises, and its failure is reported so a human can see it.
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal

logger = logging.getLogger(__name__)

_ZERO = Decimal('0.00')

#: Bump on ANY change to `_PROMPT_HEAD` or to the facts handed over. Written into the DOCUMENT, not
#: merely into a field, so a reader holding the file can tell which prompt produced it.
PROMPT_VERSION = 'spend-summary-v1'

#: The filename stem. ⚠ It must never match `sheets._SPENDING_FILENAME_RE`, which is
#: `^\d{4}-\d{2}-\d{2}\b.*usage report` — so this deliberately does NOT start with a date and
#: deliberately does not contain the words "usage report". Both halves matter; a test asserts it
#: against the reader's own regex.
FILENAME_STEM = 'Spending summary'

#: Every number the prose is allowed to contain, beyond those in the facts. Bare years and small
#: ordinals appear in ordinary English ("the first week", "2026") and are not claims about money.
_ALWAYS_ALLOWED = frozenset({'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10'})

_NUMBER = re.compile(r'\d[\d,]*(?:\.\d+)?')


# ── the facts, computed ───────────────────────────────────────────────────────

def build_facts(report, *, today=None) -> dict:
    """Everything the document states, computed in Python. **The model adds none of it.**

    `report` is the `spending_import.IngestReport` from the run that just finished. The category
    split is read back from the stored rows for the transaction ids this run created, so it
    reflects the sorter's verdict rather than re-deriving one.
    """
    from django.utils import timezone

    from .models import SPEND_CATEGORY_CHOICES, BursarySpendTxn

    today = today or timezone.localtime().date()
    labels = dict(SPEND_CATEGORY_CHOICES)

    files = [name for name, _parsed, _new in report.files]
    # Rows this run actually stored, by the files it read — `source_file` is written at import.
    # The scope is the IMPORT, not a tenant (see the module docstring): the report describes the
    # file that just landed in one configured folder, and it is filed back into that same folder.
    # org-fence: NONE, by design (an import report, scoped to its own source files).
    stored = BursarySpendTxn.objects.filter(source_file__in=files) if files else \
        BursarySpendTxn.objects.none()

    by_category: dict[str, dict] = {}
    total = _ZERO
    for category, amount in stored.filter(tx_type='SPEND').values_list('category', 'amount'):
        code = category or 'unsorted'
        row = by_category.setdefault(code, {'code': code, 'label': labels.get(code, code),
                                            'payments': 0, 'total': _ZERO})
        row['payments'] += 1
        row['total'] += amount or _ZERO
        total += amount or _ZERO

    categories = sorted(by_category.values(), key=lambda r: (-r['total'], r['label']))

    merchants: dict[str, Decimal] = {}
    for merchant, amount in stored.filter(tx_type='SPEND').values_list('merchant', 'amount'):
        merchants[merchant] = merchants.get(merchant, _ZERO) + (amount or _ZERO)
    top_merchants = sorted(merchants.items(), key=lambda kv: (-kv[1], kv[0]))[:10]

    return {
        'today': today,
        'prompt_version': PROMPT_VERSION,
        'files': files,
        'rows_stored': report.rows_stored,
        'rows_already_stored': report.rows_already_stored,
        'coverage_from': report.coverage_from,
        'coverage_to': report.coverage_to,
        'spend_payments': report.spend_rows,
        'spend_total': report.spend_total,
        'stored_total': total,
        'categories': categories,
        'top_merchants': [(m, amt) for m, amt in top_merchants],
        'unknown_wallets': dict(report.unknown_wallets),
        'ambiguous_wallets': dict(report.ambiguous_wallets),
        'students_without_wallet': list(report.students_without_wallet),
        'unreadable_files': list(report.unreadable_files),
        'needs_attention': report.needs_attention,
    }


def figures_block(facts) -> str:
    """The deterministic half of the document. **Every number the reader can rely on is here.**"""
    lines = [
        '## The figures',
        '',
        f"Files read: {', '.join(facts['files']) or 'none'}",
        f"New payments stored: {facts['rows_stored']}",
        f"Already held (repeats): {facts['rows_already_stored']}",
        f"Coverage: {facts['coverage_from']} to {facts['coverage_to']}",
        f"Spending in this import: RM{facts['spend_total']} across {facts['spend_payments']} "
        f"payments",
        '',
        '### By category',
        '',
        '| Category | Payments | Total |',
        '|---|---:|---:|',
    ]
    for row in facts['categories']:
        lines.append(f"| {row['label']} | {row['payments']} | RM{row['total']} |")
    if not facts['categories']:
        lines.append('| (nothing stored) | 0 | RM0.00 |')

    lines += ['', '### Biggest shops in this import', '']
    for merchant, amount in facts['top_merchants']:
        lines.append(f'- {merchant} — RM{amount}')
    if not facts['top_merchants']:
        lines.append('- (nothing stored)')

    if facts['needs_attention']:
        lines += ['', '### Needs a human', '']
        for name, message in facts['unreadable_files']:
            lines.append(f'- Could not read **{name}**: {message}')
        for wallet, count in sorted(facts['unknown_wallets'].items()):
            lines.append(f'- Wallet `{wallet}` matches no student — {count} payments skipped.')
        for wallet, ids in sorted(facts['ambiguous_wallets'].items()):
            lines.append(f'- Wallet `{wallet}` is claimed by applications {ids} — skipped.')
        if facts['students_without_wallet']:
            lines.append('- Funded students with no wallet recorded: '
                         f"{sorted(facts['students_without_wallet'])}")
    return '\n'.join(lines)


# ── the prose, narrated ───────────────────────────────────────────────────────

_PROMPT_HEAD = (
    'You are writing the opening of an internal note for a scholarship officer, summarising a '
    'weekly import of student spending data.\n\n'
    'Write TWO OR THREE sentences of plain British English. No headings, no bullet points, no '
    'greeting, no sign-off — just the sentences.\n\n'
    'RULES:\n'
    '1. Use ONLY the facts and figures given below. NEVER invent, estimate, alter or calculate a '
    'number. If you want to say something the figures do not support, leave it out.\n'
    '2. Prefer words to numbers. The figures are printed in full beneath your sentences, so you do '
    'not need to repeat them all — say what the week LOOKS like.\n'
    '3. Name no student. The data contains none, and you must not invent one.\n'
    '4. If something needs a human, say so first and plainly.\n'
    '5. Do not congratulate, do not apologise, and do not speculate about why students spent what '
    'they spent.\n'
)


def _facts_for_prompt(facts) -> str:
    """The context block. ⚠ Includes TODAY'S DATE — a summary reasons about dates constantly, and
    the model does not know what day it is (lesson, 2026-06-20)."""
    lines = [
        f"Today's date: {facts['today'].isoformat()} (Malaysia).",
        f"Files read this run: {', '.join(facts['files']) or 'none'}.",
        f"New payments stored: {facts['rows_stored']}.",
        f"Payments already held and skipped as repeats: {facts['rows_already_stored']}.",
        f"The imported payments cover {facts['coverage_from']} to {facts['coverage_to']}.",
        f"Total spending in this import: RM{facts['spend_total']} across "
        f"{facts['spend_payments']} payments.",
        'Category split: ' + ('; '.join(
            f"{r['label']} RM{r['total']} over {r['payments']} payments"
            for r in facts['categories']) or 'nothing stored'),
        f"Anything needing a human: {'yes' if facts['needs_attention'] else 'no'}.",
    ]
    if facts['needs_attention']:
        if facts['unreadable_files']:
            lines.append(f"Files that could not be read: {len(facts['unreadable_files'])}.")
        if facts['unknown_wallets']:
            lines.append(f"Wallets matching no student: {len(facts['unknown_wallets'])}.")
        if facts['students_without_wallet']:
            lines.append('Funded students with no wallet recorded: '
                         f"{len(facts['students_without_wallet'])}.")
    return '\n'.join(lines)


def _numbers_in(text) -> set[str]:
    """Every number in `text`, normalised — commas dropped, trailing `.00` dropped."""
    out = set()
    for raw in _NUMBER.findall(text or ''):
        value = raw.replace(',', '')
        if '.' in value:
            value = value.rstrip('0').rstrip('.')
        out.add(value or '0')
    return out


def _numbers_agree(prose, facts) -> bool:
    """⚠⚠ **THE GUARD, AND IT IS DETERMINISTIC ON PURPOSE.**

    Every number the model wrote must be one we handed it. A prompt saying "never invent a number"
    is a request; this is a rule, and it is the one that decides whether the prose is filed at all.
    Bare years and small counts are allowed because they appear in ordinary English.
    """
    return _numbers_in(prose) <= (_numbers_in(_facts_for_prompt(facts)) | _ALWAYS_ALLOWED)


def render_prose(facts):
    """Two or three sentences, or `''` if the model is unavailable or invented a figure.

    ⚠ Reached through `profile_engine._call_gemini_text`, the same seam `verdict_narrative` uses,
    inside `usage_context`. Every test patches that one function, so CI makes no billable call.
    """
    from . import usage
    from .profile_engine import _call_gemini_text

    prompt = _PROMPT_HEAD + '\nFACTS:\n' + _facts_for_prompt(facts)
    with usage.usage_context(source='spend_summary'):
        result = _call_gemini_text(prompt, 'English')
    if not isinstance(result, dict) or result.get('error'):
        logger.warning('spend_summary: no prose (%s)',
                       (result or {}).get('error') if isinstance(result, dict) else result)
        return ''
    prose = (result.get('markdown') or '').strip()
    if not prose:
        return ''
    if not _numbers_agree(prose, facts):
        # ⚠ NOT a warning to be skimmed: the model stated a figure nobody gave it, and the
        # document is about money. Drop the prose; the figures below it are unaffected.
        logger.warning('spend_summary: prose DISCARDED - it contained a figure not in the facts: '
                       '%r', prose)
        return ''
    return prose


# ── the document, and filing it ───────────────────────────────────────────────

def summary_filename(facts) -> str:
    """⚠ Must NEVER match `sheets._SPENDING_FILENAME_RE`. See the module docstring — this is lock
    number two, and `test_spend_summary` asserts it against the reader's own regex."""
    return f"{FILENAME_STEM} {facts['today'].isoformat()}.md"


def summary_text(facts, prose='') -> str:
    """The whole document: the prose (if any survived), then every computed figure."""
    parts = [f"# Student spending — import of {facts['today'].isoformat()}", '']
    if prose:
        parts += [prose, '']
    else:
        parts += ['_No written summary this time; the figures below are unaffected._', '']
    parts += [figures_block(facts), '', '---', '',
              f"Written automatically after the import. Prompt {facts['prompt_version']}. "
              'Internal — it names shops, so it stays in this folder and no part of it reaches a '
              'sponsor.']
    return '\n'.join(parts)


def file_summary(report, *, folder_path=None, today=None) -> dict:
    """Build the summary and write it to Drive. **Best-effort: never raises.**

    Returns `{'filed': bool, 'filename': str, 'url': str|None, 'prose': bool, 'error': str}` so the
    command can report what happened. A Drive failure leaves the import untouched — that is the
    whole contract, and the reason this is the LAST thing a run does.
    """
    from django.conf import settings

    from . import sheets

    out = {'filed': False, 'filename': '', 'url': None, 'prose': False, 'error': ''}
    try:
        facts = build_facts(report, today=today)
        prose = render_prose(facts)
        out['prose'] = bool(prose)
        text = summary_text(facts, prose)
        out['filename'] = summary_filename(facts)
        folder = folder_path or getattr(settings, 'VIRCLE_SPENDING_SUMMARY_FOLDER', '')
        if not folder:
            out['error'] = 'no summary folder configured'
            return out
        url = sheets.file_text_to_folder(folder, out['filename'], text,
                                         mimetype='text/markdown', create_missing=True)
        if url is None:
            # ⚠ REPORTED, NOT SWALLOWED. A summary that silently never appears is indistinguishable
            # from a week nobody looked at the folder.
            out['error'] = f'could not write into {folder!r}'
            return out
        out['filed'] = True
        out['url'] = url
    except Exception as exc:                        # pragma: no cover - defensive
        logger.warning('spend_summary: filing failed', exc_info=True)
        out['error'] = str(exc)
    return out
