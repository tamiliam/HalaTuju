'use client'

/**
 * THE HIGHER-RESULTS CARD'S OWN FURNITURE — third results route S3a + S3b (2026-10-26, rulings D12/D13).
 *
 * Fetched only when a student's card asks for higher results (`LazyHigherResults`), so the
 * `/scholarship/application` first load — at its budget — pays nothing for an SPM leaver.
 *
 *  - `KindLine` — "Type of results: STPM · Change". READ-ONLY (D13: no type picker): the type is the
 *    results page's, and "Change" opens that page, returning here.
 *  - `HigherChecklist` — the read, in one line ("STPM results. CGPA 3.67, as entered …").
 *  - `HigherNote` — the ONE note the server chose (`higher_check.note`), in the help-coach style with
 *    one action. Never a block (D13):
 *      (D) an SPM slip in this card → "Move it to SPM results slip" (re-filed, file kept), and for the
 *          rare case "Don't have …?" → the "Continue with SPM results only" confirm box;
 *      (B) another higher kind → "Update your results";  (C) differences → "Correct your … results".
 */
import { useState } from 'react'
import { useRouter } from 'next/navigation'

import { continueWithSpmOnly, refileToSpm, type ApplicantDocument, type HigherCheck } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { resultsEditPath } from '@/lib/qualification'
import { clearHigherResultsLocally } from '@/lib/resultsLocal'
import { setOnboardingReturn } from '@/lib/scholarship'

const RETURN_TO = '/scholarship/application'
const linkCls = 'inline-flex items-center gap-1 text-sm font-semibold text-primary-700 underline underline-offset-2 hover:text-primary-800'

function useKindLabel() {
  const { t } = useT()
  return (k: string) => (k ? t(`documentsTab.higher.kind.${k}`) : '')
}

function goToResults(router: ReturnType<typeof useRouter>, path: string) {
  setOnboardingReturn(RETURN_TO)
  router.push(path)
}

export function KindLine({ kind, spmOnly = false }: { kind: string; spmOnly?: boolean }) {
  const { t } = useT()
  const label = useKindLabel()
  const router = useRouter()
  // Owner ruling 2026-10-26: SPM results only + a degree chosen → the card is required; say why,
  // with the two ways out (enter higher results, or choose a post-SPM pathway).
  if (!kind && spmOnly) {
    return (
      <div className="text-xs text-ground-600 mt-1">
        <p>{t('documentsTab.higher.spmOnlyHelp')}</p>
        <p className="mt-1 flex flex-wrap gap-x-3">
          <button type="button" className="text-primary-600 hover:underline"
            onClick={() => goToResults(router, '/onboarding/exam-type')}>
            {t('documentsTab.higher.updateResults')}
          </button>
          <button type="button" className="text-primary-600 hover:underline"
            onClick={() => router.push('/profile#pathway')}>
            {t('documentsTab.higher.choosePathway')}
          </button>
        </p>
      </div>
    )
  }
  if (!kind) return null
  return (
    <p className="text-xs text-ground-600 mt-1">
      {t('documentsTab.higher.typeLabel')} <span className="font-medium text-ground-800">{label(kind)}</span>
      {' · '}
      <button type="button" className="text-primary-600 hover:underline"
        onClick={() => goToResults(router, resultsEditPath(kind))}>
        {t('documentsTab.higher.change')}
      </button>
    </p>
  )
}

/**
 * The read, in ONE line (the approved mock): clean → "STPM results. CGPA 3.67, as entered on your
 * application."; another person's name / an unreadable copy → that, plainly. Nothing while unread,
 * and nothing when a note speaks instead (the note IS the line then).
 */
export function HigherChecklist({ chk }: { chk: HigherCheck }) {
  const { t } = useT()
  const label = useKindLabel()
  if (chk.note) return null
  let line = ''
  if (chk.name === 'mismatch') line = t('documentsTab.higher.nameMismatch')
  else if (chk.readable === false) line = t('documentsTab.higher.unreadable')
  else if (chk.kind_status === 'match' && chk.cgpa_status === 'match' && chk.cgpa_slip != null)
    line = t('documentsTab.higher.readOk', { kind: label(chk.kind_held), cgpa: chk.cgpa_slip.toFixed(2) })
  if (!line) return null
  const bad = chk.name === 'mismatch' || chk.readable === false
  return <p className={`mt-2 text-xs ${bad ? 'text-critical-600' : 'text-positive-700'}`}>{line}</p>
}

export function HigherNote({ doc, chk, token, onChanged }: {
  doc: ApplicantDocument; chk: HigherCheck; token: string | null; onChanged?: () => void
}) {
  const { t } = useT()
  const label = useKindLabel()
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [failed, setFailed] = useState(false)
  if (!chk.note) return null
  const held = label(chk.kind_held)

  const refile = async () => {
    if (!token) return
    setBusy(true); setFailed(false)
    try { await refileToSpm(doc.id, { token }); onChanged?.() } catch { setFailed(true) } finally { setBusy(false) }
  }
  const spmOnly = async () => {
    if (!token) return
    setBusy(true); setFailed(false)
    try {
      await continueWithSpmOnly(doc.id, { token })
      try { clearHigherResultsLocally(localStorage) } catch { /* storage blocked — the server is the record */ }
      router.push('/profile#pathway')
    } catch { setFailed(true); setBusy(false) }
  }

  const body = chk.note === 'spm_slip'
    ? t('documentsTab.higher.note.spmSlip', { kind: held })
    : chk.note === 'kind_differs'
      ? t('documentsTab.higher.note.kindDiffers', { seen: label(chk.kind_detected), held })
      : t('documentsTab.higher.note.gradesDiffer')

  return (
    <div className="mt-2 rounded-xl bg-primary-50 ring-1 ring-primary-100 p-3">
      <p className="text-sm leading-relaxed text-primary-900/90">{body}</p>
      {chk.note === 'spm_slip' ? (chk.actions_open === false ? null : (
        <>
          <button type="button" disabled={busy} onClick={refile} className={`mt-1.5 ${linkCls} disabled:opacity-50`}>
            {t('documentsTab.higher.moveToSpm')}<span aria-hidden>→</span>
          </button>
          <p className="mt-1">
            <button type="button" disabled={busy} onClick={() => setConfirming(true)}
              className="text-xs text-ground-500 underline underline-offset-2 hover:text-ground-700">
              {t('documentsTab.higher.noHigher')}
            </button>
          </p>
        </>
      )) : (
        <button type="button" onClick={() => goToResults(router, chk.note_path || resultsEditPath(chk.kind_held))}
          className={`mt-1.5 ${linkCls}`}>
          {chk.note === 'kind_differs'
            ? t('documentsTab.higher.updateResults')
            : t('documentsTab.higher.correctResults', { kind: held })}
          <span aria-hidden>→</span>
        </button>
      )}
      {failed && <p className="mt-1 text-xs text-critical-600">{t('verifyEmail.networkError')}</p>}
      {confirming && (
        <div role="alertdialog" aria-modal="true" aria-labelledby="spm-only-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-ground-900/40 px-4">
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
            <h2 id="spm-only-title" className="text-base font-semibold text-ground-900">
              {t('documentsTab.higher.confirm.title')}
            </h2>
            <p className="mt-1 text-sm text-ground-600">{t('documentsTab.higher.confirm.intro')}</p>
            <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-ground-700">
              <li>{t('documentsTab.higher.confirm.removed', { kind: held })}</li>
              <li>{t('documentsTab.higher.confirm.pathway')}</li>
              <li>{t('documentsTab.higher.confirm.reviewer')}</li>
            </ul>
            <div className="mt-5 flex justify-end gap-3">
              <button type="button" onClick={() => setConfirming(false)} disabled={busy}
                className="rounded-lg border border-ground-300 px-4 py-2 text-sm font-medium text-ground-700 hover:bg-ground-50">
                {t('documentsTab.higher.confirm.cancel')}
              </button>
              <button type="button" onClick={spmOnly} disabled={busy}
                className="rounded-lg bg-brand-fill px-4 py-2 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {t('documentsTab.higher.confirm.go')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
