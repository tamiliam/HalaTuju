'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { getBursaryContract, type BursaryContract as ContractPayload } from '@/lib/api'

/**
 * Her contract on My Bursary (student maintenance S5b): the Overview's "Your contract" card
 * (`compact`) and the Contract tab. Design of record: the MyBursary board — "Signed <date>", View PDF.
 *
 * ⚠ PLATFORM-SIGNED ONLY: the server sends a countersigned agreement (the witness is optional) or
 * `{exists: false}` → "No contract on file". No IC number is ever in the payload.
 * ⚠ NO LINK UNTIL SHE ASKS: "View PDF" fetches a five-minute link on the click (`link: true`), a fresh
 * one each time, and the button stays usable if a try fails.
 * ⚠ A NEW TAB, NOT THE STAFF `DocViewer` (its words live in the admin message slice, which this page
 * never loads). The tab is opened SYNCHRONOUSLY on the click and pointed at the link once it arrives,
 * so a phone's pop-up blocker does not swallow it; a failed fetch closes it again. If the browser blocks
 * it anyway (`window.open` returns null) the page is NEVER navigated away — she gets a link to tap.
 */
export default function BursaryContract({ contract, token, compact = false }: {
  contract: ContractPayload
  token: string | null
  compact?: boolean
}) {
  const { t } = useT()
  const [opening, setOpening] = useState(false)
  const [noPdf, setNoPdf] = useState(false)
  // A blocked pop-up (window.open returned null): the fresh link, for her to tap (review L6).
  const [fallback, setFallback] = useState<string | null>(null)

  const open = async () => {
    if (!token) return
    setOpening(true)
    const tab = window.open('', '_blank')
    try {
      const fresh = await getBursaryContract({ token, link: true })
      if (fresh.exists && fresh.pdf_url) {
        setNoPdf(false)
        if (tab) { tab.opener = null; tab.location.href = fresh.pdf_url; setFallback(null) } else setFallback(fresh.pdf_url)
      } else {
        tab?.close()
        setNoPdf(true)
      }
    } catch { tab?.close(); setNoPdf(true) } finally { setOpening(false) }
  }

  return (
    <section className="rounded-2xl bg-ground-0 p-5 shadow-sm" data-testid={compact ? 'bursary-contract-card' : 'bursary-contract-tab'}>
      <h2 className="text-lg font-bold text-ground-900">{t('bursaryTabs.contract.title')}</h2>
      {!contract.exists ? (
        <p className="mt-2 text-sm text-ground-600" data-testid="contract-none">{t('bursaryTabs.contract.none')}</p>
      ) : (
        <>
          <p className="mt-2 text-sm text-ground-700" data-testid="contract-signed">
            {t(contract.witnessed ? 'bursaryTabs.contract.signed' : 'bursaryTabs.contract.countersigned',
              { date: contract.executed_on ? formatDate(contract.executed_on) : '—' })}
          </p>
          {!compact && (
            <ul className="mt-3 divide-y divide-ground-100 text-sm" data-testid="contract-parties">
              {contract.parties.map((p) => (
                <li key={p.role} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
                  <span>
                    <span className="text-ground-500">{t(`bursaryTabs.contract.role.${p.role}`)}</span>
                    <span className="ml-2 font-medium text-ground-900">{p.name || '—'}</span>
                  </span>
                  <span className="text-xs text-ground-500">{p.signed_on ? formatDate(p.signed_on) : '—'}</span>
                </li>
              ))}
            </ul>
          )}
          <button type="button" onClick={open} disabled={opening}
            className="mt-3 h-11 self-start rounded-xl border border-ground-300 bg-ground-0 px-4 text-sm font-medium text-ground-800 disabled:opacity-50">
            {t('bursaryTabs.contract.viewPdf')}
          </button>
          {noPdf && <p className="mt-1 text-xs text-ground-500" data-testid="contract-no-pdf">{t('bursaryTabs.contract.noPdf')}</p>}
          {fallback && (
            <a href={fallback} target="_blank" rel="noopener noreferrer" data-testid="contract-pdf-link"
              className="mt-2 text-sm font-medium text-primary-600 underline">{t('bursaryTabs.contract.openPdf')}</a>
          )}
        </>
      )}
    </section>
  )
}
