'use client'

import { useEffect, useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { refusalKey } from '@/lib/sourceConsole'
import DocViewer, { type ViewerDoc } from '@/components/DocViewer'
import RecordState from '@/components/admin/RecordState'
import { inputCls } from '@/components/admin/StaffAdmin'
import { getSourceAgreement, witnessAsSource, type SourceAgreement } from '@/lib/admin-api'
import { CARD, ContractParties, K, useSourceName } from './shared'

const W = `${K}.witness`

/**
 * The witness step (source sign-in S4, roadmap C13): the witness source reads the full contract and
 * records its witness — a typed full name and the declaration tick, nothing else.
 *
 * ⚠ THE PDF LINK IS MINTED ON A CLICK, NEVER ON LOAD (`?link=1`, five minutes — the Scholars
 * contract tab's rule), and a fresh one each time, so a page left open still opens it.
 * ⚠ THE BUTTON STAYS DEAD UNTIL BOTH ARE GIVEN — a name and the tick — and the server checks both
 * again (`confirm_required`, `name_required`, `name_too_long`). Every refusal has its own words.
 * ⚠ The name starts as the signed-in user's own (it is a signature: they may correct it, never
 * leave it blank). After the witness the page shows the signed state and nothing to press.
 */
export default function SourceWitness({ id, onBack }: { id: string; onBack: () => void }) {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const source = useSourceName()
  const [agreement, setAgreement] = useState<SourceAgreement | null>(null)
  const [missing, setMissing] = useState(false)
  const [name, setName] = useState(role?.admin_name ?? '')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [viewing, setViewing] = useState<ViewerDoc | null>(null)
  const [opening, setOpening] = useState(false)
  const [noPdf, setNoPdf] = useState(false)

  useEffect(() => {
    if (!token || !id) return
    getSourceAgreement(id, { token }).then(setAgreement).catch(() => setMissing(true))
  }, [token, id])

  if (!agreement) return <RecordState loading={!missing} />

  const openPdf = async () => {
    if (!token) return
    setOpening(true); setNoPdf(false)
    try {
      const fresh = await getSourceAgreement(id, { token, link: true })
      if (fresh.pdf_url) {
        setViewing({ label: t(`${W}.agreementFor`, { name: agreement.student_name }),
                     filename: 'agreement.pdf', url: fresh.pdf_url, kind: 'pdf' })
      } else { setNoPdf(true) }
    } catch { setNoPdf(true) } finally { setOpening(false) }
  }

  const sign = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token || !confirmed || !name.trim()) return
    setBusy(true); setError('')
    try {
      setAgreement(await witnessAsSource(id, { witness_name: name.trim(), confirm: true }, { token }))
    } catch (err) {
      const code = (err as { code?: string })?.code
      setError(t(refusalKey('witness', code)))
      // Somebody else got there first: show the signed state the server now holds.
      if (code === 'already_witnessed') {
        getSourceAgreement(id, { token }).then(setAgreement).catch(() => {})
      }
    } finally { setBusy(false) }
  }

  const signedAt = agreement.witness_signed_at
  return (
    <div data-testid="source-witness">
      <button type="button" onClick={onBack}
        className="mb-3 inline-block text-sm text-primary-600 hover:underline">← {t(`${W}.back`)}</button>
      <div className="grid items-start gap-5 lg:grid-cols-[3fr_2fr]">
        <section className={CARD} aria-label={t(`${W}.agreementFor`, { name: agreement.student_name })}>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ground-100 pb-3">
            <h2 className="font-semibold text-ground-900">{t(`${W}.agreementFor`, { name: agreement.student_name })}</h2>
            <button type="button" onClick={openPdf} disabled={opening}
              className="rounded-lg border border-ground-300 px-3 py-1.5 text-sm font-medium text-primary-600 hover:bg-ground-50 disabled:opacity-50">
              {t(opening ? `${W}.opening` : `${W}.openPdf`)}
            </button>
          </div>
          <p className="my-4 text-sm text-ground-600">{t(`${W}.pdfNote`)}</p>
          {noPdf && <p className="mb-3 text-sm text-caution-700" data-testid="witness-no-pdf">{t(`${W}.noPdf`)}</p>}
          <ContractParties contract={agreement} t={t} />
        </section>

        <section className={CARD} data-testid="witness-panel">
          {signedAt ? (
            <p className="text-sm font-medium text-positive-700" data-testid="witness-done">
              {t(`${W}.done`, { date: formatDate(signedAt) })}
            </p>
          ) : !agreement.can_witness ? (
            <p className="text-sm text-ground-600" data-testid="witness-closed">{t(`${W}.closed`)}</p>
          ) : (
            <form onSubmit={sign} className="flex flex-col gap-4">
              <h1 className="text-xl font-bold text-ground-900">{t(`${W}.heading`)}</h1>
              <p className="text-sm text-ground-600">{t(`${W}.intro`, { source })}</p>
              <label className="block text-sm">
                <span className="mb-1 block font-medium text-ground-700">{t(`${W}.nameLabel`)}</span>
                <input className={inputCls} value={name} maxLength={200} autoComplete="name"
                  onChange={(e) => setName(e.target.value)} />
              </label>
              <label className="flex items-start gap-3 text-sm text-ground-800">
                <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)}
                  className="mt-0.5 h-5 w-5 shrink-0" />
                <span>{t(`${W}.confirm`, { source })}</span>
              </label>
              {error && <p className="text-sm text-critical-600" role="alert">{error}</p>}
              <button type="submit" disabled={busy || !confirmed || !name.trim()}
                className="rounded-lg bg-brand-fill py-3 font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {t(busy ? `${W}.signing` : `${W}.sign`)}
              </button>
              <p className="text-xs text-ground-500">{t(`${W}.after`)}</p>
            </form>
          )}
        </section>
      </div>
      <DocViewer doc={viewing} onClose={() => setViewing(null)} />
    </div>
  )
}
