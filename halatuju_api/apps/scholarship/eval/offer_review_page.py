"""Offer letters read exactly — the owner's spot-check page (offer exact-read S1, 2026-11-01).

The correct answers (`snapshots/<key>.offer_expect.json`) are agent-written; the owner spot-checks
them (decision D1). This tool writes ONE self-contained local HTML page, `<eval-dir>/review_s1.html`,
INSIDE the gitignored corpus folder, which the owner opens by double-clicking. It shows real
student data: it is never published, uploaded or committed. It works offline — no server, no
external script or font; the documents load from their relative paths
(`fixtures/offer_letter/<key>.<ext>`) beside the page.

THE SAMPLE — from the held-out split (`offer_split.json`): every letter whose answer has a
non-empty `unsure_fields`, plus `--random N` (default 20) of the rest, drawn with
`random.Random(SEED).sample(sorted keys, N)`. Sorted by key. A held-out letter with no answer
file, or a malformed one, is skipped (counted, never named).

THE PAGE — one card per letter: the document on the left, the answer's fields on the right, each
with Right / Wrong and a correction box when Wrong; a note per letter. By default every line
starts ticked Right, so the owner changes only the wrong ones (`--blank`: nothing ticked). The
progress line counts letters looked at (scrolled to the note box) or changed (`--blank`: letters
with every line ticked). Work is kept in the browser (`localStorage`) and an earlier tick wins
over the default. "Save my answers" downloads `offer_review_results.json`:

  {"page": "review_s1", "mode": "prefilled" | "blank", "saved_at": "...",
   "letters": {<key>: {"fields": {<answer field>: {"verdict": "right" | "wrong" | "not_checked",
                                                  "correction": "..."}},
                       "note": "...", "looked_at": true | false}}}

`--apply <results.json>` reads that file and prints COUNTS ONLY (letters checked, fields marked
wrong per field, letters with any wrong). It never changes an answer file — the lead decides.

It prints counts and the page path — NEVER a value.

Usage:  python -I apps/scholarship/eval/offer_review_page.py [--eval-dir DIR] [--random N]
            [--seed S] [--split-file F] [--blank]
        python -I apps/scholarship/eval/offer_review_page.py --apply offer_review_results.json
"""
import argparse
import glob
import html
import json
import os
import random
import sys
from collections import Counter
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))      # halatuju_api/
_REPO_ROOT = os.path.dirname(_API_ROOT)
if _API_ROOT not in sys.path:                  # run as a script with -I: reach the app package
    sys.path.insert(0, _API_ROOT)
from apps.scholarship.eval import offer_read_check as orc

SEED = 20261101
RANDOM_N = 20
PAGE_NAME = 'review_s1.html'
RESULTS_NAME = 'offer_review_results.json'
STORAGE_KEY = 'halatuju-offer-review-s1'
VERDICTS = ('right', 'wrong', 'not_checked')
#: Where a page may be written inside this checkout: only the gitignored fixtures folder.
_IGNORED_ROOT = os.path.join(HERE, 'fixtures')

#: (answer field, plain label) in page order. `stream` / `specialisation` show only when set
#: (or marked unsure) — they belong to "Course".
PAGE_FIELDS = (
    ('candidate_name', 'Name'),
    ('candidate_nric', 'IC number'),
    ('institution_as_printed', 'Institution'),
    ('programme', 'Course'),
    ('stream', 'Course — stream (Bidang / Jurusan)'),
    ('specialisation', 'Course — specialisation (Bidang Pengkhususan)'),
    ('intake', 'Intake'),
    ('reporting_date', 'Reporting date'),
    ('offer_date', 'Offer date'),
    ('issuer', 'Issuer'),
    ('is_offer_letter', 'Is this an offer letter?'),
)
FIELD_NAMES = tuple(f for f, _ in PAGE_FIELDS)
_OPTIONAL = ('stream', 'specialisation')
_IS_OFFER_WORDS = {'yes': 'Yes', 'conditional': 'Yes, with conditions',
                   'portal_page': 'No — it is a web portal page',
                   'not_offer': 'No — it is not an offer letter', 'unsure': 'Not sure'}
NOT_PRINTED = '— not printed —'
_MAGIC = {'pdf': (b'%PDF',), 'jpg': (b'\xff\xd8',), 'jpeg': (b'\xff\xd8',),
          'png': (b'\x89PNG',)}


# ── The sample ───────────────────────────────────────────────────────────────────────────────
def _usable_answer(eval_dir, key):
    answer, problems = orc._read_answer(eval_dir, key)
    return answer if isinstance(answer, dict) and answer and not problems else None


def select_sample(eval_dir, heldout, n_random=RANDOM_N, seed=SEED):
    """(sorted keys, counts). Unsure answers always; `n_random` of the rest by a seeded draw."""
    answers, skipped = {}, 0
    for key in sorted(heldout):
        answer = _usable_answer(eval_dir, key)
        if answer is None:
            skipped += 1
        else:
            answers[key] = answer
    unsure = sorted(k for k, a in answers.items() if a.get('unsure_fields'))
    rest = sorted(set(answers) - set(unsure))
    drawn = random.Random(seed).sample(rest, min(max(n_random, 0), len(rest)))
    keys = sorted(set(unsure) | set(drawn))
    return keys, answers, {'unsure': len(unsure), 'random': len(drawn), 'skipped': skipped,
                           'total': len(keys)}


# ── The document ─────────────────────────────────────────────────────────────────────────────
def document_info(eval_dir, key):
    """{'rel': relative URL or None, 'ext', 'problem': plain words or None}."""
    hits = sorted(glob.glob(os.path.join(eval_dir, 'fixtures', 'offer_letter', key + '.*')))
    if not hits:
        return {'rel': None, 'ext': '', 'problem': 'The document file is missing, so there is '
                                                   'nothing to look at.'}
    path = hits[0]
    ext = os.path.splitext(path)[1].lstrip('.').lower()
    rel = 'fixtures/offer_letter/' + quote(os.path.basename(path))
    if os.path.getsize(path) == 0:
        return {'rel': None, 'ext': ext, 'problem': 'The document file is empty, so there is '
                                                    'nothing to look at.'}
    with open(path, 'rb') as fh:
        head = fh.read(8)
    if ext in _MAGIC and not head.startswith(_MAGIC[ext]):
        return {'rel': rel, 'ext': ext, 'problem': 'The document file looks damaged. It may not '
                                                   'open below.'}
    if ext not in _MAGIC:
        return {'rel': rel, 'ext': ext, 'problem': 'This kind of file may not open in the page. '
                                                   'Use the link to open it.'}
    return {'rel': rel, 'ext': ext, 'problem': None}


# ── The page ─────────────────────────────────────────────────────────────────────────────────
def page_fields(answer):
    """[(field, label)] shown for this answer."""
    unsure = set(answer.get('unsure_fields') or [])
    return [(f, label) for f, label in PAGE_FIELDS
            if f not in _OPTIONAL or _shown(answer.get(f)) or f in unsure]


def _shown(value):
    return value is not None and str(value).strip() != ''


def _display(field, value):
    if not _shown(value):
        return NOT_PRINTED
    if field == 'is_offer_letter':
        return _IS_OFFER_WORDS.get(str(value), str(value))
    return str(value)


def _e(value):
    return html.escape(str(value), quote=True)


def _doc_html(doc, n):
    parts = []
    if doc['problem']:
        parts.append(f'<p class="problem">{_e(doc["problem"])}</p>')
    if doc['rel']:
        src = _e(doc['rel'])
        if doc['ext'] == 'pdf':
            parts.append(f'<iframe class="doc" src="{src}" title="Letter {n} document"></iframe>')
        elif doc['ext'] in ('jpg', 'jpeg', 'png'):
            parts.append(f'<div class="doc"><img src="{src}" alt="Letter {n} document" '
                         f'data-broken="This picture could not be opened."></div>')
        parts.append(f'<p><a href="{src}" target="_blank" rel="noopener">Open the document in a '
                     f'new tab</a></p>')
    return '\n'.join(parts)


def _line_html(idx, field, label, value, unsure, blank=False):
    base = f'c{idx}-{field}'
    right_on = '' if blank else ' checked'
    tag = ' <span class="unsure">unsure</span>' if unsure else ''
    shown = _display(field, value)
    cls = ' blank' if shown == NOT_PRINTED else ''
    return f'''<fieldset class="line" data-field="{_e(field)}">
<legend>{_e(label)}{tag}</legend>
<p class="value{cls}">{_e(shown)}</p>
<div class="choices">
<label><input type="radio" name="{base}" value="right"{right_on}> Right</label>
<label><input type="radio" name="{base}" value="wrong"> Wrong</label>
</div>
<div class="fix" hidden>
<label for="{base}-fix">What the letter really says</label>
<input type="text" id="{base}-fix" class="correction" autocomplete="off">
</div>
</fieldset>'''


def _card_html(eval_dir, key, answer, idx, total, blank=False):
    unsure = set(answer.get('unsure_fields') or [])
    lines = '\n'.join(_line_html(idx, f, label, answer.get(f), f in unsure, blank)
                      for f, label in page_fields(answer))
    badge = 'Done' if blank else 'Looked at'
    doc = document_info(eval_dir, key)
    return f'''<section class="card" data-key="{_e(key)}" id="card-{idx}">
<h2>Letter {idx} of {total} <span class="done-badge" hidden>{badge}</span></h2>
<div class="cols">
<div class="left">
{_doc_html(doc, idx)}
</div>
<div class="right">
{lines}
<div class="note">
<label for="c{idx}-note">Note about this letter (you can leave this empty)</label>
<textarea id="c{idx}-note" class="note-box" rows="3"></textarea>
</div>
</div>
</div>
</section>'''


_CSS = '''
:root { --ink:#1a1a1a; --paper:#ffffff; --soft:#f3f3f0; --line:#c9c9c4; --accent:#1f5fa8;
        --warn:#9a3b00; --warnbg:#fff1e0; --ok:#1e6b2f; }
* { box-sizing:border-box; }
body { margin:0; padding:16px; font:18px/1.5 "Segoe UI", Arial, sans-serif; color:var(--ink);
       background:var(--soft); font-variant-numeric:lining-nums; }
h1 { font-size:28px; margin:0 0 8px; }
h2 { font-size:22px; margin:0 0 12px; }
.intro { max-width:900px; background:var(--paper); padding:16px; border:1px solid var(--line); }
#progress { font-size:20px; font-weight:bold; }
.card { background:var(--paper); border:1px solid var(--line); padding:16px; margin:24px 0; }
.cols { display:flex; flex-wrap:wrap; gap:24px; }
.left { flex:0 1 620px; min-width:0; position:sticky; top:8px; align-self:flex-start; }
.right { flex:1 1 360px; min-width:0; }
.doc { display:block; width:100%; max-width:600px; height:800px; border:1px solid var(--line);
       overflow:auto; background:#fafafa; }
.doc img { display:block; width:100%; height:auto; }
.problem { background:var(--warnbg); color:var(--warn); padding:8px 12px; font-weight:bold; }
.line { border:1px solid var(--line); margin:0 0 12px; padding:8px 12px; }
.line legend { font-weight:bold; padding:0 4px; }
.value { font-size:20px; margin:4px 0 8px; word-break:break-word; }
.value.blank { color:#666; font-style:italic; }
.unsure { background:var(--warnbg); color:var(--warn); border:1px solid var(--warn);
          padding:0 6px; font-size:16px; font-weight:bold; margin-left:6px; }
.choices label { display:inline-block; margin-right:24px; padding:4px 0; cursor:pointer; }
input[type=radio] { width:20px; height:20px; vertical-align:middle; }
.fix label, .note label { display:block; margin:8px 0 4px; }
input[type=text], textarea { width:100%; font:inherit; padding:6px 8px; border:1px solid #888; }
:focus-visible { outline:3px solid var(--accent); outline-offset:2px; }
.done-badge { color:var(--ok); font-size:18px; margin-left:8px; }
.save { text-align:center; padding:24px 0 48px; }
#save { font:inherit; font-size:24px; font-weight:bold; padding:16px 40px; color:#fff;
        background:var(--accent); border:0; cursor:pointer; }
#saved { font-size:20px; }
'''

_JS = r'''
(function () {
  var KEY = "__STORAGE_KEY__";
  var SEEN_KEY = KEY + "-looked-at";
  var MODE = "__MODE__";          /* "prefilled": every line starts Right; "blank": none ticked */
  var cards = Array.prototype.slice.call(document.querySelectorAll(".card"));
  var seen = {};
  try { seen = JSON.parse(localStorage.getItem(SEEN_KEY) || "{}") || {}; } catch (e) { seen = {}; }
  function markSeen(card) {
    var k = card && card.getAttribute("data-key");
    if (!k || seen[k]) { return; }
    seen[k] = true;
    try { localStorage.setItem(SEEN_KEY, JSON.stringify(seen)); } catch (e) { /* no storage */ }
    refresh();
  }
  function collect() {
    var out = {};
    cards.forEach(function (card) {
      var fields = {};
      card.querySelectorAll(".line").forEach(function (line) {
        var picked = line.querySelector("input[type=radio]:checked");
        fields[line.getAttribute("data-field")] = {
          verdict: picked ? picked.value : "not_checked",
          correction: line.querySelector(".correction").value
        };
      });
      out[card.getAttribute("data-key")] = {fields: fields,
                                            note: card.querySelector(".note-box").value,
                                            looked_at: !!seen[card.getAttribute("data-key")]};
    });
    return out;
  }
  function refresh() {
    var done = 0;
    cards.forEach(function (card) {
      var lines = card.querySelectorAll(".line"), ticked = 0;
      lines.forEach(function (line) {
        var picked = line.querySelector("input[type=radio]:checked");
        if (picked) { ticked += 1; }
        line.querySelector(".fix").hidden = !(picked && picked.value === "wrong");
      });
      var isDone = MODE === "blank" ? ticked === lines.length
                                    : !!seen[card.getAttribute("data-key")];
      card.querySelector(".done-badge").hidden = !isDone;
      if (isDone) { done += 1; }
    });
    document.getElementById("progress").textContent = done + " of " + cards.length +
      (MODE === "blank" ? " done" : " letters looked at or changed");
  }
  function remember() {
    try { localStorage.setItem(KEY, JSON.stringify(collect())); } catch (e) { /* no storage */ }
  }
  function restore() {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { saved = null; }
    if (!saved || typeof saved !== "object") { return; }
    cards.forEach(function (card) {
      var s = saved[card.getAttribute("data-key")];
      if (!s || typeof s !== "object") { return; }
      card.querySelectorAll(".line").forEach(function (line) {
        var f = (s.fields || {})[line.getAttribute("data-field")];
        if (!f) { return; }
        line.querySelector(".correction").value = f.correction || "";
        if (f.verdict !== "right" && f.verdict !== "wrong") { return; }  /* keeps the default */
        line.querySelectorAll("input[type=radio]").forEach(function (r) {
          r.checked = (r.value === f.verdict);
        });
      });
      card.querySelector(".note-box").value = s.note || "";
    });
  }
  document.querySelectorAll("img[data-broken]").forEach(function (img) {
    img.addEventListener("error", function () {
      var p = document.createElement("p");
      p.className = "problem";
      p.textContent = img.getAttribute("data-broken");
      img.parentNode.replaceChild(p, img);
    });
  });
  function cardOf(ev) { return ev.target.closest ? ev.target.closest(".card") : null; }
  document.addEventListener("change", function (ev) {
    markSeen(cardOf(ev)); refresh(); remember();
  });
  document.addEventListener("input", function (ev) { markSeen(cardOf(ev)); remember(); });
  if ("IntersectionObserver" in window) {   /* a letter is looked at once its note box shows */
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { markSeen(en.target.closest(".card")); }
      });
    });
    document.querySelectorAll(".note").forEach(function (n) { io.observe(n); });
  }
  document.getElementById("save").addEventListener("click", function () {
    var data = {page: "review_s1", mode: MODE, saved_at: new Date().toISOString(),
                letters: collect()};
    var blob = new Blob([JSON.stringify(data, null, 1)], {type: "application/json"});
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "__RESULTS_NAME__";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    remember();
    document.getElementById("saved").textContent =
      "Saved. Look for __RESULTS_NAME__ in your Downloads folder and send it back.";
  });
  restore();
  refresh();
})();
'''

#: The default page: every line starts ticked Right (owner request, 2026-11-01).
INSTRUCTION = ('Every line is already marked Right. Look at the document, and change a line to '
               'Wrong only if it does not match the letter, then type what the letter really says. '
               'When you finish, press Save my answers.')
#: `--blank`: no line ticked to start with.
INSTRUCTION_BLANK = ('For each letter, look at the document on the left and the answer on the '
                     'right. Tick Right or Wrong for each line. If wrong, type what the letter '
                     'really says. When you finish, press Save my answers at the bottom.')


def build_page(eval_dir, keys, answers, blank=False):
    total = len(keys)
    cards = '\n'.join(_card_html(eval_dir, k, answers[k], i, total, blank)
                      for i, k in enumerate(keys, start=1))
    js = (_JS.replace('__STORAGE_KEY__', STORAGE_KEY).replace('__RESULTS_NAME__', RESULTS_NAME)
          .replace('__MODE__', 'blank' if blank else 'prefilled'))
    instruction = INSTRUCTION_BLANK if blank else INSTRUCTION
    progress = f'0 of {total} done' if blank else f'0 of {total} letters looked at or changed'
    return f'''<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Offer letter check</title>
<style>{_CSS}</style>
</head>
<body>
<header class="intro">
<h1>Offer letter check</h1>
<p>{_e(instruction)}</p>
<p>Your changes are kept in this browser as you go, so closing or refreshing the page does not
lose them. Lines marked <span class="unsure">unsure</span> are the ones most worth a careful
look.</p>
<p id="progress" aria-live="polite">{progress}</p>
</header>
<main>
{cards}
</main>
<footer class="save">
<button type="button" id="save">Save my answers</button>
<p id="saved" aria-live="polite"></p>
</footer>
<script>{js}</script>
</body>
</html>
'''


def _inside(path, root):
    path, root = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:                         # different drives
        return False


def page_location_ok(eval_dir):
    """Never write the page into a tracked part of this checkout: outside it, or inside the
    gitignored `fixtures/` folder only."""
    return not _inside(eval_dir, _REPO_ROOT) or _inside(eval_dir, _IGNORED_ROOT)


# ── --apply ──────────────────────────────────────────────────────────────────────────────────
def apply_counts(results):
    """Counts only from the owner's results (never a value, never a key)."""
    letters = results.get('letters') if isinstance(results, dict) else None
    letters = letters if isinstance(letters, dict) else {}
    wrong = Counter()
    full = partly = untouched = any_wrong = corrections = notes = bad = 0
    for entry in letters.values():
        fields = entry.get('fields') if isinstance(entry, dict) else None
        if not isinstance(fields, dict):
            bad += 1
            continue
        verdicts = []
        for f, v in fields.items():
            verdict = v.get('verdict') if isinstance(v, dict) else None
            if f not in FIELD_NAMES or verdict not in VERDICTS:
                bad += 1
                continue
            verdicts.append(verdict)
            if verdict == 'wrong':
                wrong[f] += 1
                if str(v.get('correction') or '').strip():
                    corrections += 1
        ticked = sum(1 for v in verdicts if v != 'not_checked')
        if verdicts and ticked == len(verdicts):
            full += 1
        elif ticked:
            partly += 1
        else:
            untouched += 1
        if 'wrong' in verdicts:
            any_wrong += 1
        if str(entry.get('note') or '').strip():
            notes += 1
    return {'letters': len(letters), 'fully_checked': full, 'partly_checked': partly,
            'not_started': untouched, 'letters_with_any_wrong': any_wrong,
            'wrong_by_field': {f: wrong[f] for f in FIELD_NAMES},
            'corrections_typed': corrections, 'notes_typed': notes, 'unreadable_entries': bad}


def print_apply(c):
    print(f"letters in results: {c['letters']} | fully checked: {c['fully_checked']} | "
          f"partly checked: {c['partly_checked']} | not started: {c['not_started']}")
    print(f"letters with any line marked wrong: {c['letters_with_any_wrong']}")
    print('lines marked wrong, per field:')
    for f, n in c['wrong_by_field'].items():
        print(f'  {f:<24}{n:>4}')
    print(f"corrections typed: {c['corrections_typed']} | notes typed: {c['notes_typed']} | "
          f"unreadable entries: {c['unreadable_entries']}")
    print('No answer file was changed.')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--eval-dir', default=orc.DEFAULT_EVAL_DIR)
    ap.add_argument('--split-file', default=orc.SPLIT_PATH)
    ap.add_argument('--random', type=int, default=RANDOM_N, help='letters drawn from the rest')
    ap.add_argument('--seed', type=int, default=SEED)
    ap.add_argument('--blank', action='store_true',
                    help='start with no line ticked (default: every line starts Right)')
    ap.add_argument('--apply', metavar='RESULTS_JSON',
                    help="count the owner's saved results (changes nothing)")
    args = ap.parse_args(argv)
    if args.apply:
        try:
            results = orc.read_json_file(args.apply)
        except ValueError:
            print('The results file is not JSON.')
            return 1
        if results is None:
            print('The results file was not found.')
            return 2
        print_apply(apply_counts(results))
        return 0
    if not page_location_ok(args.eval_dir):
        print('Refused: the page shows real student data and may only be written outside this '
              'checkout or inside its gitignored eval fixtures folder.')
        return 2
    heldout = orc.load_heldout(args.split_file)
    keys, answers, counts = select_sample(args.eval_dir, heldout, args.random, args.seed)
    if not keys:
        print(f"No held-out letters with answers in the eval dir (skipped {counts['skipped']}).")
        return 2
    path = os.path.join(args.eval_dir, PAGE_NAME)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(build_page(args.eval_dir, keys, answers, args.blank))
    print(f"sample: {counts['total']} letters ({counts['unsure']} unsure + {counts['random']} "
          f"random; skipped {counts['skipped']})")
    print(f'page: {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
