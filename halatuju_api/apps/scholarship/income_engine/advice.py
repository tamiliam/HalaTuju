"""What the student is asked for: the cluster advice line, the compulsory salary-member
blocks, and `income_requirements` — the list the wizard mirrors.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

from ..document_snapshot import latest_doc
from .identity_checks import _cluster_docs, _member_ic_doc, student_income_ic_check, student_income_proof_check
from .relationships import _MEMBER_ORDER, effective_working_members, relationship_doc_for
from .str_route import STR_COACH_STATES, student_str_check


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
    str_doc = latest_doc(application, 'str') if route == 'str' else None
    proofs = [p for dt in ('salary_slip', 'epf') for p in _cluster_docs(application, member, dt)]
    has_proof = bool(proofs) or str_doc is not None

    ic = _member_ic_doc(application, member)
    if ic is None:
        # No IC yet. STR currency can still be judged from the STR alone; otherwise, if any
        # proof was uploaded, nudge to add the earner's IC so we can confirm the person.
        if str_doc is not None:
            sc = student_str_check(str_doc)
            if sc and sc['current_status'] in STR_COACH_STATES:
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
        if sc and sc['current_status'] in STR_COACH_STATES:
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
        rel_obj = latest_doc(application, rel_doc)
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
        # Code-health S4 #18: 'pending' can come from EITHER side of the comparison. Only
        # blame the relationship doc when the EARNER IC has actually been read — an IC whose
        # OCR is still pending (vision_run_at NULL, a known transient state the self-heal
        # cron clears) used to surface as 'income_rel_doc_unreadable', telling the student
        # to re-upload a perfectly fine birth certificate and blocking submission on it.
        ic_ran = bool(getattr(ic, 'vision_run_at', None))
        if rel_status == 'pending' and rel_ran and ic_ran:
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
        # Compulsory: the member's IC → the relationship doc (mother/guardian only). Income
        # itself is shown ANY ONE way (owner 2026-07-25: payslip / EPF / declared+letter / STR —
        # see member_income_evidenced), so the salary slip is OPTIONAL, not a lonely red-* box a
        # cash/informal earner can never fill. The gate enforces the "any one" via income_doc_blockers.
        compulsory = [('parent_ic', m)]
        rel = relationship_doc_for(m)
        if rel:
            compulsory.append((rel, ''))            # birth cert / letter — single, untagged
        optional = [('salary_slip', m), ('epf', m)]
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
        members = salary_member_blocks(effective_working_members(application))
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
