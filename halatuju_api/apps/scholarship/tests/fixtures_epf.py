"""SYNTHETIC KWSP "Penyata Ahli" OCR texts, laid out exactly as real OCR prints them.

⚠ COMMITTED DATA, SO NOTHING REAL. The layouts (cell order, labels, the `Ogs-25` month spelling,
"Tiada Transaksi", thousand separators, a statement cut off above its table) were copied from the
real corpus in `eval/snapshots/` — which is GITIGNORED because it is PII, and therefore ABSENT from
the deploy gate's build. Every name, address, member number, NRIC, employer number and amount here
is INVENTED. The real-corpus measurement is a hand-run script, `eval/epf_table_check.py`, never a
test (docs/lessons.md, 2026-10-01).

Real OCR prints the CARUMAN SEMASA table ONE CELL PER LINE, in one of two orders:

  * ``block``       — every month label first (`Jan-26` / `Caruman IWS` …), then the column
                      headers, then per row a date and three figures (Majikan, Ahli, Jumlah),
                      then the table's grand total;
  * ``interleaved`` — the headers first, then per row its month label, its transaction text, its
                      date and its three figures, then `JUMLAH (RM)` and the grand total.
"""

_HEAD = """KWSP
EPF
SULIT DAN PERSENDIRIAN
{name}
NO 7 JALAN CONTOH 3/2
TAMAN CONTOH
47000 SUNGAI BULOH
Selangor
PENYATA AHLI TAHUN {year}
Tarikh Penyata
: {stmt_date}
No. Ahli KWSP
{member_no}
No. Kad Pengenalan
No. Majikan
: {nric}
: {employer}
JUMLAH SIMPANAN: RM{balance}
RINGKASAN AKAUN
Jenis Akaun
Akaun Persaraan (Akaun 1)
Akaun Sejahtera (Akaun 2)
Akaun Fleksibel (Akaun 3)
Baki Pembuka
(RM)
Masuk
(RM)
JUMLAH (RM)
{balance}
"""

_CARUMAN_HEAD = """CARUMAN SEMASA
*Caruman semasa merujuk kepada transaksi caruman yang dikreditkan ke akaun ahli (Akaun Persaraan, Akaun Sejahtera dan Akaun Fleksibel) bagi
tahun {year} sahaja.
"""

_TAIL = """PENGELUARAN
*Melibatkan transaksi pengeluaran pada tahun {year} bagi Akaun Persaraan, Akaun Sejahtera dan Akaun Fleksibel.
Penyata ini adalah cetakan komputer dan tidak memerlukan tandatangan.
Cetakan myEPF
Muka Surat 1
"""


def _money(x):
    return f'{x:,.2f}'


def _head(**kw):
    return _HEAD.format(**kw) + _CARUMAN_HEAD.format(year=kw['year'])


def block_layout(rows, *, year='2026', **who):
    """``rows`` = [(month_label, txn, date, majikan, ahli)] in the BLOCK order."""
    out = [_head(year=year, **who), 'Bulan', 'Transaksi', 'Caruman']
    for month, txn, _date, _er, _ee in rows:
        out += [month, txn]
    out += ['JUMLAH (RM)', 'Caruman Majikan', 'Tarikh', '(RM)', 'Caruman Ahli', '(RM)',
            'Jumlah', '(RM)']
    for _month, _txn, date, er, ee in rows:
        out += [date, _money(er), _money(ee), _money(er + ee)]
    out.append(_money(sum(er + ee for *_x, er, ee in rows)))
    return '\n'.join(out) + '\n' + _TAIL.format(year=year)


def interleaved_layout(rows, *, year='2025', **who):
    """``rows`` = [(month_label, txn, date, majikan, ahli)] in the INTERLEAVED order."""
    out = [_head(year=year, **who), 'Bulan', 'Caruman Majikan', 'Transaksi', 'Tarikh', 'Caruman',
           '(RM)', 'Caruman Ahli', '(RM)', 'Jumlah', '(RM)']
    for month, txn, date, er, ee in rows:
        out += [month, txn, date, _money(er), _money(ee), _money(er + ee)]
    out += ['JUMLAH (RM)', _money(sum(er + ee for *_x, er, ee in rows))]
    return '\n'.join(out) + '\n' + _TAIL.format(year=year)


_WHO_A = dict(name='MEENA A/P TESTRAJ', member_no='90000017', nric='850505105050',
              employer='000123456', stmt_date='31/05/2026', balance='31,250.40')
_WHO_B = dict(name='KUMARAN A/L CONTOHAN', member_no='90000025', nric='780808085858',
              employer='000654321', stmt_date='31/12/2025', balance='182,004.15')
_WHO_C = dict(name='SITI BINTI SAMPEL', member_no='90000033', nric='900909095959',
              employer='000777888', stmt_date='30/06/2026', balance='64,880.00')

#: BLOCK order, five equal months. Majikan 230.00 + Ahli 195.00 = 425.00 each, so the totals are
#: 5 x 230 = 1,150.00 and 5 x 195 = 975.00, and the grand total 2,125.00 (a thousand separator).
FLAT_FIVE_ROWS = [(f'{m}-26', 'Caruman IWS' if i % 2 == 0 else 'Caruman - IWS',
                   f'1{i + 4}/{i + 1:02d}/2026', 230.00, 195.00)
                  for i, m in enumerate(['Jan', 'Feb', 'Mac', 'Apr', 'Mei'])]
FLAT_FIVE = block_layout(FLAT_FIVE_ROWS, **_WHO_A)

#: INTERLEAVED order, twelve months of 2025 — with the `Ogs-25` spelling real OCR prints for August
#: and four-figure amounts with thousand separators (1,310.00 + 1,201.00 = 2,511.00).
YEAR_TWELVE_ROWS = [
    ('Jan-25', 'Caruman IWS', '16/01/2025', 1310.00, 1201.00),
    ('Feb-25', 'Caruman IWS', '17/02/2025', 1088.00, 997.00),
    ('Mac-25', 'Caruman IWS', '17/03/2025', 744.00, 682.00),
    ('Apr-25', 'Caruman IWS', '17/04/2025', 744.00, 682.00),
    ('Mei-25', 'Caruman - IWS', '16/05/2025', 756.00, 693.00),
    ('Jun-25', 'Caruman - IWS', '16/06/2025', 756.00, 693.00),
    ('Jul-25', 'Caruman IWS', '15/07/2025', 756.00, 693.00),
    ('Ogs-25', 'Caruman IWS', '16/08/2025', 756.00, 693.00),
    ('Sep-25', 'Caruman IWS', '17/09/2025', 756.00, 693.00),
    ('Okt-25', 'Caruman', '10/10/2025', 756.00, 693.00),
    ('Nov-25', 'Caruman', '15/11/2025', 756.00, 693.00),
    ('Dis-25', 'Caruman', '17/12/2025', 756.00, 693.00),
]
YEAR_TWELVE = interleaved_layout(YEAR_TWELVE_ROWS, **_WHO_B)

#: BLOCK order, six months that VARY (a salary that moves month to month), some over RM1,000.
VARYING_SIX_ROWS = [
    ('Jan-26', 'Caruman', '09/01/2026', 1288.00, 1181.00),
    ('Feb-26', 'Caruman', '06/02/2026', 652.00, 598.00),
    ('Mac-26', 'Caruman', '12/03/2026', 830.00, 611.00),
    ('Apr-26', 'Caruman', '01/04/2026', 1305.00, 964.00),
    ('Mei-26', 'Caruman', '09/05/2026', 978.00, 721.00),
    ('Jun-26', 'Caruman', '01/06/2026', 784.00, 620.00),
]
VARYING_SIX = block_layout(VARYING_SIX_ROWS, **_WHO_C)

#: A Penyata with NO contributions this year — read as a genuine zero, never as a split.
TIADA = (_head(year='2026', **_WHO_A) + '- Tiada Transaksi\n' + _TAIL.format(year='2026'))

#: A Penyata cut off ABOVE its table (only the first lines photographed): recognised, but the
#: contribution table is not there to read → 'unknown' (TD-319's case).
TRUNCATED = _HEAD.format(**_WHO_B, year='2026').split('JUMLAH SIMPANAN')[0] + \
    'JUMLAH SIMPANAN: RM12,000.00\n'

#: name -> (text, the months a WHOLE table read gives, Σ Majikan, Σ Ahli), the last three None
#: where the statement has no table to split.
SYNTHETIC = {
    'flat_five': (FLAT_FIVE, 5, 'RM1150.00', 'RM975.00'),
    'year_twelve': (YEAR_TWELVE, 12, f'RM{sum(r[3] for r in YEAR_TWELVE_ROWS):.2f}',
                    f'RM{sum(r[4] for r in YEAR_TWELVE_ROWS):.2f}'),
    'varying_six': (VARYING_SIX, 6, f'RM{sum(r[3] for r in VARYING_SIX_ROWS):.2f}',
                    f'RM{sum(r[4] for r in VARYING_SIX_ROWS):.2f}'),
    'tiada': (TIADA, None, None, None),
    'truncated': (TRUNCATED, None, None, None),
}
