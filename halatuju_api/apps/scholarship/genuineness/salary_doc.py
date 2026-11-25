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
import re

from .declaration_doc import declaration_genuineness, is_declaration_text
from .results_doc import _any_token, _norm_fold_upper_alnum

# Version of the salary signature model. History:
#   1.0.0 (2026-07-09) — initial statutory-grammar cascade; six families.
#   1.1.0 (2026-07-14) — record `kwsp` separately in markers: the slip's own KWSP line drives
#                        whether an EPF statement is worth asking for (owner). Bands unchanged.
#   1.2.0 (2026-10-27) — #374 / income declarations (owner ruling): an income DECLARATION form is
#                        recognised first (`declaration_doc`, family 'declaration', `suspect`), and 'govt'
#                        needs a real government-payslip or PENSION-statement marker — 'KUMPULAN
#                        PERKHIDMATAN' / a bare 'PERKHIDMATAN AWAM' (a form's sector field) no longer make
#                        a civil-service slip; JPA / KWAP / "Penyata Bayaran"+"Pencen" keep pensions govt.
#   1.3.0 (2026-11-24) — #85: ≥2 statutory deductions are a private payslip even with NO wage label (the
#                        2026-07-09 rule); the MyKad reject still runs first. On that no-wage path (only) the
#                        deductions must be WHOLE words (`_STATUTORY_WORDS`: 'EIS' in LEISURE or a tax form's
#                        LHDN do not count); slips with a wage label are counted exactly as in 1.2.0. Stored
#                        not_salary rows re-score via `rescore_salary_statutory` (from stored OCR text), no read.
#                        Review round 2 (same unreleased version): letter edges, so a label glued to its
#                        amount counts (KWSP308.00), known suffixes (KWSPPEKERJA, SOCSOEE); 'MTD' is PCB.
MODEL_VERSION = '1.3.0'

# ── Marker groups (normalised substring probes; matched via _norm_fold_upper_alnum) ──────────
# Statutory scaffold — the private-payslip discriminator. Each GROUP counts once.
_STATUTORY = {
    'KWSP/EPF':      ['KWSP', 'KUMPULAN WANG SIMPANAN', 'EPF'],
    'PERKESO/SOCSO': ['PERKESO', 'SOCSO'],
    'EIS/SIP':       ['EIS', 'INSURANS PEKERJAAN'],   # bare 'SIP' too noisy (gossip/…); 'EIS' is safe
    'PCB/tax':       ['PCB', 'CUKAI BULANAN', 'LHDN'],
}
#: 1.3.0 (#85): the statutory groups as WHOLE words / phrases, read ONLY when no wage label was read —
#: there the deductions alone make the payslip, so a substring ('EIS' inside LEISURE / REISSUE, 'EPF' inside
#: a longer token) must not. 'LHDN' is left out here: it names the tax office, which every tax form and tax
#: letter prints (a BE form beside a KWSP relief line is not a payslip); the monthly deduction is PCB /
#: CUKAI BULANAN. The substring groups above still count for a slip WITH wage labels, unchanged.
#: Review round 2: 'MTD' (monthly tax deduction, the English label for PCB) counts here too — on this
#: no-wage path only; the substring groups above are left as in 1.2.0.
_STATUTORY_WORDS = {
    'KWSP/EPF':      ['KWSP', 'KUMPULAN WANG SIMPANAN', 'EPF'],
    'PERKESO/SOCSO': ['PERKESO', 'SOCSO'],
    'EIS/SIP':       ['EIS', 'INSURANS PEKERJAAN'],
    'PCB/tax':       ['PCB', 'CUKAI BULANAN', 'MTD'],
}
#: Review round 2: the word edge is a LETTER edge, so a label glued to its amount still counts (PDF text
#: layers print 'KWSP308.00', 'EIS5.10'); a letter on either side does not ('EIS' in LEISURE / REISSUE).
#: Deliberate exception: a single-word label may carry ONE of these employee / employer suffixes glued on
#: its right ('KWSPPEKERJA', 'SOCSOEE', 'EPFER') — payroll column heads, never English words. A letter
#: glued on the LEFT ('AKAUNKWSP') still does not count. Phrases keep a space between their words.
_WORD_SUFFIXES = ('PEKERJA', 'MAJIKAN', 'EMPLOYEE', 'EMPLOYER', 'EE', 'ER')


def _word_pattern(token):
    words = _norm_fold_upper_alnum(token).split()
    body = r'\s+'.join(re.escape(w) for w in words)
    if len(words) == 1:
        body += '(?:' + '|'.join(_WORD_SUFFIXES) + ')?'
    return f'(?<![A-Z]){body}(?![A-Z])'


_STATUTORY_WORD_RE = {g: re.compile('|'.join(_word_pattern(t) for t in toks))
                      for g, toks in _STATUTORY_WORDS.items()}
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
#: 1.2.0 (#374): ONLY markers a government payslip / pension statement prints and an income form does not:
#:   * the salary issuer (Jabatan Akauntan Negara / JANM, a whole word), the slip title (Penyata Gaji /
#:     e-Penyata) or a GRED CODE ("GRED N19", "Gred DG41");
#:   * a PENSION STATEMENT — its layout, never a single word (review round 2: a self-written statement can say
#:     "Jabatan Perkhidmatan Awam" in an occupation line, or "pencen KWAP"): a pension ISSUER word (the full
#:     department name JABATAN PERKHIDMATAN AWAM, the fund KWAP as a whole word, or PENCEN) TOGETHER WITH a
#:     STATEMENT marker (PENYATA BAYARAN, NO AKAUN PENCEN, jpa.gov.my). JPA's "Penyata Bayaran bagi Tahun …"
#:     for a Pencen Bulanan and PERKESO's "Penyata Bayaran Faedah" (Pencen Penakat) are computer-printed and
#:     never stamped, so they must stay a formal family, not informal (review of d0d5d079, eval a54).
#: 'KUMPULAN PERKHIDMATAN' / a bare 'PERKHIDMATAN AWAM' stay OUT: they are the SECTOR field of every income
#: form ("Kerajaan / Swasta / Tentera / Polis"), which is what made #374's declaration read civil-service.
_GOVT_FORMAT = ['PENYATA GAJI', 'E PENYATA', 'AKAUNTAN NEGARA']
_GOVT_WORD = re.compile(r'\b(JANM|GRED [A-Z]{1,3} ?\d{1,2})\b')
_PENSION_ISSUER = re.compile(r'\b(JABATAN PERKHIDMATAN AWAM|KWAP|PENCEN)\b')
_PENSION_STATEMENT = ('PENYATA BAYARAN', 'NO AKAUN PENCEN', 'JPA GOV MY')
_SINGAPORE = ['CPF', 'PTE LTD', 'PRIVATE LIMITED']
_GIG = ['GRAB', 'FOODPANDA', 'LALAMOVE', 'MAXIM', 'SHOPEEFOOD', 'PANDA']
# MyKad-distinctive markers that do NOT appear on a genuine payslip (NB: 'KAD PENGENALAN' is a
# legitimate NRIC label on many payslips, so it is NOT a reject marker — 'WARGANEGARA' is).
_MYKAD = ['WARGANEGARA', 'PENGARAH PENDAFTARAN', 'PENDAFTARAN NEGARA']


def _any_word(group, tn):
    """True when a label of statutory `group` (a `_STATUTORY_WORDS` key) appears in the normalised text
    `tn` as a whole word / phrase: letter edges, digits may touch it, known suffixes allowed (above)."""
    return bool(_STATUTORY_WORD_RE[group].search(tn))


def _count_groups(groups, tn):
    return sum(1 for g in groups for _ in [0] if _any_token(g, tn))


def score_family(ocr_text: str) -> dict:
    """The raw marker tallies for OCR text (transparent, for tests + calibration):
    ``{statutory, statutory_words, kwsp, wage, govt, singapore, gig, mykad}``. Pure.

    ``statutory_words`` (1.3.0, #85) counts the statutory groups as whole words, without LHDN; only the
    no-wage branch of `decide` reads it. It is not stored in the result's markers.

    ``kwsp`` is recorded SEPARATELY from the statutory count (owner, 2026-07-14): the payslip
    itself tells us whether an EPF statement can even exist. A slip with a KWSP deduction line means
    the earner contributes — ask for the statement. A slip we have READ that shows no KWSP line
    means he doesn't — asking would be another dead end. The count alone couldn't distinguish a
    KWSP line from a SOCSO one.
    """
    tn = _norm_fold_upper_alnum(ocr_text)
    return {
        'statutory': sum(1 for g in _STATUTORY.values() if _any_token(g, tn)),
        'statutory_words': sum(1 for g in _STATUTORY_WORDS if _any_word(g, tn)),
        'kwsp': _any_token(_STATUTORY['KWSP/EPF'], tn),
        'wage': sum(1 for g in _WAGE_LABELS if _any_token(g, tn)),
        'govt': (_any_token(_GOVT_FORMAT, tn) or bool(_GOVT_WORD.search(tn))
                 or (bool(_PENSION_ISSUER.search(tn)) and _any_token(_PENSION_STATEMENT, tn))),
        'singapore': _any_token(_SINGAPORE, tn),
        'gig': _any_token(_GIG, tn),
        'mykad': _any_token(_MYKAD, tn),
    }


def salary_genuineness(ocr_text: str) -> dict:
    """Soft genuineness signal for a salary slip → ``{status, family, probability, reason,
    model_version}``. ``status`` ∈ {'genuine', 'suspect', 'not_salary'} (the canonical cap
    vocabulary); ``family`` names the recognised kind for the verdict/officer layer
    (private/govt/singapore/gig/informal/not_salary). Pure + deterministic; never raises."""
    if is_declaration_text(ocr_text):     # 1.2.0 (#374): a declaration form is never a payslip family
        return declaration_genuineness(MODEL_VERSION)
    return decide(score_family(ocr_text))


def decide(m: dict) -> dict:
    """The decision cascade over the marker tallies of `score_family` (pure). Split out (#85) for the
    re-score command. NB the stored markers do NOT carry `statutory_words`, so stored markers alone can
    not reproduce the no-wage branch of a fresh read — the command re-scores from stored OCR text."""
    stat, wage = m['statutory'], m['wage']

    def out(status, family, prob, reason):
        return {'status': status, 'family': family, 'probability': round(prob, 3),
                'reason': reason[:300], 'model_version': MODEL_VERSION,
                'markers': {'statutory': stat, 'wage': wage, 'kwsp': m['kwsp']}}

    # Reject first: a MyKad in the slot (the #47 class) — it wins even over statutory words (a MyKad
    # photo beside a KWSP card is still an identity card, and the org was told it is still refused).
    if m['mykad'] and wage == 0:
        return out('not_salary', 'not_salary', 0.05, 'MyKad markers, no payslip fields — not a salary slip')

    # 1.3.0 (#85): with NO wage label read, ≥2 statutory deductions — as WHOLE words — ARE the private
    # payslip (the 2026-07-09 rule); otherwise nothing reads like a payslip. A slip with wage labels
    # takes the branches below exactly as in 1.2.0 (substring statutory count).
    if wage == 0:
        words = m['statutory_words']
        if words >= 2:
            return out('genuine', 'private', min(0.95, 0.60 + 0.10 * words),
                       f'{words} statutory deductions (KWSP/SOCSO/EIS/PCB, whole words) and no wage label '
                       '— private payslip')
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
