'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useMemo, useRef, useState } from 'react'

import { useT } from '@/lib/i18n'
import { searchNav, type LabelledNavItem, type VisibleNavGroup } from '@/lib/navigation'
import { Icon } from '@/components/admin/icons'

/**
 * ⌘K / Ctrl-K navigation palette.
 *
 * Scope, deliberately: it searches the MENU, not the records. Searching real applications,
 * students and sponsors needs a new organisation-fenced endpoint (and every such endpoint must
 * be classified in the backend fence test), so that is a later sprint — see the roadmap. The
 * palette ships now because it needs no backend at all, and an honest footer says so rather
 * than letting someone type a student's name and conclude the search is broken.
 *
 * No fuzzy-search dependency: ~20 routes, ranked by `searchNav` in lib/navigation.ts.
 */
export function CommandPalette({ groups, open, onClose }: {
  groups: VisibleNavGroup[]
  open: boolean
  onClose: () => void
}) {
  const { t } = useT()
  const router = useRouter()
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const restoreTo = useRef<Element | null>(null)

  const labelled: LabelledNavItem[] = useMemo(
    () => groups.flatMap((g) => g.items.map((item) => ({ item, label: t(item.labelKey) }))),
    [groups, t],
  )
  const results = useMemo(() => searchNav(query, labelled), [query, labelled])

  // Remember where focus was so Escape can put it back, and reset per opening — a palette that
  // reopens holding the last search is a small betrayal of "start typing".
  useEffect(() => {
    if (!open) return
    restoreTo.current = document.activeElement
    setQuery('')
    setCursor(0)
    inputRef.current?.focus()
    return () => { (restoreTo.current as HTMLElement | null)?.focus?.() }
  }, [open])

  useEffect(() => { setCursor(0) }, [query])

  if (!open) return null

  const go = (href: string) => { onClose(); router.push(href) }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-ground-900/40 px-4 pt-[12vh]"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t('admin.shell.search')}
        className="w-full max-w-lg overflow-hidden rounded-2xl border border-ground-200 bg-ground-0 shadow-2xl"
        onKeyDown={(e) => {
          if (e.key === 'Escape') { e.preventDefault(); onClose() }
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setCursor((c) => (results.length ? (c + 1) % results.length : 0))
          }
          if (e.key === 'ArrowUp') {
            e.preventDefault()
            setCursor((c) => (results.length ? (c - 1 + results.length) % results.length : 0))
          }
          if (e.key === 'Enter' && results[cursor]) {
            e.preventDefault()
            go(results[cursor].href)
          }
        }}
      >
        <div className="flex items-center gap-2.5 border-b border-ground-100 px-4 py-3">
          <Icon name="search" size={16} className="text-ground-400" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('admin.shell.searchPlaceholder')}
            aria-label={t('admin.shell.search')}
            className="min-w-0 flex-1 border-0 bg-transparent text-[15px] text-ground-900 outline-none placeholder:text-ground-placeholder"
          />
        </div>

        <div className="max-h-72 overflow-y-auto p-1.5">
          {results.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-ground-400">
              {t('admin.shell.searchNothing')}
            </p>
          ) : (
            results.map((item, i) => (
              <button
                key={item.id}
                type="button"
                onMouseEnter={() => setCursor(i)}
                onClick={() => go(item.href)}
                aria-current={i === cursor ? 'true' : undefined}
                className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors
                  ${i === cursor ? 'bg-primary-50 text-primary-800' : 'text-ground-700'}`}
              >
                <span className="min-w-0 flex-1 truncate">{t(item.labelKey)}</span>
                <span className="shrink-0 text-[11px] text-ground-400">
                  {t(`admin.nav.group.${item.scope}`)}
                </span>
              </button>
            ))
          )}
        </div>

        <p className="border-t border-ground-100 bg-ground-50 px-4 py-2 text-[11px] text-ground-400">
          {t('admin.shell.searchScopeNote')}
        </p>
      </div>
    </div>
  )
}
