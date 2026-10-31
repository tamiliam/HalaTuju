'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { getMyActivity, type ActivityItem } from '@/lib/admin-api'
import { activityFilters, type ActivityFilter } from '@/lib/profileCards'
import {
  ACTIVITY_KEY as P, groupByDay, rowContext, sentenceParts, subjectHref, subjectText,
} from '@/lib/profileActivity'
import { CardFrame, type CardProps } from './shared'

/**
 * "My activity" — the person's OWN actions, newest first (common profile S5, 2026-10-31; the
 * owner-approved mock-up). Everyone has it; on a wide screen it is the page's right-hand column.
 *
 * It is the one card that loads its own data, from ONE endpoint: `GET admin/me/activity/`, opted in
 * for a source user and a mentor (D3) — `components/source/noStaffCalls.test.tsx` holds a source's
 * page to that. The chips are `activityFilters` (only the ones that make sense for this person); the
 * words, the neutral subject words and the links are `lib/profileActivity.ts`.
 *
 * ⚠ A SUPERSEDED ANSWER IS DROPPED. Switching chips while a page is in the air must never paint the
 * old filter's rows under the new chip, nor append an older page to the wrong list: every request
 * carries the number of the view it was made for (`view`), and only the current view's lands.
 */
export default function ActivityCard({ state }: CardProps) {
  const { t, token, role, isSuper, permissions } = state
  const filters = activityFilters({ role, permissions, isSuper })
  const [kind, setKind] = useState<ActivityFilter>('all')
  const [attempt, setAttempt] = useState(0)
  const [rows, setRows] = useState<ActivityItem[] | null>(null)
  const [next, setNext] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [moreFailed, setMoreFailed] = useState(false)
  const view = useRef(0)

  useEffect(() => {
    if (!token) return
    const mine = ++view.current
    setRows(null); setNext(null); setFailed(false); setLoadingMore(false); setMoreFailed(false)
    getMyActivity(kind, null, { token })
      .then((p) => { if (view.current === mine) { setRows(p.results); setNext(p.next) } })
      .catch(() => { if (view.current === mine) setFailed(true) })
    return () => { view.current += 1 }
  }, [token, kind, attempt])

  const showOlder = () => {
    if (!token || !next || loadingMore) return
    const mine = view.current
    setLoadingMore(true); setMoreFailed(false)
    getMyActivity(kind, next, { token })
      .then((p) => {
        if (view.current !== mine) return
        setRows((prev) => [...(prev ?? []), ...p.results]); setNext(p.next); setLoadingMore(false)
      })
      .catch(() => { if (view.current === mine) { setMoreFailed(true); setLoadingMore(false) } })
  }

  const now = new Date()
  // Mobile standard rule 3: every chip and button is at least 44 px tall (`min-h-11`), the look small.
  const chip = (on: boolean) => `inline-flex min-h-11 items-center rounded-full px-4 text-sm font-medium transition-colors ${on
    ? 'bg-brand-fill text-brand-fill-ink'
    : 'border border-ground-300 bg-ground-0 text-ground-600 hover:bg-ground-50'}`

  const row = (item: ActivityItem) => {
    // A verb the server added before this build knew it (an API deployed first) reads as a plain
    // sentence, never a raw key: `t` echoes the key it cannot find (the `tOr` rule, written out here
    // because the page's tests mock `@/lib/i18n` down to `useT`).
    const key = `${P}.verb.${item.verb}`
    const sentence = t(key)
    const [before, after] = sentenceParts(sentence === key ? t(`${P}.unknownVerb`) : sentence)
    const href = subjectHref(item.subject)
    const words = subjectText(item.subject, t)
    return (
      <li key={item.id} className="min-w-0" data-testid="activity-row">
        <p className="text-sm text-ground-900 [overflow-wrap:anywhere]">
          {before}
          {after !== null && (href
            ? <Link href={href} className="font-medium text-primary-600 hover:underline">{words}</Link>
            : <span className="font-medium">{words}</span>)}
          {after}
          {item.backfilled && (
            // A badge, so 11 px is allowed (rule 12); no hover text (rule 4) — the footer says what it means.
            <span className="ml-2 inline-block rounded bg-ground-100 px-1.5 py-0.5 align-middle text-[11px] text-ground-600"
              data-testid="activity-rebuilt">{t(`${P}.rebuilt`)}</span>
          )}
        </p>
        <p className="text-xs text-ground-500">{rowContext(item, now, t)}</p>
      </li>
    )
  }

  return (
    <CardFrame title={t(`${P}.title`)} testId="activity">
      <div role="group" aria-label={t(`${P}.filterLabel`)} className="flex flex-wrap gap-2">
        {filters.map((f) => (
          <button key={f} type="button" aria-pressed={kind === f} onClick={() => setKind(f)} className={chip(kind === f)}>
            {t(`${P}.filter.${f}`)}
          </button>
        ))}
      </div>

      {failed ? (
        <div role="alert" className="text-sm text-critical-600">
          <p>{t(`${P}.error`)}</p>
          <button type="button" onClick={() => setAttempt((n) => n + 1)} className="mt-1 min-h-11 font-medium text-primary-600 hover:underline">
            {t(`${P}.retry`)}
          </button>
        </div>
      ) : rows === null ? (
        <p className="text-sm text-ground-500">{t('common.loading')}</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-ground-500" data-testid="activity-empty">{t(kind === 'all' ? `${P}.empty` : `${P}.emptyFiltered`)}</p>
      ) : (
        groupByDay(rows, now).map((g, i) => (
          <section key={`${g.group}-${i}`} aria-label={t(`${P}.group.${g.group}`)}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ground-400">{t(`${P}.group.${g.group}`)}</h3>
            <ul className="space-y-3">{g.rows.map(row)}</ul>
          </section>
        ))
      )}

      {rows !== null && next && (
        <button type="button" onClick={showOlder} disabled={loadingMore}
          className="min-h-11 w-full rounded-lg border border-ground-300 px-3 py-2 text-sm font-medium text-ground-700 hover:bg-ground-50 disabled:opacity-50">
          {loadingMore ? t('common.loading') : t(`${P}.showOlder`)}
        </button>
      )}
      {moreFailed && <p role="alert" className="text-sm text-critical-600">{t(`${P}.moreError`)}</p>}

      <p className="text-xs text-ground-500">{t(`${P}.footer`)}</p>
    </CardFrame>
  )
}
