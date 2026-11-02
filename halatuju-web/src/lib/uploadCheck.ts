/**
 * The browser's EARLY refusal of a file the server would refuse anyway — too big for the
 * organisation's served limit, or not a photo / PDF (TD-080). One rule for every student upload
 * surface: the documents tab and the Action Centre (Mobile M4 — the Action Centre used to send any
 * file and let the server refuse it after the upload). The server's allowlist stays the real guard.
 */
import { limitsFrom, type ResolvedDocumentLimits } from './documentLimits'
import type { DocumentLimits } from './api'

// Accept images + PDF only — the API's own allowlist (`_is_allowed_upload`, TD-080), kept in step by a
// test that reads it. drift-test: halatuju-web/src/lib/__tests__/uploadCheckDrift.test.ts
const ACCEPTED_UPLOAD_EXT = /\.(pdf|jpe?g|png|gif|bmp|webp|tiff?|heic|heif)$/i

export function isAcceptedUpload(file: File): boolean {
  const mime = (file.type || '').toLowerCase()
  if (mime.startsWith('image/') || mime === 'application/pdf') return true
  return ACCEPTED_UPLOAD_EXT.test(file.name || '')
}

/** The message (key + params) to show instead of uploading, or null when the file may go. */
export function uploadRefusal(file: File, limits: ResolvedDocumentLimits):
  { key: string; params?: Record<string, string> } | null {
  if (file.size > limits.maxDocSizeBytes) {
    return { key: 'scholarship.docs.file_too_large', params: { mb: String(limits.maxDocSizeMb) } }
  }
  if (!isAcceptedUpload(file)) return { key: 'scholarship.docs.unsupportedFormat' }
  return null
}

/** The same refusal from the SERVED limits (a missing field falls back per field). The Action Centre
 *  loads this module only when a file is picked, so the check rides in no route's first load (M4: the
 *  /scholarship/application line); if the module cannot load, the server's own refusal still stands. */
export function refusalFor(file: File, served?: DocumentLimits | null) {
  return uploadRefusal(file, limitsFrom(served))
}
