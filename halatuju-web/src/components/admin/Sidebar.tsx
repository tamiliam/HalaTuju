'use client'

import Link from 'next/link'
import { useState } from 'react'

import { useT } from '@/lib/i18n'
import {
  SIDEBAR_SCOPES, type NavScope, type VisibleNavGroup, type VisibleNavItem,
} from '@/lib/navigation'
import { Icon } from '@/components/admin/icons'

/**
 * The scope sidebar: every scope this person can reach, all visible at once (model A —
 * "scope stack", owner decision 2026-07-27). Groups collapse; they do not hide.
 *
 * Icons come from the single-colour set in ./icons (owner, 2026-07-27). They inherit the row's
 * text colour, so they sit grey at rest and turn brand-coloured when the row is active, and a
 * tenant's brand ramp carries them. No icon library was added — the set is ~25 inline paths.
 */

function NavRow({ item, active, badge, onNavigate }: {
  item: VisibleNavItem
  active: boolean
  badge?: number
  onNavigate?: () => void
}) {
  const { t } = useT()
  const icon = <Icon name={item.id} className="shrink-0" />
  const label = <span className="min-w-0 flex-1 truncate">{t(item.labelKey)}</span>

  // A reserved slot is rendered, not hidden — that is the point of shipping empty slots — but
  // it is not a link and cannot be focused into.
  if (item.placeholder) {
    return (
      <span
        aria-disabled="true"
        className="flex cursor-default items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm text-gray-400"
      >
        {icon}{label}
        <span className="shrink-0 rounded border border-gray-200 bg-gray-50 px-1 text-[9px] font-bold uppercase tracking-wide text-gray-400">
          {t('admin.nav.soon')}
        </span>
      </span>
    )
  }

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? 'page' : undefined}
      className={`flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm transition-colors
        ${active
          ? 'bg-primary-50 font-semibold text-primary-800 shadow-[inset_2px_0_0_theme(colors.primary.600)]'
          : 'text-gray-700 hover:bg-primary-50 hover:text-primary-800'}`}
    >
      {icon}{label}
      {item.state === 'soon' && (
        <span className="shrink-0 rounded bg-amber-50 px-1 text-[9px] font-bold uppercase tracking-wide text-amber-700">
          {t('admin.nav.soon')}
        </span>
      )}
      {badge != null && badge > 0 && (
        <span className="ml-auto inline-flex h-[17px] min-w-[17px] shrink-0 items-center justify-center rounded-full bg-red-600 px-1 text-[9.5px] font-bold leading-none text-white">
          {badge}
        </span>
      )}
    </Link>
  )
}

export function Sidebar({ groups, activeId, pendingSponsors, orgName, programmeName, onNavigate }: {
  groups: VisibleNavGroup[]
  activeId?: string
  pendingSponsors: number
  orgName?: string | null
  programmeName?: string
  onNavigate?: () => void
}) {
  const { t } = useT()
  const [collapsed, setCollapsed] = useState<Partial<Record<NavScope, boolean>>>({})

  // The heading names the THING (BrightPath), with the scope as a quiet tag beside it — the
  // breadcrumb and the sidebar then agree about what you are looking at.
  //
  // When we have no name — a platform-level account has no organisation — the scope label IS
  // the heading, and the tag is dropped rather than printing "Organisation  Organisation".
  const heading = (g: VisibleNavGroup): { name: string; tag?: string } => {
    const scopeLabel = t(g.headingKey)
    if (g.scope === 'organisation' && orgName) return { name: orgName, tag: scopeLabel }
    if (g.scope === 'programme' && programmeName) return { name: programmeName, tag: scopeLabel }
    if (g.scope === 'platform') return { name: 'HalaTuju', tag: scopeLabel }
    return { name: scopeLabel }
  }

  return (
    <nav aria-label={t('admin.shell.primaryNav')} className="flex flex-col gap-4 p-3">
      {groups.filter((g) => SIDEBAR_SCOPES.includes(g.scope)).map((g) => {
        const open = !collapsed[g.scope]
        const { name, tag } = heading(g)
        return (
          <div key={g.scope}>
            <button
              type="button"
              aria-expanded={open}
              onClick={() => setCollapsed((c) => ({ ...c, [g.scope]: open }))}
              className="flex w-full items-center gap-2 px-2 py-1 text-left text-gray-400 transition-colors hover:text-gray-600"
            >
              <span className="min-w-0 truncate text-[10.5px] font-bold uppercase tracking-wider">
                {name}
              </span>
              {tag && (
                <span className="shrink-0 rounded border border-gray-200 px-1 text-[8.5px] font-semibold uppercase tracking-wide">
                  {tag}
                </span>
              )}
              <Icon name="chevron" size={13}
                className={`ml-auto shrink-0 transition-transform ${open ? '' : '-rotate-90'}`} />
            </button>
            {open && (
              <div className="mt-1 flex flex-col gap-0.5">
                {g.items.map((i) => (
                  <NavRow
                    key={i.id}
                    item={i}
                    active={activeId === i.id}
                    badge={i.badge === 'pendingSponsors' ? pendingSponsors : undefined}
                    onNavigate={onNavigate}
                  />
                ))}
              </div>
            )}
          </div>
        )
      })}
    </nav>
  )
}
