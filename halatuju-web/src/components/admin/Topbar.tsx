'use client'

import { useRouter } from 'next/navigation'

import { useT } from '@/lib/i18n'
import { Menu, MenuHeading, MenuItem, MenuSeparator } from '@/components/admin/Menu'
import { Icon } from '@/components/admin/icons'
import ThemeSelector from '@/components/ThemeSelector'

/**
 * The top bar: where you ARE on the left, what is YOURS on the right.
 *
 * The breadcrumb takes its scope crumbs from `AppShell` (nav/IA N3a) — this component never
 * fetches or decides scope, it only renders what it is handed. When no switchers are passed it
 * falls back to the static org/programme text, which is what a caller with nothing to switch
 * between gets.
 *
 * ⚠ A selected scope is a DISPLAY preference and must never become an auth context — see the
 * ScopeSwitcher docstring for why that distinction is load-bearing.
 */

export interface Attention { key: string; label: string; sub?: string; tone: 'info' | 'warn' | 'crit' }

function Breadcrumb({ orgName, programmeName, scopes }: {
  orgName?: string | null; programmeName?: string; scopes?: React.ReactNode
}) {
  const crumb = (text: string, muted?: boolean) => (
    <span className={`truncate ${muted ? 'text-ground-500' : 'font-medium text-ground-800'}`}>{text}</span>
  )
  const sep = <span aria-hidden className="shrink-0 text-ground-300">/</span>
  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-[13px]">
      <span className="flex shrink-0 items-center gap-1.5 font-bold text-ground-900">
        <span aria-hidden className="grid h-5 w-5 place-items-center rounded bg-brand-fill text-[10px] font-extrabold text-brand-fill-ink">H</span>
        HalaTuju
      </span>
      {scopes ?? (
        <>
          {orgName && <>{sep}{crumb(orgName, true)}</>}
          {programmeName && <>{sep}{crumb(programmeName)}</>}
        </>
      )}
    </nav>
  )
}

export function Topbar({
  orgName, programmeName, adminName, roleLabel, attention,
  onOpenSearch, onOpenMobileNav, onSignOut, guideHref, faqHref, profileHref,
  navPinned, onTogglePin, scopes,
}: {
  orgName?: string | null
  programmeName?: string
  adminName?: string
  roleLabel: string
  attention: Attention[]
  onOpenSearch: () => void
  onOpenMobileNav: () => void
  onSignOut: () => void
  /** The rail's state, so the toggle can say which way it will go. */
  navPinned: boolean
  onTogglePin: () => void
  /** The scope switchers (nav/IA N3a). When present they REPLACE the static org/programme
   *  crumbs — Topbar stays presentational and never fetches or decides scope itself. */
  scopes?: React.ReactNode
  guideHref?: string
  faqHref?: string
  profileHref: string
}) {
  const { t } = useT()
  const router = useRouter()
  const initials = (adminName ?? '?').split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase()

  const toneBar = (tone: Attention['tone']) =>
    tone === 'crit' ? 'bg-critical-500' : tone === 'warn' ? 'bg-caution-500' : 'bg-brand-shape'

  return (
    <header className="flex h-13 items-center gap-2 border-b border-ground-200 bg-ground-0 px-3 py-2">
      <button
        type="button"
        onClick={onOpenMobileNav}
        aria-label={t('common.menu')}
        className="-ml-1 rounded-lg p-2 text-ground-600 hover:bg-ground-50 lg:hidden"
      >
        <Icon name="menu" size={20} />
      </button>

      {/* The pin sits beside the breadcrumb rather than in the account menu: it changes the
          thing immediately to its left, and burying a layout control two clicks deep is how
          people never find out the rail can stay open. Desktop only — the rail is too. */}
      <button
        type="button"
        onClick={onTogglePin}
        aria-pressed={navPinned}
        title={t(navPinned ? 'admin.shell.unpinNav' : 'admin.shell.pinNav')}
        className={`hidden rounded-lg p-1.5 transition-colors lg:block
          ${navPinned ? 'bg-primary-50 text-primary-700' : 'text-ground-400 hover:bg-ground-50 hover:text-ground-600'}`}
      >
        <span className="sr-only">{t(navPinned ? 'admin.shell.unpinNav' : 'admin.shell.pinNav')}</span>
        <Icon name={navPinned ? 'pinned' : 'pin'} size={16} />
      </button>

      <Breadcrumb orgName={orgName} programmeName={programmeName} scopes={scopes} />

      <div className="flex-1" />

      {/* Search — a button, not an input: the palette owns the input so ⌘K and a click open
          exactly the same thing. */}
      <button
        type="button"
        onClick={onOpenSearch}
        className="flex items-center gap-2 rounded-lg border border-ground-200 bg-ground-50 px-2.5 py-1.5 text-[12.5px] text-ground-400 transition-colors hover:border-primary-200 hover:text-primary-700"
      >
        <Icon name="search" size={14} />
        <span className="hidden sm:inline">{t('admin.shell.search')}</span>
        <kbd className="ml-1 hidden rounded border border-ground-200 bg-ground-0 px-1 font-mono text-[10px] text-ground-400 sm:inline">
          Ctrl K
        </kbd>
      </button>

      {/* Light / Dark / Auto (Layer 1 F7d). It sits in the bar rather than in the account menu
          because a reviewer changing it is changing the thing in front of them — the same reason
          the nav pin is not buried either. A reviewer reads documents on this shell for hours. */}
      <ThemeSelector />

      {(guideHref || faqHref) && (
        <Menu label={t('admin.shell.help')} trigger={<Icon name="help" size={17} />}>
          <MenuHeading>{t('admin.shell.help')}</MenuHeading>
          {guideHref && (
            <MenuItem icon={<Icon name="guide" />} onClick={() => router.push(guideHref)} sub={t('admin.shell.guideSub')}>
              {t('admin.guideNav')}
            </MenuItem>
          )}
          {faqHref && (
            <MenuItem icon={<Icon name="help" />} onClick={() => router.push(faqHref)}>{t('admin.faqNav')}</MenuItem>
          )}
        </Menu>
      )}

      <Menu
        label={t('admin.shell.notifications')}
        width="w-72"
        trigger={
          <span className="relative">
            <Icon name="bell" size={17} />
            {attention.length > 0 && (
              <span className="absolute -right-1 -top-1 inline-flex h-[15px] min-w-[15px] items-center justify-center rounded-full border-2 border-white bg-critical-fill px-0.5 text-[9px] font-bold leading-none text-critical-fill-ink">
                {attention.length}
              </span>
            )}
          </span>
        }
      >
        <MenuHeading>{t('admin.shell.attention')}</MenuHeading>
        {attention.length === 0 ? (
          <p className="px-3 py-3 text-sm text-ground-400">{t('admin.shell.nothingWaiting')}</p>
        ) : (
          attention.map((a) => (
            <div key={a.key} className="flex gap-2.5 rounded-lg px-3 py-2">
              <span aria-hidden className={`w-[3px] shrink-0 rounded ${toneBar(a.tone)}`} />
              <span className="min-w-0">
                <span className="block text-[12.5px] font-semibold text-ground-900">{a.label}</span>
                {a.sub && <span className="block text-[11px] text-ground-500">{a.sub}</span>}
              </span>
            </div>
          ))
        )}
        <MenuSeparator />
        {/* Honest about what this is: counts the console already fetches, gathered in one place.
            A real notification model with read state is a separate decision. */}
        <p className="px-3 pb-1 text-[11px] leading-relaxed text-ground-400">
          {t('admin.shell.attentionNote')}
        </p>
      </Menu>

      <Menu
        label={t('admin.shell.account')}
        trigger={
          <>
            <span aria-hidden className="grid h-6 w-6 place-items-center rounded-full bg-brand-fill text-[10px] font-bold text-brand-fill-ink">
              {initials}
            </span>
            <span className="hidden text-left leading-tight md:block">
              <span className="block text-[12px] font-semibold text-ground-800">{adminName}</span>
              <span className="block text-[10.5px] text-ground-400">{roleLabel}</span>
            </span>
          </>
        }
      >
        <div className="px-3 pb-1 pt-2">
          <p className="text-[13px] font-semibold text-ground-900">{adminName}</p>
          <p className="text-[11px] text-ground-400">{roleLabel}</p>
        </div>
        <MenuSeparator />
        <MenuItem icon={<Icon name="profile" />} onClick={() => router.push(profileHref)}>
          {t('admin.profile')}
        </MenuItem>
        <MenuSeparator />
        <MenuItem icon={<Icon name="signOut" />} danger onClick={onSignOut}>{t('header.logout')}</MenuItem>
      </Menu>
    </header>
  )
}
