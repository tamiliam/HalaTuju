/**
 * Asking a student for more, and actioning what comes back.
 *
 * ⚠ `AdminResolutionItem` is one half of a keep-in-sync pair with `ResolutionItem` in
 * `api/resolution.ts`; both are fed by ONE serializer and since TD-266 (2026-10-04) both declare
 * exactly what it sends.
 * drift-test: halatuju-web/src/lib/__tests__/webMirrorDrift.test.ts
 *
 * ⚠ TWO SPANS of the old `admin-api.ts` (1252-1275 and 1854-1882).
 */
import { adminMutate } from './client'
import type { ApiOptions } from './client'
import type { AdminScholarshipDetail } from './applications'

/** Admin-facing resolution item. Mirrors the student-facing ResolutionItem in
 *  src/lib/api/resolution.ts but kept separate — do not cross-import.
 *  Both are read from ONE serializer (`ResolutionItemSerializer`), and the admin payload returns
 *  system + officer + CHECK2 items, so `kind` can be `clarify`/`human` and `source` `check2`.
 *  TD-266 (2026-10-04) brought this copy level with the serializer; the drift test now asserts the
 *  two interfaces are field-for-field identical AND that their keys are the serializer's.
 *  drift-test: halatuju-web/src/lib/__tests__/webMirrorDrift.test.ts */
export interface AdminResolutionItem {
  id: number
  fact: string
  code: string
  // boolean supports flags like `needs_officer_eye` (the circuit-breaker escalation).
  params: Record<string, string | number | boolean | string[]>
  prompt: string
  // 'clarify'/'human' are Check 2 items (an AI student query / a reviewer-only item).
  kind: 'doc' | 'confirm' | 'explanation' | 'clarify' | 'human'
  doc_type: string
  status: string
  source: 'system' | 'officer' | 'check2'
  resolution_text: string
  created_at: string
  resolved_at: string | null
  // Vircle setup task only (served by the serializer for every item; null elsewhere).
  vircle_expected?: 'principal' | 'child' | null
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

