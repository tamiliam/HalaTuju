"""Replay the PROBLEM-DOCUMENT corpus: does each document that once caused a misread fix still read
the corrected way? (TD-151 (1), 2026-10-02)

A HAND-RUN check, never a test - the same shape as `epf_table_check.py`. It reads
`snapshots/<key>.json` (the stored read) and `snapshots/<key>.ocr.txt` (the OCR text), which are
gitignored PII and absent from the deploy gate. The expected outcomes live in `labels.json` ->
`regressions` (committed, PII-free). The committed tests run these SAME check functions on
synthetic twins (`tests/test_regression_corpus.py`), so the rules cannot drift from this script.

Prints one PII-free line per case (PASS / FAIL / NOT LOCAL) and exits non-zero on any FAIL or when
no case could be replayed. Run it after any change to a parser, a prompt, the signature model or
the salary figure:

    python apps/scholarship/eval/regression_check.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, 'snapshots')


# ── the checks: (stored vision_fields, ocr text, expected) -> (ok, PII-free detail) ──────────
def declared_subjects_match_stored(vf, text, expected):
    from apps.scholarship.academic_engine import _declared_subject_count
    declared = _declared_subject_count((text or '').upper())
    kept = len(((vf or {}).get('fields') or {}).get('results') or [])
    return (declared is not None and declared == kept) == bool(expected), \
        f'declared {declared}, read kept {kept}'


def declared_subjects_found(vf, text, expected):
    from apps.scholarship.academic_engine import _declared_subject_count
    declared = _declared_subject_count((text or '').upper())
    return (declared is not None) == bool(expected), f'declared {declared}'


def signature_status(vf, text, expected, doc_type=None):
    from apps.scholarship.genuineness import signature_genuineness
    dt = None if doc_type == 'results_slip' else doc_type
    got = signature_genuineness(text or '', doc_type=dt)['status']
    return got == expected, f'signature {got}'


def epf_parser_declines(vf, text, expected):
    from apps.scholarship.doc_parse import parse_by_labels
    declined = parse_by_labels('epf', text or '') is None
    return declined == bool(expected), f'parser declined {declined}'


def salary_amount_plausible(vf, text, expected):
    from apps.scholarship.income_engine.salary_figures import (_SLIP_MONTHLY_MAX, _SLIP_MONTHLY_MIN,
                                                               _salary_monthly_amount)
    amt = _salary_monthly_amount(((vf or {}).get('fields')) or {})
    ok = amt is None or _SLIP_MONTHLY_MIN <= amt <= _SLIP_MONTHLY_MAX
    return ok == bool(expected), 'no usable figure' if amt is None else 'figure inside the window'


CHECKS = {
    'declared_subjects_match_stored': declared_subjects_match_stored,
    'declared_subjects_found': declared_subjects_found,
    'signature_status': signature_status,
    'epf_parser_declines': epf_parser_declines,
    'salary_amount_plausible': salary_amount_plausible,
}


def run_case(entry, vf, text):
    """Every check of one labelled case -> list of (name, ok, detail)."""
    out = []
    for name, expected in (entry.get('checks') or {}).items():
        fn = CHECKS[name]
        if fn is signature_status:
            ok, detail = fn(vf, text, expected, doc_type=entry.get('doc_type'))
        else:
            ok, detail = fn(vf, text, expected)
        out.append((name, ok, detail))
    return out


def main():
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))   # halatuju_api/
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'halatuju.settings.base')
    import django
    django.setup()
    with open(os.path.join(HERE, 'labels.json'), encoding='utf-8') as fh:
        cases = json.load(fh).get('regressions') or {}
    replayed = failed = 0
    for key, entry in cases.items():
        js, txt = os.path.join(SNAP, f'{key}.json'), os.path.join(SNAP, f'{key}.ocr.txt')
        if not os.path.exists(js):
            print(f'{key} ({entry.get("case")}) | NOT LOCAL - capture it to replay')
            continue
        with open(js, encoding='utf-8') as fh:
            vf = (json.load(fh) or {}).get('vision_fields') or {}
        text = ''
        if os.path.exists(txt):
            with open(txt, encoding='utf-8') as fh:
                text = fh.read()
        results = run_case(entry, vf, text)
        replayed += 1
        bad = [r for r in results if not r[1]]
        failed += bool(bad)
        print(f'{key} ({entry.get("case")}) | {"FAIL" if bad else "PASS"} | '
              + '; '.join(f'{n}: {d}' for n, _, d in results))
    print(f'\n{replayed} replayed, {failed} failed, {len(cases) - replayed} not local.')
    return 1 if failed or not replayed else 0


if __name__ == '__main__':
    sys.exit(main())
