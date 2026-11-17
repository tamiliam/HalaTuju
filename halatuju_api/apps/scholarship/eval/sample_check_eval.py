"""H9 paid sample-check run: how well does the REAL sample-stamp prompt tell a stamped / drawn
SAMPLE from a real IC?

A HAND-RUN measurement, never a test (the committed test mocks the model). It calls the real prompt
through `genuineness/sample_stamp._ask_model` (gemini-2.5-flash first, as the live code does) on LOCAL
picture files only: no database write, no Storage access, no stored document is re-read. The usage
meter (`usage.record_usage`, which would write a row) is replaced by an in-memory capture, which is
also where the token counts come from. Output (answer + thinking tokens) is billed at the output
rate (`usage.gemini_tokens`, TD-459).

Sets: `real` (the real IC files, expected NOT sample), `drawings` (rasterised sample drawings,
expected sample), `stamped` (a copy of each real IC with a large diagonal SAMPLE / CONTOH, expected
sample). Real IC pictures are PII: doc ids are file-name stems only; nothing else is printed.

Usage:
  python apps/scholarship/eval/sample_check_eval.py --fixtures DIR --samples DIR --stamped DIR \
      --out results.json [--limit N] [--max-usd 1.10] [--env PATH_TO_.env] [--make-stamped]
`--fixtures` holds the `ic` and `parent_ic` sub-folders; `--samples` the PNG drawings. `--make-stamped`
(re)builds the stamped copies in `--stamped` first (PIL). The run stops before a call that could pass
`--max-usd`.
"""
import argparse
import json
import os
import sys

USD_PER_M_IN = 0.30
USD_PER_M_OUT = 2.50
FIRST_CALL_GUESS_USD = 0.004     # used for the cap check until a real call has been priced
IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.pdf')
CONTENT_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                 '.pdf': 'application/pdf'}


def cost_usd(input_tokens, output_tokens):
    return ((input_tokens or 0) * USD_PER_M_IN + (output_tokens or 0) * USD_PER_M_OUT) / 1_000_000


def list_set(folder, set_name, expected, subdirs=('',)):
    """[{'id', 'set', 'expected', 'path'}] for every picture file under ``folder``."""
    items = []
    for sub in subdirs:
        d = os.path.join(folder, sub) if sub else folder
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            stem, ext = os.path.splitext(name)
            if ext.lower() in IMAGE_EXT:
                items.append({'id': stem, 'set': set_name, 'expected': expected,
                              'path': os.path.join(d, name)})
    return items


def score(rows):
    """Per-set tallies {set: {'n', 'right', 'wrong', 'no_answer'}}; 'right' = the verdict equals
    the expected one; no_answer rows are neither right nor wrong."""
    out = {}
    for r in rows:
        t = out.setdefault(r['set'], {'n': 0, 'right': 0, 'wrong': 0, 'no_answer': 0})
        t['n'] += 1
        if r.get('is_sample') is None:
            t['no_answer'] += 1
        elif r['is_sample'] == (r['expected'] == 'sample'):
            t['right'] += 1
        else:
            t['wrong'] += 1
    return out


def run_check(items, ask, max_usd=1.10, write=None):
    """Run ``ask(item) -> {'is_sample': bool|None, 'reason', 'input_tokens', 'output_tokens'}`` over
    ``items``. One retry on no answer. Stops before a call whose worst case (the dearest call so
    far) would pass ``max_usd``. Returns (rows, summary). ``write(rows)`` runs after each item."""
    rows, spent, calls, worst, stopped = [], 0.0, 0, FIRST_CALL_GUESS_USD, False
    for it in items:
        if spent + worst > max_usd:
            stopped = True
            break
        res = None
        for attempt in (1, 2):
            if attempt == 2 and spent + worst > max_usd:
                break
            res = ask(it)
            calls += 1
            c = cost_usd(res.get('input_tokens'), res.get('output_tokens'))
            spent += c
            worst = max(worst, c)
            if res.get('is_sample') is not None:
                break
        answered = bool(res) and res.get('is_sample') is not None
        rows.append({'id': it['id'], 'set': it['set'], 'expected': it['expected'],
                     'is_sample': res['is_sample'] if answered else None,
                     'verdict': ('sample' if res['is_sample'] else 'not_sample') if answered
                     else 'no_answer',
                     'reason': (res or {}).get('reason', ''),
                     'input_tokens': (res or {}).get('input_tokens'),
                     'output_tokens': (res or {}).get('output_tokens'),
                     'model': (res or {}).get('model', '')})
        if write:
            write(rows)
    return rows, {'calls': calls, 'cost_usd': round(spent, 4), 'stopped_by_cap': stopped,
                  'scores': score(rows)}


# ── live pieces (need Django settings + the key; never used by the unit test) ────────────────────

def _setup_django(env_path):
    """Settings only; the one variable taken from the .env is the key. Never printed."""
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'halatuju.settings.development')
    os.environ.pop('DATABASE_URL', None)
    if env_path and os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as fh:
            for line in fh:
                if line.startswith('GEMINI_API_KEY='):
                    os.environ['GEMINI_API_KEY'] = line.split('=', 1)[1].strip().strip('"\'')
    import django
    django.setup()


def make_live_ask():
    """The real `_ask_model`, with the usage meter swapped for a capture (no DB) and the Gemini
    seam wrapped to keep the model's reason."""
    from apps.scholarship import usage, vision
    from apps.scholarship.genuineness import sample_stamp
    cap = {}

    def fake_record(service, *, model='', input_tokens=None, output_tokens=None, **kw):
        cap['model'] = model
        cap['in'] = cap.get('in', 0) + (input_tokens or 0)
        cap['out'] = cap.get('out', 0) + (output_tokens or 0)

    real_call = vision._call_gemini_json

    def wrapped(*a, **kw):
        r = real_call(*a, **kw)
        cap['reason'] = str(r.get('reason', ''))[:200] if isinstance(r, dict) else ''
        return r

    usage.record_usage = fake_record
    vision._call_gemini_json = wrapped

    def ask(item):
        cap.clear()
        with open(item['path'], 'rb') as fh:
            data = fh.read()
        ct = CONTENT_TYPES[os.path.splitext(item['path'])[1].lower()]
        verdict = sample_stamp._ask_model(data, ct)
        return {'is_sample': verdict, 'reason': cap.get('reason', ''), 'input_tokens': cap.get('in', 0),
                'output_tokens': cap.get('out', 0), 'model': cap.get('model', '')}
    return ask


def make_stamped(real_items, out_dir):
    """One stamped PNG per real IC: a big semi-transparent diagonal SAMPLE (even index) or CONTOH."""
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont
    from apps.scholarship.pdf_pages import pdf_first_page_png
    os.makedirs(out_dir, exist_ok=True)
    made = []
    for i, it in enumerate(real_items):
        with open(it['path'], 'rb') as fh:
            data = fh.read()
        if it['path'].lower().endswith('.pdf'):
            data = pdf_first_page_png(data)
            if not data:
                continue
        img = Image.open(BytesIO(data)).convert('RGB')
        w, h = img.size
        word = 'SAMPLE' if i % 2 == 0 else 'CONTOH'
        size = int(min(w, h) * 0.45)
        try:
            font = ImageFont.truetype('arialbd.ttf', size)
        except OSError:
            font = ImageFont.load_default(size)
        side = int((w * w + h * h) ** 0.5)
        layer = Image.new('RGBA', (side, side), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((side // 2, side // 2), word, font=font, fill=(200, 0, 0, 120),
                                   anchor='mm')
        layer = layer.rotate(30, resample=Image.BICUBIC)
        left, top = (side - w) // 2, (side - h) // 2
        crop = layer.crop((left, top, left + w, top + h))
        img.paste(crop, (0, 0), crop)
        name = f"{it['id']}__{word.lower()}.png"
        img.save(os.path.join(out_dir, name))
        made.append(name)
    return made


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--fixtures', required=True)
    ap.add_argument('--samples', required=True)
    ap.add_argument('--stamped', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--max-usd', type=float, default=1.10)
    ap.add_argument('--env', default='')
    ap.add_argument('--make-stamped', action='store_true')
    a = ap.parse_args(argv)
    _setup_django(a.env)
    real = list_set(a.fixtures, 'real', 'not_sample', ('ic', 'parent_ic'))
    if a.make_stamped:
        make_stamped(real, a.stamped)
    items = (real + list_set(a.samples, 'drawings', 'sample')
             + list_set(a.stamped, 'stamped', 'sample'))
    if a.limit:
        items = items[:a.limit]

    def write(rows):
        with open(a.out, 'w', encoding='utf-8') as fh:
            json.dump({'rows': rows}, fh, indent=1)

    rows, summary = run_check(items, make_live_ask(), a.max_usd, write)
    with open(a.out, 'w', encoding='utf-8') as fh:
        json.dump({'summary': summary, 'rows': rows}, fh, indent=1)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
