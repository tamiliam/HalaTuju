"""Does the in-house KWSP parser read the REAL statements' contribution tables? (TD-317, TD-319)

A HAND-RUN measurement, never a test: it reads `snapshots/epf__*.ocr.txt`, which is gitignored PII
(README.md, "Committed? No") and therefore absent from the deploy gate's build. The committed tests
use synthetic twins of these layouts (`tests/fixtures_epf.py`); this script is how a human checks
the twins still describe the real thing.

Prints one row per snapshot — the contribution status, months, the two split totals and the salary
`salary_figures._epf_monthly_salary` derives — and exits NON-ZERO when fewer than FLOOR statements
read both totals. Measured 2026-10-01: 5 of the 13 read (every one that carries a table); the
other eight have nothing to split (four "Tiada Transaksi", one cut off above its table, three not a
Penyata Ahli). Prints figures only — never a name, an NRIC or an address.

Usage:  python apps/scholarship/eval/epf_table_check.py
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, 'snapshots')
#: The 2026-10-01 measurement. A MINIMUM: a new snapshot that reads raises nothing here.
FLOOR = 5


def main():
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))   # halatuju_api/
    from apps.scholarship.doc_parse import parse_by_labels
    from apps.scholarship.income_engine.salary_figures import _epf_monthly_salary

    paths = sorted(glob.glob(os.path.join(SNAP, 'epf__*.ocr.txt')))
    if not paths:
        print(f'No EPF snapshots in {SNAP} - this measurement needs the local corpus.')
        return 2
    read = 0
    for path in paths:
        with open(path, encoding='utf-8') as fh:
            r = parse_by_labels('epf', fh.read())
        key = os.path.basename(path)
        if r is None:
            print(f'{key} | None (not a Penyata Ahli -> Gemini)')
            continue
        both = bool(r.get('employer_contribution_total') and r.get('employee_contribution_total'))
        read += both
        print(f"{key} | {r.get('contribution_status')} | months {r.get('months_counted')} "
              f"| er {r.get('employer_contribution_total')} "
              f"| ee {r.get('employee_contribution_total')} "
              f"| salary {_epf_monthly_salary(r)}")
    print(f'\n{read} of {len(paths)} statements read both split totals (floor {FLOOR}).')
    return 0 if read >= FLOOR else 1


if __name__ == '__main__':
    sys.exit(main())
