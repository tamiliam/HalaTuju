/**
 * The Malay pre-U track/stream label, for the officer cockpit.
 *
 * ⚠ **THIS MODULE EXISTS TO CONFINE `ms.json` TO THE ONE SCREEN THAT NEEDS IT.** (Code health
 * H17, 2026-09-20.) These sixteen labels are the only thing in the whole application that reads a
 * message catalogue for a language the reader did not choose, and they lived in
 * `lib/scholarship.ts` — a module fifteen route pages import. One static `import ms.json` there
 * put 393 kB of Malay into the first load of almost every page in the product, for a cockpit
 * label an applicant never sees. Moved here, it is paid for by `/admin/scholarship/[id]` alone.
 *
 * ⚠ **THE LABELS ARE STILL SOURCED FROM `ms.json`, NOT COPIED OUT OF IT.** A second hardcoded
 * copy is the `_SUBJECT_BM` ↔ `subjects.ts` drift trap that `lessons.md` records three times, and
 * the backend's `card_display._TRACK_LABEL` already has a cross-runtime parity guard against this
 * exact block (`apps/scholarship/tests/test_card_display.TestTrackLabelParity`, which reads
 * `src/messages/ms.json` by path). What moved is the import, not the source of truth.
 *
 * ⚠ **DO NOT MAKE THIS LAZY.** The cockpit calls it during render, for an officer who is usually
 * reading English, so there is no catalogue in memory to answer from and no loading state to hang
 * the label off. Returning `null` until a chunk arrives would blank a label the officer is
 * reading. The honest cost is written down instead: TD-280.
 */
import msMessages from '@/messages/ms.json'

/** Malay-only label for a pre-U track/stream code (STPM stream OR Matriculation track). The apply
 * form shows these bilingually ("Social Science (Sains Sosial)") for the student; the officer
 * cockpit shows the Malay term only (owner 2026-07-18). Sourced from the SAME i18n messages the
 * apply form uses — the Malay (`ms`) values under `scholarship.apply.plan.stream` / `.track` — so
 * there is one FE home for these labels, not a second hardcoded copy. `stream` (STPM) is checked
 * before `track` (matric); they share `sains` with the same value. Null for an unknown code. */
const _msPreUPlan = (msMessages as {
  scholarship?: { apply?: { plan?: {
    stream?: Record<string, string>
    track?: Record<string, string>
  } } }
}).scholarship?.apply?.plan
export function preUTrackMalay(code: string | null | undefined): string | null {
  if (!code) return null
  return _msPreUPlan?.stream?.[code] ?? _msPreUPlan?.track?.[code] ?? null
}
