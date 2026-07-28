'use client'

import Link from 'next/link'
import { useState } from 'react'

import { useT } from '@/lib/i18n'
import {
  CHORD_PREFIX,
  SIDEBAR_SCOPES, type NavScope, type VisibleNavGroup, type VisibleNavItem,
} from '@/lib/navigation'
import { Icon } from '@/components/admin/icons'

/**
 * The scope sidebar, as a rail (N4).
 *
 * At rest it is 48px of icons. Pointing at it — or tabbing into it — opens it to 216px OVER the
 * page rather than pushing the page across: a menu that reflows the content underneath your
 * cursor moves the thing you were about to click. `AppShell` keeps the 48px back with a spacer.
 *
 * Everything the wide sidebar said is still said, at the moment there is room to say it:
 *
 *   labels          fade in on open
 *   group headings  ditto — Platform / Organisation / Programme are words, and words cannot
 *                   survive at 48px. A hairline holds the boundary while collapsed, so the
 *                   scope stack (model A, owner 2026-07-27) still reads as separate stacks.
 *   a badge count   becomes a dot on the icon. Hiding it would remove the only reason it
 *                   exists; a dot says "something is waiting" in the space available.
 *   "Go to X"       appears beside the row being pointed at, with its G-then-X chord.
 *
 * Icons stay the single-colour set (owner, 2026-07-27): they inherit the row's colour, so the
 * ACTIVE row — and only the active row — is brand-coloured, which is what makes the rail
 * legible while collapsed. Do not give a glyph a colour of its own.
 *
 * `open` is threaded down as a prop rather than expressed as a CSS descendant rule. The labels
 * must FADE, so they are always mounted at opacity 0 — mounting them on open would pop, and
 * unmounting them would take the row's layout with it — and a plain prop keeps that legible in
 * the one place each element is written.
 *
 * Individual groups no longer collapse. That control existed to shorten a long wide sidebar;
 * the rail is short by construction, and two collapse mechanisms in one component is one too
 * many. The pin (open ↔ hover) is the only state a person now sets.
 */

/** Labels, pills and counts all fade on the same curve; kept here so they cannot drift apart. */
const fade = (open: boolean) => `transition-opacity duration-100 ${open ? 'opacity-100' : 'opacity-0'}`

function NavRow({ item, active, badge, open, chordHint, onNavigate }: {
  item: VisibleNavItem
  active: boolean
  badge?: number
  open: boolean
  chordHint: boolean
  onNavigate?: () => void
}) {
  const { t } = useT()
  const icon = <Icon name={item.id} className="shrink-0" />
  const label = <span className={`min-w-0 flex-1 truncate ${fade(open)}`}>{t(item.labelKey)}</span>

  // A reserved slot is rendered, not hidden — that is the point of shipping empty slots — but
  // it is not a link and cannot be focused into.
  if (item.placeholder) {
    return (
      <span
        aria-disabled="true"
        className="flex h-8 cursor-default items-center gap-2.5 rounded-lg px-2.5 text-sm text-gray-400"
      >
        {icon}{label}
        <span className={`shrink-0 rounded border border-gray-200 bg-gray-50 px-1 text-[9px] font-bold uppercase tracking-wide text-gray-400 ${fade(open)}`}>
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
      className={`group/row relative flex h-8 items-center gap-2.5 rounded-lg px-2.5 text-sm transition-colors
        ${active
          ? 'bg-primary-50 font-semibold text-primary-800 shadow-[inset_2px_0_0_theme(colors.primary.600)]'
          : 'text-gray-700 hover:bg-primary-50 hover:text-primary-800'}`}
    >
      {icon}{label}
      {item.state === 'soon' && (
        <span className={`shrink-0 rounded bg-amber-50 px-1 text-[9px] font-bold uppercase tracking-wide text-amber-700 ${fade(open)}`}>
          {t('admin.nav.soon')}
        </span>
      )}
      {badge != null && badge > 0 && (
        <>
          {/* Collapsed: a dot on the icon. Open: the number, where the count fits. */}
          {!open && (
            <span
              aria-hidden
              data-badge="dot"
              className="absolute left-[26px] top-1.5 h-[7px] w-[7px] rounded-full border-[1.5px] border-white bg-red-600"
            />
          )}
          <span className={`ml-auto inline-flex h-[17px] min-w-[17px] shrink-0 items-center justify-center rounded-full bg-red-600 px-1 text-[9.5px] font-bold leading-none text-white ${fade(open)}`}>
            {badge}
          </span>
        </>
      )}

      {/*
        The "Go to" chip, on hover or keyboard focus.
        aria-hidden: a screen reader already has the link's name and its aria-current, and the
        chord letter announced mid-list is noise. It sits OUTSIDE the rail (`left-full`), which
        is why the rail must not clip — see the overflow note on the <nav>.
      */}
      <span
        aria-hidden
        className="pointer-events-none absolute left-full top-1/2 z-30 ml-2.5 hidden -translate-y-1/2 items-center gap-1.5 whitespace-nowrap rounded-lg bg-gray-900 px-2 py-1 text-[11.5px] font-normal text-gray-50 shadow-lg group-hover/row:flex group-focus-visible/row:flex"
      >
        {t('admin.shell.goTo', { page: t(item.labelKey) })}
        {chordHint && item.chord && (
          <>
            <kbd className="rounded bg-white/20 px-1 py-px font-mono text-[9.5px] uppercase">
              {CHORD_PREFIX}
            </kbd>
            <span className="text-[9.5px] opacity-60">{t('admin.shell.then')}</span>
            <kbd className="rounded bg-white/20 px-1 py-px font-mono text-[9.5px]">{item.chord}</kbd>
          </>
        )}
      </span>
    </Link>
  )
}

export function Sidebar({
  groups, activeId, pendingSponsors, orgName, programmeName,
  pinned = false, chords = true, onNavigate,
}: {
  groups: VisibleNavGroup[]
  activeId?: string
  pendingSponsors: number
  orgName?: string | null
  programmeName?: string
  /** Open and static — either the person pinned it, or this is the mobile drawer, where
   *  hovering is not a thing that happens. */
  pinned?: boolean
  /** Show the chord on the chip. False where nothing is listening for it (the drawer). */
  chords?: boolean
  onNavigate?: () => void
}) {
  const { t } = useT()
  const [hovering, setHovering] = useState(false)
  const open = pinned || hovering

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

  const shown = groups.filter((g) => SIDEBAR_SCOPES.includes(g.scope))

  return (
    <nav
      aria-label={t('admin.shell.primaryNav')}
      data-open={open ? 'yes' : 'no'}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      onFocus={() => setHovering(true)}
      onBlur={(e) => {
        // Close only once focus has genuinely left the rail — tabbing from one row to the next
        // must not shut it mid-move.
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setHovering(false)
      }}
      /*
       * ⚠ NOT `overflow-hidden`. The "Go to" chip is positioned outside this element, and one
       * non-visible axis forces the other to auto in CSS, so there is no "clip vertically, spill
       * horizontally" to be had. The rail is short enough not to need a scrollbar (the longest
       * menu, super's, is 19 rows), and if that ever changes the chip has to move into a portal
       * rather than the overflow being tightened here.
       */
      className={`flex h-full flex-col gap-1 border-r border-gray-200 bg-white p-2 transition-[width] duration-150 ease-out
        ${open && !pinned ? 'shadow-[6px_0_24px_rgba(0,0,0,0.10)]' : ''}`}
      style={{ width: open ? 216 : 48 }}
    >
      {shown.map((g, gi) => {
        const { name, tag } = heading(g)
        return (
          <div key={g.scope}>
            {/*
              Collapsed, a hairline stands in for the heading — and it fades out as the words
              fade in, so the two never both claim the boundary. aria-hidden because the heading
              text is always in the DOM: a screen reader keeps the group structure either way.
            */}
            {gi > 0 && (
              <div
                aria-hidden
                className={`mx-1.5 my-1.5 h-px bg-gray-200 transition-opacity duration-100 ${open ? 'opacity-0' : 'opacity-100'}`}
              />
            )}
            <p className={`flex h-5 items-center gap-2 px-2 text-[10.5px] font-bold uppercase tracking-wider text-gray-400 ${fade(open)}`}>
              <span className="min-w-0 truncate">{name}</span>
              {tag && (
                <span className="shrink-0 rounded border border-gray-200 px-1 text-[8.5px] font-semibold uppercase tracking-wide">
                  {tag}
                </span>
              )}
            </p>
            <div className="mt-0.5 flex flex-col gap-0.5">
              {g.items.map((i) => (
                <NavRow
                  key={i.id}
                  item={i}
                  active={activeId === i.id}
                  badge={i.badge === 'pendingSponsors' ? pendingSponsors : undefined}
                  open={open}
                  chordHint={chords}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          </div>
        )
      })}
    </nav>
  )
}
