'use client'

import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import DocViewer, { type ViewerDoc } from '@/components/DocViewer'
import { getScholarContract, type ScholarContract as ContractPayload } from '@/lib/admin-api'

const CARD = 'rounded-xl border border-ground-200 bg-ground-0 p-5'

/**
 * The scholar file's Contract tab (student maintenance S5a). Design of record: the canvas file's
 * Contract card — "Signed and executed <date>", the parties, View signed PDF.
 *
 * ⚠ PLATFORM-SIGNED ONLY (owner ruling, 2026-10-29): the server sends a COUNTERSIGNED agreement (the
 * witness is non-blocking) or `{exists: false}` → "No contract on file" — never a scan, never a draft.
 * The line says "Countersigned by the organisation" until the witness signs, then "Signed and
 * executed" — the same words as the Overview card.
 * ⚠ NO LINK ON THE FIRST READ. "View signed PDF" asks for a five-minute link only when clicked, and
 * a fresh one each time, so a tab left open for an hour still opens it. No IC number is ever sent.
 */
export default function ScholarContract({ id, token }: { id: number; token: string | null }) {
  const { t } = useT()
  const [data, setData] = useState<ContractPayload | null>(null)
  const [failed, setFailed] = useState(false)
  const [viewing, setViewing] = useState<ViewerDoc | null>(null)
  const [opening, setOpening] = useState(false)

  const [noPdf, setNoPdf] = useState(false)

  useEffect(() => {
    if (!token) return
    getScholarContract(id, { token })
      .then((d) => { setData(d); setFailed(false) })
      .catch(() => setFailed(true))
  }, [id, token])

  const open = async () => {
    if (!token) return
    setOpening(true)
    try {
      const fresh = await getScholarContract(id, { token, link: true })
      setFailed(false)
      if (fresh.exists && fresh.pdf_url) {
        setNoPdf(false)
        setViewing({ label: t('admin.scholars.card.contract'), filename: 'agreement.pdf', url: fresh.pdf_url, kind: 'pdf' })
      } else {
        setNoPdf(true)            // the button stays: try again
      }
    } catch { setFailed(true) } finally { setOpening(false) }
  }

  if (!data && !failed) return <p className="text-sm text-ground-400">{t('common.loading')}</p>

  return (
    <section className={CARD} aria-label={t('admin.scholars.card.contract')}>
      <h2 className="text-base font-semibold text-ground-900">{t('admin.scholars.card.contract')}</h2>
      {failed && <p className="mt-2 text-sm text-critical-600">{t('admin.scholars.contractTab.loadFailed')}</p>}
      {data && !data.exists && (
        <p className="mt-2 text-sm text-ground-600" data-testid="contract-none">{t('admin.scholars.contract.none')}</p>
      )}
      {data && data.exists && (
        <>
          <p className="mt-2 text-sm font-medium text-positive-700" data-testid="contract-executed">
            {t(data.witnessed ? 'admin.scholars.contractTab.executedOn' : 'admin.scholars.contractTab.countersignedOn',
              { date: data.executed_on ? formatDate(data.executed_on) : '—' })}
          </p>
          <ul className="mt-3 divide-y divide-ground-100 text-sm" data-testid="contract-parties">
            {data.parties.map((p) => (
              <li key={p.role} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
                <span>
                  <span className="text-ground-500">{t(`admin.scholars.contractTab.role.${p.role}`)}</span>
                  <span className="ml-2 font-medium text-ground-900">{p.name || '—'}</span>
                  {(p.relationship || p.title || p.organisation) && (
                    <span className="ml-2 text-xs text-ground-500">{p.relationship || p.title || p.organisation}</span>
                  )}
                </span>
                <span className="text-xs text-ground-500">{p.signed_on ? formatDate(p.signed_on) : '—'}</span>
              </li>
            ))}
          </ul>
          <button type="button" onClick={open} disabled={opening}
            className="mt-4 rounded-lg border border-ground-300 px-3 py-1.5 text-sm font-medium text-primary-600 hover:bg-ground-50 disabled:opacity-50">
            {t('admin.scholars.contractTab.viewPdf')}
          </button>
          {noPdf && <p className="mt-1 text-xs text-ground-500" data-testid="contract-no-pdf">{t('admin.scholars.contractTab.noPdf')}</p>}
        </>
      )}
      <DocViewer doc={viewing} onClose={() => setViewing(null)} />
    </section>
  )
}
