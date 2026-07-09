"""Salary-slip genuineness — the deterministic signature scorer.

Design + calibration: docs/scholarship/salary-signature-model.md (validated on 99 live slips,
2026-07-09). Unlike the single-issuer STR/EPF/results families in results_doc.py, a salary slip
has NO shared letterhead — thousands of employer/payroll formats. The fingerprint is therefore
**statutory payroll grammar**, not issuer identity:

  private  → the statutory-deduction scaffold (KWSP/EPF · PERKESO/SOCSO · EIS/SIP · PCB), ≥2 present
  govt     → the JANM/e-Penyata Gaji issuer + GRED (civil service; pension, NOT EPF)
  singapore→ CPF / Pte Ltd (converted SGD→MYR downstream)
  gig      → a platform brand (Grab/…); treated as declared-income evidence, not a formal payslip
  informal → wage labels but NO statutory scaffold → recognisably a payslip attempt, but weakly
             verifiable → SUSPECT (low ceiling by design; corroborate via the IC/EPF chain, never
             auto-reject — a genuinely poor family often has only an informal slip)
  not_salary → no payslip fields at all, or a MyKad in the slot (the #47 class) → reject

Returns the canonical soft vocabulary ('genuine' / 'suspect' / 'not_salary') shared with every
other genuineness type (see bands.canonical_status). SOFT throughout — the reviewer/officer is the
authority; nothing here hard-blocks on its own. Pure + deterministic given the OCR text.

BUMP MODEL_VERSION on ANY change to the marker groups, weights, or the decision cascade (same
discipline as results_doc.MODEL_VERSION) — it is persisted on the document and gates re-scoring.
"""
from .results_doc import _norm

# Version of the salary signature model. History:
#   1.0.0 (2026-07-09) — initial statutory-grammar cascade; six families.
MODEL_VERSION = '1.0.0'

# ── Marker groups (normalised substring probes; matched via _norm) ───────────────────────────
# Statutory scaffold — the private-payslip discriminator. Each GROUP counts once.
_STATUTORY = {
    'KWSP/EPF':      ['KWSP', 'KUMPULAN WANG SIMPANAN', 'EPF'],
    'PERKESO/SOCSO': ['PERKESO', 'SOCSO'],
    'EIS/SIP':       ['EIS', 'INSURANS PEKERJAAN'],   # bare 'SIP' too noisy (gossip/…); 'EIS' is safe
    'PCB/tax':       ['PCB', 'CUKAI BULANAN', 'LHDN'],
}
# Wage-label grammar — "is this a payslip at all?". Each GROUP counts once.
_WAGE_LABELS = [
    ['SLIP GAJI', 'PENYATA GAJI', 'PAYSLIP', 'PAY SLIP', 'SALARY SLIP', 'PAY ADVICE'],
    ['GAJI POKOK', 'BASIC SALARY', 'BASIC PAY'],
    ['PENDAPATAN', 'EARNING', 'INCOME'],
    ['POTONGAN', 'DEDUCTION'],
    ['GAJI BERSIH', 'NET PAY', 'NET SALARY', 'PENDAPATAN BERSIH'],
    ['JUMLAH PENDAPATAN', 'GROSS', 'JUMLAH GAJI'],
    ['ELAUN', 'ALLOWANCE'],
]
# Family discriminators. The govt e-Penyata Gaji is issued by JANM for MANY departments, so the
# EMPLOYER name varies — the durable fingerprint is the TITLE + issuer: a genuine private slip says
# "Slip Gaji" / "Payslip", the civil-service one says "PENYATA GAJI" (10/10 in the corpus; 'Gred'
# turned out to be an unreliable OCR marker, only 1/99). Civil servants are on pension (KWAP), NOT
# EPF, so a govt slip legitimately has 0 statutory scaffold — it must be caught here (after the
# private branch) or it wrongly falls to 'informal'.
_GOVT_FORMAT = ['PENYATA GAJI', 'PERKHIDMATAN AWAM', 'AKAUNTAN NEGARA', 'JANM', 'KUMPULAN PERKHIDMATAN']
_SINGAPORE = ['CPF', 'PTE LTD', 'PRIVATE LIMITED']
_GIG = ['GRAB', 'FOODPANDA', 'LALAMOVE', 'MAXIM', 'SHOPEEFOOD', 'PANDA']
# MyKad-distinctive markers that do NOT appear on a genuine payslip (NB: 'KAD PENGENALAN' is a
# legitimate NRIC label on many payslips, so it is NOT a reject marker — 'WARGANEGARA' is).
_MYKAD = ['WARGANEGARA', 'PENGARAH PENDAFTARAN', 'PENDAFTARAN NEGARA']


def _any(tokens, tn):
    return any(_norm(t) in tn for t in tokens)


def _count_groups(groups, tn):
    return sum(1 for g in groups for _ in [0] if _any(g, tn))


def score_family(ocr_text: str) -> dict:
    """The raw marker tallies for OCR text (transparent, for tests + calibration):
    ``{statutory, wage, govt, singapore, gig, mykad}``. Pure."""
    tn = _norm(ocr_text)
    return {
        'statutory': sum(1 for g in _STATUTORY.values() if _any(g, tn)),
        'wage': sum(1 for g in _WAGE_LABELS if _any(g, tn)),
        'govt': _any(_GOVT_FORMAT, tn),
        'singapore': _any(_SINGAPORE, tn),
        'gig': _any(_GIG, tn),
        'mykad': _any(_MYKAD, tn),
    }


def salary_genuineness(ocr_text: str) -> dict:
    """Soft genuineness signal for a salary slip → ``{status, family, probability, reason,
    model_version}``. ``status`` ∈ {'genuine', 'suspect', 'not_salary'} (the canonical cap
    vocabulary); ``family`` names the recognised kind for the verdict/officer layer
    (private/govt/singapore/gig/informal/not_salary). Pure + deterministic; never raises."""
    m = score_family(ocr_text)
    stat, wage = m['statutory'], m['wage']

    def out(status, family, prob, reason):
        return {'status': status, 'family': family, 'probability': round(prob, 3),
                'reason': reason[:300], 'model_version': MODEL_VERSION,
                'markers': {'statutory': stat, 'wage': wage}}

    # Reject: a MyKad in the slot (the #47 class), or nothing that reads like a payslip at all.
    if m['mykad'] and wage == 0:
        return out('not_salary', 'not_salary', 0.05, 'MyKad markers, no payslip fields — not a salary slip')
    if wage == 0:
        return out('not_salary', 'not_salary', 0.10,
                   'no recognisable payslip fields (wage/deduction labels absent)')

    # Genuine families, in discriminator-strength order.
    if stat >= 2:
        return out('genuine', 'private', min(0.95, 0.60 + 0.10 * stat + 0.03 * wage),
                   f'{stat} statutory markers (KWSP/SOCSO/EIS/PCB) + {wage} wage labels — private payslip')
    if m['govt']:
        return out('genuine', 'govt', min(0.90, 0.70 + 0.03 * wage),
                   'JANM/civil-service e-Penyata Gaji (issuer + GRED)')
    if m['singapore']:
        return out('genuine', 'singapore', min(0.90, 0.68 + 0.03 * wage),
                   'Singapore payslip (CPF / Pte Ltd) — convert SGD→MYR')
    if m['gig']:
        return out('genuine', 'gig', 0.70,
                   'gig-platform earnings statement — treat as declared income')

    # Wage labels present but no statutory scaffold / issuer → informal. Low ceiling, never rejected.
    return out('suspect', 'informal', 0.50,
               f'{wage} wage labels but no statutory scaffold — informal slip, verify via the '
               'IC/EPF chain + amount')
