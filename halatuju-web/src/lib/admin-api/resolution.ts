/**
 * Asking a student for more, and actioning what comes back.
 *
 * ⚠ `AdminResolutionItem` is one half of a keep-in-sync pair with `ResolutionItem` in
 * `api/resolution.ts`, and the two have fallen out of step (TD-266).
 * drift-test: halatuju-web/src/lib/__tests__/webMirrorDrift.test.ts
 *
 * ⚠ TWO SPANS of the old `admin-api.ts` (1252-1275 and 1854-1882).
 */
import { adminMutate } from './client'
import type { ApiOptions } from './client'
import type { AdminScholarshipDetail } from './applications'

/** Admin-facing resolution item. Mirrors the student-facing ResolutionItem in
 *  src/lib/api.ts but kept separate — do not cross-import.
 *  ⚠ THE COPY IS STALE, and both are fed by ONE serializer (`ResolutionItemSerializer`): the admin
 *  payload returns system + officer + CHECK2 items, so `kind` can be `clarify`/`human`, `source`
 *  can be `check2`, and `vircle_expected` is always sent. None of the three is declared here.
 *  Pinned, not fixed — narrowing or widening a type the cockpit reads changes what that screen can
 *  render (TD-266; the end state is to delete one side).
 *  drift-test: halatuju-web/src/lib/__tests__/webMirrorDrift.test.ts */
export interface AdminResolutionItem {
  id: number
  fact: string
  code: string
  // boolean supports flags like `needs_officer_eye` (the circuit-breaker escalation).
  params: Record<string, string | number | boolean | string[]>
  prompt: string
  kind: 'doc' | 'confirm' | 'explanation'
  doc_type: string
  status: string
  source: 'system' | 'officer'
  resolution_text: string
  created_at: string
  resolved_at: string | null
}

/** Coordinator raises a new resolution item (free-text or doc request) for the
 *  student's Action Centre. */
export async function raiseResolutionItem(
  id: number,
  payload: { kind: 'doc' | 'confirm' | 'explanation'; prompt: string; doc_type?: string; fact?: string; household_member?: string },
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/resolution-items/`,
    'POST',
    payload,
    options,
  )
}

/** Waive, resolve, or reopen ("Ask again") a resolution item on behalf of the coordinator. */
export async function actionResolutionItem(
  itemId: number,
  action: 'waive' | 'resolve' | 'reopen',
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/resolution-items/${itemId}/${action}/`,
    'POST',
    {},
    options,
  )
}

