'use client'

import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { getBursaryNews, markNewsRead, type BursaryNews as Payload } from '@/lib/api/bursaryNews'

const P = 'bursaryTabs.news'
const URL_RE = /((?:https?:\/\/|www\.)[^\s<>"]+)/g
const TRAILING = /[.,;:!?)\]'"]+$/

/** Plain text with its web addresses made into links (owner ruling: "URLs become links on display"). Only
 *  `http(s)://` and `www.` addresses; trailing punctuation stays text. Nothing else is ever markup. */
export function linkify(text: string): ReactNode[] {
  return text.split(URL_RE).map((part, i) => {
    if (i % 2 === 0) return <Fragment key={i}>{part}</Fragment>
    const tail = part.match(TRAILING)?.[0] ?? ''
    const url = tail ? part.slice(0, -tail.length) : part
    const href = url.startsWith('www.') ? `https://${url}` : url
    return (
      <Fragment key={i}>
        <a href={href} target="_blank" rel="noopener noreferrer" className="break-all text-primary-600 underline">{url}</a>
        {tail}
      </Fragment>
    )
  })
}

/**
 * Her News tab on My Bursary (student maintenance S8; the owner-approved StudentNews board).
 *
 * ⚠ WHAT SHE SEES IS THE SERVER'S ALLOWLIST (`announcements.student_payload`): title, message, pinned,
 * when, edited, new — never who wrote it, who else it is for, or the email. Pinned ones first, then newest.
 * ⚠ OPENING THE TAB MARKS THE SHOWN ONES READ: once the list has drawn, the new ones are sent to
 * `news/read/` (the server records only the ones she may see) and the tab's red number follows the reply.
 * "New" stays on screen for this visit, so she can still tell which they were. Words: `bursaryTabs.news`.
 */
export default function BursaryNews({ token, onRead }: { token: string | null; onRead?: (unread: number) => void }) {
  const { t } = useT()
  const [data, setData] = useState<Payload | null>(null)
  const [failed, setFailed] = useState(false)
  // The page's callback, held in a ref: a re-created callback must never read the list again.
  const told = useRef(onRead)
  told.current = onRead

  useEffect(() => {
    if (!token) return
    let live = true
    getBursaryNews({ token })
      .then((d) => {
        if (!live) return
        setData(d); setFailed(false)
        const fresh = d.announcements.filter((a) => a.new).map((a) => a.id)
        if (fresh.length) {
          markNewsRead(fresh, { token }).then((r) => { if (live) told.current?.(r.unread) }).catch(() => {})
        }
      })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [token])

  if (failed) return <p className="text-sm text-critical-600">{t(`${P}.loadFailed`)}</p>
  if (!data) return null
  const items = data.announcements
  if (items.length === 0) {
    return <p className="rounded-2xl bg-ground-0 p-5 text-sm text-ground-600 shadow-sm" data-testid="news-empty">{t(`${P}.empty`)}</p>
  }
  const fresh = items.filter((a) => a.new).length

  return (
    <>
      {fresh > 0 && (
        <p className="rounded-2xl border border-info-200 bg-info-50 p-4 text-sm text-info-800" data-testid="news-fresh">
          {t(fresh === 1 ? `${P}.freshOne` : `${P}.fresh`, { count: String(fresh) })}
        </p>
      )}
      {items.map((a) => (
        <article key={a.id} data-testid={`news-${a.id}`}
          className={`rounded-2xl bg-ground-0 p-5 shadow-sm ${a.new ? 'border-l-4 border-brand-shape' : ''}`}>
          <p className="text-xs text-ground-600">
            {[a.pinned ? t(`${P}.pinned`) : '', a.new ? t(`${P}.new`) : '', formatDate(a.published_at),
              a.edited_at ? t(`${P}.edited`, { date: formatDate(a.edited_at) }) : ''].filter(Boolean).join(' · ')}
          </p>
          <h2 className="mt-1 break-words text-base font-semibold text-ground-900">{a.title}</h2>
          <p className="mt-1 whitespace-pre-line break-words text-sm leading-relaxed text-ground-700">{linkify(a.body)}</p>
        </article>
      ))}
      <p className="px-1 text-xs text-ground-600">{t(`${P}.readNote`)}</p>
    </>
  )
}
