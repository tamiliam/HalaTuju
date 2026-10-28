"""EPF — the KWSP mobile app's "Semakan Baki Simpanan" balance screen (TD-411, MODEL_VERSION 1.17.0).

Before 1.17.0 the EPF slot knew only the printed Penyata Ahli, so a real screenshot of the app (doc 1395:
the balance, the month-by-month contribution table, the "Kembali" and "Dapatkan Penyata" buttons, the
KWSP logo) matched three generic probes — p=0.15 — and read `not_epf`, as if it were the wrong document.

The list is scored BESIDE the Penyata Ahli in `results_doc._FAMILIES['epf']`: best fit wins and names
the type (`epf` / `epf_app`); a tie keeps `epf`, the first key, and a printed statement scores far lower
here than on its own list (its contribution table shares only the 1-point column names), so every
Penyata Ahli reads exactly as before. The distinctive marks are the screen title, "Baki Simpanan" and
the app's buttons (2-3 points); the table's column names are shared with the printed statement and with
the KWSP lines of a payslip, so they weigh 1 — a payslip's "KWSP" + "Caruman Majikan" is 2/15 and still
reads `not_epf`.

⚠ AT MOST SUSPECT. A screenshot is easy to fake and is not the issued statement, so this family never
reads `genuine` however complete the screen: `screen_at_most_suspect` lowers it to `suspect` — the right
kind of proof, for the officer to confirm by eye. Pure + deterministic; no Django.
"""

EPF_APP_SIGNATURES = [
    ('KWSP / EPF',                 ['KWSP', 'KUMPULAN WANG SIMPANAN PEKERJA'],            1, 'text'),
    ('SEMAKAN BAKI SIMPANAN',      ['SEMAKAN BAKI SIMPANAN'],                             3, 'text'),
    ('BAKI SIMPANAN',              ['BAKI SIMPANAN'],                                     2, 'text'),
    ('Bulan Caruman',              ['BULAN CARUMAN'],                                     2, 'text'),
    ('Caruman Majikan',            ['CARUMAN MAJIKAN'],                                   1, 'text'),
    ('Caruman Ahli',               ['CARUMAN AHLI'],                                      1, 'text'),
    ('Caruman - IWS',              ['CARUMAN IWS'],                                       1, 'text'),
    ('DAPATKAN PENYATA',           ['DAPATKAN PENYATA'],                                  3, 'text'),
    ('Kembali',                    ['KEMBALI'],                                           1, 'text'),
]

#: Families that are a SCREENSHOT of an app, never the issued document: their best band is suspect.
SCREEN_ONLY = frozenset({'epf_app'})


def screen_at_most_suspect(family: str, status: str, reason: str):
    """``(status, reason)`` with a `SCREEN_ONLY` family's `genuine` lowered to `suspect` (and the reason
    saying why); every other family and band is returned unchanged."""
    if family in SCREEN_ONLY and status == 'genuine':
        return 'suspect', f'an app screenshot, not the printed statement — {reason}'
    return status, reason
