"""What the S4 offer reads WOULD do to live records — a READ-ONLY dry run (offer exact-read S4, 2026-11-02).

For each corpus letter with an S4 cache (`snapshots/<key>.fresh_s4.json`), the document `__d<id>` is
loaded from the database and the planners the live repairs use are run TWICE — once on the stored
`vision_fields.fields`, once on the S4 fields put in their place IN MEMORY (genuineness, verdict and
everything else stay the stored ones; S4 does not change genuineness):

  * realign   `services.offer_sync.plan_bumi_realign` (the `realign_bumi_offers` rule);
  * link      `services.offer_link.plan_offer_link` for an offer-sourced or empty pick, after the
              realignment as `link_offer_courses` orders them (`realign_first`);
  * fill      `services.offer_sync.institution_fill` (the sponsor-facing institution);
  * ticks     `pathway_engine.student_offer_check`: name, ic and the pathway / institution ticks.

Planners only — no writer (`realign_bumi_only_pick`, `link_offer_course`,
`sync_institution_from_catalogue`) is imported. Per key it prints ids and outcomes only: the doc and
application ids, each planner's outcome and course id before -> after, the campus as its catalogue
`institution_id` (or an 8-hex hash of the name when no id), and which ticks / name / IC verdicts
change. NEVER a name, an IC, a programme or an institution line. Then totals.

SAFETY — it reads the production database, so every run is ONE transaction that is never committed:
  * `transaction.atomic()`, whose FIRST statement is `SET TRANSACTION READ ONLY` (transaction-scoped:
    it dies with the transaction; never a session-level SET through a pooler — memory
    feedback_never_readonly_session_on_pooler), checked with `SHOW transaction_read_only`;
  * the transaction is ALWAYS marked for rollback (`transaction.set_rollback(True)`), error or not;
  * a `connection.execute_wrapper` refuses any statement that is not a read (INSERT / UPDATE / DELETE /
    CREATE / ALTER / DROP / TRUNCATE / GRANT / COPY / LOCK / any other SET) before it reaches the
    server — `WriteRefused`;
  * Storage (`vision._fetch_image_bytes`), Gemini (`vision._call_gemini_json`, `google.genai.Client`)
    and the usage meter raise if reached.
Refuses to start without DATABASE_URL, or on a database that is not PostgreSQL (`--allow-sqlite` is for
the tests' fake layer only).

S5 (`--suffix .s5_exact.json`, the caches `offer_s5_caches.py` writes): the Exact read is RE-DERIVED here
against the LIVE row - `offer_exact.exact_read` on the corpus's cached text, with the production profile IC
for the IC guard and the live `vision_fields` as the prior it merges over (what a live re-read would store).
A lock the guard refuses with the production IC would go to the AI reader: unknown here, so the live fields
stand, flagged `s5:ic_refused_live`. A fallback cache (a stored Exact read S5 no longer locks) carries the
corpus's AI read, or the stored read when the corpus has none - a GUESS, flagged `fallback:<which>`.

THE MONEY REACH (every suffix): per document, whether `parse_reporting_date(reporting_date)` and the intake
year the money path reads (`student_offer_check(...)['intake_year']`) change, stored vs new - changed /
unchanged only, never the value. `new_red:name` / `new_red:ic` count a Name / IC tick that becomes
`mismatch` (a wrong-person red) where it was not.

Usage (from halatuju_api/; the operator runs it, never an agent):
  python -I apps/scholarship/eval/offer_s4_dry_run.py --eval-dir <corpus> [--suffix .s5_exact.json]
      [--keys K1,K2] [--json]
Env: DATABASE_URL (the session pooler URL). Nothing else is read.
"""
import argparse
import contextlib
import copy
import glob
import hashlib
import json
import os
import re
import sys
from collections import Counter
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

#: The final S4 reader's caches (2.3.0, `offer_fresh_read.py --reader new`); `--suffix` for another.
S4_SUFFIX = '.fresh_s4d.json'
DEFAULT_EVAL_DIR = os.path.join(HERE, 'fixtures', 'offer_letters_2026-11-01')
TICKS = ('name', 'ic', 'pathway', 'institution_status', 'chosen_institution_status',
         'intake_year_status', 'reporting_official')
_DOC_ID = re.compile(r'__d(\d+)$')
#: Statements a read may send. Everything else is refused before it reaches the server.
_READ_SQL = re.compile(r'^\s*(SELECT|WITH|SHOW|SET\s+TRANSACTION\s+READ\s+ONLY|SAVEPOINT|RELEASE\s+SAVEPOINT'
                       r'|ROLLBACK\s+TO\s+SAVEPOINT|BEGIN|ROLLBACK|DECLARE|FETCH|CLOSE)\b', re.I)
_WITH_WRITE = re.compile(r'\b(INSERT|UPDATE|DELETE|MERGE)\b', re.I)


class WriteRefused(BaseException):
    """A statement that is not a read. A BaseException: no `except Exception` on the path swallows it."""


class Unreachable(BaseException):
    """Storage, Gemini or the meter was reached."""


def refuse_writes(execute, sql, params, many, context):
    s = str(sql or '')
    if not _READ_SQL.match(s) or (s.lstrip()[:4].upper() == 'WITH' and _WITH_WRITE.search(s)):
        raise WriteRefused(f'offer_s4_dry_run: refused a non-read statement: {s.split()[0] if s.split() else ""}')
    return execute(sql, params, many, context)


def begin_read_only(cursor):
    """The transaction's first statement: read only for THIS transaction, then proved."""
    cursor.execute('SET TRANSACTION READ ONLY')
    cursor.execute('SHOW transaction_read_only')
    row = cursor.fetchone()
    if not row or str(row[0]).lower() != 'on':
        raise WriteRefused('offer_s4_dry_run: the transaction did not become read only')


def _unreachable(what):
    def _raise(*a, **k):
        raise Unreachable(f'offer_s4_dry_run: {what} was reached')
    return _raise


@contextlib.contextmanager
def read_only_rollback(*, allow_sqlite=False):
    """ONE read-only transaction, always rolled back, with every write / Storage / AI door shut."""
    from django.db import connection, transaction
    from apps.scholarship import usage, vision
    if connection.vendor != 'postgresql' and not allow_sqlite:
        raise WriteRefused(f'offer_s4_dry_run: expects PostgreSQL, got {connection.vendor}')
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(vision, '_fetch_image_bytes', _unreachable('Storage')))
        stack.enter_context(mock.patch.object(vision, '_call_gemini_json', _unreachable('Gemini')))
        stack.enter_context(mock.patch('google.genai.Client', _unreachable('Gemini')))
        stack.enter_context(mock.patch.object(usage, 'record_usage', _unreachable('the usage meter')))
        stack.enter_context(connection.execute_wrapper(refuse_writes))
        with transaction.atomic():
            try:
                if connection.vendor == 'postgresql':
                    with connection.cursor() as cur:
                        begin_read_only(cur)
                yield
            finally:
                transaction.set_rollback(True)          # never committed, error or not


# ── One letter ───────────────────────────────────────────────────────────────────────────────
def doc_id_of(key):
    m = _DOC_ID.search(key)
    return int(m.group(1)) if m else None


def s4_keys(eval_dir, suffix=S4_SUFFIX):
    return sorted(os.path.basename(p)[:-len(suffix)]
                  for p in glob.glob(os.path.join(eval_dir, 'snapshots', '*' + suffix)))


def _cache(eval_dir, key, suffix=S4_SUFFIX):
    with open(os.path.join(eval_dir, 'snapshots', key + suffix), encoding='utf-8') as fh:
        return json.load(fh) or {}


def s4_fields(eval_dir, key, suffix=S4_SUFFIX):
    with open(os.path.join(eval_dir, 'snapshots', key + suffix), encoding='utf-8') as fh:
        return (json.load(fh).get('fields') or {})


def campus_token(cp):
    cp = cp if isinstance(cp, dict) else {}
    if (cp.get('institution_id') or '').strip():
        return cp['institution_id'].strip()
    name = (cp.get('institution') or '').strip()
    return 'h:' + hashlib.sha256(name.upper().encode('utf-8')).hexdigest()[:8] if name else '-'


def _name_token(name):
    return 'h:' + hashlib.sha256(name.strip().upper().encode('utf-8')).hexdigest()[:8] if (name or '').strip() else '-'


def plan_offer_doc(doc, fields=None):
    """Every planner's outcome for one offer document — on its stored fields, or on ``fields`` put in
    their place on an in-memory COPY (the row and its application are never changed)."""
    from apps.scholarship.pathway_engine import student_offer_check
    from apps.scholarship.services.offer_link import OFFER_SOURCES, is_empty_pick, plan_offer_link
    from apps.scholarship.services.offer_sync import institution_fill, plan_bumi_realign
    d = copy.copy(doc)
    d.application = copy.deepcopy(doc.application)
    vf = copy.deepcopy(doc.vision_fields) if isinstance(doc.vision_fields, dict) else {}
    if fields is not None:
        vf['fields'] = copy.deepcopy(fields)
    d.vision_fields = vf
    app = d.application
    chk = student_offer_check(d)
    reason, r_cp, _ = plan_bumi_realign(app, d, chk)
    out = {'ticks': {k: chk.get(k) for k in TICKS},
           'realign': reason or 'realign', 'realign_course': (r_cp or {}).get('course_id') or '-',
           'realign_campus': campus_token(r_cp) if r_cp else '-'}
    cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
    if (cp.get('source') or '') not in OFFER_SOURCES and not is_empty_pick(cp):
        out.update(link='not_offer_sourced', link_course='-', link_campus='-')
    elif not reason:
        out.update(link='realign_first', link_course=out['realign_course'], link_campus=out['realign_campus'])
    else:
        l_reason, l_cp, _ = plan_offer_link(app, d, chk)
        out.update(link=l_reason or 'link', link_course=(l_cp or {}).get('course_id') or '-',
                   link_campus=campus_token(l_cp) if l_cp else '-')
    out['fill'] = _name_token(institution_fill(app, offer=d, offer_check=chk))
    # The owner's money ruling (2026-11-02): a not_offer_letter document never dates the course. Shown
    # per letter: the start year this letter WOULD give if it were allowed to (the ruling's reach).
    from apps.scholarship.pathway_engine import offer_band
    iy = (chk.get('intake_year') or '').strip()
    out['not_offer_dated'] = bool(iy and offer_band(d) == 'not_offer_letter')
    from apps.scholarship.pathway_engine import parse_reporting_date
    rd = chk.get('reporting_date')
    out['_money'] = {'reporting_date': str(parse_reporting_date(rd) if isinstance(rd, str) else None),
                     'intake_year': iy}                  # compared in `compare_one`, never printed
    return out


def reguard(eval_dir, key, cache, fields, profile_nric):
    """The S4 fields with the IC guard RE-APPLIED against the production profile IC, when the cache holds
    the model's own pre-guard read (`raw_identity`, caches made since 2026-11-02); else the fields as cached.
    Returns (fields, how): 'reguarded:<outcome>' | 'no_raw_read' (an older cache: the eval-time blank stands)."""
    from apps.scholarship.offer_ic import guard_nric
    raw = (cache or {}).get('raw_identity')
    if not isinstance(raw, dict):
        return fields, 'no_raw_read'
    ocr = os.path.join(eval_dir, 'snapshots', key + '.ocr.txt')
    text = open(ocr, encoding='utf-8').read() if os.path.exists(ocr) else ''
    layer = bool(((cache or {}).get('offer_reader_inputs') or {}).get('text_layer_chars'))
    out = {**fields, **raw}
    return out, 'reguarded:' + guard_nric(out, profile_nric=profile_nric, page1_text=text, page1_is_text_layer=layer)


def printed_ic_is_profile(eval_dir, key, profile_nric):
    """Does the IC the letter PRINTS (the hand-checked answer) equal the production profile IC? 'yes' / 'no' /
    'no_answer' / 'no_profile' — the evidence for a blank the guard made for want of a profile."""
    from apps.scholarship.offer_ic import digits
    path = os.path.join(eval_dir, 'snapshots', key + '.offer_expect.json')
    printed = digits((json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}).get('candidate_nric'))
    if not printed:
        return 'no_answer'
    return 'no_profile' if not digits(profile_nric) else ('yes' if printed == digits(profile_nric) else 'no')


def compare_one(doc, fields):
    """{doc, app, live, stored, s4, changed: [what differs]} — ids and outcomes only."""
    stored, s4 = plan_offer_doc(doc), plan_offer_doc(doc, fields)
    changed = [k for k in ('realign', 'realign_course', 'realign_campus', 'link', 'link_course',
                           'link_campus', 'fill') if stored[k] != s4[k]]
    changed += [f'tick:{k}' for k in TICKS if stored['ticks'][k] != s4['ticks'][k]]
    m_old, m_new = stored.pop('_money'), s4.pop('_money')
    money = [f'money:{k}' for k in ('reporting_date', 'intake_year') if m_old[k] != m_new[k]]
    new_red = [k for k in ('name', 'ic') if s4['ticks'][k] == 'mismatch' and stored['ticks'][k] != 'mismatch']
    return {'doc': doc.pk, 'app': doc.application_id, 'live': doc.superseded_at is None,
            'stored': stored, 's4': s4, 'changed': changed, 'money': money, 'new_red': new_red}


def s5_fields(eval_dir, key, cache, doc, profile_nric):
    """(fields, how) for an S5 cache: a lock RE-DERIVED against the live row (the production profile IC, the
    live `vision_fields` as the prior); a fallback cache's own fields (a guess, flagged)."""
    if cache.get('s5') != 'locked':
        return cache.get('fields') or {}, 'fallback:' + str(cache.get('fallback_guess') or 'unknown')
    from apps.scholarship.eval.offer_replay import page1_of, production_text
    from apps.scholarship.offer_exact import exact_read
    text, route = production_text(os.path.join(eval_dir, 'snapshots'), key)
    ex = exact_read(text, from_text_layer=route == 'text_layer', page1_layer=page1_of(eval_dir, key, route),
                    prior=doc.vision_fields, profile_nric=profile_nric)
    if ex is None:
        live = doc.vision_fields.get('fields') if isinstance(doc.vision_fields, dict) else None
        return dict(live or {}), 's5:ic_refused_live'
    return ex['fields'], 's5:' + ex['offer_reader_inputs']['nric_check']


def dry_run(eval_dir, keys, *, session=read_only_rollback, out=print, suffix=S4_SUFFIX):
    from apps.scholarship.models import ApplicantDocument
    rows, totals = {}, Counter()
    with session():
        for key in keys:
            did = doc_id_of(key)
            doc = (ApplicantDocument.objects.select_related('application', 'application__profile')
                   .filter(pk=did, doc_type='offer_letter').first()) if did else None
            if doc is None:
                totals['no_document'] += 1
                out(f'  {key:<32} no offer document in this database')
                continue
            cache = _cache(eval_dir, key, suffix)
            profile_ic = getattr(getattr(doc.application, 'profile', None), 'nric', '') or ''
            if 's5' in cache:
                fields, how = s5_fields(eval_dir, key, cache, doc, profile_ic)
            else:
                fields, how = reguard(eval_dir, key, cache, cache.get('fields') or {}, profile_ic)
            r = compare_one(doc, fields)
            r['ic_guard'] = how
            totals[f'ic_guard:{how.split(":")[0]}'] += 1
            eval_check = ((cache.get('offer_reader_inputs') or {}).get('nric_check') or '')
            if eval_check.startswith('blank'):
                r['eval_blank_printed_is_profile'] = printed_ic_is_profile(eval_dir, key, profile_ic)
                totals[f"eval_blank:{eval_check.split('+')[0]}:printed_is_profile={r['eval_blank_printed_is_profile']}"] += 1
            rows[key] = r
            totals['letters'] += 1
            totals['live' if r['live'] else 'superseded'] += 1
            totals['changed' if r['changed'] else 'unchanged'] += 1
            for which in ('stored', 's4'):
                totals[f'not_offer_dated:{which}'] += r[which]['not_offer_dated']
            for c in r['changed']:
                totals[f'changed:{c}'] += 1
            for c in r['money'] + [f'new_red:{k}' for k in r['new_red']]:
                totals[c] += 1
            totals['money:changed' if r['money'] else 'money:unchanged'] += 1
            out(_line(key, r))
    out('totals: ' + ', '.join(f'{k}={v}' for k, v in sorted(totals.items())))
    return rows, totals


def _line(key, r):
    s, n = r['stored'], r['s4']
    parts = [f"realign {s['realign']}:{s['realign_course']}@{s['realign_campus']} -> "
             f"{n['realign']}:{n['realign_course']}@{n['realign_campus']}",
             f"link {s['link']}:{s['link_course']}@{s['link_campus']} -> {n['link']}:{n['link_course']}@{n['link_campus']}",
             f"fill {s['fill']} -> {n['fill']}"]
    ticks = [f"{k} {s['ticks'][k]}->{n['ticks'][k]}" for k in TICKS if s['ticks'][k] != n['ticks'][k]]
    return (f"  {key:<32} doc={r['doc']} app={r['app']} {'live' if r['live'] else 'superseded'} | "
            + ' | '.join(parts) + ' | ticks ' + (', '.join(ticks) or 'same')
            + f" | money {','.join(m.split(':')[1] for m in r.get('money', [])) or 'same'}"
            + (f" | NEW_RED {','.join(r['new_red'])}" if r.get('new_red') else '')
            + f" | ic_guard {r.get('ic_guard', '-')}"
            + (f" | eval_blank printed_is_profile={r['eval_blank_printed_is_profile']}"
               if 'eval_blank_printed_is_profile' in r else ''))


def main(argv=None, *, session=None, out=print):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--eval-dir', default=DEFAULT_EVAL_DIR)
    ap.add_argument('--keys', default='')
    ap.add_argument('--suffix', default=S4_SUFFIX, help='the S4 cache suffix (default: the final reader)')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--allow-sqlite', action='store_true', help='tests only')
    args = ap.parse_args(argv)
    keys = [k.strip() for k in args.keys.split(',') if k.strip()] or s4_keys(args.eval_dir, args.suffix)
    if not keys:
        out(f'No {args.suffix} caches in {args.eval_dir}.')
        return 2
    sess = session or (lambda: read_only_rollback(allow_sqlite=args.allow_sqlite))
    rows, totals = dry_run(args.eval_dir, keys, session=sess, out=(lambda *_: None) if args.json else out,
                           suffix=args.suffix)
    if args.json:
        out(json.dumps({'rows': rows, 'totals': dict(totals)}, indent=1, sort_keys=True, default=str))
    return 0


def bootstrap_django():
    """Development settings on the DATABASE_URL given (no other env read); refuses without one."""
    if not os.environ.get('DATABASE_URL'):
        print('DATABASE_URL is not set - nothing read.')
        sys.exit(2)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'halatuju.settings.development'
    import django
    django.setup()
    from django.db import connection
    s = connection.settings_dict
    print(f"DB: {s.get('ENGINE')} -> {s.get('HOST')}:{s.get('PORT')} (one read-only transaction, rolled back)")


if __name__ == '__main__':
    bootstrap_django()
    sys.exit(main(sys.argv[1:]))
