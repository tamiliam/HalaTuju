"""Document-recognition evaluation harness — the "golden master" for the Vision +
matcher + verdict pipeline (the document equivalent of the SPM/STPM golden master).

WHY: today the only way to know whether the pipeline reads a document correctly,
distinguishes a right document from a wrong one, and reaches the right verdict is to
upload it and eyeball the result by hand — slow and draining. This harness captures
that judgement ONCE (a small labelled set) and re-checks the whole pipeline in seconds.

THE TWO-LAYER SPLIT (keeps it cheap + deterministic):
  • Layer A — the Gemini READ (run_vision_for_document / field extraction). Costs money
    and wobbles run-to-run. We run it only on `--rerun-vision` and CACHE the result per
    document to `snapshots/`.
  • Layer B — the matchers + verdict (`resolution.doc_match_verdict`, the per-type
    `*_check` functions). Deterministic and FREE. Day-to-day eval replays Layer B against
    the cached snapshot, so re-checking is instant, free, and identical every time.

It does NOT re-detect anything: it drives the SAME `doc_match_verdict` the cockpit shows.

PII: the document files (`fixtures/`), their cached reads (`snapshots/`) and the
profile context (`context.json`) are gitignored / local-only. Only `labels.json` —
which holds PII-FREE assertions ("type should be offer_letter", "verdict should be
mismatch") — is committed.

Nothing is persisted to the DB: every fixture is built inside a transaction that is
rolled back. Run locally only (it is not wired to any endpoint or cron).

Usage:
  python manage.py eval_doc_recognition                 # Layer B replay (free) — the scorecard
  python manage.py eval_doc_recognition --rerun-vision   # Layer A — (re)capture Gemini reads (costs $)
  python manage.py eval_doc_recognition --json           # machine-readable scorecard
  python manage.py eval_doc_recognition --eval-dir PATH  # point at a different eval set (used by tests)
  python manage.py eval_doc_recognition --auto-ok        # the whole corpus: content AND stored genuineness
"""
import json
import os

from django.core.management.base import BaseCommand
from django.utils import timezone

# Fields restored onto / captured from an ApplicantDocument to replay Layer B.
_SNAPSHOT_FIELDS = ['vision_nric', 'vision_name', 'vision_address', 'vision_error', 'vision_fields']

# A single Layer-A extractor per doc_type, mirroring views.DocumentListCreateView.post.
# Returns the set of doc_types we know how to (re)read; anything else has no Gemini step.
_VISION_TYPES = {'ic', 'parent_ic', 'results_slip', 'salary_slip', 'epf', 'str',
                 'offer_letter', 'birth_certificate', 'guardianship_letter',
                 'water_bill', 'electricity_bill', 'statement_of_intent'}


class Command(BaseCommand):
    help = 'Evaluate the document-recognition pipeline against a labelled golden set.'

    def add_arguments(self, parser):
        parser.add_argument('--eval-dir', default=None,
                            help='Eval set directory (default: apps/scholarship/eval).')
        parser.add_argument('--rerun-vision', action='store_true',
                            help='Re-run the (billable) Gemini read for each fixture and cache it.')
        parser.add_argument('--auto-ok', action='store_true',
                            help='Score every surviving fixture as expected "ok" (genuine corpus), '
                                 'grouped per application. Uses context.json + snapshots, plus the '
                                 'corpus_relabels / corpus_known notes in labels.json.')
        parser.add_argument('--labels', default=None,
                            help='labels.json to read (default: the one in --eval-dir). Lets a '
                                 'worktree score the main checkout corpus with its own labels.')
        parser.add_argument('--json', action='store_true', help='Emit a machine-readable scorecard.')

    # ── paths ────────────────────────────────────────────────────────────────
    def _dirs(self, eval_dir):
        base = eval_dir or os.path.join(os.path.dirname(__file__), '..', '..', 'eval')
        base = os.path.abspath(base)
        return {
            'base': base,
            'labels': os.path.join(base, 'labels.json'),
            'context': os.path.join(base, 'context.json'),
            'applicants': os.path.join(base, 'applicants.json'),
            'snapshots': os.path.join(base, 'snapshots'),
            'fixtures': os.path.join(base, 'fixtures'),
            'counter': os.path.join(base, 'counter_examples'),
        }

    def handle(self, *args, **opts):
        d = self._dirs(opts['eval_dir'])
        if opts.get('labels'):
            d['labels'] = os.path.abspath(opts['labels'])
        if opts.get('auto_ok'):
            self._auto_ok(d, opts['json'])
            return
        if not os.path.exists(d['labels']):
            self.stderr.write(f"No labels.json at {d['labels']} — nothing to evaluate.")
            return
        with open(d['labels'], encoding='utf-8') as f:
            labels = (json.load(f) or {}).get('docs', {})
        context = {}
        if os.path.exists(d['context']):
            with open(d['context'], encoding='utf-8') as f:
                context = json.load(f) or {}

        if opts['rerun_vision']:
            self._rerun_vision(labels, context, d)
            return

        results = [self._score_one(key, label, context.get(key, {}), d) for key, label in labels.items()]
        self._report(results, opts['json'])

    # ── Layer B replay + scoring (free, deterministic) ─────────────────────────
    def _score_one(self, key, label, ctx, d):
        from apps.scholarship._test_fixtures import build_doc_fixture, rolled_back
        snap_path = os.path.join(d['snapshots'], f'{key}.json')
        if not os.path.exists(snap_path):
            return {'key': key, 'status': 'no_snapshot',
                    'note': 'run --rerun-vision to capture the Gemini read first'}
        with open(snap_path, encoding='utf-8') as f:
            snap = json.load(f)

        from apps.scholarship.resolution import doc_match_verdict
        actual = None
        expected = label.get('expect_verdict')
        outcome, detail = 'error', ''
        try:
            captured = {}
            with rolled_back():   # build + score, then discard the fixtures
                doc = build_doc_fixture(label['doc_type'], snap, ctx)
                captured['verdict'] = doc_match_verdict(doc)
            actual = captured.get('verdict')
            if expected is None:
                outcome, detail = 'unlabelled', 'no expect_verdict in label'
            else:
                outcome = 'pass' if actual == expected else 'fail'
                detail = '' if outcome == 'pass' else f'expected {expected!r}, got {actual!r}'
        except Exception as e:  # noqa: BLE001 — a broken fixture must not abort the whole run
            detail = f'{type(e).__name__}: {e}'
        return {'key': key, 'doc_type': label['doc_type'], 'status': outcome,
                'expected': expected, 'actual': actual, 'note': label.get('note', ''), 'detail': detail}

    # ── Corpus mode: score fixtures (expect 'ok') + counter_examples (expect FLAGGED) ──
    def _corpus_items(self, d, relabels):
        """Each corpus file -> ``key: (doc_type, expect)``. ONLY the immediate ``<doc_type>/`` folders
        of fixtures/ and counter_examples/ are scored, and only a real ``ApplicantDocument`` type
        (TD-121, A2.8b): the walk used to recurse into the nested corpora (``offer_letters_<date>/``,
        ``results_split/``), so their snapshot files were scored as a doc type called 'snapshots' and
        a same-stem nested copy overwrote the real letter. A folder that is not a doc type is reported,
        not scored. ``relabels`` (labels.json ``corpus_relabels``) moves a key's expectation."""
        from apps.scholarship.models import ApplicantDocument
        doc_types = {v for v, _ in ApplicantDocument.DOC_TYPES}
        survivors, skipped = {}, set()
        for base, expect in ((d['fixtures'], 'ok'), (d['counter'], 'flag')):
            if not os.path.isdir(base):
                continue
            for dt in sorted(os.listdir(base)):
                folder = os.path.join(base, dt)
                if not os.path.isdir(folder):
                    continue
                if dt not in doc_types:
                    skipped.add(dt)
                    continue
                for fn in sorted(os.listdir(folder)):
                    if fn != '.gitkeep' and os.path.isfile(os.path.join(folder, fn)):
                        key = os.path.splitext(fn)[0]
                        survivors[key] = (dt, (relabels.get(key) or {}).get('expect', expect))
        return survivors, sorted(skipped)

    @staticmethod
    def _offer_rulings(d):
        """The owner's offer-letter rulings, read from their one home (``offer_genuineness_expect.json``
        beside labels.json): a letter ruled ``suspect`` / ``not_offer_letter`` is NOT a genuine offer, so
        it is expected FLAGGED wherever it sits in the corpus (A2.8b). Only that direction moves: a
        letter ruled genuine can still carry a content gap, so its folder stands."""
        path = os.path.join(os.path.dirname(d['labels']), 'offer_genuineness_expect.json')
        if not os.path.exists(path):
            return {}
        expect = (json.load(open(path, encoding='utf-8')) or {}).get('expect') or {}
        return {k: {'expect': 'flag', 'why': f'owner offer ruling: {v}'}
                for k, v in expect.items() if v in ('suspect', 'not_offer_letter')}

    @staticmethod
    def _genuineness(snap, doc_type):
        """TD-121: the STORED genuineness of a cached read, folded to the canonical enum -
        'genuine' / 'suspect' / 'not_<type>' / '' (never scored). The value the verdict cap and the
        officer flag read (``bands``). Nothing is re-scored, so no read and no model call is made."""
        from apps.scholarship.genuineness.bands import canonical_status, stored_status
        return canonical_status(stored_status((snap or {}).get('vision_fields')), doc_type)

    def _auto_ok(self, d, as_json):
        from collections import defaultdict
        from apps.scholarship._test_fixtures import build_application_with_docs, rolled_back
        from apps.scholarship.genuineness.bands import needs_attention
        from apps.scholarship.resolution import doc_match_verdict
        if not os.path.exists(d['context']):
            self.stderr.write('No context.json — run eval/fetch_corpus.py first.')
            return
        context = json.load(open(d['context'], encoding='utf-8'))
        applicants = json.load(open(d['applicants'], encoding='utf-8')) if os.path.exists(d['applicants']) else {}
        meta = json.load(open(d['labels'], encoding='utf-8')) if os.path.exists(d['labels']) else {}
        relabels = {**self._offer_rulings(d), **(meta.get('corpus_relabels') or {})}
        known = meta.get('corpus_known') or {}

        survivors, skipped = self._corpus_items(d, relabels)
        groups, missing = defaultdict(list), []
        for key, (dt, expect) in survivors.items():
            ctx = context.get(key)
            (groups[ctx.get('_app_id')].append((key, dt, expect, ctx)) if ctx else missing.append(key))

        results = []
        for app_id, items in groups.items():
            app_ctx = items[0][3]
            rec = applicants.get(str(app_id)) or applicants.get(app_id) or {}
            docs = []
            for key, dt, expect, ctx in items:
                sp = os.path.join(d['snapshots'], f'{key}.json')
                snap = json.load(open(sp, encoding='utf-8')) if os.path.exists(sp) else {}
                docs.append({'key': key, 'doc_type': dt, 'household_member': ctx.get('household_member', ''), 'snapshot': snap})
            snaps = {m['key']: m['snapshot'] for m in docs}
            captured = {}
            try:
                with rolled_back():
                    built = build_application_with_docs(app_ctx, docs,
                                                        profile_fields=rec.get('profile'), app_fields=rec.get('application'))
                    for obj, m in zip(built, docs):
                        captured[m['key']] = doc_match_verdict(obj)
            except Exception as e:  # noqa: BLE001 — one failing case is recorded as ERROR and the run continues
                for m in docs:
                    results.append({'key': m['key'], 'doc_type': m['doc_type'], 'expect': '?', 'verdict': 'ERROR',
                                    'detail': f'{type(e).__name__}: {e}'})
                continue
            for key, dt, expect, ctx in items:
                v = captured.get(key)
                g = self._genuineness(snaps.get(key), dt)
                by = [n for n, hit in (('content', v not in ('ok', None)), ('genuineness', needs_attention(g, dt))) if hit]
                # A counter-example is caught when EITHER layer flags it: production caps a suspect /
                # not_<type> document and flags it to the officer even when its content matches (TD-121).
                ok = (v == 'ok') if expect == 'ok' else bool(by)
                results.append({'key': key, 'doc_type': dt, 'expect': expect, 'verdict': v,
                                'genuineness': g or 'unscored', 'correct': ok,
                                'caught_by': '+'.join(by) if expect == 'flag' else '',
                                'known': (known.get(key) or {}).get('why', ''), 'relabelled': key in relabels,
                                'prod_status': ctx.get('_prod_status')})
        self._auto_ok_report(results, missing, skipped, as_json)

    @staticmethod
    def _g_bucket(g):
        return 'unscored' if g in ('', 'unscored', None) else ('genuine' if g == 'genuine' else 'flagged')

    def _auto_ok_report(self, results, missing, skipped, as_json):
        from collections import Counter
        gen = [r for r in results if r['expect'] == 'ok']
        ctr = [r for r in results if r['expect'] == 'flag']
        false_pos = [r for r in gen if not r['correct']]      # genuine doc wrongly flagged
        false_neg = [r for r in ctr if not r['correct']]      # wrong doc wrongly passed
        explained = sum(1 for r in false_pos if r.get('known'))
        g_gen = Counter(self._g_bucket(r.get('genuineness')) for r in gen)
        g_ctr = Counter(self._g_bucket(r.get('genuineness')) for r in ctr)
        genuineness = {
            'genuine_docs': {k: g_gen[k] for k in ('genuine', 'flagged', 'unscored')},
            'counter': {k: g_ctr[k] for k in ('flagged', 'genuine', 'unscored')},
            'counter_caught_by_genuineness_only': sum(1 for r in ctr if r.get('caught_by') == 'genuineness'),
        }
        if as_json:
            self.stdout.write(json.dumps({
                'genuine': len(gen), 'genuine_passed': len(gen) - len(false_pos), 'false_positives': len(false_pos),
                'false_positives_explained': explained,
                'counter': len(ctr), 'counter_caught': len(ctr) - len(false_neg), 'false_negatives': len(false_neg),
                'genuineness': genuineness, 'skipped_folders': skipped,
                'missing_context': missing, 'results': results}, indent=2, ensure_ascii=False))
            return
        self.stdout.write(f"\n=== Genuine documents (expected to PASS): {len(gen)} ===")
        self.stdout.write(self.style.SUCCESS(f"  {len(gen) - len(false_pos)} passed")
                          + f"  ·  {len(false_pos)} FALSE POSITIVES (genuine doc flagged)"
                          + f"  ·  {explained} explained (labels.json corpus_known)")
        for (dt, v), n in sorted(Counter((r['doc_type'], r['verdict']) for r in false_pos).items()):
            self.stdout.write(f"     ! {dt:20s} got {str(v):10s} ×{n}")
        if ctr:
            self.stdout.write(f"\n=== Counter-examples (expected to be FLAGGED): {len(ctr)} ===")
            self.stdout.write(self.style.SUCCESS(f"  {len(ctr) - len(false_neg)} caught")
                              + f"  ·  {len(false_neg)} FALSE NEGATIVES (wrong doc accepted)")
            for (dt,), n in sorted(Counter((r['doc_type'],) for r in false_neg).items()):
                self.stdout.write(f"     !! {dt:20s} wrongly passed ×{n}")
        else:
            self.stdout.write("\n  (no counter_examples/ yet — add wrong docs there to test false-negatives)")
        gd, gc = genuineness['genuine_docs'], genuineness['counter']
        self.stdout.write("\n=== Genuineness (the stored score, TD-121) ===")
        self.stdout.write(f"  genuine docs: {gd['genuine']} genuine · {gd['flagged']} flagged · {gd['unscored']} unscored")
        self.stdout.write(f"  counter-examples: {gc['flagged']} flagged · {gc['genuine']} genuine · {gc['unscored']} "
                          f"unscored ({genuineness['counter_caught_by_genuineness_only']} caught by genuineness alone)")
        if skipped:
            self.stdout.write(self.style.WARNING(f"\n  Not scored (not a document type): {', '.join(skipped)}"))
        if missing:
            self.stdout.write(self.style.WARNING(f"\n  {len(missing)} fixtures had no context entry (skipped)."))

    # ── Layer A re-capture (billable Gemini) ────────────────────────────────────
    def _rerun_vision(self, labels, context, d):
        from unittest.mock import patch
        from apps.scholarship._test_fixtures import build_doc_fixture, rolled_back
        from apps.scholarship import vision as _vision
        os.makedirs(d['snapshots'], exist_ok=True)
        done, skipped = 0, 0
        for key, label in labels.items():
            dt = label['doc_type']
            fixture_file = self._find_fixture(d['fixtures'], key)
            if dt not in _VISION_TYPES or not fixture_file:
                skipped += 1
                self.stdout.write(f'  skip {key} ({dt}) — no fixture file or no Gemini step')
                continue
            with open(fixture_file, 'rb') as fh:
                file_bytes = fh.read()
            captured = {}
            with rolled_back():
                doc = build_doc_fixture(dt, snap=None, ctx=context.get(key, {}))
                # Feed the LOCAL file to the real extractor instead of Supabase storage.
                with patch.object(_vision, '_fetch_image_bytes', return_value=file_bytes):
                    self._run_extractor(doc, _vision)
                captured = {f: getattr(doc, f) for f in _SNAPSHOT_FIELDS}
                captured['vision_run_at'] = (doc.vision_run_at or timezone.now()).isoformat()
            with open(os.path.join(d['snapshots'], f'{key}.json'), 'w', encoding='utf-8') as out:
                json.dump(captured, out, indent=2, ensure_ascii=False, default=str)
            done += 1
            self.stdout.write(self.style.SUCCESS(f'  captured {key} ({dt})'))
        self.stdout.write(f'\nLayer-A capture: {done} captured, {skipped} skipped.')

    def _run_extractor(self, doc, _vision):
        dt = doc.doc_type
        if dt in ('ic', 'parent_ic'):
            _vision.run_vision_for_document(doc)
        elif dt == 'statement_of_intent':
            _vision.read_text_document(doc)
        else:   # supporting docs: OCR → name/address match → Gemini field extraction
            ocr = _vision.ocr_document(doc)
            _vision.run_vision_match_for_document(doc, names=[], postcode='', city='', street='',
                                                  check_address=dt in ('water_bill', 'electricity_bill'), ocr=ocr)
            if dt in _vision.GEMINI_EXTRACT_DOC_TYPES:
                _vision.run_field_extraction_for_document(doc, ocr=ocr, force=True)

    def _find_fixture(self, fixtures_dir, key):
        if not os.path.isdir(fixtures_dir):
            return None
        for name in os.listdir(fixtures_dir):
            if os.path.splitext(name)[0] == key:
                return os.path.join(fixtures_dir, name)
        return None

    # ── reporting ───────────────────────────────────────────────────────────────
    def _report(self, results, as_json):
        passed = [r for r in results if r['status'] == 'pass']
        failed = [r for r in results if r['status'] == 'fail']
        errored = [r for r in results if r['status'] == 'error']
        other = [r for r in results if r['status'] in ('no_snapshot', 'unlabelled')]
        if as_json:
            self.stdout.write(json.dumps({
                'total': len(results), 'passed': len(passed), 'failed': len(failed),
                'errored': len(errored), 'skipped': len(other), 'results': results,
            }, indent=2, ensure_ascii=False))
            return
        self.stdout.write('')
        for r in results:
            mark = {'pass': self.style.SUCCESS('PASS'), 'fail': self.style.ERROR('FAIL'),
                    'error': self.style.ERROR('ERR '), 'no_snapshot': self.style.WARNING('SKIP'),
                    'unlabelled': self.style.WARNING('????')}.get(r['status'], '????')
            line = f"  [{mark}] {r['key']}"
            if r.get('detail'):
                line += f" — {r['detail']}"
            elif r.get('note'):
                line += f" — {r['note']}"
            self.stdout.write(line)
        n = len(results)
        summary = f'\n{len(passed)}/{n} correct'
        if failed:
            summary += f' · {len(failed)} regression(s)'
        if errored:
            summary += f' · {len(errored)} error(s)'
        if other:
            summary += f' · {len(other)} skipped (no snapshot — run --rerun-vision)'
        self.stdout.write(self.style.SUCCESS(summary) if not (failed or errored) else self.style.ERROR(summary))
