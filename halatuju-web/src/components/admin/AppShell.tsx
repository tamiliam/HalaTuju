'use client'

import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { getPendingSponsorCount, getAdminScopes, type AdminScopes } from '@/lib/admin-api'
import { adminSignOut } from '@/lib/admin-supabase'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { useNavProbes } from '@/lib/useNavProbes'
import { activeItem, chordTarget, effectiveRole, visibleNav, CHORD_PREFIX } from '@/lib/navigation'
import { PREF_KEYS, readPref, writePref } from '@/lib/uiPrefs'
import { Sidebar } from '@/components/admin/Sidebar'
import { Topbar, type Attention } from '@/components/admin/Topbar'
import { CommandPalette } from '@/components/admin/CommandPalette'
import { ScopeSwitcher } from '@/components/admin/ScopeSwitcher'

/**
 * The console shell: breadcrumb + scope sidebar + the account cluster.
 *
 * The shell probes the dark-shipped endpoints and fetches the pending-sponsor count once, and
 * passes both down, so the sidebar badge and the notification bell read the same values rather
 * than each asking for themselves.
 *
 * Counts travel as ONE `badgeCounts` map keyed by the registry's `badge` field, so a new badge
 * is a registry entry plus a count — not another prop threaded through Sidebar twice and a
 * literal comparison at the render site (TD-205).
 *
 * ⚠ A previous version of this comment said the Administration hub "still probes for ITSELF"
 * because it needed the request COUNT. It does not, and by 2026-08-01 it did not call the count
 * endpoint at all — the count was fetched here and DISCARDED, which is why four bug reports sat
 * unnoticed for two days. Corrected rather than deleted: the claim looked like justification for
 * leaving the number unused.
 *
 * Who may see what comes from the registry (lib/navigation.ts), never from a role check
 * written here. It is UX only: the org fence and the endpoint role gates are unchanged.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { role, token } = useAdminAuth()
  const { t, locale } = useT()
  const pathname = usePathname()
  const router = useRouter()

  const [pendingSponsors, setPendingSponsors] = useState(0)
  const [mobileNav, setMobileNav] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)

  /*
   * The rail starts on hover-open for everyone, then adopts the person's saved choice after
   * mount. Reading `localStorage` during render would give the server one answer and the
   * browser another and hydrate mismatched — so the first paint is deliberately the default,
   * and a pinned rail widens a frame later. Nothing moves under the cursor: the person has to
   * reach the pin to have set it.
   */
  const [pinned, setPinned] = useState(false)
  useEffect(() => {
    setPinned(readPref(PREF_KEYS.navPin, ['pinned', 'hover'] as const, 'hover') === 'pinned')
  }, [])
  const togglePin = () => {
    setPinned((was) => {
      writePref(PREF_KEYS.navPin, was ? 'hover' : 'pinned')
      return !was
    })
  }

  /*
   * The scopes behind the breadcrumb switchers (nav/IA N3a).
   *
   * ⚠ A selected scope is a DISPLAY preference. It is not sent with any request, and nothing is
   * re-scoped because of it — the organisation fence is server-side and unchanged. Putting it in
   * a header or a cookie would relocate that fence into the client.
   *
   * A failed fetch is swallowed: a switcher is furniture, and the console must not go down
   * because a dropdown could not be populated. Empty scopes fall back to the static crumbs.
   */
  const [scopes, setScopes] = useState<AdminScopes>({ organisations: [], programmes: [] })
  const [selectedOrg, setSelectedOrg] = useState('')
  const [selectedProgramme, setSelectedProgramme] = useState('')
  useEffect(() => {
    if (!token) return
    getAdminScopes(locale, { token })
      .then(setScopes)
      .catch(() => { /* furniture — never block the shell */ })
  }, [token, locale])

  const { probes, requestsWaiting } = useNavProbes(token)
  const r = effectiveRole(role)
  const groups = useMemo(() => visibleNav({ role: r, probes }), [r, probes])
  const active = activeItem(pathname)
  const activeId = active?.id

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

  /*
   * `G` then a letter jumps to a page — the chord the rail's own "Go to" chip advertises.
   *
   * The armed `G` expires after 1.2s. Without that, pressing G and wandering off leaves the
   * console silently waiting, and the next stray keystroke navigates — the classic complaint
   * about chorded shortcuts. An unrecognised second key simply disarms.
   *
   * `chordTarget` resolves against the VISIBLE menu, so a chord never carries anyone to a page
   * their sidebar does not offer. That is courtesy, not access control: the page guard and the
   * endpoint are unchanged and still refuse them.
   */
  const armed = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    const disarm = () => {
      if (armed.current) clearTimeout(armed.current)
      armed.current = null
    }

    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const el = document.activeElement
      const typing = el instanceof HTMLElement
        && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)
      if (typing || paletteOpen) return

      if (!armed.current) {
        if (e.key.toLowerCase() !== CHORD_PREFIX) return
        armed.current = setTimeout(disarm, 1200)
        return
      }

      disarm()
      const target = chordTarget(e.key, groups)
      if (!target) return
      e.preventDefault()
      router.push(target.href)
    }

    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); disarm() }
  }, [groups, paletteOpen, router])

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
    // TD-205. 'warn', not 'crit': a waiting request is work owed, not money or consent stuck —
    // and a bell where everything shouts is a bell nobody reads. The count comes from the probe
    // the shell already runs, so this adds no request.
    if (requestsWaiting > 0) {
      out.push({
        key: 'requests',
        label: t('admin.shell.attn.requests', { count: String(requestsWaiting) }),
        tone: 'warn',
      })
    }
    return out
  }, [pendingSponsors, requestsWaiting, t])

  const badgeCounts = useMemo(
    () => ({ pendingSponsors, requestsWaiting }),
    [pendingSponsors, requestsWaiting],
  )

  // Only a genuine super sees "Super admin"; an org member shows their organisation; everyone
  // else shows their own role label. A reviewer with no org must not read "Super admin".
  const roleLabel = role?.is_super_admin
    ? t('admin.role.super')
    : role?.org_name || t(`admin.role.${r}`)

  const utility = groups.find((g) => g.scope === 'utility')
  const hrefOf = (id: string) => utility?.items.find((i) => i.id === id)?.href

  return (
    <div className="flex min-h-screen flex-col bg-ground-50">
      <Topbar
        orgName={role?.owning_org_name ?? role?.org_name}
        programmeName={undefined}
        adminName={role?.admin_name}
        roleLabel={roleLabel}
        attention={attention}
        onOpenSearch={() => setPaletteOpen(true)}
        onOpenMobileNav={() => setMobileNav(true)}
        scopes={
          scopes.organisations.length || scopes.programmes.length ? (
            <ScopeSwitcher
              organisations={scopes.organisations}
              programmes={scopes.programmes}
              selectedOrg={selectedOrg}
              selectedProgramme={selectedProgramme}
              onSelectOrg={setSelectedOrg}
              onSelectProgramme={setSelectedProgramme}
              scope={active?.scope}
            />
          ) : undefined
        }
        navPinned={pinned}
        onTogglePin={togglePin}
        onSignOut={async () => { await adminSignOut(); router.replace('/admin/login') }}
        guideHref={hrefOf('guide')}
        faqHref={hrefOf('faq')}
        profileHref={hrefOf('profile') ?? '/admin/profile'}
      />

      <div className="relative flex flex-1">
        {/*
          Two elements, one rail. The spacer is a plain box in the flow that reserves exactly
          the collapsed width; the rail itself is absolutely positioned over the content, so
          opening it changes nothing about the page's layout. Pinned, the two swap roles — the
          spacer widens and the rail sits flush against it — which is why the pinned rail casts
          no shadow: it is not floating over anything.
        */}
        <div
          aria-hidden
          className="hidden shrink-0 transition-[width] duration-150 ease-out lg:block"
          style={{ width: pinned ? 216 : 48 }}
        />
        <aside className="absolute inset-y-0 left-0 z-30 hidden lg:block">
          <div className="sticky top-0 h-full">
            <Sidebar
              groups={groups}
              activeId={activeId}
              badgeCounts={badgeCounts}
              orgName={role?.owning_org_name ?? role?.org_name}
              pinned={pinned}
            />
          </div>
        </aside>

        {mobileNav && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div
              className="absolute inset-0 bg-ground-900/40"
              onClick={() => setMobileNav(false)}
              aria-hidden
            />
            {/* The drawer is always open and never chorded: there is no hover on a phone and
                no keyboard to press G on. Same component, different truth about the device. */}
            <div className="absolute inset-y-0 left-0 w-64 overflow-y-auto bg-ground-0 shadow-xl">
              <Sidebar
                groups={groups}
                activeId={activeId}
                badgeCounts={badgeCounts}
                orgName={role?.owning_org_name ?? role?.org_name}
                pinned
                chords={false}
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
