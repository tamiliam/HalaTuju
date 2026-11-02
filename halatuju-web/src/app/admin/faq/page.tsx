'use client'
// Role-aware FAQ (rebuilt 2026-07-16). Native <details> accordion, grouped by audience, with a
// default filter of the caller's own role (Everyone always shown). org_admin/super can widen to
// "All". Content lives in src/content/manual/faq.tsx; every answer traces to the role matrix.

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { manualRole } from '@/content/manual'
import {
  FAQ, defaultFaqAudiences, canSeeAllFaq, ALL_FAQ_AUDIENCES, AUDIENCE_LABEL, type QA,
} from '@/content/manual/faq'
import type { Audience } from '@/content/manual'

function Item({ item }: { item: QA }) {
  return (
    <details className="group transition-colors md:rounded-xl md:border md:border-ground-200 md:bg-ground-0 md:open:border-info-200 md:open:bg-info-50/30 md:hover:border-ground-300">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 py-3.5 font-medium md:px-4 text-ground-900 [&::-webkit-details-marker]:hidden">
        <span>{item.q}</span>
        <svg className="h-5 w-5 shrink-0 text-ground-400 transition-transform duration-200 group-open:rotate-180 group-open:text-primary-600"
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="m19 9-7 7-7-7" />
        </svg>
      </summary>
      <div className="pb-4 text-sm leading-relaxed text-ground-600 md:px-4">{item.a}</div>
    </details>
  )
}

function Section({ audience }: { audience: Audience }) {
  const items = FAQ[audience]
  if (!items.length) return null
  return (
    <section className="mt-8">
      <h2 className="flex items-center gap-2 text-base font-semibold text-ground-900">
        {AUDIENCE_LABEL[audience]}
        <span className="text-sm font-normal text-ground-400">· {items.length}</span>
      </h2>
      <div className="mt-3 max-md:divide-y max-md:divide-ground-100 max-md:border-y max-md:border-ground-100 md:space-y-2.5">
        {items.map((item, i) => <Item key={i} item={item} />)}
      </div>
    </section>
  )
}

export default function AdminFaqPage() {
  const { role } = useAdminAuth()
  const mr = useMemo(() => manualRole(role), [role])
  const defaults = useMemo(() => defaultFaqAudiences(mr), [mr])
  const canWiden = canSeeAllFaq(mr)
  const [showAll, setShowAll] = useState(false)

  const shown: Audience[] = showAll ? ALL_FAQ_AUDIENCES : defaults

  return (
    <div>
      <div className="flex items-start gap-4 md:rounded-2xl md:border md:border-info-100 md:bg-gradient-to-br md:from-info-50 md:to-ground-0 md:p-5">
        <span className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-fill text-brand-fill-ink md:flex">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
          </svg>
        </span>
        <div>
          <h1 className="text-2xl font-bold text-ground-900">Frequently asked questions</h1>
          <p className="mt-1 text-sm text-ground-600">
            Short answers, grouped by role. Tap a question to expand it — and see the{' '}
            <Link href="/admin/guide" className="font-medium text-primary-600 hover:underline">Manual</Link> for a
            full walkthrough.
          </p>
        </div>
      </div>

      {canWiden && (
        <div className="mt-5 flex items-center gap-2">
          <button type="button" onClick={() => setShowAll(false)}
            className={`inline-flex min-h-11 items-center rounded-full px-3 py-1 text-sm font-medium transition-colors md:min-h-0 ${
              !showAll ? 'bg-brand-fill text-brand-fill-ink' : 'bg-ground-0 text-ground-600 border border-ground-300 hover:bg-ground-50'}`}>
            For me
          </button>
          <button type="button" onClick={() => setShowAll(true)}
            className={`inline-flex min-h-11 items-center rounded-full px-3 py-1 text-sm font-medium transition-colors md:min-h-0 ${
              showAll ? 'bg-brand-fill text-brand-fill-ink' : 'bg-ground-0 text-ground-600 border border-ground-300 hover:bg-ground-50'}`}>
            All roles
          </button>
        </div>
      )}

      {shown.map((a) => <Section key={a} audience={a} />)}
    </div>
  )
}
