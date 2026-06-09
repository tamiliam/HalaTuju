/**
 * Pure helpers for the shared <Pagination> control.
 *
 * Kept separate from the component so the windowing logic is unit-testable
 * without rendering React.
 */

/**
 * Build a compact, windowed page list: always first + last + current ±1, with
 * a `'gap'` marker standing in for any skipped run. Keeps the control small
 * even with hundreds of pages.
 *
 * Examples (page/totalPages → result):
 *   3 / 3   → [1, 2, 3]
 *   1 / 10  → [1, 2, 'gap', 10]
 *   5 / 10  → [1, 'gap', 4, 5, 6, 'gap', 10]
 *   10 / 10 → [1, 'gap', 9, 10]
 */
export function pageWindow(page: number, totalPages: number): (number | 'gap')[] {
  const wanted = new Set([1, totalPages, page, page - 1, page + 1])
  const shown = Array.from(wanted)
    .filter((p) => p >= 1 && p <= totalPages)
    .sort((a, b) => a - b)
  const out: (number | 'gap')[] = []
  let prev = 0
  for (const p of shown) {
    if (prev && p - prev > 1) out.push('gap')
    out.push(p)
    prev = p
  }
  return out
}
