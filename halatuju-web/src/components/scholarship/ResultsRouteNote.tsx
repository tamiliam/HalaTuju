'use client'

/**
 * Step 3's two results notes (TD-773), drawn under the results card on /scholarship/apply.
 *
 * * `needsPostSpm` - a caution box: the gift needs results from after SPM and this student holds SPM
 *   only. It names the card's own "Results wrong? Edit them" link (passed in the language on
 *   screen, so the two always match). No button, and it never blocks Continue.
 * * `pngkOnly` - a small blue note: the gift judges each student on their own results, so every
 *   post-SPM holder (STPM, Matriculation, Asasi, Diploma) is judged on the PNGK, not the SPM grades.
 *
 * Display only: which note shows is the server's `results_routes` (read from the criteria tree the
 * gate reads); nothing here changes a verdict.
 *
 * Its words live under `documentsTab.resultsNote.*` in the Documents slice, which travels with
 * THIS chunk (`LazyResultsRouteNote`), not with the apply page's first-load JS.
 */
import { useT } from '@/lib/i18n'
import '@/lib/messagesDocuments'
import { loadCatalogue } from '@/lib/messages'

export type ResultsNoteKind = 'needsPostSpm' | 'pngkOnly'

/** Resolves once the on-screen language holds the Documents slice (English always does); never rejects. */
export async function wordsReady(locale: string | undefined): Promise<void> {
  if (!locale || locale === 'en') return
  try { await loadCatalogue(locale as Parameters<typeof loadCatalogue>[0]) } catch { /* English fallback */ }
}

export default function ResultsRouteNote({ kind }: { kind: ResultsNoteKind }) {
  const { t } = useT()
  if (kind === 'needsPostSpm') {
    return (
      <div role="note" data-results-note="needsPostSpm"
        className="mt-4 flex gap-3 rounded-xl border border-caution-200 bg-caution-50 p-4 text-left">
        <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-caution-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        <div className="space-y-1.5">
          <p className="font-medium text-ground-900">{t('documentsTab.resultsNote.postSpmTitle')}</p>
          <p className="text-sm text-ground-700">{t('documentsTab.resultsNote.postSpmBody')}</p>
          <p className="text-sm text-ground-700">
            {t('documentsTab.resultsNote.postSpmAdd', { link: t('scholarship.apply.resultsWrong') })}
          </p>
        </div>
      </div>
    )
  }
  return (
    <p role="note" data-results-note={kind}
      className="mt-3 rounded-lg border border-info-200 bg-info-50 px-3 py-2 text-sm text-info-800">
      {t(`documentsTab.resultsNote.${kind}`)}
    </p>
  )
}
