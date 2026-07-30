/**
 * How a screenshot gets INTO a request — the one home for the rule, shared by both surfaces.
 *
 * There are TWO places a screenshot enters the system and they cannot share a component:
 *   * the request DETAIL page, via `components/OrgRequestAttachments.tsx`, which uploads
 *     immediately against an existing request id;
 *   * the request CREATE form, inline in `app/admin/requests/page.tsx`, which STAGES `File`
 *     objects because there is no request id to attach them to until the request exists.
 *
 * That difference is real and unavoidable. What is NOT unavoidable is each of them having its own
 * copy of "which files count and what do we call a pasted one" — when paste and drag-and-drop
 * shipped on 2026-07-30 they landed on the detail page only, and the create form (where a
 * screenshot most naturally starts life: Win+Shift+S, then Ctrl+V into the form you are typing)
 * kept accepting uploads alone. The owner had to report it twice.
 *
 * So the rule lives here and both import it. `screenshotInput.test.ts` additionally asserts that
 * BOTH surfaces wire up paste and drop, because a shared helper nothing calls is no protection.
 */

/**
 * A pasted image has NO filename — the clipboard carries bytes and a mime type only. Both
 * surfaces render the name (as a caption, and stored as `original_filename`), so an unnamed file
 * shows as blank. Give it one.
 */
export function namedForPaste(file: File): File {
  if (file.name) return file
  const ext = (file.type.split('/')[1] || 'png').replace('jpeg', 'jpg')
  return new File([file], `screenshot-${Date.now()}.${ext}`, { type: file.type })
}

/**
 * Images only, each guaranteed a name. Paste and drop both carry arbitrary content — a dragged
 * PDF, a dragged folder, a copied block of text — so the filter is not optional here. The server
 * refuses non-images too (`org_requests.is_allowed_attachment`); this keeps the UI honest before
 * a round trip rather than replacing that check.
 */
export function imagesFrom(list: FileList | null | undefined): File[] {
  return Array.from(list || []).filter((f) => f.type.startsWith('image/')).map(namedForPaste)
}
