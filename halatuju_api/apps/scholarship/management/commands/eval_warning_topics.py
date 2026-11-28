"""Case 1048 paid eval: the topic-coded salary-slip read, against the stored read. Writes nothing.

Run on the release-decisions Cloud Run job from the deployed image BEFORE the owner relies on the topic codes.
It takes the newest live salary-slip documents whose stored read came from the AI (``capture`` 'ai', fields
filled; a label-parsed read never meets the prompt and is only counted) and re-reads each IN MEMORY: the file is
fetched, its text read by `vision.extract_text` (the free text layer of a digital PDF, else one Vision OCR), and
`vision.extract_document_fields(text, 'salary_slip')` reads it with the NEW prompt and schema, as a Re-run does.
It reports, as counts and ids only:

  (a) field changes against the stored read: gross_income, net_income, period and employer (same / changed),
      and name present or absent only (never the name);
  (b) how many new reads carry valid topics (`warning_topics.valid_topics`);
  (c) on documents seen as a declaration, how many warnings the tagged path hides against the word filter;
  (d) the ids of documents where a warning with a keep word was tagged payslip-only (the display still shows it).

WRITES NOTHING: every document save and every ApplicantDocument queryset update is refused during the run, and
the OCR text is never kept (`extract_text` does not keep it). The one row is the seams' own billing meter, a
PLATFORM row (`usage_context(source=USAGE_SOURCE)`).

DRY RUN BY DEFAULT: counts and the estimated cost only; no download, no AI call. `--run` needs `--limit` (at
most `MAX_LIMIT`) and `--max-cost-usd` (at most `MAX_COST_USD`); it stops before the document that could pass
the cap, and after `FAIL_FAST` service errors (or failed fetches) in a row. COST: each METERED Gemini row (one
call can bill up to 3 cascade models, one row each) is charged at an ASSUMED upper bound of US$0.004 (or its
reported tokens at the assumed prices when higher), each Vision OCR row at US$0.0015; a Gemini call that left no
row is charged once at US$0.004. The cap is checked after EVERY row: the run stops (mid-read if need be) once the
next row could pass it. Before each call the next row is RESERVED (`row_reserve`: the prompt's bytes bound its
input tokens, never below the largest row seen), so a long prompt is refused before it is billed.

PRIVATE: prints counts and document ids only; never a name, an IC number, document text or model free text.

    python manage.py eval_warning_topics                                     # dry run
    python manage.py eval_warning_topics --run --limit 60 --max-cost-usd 0.50
"""
import logging
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from unittest import mock

from django.core.management.base import BaseCommand, CommandError
from django.db.models import QuerySet

from apps.scholarship import usage, vision
from apps.scholarship.income_declaration import is_declaration
from apps.scholarship.income_engine.declaration_name import has_keep_word, payslip_only_warning, tagged_hides
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.vision.warning_topics import KEY, PAYSLIP_ONLY_TOPICS, valid_topics

logger = logging.getLogger(__name__)

USAGE_SOURCE = 'warning_topics_eval'
MAX_LIMIT = 100
MAX_COST_USD = Decimal('1.00')
FAIL_FAST = 5
PROGRESS_EVERY = 20
IDS_SHOWN = 50
#: The cascade's most calls on one document (one per model, `profile_engine.MODEL_CASCADE`).
MAX_GEMINI_CALLS = 3
#: An ASSUMED upper bound per Gemini text call (a salary-slip prompt is ~2k tokens in, ~300 out).
USD_PER_GEMINI_CALL = Decimal('0.004')
USD_PER_VISION_OCR = Decimal('0.0015')
#: Token prices assumed for the newest Flash (US$ per 1M tokens; as `eval_genuineness_38`).
PRICE_ASSUMED = {'input': Decimal('0.60'), 'output': Decimal('5.00')}
FIELDS = ('gross_income', 'net_income', 'period', 'employer')

COUNTERS = ('docs', 'read', 'fetch_failed', 'ocr_failed', 'service_error', 'error', 'gemini_calls', 'vision_ocr',
            'valid_topics', 'no_topics', 'invalid_topics', 'declarations', 'declaration_warnings',
            'hidden_by_topic', 'hidden_by_words', 'name_present_both', 'name_absent_both', 'name_lost',
            'name_gained') + tuple(f'{f}_{k}' for f in FIELDS for k in ('same', 'changed'))
ID_LISTS = ('keep_word_tagged_payslip_only', 'topics_hide_more', 'words_hide_more', 'service_error', 'fetch_failed')


def _ai_read(vf) -> bool:
    return isinstance(vf, dict) and vf.get('capture', 'ai') == 'ai' and bool(vf.get('fields'))


def topics_sample(limit=None):
    """(the newest live salary-slip ids with a stored AI read, how many label-parsed reads were passed over)."""
    qs = ApplicantDocument.live(ApplicantDocument.objects.filter(doc_type='salary_slip').exclude(storage_path=''))
    ids, parsed = [], 0
    for pk, vf in qs.order_by('-pk').values_list('pk', 'vision_fields').iterator():
        if _ai_read(vf):
            ids.append(pk)
        elif isinstance(vf, dict) and vf.get('capture') == 'deterministic':
            parsed += 1
    return (ids[:limit] if limit else ids), parsed


def gemini_cost(tokens):
    """One Gemini call's charge: the flat assumed US$0.004, or its reported tokens at the assumed prices if higher."""
    tin, tout = (usage._int_or_none(v) for v in (tokens or (None, None)))
    if tin is None and tout is None:
        return USD_PER_GEMINI_CALL
    metered = (Decimal(tin or 0) * PRICE_ASSUMED['input'] + Decimal(tout or 0) * PRICE_ASSUMED['output']) / 1_000_000
    return max(USD_PER_GEMINI_CALL, metered)


def _same(a, b) -> bool:
    return ' '.join(str(a or '').split()).lower() == ' '.join(str(b or '').split()).lower()


def tally_topics(n, ids, doc, new):
    """Add one new read to the counts: (a) field changes, (b) topics, (c) and (d) on a declaration. Ids only."""
    old = (doc.vision_fields or {}).get('fields') or {}
    fields = new.get('fields') or {}
    for f in FIELDS:
        n[f'{f}_{"same" if _same(old.get(f), fields.get(f)) else "changed"}'] += 1
    had, has = bool(str(old.get('name') or '').strip()), bool(str(fields.get('name') or '').strip())
    n['name_present_both' if had and has else 'name_absent_both' if not (had or has)
      else 'name_lost' if had else 'name_gained'] += 1
    warnings, topics = new.get('warnings') or [], new.get(KEY)
    ok = valid_topics(warnings, topics)
    n['valid_topics' if ok else 'no_topics' if topics is None else 'invalid_topics'] += 1
    if ok and any(t in PAYSLIP_ONLY_TOPICS and has_keep_word(w) for w, t in zip(warnings, topics)):
        ids['keep_word_tagged_payslip_only'].append(doc.pk)
    if not is_declaration(doc):
        return
    n['declarations'] += 1
    n['declaration_warnings'] += len(warnings)
    by_words = sum(1 for w in warnings if payslip_only_warning(w))
    by_topic = (sum(1 for w, t in zip(warnings, topics) if t in PAYSLIP_ONLY_TOPICS and tagged_hides(w))
                if ok else by_words)      # the display's own rule; it falls back to the words, whole list
    n['hidden_by_topic'] += by_topic
    n['hidden_by_words'] += by_words
    if by_topic != by_words:
        ids['topics_hide_more' if by_topic > by_words else 'words_hide_more'].append(doc.pk)


class CapReached(Exception):
    """The next billed row could pass ``--max-cost-usd``: the run stops here (review round 1)."""


def _add_row_cost(trace, cost):
    trace['usd'] += cost
    trace['peak'] = max(trace['peak'], cost)
    if trace['usd'] + max(trace['peak'], trace['reserve']) > trace['cap']:
        trace['over'] = True


def row_reserve(trace, prompt):
    """Review round 2: what the NEXT row may cost, reserved BEFORE the call. The prompt's UTF-8 bytes bound
    its input tokens (a token is at least one byte), priced as `gemini_cost`; never below the largest row
    seen. The call sets no output ceiling, so the output part stays the flat US$0.004 bound."""
    size = len(prompt.encode('utf-8')) if isinstance(prompt, str) else None
    return max(trace['peak'], gemini_cost((size, None)))


@contextmanager
def _traced(trace):
    """Count and price every metered Gemini row and Vision OCR (never their text), check the cap after each
    row, and refuse every document write. One Gemini call can bill up to 3 cascade models: each row counts."""
    real_call, real_meter, real_update = vision._call_gemini_json, usage.record_usage, QuerySet.update

    def counted(*a, **k):
        trace['reserve'] = row_reserve(trace, a[0] if a else k.get('prompt'))
        if trace['over'] or trace['usd'] + trace['reserve'] > trace['cap']:
            raise CapReached          # one large row (a long prompt) can never pass the cap
        trace['gemini'] += 1
        rows = trace['rows']
        try:
            return real_call(*a, **k)
        finally:
            if trace['rows'] == rows:      # no metered row (every model failed, or a test seam): the flat bound
                _add_row_cost(trace, USD_PER_GEMINI_CALL)

    def metered(service, *a, **k):
        out = real_meter(service, *a, **k)        # the billed row is recorded first, always
        if service == usage.GEMINI:
            trace['rows'] += 1
            _add_row_cost(trace, gemini_cost((k.get('input_tokens'), k.get('output_tokens'))))
            if trace['over']:
                raise CapReached          # outside the cascade's own try: the next model is never called
        elif service == usage.VISION_OCR:
            trace['vision'] += 1
            _add_row_cost(trace, USD_PER_VISION_OCR)   # the OCR seam swallows a raise; `counted` stops the Gemini call
        return out

    def refuse(*a, **k):
        raise RuntimeError('eval_warning_topics writes nothing')

    def update(qs, *a, **k):
        if qs.model is ApplicantDocument:
            refuse()
        return real_update(qs, *a, **k)

    with mock.patch.object(vision, '_call_gemini_json', counted), mock.patch.object(usage, 'record_usage', metered), \
            mock.patch.object(ApplicantDocument, 'save', refuse), mock.patch.object(QuerySet, 'update', update), \
            mock.patch.object(QuerySet, 'bulk_update', refuse):
        yield


class Command(BaseCommand):
    help = ('Case 1048: re-read recent salary slips in memory with the topic-coded prompt and compare with the '
            'stored read. Writes nothing. DRY RUN unless --run (which needs --limit and --max-cost-usd).')

    def add_arguments(self, parser):
        parser.add_argument('--run', action='store_true', help='Call OCR and Gemini. Without it: counts only.')
        parser.add_argument('--limit', type=int, default=None, help=f'At most this many documents (1 to {MAX_LIMIT}).')
        parser.add_argument('--max-cost-usd', default=None, help=f'Stop before the cap (at most {MAX_COST_USD}).')

    def handle(self, *args, **opts):
        limit, cap = self._checked(opts)
        todo, parsed = topics_sample(limit)
        cent = Decimal('0.01')
        usual = (USD_PER_GEMINI_CALL + USD_PER_VISION_OCR) * len(todo)
        worst = (USD_PER_GEMINI_CALL * MAX_GEMINI_CALLS + USD_PER_VISION_OCR) * len(todo)
        out = self.stdout.write
        out(f'eval_warning_topics: {"RUN" if opts["run"] else "DRY RUN (no download, no AI call, no write)"}')
        out(f'  salary slips to re-read: {len(todo)} (stored AI reads, newest first); '
            f'label-parsed passed over: {parsed}')
        out(f'  estimated cost: about US${usual.quantize(cent)} (one OCR and one Gemini call each), at most '
            f'US${worst.quantize(cent)} if every read falls through the cascade (ASSUMED prices)')
        if opts['run']:
            self._run(todo, cap)

    @staticmethod
    def _checked(opts):
        limit, raw_cap = opts['limit'], opts['max_cost_usd']
        if limit is not None and not 1 <= limit <= MAX_LIMIT:
            raise CommandError(f'--limit must be 1 to {MAX_LIMIT}.')
        if not opts['run']:
            return limit, None
        if limit is None or raw_cap is None:
            raise CommandError('--run needs --limit and --max-cost-usd.')
        try:
            cap = Decimal(str(raw_cap))
        except InvalidOperation:
            raise CommandError('--max-cost-usd must be a number, e.g. 0.50.') from None
        if not (cap.is_finite() and Decimal('0') < cap <= MAX_COST_USD):
            raise CommandError(f'--max-cost-usd must be above 0 and at most {MAX_COST_USD}.')
        return limit, cap

    def _run(self, todo, cap):
        n, ids = dict.fromkeys(COUNTERS, 0), {k: [] for k in ID_LISTS}
        trace = {'gemini': 0, 'vision': 0, 'rows': 0, 'usd': Decimal('0'), 'peak': USD_PER_GEMINI_CALL,
                 'reserve': USD_PER_GEMINI_CALL, 'cap': cap, 'over': False}
        streak, stopped = {'service': 0, 'fetch': 0}, ''
        with _traced(trace):
            for done, pk in enumerate(todo, 1):
                if trace['usd'] + trace['peak'] * MAX_GEMINI_CALLS + USD_PER_VISION_OCR > cap:
                    stopped = f'the next document could pass the cap US${cap}'
                    break
                try:
                    stopped = self._one(n, ids, streak, pk)
                except CapReached:
                    stopped = f'the next billed row could pass the cap US${cap} (stopped mid-read)'
                if done % PROGRESS_EVERY == 0:
                    self.stdout.write(f'  progress: {done} documents, {trace["gemini"]} Gemini calls, '
                                      f'US${trace["usd"].quantize(Decimal("0.0001"))}')
                if stopped:
                    break
        n['gemini_calls'], n['vision_ocr'] = trace['gemini'], trace['vision']
        out = self.stdout.write
        out(f'done: {n["docs"]} documents, charged up to US${trace["usd"].quantize(Decimal("0.0001"))} (ASSUMED prices)')
        if stopped:
            out(f'STOPPED: {stopped}')
        out(', '.join(f'{k} {v}' for k, v in n.items()))
        for key, pks in ids.items():
            if pks:
                out(f'{key} ids: {",".join(map(str, pks[:IDS_SHOWN]))}'
                    + (f' (+{len(pks) - IDS_SHOWN} more)' if len(pks) > IDS_SHOWN else ''))

    @staticmethod
    def _one(n, ids, streak, pk):
        n['docs'] += 1
        try:
            doc = ApplicantDocument.objects.filter(pk=pk).first()
            with usage.usage_context(source=USAGE_SOURCE):     # a PLATFORM meter row
                image = vision._fetch_image_bytes(doc.storage_path) if doc else None
                if not image:
                    n['fetch_failed'] += 1
                    ids['fetch_failed'].append(pk)
                    streak['fetch'] += 1
                    return f'{FAIL_FAST} fetches in a row failed (check Storage)' if streak['fetch'] >= FAIL_FAST else ''
                streak['fetch'] = 0
                text = (vision.extract_text(image, doc.content_type or '') or {}).get('text') or ''
                new = vision.extract_document_fields(text, 'salary_slip') if text.strip() else None
        except CapReached:
            raise
        except Exception as e:    # one document never stops the run; the type only, never the message
            logger.warning('eval_warning_topics: doc %s failed (%s)', pk, type(e).__name__)
            n['error'] += 1
            return ''
        failed = 'ocr_failed' if new is None else 'service_error' if new.get('error') else ''
        if failed:
            n[failed] += 1
            ids['service_error'].append(pk)
            streak['service'] += 1
            return f'{FAIL_FAST} service errors in a row (check the keys, quota or models)' \
                if streak['service'] >= FAIL_FAST else ''
        streak['service'] = 0
        n['read'] += 1
        tally_topics(n, ids, doc, new)
        return ''
