"""
Income verification — Check-1 item 3: earner identity + relationship.

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

⚠ THIS IS A RE-EXPORT SHELL AND NO CODE (code health H16, 2026-09-20). `income_engine.py`
was 3,188 lines and the worst hotspot in the repository; its bodies are the modules beside
this file, every line byte-identical to the line it came from. Import from
`apps.scholarship.income_engine` exactly as before — every name the old module defined is
re-exported here, and no importing file was changed.

⛔ THIS PACKAGE IS ELIGIBILITY. A change here changes who is funded. H16 moved it and
changed NOTHING: no verdict moved, `VERDICT_ENGINE_VERSION` was not bumped, and the
eligibility suites are green on the same counts. The owner rulings that settled this code
are TD-262 chunks 1-3, rule-4 items 1 and 1b, F8, and the 2026-09-20 ruling that the cash
door stays off the STR route. Read `docs/technical-debt.md` before editing any of it.

⚠ `halatuju-web/src/lib/incomeWizard.ts` is a deliberate MIRROR of this engine and carries
the three remaining `unguarded_mirrors` entries, parked until TD-262 is fully settled. It
was not touched here, and it still names `income_engine` — which is this package now.
"""


from .buckets import _combine_relationship, _name_bucket, _nric_bucket
from .relationships import (
    _MEMBER_ORDER, _PATRONYMIC_MEMBERS, _PATRONYMIC_RE, _RELATIONSHIP_DOC, _bc_link,
    _relationship_inputs, effective_working_members, father_link, father_name_from_ic,
    father_relationship, father_via_bc, guardian_relationship, member_relationship_status,
    mother_relationship, relationship_doc_for, student_name_for_link, working_members
)
from .salary_figures import (
    _AMOUNT_RE, _EPF_CONTRIB_RATE, _NET_OVER_GROSS_TOL, _SLIP_EPF_HI, _SLIP_EPF_LO,
    _arrears_amount, _doc_fields, _epf_monthly_salary, _parse_rm, _salary_monthly_amount,
    epf_no_employer
)
from .identity_checks import (
    _RESOLVABLE_INCOME_DOCS, _bc_anchorable, _bc_doc, _bc_parent_identity, _cluster_docs,
    _cluster_proof_identity, _doc_person_name, _member_ic_doc, _name_matched_members,
    _proof_member, _roster_candidates, chain_verified_earner, implied_single_member,
    name_contradicts_tag, resolved_member_for, student_income_ic_check,
    student_income_proof_check
)
from .doc_checks import (
    _REL_DOC_READ_FIELDS, relationship_doc_unreadable, student_bc_check,
    student_guardianship_check, student_income_support_check
)
from .str_route import (
    STR_COACH_STATES, STR_RED_STATES, _STR_APPROVED_WORDS, _STR_CURRENCY_RANK,
    _STR_RECOGNISED_SOURCES, _STR_REJECTED_WORDS, _STR_SOURCE_RANK, _STR_YEAR_RE, _str_currency,
    _str_recipient_household_match, str_proof_quality, student_str_check
)
from .utilities import (
    _MONTH_ABBR, _UTILITY_ACCEPT_MONTHS, _UTILITY_B40_CEILING, _UTILITY_CURRENT_MONTHS,
    _UTILITY_HIGH_FLOOR, _UTILITY_MONTHS, _bill_age_months, _bill_as_of, _bill_month_label,
    _latest_doc, _parse_billing_month, _reconciled_holder_name, _same_utility_holder,
    _utility_currency, _utility_holder_names, _utility_name_unrelated, utility_address_mismatch,
    utility_check, utility_hardship, utility_holder_unknown, utility_monthly_total,
    utility_per_capita, utility_reasonable
)
from .advice import income_cluster_advice, income_requirements, salary_member_blocks
from .evidence import (
    _member_has_epf_value, _salary_slip_not_wrongtype, any_member_income_evidenced,
    declared_amount, has_income_support_doc, has_valid_str, household_str_status,
    income_established, member_cluster_complete, member_income_evidenced,
    salary_income_satisfied, str_confirmed_current, str_not_breached, usable_salary_slip
)
from .freshness import (
    _DEDUP_DOC_TYPES, _HOUSEHOLD_WIDE_DEDUP, _INCOME_DOC_CURRENT_MONTHS, _dedup_clean_rank,
    _doc_genuine_rank, _income_doc_recency, _salary_period_age_months, dedupe_income_proof,
    income_dedup_rank, stale_income_proof
)
from .amounts import (
    _HEADROOM_THIN_RM, _INCOME_CONVERT_STATUSES, _SGD_EMPLOYER_RE, _slip_is_sgd, _to_myr,
    earner_monthly_income, income_headroom, income_per_capita, income_test_configured,
    sgd_to_myr_rate, slip_epf_divergence
)
from .occupation import (
    _NON_EARNING_OCC, _docs_or_none, _has_read_doc, _member_occupation,
    epf_confirms_unemployment, school_leaving_cert_gap, sibling_school_detail_unknown,
    sibling_tertiary_funding_unknown, unemployed_members, unemployment_corroborated_members,
    unemployment_detail_gap, unemployment_epf_gap, unemployment_epf_members, unemployment_status
)
from .bill_followups import (
    _bill_needs_upload, _undated_clean_bill_attempts, utility_bill_gap, utility_bill_recheck
)
from .gaps import (
    _member_income_documented, _parent_has_income_evidence, household_status_gaps,
    member_income_status, parent_income_gaps, parent_income_status
)
from .household import (
    _INCOME_MATCH_TOL_FRAC, _INCOME_MATCH_TOL_MIN, _NOT_IN_HOUSEHOLD, _described_household_count,
    _income_earning_members, _member_income_genuine, household_income_reconciliation,
    household_size_accounted, household_size_shortfall
)
from .informal import (
    _NEGATIONS, _PAYSLIP_TERMS, _member_occupation_label, deceased_parent_detail_gap,
    deceased_parent_members, informal_income_context, informal_income_detail_gap,
    informal_income_members, informal_payslip_claimed, informal_work_detail_gap,
    member_is_informal, payslip_claim
)
from .epf_evidence import (
    _MULTI_YEAR_PATHWAYS, _doc_authenticity, employed_epf_gap, employed_epf_members,
    semester_result_gap, slip_epf_evidence
)
from .followups import (
    _ROSTER_UNDERCOUNT_MARGIN, high_utility_expense_context, high_utility_expense_gap,
    household_roster_undercount, other_scholarships_followup_gap
)
from .pension import (
    _PENSION_TERMS, pension_claim, pension_claimed, pension_context, pension_members,
    str_earner_income_document_gap
)

__all__ = [n for n in dir() if not n.startswith("__")]
