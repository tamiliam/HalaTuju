/**
 * THE COCKPIT TEST FIXTURE — an `AdminScholarshipDetail` at a NAMED STAGE.
 *
 * **Why this file exists.** `view.tsx` — the reviewer/QC/org-admin cockpit, 3,587 lines and the
 * most consequential screen in the product — had no rendered test, because nothing could build
 * the payload it needs. `approveLockoutGuard.test.ts` said so in its own docblock: it settled for
 * reading the file's SOURCE TEXT because "the officer cockpit has no test harness (mounting it is
 * the deferred `AdminApplicationDetail` fixture work)". This is that work.
 *
 * **WHY EVERY FIELD IS FILLED.** A partial fixture describes a state the product cannot produce,
 * and then the test passes for ever while testing nothing. That is exactly how BrightPath request
 * #24 happened: a hand-built object fed `status='rejected'` to a check whose live states never
 * include it, so the branch the test named could never be reached and a real defect sat behind a
 * green test for weeks. Every field of the interface is written out below, once, at its
 * `submitted` value; the stages then layer on top of it.
 *
 * **MIRRORS `halatuju_api/apps/scholarship/tests/factories.py`** (code health H5) — the same
 * stage names, the same branch points, and above all the same TWO ROADS TO QC:
 *
 *   * `outcome: 'recommend'` is the verify-accept road. It stamps `verified_at`, `verified_by`
 *     and `verify_checklist`, and locks `nric_verified`.
 *   * `outcome: 'decline'` is the submit-decline road. It stamps **none** of those — a decline
 *     has no identity or completeness gate, because an incomplete applicant is exactly who gets
 *     declined. Both roads leave the case at status `interviewed` (AWAITING QC).
 *
 * Asking for `verified_at` on the decline road is asking for a mark production never writes.
 * Keep the two stage tables in step.
 *
 * drift-test: halatuju-web/src/test/adminApplicationDetail.test.ts
 *
 * ⚠ EVERY DATE IS A FIXED LITERAL, never `new Date()`. The screen formats dates, the deploy gate
 * runs on a machine in another timezone, and a fixture that says "now" makes a test that can
 * disagree with itself at midnight.
 *
 * ⚠ OBVIOUSLY-FAKE PERSONAL DATA ONLY. "Test Student 07"; the NRIC stem `030303-14-` is the same
 * one the backend factory uses and belongs to no real person.
 */
import type {
  AdminApplicantDocument,
  AdminDisbursement,
  AdminInterviewSession,
  AdminResolutionItem,
  AdminScholarshipDetail,
  AdminSponsorProfile,
  AdminVerdictFact,
} from '@/lib/admin-api'

// ── The stage table (mirrors factories.STAGES) ───────────────────────────────────────────────
/**
 * Every stage the builder can reach, in the order the product reaches them.
 *
 * ⚠ There is NO 'draft': a row is created at submit and its status default is `submitted`.
 * ⚠ `scored`, `assigned` and `verdict_recorded` are real stages with NO status of their own —
 * the engine scores while the status stays `submitted`, a reviewer is attached while it stays
 * `profile_complete`, and `record-verdict` moves no status at all.
 */
export const STAGES = [
  'submitted',
  'scored',
  'shortlisted',
  'profile_complete',
  'assigned',
  'interviewing',
  'verdict_recorded',   // REQUIRES an outcome; status stays 'interviewing'
  'awaiting_qc',        // REQUIRES an outcome; status 'interviewed'
  'recommended',
  'awarded',
  'active',
  'maintenance',
  'closed',
  // ── the two terminal BRANCHES ──
  'rejected',
  'expired',
] as const

export type Stage = (typeof STAGES)[number]

/** Where each terminal branch LEAVES the main line, so a branch cannot inherit stamps it never
 *  had. A `rejected` case comes off the decline road at AWAITING QC; an `expired` one never got
 *  past `shortlisted`. (factories.BRANCHES) */
export const BRANCHES: Record<string, Stage> = { rejected: 'awaiting_qc', expired: 'shortlisted' }

const MAIN_LINE = STAGES.filter((s) => !(s in BRANCHES))

/** The two roads exist at exactly one point in the funnel; pretending otherwise is the #24
 *  mistake. (factories.OUTCOME_STAGES) */
export const OUTCOME_STAGES: readonly Stage[] = ['verdict_recorded', 'awaiting_qc']
export type Outcome = 'recommend' | 'decline'

/** What `verify-accept` records when the reviewer ticks every box. */
const VERIFY_CHECKLIST = { nric: true, name: true, results: true, document: true }
/** What `record-verdict` stores for each road. `overall` is what submit-decline and the QC view
 *  both branch on. */
const RECOMMEND_VERDICT = {
  identity: 'pass', academic: 'pass', pathway: 'pass', income: 'pass', overall: 'accept',
}
const DECLINE_VERDICT = {
  identity: 'pass', academic: 'fail', pathway: 'pass', income: 'fail', overall: 'decline',
}

const AT = '2026-06-01T09:00:00.000Z'          // the one timestamp every stamp uses
const DECLINE_DUE_AT = '2026-06-02T09:00:00.000Z'   // the 24h QC cool-off
const REPORTING_DATE = '2026-06-08'
const STANDARD_AWARD = '2000.00'
const REVIEWER_EMAIL = 'reviewer@example.test'
const REVIEWER_NAME = 'Test Reviewer 01'
const QC_EMAIL = 'qc@example.test'
const QC_NAME = 'Test Quality Officer 02'

// ── Errors, phrased the way the backend factory phrases them ─────────────────────────────────
function stageError(message: string): Error {
  return new Error(`buildApplicationDetail: ${message}`)
}

// ── The empty sub-objects, each shaped by its own interface ──────────────────────────────────
const EMPTY_VERDICT: AdminVerdictFact[] = []
const EMPTY_DOCUMENTS: AdminApplicantDocument[] = []
const EMPTY_RESOLUTION: AdminResolutionItem[] = []
const EMPTY_DISBURSEMENTS: AdminDisbursement[] = []

/** A four-fact verdict the engine could really have produced. Exported because a test that wants
 *  a RED fact (the QC gap floor) edits one entry rather than inventing the whole shape. */
export function buildVerdict(
  statuses: Partial<Record<AdminVerdictFact['fact'], AdminVerdictFact['status']>> = {},
): AdminVerdictFact[] {
  const facts: AdminVerdictFact['fact'][] = ['identity', 'academic', 'income', 'pathway']
  return facts.map((fact) => ({
    fact,
    status: statuses[fact] ?? 'verified',
    evidence: [{ code: `${fact}_ok`, params: {} }],
    unresolved: [],
  }))
}

/** One uploaded document. Every field of the interface, so a card cannot be drawn from a
 *  half-described file; `overrides` supplies the per-fact check a test is actually about. */
export function buildDocument(
  docType: string, overrides: Partial<AdminApplicantDocument> = {},
): AdminApplicantDocument {
  return {
    id: 301,
    doc_type: docType,
    household_member: '',
    resolved_member: '',
    original_filename: `test-${docType}.pdf`,
    content_type: 'application/pdf',
    size: 12_345,
    verification_status: 'pending',
    download_url: 'https://example.test/doc',
    vision_nric: '', vision_name: '', vision_address: '',
    vision_run_at: null, vision_error: '',
    vision_nric_verdict: '', vision_name_verdict: '',
    vision_name_match: '', vision_address_match: '',
    academic_check: null, pathway_check: null, income_ic_check: null, income_proof_check: null,
    str_check: null, utility_check: null, bc_check: null, guardianship_check: null,
    support_doc_check: null, semester_check: null, school_leaving_check: null,
    authenticity: null,
    superseded_at: null, superseded_by: null,
    ...overrides,
  }
}

/** A submitted interview session — what `isDecisionReady` needs before Approve/Decline wake. */
export function buildInterviewSession(
  overrides: Partial<AdminInterviewSession> = {},
): AdminInterviewSession {
  return {
    id: 501,
    status: 'submitted',
    findings: {},
    rubric: {},
    overall_note: 'The interview was held and the answers were consistent.',
    interviewer_name: REVIEWER_NAME,
    started_at: AT,
    submitted_at: AT,
    updated_at: AT,
    ...overrides,
  }
}

/** A published sponsor profile — what makes a `recommended` case pool-eligible. */
export function buildSponsorProfile(
  overrides: Partial<AdminSponsorProfile> = {},
): AdminSponsorProfile {
  return {
    draft_markdown: 'A determined SPM leaver hoping to read engineering.',
    edited_markdown: '',
    current_markdown: 'A determined SPM leaver hoping to read engineering.',
    status: 'published',
    model_used: 'test-model',
    generated_at: AT,
    published_at: AT,
    updated_at: AT,
    final_markdown: 'A determined SPM leaver hoping to read engineering.',
    final_model_used: 'test-model',
    finalised_at: AT,
    anon_markdown: 'A determined SPM leaver.',
    anon_model_used: 'test-model',
    anon_generated_at: AT,
    anon_published: true,
    anon_published_at: AT,
    ...overrides,
  }
}

// ── The base row: every field of the interface, at its `submitted` value ─────────────────────
function base(): AdminScholarshipDetail {
  return {
    id: 7,
    name: 'Test Student 07',
    school: 'SMK Test',
    nric: '030303-14-0007',
    nric_verified: false,
    mentoring_candidate: false,
    verified_at: null,
    verified_by: '',
    verify_checklist: {},
    profile_id: null,
    declaration_name: 'Test Student 07',
    qualification: 'spm',
    spm_a_count: 8,
    merit_score: 82,
    stpm_pngk: null,
    household_income: 2500,
    household_size: 5,
    receives_str: true,
    income_route: 'salary',
    income_earner: 'father',
    income_working_members: ['father'],
    receives_jkm: false,
    intended_pathway: 'university',
    intends_tertiary_2026: true,
    aspirations: 'To read engineering and support the family.',
    plans: 'Complete the foundation year, then the degree.',
    fears: 'That the fees cannot be met.',
    justification: '',
    address: 'No. 1 Jalan Test',
    postal_code: '62100',
    city: 'Putrajaya',
    preferred_state: 'Selangor',
    contact_phone: '0123456789',
    contact_email: 'student07@example.test',
    notify_email: 'student07@example.test',
    verified_email: 'student07@example.test',
    preferred_call_language: 'en',
    referral_source: null,
    referred_by_org: { id: 3, code: 'test-source', name: 'Test Referring Organisation' },
    witness_org: null,
    guardians: [{ name: 'Test Guardian 03', phone: '0123456788', relationship: 'father' }],
    muet_band: null,
    coq_score: null,
    grades: { bm: 'A', bi: 'A', maths: 'A' },
    stpm_grades: {},
    spm_prereq_grades: {},
    first_in_family: true,
    parents_occupation: 'Lorry driver',
    siblings_studying_count: 2,
    siblings_in_school: 1,
    siblings_in_tertiary: 1,
    family_context: 'One earner, five in the household.',
    daily_life: 'School, then helping at home.',
    consent_to_contact: true,
    declared_at: AT,
    pathway_certainty: 'sure',
    chosen_pathway: 'university',
    chosen_programme: { course_id: 'test-course', course_name: 'Test Engineering Degree',
                        institution: 'Test University' },
    chosen_programme_display: { title: 'Test Engineering Degree', stream: '' },
    pre_u_track: '',
    // Served by the api (TD-280), never computed here. Null is what the server sends for a blank
    // or unlabelled code, which is what this university-pathway applicant has.
    pre_u_track_label: null,
    pre_u_institution: '',
    uncertainty_reasons: [],
    uncertainty_note: '',
    pathways_considered: [],
    top_choices: [],
    upu_status: '',
    field_of_study: 'engineering',
    other_scholarships: [],
    other_scholarships_text: '',
    help_university: 'yes',
    help_scholarship: 'yes',
    anything_else: '',
    status: 'submitted',
    bucket: '',
    shortlist_reason: '',
    rejection_category: '',
    rejected_at: null,
    rejected_by: '',
    rejection_comments: '',
    reporting_date: null,
    closure_reason: '',
    pending_rejection_category: '',
    decline_due_at: null,
    award_due_at: null,
    submitted_at: AT,
    funding_need: { categories: ['fees'], funding_note: '', programme_months: 48 },
    anomalies: [],
    interview_agenda: [],
    verdict: EMPTY_VERDICT,
    submission_review: { ledger: [], completeness: [], consistency: [] },
    query_sla: {
      deadline: null, lapsed: false, open_count: 0, days_left: null,
      ready_for_assignment: true, proceeding_with_open_queries: false, clarify_overflow: 0,
    },
    funding_estimate: {
      pathway: 'university', known: true, monthly: 300, months: 48,
      total: 14400, variable: false, practical: false,
    },
    interview_gaps: [],
    interview_gaps_run_at: null,
    household_check: undefined,
    documents: EMPTY_DOCUMENTS,
    referees: [],
    consents: [],
    sponsor_profile: null,
    profile_completed_at: null,
    completeness: {
      quiz_done: true, details_done: true, funding_done: true, documents_done: true,
      consent_done: true, address_done: true, guardian_docs_done: true, family_done: true,
      complete: true,
    },
    consent_blockers: [],
    nudge: { applicable: false, sent_at: null, available: false, available_at: null },
    interview_session: null,
    assigned_to_id: null,
    assigned_to_name: null,
    assigned_at: null,
    info_request_note: '',
    info_requested_at: null,
    ai_verdict_snapshot: [],
    officer_verdict: {},
    verdict_reason: '',
    verdict_decided_by: '',
    verdict_decided_at: null,
    recommended_by: '',
    verified_by_name: '',
    verdict_decided_by_name: '',
    recommended_by_name: '',
    qc_override_by: '',
    qc_override_by_name: '',
    qc_override_at: null,
    qc_override_reason: '',
    rejected_by_name: '',
    resolution_items: EMPTY_RESOLUTION,
    award_amount: null,
    proposed_award_amount: STANDARD_AWARD,
    award_disqualifier: null,
    interview_schedule: {
      enabled: false, status: '', start: null, meeting_url: '', meeting_provider: '',
      booked_slot_id: null, slots: [], reschedule_cutoff_hours: 24,
    },
    decision_reopened_at: null,
    decision_reopen_reason: '',
    last_decision_reopen: null,
    assigned_to_corrections: 0,
    programme_id: 11,
    bursary_agreement_enabled: false,
    bursary_agreement: null,
    disbursements: EMPTY_DISBURSEMENTS,
    maintenance_substate: 'on_track',
    closed_at: null,
    closed_by: '',
    recommended_at: null,
    awarded_at: null,
    active_at: null,
    maintenance_at: null,
  }
}

/** Options for the builder — every field of the payload is overridable, plus the road at the two
 *  stages that have one. An override always wins, so a test that needs one odd value says so in
 *  one line instead of rebuilding the object. */
export interface BuildOptions extends Partial<AdminScholarshipDetail> {
  /** Required at — and permitted only at — `verdict_recorded` and `awaiting_qc`. */
  outcome?: Outcome
}

/**
 * An `AdminScholarshipDetail` at `stage`, carrying what the product would have stamped by then
 * and nothing it would not.
 *
 * Throws on an unknown stage, on an outcome at a stage that has none, and on a missing outcome
 * at a stage that needs one — the same three refusals the backend factory makes, for the same
 * reason: a fixture must SAY which of the two roads it means.
 */
export function buildApplicationDetail(
  stage: Stage, overrides: BuildOptions = {},
): AdminScholarshipDetail {
  if (!(STAGES as readonly string[]).includes(stage)) {
    throw stageError(
      `unknown stage '${stage}'. It builds only states the product can reach; the stages are: `
      + `${STAGES.join(', ')}.`)
  }
  const { outcome, ...fieldOverrides } = overrides
  const hasRoads = (OUTCOME_STAGES as readonly string[]).includes(stage)
  if (outcome !== undefined && !hasRoads) {
    throw stageError(
      `stage '${stage}' takes no outcome (got '${outcome}'). The stages with two roads are: `
      + `${OUTCOME_STAGES.join(', ')} — recommend leaves the verify stamps, decline leaves none.`)
  }
  if (outcome !== undefined && outcome !== 'recommend' && outcome !== 'decline') {
    throw stageError(`unknown outcome '${outcome}'; the two roads to QC are: recommend, decline.`)
  }
  if (outcome === undefined && hasRoads) {
    throw stageError(
      `stage '${stage}' needs an outcome: outcome='recommend' (the verify-accept road, which `
      + `stamps verified_at/verified_by/verify_checklist and locks nric_verified) or `
      + `outcome='decline' (the submit-decline road, which stamps none of them). They are `
      + 'different states and a fixture must say which one it means.')
  }

  // ⚠ A BRANCH DOES NOT INHERIT THE REST OF THE MAIN LINE.
  const leavesAt = BRANCHES[stage] ?? stage
  const passed = MAIN_LINE.slice(0, MAIN_LINE.indexOf(leavesAt) + 1)
  const reached = (name: Stage) => passed.includes(name)
  const declinedRoad = (hasRoads && outcome === 'decline') || stage === 'rejected'

  const app = base()

  if (reached('scored')) {
    app.bucket = 'A'
    app.shortlist_reason = 'STR household'
    app.verdict = buildVerdict()
    app.ai_verdict_snapshot = buildVerdict()
  }
  if (reached('shortlisted')) app.status = 'shortlisted'
  if (reached('profile_complete')) {
    app.status = 'profile_complete'
    app.profile_completed_at = AT
  }
  if (reached('assigned')) {
    app.assigned_to_id = 42
    app.assigned_to_name = REVIEWER_NAME
    app.assigned_at = AT
  }
  if (reached('interviewing')) {
    app.status = 'interviewing'
    app.reporting_date = REPORTING_DATE
    app.interview_session = buildInterviewSession()
  }
  // record-verdict writes the verdict and MOVES NO STATUS. On an approve it also auto-applies
  // the standardised award amount; on a decline it clears one.
  if (reached('verdict_recorded')) {
    app.officer_verdict = { ...(declinedRoad ? DECLINE_VERDICT : RECOMMEND_VERDICT) }
    app.verdict_reason = 'The evidence supports the conclusion recorded here.'
    app.verdict_decided_by = REVIEWER_EMAIL
    app.verdict_decided_by_name = REVIEWER_NAME
    app.verdict_decided_at = AT
    app.award_amount = declinedRoad ? null : STANDARD_AWARD
  }
  // awaiting_qc — the reviewer took ONE of the two roads, and they leave different marks.
  if (reached('awaiting_qc')) {
    app.status = 'interviewed'
    if (!declinedRoad) {
      app.verified_at = AT
      app.verified_by = REVIEWER_EMAIL
      app.verified_by_name = REVIEWER_NAME
      app.verify_checklist = { ...VERIFY_CHECKLIST }
      app.nric_verified = true
    }
    // ⚠ THE DECLINE ROAD STAMPS NOTHING ELSE. No verified_at, no verified_by, no checklist,
    // no NRIC lock — which is why `isStuckAfterVerdict` has to be told the outcome.
  }
  if (reached('recommended')) {
    app.status = 'recommended'
    app.recommended_at = AT
    app.recommended_by = QC_EMAIL
    app.recommended_by_name = QC_NAME
    app.sponsor_profile = buildSponsorProfile()
  }
  if (reached('awarded')) {
    app.status = 'awarded'
    app.awarded_at = AT
  }
  if (reached('active')) {
    app.status = 'active'
    app.active_at = AT
  }
  if (reached('maintenance')) {
    app.status = 'maintenance'
    app.maintenance_at = AT
  }
  if (reached('closed')) {
    app.status = 'closed'
    app.closure_reason = 'graduated'
    app.closed_at = AT
    app.closed_by = 'admin@example.test'
  }
  // expired — the branch off `shortlisted`: the student never completed and the sweep closed it.
  if (stage === 'expired') app.status = 'expired'
  // rejected — the QC confirmed the DECLINE. The decline verdict already cleared award_amount.
  if (stage === 'rejected') {
    app.status = 'rejected'
    app.rejection_category = 'interview'
    app.rejected_at = AT
    app.rejected_by = QC_EMAIL
    app.rejected_by_name = QC_NAME
    app.award_amount = null
    app.pending_rejection_category = 'interview'
    app.decline_due_at = DECLINE_DUE_AT
  }

  return { ...app, ...fieldOverrides }
}
