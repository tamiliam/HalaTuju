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
    <details className="group rounded-xl border border-gray-200 bg-white transition-colors open:border-blue-200 open:bg-blue-50/30 hover:border-gray-300">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 font-medium text-gray-900 [&::-webkit-details-marker]:hidden">
        <span>{item.q}</span>
        <svg className="h-5 w-5 shrink-0 text-gray-400 transition-transform duration-200 group-open:rotate-180 group-open:text-blue-500"
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="m19 9-7 7-7-7" />
        </svg>
      </summary>
      <div className="px-4 pb-4 text-sm leading-relaxed text-gray-600">{item.a}</div>
    </details>
  )
}

function Section({ audience }: { audience: Audience }) {
  const items = FAQ[audience]
  if (!items.length) return null
  return (
    <section className="mt-8">
      <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900">
        {AUDIENCE_LABEL[audience]}
        <span className="text-sm font-normal text-gray-400">· {items.length}</span>
      </h2>
      <div className="mt-3 space-y-2.5">
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
    <div className="max-w-2xl">
      <div className="flex items-start gap-4 rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white p-5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
          </svg>
        </span>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Frequently asked questions</h1>
          <p className="mt-1 text-sm text-gray-600">
            Short answers, grouped by role. Tap a question to expand it — and see the{' '}
            <Link href="/admin/guide" className="font-medium text-blue-600 hover:underline">Manual</Link> for a
            full walkthrough.
          </p>
        </div>
      </div>

      {canWiden && (
        <div className="mt-5 flex items-center gap-2">
          <button type="button" onClick={() => setShowAll(false)}
            className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
              !showAll ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}`}>
            For me
          </button>
          <button type="button" onClick={() => setShowAll(true)}
            className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
              showAll ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}`}>
            All roles
          </button>
        </div>
      )}

      {shown.map((a) => <Section key={a} audience={a} />)}
    </div>
  )
}
