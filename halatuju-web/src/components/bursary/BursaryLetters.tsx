'use client'

import { useCallback, useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import {
  acknowledgeLetter, bursaryLetterPdf, getBursaryLetters, markLetterRead,
  type BursaryLetter, type BursaryLetters as Payload,
} from '@/lib/api/bursaryLetters'

const P = 'bursaryTabs.letters'
const STATE_TONE: Record<string, string> = {
  overdue: 'bg-critical-100 text-critical-800', awaiting: 'bg-info-100 text-info-800',
  acknowledged: 'bg-positive-100 text-positive-800', withdrawn: 'bg-ground-100 text-ground-600',
}

/**
 * Her letters on My Bursary (student maintenance S6b; the owner-approved LettersStudent board).
 *
 * ⚠ HER OWN FILE ONLY (the server's 404 for anything else). She reads the letter as it was issued —
 * its PDF is English or Malay (owner ruling); the screen around it is in her language. "I have read
 * this letter" tells the organisation she received it — IT DOES NOT MEAN SHE AGREES, and the page says
 * so beside the button. A withdrawn letter reads, says she need do nothing, and cannot be acknowledged.
 * Words: the `bursaryTabs` namespace (the bursary slice, loaded by this route's page only).
 */
export default function BursaryLetters({ token, onAcknowledged }: {
  token: string | null
  onAcknowledged: () => void
}) {
  const { t } = useT()
  const [data, setData] = useState<Payload | null>(null)
  const [failed, setFailed] = useState(false)
  const [openId, setOpenId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [link, setLink] = useState<string | null>(null)

  const load = useCallback(() => {
    if (!token) return
    getBursaryLetters({ token }).then((d) => { setData(d); setFailed(false) }).catch(() => setFailed(true))
  }, [token])
  useEffect(() => { load() }, [load])

  if (failed) return <p className="text-sm text-critical-600">{t(`${P}.loadFailed`)}</p>
  if (!data) return null

  const replace = (row: BursaryLetter) => setData({ ...data, letters: data.letters.map((x) => (x.id === row.id ? row : x)) })
  const open = data.letters.find((l) => l.id === openId) ?? null

  function read(letter: BursaryLetter) {
    setOpenId(letter.id); setError(''); setLink(null)
    if (!letter.read && token) markLetterRead(letter.id, { token }).then(replace).catch(() => {})
  }

  async function acknowledge(letter: BursaryLetter) {
    if (!token) return
    setBusy(true); setError('')
    try { replace(await acknowledgeLetter(letter.id, { token })); onAcknowledged() }
    catch { setError(t(`${P}.ackFailed`)) } finally { setBusy(false) }
  }

  async function download(letter: BursaryLetter) {
    setError(''); setLink(null)
    const tab = typeof window !== 'undefined' ? window.open('', '_blank') : null
    try {
      const { url } = await bursaryLetterPdf(letter.id, { token: token! })
      if (tab) tab.location.href = url
      else setLink(url)
    } catch { tab?.close(); setError(t(`${P}.pdfFailed`)) }
  }

  const chip = (l: BursaryLetter) => (
    <span className={`self-start rounded-full px-2.5 py-0.5 text-xs font-medium ${STATE_TONE[l.state]}`}
      data-testid={`her-letter-state-${l.id}`}>
      {l.state === 'acknowledged' ? t(`${P}.state.acknowledged`, { date: formatDate(l.acknowledged_at) })
        : l.state === 'withdrawn' ? t(`${P}.state.withdrawn`, { date: formatDate(l.withdrawn_at) })
          : t(`${P}.state.${l.state}`, { date: formatDate(l.response_due_on) })}
    </span>
  )

  return (
    <div className="space-y-4" data-testid="her-letters">
      <section aria-label={t(`${P}.title`)} className="overflow-hidden rounded-2xl bg-ground-0 shadow-sm">
        {data.letters.length === 0 && <p className="p-4 text-sm text-ground-500">{t(`${P}.empty`)}</p>}
        <ul className="divide-y divide-ground-100">
          {data.letters.map((l) => (
            <li key={l.id}>
              <button type="button" onClick={() => read(l)} data-testid={`her-letter-${l.id}`}
                className={`flex w-full flex-col gap-1.5 p-4 text-left ${l.state === 'withdrawn' ? 'text-ground-500' : 'text-ground-900'}`}>
                <span className="flex items-center gap-2">
                  {!l.read && l.state !== 'withdrawn' && (
                    <span role="img" aria-label={t(`${P}.unread`)} className="h-2 w-2 rounded-full bg-brand-shape" />
                  )}
                  <strong className="text-[15px]">{l.subject}</strong>
                </span>
                <span className="text-sm text-ground-600">{t(`${P}.kind.${l.kind}`)} · {formatDate(l.issued_at)}</span>
                {chip(l)}
              </button>
            </li>
          ))}
        </ul>
      </section>

      {open && (
        <section aria-label={t(`${P}.readLabel`)} className="space-y-3 rounded-2xl bg-ground-0 p-5 shadow-sm" data-testid="her-letter-read">
          <p className="text-sm text-ground-600">{data.organisation} · {formatDate(open.issued_at)}</p>
          <h2 className="text-lg font-semibold text-ground-900">{open.subject}</h2>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-ground-700">{open.body}</p>
          {open.state !== 'withdrawn' && open.state !== 'acknowledged' && (
            <p className="text-sm text-ground-600">{t(`${P}.ackBy`, { date: formatDate(open.response_due_on) })}</p>
          )}
          {open.has_pdf && (
            <button type="button" onClick={() => download(open)}
              className="h-11 w-full rounded-xl border border-ground-300 bg-ground-0 text-sm text-ground-800">
              {t(`${P}.download`, { language: t(`${P}.pdfLang.${open.language}`) })}
            </button>
          )}
          {link && (
            <a href={link} target="_blank" rel="noopener noreferrer" className="block text-sm text-primary-600 underline">
              {t(`${P}.openPdf`)}
            </a>
          )}
          {open.state === 'withdrawn' && (
            <p className="rounded-xl bg-ground-100 p-3 text-sm text-ground-700">{t(`${P}.withdrawnNote`)}</p>
          )}
          {open.state === 'acknowledged' && (
            <p className="rounded-xl border border-positive-200 bg-positive-50 p-3 text-sm text-positive-800" data-testid="her-letter-acked">
              {t(`${P}.acknowledgedOn`, { date: formatDate(open.acknowledged_at) })}
            </p>
          )}
          {(open.state === 'awaiting' || open.state === 'overdue') && (
            <div className="space-y-2 border-t border-ground-100 pt-3">
              <button type="button" onClick={() => acknowledge(open)} disabled={busy}
                className="h-12 w-full rounded-xl bg-brand-fill text-[15px] font-semibold text-brand-fill-ink disabled:opacity-50">
                {busy ? t('common.loading') : t(`${P}.acknowledge`)}
              </button>
              <p className="text-xs text-ground-600">{t(`${P}.notAgreement`, { organisation: data.organisation })}</p>
            </div>
          )}
          {error && <p className="text-sm text-critical-600" role="alert">{error}</p>}
        </section>
      )}
    </div>
  )
}
