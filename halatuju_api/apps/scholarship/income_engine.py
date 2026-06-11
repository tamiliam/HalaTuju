"""Income verification — Check-1 item 3: earner identity + relationship.

Pure, deterministic helpers (no DB writes, no live calls) that the income verdict
(verdict_engine._verdict_income, Sprint I2) and the student wizard checklist
(Sprint I3) both consume, so they can never disagree.

The model: a guided wizard collects three answers on the application —
``income_route`` (str | salary), ``income_earner`` (father | mother | guardian),
``earner_work_status`` (payslip | informal | not_working). From those,
``income_requirements`` returns the documents the family must upload (compulsory)
plus credibility boosters (optional). Proving the earner is the student's family:

  - **father**  → the father's name is carried in the student's OWN IC patronymic
                  (``A/L`` / ``A/P`` / ``S/O`` / ``D/O`` / ``bin`` / ``binti``);
                  match it to the earner IC. No extra document.
  - **mother**  → a **Birth Certificate** (the patronymic names only the father):
                  its child-name must be the student and its mother-name the earner IC.
  - **guardian**→ a guardianship order/letter (presence; name match is a soft bonus).

Never blocks a genuinely poor family: a missing payslip/EPF for a non-working or
informal earner becomes an officer/interview judgement upstream, not a hard gate.
"""
from __future__ import annotations

import datetime
import re

# Every name comparison in this module is the SAME real person across TWO documents
# (relationships, earner-IC ↔ income-proof, STR-recipient ↔ IC, BC names) — never the student's
# own identity — so they all use the transliteration-tolerant matcher (#2, Sarawanan A/L case).
from .vision import relationship_name_match as name_match


# ── Father's name from the student's IC patronymic ───────────────────────────
# A Malaysian full name carries the FATHER's given name after the relationship
# connector: "DIVASHINI A/P MURUGAN" → father "MURUGAN"; "AHMAD BIN ALI" → "ALI".
_PATRONYMIC_RE = re.compile(
    r'\b(?:a\s*/\s*[lp]|s\s*/\s*o|d\s*/\s*o|bin|binti|anak\s+(?:lelaki|perempuan))\b',
    re.IGNORECASE,
)


def father_name_from_ic(student_name: str) -> str:
    """The father's name carried in the student's name (the part AFTER the
    patronymic connector). '' when there is no connector — e.g. a single given
    name or a Chinese-style name — so the caller knows it can't derive the father
    this way and must fall back to officer review rather than guess."""
    s = (student_name or '').strip()
    m = _PATRONYMIC_RE.search(s)
    if not m:
        return ''
    return s[m.end():].strip(' .,')


# ── Relationship checks (pure; statuses mirror the slip/offer checks) ─────────
# 'match' | 'mismatch' | 'unknown' (can't derive) | 'pending' (not yet read).

def father_relationship(student_name: str, earner_ic_name: str) -> str:
    """Does the earner IC belong to the student's father? The father's given name
    from the student IC must appear in the earner's full IC name. A subset match
    (the given name inside the earner's fuller name) COUNTS — only disjoint tokens
    are a real mismatch."""
    father = father_name_from_ic(student_name)
    if not father:
        return 'unknown'                       # no patronymic → officer reviews
    if not (earner_ic_name or '').strip():
        return 'pending'                       # earner IC not read yet
    return 'mismatch' if name_match(father, earner_ic_name) == 'mismatch' else 'match'


def mother_relationship(bc_child_name: str, bc_mother_name: str,
                        student_name: str, earner_ic_name: str) -> str:
    """The Birth Certificate ties the earner (mother) to the student: its child
    must be the student AND its mother must be the earner IC. Either side disjoint
    → mismatch; both agree → match; not enough read yet → pending."""
    if not (bc_child_name or '').strip() and not (bc_mother_name or '').strip():
        return 'pending'                       # BC not uploaded / not read
    child_ok = (name_match(bc_child_name, student_name) != 'mismatch'
                if bc_child_name and student_name else None)
    mother_ok = (name_match(bc_mother_name, earner_ic_name) != 'mismatch'
                 if bc_mother_name and earner_ic_name else None)
    if child_ok is False or mother_ok is False:
        return 'mismatch'
    if child_ok and mother_ok:
        return 'match'
    return 'pending'


def father_via_bc(bc_child_name: str, bc_father_name: str,
                  student_name: str, earner_ic_name: str) -> str:
    """Mononym fallback for the FATHER link: when the student's name carries no patronymic,
    father_relationship can't read the father off it (#55, DIVIYA) — so the Birth Certificate
    ties the earner (father) to the student instead: its child must be the student AND its
    FATHER must be the earner's IC. Mirrors mother_relationship (which uses the BC mother).
    Either side disjoint → mismatch; both agree → match; not enough read → pending."""
    if not (bc_child_name or '').strip() and not (bc_father_name or '').strip():
        return 'pending'
    child_ok = (name_match(bc_child_name, student_name) != 'mismatch'
                if bc_child_name and student_name else None)
    father_ok = (name_match(bc_father_name, earner_ic_name) != 'mismatch'
                 if bc_father_name and earner_ic_name else None)
    if child_ok is False or father_ok is False:
        return 'mismatch'
    if child_ok and father_ok:
        return 'match'
    return 'pending'


def father_link(student_name: str, earner_ic_name: str,
                bc_child_name: str = '', bc_father_name: str = '') -> str:
    """The father→student link: the shared patronymic, OR — when the student is a mononym so
    the patronymic can't apply — the Birth Certificate's child+father (#55). The patronymic
    result wins; only its 'unknown' (no patronymic) defers to the BC, and only if one was
    uploaded. So a normal applicant is unaffected; a mononym applicant who adds their BC gets
    a deterministic father verdict instead of a permanent 'officer reviews'."""
    r = father_relationship(student_name, earner_ic_name)
    if r == 'unknown' and (bc_child_name or bc_father_name):
        return father_via_bc(bc_child_name, bc_father_name, student_name, earner_ic_name)
    return r


def guardian_relationship(letter_name: str, earner_ic_name: str) -> str:
    """Soft name check between a guardianship letter and the earner IC. The hard
    requirement is the letter's PRESENCE (handled by income_requirements); a name
    that disagrees is a flag, agreement a bonus, missing text → pending."""
    if not (letter_name or '').strip():
        return 'pending'
    if not (earner_ic_name or '').strip():
        return 'pending'
    return 'mismatch' if name_match(letter_name, earner_ic_name) == 'mismatch' else 'match'


_RELATIONSHIP_DOC = {'mother': 'birth_certificate', 'guardian': 'guardianship_letter'}


def relationship_doc_for(earner: str) -> str:
    """The extra document a given earner needs to prove the relationship
    ('birth_certificate' / 'guardianship_letter'), or '' for a father/sibling (derived
    from the shared student-IC patronymic — siblings carry the same father's name)."""
    return _RELATIONSHIP_DOC.get(earner or '', '')


# ── Salary route: multiple working household members ──────────────────────────
# Each ticked member gets their own IC + salary slip + EPF (tagged on the document
# via household_member). The relationship to the student:
#   - father / brother / sister → the SAME father's name from the student's IC
#     patronymic (siblings carry it too) → father_relationship, no extra doc.
#   - mother  → birth certificate.
#   - guardian→ guardianship letter.
_MEMBER_ORDER = ('father', 'mother', 'guardian', 'brother', 'sister')
# father/brother/sister all verify the same way (patronymic); only mother/guardian need a doc.
_PATRONYMIC_MEMBERS = {'father', 'brother', 'sister'}


def working_members(application) -> list:
    """The ticked salary-route members, de-duped and in display order. Tolerant of a
    blank/None/garbage JSON value (returns [])."""
    raw = getattr(application, 'income_working_members', None) or []
    if not isinstance(raw, (list, tuple)):
        return []
    chosen = {m for m in raw if m in _MEMBER_ORDER}
    return [m for m in _MEMBER_ORDER if m in chosen]


def member_relationship_status(member: str, student_name: str, member_ic_name: str,
                               bc_child_name: str = '', bc_mother_name: str = '',
                               letter_name: str = '', bc_father_name: str = '') -> str:
    """The relationship verdict for one working member — routes to the right check.
    father → patronymic, with a Birth-Certificate fallback for a mononym student (#55);
    brother/sister → father_relationship (shared patronymic only); mother → birth cert;
    guardian → guardianship letter. 'match' | 'mismatch' | 'unknown' | 'pending'."""
    if member == 'father':
        return father_link(student_name, member_ic_name, bc_child_name, bc_father_name)
    if member in _PATRONYMIC_MEMBERS:            # brother / sister — patronymic only
        return father_relationship(student_name, member_ic_name)
    if member == 'mother':
        return mother_relationship(bc_child_name, bc_mother_name, student_name, member_ic_name)
    if member == 'guardian':
        return guardian_relationship(letter_name, member_ic_name)
    return 'unknown'


def _relationship_inputs(application, member, member_ic_name):
    """Pull the relationship-proof inputs for one member from the application's documents
    (birth cert for a mother — also the FATHER fields for the #55 mononym father fallback;
    guardianship letter for a guardian)."""
    bc_child = bc_mother = bc_father = letter_name = ''
    if member in ('mother', 'father', 'brother', 'sister'):
        bc = (application.documents.filter(doc_type='birth_certificate')
              .order_by('-uploaded_at').first())
        vf = (getattr(bc, 'vision_fields', None) if bc else None) or {}
        f = vf.get('fields', {}) if isinstance(vf, dict) else {}
        if isinstance(f, dict):
            bc_child = f.get('bc_child_name', '')
            bc_mother = f.get('bc_mother_name', '')
            bc_father = f.get('bc_father_name', '')
    elif member == 'guardian':
        g = (application.documents.filter(doc_type='guardianship_letter')
             .order_by('-uploaded_at').first())
        letter_name = (getattr(g, 'vision_name', '') or '') if g else ''
    return bc_child, bc_mother, bc_father, letter_name


def _cluster_proof_identity(application, member):
    """The income proof's recipient identity ``(kind, name, nric)`` that the earner IC must
    match — the whole point of uploading the IC. STR route → the STR (recipient_name/nric);
    salary route → the member's salary slip, then EPF (name/nric). ('', '', '') when no
    income proof is present yet to compare against."""
    route = (getattr(application, 'income_route', '') or '').strip()
    if route == 'str':
        p = application.documents.filter(doc_type='str').order_by('-uploaded_at').first()
        if p:
            f = _doc_fields(p)
            return 'str', (f.get('recipient_name', '') or '').strip(), (f.get('recipient_nric', '') or '').strip()
        return '', '', ''
    for dt in ('salary_slip', 'epf'):
        p = _cluster_docs(application, member, dt).first()
        if p:
            f = _doc_fields(p)
            return dt, (f.get('name', '') or '').strip(), (f.get('nric', '') or '').strip()
    return '', '', ''


def student_income_ic_check(doc):
    """For an income earner's IC (``parent_ic``): the OCR'd IC No / Name / Address, the
    RELATIONSHIP verdict (``name_status`` — does this earner link to the student's family,
    via patronymic / birth cert / letter), AND — the student-facing point — whether this IC
    MATCHES the cluster's income proof (the STR / salary slip it must belong to). The NRIC is
    the earner's, never matched to the student. Returns ``{nric, name, address, member,
    name_status, readable, proof_kind, proof_name_status, proof_nric_status}`` or None.

    ``name_status`` (relationship): 'match' | 'mismatch' | 'unknown' | 'pending'.
    ``proof_name_status`` / ``proof_nric_status`` (vs the income proof): 'match' | 'mismatch'
    | 'no_ref' (no proof uploaded yet, or the field wasn't read). ``proof_kind``: 'str' |
    'salary_slip' | 'epf' | '' — drives the "Matches the STR document" student label."""
    from .vision import nric_match
    if getattr(doc, 'doc_type', '') != 'parent_ic':
        return None
    app = doc.application
    member = ((getattr(doc, 'household_member', '') or '').strip()
              or (getattr(app, 'income_earner', '') or '').strip())
    name = (getattr(doc, 'vision_name', '') or '').strip()
    nric = (getattr(doc, 'vision_nric', '') or '').strip()
    readable = bool(getattr(doc, 'vision_run_at', None)) and not getattr(doc, 'vision_error', '') and bool(name)

    name_status = 'pending'
    if not member or not name:
        name_status = 'unknown' if (readable and not member) else 'pending'
    else:
        student_name = getattr(getattr(app, 'profile', None), 'name', '') or ''
        bc_child, bc_mother, bc_father, letter_name = _relationship_inputs(app, member, name)
        name_status = member_relationship_status(member, student_name, name,
                                                 bc_child, bc_mother, letter_name, bc_father)

    # Cross-check against the cluster's income proof (STR / salary slip) — the reason the
    # earner IC is uploaded. Green when the IC's name + number match the proof's recipient.
    proof_kind, p_name, p_nric = _cluster_proof_identity(app, member) if member else ('', '', '')
    proof_name_status = 'no_ref'
    if name and p_name:
        proof_name_status = 'mismatch' if name_match(name, p_name) == 'mismatch' else 'match'
    proof_nric_status = 'no_ref'
    if nric and p_nric:
        proof_nric_status = 'match' if nric_match(nric, p_nric) else 'mismatch'

    return {
        'nric': getattr(doc, 'vision_nric', '') or '',
        'name': getattr(doc, 'vision_name', '') or '',
        'address': getattr(doc, 'vision_address', '') or '',
        'member': member,
        'name_status': name_status,
        'readable': readable,
        'proof_kind': proof_kind,
        'proof_name_status': proof_name_status,
        'proof_nric_status': proof_nric_status,
    }


def _cluster_docs(application, member, doc_type):
    """The documents of *doc_type* in *member*'s income cluster, latest first. The two
    routes store income docs differently: the SALARY route tags each doc with the
    household member; the STR route stores ONE untagged earner set (single earner). So
    the storage tag is the member on the salary route and '' on the STR route — this
    hides that difference so every income check works the same for both routes."""
    route = (getattr(application, 'income_route', '') or '').strip()
    tag = member if route == 'salary' else ''
    return (application.documents.filter(doc_type=doc_type, household_member=tag)
            .order_by('-uploaded_at'))


def _member_ic_doc(application, member):
    """That earner's IC (parent_ic) — salary route: tagged with the member; STR route:
    the single untagged earner IC. None if not uploaded."""
    if not member:
        return None
    return _cluster_docs(application, member, 'parent_ic').first()


def _proof_member(doc):
    """The earner a salary slip / EPF belongs to: its own household_member tag (salary
    route), or the application's single income_earner (STR route). '' if no income
    context (e.g. the wizard hasn't been walked) — the caller then skips the check."""
    member = (getattr(doc, 'household_member', '') or '').strip()
    if member:
        return member
    app = doc.application
    if (getattr(app, 'income_route', '') or '').strip() == 'str':
        return (getattr(app, 'income_earner', '') or '').strip()
    return ''


def student_income_proof_check(doc):
    """For a salary slip / EPF: the earner facts read off the document (name · NRIC ·
    amount · period) cross-checked against THAT earner's IC — NOT the student. So a
    father's payslip is verified against the father's IC, and the coach never tells the
    student to edit their own name. Works for both routes (salary = the member-tagged
    IC; STR = the single untagged earner IC). Returns
    ``{name, nric, amount, period, member, name_status, nric_status, ic_present}`` or
    None when it is not a salary_slip/epf with an income context.

    name_status / nric_status: 'match' | 'mismatch' | 'no_ref' (that earner's IC not
    uploaded yet, or the field wasn't read) — a soft, never-blocking signal."""
    from .vision import relationship_name_match as name_match, nric_match
    dt = getattr(doc, 'doc_type', '')
    if dt not in ('salary_slip', 'epf'):
        return None
    member = _proof_member(doc)
    if not member:
        return None

    f = _doc_fields(doc)
    name = (f.get('name', '') or '').strip()
    nric = (f.get('nric', '') or '').strip()
    # Data points shown on the card. Salary → gross + period. EPF → the MONTHLY
    # contribution (the income figure) + the total accumulated + the year (so the big
    # lifetime balance is never mistaken for monthly income).
    if dt == 'salary_slip':
        raw_points = [('amount', f.get('gross_income') or f.get('net_income')),
                      ('period', f.get('period'))]
    else:                                          # epf
        raw_points = [('monthlyContribution', f.get('monthly_contribution')),
                      ('totalAccumulated', f.get('latest_balance')),
                      ('year', f.get('year') or f.get('last_contribution'))]
    points = [{'key': k, 'value': (v or '').strip()} for k, v in raw_points if (v or '').strip()]

    ic = _member_ic_doc(doc.application, member)
    ic_name = (getattr(ic, 'vision_name', '') or '').strip() if ic else ''
    ic_nric = (getattr(ic, 'vision_nric', '') or '').strip() if ic else ''

    name_status = 'no_ref'
    if ic_name and name:
        name_status = 'mismatch' if name_match(name, ic_name) == 'mismatch' else 'match'
    nric_status = 'no_ref'
    if ic_nric and nric:
        nric_status = 'match' if nric_match(nric, ic_nric) else 'mismatch'

    return {
        'name': name, 'nric': nric, 'points': points,
        'member': member, 'name_status': name_status, 'nric_status': nric_status,
        'ic_present': ic is not None,
    }


_STR_REJECTED_WORDS = ('tolak', 'tidak layak', 'gagal', 'reject')
# Positive STR approval signals. 'lulus' also matches 'diLULUSkan'. NOTE: SARA's 'Layak' is
# deliberately NOT here — SARA (Sumbangan Asas Rahmah) is a different programme from STR, and the
# STR status on the MySTR portal is 'Lulus', never 'Layak'. (#5b SARA≠STR, 2026-06-11)
_STR_APPROVED_WORDS = ('lulus', 'approve')
_STR_YEAR_RE = re.compile(r'(20\d{2})')


def _str_currency(status_raw, year_str, cohort_year, source_type=''):
    """Whether an STR positively PROVES current B40. It proves B40 when the document is a
    RECOGNISED STR proof AND shows an APPROVED status ('Lulus' / 'Diluluskan' / SARA 'Layak');
    the MySTR 'Semakan Status' / Dashboard pages show that status as CURRENT ("Semasa") and print
    NO cohort year, so an approval is accepted even without a readable year (a year only adds the
    ability to catch a stale prior-year STR).
      'rejected'    — a clear negative status (Ditolak / Tidak Layak / Gagal);
      'stale'       — APPROVED but a readable year OLDER than the cohort year (STR is annual);
      'current'     — a recognised STR proof with an approval word (current year, or no year);
      'unconfirmed' — NO approval status (a SALINAN / application printout, or a status we
                      couldn't read), OR the document is not a recognised STR proof at all
                      (``source_type='unknown'`` — e.g. a SARA-only Perdana Menteri letter; SARA
                      (Sumbangan Asas Rahmah) is a DIFFERENT programme from STR). NOT proof — the
                      student is asked for the MySTR page showing 'Lulus' or the STR approval letter.
    Earlier this returned 'current' by default (benefit of the doubt), which wrongly accepted
    unapproved application records as B40 proof."""
    s = (status_raw or '').lower()
    if any(w in s for w in _STR_REJECTED_WORDS):
        return 'rejected'
    # The document must be a RECOGNISED STR proof (official STR letter / MySTR 'Semakan Status' /
    # Dashboard). A positively-classified 'unknown' source — e.g. a SARA-only Perdana Menteri
    # letter (SARA ≠ STR) — is NOT STR proof, whatever status text was read off it. A blank/legacy
    # source_type (extracted before classification existed) falls through to the status check so
    # existing approvals are not retro-broken. (#5b SARA≠STR, 2026-06-11)
    if (source_type or '').strip().lower() == 'unknown':
        return 'unconfirmed'
    if not any(w in s for w in _STR_APPROVED_WORDS):
        return 'unconfirmed'    # no approval status shown (a SALINAN / application printout, or
                                # a status we couldn't read) → still NOT proof of approval.
    # Approved. A readable PRIOR-year STR is stale (STR is annual); but the MySTR 'Semakan
    # Status' / Dashboard page shows "Status Permohonan SEMASA: Lulus" with NO printed year —
    # "Semasa" (current) IS the currency signal — so an approval WITHOUT a year is accepted as
    # current (the live portal reflects this cycle). The year is a bonus that only ADDS the
    # ability to catch a stale prior-year STR; its absence no longer demotes a valid Lulus. (#5)
    m = _STR_YEAR_RE.search(year_str or '')
    if m and cohort_year and int(m.group(1)) < int(cohort_year):
        return 'stale'
    return 'current'


def student_str_check(doc):
    """For an STR document: the recipient facts (name · NRIC · status · year · amount)
    cross-checked against the STR EARNER's IC (the household benefit is in the earner's
    name — Q2 'whose STR?'), plus whether it's CURRENT (this cohort year + approved).
    Returns ``{name, nric, status, year, amount, member, name_status, nric_status,
    current_status, ic_present}`` or None for a non-STR doc.

    name_status / nric_status: 'match' | 'mismatch' | 'no_ref'.
    current_status: 'current' | 'stale' | 'rejected'."""
    from .vision import relationship_name_match as name_match, nric_match
    if getattr(doc, 'doc_type', '') != 'str':
        return None
    app = doc.application
    member = (getattr(app, 'income_earner', '') or '').strip()   # STR route single earner

    vf = doc.vision_fields if isinstance(getattr(doc, 'vision_fields', None), dict) else {}
    f = vf.get('fields', {}) if isinstance(vf.get('fields', {}), dict) else {}
    name = (f.get('recipient_name', '') or '').strip()
    nric = (f.get('recipient_nric', '') or '').strip()
    status = (f.get('status', '') or '').strip()
    year = (f.get('year', '') or '').strip()
    amount = (f.get('amount', '') or '').strip()

    ic = _member_ic_doc(app, member) if member else None
    ic_name = (getattr(ic, 'vision_name', '') or '').strip() if ic else ''
    ic_nric = (getattr(ic, 'vision_nric', '') or '').strip() if ic else ''

    name_status = 'no_ref'
    if ic_name and name:
        name_status = 'mismatch' if name_match(name, ic_name) == 'mismatch' else 'match'
    nric_status = 'no_ref'
    if ic_nric and nric:
        nric_status = 'match' if nric_match(nric, ic_nric) else 'mismatch'

    cohort_year = getattr(getattr(app, 'cohort', None), 'year', None)
    return {
        'name': name, 'nric': nric, 'status': status, 'year': year, 'amount': amount,
        'member': member, 'name_status': name_status, 'nric_status': nric_status,
        'current_status': _str_currency(status, year, cohort_year, f.get('source_type', '')),
        'ic_present': ic is not None,
    }


# ── Per-capita income from the documents (Check-1 I4, salary route) ──────────
_AMOUNT_RE = re.compile(r'(\d[\d,]*\.?\d*)')
# EPF total monthly contribution ≈ 11% (employee) + 13% (employer) = 24% of salary, so a
# salary estimate when there's no payslip: monthly_salary ≈ contribution / 0.24.
_EPF_CONTRIB_RATE = 0.24


def _parse_rm(s):
    """Parse an RM figure ('RM 9,900.04' / '2400.00' / 'RM2,400') → float, or None."""
    if not s:
        return None
    m = _AMOUNT_RE.search(str(s).replace(' ', ''))
    if not m:
        return None
    try:
        return float(m.group(1).replace(',', ''))
    except ValueError:
        return None


def _doc_fields(doc):
    vf = doc.vision_fields if isinstance(getattr(doc, 'vision_fields', None), dict) else {}
    f = vf.get('fields', {})
    return f if isinstance(f, dict) else {}


def earner_monthly_income(application, member):
    """A working member's estimated MONTHLY income from their documents + the source.
    The salary slip's gross is primary; failing that, estimate from the EPF monthly
    contribution (≈24% of salary). Returns ``(amount: float | None, source)`` where
    source is 'salary' | 'epf_estimate' | 'unknown'."""
    for slip in _cluster_docs(application, member, 'salary_slip'):
        f = _doc_fields(slip)
        amt = _parse_rm(f.get('gross_income') or f.get('net_income'))
        if amt:
            return amt, 'salary'
    for epf in _cluster_docs(application, member, 'epf'):
        contrib = _parse_rm(_doc_fields(epf).get('monthly_contribution'))
        if contrib:
            return round(contrib / _EPF_CONTRIB_RATE, 2), 'epf_estimate'
    return None, 'unknown'


def income_per_capita(application, members):
    """``(per_capita, all_known)`` — the document-derived household monthly income
    (sum of every working member's income) divided by the household size. ``all_known``
    is False when any member's income couldn't be read (so the per-capita is unreliable
    → the verdict falls to a human/interview). ``per_capita`` is None when income is
    unknown or there's no household size."""
    total, all_known = 0.0, True
    for m in (members or []):
        amt, _src = earner_monthly_income(application, m)
        if amt is None:
            all_known = False
        else:
            total += amt
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not all_known or not size:
        return None, all_known
    return total / size, all_known


# ── Relationship-proof documents: birth certificate + guardianship letter ────
def _name_bucket(extracted, reference):
    if not (extracted or '').strip() or not (reference or '').strip():
        return 'no_ref'
    return 'mismatch' if name_match(extracted, reference) == 'mismatch' else 'match'


def _nric_bucket(extracted, reference):
    from .vision import nric_match
    if not (extracted or '').strip() or not (reference or '').strip():
        return 'no_ref'
    return 'match' if nric_match(extracted, reference) else 'mismatch'


def _combine(a, b):
    return 'mismatch' if 'mismatch' in (a, b) else ('match' if 'match' in (a, b) else 'no_ref')


def student_bc_check(doc):
    """Birth certificate: it links the student to their MOTHER (the income earner). Three
    rows: CHILD = the student (name + NRIC); MOTHER = the mother's IC (name + NRIC);
    FATHER = the student's patronymic. Returns the read fields + per-row status, or None."""
    if getattr(doc, 'doc_type', '') != 'birth_certificate':
        return None
    app = doc.application
    f = _doc_fields(doc)
    student = getattr(getattr(app, 'profile', None), 'name', '') or ''
    student_nric = getattr(getattr(app, 'profile', None), 'nric', '') or ''
    child_name = (f.get('bc_child_name', '') or '').strip()
    child_status = _combine(_name_bucket(child_name, student),
                            _nric_bucket(f.get('bc_child_nric'), student_nric))
    mother_name = (f.get('bc_mother_name', '') or '').strip()
    mother_nric = (f.get('bc_mother_nric', '') or '').strip()
    mic = _member_ic_doc(app, 'mother')
    mother_status = _combine(_name_bucket(mother_name, getattr(mic, 'vision_name', '') if mic else ''),
                             _nric_bucket(mother_nric, getattr(mic, 'vision_nric', '') if mic else ''))
    father_name = (f.get('bc_father_name', '') or '').strip()
    father_status = _name_bucket(father_name, father_name_from_ic(student))
    return {
        'child_name': child_name, 'child_status': child_status,
        'mother_name': mother_name, 'mother_nric': mother_nric, 'mother_status': mother_status,
        'father_name': father_name, 'father_status': father_status,
        'bc_number': (f.get('bc_number', '') or '').strip(),
    }


def student_guardianship_check(doc):
    """Guardianship order / authorisation letter: ties the legal guardian to the student
    (the ward). GUARDIAN = the guardian's IC (name + NRIC); WARD = the student. Returns
    the read fields + per-row status, or None for a non-guardianship doc."""
    if getattr(doc, 'doc_type', '') != 'guardianship_letter':
        return None
    app = doc.application
    f = _doc_fields(doc)
    student = getattr(getattr(app, 'profile', None), 'name', '') or ''
    g_name = (f.get('guardian_name', '') or '').strip()
    g_nric = (f.get('guardian_nric', '') or '').strip()
    gic = _member_ic_doc(app, 'guardian')
    guardian_status = _combine(_name_bucket(g_name, getattr(gic, 'vision_name', '') if gic else ''),
                               _nric_bucket(g_nric, getattr(gic, 'vision_nric', '') if gic else ''))
    ward_name = (f.get('ward_name', '') or '').strip()
    return {
        'guardian_name': g_name, 'guardian_nric': g_nric, 'guardian_status': guardian_status,
        'ward_name': ward_name, 'ward_status': _name_bucket(ward_name, student),
        'doc_kind': (f.get('doc_kind', '') or '').strip(),
    }


# ── Utility bills as a SOFT B40 proxy + hardship signal (imperfect; officer context) ─
_UTILITY_B40_CEILING = 25   # < RM25/capita/month combined → consistent with B40
_UTILITY_HIGH_FLOOR = 40    # > RM40/capita/month → likely M40/T20 consumption


# Reading a utility bill: a month-name → number map (Malay + English, common OCR forms)
# and a tolerant period parser, so "Mei 2026" / "05/2026" / "2026-05" all resolve.
_UTILITY_MONTHS = {
    'jan': 1, 'feb': 2, 'mac': 3, 'mar': 3, 'apr': 4, 'apl': 4, 'mei': 5, 'may': 5,
    'jun': 6, 'jul': 7, 'ogo': 8, 'aug': 8, 'sep': 9, 'okt': 10, 'oct': 10,
    'nov': 11, 'dis': 12, 'dec': 12,
}
_UTILITY_CURRENT_MONTHS = 3   # a bill within ~3 months of the review date counts as current


def _parse_billing_month(period):
    """``(year, month)`` from a free-form billing period ('Mei 2026', '05/2026',
    '2026-05', 'April 2026'), or None when nothing parseable is found."""
    if not period:
        return None
    t = str(period).lower()
    ym = re.search(r'(20\d{2})', t)
    year = int(ym.group(1)) if ym else None
    month = None
    for name, num in _UTILITY_MONTHS.items():
        if name in t:
            month = num
            break
    if month is None:                                  # numeric month
        m = re.search(r'\b(\d{1,2})[/\-.](20\d{2})\b', t)
        if m:
            month, year = int(m.group(1)), int(m.group(2))
        else:
            m = re.search(r'\b(20\d{2})[/\-.](\d{1,2})\b', t)
            if m:
                year, month = int(m.group(1)), int(m.group(2))
    if not year or not month or not (1 <= month <= 12):
        return None
    return year, month


def _utility_currency(period, today):
    """Is the bill recent? 'current' (within ~3 months of *today*) | 'stale' (older) |
    'unknown' (no readable date). Measured against the review date, not the application
    date — the question is whether this is a LIVE household paying bills now."""
    ym = _parse_billing_month(period)
    if not ym:
        return 'unknown'
    year, month = ym
    months_ago = (today.year - year) * 12 + (today.month - month)
    if months_ago < 0:                                 # future-dated (data entry) → treat current
        return 'current'
    return 'current' if months_ago <= _UTILITY_CURRENT_MONTHS else 'stale'


def utility_reasonable(application):
    """Combined household utility consumption as a soft B40 proxy, shown identically on
    every bill row. Water alone is a weak signal (cheap, flat across households) — so a
    verdict is only given when BOTH bills are present; one bill → 'partial' (can't judge).
    Returns ``{status, detail, per_capita}``:
      - status: 'reasonable' (< RM25/head) | 'borderline' (RM25–40) | 'high' (> RM40)
                | 'partial' (only one bill) | 'unknown' (no amount / no household size).
      - detail: 'both' | 'water_only' | 'electricity_only' | '' — which bills informed it."""
    amounts = {}
    for dt in ('water_bill', 'electricity_bill'):
        d = _latest_doc(application, dt)
        amt = _parse_rm(_doc_fields(d).get('amount')) if d else None
        if amt is not None:
            amounts[dt] = amt
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not amounts or not size:
        return {'status': 'unknown', 'detail': '', 'per_capita': None}
    if len(amounts) < 2:                               # one bill alone can't judge consumption
        detail = 'water_only' if 'water_bill' in amounts else 'electricity_only'
        return {'status': 'partial', 'detail': detail, 'per_capita': None}
    pc = sum(amounts.values()) / size
    status = ('reasonable' if pc < _UTILITY_B40_CEILING
              else 'high' if pc > _UTILITY_HIGH_FLOOR else 'borderline')
    return {'status': status, 'detail': 'both', 'per_capita': round(pc, 2)}


def _utility_name_unrelated(application, bill_name):
    """True when the account-holder name matches NEITHER the student nor any uploaded
    parent/earner IC — a soft 'bill is in someone else's name' note. Bills are routinely
    in a parent's name (fine, matches the IC); the note fires only when it's a stranger.
    Never asserted on a blank read or with no reference name to compare against."""
    bill = (bill_name or '').strip()
    if not bill:
        return False
    candidates = []
    student = getattr(getattr(application, 'profile', None), 'name', '') or ''
    if student.strip():
        candidates.append(student)
    for ic in application.documents.filter(doc_type='parent_ic'):
        nm = (getattr(ic, 'vision_name', '') or '').strip()
        if nm:
            candidates.append(nm)
    if not candidates:
        return False
    return all(name_match(bill, c) == 'mismatch' for c in candidates)


def utility_check(doc, today=None):
    """For a water / electricity bill: the account-holder name (a data point — bills are in
    a parent's name), the home address (matched via the upload-time ``vision_address_match``),
    the monthly charge + any arrears, plus three soft facts — whether the bill is CURRENT
    (≤3 months old), whether household consumption is REASONABLE (combined per-capita, both
    bills), and whether ARREARS exceed the current charge (a hardship signal). All soft,
    never a gate. Returns the fact dict or None for a non-utility doc."""
    if getattr(doc, 'doc_type', '') not in ('water_bill', 'electricity_bill'):
        return None
    if today is None:
        today = datetime.date.today()
    app = doc.application
    f = _doc_fields(doc)
    name = (f.get('name', '') or '').strip()
    monthly = _parse_rm(f.get('amount'))
    arrears = _parse_rm(f.get('unpaid_balance'))
    reasonable = utility_reasonable(app)
    return {
        'name': name,
        'address': (f.get('address', '') or '').strip(),
        'monthly_bill': (f.get('amount', '') or '').strip(),
        'unpaid_balance': (f.get('unpaid_balance', '') or '').strip(),
        'address_status': getattr(doc, 'vision_address_match', '') or '',
        'current_status': _utility_currency(f.get('billing_period'), today),
        'reasonable_status': reasonable['status'],
        'reasonable_detail': reasonable['detail'],
        # 'arrears' (shown green) only when arrears exceed the current charge; else hidden.
        'outstanding_status': 'arrears' if (arrears and monthly and arrears > monthly) else '',
        'name_note': 'unrelated' if _utility_name_unrelated(app, name) else '',
    }


def _latest_doc(application, doc_type):
    return application.documents.filter(doc_type=doc_type).order_by('-uploaded_at').first()


def utility_per_capita(application):
    """Combined water + electricity MONTHLY bill ÷ household size, with a soft B40 proxy.
    Returns ``{per_capita, signal}`` ('b40' | 'neutral' | 'high') or None when no bill
    amount / household size. IMPERFECT — officer context, never a verdict gate."""
    total, any_read = 0.0, False
    for dt in ('water_bill', 'electricity_bill'):
        doc = _latest_doc(application, dt)
        amt = _parse_rm(_doc_fields(doc).get('amount')) if doc else None
        if amt is not None:
            total += amt
            any_read = True
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not any_read or not size:
        return None
    pc = total / size
    signal = 'b40' if pc < _UTILITY_B40_CEILING else ('high' if pc > _UTILITY_HIGH_FLOOR else 'neutral')
    return {'per_capita': round(pc, 2), 'signal': signal}


def utility_monthly_total(application):
    """Combined water + electricity MONTHLY charge (RM), or None when neither bill
    amount could be read. Used for the 'utility spend high vs declared income' flag."""
    total, any_read = 0.0, False
    for dt in ('water_bill', 'electricity_bill'):
        doc = _latest_doc(application, dt)
        amt = _parse_rm(_doc_fields(doc).get('amount')) if doc else None
        if amt is not None:
            total += amt
            any_read = True
    return round(total, 2) if any_read else None


def utility_hardship(application):
    """True when the utility bills carry meaningful arrears (unpaid balance) — a soft
    hardship signal that SUPPORTS need. Sums arrears across water + electricity."""
    total = 0.0
    for dt in ('water_bill', 'electricity_bill'):
        doc = _latest_doc(application, dt)
        amt = _parse_rm(_doc_fields(doc).get('unpaid_balance')) if doc else None
        if amt:
            total += amt
    return total > 100


def income_cluster_advice(application, member):
    """The SINGLE coach verdict for a household member's whole Income cluster — their IC
    (the anchor) + their income proofs (STR / salary slip / EPF) + their relationship doc —
    so Cikgu Gopal speaks ONCE per earner, at the foot of the cluster, not once per file.
    Income is a cluster (Father's IC + Father's payslip + …), unlike the single-document
    Identity / Academic / Pathway facts. The verdict is anchored on a POSITION (the cluster
    foot), so it speaks even before the IC arrives — it folds in the STR-currency and
    'add the IC' nudges that used to live on the STR / payslip rows.

    Precedence (most serious first):
      1. relationship — the IC does not link to the student (wrong person's card);
      2. readable     — the IC could not be read;
      3. STR currency — the STR is stale / rejected (STR route);
      4. coherence    — a payslip / EPF / STR is a DIFFERENT person from the IC;
      5. missing IC   — proofs are uploaded but the earner's IC is not, so we can't confirm.
    Returns '' when the cluster is consistent (or empty)."""
    if not member:
        return ''
    route = (getattr(application, 'income_route', '') or '').strip()
    str_doc = (application.documents.filter(doc_type='str').order_by('-uploaded_at').first()
               if route == 'str' else None)
    proofs = [p for dt in ('salary_slip', 'epf') for p in _cluster_docs(application, member, dt)]
    has_proof = bool(proofs) or str_doc is not None

    ic = _member_ic_doc(application, member)
    if ic is None:
        # No IC yet. STR currency can still be judged from the STR alone; otherwise, if any
        # proof was uploaded, nudge to add the earner's IC so we can confirm the person.
        if str_doc is not None:
            sc = student_str_check(str_doc)
            if sc and sc['current_status'] in ('stale', 'rejected', 'unconfirmed'):
                return 'str_not_current'
        return 'income_ic_needed' if has_proof else ''

    # IC present — the full cluster, in precedence order.
    icc = student_income_ic_check(ic)
    if icc:
        if icc['name_status'] == 'mismatch':
            return 'income_relationship_mismatch'
        if getattr(ic, 'vision_run_at', None) and not icc['readable']:
            return 'unreadable'
    if str_doc is not None:
        sc = student_str_check(str_doc)
        if sc and sc['current_status'] in ('stale', 'rejected', 'unconfirmed'):
            return 'str_not_current'
    # Coherence — every proof (payslip / EPF, and the STR recipient) must be the SAME
    # person as the earner's IC.
    for p in proofs:
        pc = student_income_proof_check(p)
        if pc and 'mismatch' in (pc['name_status'], pc['nric_status']):
            return 'income_proof_person_mismatch'
    if str_doc is not None:
        sc = student_str_check(str_doc)
        if sc and 'mismatch' in (sc['name_status'], sc['nric_status']):
            return 'income_proof_person_mismatch'
    # Salary route: the salary slip is this earner's compulsory income PROOF — the document that
    # actually shows the income. If the IC is in and matches but the salary slip is still
    # missing, nudge it as the logical NEXT step, BEFORE the relationship doc (uploading a birth
    # certificate before any proof of income is out of order). EPF doesn't substitute it (gate v2).
    if route == 'salary' and not _cluster_docs(application, member, 'salary_slip').exists():
        return 'income_proof_needed'
    # IC present + coherent. The relationship-proof doc (mother → birth certificate, guardian
    # → letter) links the earner to the student — it's the LAST step (father/sibling need none:
    # the shared patronymic on the IC proves it).
    rel_doc = relationship_doc_for(member)
    if rel_doc:
        rel_obj = (application.documents.filter(doc_type=rel_doc)
                   .order_by('-uploaded_at').first())
        if rel_obj is None:
            return 'income_rel_doc_needed'             # not uploaded yet → nudge for it
        # Uploaded, but we still can't confirm the link. A name CLASH already returned
        # 'income_relationship_mismatch' above; a 'pending' here once the doc has been
        # PROCESSED means it was unreadable / the wrong document (e.g. an IC sent as a birth
        # cert). The relationship doc is a field-extraction doc (birth cert / letter), so its
        # "processed" stamp is vision_fields_run_at — NOT vision_run_at, which only the IC path
        # sets (a birth cert never has it). Accept either so the check survives doc-type quirks.
        rel_status = icc['name_status'] if icc else 'pending'
        rel_ran = (getattr(rel_obj, 'vision_fields_run_at', None)
                   or getattr(rel_obj, 'vision_run_at', None))
        if rel_status == 'pending' and rel_ran:
            return 'income_rel_doc_unreadable'
    return ''


def salary_member_blocks(members) -> list:
    """Per-member document plan for the salary route. For each working member, the
    documents that person contributes — compulsory IC (+ relationship doc for a
    mother/guardian), optional salary slip + EPF. Income-evidence docs (parent_ic /
    salary_slip / epf) are TAGGED to the member; the relationship doc (birth cert /
    guardianship letter) is a single household doc, untagged.

    Returns ``[{member, compulsory: [(doc_type, member_tag)],
                optional: [(doc_type, member_tag)], rel_doc}]`` in display order."""
    chosen = {m for m in (members or []) if m in _MEMBER_ORDER}
    blocks = []
    for m in _MEMBER_ORDER:
        if m not in chosen:
            continue
        # Compulsory order (drives both the gate and the cockpit panel): the member's
        # IC → their salary slip → the relationship doc (mother/guardian only). The
        # salary slip is COMPULSORY (gate v2, 2026-06-05) — EPF does not substitute it.
        compulsory = [('parent_ic', m), ('salary_slip', m)]
        rel = relationship_doc_for(m)
        if rel:
            compulsory.append((rel, ''))            # birth cert / letter — single, untagged
        optional = [('epf', m)]
        blocks.append({'member': m, 'compulsory': compulsory,
                       'optional': optional, 'rel_doc': rel})
    return blocks


# ── The requirement engine ───────────────────────────────────────────────────

def income_requirements(application) -> dict:
    """Given the wizard answers on *application*, the documents the family needs.

    Returns ``{route, members, compulsory, optional}``:
      - ``route``      — '' | 'str' | 'salary'.
      - ``members``    — salary route only: the per-member blocks from
                         ``salary_member_blocks`` (empty for the STR route).
      - ``compulsory`` — flat doc-type list (STR route: earner IC + relationship + STR;
                         salary route: empty — everything is per-member).
      - ``optional``   — household-level credibility docs (utility bills).

    The STR route keeps the original single-earner shape; the salary route is driven
    by ``income_working_members`` (multi-select). Optional docs never block. Blank
    answers (wizard not walked) → just the earner IC compulsory; the verdict flags it."""
    route = (getattr(application, 'income_route', '') or '').strip()

    if route == 'salary':
        members = salary_member_blocks(working_members(application))
        return {'route': 'salary', 'members': members,
                'compulsory': [], 'optional': ['water_bill', 'electricity_bill']}

    # STR route (single earner) + the blank fallback.
    earner = (getattr(application, 'income_earner', '') or '').strip()
    compulsory = ['parent_ic']                 # the earner's IC — always
    rel_doc = relationship_doc_for(earner)
    if rel_doc:
        compulsory.append(rel_doc)             # mother→BC, guardian→letter; father→none
    optional: list[str] = []
    if route == 'str':
        compulsory.append('str')
        optional += ['water_bill', 'electricity_bill', 'salary_slip', 'epf']
    # route blank → wizard not started; only the earner IC stands. Verdict flags it.

    # De-dup while preserving order; a doc is never both compulsory and optional.
    seen = set(compulsory)
    optional = [d for d in optional if not (d in seen or seen.add(d))]
    return {'route': route, 'members': [], 'compulsory': compulsory, 'optional': optional}
