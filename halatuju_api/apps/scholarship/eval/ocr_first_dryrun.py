"""OCR-first dry run: how often do FIXED RULES alone already agree with the truth? (S0, 2026-11-18)

Roadmap: ``docs/plans/ocr-first-roadmap.md`` (section 2, Phase 0). A HAND-RUN measurement, never a
test, and FREE: it runs ONLY on cached OCR text in the local, gitignored corpus (``README.md``; real
PII). No network, no model call, no OCR call, nothing written. It prints COUNTS only: no name, no
IC, no value, no key. Committed tests: ``tests/test_ocr_first_dryrun.py`` (synthetic twins).

WHAT IT RUNS (existing code, never a copy of the rules)
  * offer letters: ``offer_exact.exact_read`` (the offer parsers + the IC guard, exactly as
    production derives the inputs), then ``offer_course_match.match_offer_course``;
  * EPF / STR / electricity / water / birth certificate: ``doc_parse.parse_by_labels`` (and
    ``doc_parse_epf`` through it).
  A lane with no parser yet (a university with no offer rules; salary slips; SPM results slips, whose
  parser reads word boxes, not text) is reported as "no rules yet", never as a failure.

WHAT IT COMPARES WITH (two answers, never mixed)
  1. the hand-checked answer (``<key>.offer_expect.json``): the TRUTH. Scored with
     ``offer_read_check``'s scorer: exact / blank_correct / missing / wrong / extra per core field.
  2. the stored AI read: AGREEMENT ONLY (the AI is not the truth): agree / differ / rules_blank /
     ai_blank / both_blank per field.
  Only the offer corpus has hand-checked answers. The other document types are agreement-only, so
  they can never pass Gate 1 (the lane table says "no truth set").

THE OUTPUT
  * per lane (offers: per university or family; other types: per document type): documents, how many
    the rules answered (coverage), agreement %, the per-field outcome buckets, the course match
    (unique / none / refused, and how many differ from the one the answer names), the agreement with
    the stored AI, and the Gate 1 verdict with its reasons (``scholarship.ocr_first_gate``);
  * a LANE TABLE: pass / fail / no rules yet, and why.
  Gate 1 is judged on the HELD-OUT split (``offer_split.json``), the default. Rules are tuned on dev.

THE COURSE MATCH needs the catalogue (Django ORM: ``Institution`` / ``Course``). Without it the
course column reads "not run". ``--catalogue-db <sqlite file>`` points Django at a local copy of the
catalogue; nothing is written to it. Pre-U letters (STPM, matriculation) have no catalogue course
("n/a").

THE ROW COUNTS: a lane's ``docs`` is every held-out document in it that has a hand-checked answer
and is a real offer; the agreement is over the core-field cells of the documents the rules ANSWERED
(a locked read). A blank, or a document the rules leave to the AI, is acceptable; a wrong value is
not. An ``extra`` value on a guarded field counts as a wrong one (the letter prints nothing there).

Usage:  python -I apps/scholarship/eval/ocr_first_dryrun.py [--split heldout|dev|all]
            [--eval-dir DIR] [--snap-dir DIR] [--catalogue-db FILE] [--json]
Run from a checkout that holds the corpus, or pass ``--eval-dir`` (the offer corpus folder) and
``--snap-dir`` (the other types' ``snapshots/`` folder).
"""
import argparse
import glob
import json
import logging
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))      # halatuju_api/
if _API_ROOT not in sys.path:                  # run as a script with -I: reach the app package
    sys.path.insert(0, _API_ROOT)
from apps.scholarship import doc_parse
from apps.scholarship.eval import offer_read_check as orc
from apps.scholarship.eval import offer_replay as rp
from apps.scholarship.ocr_first_gate import GUARDED_FIELDS, lane_gate
from apps.scholarship.offer_exact import exact_read

DEFAULT_SNAP_DIR = os.path.join(HERE, 'snapshots')
REAL_OFFER = ('yes', 'conditional')
#: Document types read by ``doc_parse.parse_by_labels`` (agreement only: no hand-checked answers).
LABEL_TYPES = ('str', 'electricity_bill', 'water_bill', 'birth_certificate', 'epf')
#: Types with cached text but no text parser: reported as "no rules yet".
NO_RULES_TYPES = {'salary_slip': 'no rules yet (signature model, not a text parser)',
                  'results_slip': 'no rules yet (the slip parser reads word boxes; none cached)'}
AGREEMENT = ('agree', 'differ', 'rules_blank', 'ai_blank', 'both_blank')
COURSE = ('unique', 'none', 'refused', 'n/a', 'not_run')


# ── The course match (needs the catalogue) ───────────────────────────────────────────────────
def setup_django(catalogue_db=None):
    """Configure Django (the parsers import models), and point it at ``catalogue_db`` (a sqlite
    file) when one is named. Returns ``match_offer_course``, or None when no catalogue is named
    (the course column then reads "not run"). Nothing is ever written to the catalogue."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'halatuju.settings.development')
    import django
    from django.conf import settings
    if catalogue_db:                    # BEFORE setup: the app registry reads the catalogue at start
        settings.DATABASES['default']['NAME'] = os.path.abspath(catalogue_db)
    django.setup()
    if not catalogue_db:
        return None
    from apps.scholarship.offer_course_match import match_offer_course
    return match_offer_course


def _course_id(match):
    return (match or {}).get('course_id') or ''


def course_verdict(matcher, fields, answer):
    """``(rules side, wrong)`` for one locked letter: the rules side is one of COURSE; ``wrong`` is
    True when the rules' read sets a course the answer's own text does not name (the answer's
    programme and institution through the same matcher is the truth side)."""
    from apps.scholarship.catalogue_levels import private_arm_letter
    from apps.scholarship.offer_course_match import letter_institution
    from apps.scholarship.offer_pathway import detect_pathway_type, is_pre_u
    programme = fields.get('programme') or ''
    inst = letter_institution(fields.get('institution') or '', fields.get('campus') or '')
    if is_pre_u(detect_pathway_type(programme or fields.get('stream') or '', inst)):
        return 'n/a', False
    if matcher is None:
        return 'not_run', False
    if private_arm_letter(programme, inst):
        return 'refused', False
    got = _course_id(matcher(programme, inst, fields.get('issuer') or ''))
    if not got:
        return 'none', False
    want = _course_id(matcher(answer.get('programme') or '',
                              letter_institution(answer.get('institution_as_printed') or '',
                                                 answer.get('institution_campus') or ''),
                              answer.get('issuer') or ''))
    return 'unique', got != want


# ── Offer letters ────────────────────────────────────────────────────────────────────────────
def offer_lane(family, answer):
    """The lane of an offer letter: the family for the fixed-format and the minor ones, the
    university (the answer's institution name) for UiTM and the other universities."""
    if family in ('uitm', 'other_university'):
        name = orc.tidy_institution((answer or {}).get('institution_as_printed') or '')
        return name.lower() if name else family
    return family


def _ai_agreement(fields, stored, family):
    """``{field: AGREEMENT bucket}`` of the rules' read against the stored AI read."""
    pairs = {
        'name': ('candidate_name', 'candidate_name', orc.tidy_text),
        'nric': ('candidate_nric', 'candidate_nric', orc.tidy_nric),
        'institution': ('institution', 'institution', orc.tidy_institution),
        'programme': (('stream', 'stream') if family in ('stpm', 'matriculation')
                      else ('programme', 'programme')) + (orc.tidy_text,),
        'intake': ('intake', 'intake', orc.tidy_intake),
        'reporting_date': ('reporting_date', 'reporting_date', orc.tidy_date),
    }
    out = {}
    for field, (rule_key, ai_key, tidy) in pairs.items():
        a, b = tidy(fields.get(rule_key)), tidy(stored.get(ai_key))
        out[field] = ('both_blank' if not a and not b else 'rules_blank' if not a else
                      'ai_blank' if not b else 'agree' if a == b else 'differ')
    return out


def offer_record(eval_dir, key, context, heldout, matcher):
    """One letter's counts-only record (no value ever kept)."""
    snap = os.path.join(eval_dir, 'snapshots')
    stored_vf = orc.stored_vision_fields(eval_dir, key)
    answer, problems = orc._read_answer(eval_dir, key)
    answer = answer if isinstance(answer, dict) and not problems else None
    family = orc.offer_family(stored_vf, answer)
    text, route = rp.production_text(snap, key)
    ex = exact_read(text, from_text_layer=route == 'text_layer', page1_layer=rp.page1_of(eval_dir, key, route),
                    profile_nric=(context.get(key) or {}).get('profile_nric') or '')
    fields = ex['fields'] if ex else None
    rec = {'lane': offer_lane(family, answer), 'family': family, 'split': 'heldout' if key in heldout else 'dev',
           'has_truth': answer is not None, 'real_offer': bool(answer) and answer.get('is_offer_letter') in REAL_OFFER,
           'locked': fields is not None, 'rules_exist': family in orc.KNOWN_FORMAT_FAMILIES,
           'outcomes': None, 'ai': None, 'course': None, 'course_wrong': False}
    if fields is None:
        return rec
    stored, capture = orc.stored_read(eval_dir, key)
    if stored and capture == 'ai':
        rec['ai'] = _ai_agreement(fields, stored, family)
    if answer is not None:
        rec['outcomes'] = orc.score_letter(answer, fields, family)
        rec['course'], rec['course_wrong'] = course_verdict(matcher, fields, answer)
    return rec


def offer_records(eval_dir, split, split_file, matcher):
    context = orc.read_json_file(os.path.join(eval_dir, 'context.json')) or {}
    heldout = orc.load_heldout(split_file)
    recs = [offer_record(eval_dir, key, context, heldout, matcher) for key in orc.offer_keys(eval_dir)]
    return [r for r in recs if split == 'all' or r['split'] == split]


def _new_lane(name, rules_exist):
    return {'lane': name, 'rules_exist': rules_exist, 'docs': 0, 'locked': 0, 'control_locked': 0,
            'core_right': 0, 'core_total': 0, 'wrong': Counter(), 'fields': {f: Counter() for f in orc.CORE},
            'course': Counter(), 'course_wrong': 0, 'ai': {f: Counter() for f in orc.CORE}}


def _add_scored(lane, rec):
    """Fold one locked, answered real offer into the lane's core cells and buckets."""
    lane['locked'] += 1
    for field in orc.CORE:
        outcome = rec['outcomes'][field]
        lane['fields'][field][outcome] += 1
        lane['core_total'] += 1
        lane['core_right'] += outcome in orc.RIGHT
        if field in GUARDED_FIELDS and outcome in ('wrong', 'extra'):
            lane['wrong'][field] += 1
    lane['course'][rec['course']] += 1
    lane['course_wrong'] += rec['course_wrong']


def aggregate_offers(records):
    """``{lane: totals}`` over the letters of the split (a control letter the rules lock counts apart)."""
    lanes = {}
    for rec in records:
        lane = lanes.setdefault(rec['lane'], _new_lane(rec['lane'], rec['rules_exist']))
        if rec['has_truth'] and not rec['real_offer']:
            lane['control_locked'] += rec['locked']
            continue
        if rec['real_offer']:
            lane['docs'] += 1
            if rec['locked']:
                _add_scored(lane, rec)
        if rec['ai']:
            for field, bucket in rec['ai'].items():
                lane['ai'][field][bucket] += 1
    return lanes


def gate_lane(lane, heldout=True):
    """``(status, why)``: pass / fail / no rules yet, with the reasons (Gate 1). Only the held-out
    split may give a verdict: any other split reads "informational (not held-out)", never pass."""
    if not lane['rules_exist']:
        return 'no rules yet', 'no deterministic parser for this issuer'
    measured = lane['course']['not_run'] == 0
    gate = lane_gate(locked=lane['locked'], core_right=lane['core_right'], core_total=lane['core_total'],
                     wrong=lane['wrong'], course_match_wrong=lane['course_wrong'] if measured else None)
    reasons = list(gate.reasons)
    if lane['control_locked']:
        reasons.append(f"{lane['control_locked']} non-offer letter(s) locked (report only)")
    if not heldout:
        return 'informational (not held-out)', ('would pass Gate 1' if gate.passed else '; '.join(reasons))
    return ('pass' if gate.passed else 'fail'), '; '.join(reasons)


# ── The other document types (agreement with the stored AI only) ─────────────────────────────
def _norm(value):
    return orc.tidy_text(value if not isinstance(value, (dict, list)) else json.dumps(value, sort_keys=True))


def other_type_counts(snap_dir, doc_type):
    """Counts for one document type: cached texts, how many the parser answered, and per field the
    agreement of the parser with the stored AI read (``AGREEMENT`` buckets). No truth set exists."""
    out = {'doc_type': doc_type, 'texts': 0, 'answered': 0, 'ai_compared': 0, 'fields': {}}
    for txt in sorted(glob.glob(os.path.join(snap_dir, f'{doc_type}__*.ocr.txt'))):
        out['texts'] += 1
        with open(txt, encoding='utf-8') as fh:
            read = doc_parse.parse_by_labels(doc_type, fh.read())
        if read is None:
            continue
        out['answered'] += 1
        stored = orc.read_json_file(txt[:-len('.ocr.txt')] + '.json') or {}
        vf = stored.get('vision_fields') or {}
        ai = vf.get('fields') or {}
        if not ai or str(vf.get('capture')) == 'deterministic':
            continue
        out['ai_compared'] += 1
        for field, value in sorted(read.items()):
            if field.startswith('_'):
                continue
            a, b = _norm(value), _norm(ai.get(field))
            bucket = ('both_blank' if not a and not b else 'rules_blank' if not a else
                      'ai_blank' if not b else 'agree' if a == b else 'differ')
            out['fields'].setdefault(field, Counter())[bucket] += 1
    return out


def other_summary(snap_dir):
    rows = []
    for doc_type in LABEL_TYPES:
        c = other_type_counts(snap_dir, doc_type)
        agree = sum(f['agree'] for f in c['fields'].values())
        cells = sum(f['agree'] + f['differ'] + f['ai_blank'] + f['rules_blank'] for f in c['fields'].values())
        c.update({'agree_cells': agree, 'compared_cells': cells,
                  'status': 'no truth set' if c['texts'] else 'no cached text',
                  'why': 'agreement with the stored AI only; cannot pass Gate 1'})
        c['fields'] = {f: {b: n[b] for b in AGREEMENT} for f, n in sorted(c['fields'].items())}
        rows.append(c)
    for doc_type, why in NO_RULES_TYPES.items():
        texts = len(glob.glob(os.path.join(snap_dir, f'{doc_type}__*.ocr.txt')))
        rows.append({'doc_type': doc_type, 'texts': texts, 'answered': 0, 'ai_compared': 0, 'fields': {},
                     'agree_cells': 0, 'compared_cells': 0, 'status': 'no rules yet', 'why': why})
    return rows


# ── Report ───────────────────────────────────────────────────────────────────────────────────
def _pct(n, d):
    return f'{100.0 * n / d:.1f}%' if d else '-'


def dryrun_summary(eval_dir, snap_dir, split, split_file, matcher):
    lanes = aggregate_offers(offer_records(eval_dir, split, split_file, matcher))
    offers = []
    for name, lane in sorted(lanes.items(), key=lambda kv: (-kv[1]['docs'], kv[0])):
        if not lane['docs']:                    # only controls / unanswered letters: no lane to judge
            continue
        status, why = gate_lane(lane, heldout=split == 'heldout')
        offers.append({**lane, 'status': status, 'why': why,
                       'wrong': dict(lane['wrong']), 'course': {c: lane['course'][c] for c in COURSE},
                       'fields': {f: {o: lane['fields'][f][o] for o in orc.OUTCOMES} for f in orc.CORE},
                       'ai': {f: {b: lane['ai'][f][b] for b in AGREEMENT} for f in orc.CORE}})
    return {'split': split, 'offers': offers, 'other': other_summary(snap_dir) if snap_dir else []}


def _print_offer_lane(lane):
    print(f"\nlane offer_letter/{lane['lane']}: {lane['status']}  docs {lane['docs']}  rules answered "
          f"{lane['locked']} ({_pct(lane['locked'], lane['docs'])})  agreement "
          f"{_pct(lane['core_right'], lane['core_total'])}  course_wrong {lane['course_wrong']}")
    if not lane['locked']:
        return
    print(f"  {'field':<15}" + ''.join(f'{o:>14}' for o in orc.OUTCOMES) + f"{'vs AI agree':>13}")
    for field in orc.CORE:
        c, a = lane['fields'][field], lane['ai'][field]
        print(f'  {field:<15}' + ''.join(f'{c[o]:>14}' for o in orc.OUTCOMES)
              + f"{a['agree']}/{a['agree'] + a['differ']}".rjust(13))
    print('  course match: ' + '  '.join(f'{k} {v}' for k, v in lane['course'].items() if v))


def print_report(s):
    print(f"OCR-first dry run | split: {s['split']} | cached text only: no network, no model, no OCR")
    print('\n== LANE TABLE (Gate 1: >=20 docs, >=98% core agreement, zero wrong name/IC/institution/'
          'course, course match never wrong)')
    print(f"  {'lane':<44}{'status':<30}{'docs':>5}{'locked':>8}{'coverage':>10}{'agree':>8}  why")
    for lane in s['offers']:
        print(f"  {'offer_letter/' + lane['lane'][:30]:<44}{lane['status']:<30}{lane['docs']:>5}"
              f"{lane['locked']:>8}{_pct(lane['locked'], lane['docs']):>10}"
              f"{_pct(lane['core_right'], lane['core_total']):>8}  {lane['why']}")
    for row in s['other']:
        print(f"  {row['doc_type']:<44}{row['status']:<30}{row['texts']:>5}{row['answered']:>8}{'':>10}"
              f"{_pct(row['agree_cells'], row['compared_cells']):>8}  {row['why']}")
    print('\n== OFFER LANES (truth = hand-checked answers; "vs AI agree" = agreement only)')
    for lane in s['offers']:
        if lane['docs']:
            _print_offer_lane(lane)
    print('\n== OTHER DOCUMENT TYPES (agreement with the stored AI only; no hand-checked truth)')
    for row in s['other']:
        print(f"\n{row['doc_type']}: texts {row['texts']}  parser answered {row['answered']}  compared with "
              f"AI {row['ai_compared']}  agreement {_pct(row['agree_cells'], row['compared_cells'])}")
        for field, c in row['fields'].items():
            print(f'  {field:<18}' + '  '.join(f'{b} {c[b]}' for b in AGREEMENT))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--split', choices=('heldout', 'dev', 'all'), default='heldout')
    ap.add_argument('--eval-dir', default=orc.DEFAULT_EVAL_DIR, help='the offer corpus folder')
    ap.add_argument('--snap-dir', default=DEFAULT_SNAP_DIR, help="the other types' snapshots/ folder")
    ap.add_argument('--split-file', default=orc.SPLIT_PATH)
    ap.add_argument('--catalogue-db', default=None, help='a sqlite file holding the catalogue')
    ap.add_argument('--json', action='store_true', help='the summary as JSON (counts only)')
    args = ap.parse_args(argv)
    logging.getLogger('pypdf').setLevel(logging.ERROR)      # a damaged corpus PDF's warnings are noise here
    if not orc.offer_keys(args.eval_dir):
        print(f'No offer letters in {args.eval_dir} - this measurement needs the local corpus.')
        return 2
    matcher = setup_django(args.catalogue_db)
    snap_dir = args.snap_dir if os.path.isdir(args.snap_dir) else ''
    summary = dryrun_summary(args.eval_dir, snap_dir, args.split, args.split_file, matcher)
    if args.json:
        print(json.dumps(summary, indent=1, sort_keys=True))
    else:
        print_report(summary)
    return 0


if __name__ == '__main__':
    sys.exit(main())
