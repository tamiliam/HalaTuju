"""The render pre-filter over the fixture corpus, through the REAL gate (TD-692, 2026-11-20).

A HAND-RUN measurement (and the body of `tests/test_render_check_corpus.py`): every *.pdf / *.PDF under the
fixtures root, recursively, goes through `pdf_render_check.render_refusal(data, lambda n: range(min(n, 30)))`,
the same call `pdf_pages` makes before pdfium renders, so the image-filter and content-filter whitelists count
(a `page_cost(limits=False)` probe does not see them). It prints counts and refusal reasons only, NEVER a file
name, a letter's text or any other personal data. The real letters are gitignored (README.md).

    python -I apps/scholarship/eval/render_check_corpus.py [fixtures root]

The root defaults to $HALATUJU_FIXTURES_ROOT, else this folder's `fixtures/`.
"""
import logging
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))      # halatuju_api/
if _API_ROOT not in sys.path:                  # run as a script with -I: reach the app package
    sys.path.insert(0, _API_ROOT)

#: The environment variable that names another fixtures root (the main checkout's real letters).
ROOT_ENV = 'HALATUJU_FIXTURES_ROOT'
#: The pages the gate is asked about, as the eval of round 11 measured them: every page up to 30.
MAX_PAGES = 30


def fixtures_root() -> str:
    return os.environ.get(ROOT_ENV) or os.path.join(HERE, 'fixtures')


def pdf_paths(root: str) -> list:
    """Every *.pdf / *.PDF (any case) under ``root``, recursively, sorted."""
    found = []
    for folder, _, names in os.walk(root):
        found.extend(os.path.join(folder, n) for n in names if n.lower().endswith('.pdf'))
    return sorted(found)


def census(root: str) -> dict:
    """{'files', 'empty', 'pages', 'refused': Counter(reason), 'refused_not_empty': Counter(reason)}.
    ``refused_not_empty`` counts refusals of files that are not already known unreadable (an empty file)."""
    from apps.scholarship.pdf_render_check import render_refusal
    out = {'files': 0, 'empty': 0, 'pages': 0, 'refused': Counter(), 'refused_not_empty': Counter()}
    for path in pdf_paths(root):
        with open(path, 'rb') as f:
            data = f.read()
        out['files'] += 1
        out['empty'] += not data
        n, reason = render_refusal(data, lambda n: range(min(n, MAX_PAGES)))
        out['pages'] += min(n, MAX_PAGES)
        if reason is not None:
            out['refused'][reason] += 1
            if data:
                out['refused_not_empty'][reason] += 1
    return out


def main(argv) -> int:
    root = argv[1] if len(argv) > 1 else fixtures_root()
    logging.getLogger('pypdf').setLevel(logging.ERROR)     # its repair notes name nothing, but are noise
    c = census(root)
    print(f"{c['files']} PDFs ({c['empty']} empty), {c['pages']} pages cleared, "
          f"{sum(c['refused'].values())} refused, {sum(c['refused_not_empty'].values())} of them not empty")
    for reason, k in c['refused'].most_common():
        print(f'  {k:4d}  {reason}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
