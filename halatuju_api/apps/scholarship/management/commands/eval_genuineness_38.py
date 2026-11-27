"""OCR-16 paid eval: the four genuineness checks on 3.8 Flash, against the stored 2.5 verdicts and the reviewer.

Run on the release-decisions Cloud Run job from the deployed image, BEFORE `GENUINENESS_MODEL` is set on the
service. It forces the 3.8 path (`ai_model.ask` with `model=`) on a sample of live documents, per check:

  * ic           — `ic.ic_genuineness` on live ic / parent_ic rows with a stored MyKad verdict;
  * results_slip — `results_doc.results_visual_markers` (QR + crest) on live results slips with a stored
                   signature verdict. Where the private OCR store holds the slip's text the verdict is
                   re-scored (`signature_genuineness`) with the new markers; every slip also compares each
                   marker the stored verdict scored;
  * supporting   — `supporting_doc.doc_genuineness` on live str / birth_certificate / epf rows whose stored
                   verdict is the holistic read (no probability);
  * sample       — `sample_stamp._ask_model` on stored-flagged samples, then rows with a sample word in their
                   stored text, then rows the check stamped clean.

Each sample takes `--fake-ids` (known fakes, e.g. the typed-fake class) first, then reviewer-rejected rows, then
rows the stored verdict flagged, then the newest. It reports per check: agreement with the stored 2.5 verdict,
agreement with the reviewer (verified = genuine, rejected = not), NEW not-genuine on a reviewer-accepted row the
2.5 verdict called genuine (must be 0), genuine on a known fake (must be 0), malformed answers after the retry,
document refusals and service errors.

WRITES NOTHING: no verdict, no vision_fields, no genuineness field, no read state (a guard refuses every
document save during the run). The one row is the seam's own billing meter, a PLATFORM row
(`usage_context(source=USAGE_SOURCE)`, no organisation, no application), as in `capture_parent_ic_text`.

DRY RUN BY DEFAULT: counts and the estimated cost only; no download, no AI call. `--run` needs `--limit`
(documents, at most `MAX_LIMIT`) and `--max-cost-usd` (at most `MAX_COST_USD`); it stops before the document
that could pass the cap, and after `FAIL_FAST` AI service errors (or Storage fetch failures) in a row.

PRIVATE: prints counts and document ids only; never a name, an IC number, document text, model free text or a key.

    python manage.py eval_genuineness_38                                                   # dry run
    python manage.py eval_genuineness_38 --run --limit 300 --max-cost-usd 3.00 --fake-ids 12,34
"""
import logging
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from unittest import mock

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.scholarship import usage, vision
from apps.scholarship.genuineness import ai_model
from apps.scholarship.genuineness.bands import canonical_status, stored_authenticity
from apps.scholarship.models import ApplicantDocument, ApplicantDocumentOcrText
from apps.scholarship.read_errors import DOCUMENT_FAILED
from apps.scholarship.vision.slip_read import is_slip_model

logger = logging.getLogger(__name__)

USAGE_SOURCE = 'ocr16_genuineness_eval'
DEFAULT_MODEL = 'gemini-3.8-flash'
#: Documents per check (the brief: ~100 ICs, 100 slips, 60 supporting docs, 40 sample-stamp docs).
SAMPLE = {'ic': 100, 'results_slip': 100, 'supporting': 60, 'sample': 40}
CHECKS = tuple(SAMPLE)
MAX_LIMIT = 400
MAX_COST_USD = Decimal('5.00')
FAIL_FAST = 5
PROGRESS_EVERY = 50
IDS_SHOWN = 50
#: Per 3.8 Flash call, an UPPER bound: twice the S5 gate's 2.5 per-call figure (`eval/slip_s5_gate.py`
#: USD_PER_CALL_38_MAX). 3.8 Flash has no row in `eval/offer_fresh_gemini.PRICES`; this is ASSUMED, so the
#: cap can only stop early. Each document reserves `ai_model.MAX_CALLS` calls before it is read.
USD_PER_CALL_38 = Decimal('0.008')
#: The token prices assumed for 3.8 Flash (US$ per 1M tokens; the S5 gate's PRICE_38_ASSUMED), shown only.
PRICE_38_ASSUMED = {'input': 0.60, 'output': 5.00}

_TYPES = {'ic': ('ic', 'parent_ic'), 'results_slip': ('results_slip',),
          'supporting': ('str', 'birth_certificate', 'epf')}
_SAMPLE_WORDS = ('sample', 'contoh', 'specimen', 'spesimen')
_VISUAL = {'has_qr': 'QR CODE', 'has_crest': 'JATA NEGARA'}

COUNTERS = ('docs', 'calls', 'answered', 'no_signal', 'service_error', 'malformed_after_retry',
            'document_refused', 'fetch_failed', 'error', 'agree_stored', 'disagree_stored',
            'agree_reviewer', 'disagree_reviewer', 'new_not_genuine_on_accepted', 'genuine_on_known_fake',
            'rescored_from_text', 'marker_agree', 'marker_disagree', 'marker_lost_on_accepted')
ID_LISTS = ('disagree_stored', 'new_not_genuine_on_accepted', 'genuine_on_known_fake',
            'malformed_after_retry', 'service_error', 'marker_lost_on_accepted')


def _live(types):
    qs = ApplicantDocument.objects.filter(doc_type__in=types).exclude(storage_path='')
    return ApplicantDocument.live(qs)


def _sample_word_ids():
    q = Q()
    for word in _SAMPLE_WORDS:
        q |= Q(text__icontains=word)
    return set(ApplicantDocumentOcrText.objects.filter(q).values_list('document_id', flat=True))


def stored_value(check, doc_type, vf):
    """The stored 2.5 answer as a canonical verdict ('genuine' / 'suspect' / 'not_<type>' / 'sample'), or ''."""
    auth = stored_authenticity(vf)
    if check == 'sample':
        if auth.get('sample'):
            return 'sample'
        return 'genuine' if isinstance(vf, dict) and vf.get('sample_check_version') else ''
    if check == 'results_slip' and 'probability' not in auth:
        return ''
    if check in ('ic', 'supporting') and 'probability' in auth:
        return ''      # a signature scorer's verdict, not this check's
    return canonical_status(auth.get('status'), doc_type)


def genuineness_sample(checks, fake_ids, sizes=None):
    """{check: [document id, ...]} in priority order: known fakes, rejected, flagged, newest."""
    sizes = sizes or SAMPLE
    words = _sample_word_ids() if 'sample' in checks else set()
    out = {}
    for check in checks:
        qs = (ApplicantDocument.live(ApplicantDocument.objects.exclude(storage_path='')) if check == 'sample'
              else _live(_TYPES[check]))
        rows = []
        for pk, doc_type, vs, vf in qs.values_list('pk', 'doc_type', 'verification_status', 'vision_fields').iterator():
            stored = stored_value(check, doc_type, vf)
            if not stored and pk not in fake_ids and not (check == 'sample' and pk in words):
                continue
            flagged = stored not in ('', 'genuine')
            rank = (0 if pk in fake_ids else 1 if vs == 'rejected' else 2 if flagged
                    else 3 if check == 'sample' and pk in words else 4)
            rows.append((rank, -pk))
        rows.sort()
        out[check] = [-neg for _rank, neg in rows[:sizes[check]]]
    return out


def interleave(by_check):
    """Round-robin over the checks, so a cap stop still leaves every check sampled."""
    order, i = [], 0
    while any(i < len(ids) for ids in by_check.values()):
        order.extend((check, ids[i]) for check, ids in by_check.items() if i < len(ids))
        i += 1
    return order


def _new_value(check, doc, image, model, text):
    """One forced 3.8 read → (canonical new verdict or '', {marker: bool} for the slip)."""
    from apps.scholarship.genuineness import ic, results_doc, sample_stamp, supporting_doc
    ct = doc.content_type or ''
    if check == 'ic':
        return canonical_status(ic.ic_genuineness(image, ct, model=model).get('status'), doc.doc_type), {}
    if check == 'supporting':
        r = supporting_doc.doc_genuineness(image, ct, doc.doc_type, model=model)
        return canonical_status(r.get('status'), doc.doc_type), {}
    if check == 'sample':
        v = sample_stamp._ask_model(image, ct, model=model)
        return ('' if v is None else 'sample' if v else 'genuine'), {}
    markers = results_doc.results_visual_markers(image, ct, model=model)
    if not markers or not (text or '').strip():
        return '', markers
    sg = results_doc.signature_genuineness(text, has_qr=markers['has_qr'], has_crest=markers['has_crest'])
    return canonical_status(sg.get('status'), doc.doc_type), markers


@contextmanager
def _traced(trace):
    """Count every 3.8 call and keep each ask's outcome class (never its text); refuse document writes."""
    real_call, real_ask = getattr(vision, '_call_gemini_json'), ai_model.ask

    def counted(*a, **k):
        trace['calls'] += 1
        return real_call(*a, **k)

    def asked(*a, **k):
        r = real_ask(*a, **k)
        err = str(r.get('_error') or '') if isinstance(r, dict) else ''
        trace['outcome'] = ('' if not err else 'malformed_after_retry' if ai_model.MALFORMED in err
                            else 'document_refused' if err.startswith(DOCUMENT_FAILED) else 'service_error')
        return r

    def refuse(*a, **k):
        raise RuntimeError('eval_genuineness_38 writes nothing')

    with mock.patch.object(vision, '_call_gemini_json', counted), mock.patch.object(ai_model, 'ask', asked), \
            mock.patch.object(ApplicantDocument, 'save', refuse), \
            mock.patch.object(ApplicantDocumentOcrText, 'save', refuse):
        yield


def tally_the_read(tally, check, doc, stored, new, markers, fake_ids):
    """Add one read to the tally. Ids only, never content."""
    t, ids = tally[check]['n'], tally[check]['ids']
    pk, vs = doc.pk, doc.verification_status
    if new:
        t['answered'] += 1
    if new and stored:
        same = new == stored
        t['agree_stored' if same else 'disagree_stored'] += 1
        if not same:
            ids['disagree_stored'].append(pk)
    if new and vs in ('verified', 'rejected'):
        t['agree_reviewer' if (new == 'genuine') == (vs == 'verified') else 'disagree_reviewer'] += 1
    if new not in ('', 'genuine') and vs == 'verified' and stored == 'genuine':
        t['new_not_genuine_on_accepted'] += 1
        ids['new_not_genuine_on_accepted'].append(pk)
    if new == 'genuine' and pk in fake_ids:
        t['genuine_on_known_fake'] += 1
        ids['genuine_on_known_fake'].append(pk)
    if check == 'results_slip' and markers:
        auth = stored_authenticity(doc.vision_fields)
        present, missing = set(auth.get('present') or []), set(auth.get('missing') or [])
        for key, label in _VISUAL.items():
            if label not in present | missing:
                continue       # the stored verdict did not score this marker
            was = label in present
            t['marker_agree' if was == markers.get(key) else 'marker_disagree'] += 1
            if was and not markers.get(key) and vs == 'verified':
                t['marker_lost_on_accepted'] += 1
                ids['marker_lost_on_accepted'].append(pk)


class Command(BaseCommand):
    help = ('OCR-16: the four genuineness checks on 3.8 Flash against the stored 2.5 verdicts and the reviewer. '
            'Writes nothing. DRY RUN unless --run (which needs --limit and --max-cost-usd).')

    def add_arguments(self, parser):
        parser.add_argument('--run', action='store_true', help='Call 3.8 Flash. Without it: counts only.')
        parser.add_argument('--limit', type=int, default=None, help=f'At most this many documents (1 to {MAX_LIMIT}).')
        parser.add_argument('--max-cost-usd', default=None, help=f'Stop before the cap (at most {MAX_COST_USD}).')
        parser.add_argument('--checks', default=','.join(CHECKS), help='Comma list of: ' + ', '.join(CHECKS))
        parser.add_argument('--fake-ids', default='', help='Comma list of known-fake document ids (read first).')
        parser.add_argument('--model', default=DEFAULT_MODEL, help='A 3.8 Flash name (the slip allow-list).')

    def handle(self, *args, **opts):
        limit, cap, checks, fakes = self._checked(opts)
        order = interleave(genuineness_sample(checks, fakes))
        todo = order[:limit] if limit else order
        out = self.stdout.write
        out(f'eval_genuineness_38: {"RUN" if opts["run"] else "DRY RUN (no download, no AI call, no write)"}')
        out(f'  model forced: {opts["model"]}; service setting {ai_model.SETTING}: '
            f'{ai_model.chosen_model() or "unset (2.5 Flash cascade)"}')
        for check in checks:
            out(f'  {check}: {sum(1 for c, _ in todo if c == check)} to read')
        out(f'  known fakes given: {len(fakes)}')
        out(f'  estimated calls: {len(todo)} to {ai_model.MAX_CALLS * len(todo)} (one retry at most)')
        out(f'  estimated cost: up to US${(USD_PER_CALL_38 * ai_model.MAX_CALLS * len(todo)).quantize(Decimal("0.01"))}'
            f' at an ASSUMED US${USD_PER_CALL_38} per call')
        if opts['run']:
            self._run(todo, cap, opts['model'], fakes, checks)

    def _checked(self, opts):
        limit, raw_cap = opts['limit'], opts['max_cost_usd']
        if limit is not None and not 1 <= limit <= MAX_LIMIT:
            raise CommandError(f'--limit must be 1 to {MAX_LIMIT}.')
        checks = [c.strip() for c in opts['checks'].split(',') if c.strip()]
        if not checks or any(c not in CHECKS for c in checks):
            raise CommandError('--checks takes: ' + ', '.join(CHECKS))
        try:
            fakes = {int(x) for x in opts['fake_ids'].split(',') if x.strip()}
        except ValueError:
            raise CommandError('--fake-ids takes document ids, e.g. 12,34.') from None
        if not is_slip_model(opts['model']):
            raise CommandError('--model must be a 3.8 Flash name.')
        if not opts['run']:
            return limit, None, checks, fakes
        if limit is None or raw_cap is None:
            raise CommandError('--run needs --limit and --max-cost-usd.')
        try:
            cap = Decimal(str(raw_cap))
        except InvalidOperation:
            raise CommandError('--max-cost-usd must be a number, e.g. 3.00.') from None
        if not (cap.is_finite() and Decimal('0') < cap <= MAX_COST_USD):
            raise CommandError(f'--max-cost-usd must be above 0 and at most {MAX_COST_USD}.')
        return limit, cap, checks, fakes

    def _run(self, todo, cap, model, fakes, checks):
        tally = {c: {'n': dict.fromkeys(COUNTERS, 0), 'ids': {k: [] for k in ID_LISTS}} for c in checks}
        trace = {'calls': 0, 'outcome': ''}
        texts = dict(ApplicantDocumentOcrText.objects.filter(
            document_id__in=[pk for c, pk in todo if c == 'results_slip']).values_list('document_id', 'text'))
        streak, stopped, done = {'service': 0, 'fetch': 0}, '', 0
        with _traced(trace):
            for check, pk in todo:
                spent = USD_PER_CALL_38 * trace['calls']
                if spent + USD_PER_CALL_38 * ai_model.MAX_CALLS > cap:
                    stopped = f'the next document could pass the cap US${cap}'
                    break
                stopped = self._one(tally, trace, streak, check, pk, model, fakes, texts)
                done += 1
                if done % PROGRESS_EVERY == 0:
                    logger.info('eval_genuineness_38: %s documents, %s calls', done, trace['calls'])
                if stopped:
                    break
        self._report(tally, trace, done, stopped)

    def _one(self, tally, trace, streak, check, pk, model, fakes, texts):
        t = tally[check]['n']
        t['docs'] += 1
        before = trace['calls']
        trace['outcome'] = ''
        try:
            doc = ApplicantDocument.objects.filter(pk=pk).first()
            image = vision._fetch_image_bytes(doc.storage_path) if doc else None
            if not image:
                t['fetch_failed'] += 1
                streak['fetch'] += 1
                return f'{FAIL_FAST} fetches in a row failed (check Storage)' if streak['fetch'] >= FAIL_FAST else ''
            streak['fetch'] = 0
            with usage.usage_context(source=USAGE_SOURCE):     # a PLATFORM meter row
                new, markers = _new_value(check, doc, image, model, texts.get(pk))
            stored = stored_value(check, doc.doc_type, doc.vision_fields)
            if check == 'results_slip' and markers and (texts.get(pk) or '').strip():
                t['rescored_from_text'] += 1
            tally_the_read(tally, check, doc, stored, new, markers, fakes)
        except Exception as e:    # one document never stops the run; the type only, never the message
            logger.warning('eval_genuineness_38: doc %s failed (%s)', pk, type(e).__name__)
            t['error'] += 1
        finally:
            t['calls'] += trace['calls'] - before
        outcome = trace['outcome']
        if outcome:
            t[outcome] += 1
            if outcome in tally[check]['ids']:
                tally[check]['ids'][outcome].append(pk)
        streak['service'] = streak['service'] + 1 if outcome == 'service_error' else 0
        if streak['service'] >= FAIL_FAST:
            return f'{FAIL_FAST} AI service errors in a row (check the key, quota or model name)'
        return ''

    def _report(self, tally, trace, done, stopped):
        out = self.stdout.write
        out(f'done: {done} documents, {trace["calls"]} calls, charged up to US${USD_PER_CALL_38 * trace["calls"]} (assumed)')
        if stopped:
            out(f'STOPPED: {stopped}')
        for check, row in tally.items():
            n = row['n']
            n['no_signal'] = n['docs'] - n['answered'] - n['fetch_failed'] - n['error']
            out(f'[{check}] ' + ', '.join(f'{k} {v}' for k, v in n.items()))
            for key, ids in row['ids'].items():
                if ids:
                    out(f'[{check}] {key} ids: {",".join(map(str, ids[:IDS_SHOWN]))}'
                        + (f' (+{len(ids) - IDS_SHOWN} more)' if len(ids) > IDS_SHOWN else ''))
        gates = {c: (r['n']['new_not_genuine_on_accepted'], r['n']['genuine_on_known_fake']) for c, r in tally.items()}
        out('GATES (both must be 0): ' + '; '.join(f'{c} new_not_genuine_on_accepted {a}, genuine_on_known_fake {b}'
                                                    for c, (a, b) in gates.items()))
