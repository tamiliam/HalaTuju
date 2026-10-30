'use client'

import { useCallback, useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import {
  getScholarLetters, letterPdfLink, resendLetter, withdrawLetter,
  type AdminLetter, type ScholarLetters as Payload,
} from '@/lib/admin-api/letters'
import IssueLetterDialog from './IssueLetterDialog'

const P = 'admin.scholars.letters'
const KIND_TONE: Record<string, string> = {
  termination: 'bg-critical-100 text-critical-800', suspension: 'bg-caution-100 text-caution-800',
  discipline: 'bg-caution-50 text-caution-800', general: 'bg-ground-100 text-ground-700',
  close_out: 'bg-info-100 text-info-800',
}
const STATE_TONE: Record<string, string> = {
  awaiting: 'bg-info-100 text-info-800', overdue: 'bg-critical-100 text-critical-800',
  acknowledged: 'bg-positive-100 text-positive-800',
}

/**
 * The scholar file's Letters tab (student maintenance S6b; the owner-approved LettersAdmin board).
 *
 * ⚠ DOCUMENTS ONLY. Issuing never changes her status or payments. After a termination letter the tab
 * asks "Close the file?" — its button takes the officer to the file's OWN Close control in the header
 * (`ScholarControls`), which keeps every rule of a close; nothing here closes anything.
 * ⚠ THE SERVER DECIDES: which kinds this officer may issue (`can_issue`), who may withdraw, and the
 * typed name. A letter is never edited or deleted — Withdraw, with a reason, is the only way out.
 */
export default function ScholarLetters({ id, token, canClose, onGoToClose, onChanged }: {
  id: number
  token: string | null
  /** The header's Close control offers a close (its own rules decide). */
  canClose: boolean
  onGoToClose: () => void
  onChanged: () => void
}) {
  const { t } = useT()
  const [data, setData] = useState<Payload | null>(null)
  const [failed, setFailed] = useState(false)
  const [issuing, setIssuing] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState<number | null>(null)
  const [withdrawing, setWithdrawing] = useState<number | null>(null)
  const [reason, setReason] = useState('')
  const [link, setLink] = useState<string | null>(null)

  const load = useCallback(() => {
    if (!token) return
    getScholarLetters(id, { token }).then((d) => { setData(d); setFailed(false) }).catch(() => setFailed(true))
  }, [id, token])
  useEffect(() => { load() }, [load])

  if (failed) return <p className="text-sm text-critical-600">{t(`${P}.loadError`)}</p>
  if (!data) return null

  const replace = (row: AdminLetter) => setData({ ...data, letters: data.letters.map((x) => (x.id === row.id ? row : x)) })

  async function viewPdf(letter: AdminLetter) {
    setLink(null); setMessage('')
    const tab = typeof window !== 'undefined' ? window.open('', '_blank') : null
    try {
      const { url } = await letterPdfLink(id, letter.id, { token: token! })
      if (tab) tab.location.href = url
      else setLink(url)
    } catch {
      tab?.close()
      setMessage(t(`${P}.pdfFailed`))
    }
  }

  async function resend(letter: AdminLetter) {
    setBusy(letter.id); setMessage('')
    try {
      const row = await resendLetter(id, letter.id, { token: token! })
      replace(row)
      setMessage(t(row.emailed_at ? `${P}.resent` : `${P}.resendFailed`))
    } catch { setMessage(t(`${P}.resendFailed`)) } finally { setBusy(null) }
  }

  async function withdraw(letter: AdminLetter) {
    if (!reason.trim()) return
    setBusy(letter.id); setMessage('')
    try {
      replace(await withdrawLetter(id, letter.id, reason.trim(), { token: token! }))
      setWithdrawing(null); setReason(''); load(); onChanged()
    } catch { setMessage(t(`${P}.actionFailed`)) } finally { setBusy(null) }
  }

  const termination = data.letters.find((l) => l.kind === 'termination' && !l.withdrawn_at)
  return (
    <div className="space-y-4" data-testid="scholar-letters">
      {data.prompt_close && !dismissed && termination && (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-caution-200 bg-caution-50 px-4 py-3"
          data-testid="letters-close-prompt">
          <p className="text-sm text-caution-800">
            {t(`${P}.closePrompt`, { date: formatDate(termination.issued_at) })}
          </p>
          <div className="flex gap-2">
            {canClose && (
              <button type="button" onClick={onGoToClose}
                className="h-10 rounded-lg border border-critical-300 bg-ground-0 px-3 text-sm text-critical-700 hover:bg-critical-50">
                {t(`${P}.closeFile`)}
              </button>
            )}
            <button type="button" onClick={() => setDismissed(true)}
              className="h-10 rounded-lg border border-ground-300 bg-ground-0 px-3 text-sm text-ground-700 hover:bg-ground-50">
              {t(`${P}.notNow`)}
            </button>
          </div>
        </section>
      )}

      <section className="overflow-hidden rounded-xl border border-ground-200 bg-ground-0">
        <div className="flex items-center justify-between border-b px-4 py-3 sm:px-5">
          <h2 className="font-semibold text-ground-900">{t(`${P}.title`)}</h2>
          {data.can_issue.length > 0 && !issuing && (
            <button type="button" onClick={() => setIssuing(true)}
              className="h-10 rounded-lg bg-primary-600 px-4 text-sm font-semibold text-white hover:bg-primary-700">
              {t(`${P}.issue`)}
            </button>
          )}
        </div>
        {message && <p className="border-b px-4 py-2 text-sm text-ground-700 sm:px-5" role="status">{message}</p>}
        {link && (
          <p className="border-b px-4 py-2 text-sm sm:px-5">
            <a href={link} target="_blank" rel="noopener noreferrer" className="text-primary-600 underline">{t(`${P}.openPdf`)}</a>
          </p>
        )}
        {data.letters.length === 0 && <p className="px-4 py-6 text-sm text-ground-500 sm:px-5">{t(`${P}.empty`)}</p>}
        <ul className="divide-y divide-ground-100">
          {data.letters.map((l) => (
            <li key={l.id} data-testid={`letter-${l.id}`}
              className={`flex flex-wrap justify-between gap-3 px-4 py-4 sm:px-5 ${l.withdrawn_at ? 'bg-ground-50' : ''}`}>
              <div className="flex min-w-0 flex-col gap-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${l.withdrawn_at ? 'bg-ground-100 text-ground-600' : KIND_TONE[l.kind]}`}>
                    {t(`${P}.kind.${l.kind}`)}
                  </span>
                  <strong className={`text-sm ${l.withdrawn_at ? 'text-ground-500 line-through' : 'text-ground-900'}`}>{l.subject}</strong>
                </div>
                {l.withdrawn_at ? (
                  <span className="text-sm text-ground-600" data-testid={`letter-withdrawn-${l.id}`}>
                    {t(`${P}.withdrawnLine`, { date: formatDate(l.withdrawn_at), name: l.withdrawn_by_name, reason: l.withdrawn_reason })}
                  </span>
                ) : (<>
                  <span className="text-sm text-ground-600">
                    {t(`${P}.issuedLine`, { date: formatDate(l.issued_at), name: l.issued_by_name || '—',
                      language: t(`${P}.lang.${l.language}`) })}
                  </span>
                  {l.emailed_at ? (
                    <span className="text-sm text-ground-700">
                      {t(`${P}.emailed`, { date: formatDate(l.emailed_at), to: l.emailed_to })}
                    </span>
                  ) : (
                    <span className="text-sm text-caution-800" data-testid={`letter-not-emailed-${l.id}`}>
                      {t(`${P}.notEmailed`)}{' — '}
                      <button type="button" onClick={() => resend(l)} disabled={busy === l.id}
                        className="text-primary-600 underline disabled:opacity-50">{t(`${P}.resend`)}</button>
                    </span>
                  )}
                  <span className={`self-start rounded-full px-2.5 py-0.5 text-xs font-medium ${STATE_TONE[l.state]}`}
                    data-testid={`letter-state-${l.id}`}>
                    {l.state === 'acknowledged'
                      ? t(`${P}.state.acknowledged`, { date: formatDate(l.acknowledged_at) })
                      : t(`${P}.state.${l.state}`, { date: formatDate(l.response_due_on) })}
                  </span>
                </>)}
                {withdrawing === l.id && (
                  <div className="mt-2 flex flex-wrap items-end gap-2">
                    <label className="text-sm text-ground-700">
                      {t(`${P}.withdrawReason`)}
                      <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500}
                        className="mt-1 block w-72 max-w-full rounded-lg border border-ground-300 px-3 py-2 text-sm" />
                    </label>
                    <button type="button" onClick={() => withdraw(l)} disabled={!reason.trim() || busy === l.id}
                      className="h-10 rounded-lg bg-critical-fill px-3 text-sm font-medium text-critical-fill-ink disabled:opacity-50">
                      {t(`${P}.withdrawConfirm`)}
                    </button>
                    <button type="button" onClick={() => { setWithdrawing(null); setReason('') }}
                      className="h-10 rounded-lg border border-ground-300 px-3 text-sm text-ground-700">{t('common.cancel')}</button>
                  </div>
                )}
              </div>
              <div className="flex flex-wrap items-start gap-2">
                {l.has_pdf && (
                  <button type="button" onClick={() => viewPdf(l)}
                    className="h-10 rounded-lg border border-ground-300 bg-ground-0 px-3 text-sm text-ground-800 hover:bg-ground-50">
                    {t(`${P}.viewPdf`)}
                  </button>
                )}
                {data.can_withdraw && !l.withdrawn_at && withdrawing !== l.id && (
                  <button type="button" onClick={() => { setWithdrawing(l.id); setReason('') }}
                    className="h-10 rounded-lg border border-ground-300 bg-ground-0 px-3 text-sm text-ground-700 hover:bg-ground-50">
                    {t(`${P}.withdraw`)}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      {issuing && (
        <IssueLetterDialog id={id} token={token} data={data}
          onCancel={() => setIssuing(false)}
          onIssued={(row) => {
            setIssuing(false)
            // The email goes after the letter is stored, so the list (re-read) says whether it went.
            setMessage(t(`${P}.issued`, { subject: row.subject }))
            setDismissed(false); load(); onChanged()
          }} />
      )}
    </div>
  )
}
