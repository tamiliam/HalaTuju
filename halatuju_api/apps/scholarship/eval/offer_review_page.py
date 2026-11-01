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

THE OFFER CHECK (`--offer-check`, offer exact-read S2, 2026-11-01) — a second page,
`<eval-dir>/review_s2_offer.html`, same rules (local, offline, gitignored, every line starts
Right). It shows every letter, ANY split, with a usable answer where EITHER the answer's
`is_offer_letter` is not `yes` OR the stored production genuineness status is `not_offer_letter`
(read by the shared `stored_status` helper, TD-293). A letter with no usable answer is left off
(it has no label to check) and only counted. Each card: the document, then three lines only —
"What is this document?" (the answer's `is_offer_letter` in plain words), "What the live system
decided" (the stored status in plain words; Wrong = the system got it wrong), and the labeller's
note (read only, when there is one). Save downloads `offer_review_s2_results.json`
(`"page": "review_s2_offer"`, fields `is_offer_letter` and `system_status`); `--apply` counts it
the same way.

It prints counts and the page path — NEVER a value.

Usage:  python -I apps/scholarship/eval/offer_review_page.py [--eval-dir DIR] [--random N]
            [--seed S] [--split-file F] [--blank]
        python -I apps/scholarship/eval/offer_review_page.py [--eval-dir DIR] --offer-check
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
from apps.scholarship.eval import offer_review_html as orh
from apps.scholarship.genuineness.bands import stored_status   # the one reader (TD-293)

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

# The offer check (`--offer-check`, S2).
S2_PAGE_NAME = 'review_s2_offer.html'
S2_RESULTS_NAME = 'offer_review_s2_results.json'
S2_STORAGE_KEY = 'halatuju-offer-review-s2'
S2_PAGE_ID = 'review_s2_offer'
#: (results field, plain label, what the correction box asks) in page order.
S2_FIELDS = (
    ('is_offer_letter', 'What is this document?', 'What it really is'),
    ('system_status', 'What the live system decided', 'What the system should have decided'),
)
S2_FIELD_NAMES = tuple(f for f, _, _ in S2_FIELDS)
S2_IS_OFFER_WORDS = {'yes': 'Offer letter', 'conditional': 'Conditional offer',
                     'portal_page': 'Portal page or screenshot',
                     'not_offer': 'Not an offer letter', 'unsure': 'Unsure'}
#: Stored genuineness status → plain words. Unscored ('') and `unchecked` both read "Not checked".
S2_STATUS_WORDS = {'genuine': 'Genuine', 'likely_genuine': 'Genuine', 'suspect': 'Suspect',
                   'not_offer_letter': 'Not an offer letter', 'unchecked': 'Not checked',
                   '': 'Not checked'}
S2_INSTRUCTION = ("For each document, say whether our label is right, and whether the live "
                  "system's decision is right. Change a line to Wrong only if it is wrong. Press "
                  "Save my answers when you finish.")
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


def select_offer_check(eval_dir):
    """(sorted keys, answers, statuses, counts) for `--offer-check`: every letter, any split,
    with a usable answer whose `is_offer_letter` is not `yes`, OR whose stored genuineness status
    is `not_offer_letter`. A matching letter without a usable answer is only counted."""
    keys, answers, statuses = [], {}, {}
    counts = Counter()
    for key in orc.offer_keys(eval_dir):
        status = stored_status(orc.stored_vision_fields(eval_dir, key))
        answer = _usable_answer(eval_dir, key)
        system_no = status == 'not_offer_letter'
        if answer is None:
            if system_no:
                counts['skipped_no_answer'] += 1
            continue
        label_no = answer.get('is_offer_letter') != 'yes'
        if not (label_no or system_no):
            continue
        keys.append(key)
        answers[key], statuses[key] = answer, status
        counts['both' if label_no and system_no else 'label_only' if label_no else 'system_only'] += 1
    return keys, answers, statuses, {'total': len(keys), 'label_only': counts['label_only'],
                                     'system_only': counts['system_only'], 'both': counts['both'],
                                     'skipped_no_answer': counts['skipped_no_answer']}


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
    tag = ' <span class="unsure">unsure</span>' if unsure else ''
    return _choice_line(idx, field, label, _display(field, value), tag, blank)


def _choice_line(idx, field, label, shown, tag='', blank=False,
                 fix_label='What the letter really says'):
    """One Right / Wrong line: `shown` is already plain words; `tag` is trusted HTML."""
    base = f'c{idx}-{field}'
    right_on = '' if blank else ' checked'
    cls = ' blank' if shown == NOT_PRINTED else ''
    return f'''<fieldset class="line" data-field="{_e(field)}">
<legend>{_e(label)}{tag}</legend>
<p class="value{cls}">{_e(shown)}</p>
<div class="choices">
<label><input type="radio" name="{base}" value="right"{right_on}> Right</label>
<label><input type="radio" name="{base}" value="wrong"> Wrong</label>
</div>
<div class="fix" hidden>
<label for="{base}-fix">{_e(fix_label)}</label>
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


def s2_label_words(answer):
    value = answer.get('is_offer_letter')
    return S2_IS_OFFER_WORDS.get(str(value), str(value))


def s2_status_words(status):
    return S2_STATUS_WORDS.get(status, status)


def _s2_card_html(eval_dir, key, answer, status, idx, total):
    label, system = S2_FIELDS
    lines = [_choice_line(idx, label[0], label[1], s2_label_words(answer), fix_label=label[2]),
             _choice_line(idx, system[0], system[1], s2_status_words(status), fix_label=system[2])]
    note = answer.get('labeller_note')
    if _shown(note):
        lines.append(f'<div class="readonly"><p class="ro-label">Labeller\'s note</p>\n'
                     f'<p class="value">{_e(note)}</p></div>')
    doc = document_info(eval_dir, key)
    lines = '\n'.join(lines)
    return f'''<section class="card" data-key="{_e(key)}" id="card-{idx}">
<h2>Document {idx} of {total} <span class="done-badge" hidden>Looked at</span></h2>
<div class="cols">
<div class="left">
{_doc_html(doc, idx)}
</div>
<div class="right">
{lines}
<div class="card-end"></div>
</div>
</div>
</section>'''


#: The default page: every line starts ticked Right (owner request, 2026-11-01).
INSTRUCTION = ('Every line is already marked Right. Look at the document, and change a line to '
               'Wrong only if it does not match the letter, then type what the letter really says. '
               'When you finish, press Save my answers.')
#: `--blank`: no line ticked to start with.
INSTRUCTION_BLANK = ('For each letter, look at the document on the left and the answer on the '
                     'right. Tick Right or Wrong for each line. If wrong, type what the letter '
                     'really says. When you finish, press Save my answers at the bottom.')


_KEPT = ('Your changes are kept in this browser as you go, so closing or refreshing the page does '
         'not lose them.')


def build_page(eval_dir, keys, answers, blank=False):
    total = len(keys)
    cards = '\n'.join(_card_html(eval_dir, k, answers[k], i, total, blank)
                      for i, k in enumerate(keys, start=1))
    intro = (f'<p>{_e(INSTRUCTION_BLANK if blank else INSTRUCTION)}</p>\n<p>{_KEPT} Lines marked '
             f'<span class="unsure">unsure</span> are the ones most worth a careful look.</p>')
    return orh.page_html('Offer letter check', intro, cards, total, 'review_s1', STORAGE_KEY,
                         RESULTS_NAME, blank)


def build_offer_check_page(eval_dir, keys, answers, statuses):
    total = len(keys)
    cards = '\n'.join(_s2_card_html(eval_dir, k, answers[k], statuses[k], i, total)
                      for i, k in enumerate(keys, start=1))
    intro = f'<p>{html.escape(S2_INSTRUCTION, quote=False)}</p>\n<p>{_KEPT}</p>'
    return orh.page_html('Is it an offer letter?', intro, cards, total, S2_PAGE_ID,
                         S2_STORAGE_KEY, S2_RESULTS_NAME, blank=False)


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
    """Counts only from the owner's results (never a value, never a key). The fields counted
    follow the page that saved them (`review_s1` or the S2 offer check)."""
    letters = results.get('letters') if isinstance(results, dict) else None
    letters = letters if isinstance(letters, dict) else {}
    names = (S2_FIELD_NAMES if isinstance(results, dict) and results.get('page') == S2_PAGE_ID
             else FIELD_NAMES)
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
            if f not in names or verdict not in VERDICTS:
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
            'wrong_by_field': {f: wrong[f] for f in names},
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


def _write_offer_check(args):
    if args.blank:
        print('--blank does not apply to --offer-check: every line starts Right.')
        return 2
    keys, answers, statuses, counts = select_offer_check(args.eval_dir)
    if not keys:
        print(f"No letters for the offer check (left off, no usable answer: "
              f"{counts['skipped_no_answer']}).")
        return 2
    path = os.path.join(args.eval_dir, S2_PAGE_NAME)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(build_offer_check_page(args.eval_dir, keys, answers, statuses))
    print(f"offer check: {counts['total']} letters ({counts['label_only']} label not yes only + "
          f"{counts['system_only']} system not_offer_letter only + {counts['both']} both; "
          f"left off, no usable answer: {counts['skipped_no_answer']})")
    print(f'page: {path}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--eval-dir', default=orc.DEFAULT_EVAL_DIR)
    ap.add_argument('--split-file', default=orc.SPLIT_PATH)
    ap.add_argument('--random', type=int, default=RANDOM_N, help='letters drawn from the rest')
    ap.add_argument('--seed', type=int, default=SEED)
    ap.add_argument('--blank', action='store_true',
                    help='start with no line ticked (default: every line starts Right)')
    ap.add_argument('--offer-check', action='store_true',
                    help=f'write {S2_PAGE_NAME}: every letter whose label is not yes or whose '
                         f'stored status is not_offer_letter (any split)')
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
    if args.offer_check:
        return _write_offer_check(args)
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
