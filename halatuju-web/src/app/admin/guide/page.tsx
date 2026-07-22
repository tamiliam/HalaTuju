'use client'
/* eslint-disable @next/next/no-img-element */
// Role-aware admin manual (rebuilt 2026-07-16). One page, sidebar of chapters filtered by the
// caller's role, role-aware landing, stable deep-link anchors. Content lives in
// src/content/manual/* — every capability claim traces to docs/scholarship/role-matrix.md.

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import {
  visibleChapters, manualRole, resolveTarget, defaultChapterSlug,
  type ManualChapter, type ManualRole,
} from '@/content/manual'

// Reuse the Administration panel's role-badge palette so a role reads the same colour everywhere.
const roleBadgeCls = (r: ManualRole) =>
  r === 'super' ? 'bg-purple-100 text-purple-700'
  : r === 'org_admin' ? 'bg-amber-100 text-amber-700'
  : r === 'admin' ? 'bg-indigo-100 text-indigo-700'
  : r === 'qc' ? 'bg-orange-100 text-orange-700'
  : r === 'finance' ? 'bg-emerald-100 text-emerald-700'
  : 'bg-blue-100 text-blue-700'   // reviewer
// Record<ManualRole, string> on purpose: adding a role to the union fails the build here until
// its label exists, rather than rendering an undefined badge.
const roleLabel: Record<ManualRole, string> = {
  super: 'Super admin', org_admin: 'Org admin', admin: 'General admin', qc: 'QC',
  reviewer: 'Reviewer', finance: 'Finance',
}
const GROUP_LABEL: Record<ManualChapter['group'], string> = {
  basics: 'Basics', role: 'Your role', help: 'Help',
}

/** A screenshot that quietly degrades to a labelled placeholder while the file is missing
 *  (the owner capture pass drops real files into /public/manual/ — no code change needed). */
function ManualImage({ src, alt, float }: { src: string; alt?: string; float?: boolean }) {
  const [failed, setFailed] = useState(false)
  const cls = 'mb-3 block h-auto max-w-full rounded-lg border shadow-sm'
    + (float ? ' sm:float-right sm:ml-6 sm:mb-2 sm:max-w-[340px]' : '')
  if (failed) {
    return (
      <div className={`${cls} border-dashed border-gray-300 bg-gray-50 px-4 py-8 text-center`}>
        <p className="text-xs font-medium text-gray-400">Screenshot coming soon</p>
        {alt && <p className="mt-1 text-[11px] text-gray-400">{alt}</p>}
      </div>
    )
  }
  return (
    <img src={src} alt={alt} onError={() => setFailed(true)} loading="lazy"
      className={`${cls} border-gray-200`} />
  )
}

export default function AdminManualPage() {
  const { role } = useAdminAuth()
  const mr = useMemo(() => manualRole(role), [role])
  const chapters = useMemo(() => visibleChapters(mr), [mr])
  const [active, setActive] = useState<string>(() => defaultChapterSlug(mr))
  const [pendingAnchor, setPendingAnchor] = useState<string | undefined>(undefined)

  // Land on the caller's own chapter (or a deep-linked one). Re-resolve when the role loads.
  useEffect(() => {
    const apply = () => {
      const t = resolveTarget(typeof window !== 'undefined' ? window.location.hash : '', mr)
      setActive(t.slug)
      setPendingAnchor(t.anchor)
    }
    apply()
    window.addEventListener('hashchange', apply)
    return () => window.removeEventListener('hashchange', apply)
  }, [mr])

  // After the chapter renders, scroll to a deep-linked section (else to the top).
  useEffect(() => {
    if (pendingAnchor) {
      const el = document.getElementById(pendingAnchor)
      if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); return }
    }
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [active, pendingAnchor])

  const openChapter = (slug: string) => {
    setPendingAnchor(undefined)
    setActive(slug)
    if (typeof window !== 'undefined') history.replaceState(null, '', `#${slug}`)
  }

  const chapter = chapters.find((c) => c.slug === active) ?? chapters[0]
  const idx = chapters.findIndex((c) => c.slug === chapter.slug)
  const prev = idx > 0 ? chapters[idx - 1] : null
  const next = idx < chapters.length - 1 ? chapters[idx + 1] : null

  // Sidebar groups in fixed order.
  const groups: ManualChapter['group'][] = ['basics', 'role', 'help']

  return (
    <div className="lg:grid lg:grid-cols-[220px_1fr] lg:gap-8">
      {/* Sidebar */}
      <aside className="mb-6 lg:mb-0 lg:sticky lg:top-6 lg:self-start">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">Manual</p>
        <nav className="space-y-4">
          {groups.map((g) => {
            const items = chapters.filter((c) => c.group === g)
            if (items.length === 0) return null
            return (
              <div key={g}>
                <p className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wider text-gray-400">{GROUP_LABEL[g]}</p>
                <ul className="space-y-0.5">
                  {items.map((c) => (
                    <li key={c.slug}>
                      <button type="button" onClick={() => openChapter(c.slug)}
                        className={`w-full rounded-lg px-2 py-1.5 text-left text-sm transition-colors ${
                          c.slug === chapter.slug ? 'bg-blue-50 font-semibold text-blue-700'
                          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}>
                        {c.title}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </nav>
      </aside>

      {/* Chapter */}
      <div className="min-w-0 max-w-3xl">
        <nav className="mb-2 text-xs text-gray-400">
          Manual <span className="mx-1">/</span> {GROUP_LABEL[chapter.group]}
          <span className="mx-1">/</span> <span className="text-gray-600">{chapter.title}</span>
        </nav>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">{chapter.title}</h1>
          {chapter.role && (
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${roleBadgeCls(chapter.role)}`}>
              {roleLabel[chapter.role]}
            </span>
          )}
        </div>
        {chapter.blurb && <p className="mt-1 text-sm text-gray-500">{chapter.blurb}</p>}

        <div className="mt-8 space-y-10">
          {chapter.sections.map((s, i) => (
            <section key={s.anchor} id={s.anchor} className="scroll-mt-6">
              {s.noConflictBanner && (
                <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-900">
                  <strong>Two-person control.</strong> No one QCs a case whose verdict they recorded — or that they
                  reviewed. It always goes to a second person.
                </div>
              )}
              <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white">
                  {i + 1}
                </span>
                {s.title}
              </h2>
              <div className="mt-2 overflow-hidden">
                {s.img && <ManualImage src={s.img} alt={s.alt} float={s.float} />}
                <div className="text-sm leading-relaxed text-gray-700">{s.body}</div>
              </div>
            </section>
          ))}
        </div>

        {/* Prev / next */}
        <div className="mt-10 flex items-center justify-between border-t border-gray-100 pt-4 text-sm">
          {prev ? (
            <button type="button" onClick={() => openChapter(prev.slug)} className="text-blue-600 hover:underline">
              ← {prev.title}
            </button>
          ) : <span />}
          {next ? (
            <button type="button" onClick={() => openChapter(next.slug)} className="text-blue-600 hover:underline">
              {next.title} →
            </button>
          ) : (
            <Link href="/admin/faq" className="text-blue-600 hover:underline">Questions? See the FAQ →</Link>
          )}
        </div>
      </div>
    </div>
  )
}
