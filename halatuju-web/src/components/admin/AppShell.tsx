'use client'

import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useMemo, useState, type ReactNode } from 'react'

import { getPendingSponsorCount } from '@/lib/admin-api'
import { adminSignOut } from '@/lib/admin-supabase'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { useNavProbes } from '@/lib/useNavProbes'
import { activeItem, effectiveRole, visibleNav } from '@/lib/navigation'
import { Sidebar } from '@/components/admin/Sidebar'
import { Topbar, type Attention } from '@/components/admin/Topbar'
import { CommandPalette } from '@/components/admin/CommandPalette'

/**
 * The console shell: breadcrumb + scope sidebar + the account cluster.
 *
 * The shell probes the dark-shipped endpoints and fetches the pending-sponsor count once, and
 * passes both down, so the sidebar badge and the notification bell read the same values rather
 * than each asking for themselves.
 *
 * The Administration hub still probes for ITSELF, deliberately. It needs the request COUNT for
 * its badge and not merely whether the endpoint answers, so sharing would mean widening this
 * hook — and N3 deletes that page when the hub is split into real routes. Refactoring a file
 * that is about to be removed buys nothing.
 *
 * Who may see what comes from the registry (lib/navigation.ts), never from a role check
 * written here. It is UX only: the org fence and the endpoint role gates are unchanged.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { role, token } = useAdminAuth()
  const { t } = useT()
  const pathname = usePathname()
  const router = useRouter()

  const [pendingSponsors, setPendingSponsors] = useState(0)
  const [mobileNav, setMobileNav] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)

  const probes = useNavProbes(token)
  const r = effectiveRole(role)
  const groups = useMemo(() => visibleNav({ role: r, probes }), [r, probes])
  const activeId = activeItem(pathname)?.id

  // Close the drawer on navigation — a menu that stays open over the page you just chose is
  // the mobile equivalent of not responding.
  useEffect(() => { setMobileNav(false) }, [pathname])

  // ⌘K / Ctrl-K. Ignored while typing so it cannot steal a keystroke from a form field.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== 'k' || !(e.metaKey || e.ctrlKey)) return
      const el = document.activeElement
      const typing = el instanceof HTMLElement
        && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)
      if (typing) return
      e.preventDefault()
      setPaletteOpen((v) => !v)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  // The badge fires iff a badged item is actually on this person's sidebar — the registry
  // answers "who may see Sponsors", so it is not re-derived here. A refusal is swallowed: a
  // badge is a hint and must never break the shell.
  const wantsSponsorCount = groups.some((g) => g.items.some((i) => i.badge === 'pendingSponsors'))
  useEffect(() => {
    if (!token || !wantsSponsorCount) { setPendingSponsors(0); return }
    getPendingSponsorCount({ token })
      .then((d) => setPendingSponsors(d.count))
      .catch(() => { /* a badge is a hint; never block the shell on it */ })
  }, [token, wantsSponsorCount, pathname])

  // What the bell shows: counts the console already fetches, gathered in one place. Nothing
  // here is a new endpoint, and nothing here has read state — see the note in the menu.
  const attention: Attention[] = useMemo(() => {
    const out: Attention[] = []
    if (pendingSponsors > 0) {
      out.push({
        key: 'sponsors',
        label: t('admin.shell.attn.sponsors', { count: String(pendingSponsors) }),
        tone: 'crit',
      })
    }
    return out
  }, [pendingSponsors, t])

  // Only a genuine super sees "Super admin"; an org member shows their organisation; everyone
  // else shows their own role label. A reviewer with no org must not read "Super admin".
  const roleLabel = role?.is_super_admin
    ? t('admin.role.super')
    : role?.org_name || t(`admin.role.${r}`)

  const utility = groups.find((g) => g.scope === 'utility')
  const hrefOf = (id: string) => utility?.items.find((i) => i.id === id)?.href

  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      <Topbar
        orgName={role?.owning_org_name ?? role?.org_name}
        programmeName={undefined}
        adminName={role?.admin_name}
        roleLabel={roleLabel}
        attention={attention}
        onOpenSearch={() => setPaletteOpen(true)}
        onOpenMobileNav={() => setMobileNav(true)}
        onSignOut={async () => { await adminSignOut(); router.replace('/admin/login') }}
        guideHref={hrefOf('guide')}
        faqHref={hrefOf('faq')}
        profileHref={hrefOf('profile') ?? '/admin/profile'}
      />

      <div className="flex flex-1">
        <aside className="hidden w-60 shrink-0 border-r border-gray-200 bg-white lg:block">
          <div className="sticky top-0">
            <Sidebar
              groups={groups}
              activeId={activeId}
              pendingSponsors={pendingSponsors}
              orgName={role?.owning_org_name ?? role?.org_name}
            />
          </div>
        </aside>

        {mobileNav && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div
              className="absolute inset-0 bg-gray-900/40"
              onClick={() => setMobileNav(false)}
              aria-hidden
            />
            <div className="absolute inset-y-0 left-0 w-64 overflow-y-auto bg-white shadow-xl">
              <Sidebar
                groups={groups}
                activeId={activeId}
                pendingSponsors={pendingSponsors}
                orgName={role?.owning_org_name ?? role?.org_name}
                onNavigate={() => setMobileNav(false)}
              />
            </div>
          </div>
        )}

        <main className="min-w-0 flex-1 p-4 md:p-6">{children}</main>
      </div>

      <CommandPalette
        groups={groups}
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
      />
    </div>
  )
}
