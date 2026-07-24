/**
 * Single source of truth for an OrgRequest's status VOCABULARY on the Requests-space admin
 * surface (Sprint 15): one label (via i18n key) and one tone per status, plus the pure
 * decision `requestActionsFor` that both the list and the detail page read for action visibility.
 *
 * Mirrors applicationStatus.ts: a PURE module (no React, no i18n import) that returns i18n KEYS;
 * the caller does `t(...)`. requestStatus.test.ts fails if a page invents its own status→label or
 * status→colour map, or if the action rules here drift from the backend org_requests.TRANSITIONS
 * table.
 *
 * KEEP IN STEP with halatuju_api/apps/scholarship/org_requests.py — the model STATUS_CHOICES and
 * the transition/actor matrix. The FE reads the payload and this pure helper; it never re-encodes
 * a business rule the server doesn't also enforce (the server is authoritative — this only decides
 * which BUTTONS to show).
 */

/** The 8 statuses in flow order. Mirrors OrgRequest.STATUS_CHOICES in models.py. */
export const REQUEST_STATUSES = [
  'submitted',
  'triaged',
  'quoted',
  'approved',
  'deferred',
  'scheduled',
  'done',
  'declined',
] as const

export type RequestStatus = (typeof REQUEST_STATUSES)[number]

/** Tailwind tone per status — complete literal class names (JIT can't see runtime-assembled ones). */
const STATUS_TONE: Record<string, string> = {
  // Awaiting a decision / in the review loop — blue ramp.
  submitted: 'bg-blue-50 text-blue-700',
  triaged: 'bg-blue-100 text-blue-700',
  quoted: 'bg-blue-200 text-blue-800',
  // Committed — green.
  approved: 'bg-green-100 text-green-800',
  scheduled: 'bg-green-200 text-green-900',
  done: 'bg-green-300 text-green-900',
  // Parked — amber (needs the org's attention to un-park).
  deferred: 'bg-amber-100 text-amber-700',
  // Ended — grey.
  declined: 'bg-gray-100 text-gray-600',
}

const DEFAULT_TONE = 'bg-gray-100 text-gray-600'

/** i18n key for a status label. */
export function statusLabelKey(status: string): string {
  return `admin.requests.status.${status}`
}

/** Tailwind tone classes for a status, with a safe grey default. */
export function statusTone(status: string): string {
  return STATUS_TONE[status] || DEFAULT_TONE
}

/** Whether a status has an EXPLICIT tone (membership, not "differs from grey"). */
export function hasStatusTone(status: string): boolean {
  return Object.prototype.hasOwnProperty.call(STATUS_TONE, status)
}

/** i18n key for a kind label ('bug' | 'feature'). */
export function kindLabelKey(kind: string): string {
  return `admin.requests.kind.${kind}`
}

/** i18n key for a lane label ('small_change' | 'sprint'). */
export function laneLabelKey(lane: string): string {
  return `admin.requests.lane.${lane}`
}

export type RequestRole = 'super' | 'org_admin'

/** Every action the two pages can render. */
export type RequestAction =
  | 'answer' | 'accept' | 'defer' | 'modify' | 'withdraw'       // requestee (org_admin)
  | 'triage' | 'quote' | 'requote' | 'schedule' | 'done' | 'decline' | 'ai_rerun'  // owner (super)

/**
 * Which actions to OFFER, given the caller's role, the request status, the OWNER's triaged kind
 * (the authoritative kind once triaged; '' before), and whether an unanswered clarifying question
 * is waiting. The server re-gates every one of these — this only decides what to show.
 *
 * Mirrors org_requests.TRANSITIONS + the actor rules:
 *   org_admin (requestee) — answer (submitted/triaged, question waiting); accept (quoted/deferred);
 *     defer (quoted); modify (quoted/deferred); withdraw (submitted/triaged/quoted/deferred).
 *   super (owner) — triage (submitted); quote (triaged + feature); schedule (triaged + bug, or
 *     approved); requote (deferred); done (scheduled); decline (submitted/triaged/quoted/deferred);
 *     ai_rerun (submitted/triaged).
 */
export function requestActionsFor(
  role: RequestRole,
  status: string,
  triagedKind: string,
  hasUnansweredQuestions: boolean,
): RequestAction[] {
  const out: RequestAction[] = []
  if (role === 'org_admin') {
    if (hasUnansweredQuestions && (status === 'submitted' || status === 'triaged')) out.push('answer')
    if (status === 'quoted' || status === 'deferred') out.push('accept')
    if (status === 'quoted') out.push('defer')
    if (status === 'quoted' || status === 'deferred') out.push('modify')
    if (['submitted', 'triaged', 'quoted', 'deferred'].includes(status)) out.push('withdraw')
    return out
  }
  // super (owner)
  if (status === 'submitted') out.push('triage')
  if (status === 'triaged' && triagedKind === 'feature') out.push('quote')
  if ((status === 'triaged' && triagedKind === 'bug') || status === 'approved') out.push('schedule')
  if (status === 'deferred') out.push('requote')
  if (status === 'scheduled') out.push('done')
  if (['submitted', 'triaged', 'quoted', 'deferred'].includes(status)) out.push('decline')
  if (status === 'submitted' || status === 'triaged') out.push('ai_rerun')
  return out
}

/**
 * The Requests COMPONENT tree (Sprint 15.1) — the FE mirror of models.REQUEST_COMPONENT_TREE.
 * A parent is a top-level admin surface; the only parent carrying sub-components is `applications`
 * (the B40 pipeline stages). A sub-component's stored VALUE is `${parent}_${sub}` (underscore — a
 * dot breaks the nested i18n lookup). Students + Course Data are deliberately ABSENT (super-only
 * surfaces, removed in 15.1). test_org_requests pins this against VALID_COMPONENTS + the i18n keys.
 */
export const REQUEST_COMPONENT_TREE: Record<string, readonly string[]> = {
  applications: [
    'student_details', 'documents', 'ai_prediction', 'queries', 'interview',
    'decision', 'agreement', 'student_profile',
  ],
  sponsors: [],
  payments: [],
  contracts: [],
  sources: [],
  administration: [],
  access: [],
  other: [],
}

/** The parent surfaces, in display order (the top-level select options). */
export const REQUEST_COMPONENT_PARENTS = Object.keys(REQUEST_COMPONENT_TREE)

/** The child sub-component VALUES (`${parent}_${sub}`) for a parent — [] when it has no children. */
export function requestSubComponents(parent: string): string[] {
  return (REQUEST_COMPONENT_TREE[parent] || []).map((sub) => `${parent}_${sub}`)
}

/** i18n key for a component value (parent OR `${parent}_${sub}` — the nested lookup works for both). */
export function componentLabelKey(value: string): string {
  return `admin.requests.component.${value}`
}

/** Every valid component VALUE (parents + `${parent}_${sub}` children). Mirrors VALID_COMPONENTS. */
export const REQUEST_COMPONENT_VALUES = REQUEST_COMPONENT_PARENTS.flatMap(
  (parent) => [parent, ...requestSubComponents(parent)],
)

/** True if the request carries an unanswered clarifying question (a clarification with a
 *  question and no answer). Used by the list badge + the detail answer box. */
export function hasUnansweredQuestions(
  clarifications: Array<{ question?: string | null; answer?: string | null }> | null | undefined,
): boolean {
  return (clarifications || []).some((c) => c.question && !c.answer)
}
