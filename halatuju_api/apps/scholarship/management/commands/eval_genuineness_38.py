"""OCR-16 paid eval: the four genuineness checks on 3.8 Flash, against the stored 2.5 verdicts and the reviewer.

Run on the release-decisions Cloud Run job from the deployed image, BEFORE `GENUINENESS_MODEL` is set on the
service. It forces the 3.8 path (`ai_model.ask` with `model=`) on a sample of live documents, per check:

  * ic           — `ic.ic_genuineness` on live ic / parent_ic rows with a stored MyKad verdict;
  * results_slip — `results_doc.results_visual_markers` (QR + crest) on live results slips with a stored
                   signature verdict, re-scored as live does (`vision.authenticity._auth_results_slip`): with
                   the slip's stored OCR text, `signature_genuineness` with the new markers (both absent when
                   3.8 gave none); without stored text live gives no verdict, so the slip is NOT GATED
                   (`not_gated_no_text`) and only its markers are compared with the stored ones;
  * supporting   — `supporting_doc.doc_genuineness` on live str / birth_certificate / epf rows whose stored
                   verdict is the holistic read (no probability);
  * sample       — `sample_stamp._ask_model` on stored-flagged samples, then rows with a sample word in their
                   stored text, then rows the check stamped clean.

Known fakes come first in each sample. `--fake-ids` (typed or forged fakes) go ONLY through the check of their
own document type (never the sample check: a fake MyKad is rightly "not a SAMPLE stamp");
`--sample-fake-ids` (stamped SAMPLE / CONTOH uploads) go ONLY through the sample check. A known fake that no
chosen check samples is listed. Then reviewer-rejected rows, then rows the stored verdict flagged, then the
newest. It reports per check: agreement with the stored 2.5 verdict, agreement with the reviewer (verified =
genuine, rejected = not), malformed answers after the retry, document refusals, service errors and THE GATES
(each must be 0): a not-genuine 3.8 verdict on ANY reviewer-accepted row (whatever its stored value; the subset
whose stored value was genuine is shown too), genuine on a known fake, a known fake left WITHOUT a verdict
(`unanswered_known_fake`, with its ids: fetch failed, call errored, refused or malformed twice, a slip with no
stored text, or not reached before a stop or the limit), and for the slip a marker the stored verdict had found
that 3.8 lost on an accepted row. A slip fake whose marker read errored is unanswered too (scored from text
alone). A known fake no chosen check reads fails the gates, and so does an incomplete run: a stop (cost cap,
service errors, fetch failures), a chosen check with 0 answers, or a reviewer-accepted row in the planned sample
(what `--limit` chose) left untested by a stop, a fetch failure, an error or a service error
(`unanswered_accepted`). The last line says GATES MET or GATES NOT MET. A gate with nothing to test is said so
(`reviewer gate NOT TESTED (0 accepted rows)`, `known-fake gate NOT TESTED (0 testable fakes)`) and the last line
then reads `GATES MET (untested: ...)`, never a plain GATES MET. An answer that is unreadable (not JSON) twice counts as malformed, not refused.
Malformed answers on known fakes and on reviewer-rejected rows are shown beside the gates.
Per check it also prints the DIRECTION of each disagreement with the stored verdict: counts per `stored -> new`
and one `id: stored -> new` line per differing document (canonical statuses and ids only).
`--ids 1,2,3` runs only those documents, each through the check of its own type (`--limit` then defaults to the
id count); ids of a type no check reads, and ids that are not live documents, are listed and skipped.

WRITES NOTHING: no verdict, no vision_fields, no genuineness field, no read state (a guard refuses every
document save during the run, and `ocr_keep.writes_refused` every OCR-text save). It reads stored text only
through `ocr_keep` (`kept_texts` for the slips, `ids_with_kept_text_containing` for the sample words). The one
row is the seam's own billing meter, a PLATFORM row (`usage_context(source=USAGE_SOURCE)`, no organisation, no
application), as in `capture_parent_ic_text`.

DRY RUN BY DEFAULT: counts and the estimated cost only; no download, no AI call. `--run` needs `--limit`
(documents, at most `MAX_LIMIT`) and `--max-cost-usd` (at most `MAX_COST_USD`; suggested 2.00); it stops before
the document that could pass the cap, and after `FAIL_FAST` AI service errors (or Storage fetch failures) in a
row. COST: 3.8 Flash has no price row, so each call is charged at an ASSUMED upper bound of US$0.008
(`USD_PER_CALL_38`). When a Gemini response reports its token counts the call is charged at those tokens at the
assumed 3.8 prices (`PRICE_38_ASSUMED`) when that is higher; the flat US$0.008 is the floor.

PRIVATE: prints counts and document ids only; never a name, an IC number, document text, model free text or a key.

    python manage.py eval_genuineness_38                                                   # dry run
    python manage.py eval_genuineness_38 --run --ids 12,34,56 --max-cost-usd 0.60                # only these ids
    python manage.py eval_genuineness_38 --run --limit 240 --max-cost-usd 2.00 --fake-ids 12,34 --sample-fake-ids 56
"""
import logging
from collections import Counter
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from unittest import mock

from django.core.management.base import BaseCommand, CommandError

from apps.scholarship import ocr_keep, usage, vision
from apps.scholarship.genuineness import ai_model
from apps.scholarship.genuineness.bands import canonical_status, stored_authenticity
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.read_errors import DOCUMENT_FAILED, UNPARSEABLE_RESPONSE
from apps.scholarship.vision.slip_read import is_slip_model

logger = logging.getLogger(__name__)

USAGE_SOURCE = 'ocr16_genuineness_eval'
DEFAULT_MODEL = 'gemini-3.8-flash'
#: Documents per check (the brief: ~100 ICs, 100 slips, 60 supporting docs, 40 sample-stamp docs).
SAMPLE = {'ic': 100, 'results_slip': 100, 'supporting': 60, 'sample': 40}
CHECKS = tuple(SAMPLE)
MAX_LIMIT = 400
MAX_COST_USD = Decimal('5.00')
SUGGESTED_COST_USD = Decimal('2.00')
FAIL_FAST = 5
PROGRESS_EVERY = 50
IDS_SHOWN = 50
CHANGES_SHOWN = 400
#: Per 3.8 Flash call, an ASSUMED upper bound: twice the S5 gate's 2.5 per-call figure (`eval/slip_s5_gate.py`
#: USD_PER_CALL_38_MAX). 3.8 Flash has no row in `eval/offer_fresh_gemini.PRICES`. It is the FLOOR of each
#: call's charge: a response that reports more tokens is charged at them (`call_cost`).
USD_PER_CALL_38 = Decimal('0.008')
#: The token prices assumed for 3.8 Flash (US$ per 1M tokens; the S5 gate's PRICE_38_ASSUMED).
PRICE_38_ASSUMED = {'input': 0.60, 'output': 5.00}

_TYPES = {'ic': ('ic', 'parent_ic'), 'results_slip': ('results_slip',),
          'supporting': ('str', 'birth_certificate', 'epf')}
_SAMPLE_WORDS = ('sample', 'contoh', 'specimen', 'spesimen')
_VISUAL = {'has_qr': 'QR CODE', 'has_crest': 'JATA NEGARA'}

COUNTERS = ('docs', 'calls', 'answered', 'no_signal', 'service_error', 'malformed_after_retry',
            'document_refused', 'fetch_failed', 'error', 'agree_stored', 'disagree_stored',
            'agree_reviewer', 'disagree_reviewer', 'new_not_genuine_on_accepted',
            'new_not_genuine_on_accepted_stored_genuine', 'genuine_on_known_fake',
            'malformed_on_known_fake', 'malformed_on_rejected', 'unanswered_known_fake', 'rescored_from_text',
            'not_gated_no_text', 'marker_agree', 'marker_disagree', 'marker_lost_on_accepted', 'unanswered_accepted')
ID_LISTS = ('disagree_stored', 'new_not_genuine_on_accepted', 'genuine_on_known_fake', 'unanswered_known_fake',
            'malformed_after_retry', 'malformed_on_known_fake', 'malformed_on_rejected', 'document_refused',
            'service_error', 'not_gated_no_text', 'marker_lost_on_accepted', 'unanswered_accepted')
#: The counts that must be 0 per check (the GATES line); `unanswered_known_fake` = a known fake with no verdict,
#: `unanswered_accepted` = a reviewer-accepted row of the planned sample that 3.8 was never fairly asked about.
GATE_KEYS = {c: ('new_not_genuine_on_accepted', 'genuine_on_known_fake')
             + (('marker_lost_on_accepted',) if c == 'results_slip' else ())
             + ('unanswered_known_fake', 'unanswered_accepted') for c in CHECKS}
#: The gate counts whose ids go on the GATES line.
GATE_IDS = ('unanswered_known_fake', 'unanswered_accepted')


def _live(types):
    qs = ApplicantDocument.objects.filter(doc_type__in=types).exclude(storage_path='')
    return ApplicantDocument.live(qs)


def _sample_pool():
    """The documents the sample check reads from: every live document with a file."""
    return ApplicantDocument.live(ApplicantDocument.objects.exclude(storage_path=''))


def _sample_word_ids():
    """The ids in the sample pool whose stored text holds a sample word (ids only, through ocr_keep)."""
    return ocr_keep.ids_with_kept_text_containing(_SAMPLE_WORDS, _sample_pool().values('pk'))


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


def fakes_for(check, fake_ids, sample_fake_ids):
    """The known fakes one check reads: sample-stamp fakes for the sample check, the others for the rest."""
    return set(sample_fake_ids) if check == 'sample' else set(fake_ids)


def genuineness_sample(checks, fake_ids, sizes=None, sample_fake_ids=()):
    """{check: [document id, ...]} in priority order: known fakes, rejected, flagged, newest."""
    sizes = sizes or SAMPLE
    words = _sample_word_ids() if 'sample' in checks else set()
    out = {}
    for check in checks:
        fakes = fakes_for(check, fake_ids, sample_fake_ids)
        qs = _sample_pool() if check == 'sample' else _live(_TYPES[check])
        rows = []
        for pk, doc_type, vs, vf in qs.values_list('pk', 'doc_type', 'verification_status', 'vision_fields').iterator():
            stored = stored_value(check, doc_type, vf)
            if not stored and pk not in fakes and not (check == 'sample' and pk in words):
                continue
            flagged = stored not in ('', 'genuine')
            rank = (0 if pk in fakes else 1 if vs == 'rejected' else 2 if flagged
                    else 3 if check == 'sample' and pk in words else 4)
            rows.append((rank, -pk))
        rows.sort()
        out[check] = [-neg for _rank, neg in rows[:sizes[check]]]
    return out


def check_of_type(doc_type):
    """The check that reads a document type ('' when none does; the sample check is never picked by type)."""
    return next((c for c, types in _TYPES.items() if doc_type in types), '')


def sample_of_ids(ids, checks):
    """(by_check, unknown, unread): the given document ids routed to the check of their own type.
    `unknown` = not a live document with a file; `unread` = a type no chosen check reads."""
    found = dict(_sample_pool().filter(pk__in=ids).values_list('pk', 'doc_type'))
    by_check, unread = {}, []
    for pk in ids:
        if pk not in found:
            continue
        check = check_of_type(found[pk])
        if check and check in checks:
            by_check.setdefault(check, []).append(pk)
        else:
            unread.append(pk)
    return by_check, [pk for pk in ids if pk not in found], unread


def unsampled_fakes(by_check, fake_ids, sample_fake_ids):
    """Known fakes no chosen check will read (another type, not live, or their check not chosen)."""
    typed = set().union(*(ids for c, ids in by_check.items() if c != 'sample'))
    return sorted((set(fake_ids) - typed) | (set(sample_fake_ids) - set(by_check.get('sample', ()))))


def outcome_of(answer):
    """The class of one `ai_model.ask` answer: '' (an answer), 'malformed_after_retry' (failed the check, or
    unreadable JSON, after the retry), 'document_refused' (refused twice) or 'service_error'."""
    err = str(answer.get('_error') or '') if isinstance(answer, dict) else ''
    if not err:
        return ''
    if ai_model.MALFORMED in err or UNPARSEABLE_RESPONSE in err:
        return 'malformed_after_retry'
    return 'document_refused' if err.startswith(DOCUMENT_FAILED) else 'service_error'


def unanswered_fakes(by_check, known, answered):
    """{check: [id, ...]}: the known fakes a check was to read that got no verdict, for any reason."""
    return {c: [pk for pk in ids if pk in fakes_for(c, *known) and pk not in answered.get(c, ())]
            for c, ids in by_check.items()}


def interleave(by_check):
    """Round-robin over the checks, so a cap stop still leaves every check sampled."""
    order, i = [], 0
    while any(i < len(ids) for ids in by_check.values()):
        order.extend((check, ids[i]) for check, ids in by_check.items() if i < len(ids))
        i += 1
    return order


def call_cost(tokens):
    """One 3.8 call's charge: the flat assumed US$0.008, or its reported tokens at the assumed prices if higher."""
    tin, tout = (usage._int_or_none(v) for v in (tokens or (None, None)))
    if tin is None and tout is None:
        return USD_PER_CALL_38
    metered = (Decimal(tin or 0) * Decimal(str(PRICE_38_ASSUMED['input']))
               + Decimal(tout or 0) * Decimal(str(PRICE_38_ASSUMED['output']))) / Decimal(1_000_000)
    return max(USD_PER_CALL_38, metered)


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
    if not (text or '').strip():
        return '', markers           # live gives no verdict without OCR text: not gated (counted apart)
    # As live (`_auth_results_slip`): no markers from the model reads as both absent, never as no verdict.
    sg = results_doc.signature_genuineness(text, has_qr=markers.get('has_qr', False),
                                           has_crest=markers.get('has_crest', False))
    return canonical_status(sg.get('status'), doc.doc_type), markers


@contextmanager
def _traced(trace):
    """Count and price every 3.8 call, keep each ask's outcome class (never its text); refuse document writes."""
    real_call, real_ask, real_meter = getattr(vision, '_call_gemini_json'), ai_model.ask, usage.record_usage

    def counted(*a, **k):
        trace['calls'] += 1
        trace['tokens'] = None
        try:
            return real_call(*a, **k)
        finally:
            cost = call_cost(trace['tokens'])
            trace['usd'] += cost
            trace['peak'] = max(trace['peak'], cost)

    def metered(service, *a, **k):
        if service == usage.GEMINI:
            trace['tokens'] = (k.get('input_tokens'), k.get('output_tokens'))
        return real_meter(service, *a, **k)

    def asked(*a, **k):
        r = real_ask(*a, **k)
        trace['outcome'] = outcome_of(r)
        return r

    def refuse(*a, **k):
        raise RuntimeError('eval_genuineness_38 writes nothing')

    with mock.patch.object(vision, '_call_gemini_json', counted), mock.patch.object(ai_model, 'ask', asked), \
            mock.patch.object(usage, 'record_usage', metered), \
            mock.patch.object(ApplicantDocument, 'save', refuse), ocr_keep.writes_refused('eval_genuineness_38'):
        yield


def tally_the_read(tally, check, doc, stored, new, markers, fake_ids):
    """Add one read to the tally. `fake_ids` are this check's known fakes. Ids only, never content."""
    t, ids = tally[check]['n'], tally[check]['ids']
    pk, vs = doc.pk, doc.verification_status
    if new:
        t['answered'] += 1
    if new and stored:
        same = new == stored
        t['agree_stored' if same else 'disagree_stored'] += 1
        if not same:
            ids['disagree_stored'].append(pk)
            tally[check]['changes'].append((pk, stored, new))
    if new and vs in ('verified', 'rejected'):
        t['agree_reviewer' if (new == 'genuine') == (vs == 'verified') else 'disagree_reviewer'] += 1
    if new not in ('', 'genuine') and vs == 'verified':      # the gate: whatever the stored value was
        t['new_not_genuine_on_accepted'] += 1
        ids['new_not_genuine_on_accepted'].append(pk)
        if stored == 'genuine':
            t['new_not_genuine_on_accepted_stored_genuine'] += 1
    if new and vs == 'verified':
        tally[check]['accepted_tested'].add(pk)
    if new and pk in fake_ids:
        tally[check]['fakes_answered'].add(pk)
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


def _add(tally, check, key, pk):
    tally[check]['n'][key] += 1
    if key in tally[check]['ids']:
        tally[check]['ids'][key].append(pk)


class Command(BaseCommand):
    help = ('OCR-16: the four genuineness checks on 3.8 Flash against the stored 2.5 verdicts and the reviewer. '
            'Writes nothing. DRY RUN unless --run (which needs --limit and --max-cost-usd; suggested '
            f'--max-cost-usd {SUGGESTED_COST_USD}). Each call is charged at an ASSUMED upper bound of '
            f'US${USD_PER_CALL_38} (3.8 Flash has no price row), or at its reported tokens when higher.')

    def add_arguments(self, parser):
        parser.add_argument('--run', action='store_true', help='Call 3.8 Flash. Without it: counts only.')
        parser.add_argument('--limit', type=int, default=None, help=f'At most this many documents (1 to {MAX_LIMIT}).')
        parser.add_argument('--max-cost-usd', default=None,
                            help=f'Stop before the cap (suggested {SUGGESTED_COST_USD}, at most {MAX_COST_USD}).')
        parser.add_argument('--checks', default=','.join(CHECKS), help='Comma list of: ' + ', '.join(CHECKS))
        parser.add_argument('--fake-ids', default='',
                            help='Comma list of known-fake document ids, read first and ONLY by the check of '
                                 'their own type (ic, results_slip, supporting), never by the sample check.')
        parser.add_argument('--sample-fake-ids', default='',
                            help='Comma list of known SAMPLE-stamp document ids, read first by the sample check only.')
        parser.add_argument('--ids', default='',
                            help='Comma list of document ids: run ONLY these, each through the check of its own '
                                 'type (--limit then defaults to the id count).')
        parser.add_argument('--model', default=DEFAULT_MODEL, help='A 3.8 Flash name (the slip allow-list).')

    def handle(self, *args, **opts):
        limit, cap, checks, fakes, sample_fakes, model, ids = self._checked(opts)
        unknown, unread = [], []
        if ids:
            by_check, unknown, unread = sample_of_ids(ids, checks)
        else:
            by_check = genuineness_sample(checks, fakes, sample_fake_ids=sample_fakes)
        order = interleave(by_check)
        todo = order[:limit] if limit else order
        out = self.stdout.write
        out(f'eval_genuineness_38: {"RUN" if opts["run"] else "DRY RUN (no download, no AI call, no write)"}')
        out(f'  model forced: {model}; service setting {ai_model.SETTING}: '
            f'{ai_model.chosen_model() or "unset (2.5 Flash cascade)"}')
        for check in checks:
            out(f'  {check}: {sum(1 for c, _ in todo if c == check)} to read')
        if ids:
            out(f'  --ids: {len(ids)} given, {len(todo)} to read')
        if unread:
            out(f'  --ids of a type no chosen check reads (skipped): {",".join(map(str, unread[:IDS_SHOWN]))}')
        if unknown:
            out(f'  --ids not live documents with a file (skipped): {",".join(map(str, unknown[:IDS_SHOWN]))}')
        out(f'  known fakes given: {len(fakes)} by type, {len(sample_fakes)} sample-stamp')
        missed = unsampled_fakes(by_check, fakes, sample_fakes)
        if missed:
            out(f'  known fakes no chosen check reads: {",".join(map(str, missed[:IDS_SHOWN]))}'
                ' (a run would fail the gates)')
        out(f'  estimated calls: {len(todo)} to {ai_model.MAX_CALLS * len(todo)} (one retry at most)')
        out(f'  estimated cost: up to US${(USD_PER_CALL_38 * ai_model.MAX_CALLS * len(todo)).quantize(Decimal("0.01"))}'
            f' at an ASSUMED upper bound of US${USD_PER_CALL_38} per call (3.8 Flash has no price row; a run '
            'charges reported tokens when higher)')
        if opts['run']:
            self._run(todo, cap, model, (fakes, sample_fakes), by_check, missed)

    def _checked(self, opts):
        limit, raw_cap = opts['limit'], opts['max_cost_usd']
        try:
            ids = list(dict.fromkeys(int(x) for x in opts['ids'].split(',') if x.strip()))
        except ValueError:
            raise CommandError('--ids takes document ids, e.g. 12,34.') from None
        if ids and limit is None:
            limit = len(ids)
        if limit is not None and not 1 <= limit <= MAX_LIMIT:
            raise CommandError(f'--limit must be 1 to {MAX_LIMIT}.')
        checks = [c.strip() for c in opts['checks'].split(',') if c.strip()]
        if not checks or any(c not in CHECKS for c in checks):
            raise CommandError('--checks takes: ' + ', '.join(CHECKS))
        try:
            fakes = {int(x) for x in opts['fake_ids'].split(',') if x.strip()}
            sample_fakes = {int(x) for x in opts['sample_fake_ids'].split(',') if x.strip()}
        except ValueError:
            raise CommandError('--fake-ids and --sample-fake-ids take document ids, e.g. 12,34.') from None
        model = str(opts['model'] or '').strip().lower()
        if not is_slip_model(model):
            raise CommandError('--model must be a 3.8 Flash name.')
        if not opts['run']:
            return limit, None, checks, fakes, sample_fakes, model, ids
        if limit is None or raw_cap is None:
            raise CommandError('--run needs --limit and --max-cost-usd.')
        try:
            cap = Decimal(str(raw_cap))
        except InvalidOperation:
            raise CommandError(f'--max-cost-usd must be a number, e.g. {SUGGESTED_COST_USD}.') from None
        if not (cap.is_finite() and Decimal('0') < cap <= MAX_COST_USD):
            raise CommandError(f'--max-cost-usd must be above 0 and at most {MAX_COST_USD}.')
        return limit, cap, checks, fakes, sample_fakes, model, ids

    def _run(self, todo, cap, model, known, by_check, missed):
        tally = {c: {'n': dict.fromkeys(COUNTERS, 0), 'ids': {k: [] for k in ID_LISTS}, 'fakes_answered': set(),
                     'settled': set(), 'changes': [], 'accepted_tested': set()} for c in by_check}
        trace = {'calls': 0, 'outcome': '', 'usd': Decimal('0'), 'peak': USD_PER_CALL_38, 'tokens': None}
        texts = ocr_keep.kept_texts([pk for c, pk in todo if c == 'results_slip'])
        accepted = set(ApplicantDocument.objects.filter(pk__in={pk for _c, pk in todo}, verification_status='verified')
                       .values_list('pk', flat=True))
        streak, stopped, done = {'service': 0, 'fetch': 0}, '', 0
        with _traced(trace):
            for check, pk in todo:
                if trace['usd'] + trace['peak'] * ai_model.MAX_CALLS > cap:
                    stopped = f'the next document could pass the cap US${cap}'
                    break
                stopped = self._one(tally, trace, streak, check, pk, model, fakes_for(check, *known), texts)
                done += 1
                if done % PROGRESS_EVERY == 0:
                    logger.info('eval_genuineness_38: %s documents, %s calls', done, trace['calls'])
                if stopped:
                    break
        answered = {c: row['fakes_answered'] for c, row in tally.items()}
        for check, ids in unanswered_fakes(by_check, known, answered).items():
            tally[check]['n']['unanswered_known_fake'] = len(ids)
            tally[check]['ids']['unanswered_known_fake'] = ids
        for check, pk in todo:      # the planned sample: --limit's cut is fine, a stop or a failure is not
            if pk in accepted and pk not in tally[check]['settled']:
                _add(tally, check, 'unanswered_accepted', pk)
        testable = sum(1 for c, planned in by_check.items() for pk in planned if pk in fakes_for(c, *known))
        self._report(tally, trace, done, stopped, missed, testable)

    def _one(self, tally, trace, streak, check, pk, model, fakes, texts):
        t = tally[check]['n']
        t['docs'] += 1
        before, vs, read = trace['calls'], '', False
        trace['outcome'] = ''
        try:
            doc = ApplicantDocument.objects.filter(pk=pk).first()
            image = vision._fetch_image_bytes(doc.storage_path) if doc else None
            if not image:
                t['fetch_failed'] += 1
                streak['fetch'] += 1
                return f'{FAIL_FAST} fetches in a row failed (check Storage)' if streak['fetch'] >= FAIL_FAST else ''
            streak['fetch'] = 0
            vs = doc.verification_status
            text = texts.get(pk) or ''
            with usage.usage_context(source=USAGE_SOURCE):     # a PLATFORM meter row
                new, markers = _new_value(check, doc, image, model, text)
            stored = stored_value(check, doc.doc_type, doc.vision_fields)
            if check == 'results_slip':
                _add(tally, check, 'rescored_from_text' if text.strip() else 'not_gated_no_text', pk)
            tally_the_read(tally, check, doc, stored, new, markers, fakes)
            read = True
        except Exception as e:    # one document never stops the run; the type only, never the message
            logger.warning('eval_genuineness_38: doc %s failed (%s)', pk, type(e).__name__)
            t['error'] += 1
        finally:
            t['calls'] += trace['calls'] - before
        outcome = trace['outcome']
        if outcome:
            _add(tally, check, outcome, pk)
        if outcome == 'malformed_after_retry':
            if pk in fakes:
                _add(tally, check, 'malformed_on_known_fake', pk)
            if vs == 'rejected':
                _add(tally, check, 'malformed_on_rejected', pk)
        if outcome and check == 'results_slip':      # a slip fake scored from text alone: its 3.8 read failed
            tally[check]['fakes_answered'].discard(pk)
        if read and outcome != 'service_error':      # 3.8 gave this document its own answer (or a slip, no text)
            tally[check]['settled'].add(pk)
        streak['service'] = streak['service'] + 1 if outcome == 'service_error' else 0
        if streak['service'] >= FAIL_FAST:
            return f'{FAIL_FAST} AI service errors in a row (check the key, quota or model name)'
        return ''

    def _report(self, tally, trace, done, stopped, missed, testable_fakes):
        out = self.stdout.write
        out(f'done: {done} documents, {trace["calls"]} calls, charged up to US${trace["usd"].quantize(Decimal("0.0001"))}'
            f' (assumed: US${USD_PER_CALL_38} a call at least, reported tokens at the assumed 3.8 prices when higher)')
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
        for check, row in tally.items():
            self._direction(check, row['changes'])
        lines = [self._gate_line(c, r['n'], r['ids']) for c, r in tally.items()]
        untested = []
        if not any(r['accepted_tested'] for r in tally.values()):
            untested.append('reviewer gate NOT TESTED (0 accepted rows)')
        if not testable_fakes:
            untested.append('known-fake gate NOT TESTED (0 testable fakes)')
        out('GATES (each must be 0): ' + '; '.join(lines)
            + f'; known_fake_no_check_reads {len(missed)}' + _ids_in(missed)
            + ''.join(f'; {u}' for u in untested))
        failed = [f'{c} {k}' for c, r in tally.items() for k in GATE_KEYS[c] if r['n'][k]]
        failed += ['known_fake_no_check_reads'] if missed else []
        failed += [f'{c} answered 0' for c, r in tally.items() if not r['n']['answered']]
        failed += [f'run stopped: {stopped}'] if stopped else []
        failed += ['nothing was read (0 documents)'] if not done else []
        if failed:
            out('GATES NOT MET: ' + ', '.join(failed))
        elif untested:
            out('GATES MET (untested: ' + ', '.join(u.split(' NOT TESTED')[0] for u in untested) + ')')
        else:
            out('GATES MET')

    def _direction(self, check, changes):
        """Which way each disagreement went: counts per `stored -> new`, then one line per id (statuses, ids only)."""
        if not changes:
            return
        out = self.stdout.write
        counts = Counter((s, n) for _pk, s, n in changes)
        out(f'[{check}] transitions: ' + ', '.join(f'{s} -> {n}: {c}' for (s, n), c in sorted(counts.items())))
        for pk, s, n in changes[:CHANGES_SHOWN]:
            out(f'[{check}] {pk}: {s} -> {n}')

    @staticmethod
    def _gate_line(check, n, ids):
        line = ', '.join(f'{k} {n[k]}' + (_ids_in(ids[k]) if k in GATE_IDS else '') for k in GATE_KEYS[check])
        return (f'{check} {line} (also: malformed_on_known_fake {n["malformed_on_known_fake"]}, '
                f'malformed_on_rejected {n["malformed_on_rejected"]})')


def _ids_in(ids):
    """' [id,id,...]' for a non-empty id list on the GATES line (at most IDS_SHOWN), else ''."""
    return f' [{",".join(map(str, list(ids)[:IDS_SHOWN]))}]' if ids else ''
