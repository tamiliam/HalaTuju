"""Electricity-bill genuineness — the deterministic signature scorer.

Design + calibration: docs/scholarship/electricity-bill-catalogue.md (validated on 27 live OCR'd
bills, 2026-07-10). Unlike the multi-format salary slip (salary_doc.py), an electricity bill has a
DOMINANT ISSUER — TNB in Peninsular Malaysia (SESB Sabah / SESCO Sarawak are the East-Malaysia
siblings, absent from the current cohort but scored for future-proofing). The fingerprint is
therefore **issuer identity + the standard Malay bill-field grammar**, closer to the single-issuer
STR/EPF families than to salary:

  tnb / sesb / sesco → a recognised issuer + bill-field labels → genuine
  unrecognised       → electricity-bill grammar (ELEKTRIK/kWj + fields) but no known issuer header
                       (e.g. a cropped photo that lost the letterhead) → genuine if the grammar is
                       strong, else suspect
  not_electricity_bill → a MyKad in the slot (the #47 class, mirrors salary), a WATER bill misfiled
                       into the electricity slot, or nothing bill-shaped at all → reject

Calibration (n=27, real OCR): NO AKAUN 100% · TNB/ELEKTRIK 92% · CAJ SEMASA / SILA BAYAR SEBELUM 92%
· TARIKH BIL 88% · KEGUNAAN/kWj 88% · TARIF 85% · TEMPOH BIL 85%. Distribution: 25 issuer+≥3-labels
(genuine) · 2 thin TNB app screenshots (issuer, 0 labels → suspect, not rejected) · 0 without an
issuer marker. So an issuer marker guarantees the doc is never rejected — a genuine bill can only be
'genuine' or 'suspect', never 'not_electricity_bill'. Conservative by design (mirrors salary): a
thin/cropped read lands in 'suspect' (officer confirms), never a false 'genuine' or a false reject.

Returns the canonical soft vocabulary ('genuine' / 'suspect' / 'not_electricity_bill') shared with
every other genuineness type (bands.canonical_status). SOFT throughout — the reviewer/officer is the
authority; nothing here hard-blocks. Pure + deterministic given the OCR text.

BUMP MODEL_VERSION on ANY change to the marker groups, thresholds, or the decision cascade (same
discipline as results_doc.MODEL_VERSION / salary_doc.MODEL_VERSION) — it is persisted on the document
and gates re-scoring.
"""
from .results_doc import _norm

# Version of the electricity-bill signature model. History:
#   1.0.0 (2026-07-10) — initial issuer-identity + bill-grammar cascade; tnb/sesb/sesco/unrecognised.
MODEL_VERSION = '1.0.0'

# ── Marker groups (normalised substring probes; matched via _norm) ───────────────────────────
# Issuer identity — the dominant discriminator (TNB is a near-monopoly in the corpus).
_TNB = ['TENAGA NASIONAL', 'TNB', 'BIL ELEKTRIK']            # 'Bil Elektrik Anda' header
_SESB = ['SABAH ELECTRICITY', 'SESB']                        # East Malaysia — Sabah
_SESCO = ['SARAWAK ENERGY', 'SESCO', 'SYARIKAT SESCO']       # East Malaysia — Sarawak
# Bill-field grammar — "is this an electricity bill at all?". Each GROUP counts once (hit-rate n=27).
_BILL_LABELS = [
    ['NO AKAUN', 'NOMBOR AKAUN', 'ACCOUNT NO', 'ACCOUNT NUMBER'],       # 100%
    ['CAJ SEMASA', 'CURRENT CHARGE'],                                   # 92%
    ['SILA BAYAR SEBELUM', 'BAYAR SEBELUM', 'DUE DATE'],                # 92%
    ['TARIKH BIL', 'BILL DATE'],                                        # 88% (Tarikh Bil — bill date)
    ['KEGUNAAN', 'KWJ', 'KWH', 'PENGGUNAAN'],                           # 88% (usage)
    ['BACAAN METER', 'BACAAN SEBENAR', 'METER READING', 'JENIS BACAAN'],  # 88%
    ['BAKI TERDAHULU', 'TUNGGAKAN', 'PREVIOUS BALANCE', 'ARREARS'],     # 88% (arrears)
    ['TARIF', 'TARIFF'],                                                # 85% (tariff / premise class)
    ['TEMPOH BIL', 'BILLING PERIOD'],                                   # 85% (period)
    ['JUMLAH PERLU DIBAYAR', 'JUMLAH PERLU', 'TOTAL AMOUNT', 'AMOUNT PAYABLE', 'AMOUNT DUE'],  # 62%
]
# Electricity-specific terms — separate a genuine bill from a WATER bill (the wrong-type backstop)
# and rescue a cropped photo that lost the TNB header (ELEKTRIK/TENAGA 92%, kWj/kWh the meter unit).
_ELECTRICITY_TERM = ['ELEKTRIK', 'ELECTRICITY', 'TENAGA', 'KWJ', 'KWH', 'KILOWATT']
# Water-utility markers — a water bill dropped into the electricity slot. Only rejects when NO
# electricity/issuer marker is present (a genuine TNB bill with an incidental 'AIR' token is safe).
_WATER_TERM = ['BEKALAN AIR', 'AIR SELANGOR', 'BIL AIR', 'METER AIR', 'PBAPP', 'SYABAS', 'LAKU AIR',
               'AIR KELANTAN', 'AIR JOHOR']
# MyKad-distinctive markers that never appear on a genuine bill (mirrors salary's #47 reject).
_MYKAD = ['WARGANEGARA', 'PENGARAH PENDAFTARAN', 'PENDAFTARAN NEGARA']


def _any(tokens, tn):
    return any(_norm(t) in tn for t in tokens)


def score_markers(ocr_text: str) -> dict:
    """The raw marker tallies for OCR text (transparent, for tests + calibration):
    ``{issuer, labels, electricity, water, mykad}``. ``issuer`` names the recognised utility or ''.
    Pure."""
    tn = _norm(ocr_text)
    issuer = ('tnb' if _any(_TNB, tn) else 'sesb' if _any(_SESB, tn)
              else 'sesco' if _any(_SESCO, tn) else '')
    return {
        'issuer': issuer,
        'labels': sum(1 for g in _BILL_LABELS if _any(g, tn)),
        'electricity': _any(_ELECTRICITY_TERM, tn),
        'water': _any(_WATER_TERM, tn),
        'mykad': _any(_MYKAD, tn),
    }


def electricity_genuineness(ocr_text: str) -> dict:
    """Soft genuineness signal for an electricity bill → ``{status, family, probability, reason,
    model_version, markers}``. ``status`` ∈ {'genuine', 'suspect', 'not_electricity_bill'} (the
    canonical cap vocabulary); ``family`` names the recognised kind (tnb/sesb/sesco/unrecognised/
    not_electricity_bill). Pure + deterministic; never raises."""
    m = score_markers(ocr_text)
    issuer, labels = m['issuer'], m['labels']

    def out(status, family, prob, reason):
        return {'status': status, 'family': family, 'probability': round(prob, 3),
                'reason': reason[:300], 'model_version': MODEL_VERSION,
                'markers': {'issuer': issuer or 'none', 'labels': labels}}

    # ── Reject floor (not_electricity_bill) — only when NO issuer marker anchors it ──────────────
    # A recognised issuer (TNB/SESB/SESCO) guarantees the doc is at worst 'suspect', never rejected
    # (corpus: every genuine bill carried one). So the reject branches are gated on `not issuer`.
    if not issuer:
        if m['mykad'] and labels == 0:
            return out('not_electricity_bill', 'not_electricity_bill', 0.05,
                       'MyKad markers, no bill fields — not an electricity bill')
        if m['water'] and not m['electricity']:
            return out('not_electricity_bill', 'water_bill', 0.10,
                       'water-utility markers (not electricity) — wrong bill type in the slot')
        if labels < 2 and not m['electricity']:
            return out('not_electricity_bill', 'not_electricity_bill', 0.12,
                       'no issuer, no electricity terms, no bill fields — not an electricity bill')

    # ── Genuine / suspect ───────────────────────────────────────────────────────────────────────
    if issuer:
        if labels >= 2:
            return out('genuine', issuer, min(0.95, 0.62 + 0.06 * labels),
                       f'{issuer.upper()} issuer + {labels} bill-field labels — genuine electricity bill')
        # Issuer present but thin (a cropped myTNB app screenshot: header + amount, no field grammar)
        # → soft suspect, officer confirms. NOT rejected — it is a real bill, just weakly verifiable.
        return out('suspect', issuer, 0.55,
                   f'{issuer.upper()} issuer but only {labels} bill-field labels — thin read, confirm')

    # No recognised issuer, but electricity grammar (a cropped photo that lost the letterhead).
    if m['electricity'] and labels >= 3:
        return out('genuine', 'unrecognised', 0.72,
                   f'electricity-bill grammar ({labels} labels + kWj/ELEKTRIK) without a known issuer '
                   'header — genuine (likely a cropped bill)')
    # Utility-shaped but weak / unconfirmed electricity → suspect (never a false genuine).
    return out('suspect', 'unrecognised', 0.45,
               f'{labels} bill-field labels but no recognised issuer/electricity signature — confirm')
