"""EPF — the KWSP mobile app's "Semakan Baki Simpanan" balance screen (TD-411, MODEL_VERSION 1.17.0).

Before 1.17.0 the EPF slot knew only the printed Penyata Ahli, so a real screenshot of the app (doc 1395:
the balance, the month-by-month contribution table, the "Kembali" and "Dapatkan Penyata" buttons, the
KWSP logo) matched three generic probes — p=0.15 — and read `not_epf`, as if it were the wrong document.

⚠ ONLY WITH AN APP ANCHOR. The list competes in `results_doc.score_signatures` (doc_type 'epf') ONLY when
the text carries one of the app's own marks, `APP_ANCHORS` — the screen title or the "Dapatkan Penyata"
button. Without one, EPF scoring is exactly the old Penyata-only result, so a cropped Penyata is never
relabelled `epf_app` and no other paperwork (a bank or Tabung Haji "Baki Simpanan", a payslip's KWSP
lines) can climb out of `not_epf` through this list. With an anchor, best fit wins and names the type
(`epf` / `epf_app`); a tie keeps `epf`, the first key.

Probes are matched as WHOLE WORDS on the normalised text (" KEMBALI " never hits "dikembalikan" or
"pengembalian"). The table's column names are shared with the printed statement and a payslip, so they
weigh 1; the anchors and "Baki Simpanan" carry the weight.

⚠ AT MOST SUSPECT. A screenshot is easy to fake and is not the issued statement, so this family never
reads `genuine` however complete the screen: `screen_at_most_suspect` lowers it to `suspect` — the right
kind of proof, for the officer to confirm by eye.

Known gap: `epf_app` is NOT in `results_doc._MISFILE_FAMILIES`, so an app screenshot in another slot (a
salary slip's) is not flagged as a misfiled EPF. Pure + deterministic; no Django.
"""

#: (label, [probes already in normalised form — upper case, single spaces], weight).
EPF_APP_SIGNATURES = [
    ('KWSP / EPF',            ['KWSP', 'KUMPULAN WANG SIMPANAN PEKERJA'], 1),
    ('SEMAKAN BAKI SIMPANAN', ['SEMAKAN BAKI SIMPANAN'],                  3),
    ('BAKI SIMPANAN',         ['BAKI SIMPANAN'],                          2),
    ('Bulan Caruman',         ['BULAN CARUMAN'],                          2),
    ('Caruman Majikan',       ['CARUMAN MAJIKAN'],                        1),
    ('Caruman Ahli',          ['CARUMAN AHLI'],                           1),
    ('Caruman - IWS',         ['CARUMAN IWS'],                            1),
    ('DAPATKAN PENYATA',      ['DAPATKAN PENYATA'],                       3),
    ('Kembali',               ['KEMBALI'],                                1),
]

#: The app's own marks; without one of them the list does not compete at all.
APP_ANCHORS = ('SEMAKAN BAKI SIMPANAN', 'DAPATKAN PENYATA')

#: Families that are a SCREENSHOT of an app, never the issued document: their best band is suspect.
SCREEN_ONLY = frozenset({'epf_app'})


def _has_word(probe: str, padded: str) -> bool:
    return f' {probe} ' in padded


def score_app_screen(text_norm: str) -> dict:
    """Whole-word score of normalised text against `EPF_APP_SIGNATURES`, in `results_doc._score_list`'s shape."""
    padded = f' {text_norm} '
    present, missing, got, total = [], [], 0, 0
    for label, probes, weight in EPF_APP_SIGNATURES:
        total += weight
        hit = any(_has_word(p, padded) for p in probes)
        (present if hit else missing).append(label)
        got += weight if hit else 0
    return {'weight_got': got, 'weight_total': total, 'probability': round(got / total, 3),
            'present': present, 'missing': missing}


def epf_app_scores(text_norm: str) -> dict:
    """``{'epf_app': score}`` when the normalised text carries an app anchor, else ``{}`` (no competitor)."""
    padded = f' {text_norm} '
    if not any(_has_word(a, padded) for a in APP_ANCHORS):
        return {}
    return {'epf_app': score_app_screen(text_norm)}


def screen_at_most_suspect(family: str, status: str, reason: str):
    """``(status, reason)`` with a `SCREEN_ONLY` family's `genuine` lowered to `suspect` (and the reason
    saying why); every other family and band is returned unchanged."""
    if family in SCREEN_ONLY and status == 'genuine':
        return 'suspect', f'an app screenshot, not the printed statement — {reason}'
    return status, reason
