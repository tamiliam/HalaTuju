/** The organisation's document-upload limits, as SERVED on the document list.
 *
 *  ⚠ THE LIMITS ARE SERVED, NOT MIRRORED (Org Config Sprint E). `ScholarshipDocuments` used to
 *  carry its own `MAX_DOC_SIZE_BYTES = 8 * 1024 * 1024` under a comment saying the server was
 *  authoritative — true, and beside the point: the browser still had to know the number to warn
 *  a student BEFORE a doomed upload, and a copy cannot be right for more than one tenant.
 *
 *  The constants below are the PLATFORM DEFAULT only — what a payload that predates the fields
 *  falls back to, per field. Do not read them where a payload is in hand.
 */
import type { DocumentLimits } from './api'

export const DEFAULT_MAX_DOC_SIZE_MB = 8
export const DEFAULT_MAX_DOCS_PER_APPLICATION = 40
export const DEFAULT_MAX_OTHER_DOCS = 10

export interface ResolvedDocumentLimits {
  maxDocSizeMb: number
  maxDocSizeBytes: number
  maxDocsPerApplication: number
  maxOtherDocs: number
}

/** Read the served limits, falling back per FIELD.
 *
 *  Per field, not per object: a payload carrying only some of them still contributes what it
 *  has, and a nonsense value (0 or negative — every upload would be "too large") is refused on
 *  its own rather than discarding the good numbers beside it. */
export function limitsFrom(served?: DocumentLimits | null): ResolvedDocumentLimits {
  const num = (v: number | undefined, fallback: number) =>
    (typeof v === 'number' && Number.isFinite(v) && v >= 1 ? v : fallback)
  const mb = num(served?.max_doc_size_mb, DEFAULT_MAX_DOC_SIZE_MB)
  return {
    maxDocSizeMb: mb,
    // The SAME arithmetic the server does (`org_config.max_doc_size_bytes`), so the browser's
    // early warning and the server's refusal land on the same byte.
    maxDocSizeBytes: mb * 1024 * 1024,
    maxDocsPerApplication: num(served?.max_docs_per_application, DEFAULT_MAX_DOCS_PER_APPLICATION),
    maxOtherDocs: num(served?.max_other_docs, DEFAULT_MAX_OTHER_DOCS),
  }
}
