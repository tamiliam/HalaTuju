'use client'

import { usePathname, useRouter } from 'next/navigation'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { getPendingSponsorCount, getAdminScopes, getPaymentRuns, type AdminScopes } from '@/lib/admin-api'
import { adminSignOut } from '@/lib/admin-supabase'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { useNavProbes } from '@/lib/useNavProbes'
import { activeItem, chordTarget, effectiveRole, visibleNav, CHORD_PREFIX } from '@/lib/navigation'
import { withGiftHrefs } from '@/lib/giftHref'
import { pageWidthFor, WIDTH_CLASS } from '@/lib/pageWidth'
import { desktopOnlyRoute } from '@/lib/desktopOnly'
import { DesktopOnly } from '@/components/DesktopOnly'
import { PREF_KEYS, readPref, writePref } from '@/lib/uiPrefs'
import { ProgrammeScopeProvider, useProgrammeScope } from '@/lib/programmeScope'
import { OrgScopeProvider } from '@/lib/orgScope'
import { Sidebar } from '@/components/admin/Sidebar'
import { Topbar, type Attention } from '@/components/admin/Topbar'
import { CommandPalette } from '@/components/admin/CommandPalette'
import { BreadcrumbScopes } from '@/components/admin/ScopeSwitcher'
import { SystemHealthLight } from '@/components/admin/SystemHealthLight'
import { LazyShellBanners } from '@/components/admin/LazyShellBanners'
import StaffAvatar from '@/components/admin/StaffAvatar'
import { Icon } from '@/components/admin/icons'
import { ThemeSegments } from '@/components/DisplaySegments'
import Link from 'next/link'

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
 *
 * ⚠ TWO COMPONENTS, AND THE SPLIT IS THE POINT (2026-09-08). `AppShell` fetches the scopes and
 * PROVIDES the programme context; `Chrome` renders inside it and CONSUMES it. They had to
 * separate the day the sidebar started depending on which gift is open: the selection lives in
 * `ProgrammeScopeProvider`'s own state, and a component cannot read a context it is itself
 * mounting. Lifting that state up here instead would have given the crumb and the pages two
 * holders for one answer — the exact thing `ScopeSwitcher`'s docstring forbids.
 */
/**
 * `path` is for the design SANDBOX only (Mobile M6a): a surface lives at `/sandbox/[surface]`, and Next's
 * pathname context does not reach it, so it names the console route it stands for. Pages never pass it.
 */
export function AppShell({ children, path }: { children: ReactNode; path?: string }) {
  const { token: authToken, role } = useAdminAuth()
  // A MENTOR has no gift to scope (S7a): the scope list is a staff endpoint that refuses the role.
  // Nor has a MEMBER, in no group (M1b, TD-604): the server opens them Profile and nothing else.
  const token = role?.role === 'mentor' || role?.role === 'member' ? null : authToken
  const { locale } = useT()

  /*
   * The scopes behind the breadcrumb switchers (nav/IA N3a).
   *
   * ⚠ A selected scope is a DISPLAY preference. It is not sent as a header, a cookie or anything
   * ambient, and nothing is re-scoped because of it — the organisation fence is server-side and
   * unchanged. Putting it in a header or a cookie would relocate that fence into the client.
   *
   * ⚠ THE PROGRAMME HALF NOW LIVES IN `ProgrammeScopeProvider`, NOT IN THIS COMPONENT'S STATE
   * (TD-193, 2026-09-03). The crumb and the Programme-scope pages must agree about which gift is
   * open, and the only way to guarantee that is one holder — so the shell provides the context and
   * the crumb consumes it exactly as the tabs do. The chosen code is handed to each endpoint as an
   * explicit request value the server re-fences; it never travels on its own.
   *
   * A failed fetch is swallowed: a switcher is furniture, and the console must not go down
   * because a dropdown could not be populated. Empty scopes fall back to the static crumbs.
   */
  const [scopes, setScopes] = useState<AdminScopes>({ organisations: [], programmes: [] })
  /*
   * ⚠ HAS THE LIST ARRIVED YET? An empty `programmes` array is TWO different facts — "this tenant
   * runs no gifts" and "we have not asked yet" — and the menu now behaves differently for each.
   * Without this flag the Configuration row would be hidden on the first paint of every page load
   * and pop into the rail a moment later, which is exactly the kind of movement the pinned-rail
   * note above refuses to make. Until we know, we show: `programmeChosen` stays `undefined`, and
   * `NavContext` says an omitted value means show.
   */
  const [scopesLoaded, setScopesLoaded] = useState(false)
  // ⚠ NOT `scopesLoaded`. That stays false on a FAILED fetch, on purpose, so the rail never hides a
  // row on a list it could not get. `settled` is true either way: the money pages wait for it
  // before redirecting (2026-09-28), and a page waiting on furniture must never wait for ever.
  const [scopesSettled, setScopesSettled] = useState(false)
  // Review F4 (TD-303): the fetch REJECTED, as opposed to answering with an empty list.
  const [scopesFailed, setScopesFailed] = useState(false)
  // ⚠ EXTRACTED SO IT CAN BE RE-RUN. It used to be an inline effect on [token, locale],
  // i.e. fetched ONCE per console session — so a gift created during that session was
  // missing from this list, `programmeScope` refused to resolve the unknown code (correctly),
  // and the Configuration screen asked which gift forever with every click a no-op. Reported
  // by the owner on first real use, 2026-09-07. The list was stale; the guard was right.
  const loadScopes = useCallback(async () => {
    if (!token) return
    try {
      setScopes(await getAdminScopes(locale, { token }))
      setScopesLoaded(true)
      setScopesFailed(false)
    } catch {
      setScopesFailed(true)
      /* furniture — never block the shell. ⚠ `scopesLoaded` stays false on a failure, so a menu
         row is never hidden on the strength of a list we could not fetch. */
    } finally {
      setScopesSettled(true)
    }
  }, [token, locale])

  useEffect(() => { void loadScopes() }, [loadScopes])

  const programmeChoices = useMemo(
    () => scopes.programmes.map((p) => ({
      code: p.code, name: p.name, isActive: p.is_active, organisationId: p.organisation_id })),
    [scopes.programmes],
  )

  return (
    <ProgrammeScopeProvider choices={programmeChoices} onReload={loadScopes} settled={scopesSettled}
      failed={scopesFailed}>
      <Chrome scopes={scopes} scopesLoaded={scopesLoaded} path={path}>{children}</Chrome>
    </ProgrammeScopeProvider>
  )
}

/** Everything that reads the programme context — see the split note on `AppShell`. */
function Chrome(
  { scopes, scopesLoaded, path, children }:
  { scopes: AdminScopes; scopesLoaded: boolean; path?: string; children: ReactNode },
) {
  const { role, token, photoUrl, profileCompletion, session } = useAdminAuth()
  const { t } = useT()
  const routerPath = usePathname()
  const pathname = path ?? routerPath
  const desktopOnly = desktopOnlyRoute(pathname)
  const router = useRouter()

  const [pendingSponsors, setPendingSponsors] = useState(0)
  const [paymentsWaiting, setPaymentsWaiting] = useState(0)
  const [mobileNav, setMobileNav] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [selectedOrg, setSelectedOrg] = useState('')
  // TD-228: the crumb's organisation, handed to the page beneath (`lib/orgScope`) — one answer.
  const orgScope = useMemo(() => ({ selected: selectedOrg, select: setSelectedOrg }), [selectedOrg])

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

  const r = effectiveRole(role)
  // A source user probes nothing: both probes are staff endpoints, which refuse the role, and no
  // row it can see is probe-gated (source sign-in, 2026-10-30). Nor does a mentor (S7a), nor a member (M1b).
  const { probes, requestsWaiting } = useNavProbes(r === 'source_partner' || r === 'mentor' || r === 'member' ? null : token)
  /*
   * ⚠ THE MENU NOW DEPENDS ON WHETHER A GIFT IS KNOWN (owner, 2026-09-08: *"the programme
   * shouldn't show up until they are selected"*). `chosen` is `''` only when there are SEVERAL
   * gifts and none picked — with one gift it fills itself in, so on a single-gift tenant nothing
   * here changes at all.
   *
   * ⚠ IT HIDES THE ROWS THAT WOULD GO WRONG, NOT THE GROUP. `programmeConfig`, `payments` and
   * `spending` carry `needsProgramme` (the last two since 2026-09-28); Applications stays, because
   * a list of every gift is a true answer and it is a reviewer's only door. See `NavItem.needsProgramme` for why that removes the need for any
   * role exemption.
   */
  const { chosen, programme, pinned: onRecord } = useProgrammeScope()
  const groups = useMemo(
    // ⚠ `undefined` UNTIL THE LIST HAS ARRIVED — see `scopesLoaded` on AppShell. Hiding a row on
    // the strength of a list we have not fetched would make it pop in on every page load.
    // `pathname` is what folds the Programme group away outside a gift (owner, 2026-09-14) —
    // see `programmeGroupFolded`. It is the path and not `chosen`, because `chosen` fills itself
    // in on a single-gift tenant and would never let the group fold at all.
    // ⚠ THE PROGRAMME ROWS CARRY THE GIFT (TD-296), so Overview → Applications → Payments keeps it
    // in the address bar — but NOT while a detail page has pinned its record's gift: the pin never
    // selects (review F2), and a rail link naming it would select it one click later, narrowing a
    // reviewer's all-gifts Applications list to the applicant they just opened.
    () => withGiftHrefs(visibleNav({
      role: r, probes, pathname, permissions: role?.permissions, mentoring: role?.mentoring,
      tables: role?.tables,   // Team tables T1
      pageKeys: role?.page_keys,   // Team tables T5c P4: rows on a server door read its keys
      programmeChosen: scopesLoaded ? chosen !== '' : undefined,
    }), onRecord ? '' : chosen),
    [r, role?.permissions, role?.mentoring, role?.tables, role?.page_keys, probes, chosen, scopesLoaded, pathname,
      onRecord],
  )
  const active = activeItem(pathname)
  const activeId = active?.id

  // Close the drawer on navigation — a menu that stays open over the page you just chose is
  // the mobile equivalent of not responding.
  useEffect(() => { setMobileNav(false) }, [pathname])
  // Escape closes the phone drawer too (Mobile M1b) — it is a side panel, not a Sheet, but it must
  // answer the key every overlay answers.
  useEffect(() => {
    if (!mobileNav) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMobileNav(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [mobileNav])

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

  // #39 S2: the runs whose next step is THIS person's (served `your_step`, the predicate the sign
  // endpoint asks). Same manners as the sponsor badge: only while the row is on the sidebar, and a
  // refusal is swallowed. A badge is a number, so it costs no message string.
  const wantsPaymentsCount = groups.some((g) => g.items.some((i) => i.badge === 'paymentsWaiting'))
  // TD-525: a super with NO organisation of their own is refused this read without a gift
  // (400 `programme_required`, the server's `_gift_required_for_orgless_super`), so the call is
  // skipped for them: the badge was always 0 anyway and the console showed a red 400 on every page.
  const orgless = effectiveRole(role) === 'super' && role?.owning_org_id == null
  useEffect(() => {
    if (!token || !wantsPaymentsCount || orgless) { setPaymentsWaiting(0); return }
    getPaymentRuns(undefined, { token })
      .then((d) => setPaymentsWaiting(d.runs.filter((run) => run.your_step).length))
      .catch(() => { /* a badge is a hint; never block the shell on it */ })
  }, [token, wantsPaymentsCount, orgless, pathname])

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
    () => ({ pendingSponsors, requestsWaiting, paymentsWaiting }),
    [pendingSponsors, requestsWaiting, paymentsWaiting],
  )

  // Only a genuine super sees "Super admin"; an org member shows their organisation; everyone
  // else shows their own role label. A reviewer with no org must not read "Super admin".
  // A source user reads "MUETMyWay · Source": the source it signs in for, then the role.
  const roleLabel = role?.is_super_admin
    ? t('admin.role.super')
    : r === 'source_partner' && role?.source_name
      ? t('admin.sourceConsole.roleLine', { source: role.source_name, role: t('admin.role.source_partner') })
      : role?.org_name || t(`admin.role.${r}`)

  const utility = groups.find((g) => g.scope === 'utility')
  const hrefOf = (id: string) => utility?.items.find((i) => i.id === id)?.href

  // ⚠ ONE SIGN-OUT, TWO DOORS (Mobile M6a). The account menu and the phone menu's Log out call THIS
  // function — the exact body the account menu always ran — so the two can never drift apart.
  const signOut = async () => { await adminSignOut(); router.replace('/admin/login') }

  const orgName = role?.owning_org_name ?? role?.org_name
  // The phone row's two lines: the page's own name from the registry, then the gift on a programme
  // page, else the organisation. Text only; the switchers are in the phone menu.
  const phoneTitle = active ? t(active.labelKey) : 'HalaTuju'
  const phoneSub = active?.scope === 'programme' ? (programme?.name ?? orgName) : orgName
  const scopeSwitchers = scopes.organisations.length || scopes.programmes.length ? (
    <BreadcrumbScopes
      organisations={scopes.organisations}
      selectedOrg={selectedOrg}
      onSelectOrg={setSelectedOrg}
      scope={active?.scope}
      pathname={pathname}
    />
  ) : undefined
  const guideHref = hrefOf('guide')
  const faqHref = hrefOf('faq')
  const profileHref = hrefOf('profile') ?? '/admin/profile'
  const drawerLink = 'flex min-h-11 items-center gap-3 rounded-lg px-2.5 text-[15px] text-ground-700 hover:bg-primary-50'

  return (
    // Rule 15 (Mobile M6a): a phone reads the console on the plain ground, sections not cards; from
    // `md` it is the grey desk it always was.
    <div className="flex min-h-screen flex-col bg-ground-0 md:bg-ground-50">
      <Topbar
        orgName={orgName}
        programmeName={undefined}
        adminName={role?.admin_name}
        photoUrl={photoUrl}
        roleLabel={roleLabel}
        attention={attention}
        onOpenSearch={() => setPaletteOpen(true)}
        onOpenMobileNav={() => setMobileNav(true)}
        scopes={scopeSwitchers}
        navPinned={pinned}
        onTogglePin={togglePin}
        onSignOut={signOut}
        // SUPER ONLY: no other admin mounts the light, so no other browser ever asks for it.
        // (`r` is `effectiveRole`: the flag OR role 'super', the server's own `is_super` rule.)
        healthLight={r === 'super' ? <SystemHealthLight token={token} /> : undefined}
        guideHref={guideHref}
        faqHref={faqHref}
        profileHref={profileHref}
        phoneTitle={phoneTitle}
        phoneSub={phoneSub}
      />
      {/* Staff nudges: the top-banner slot, one banner at a time, lazily loaded (`ShellBanners`). */}
      <LazyShellBanners pathname={pathname} accountId={role?.admin_id} completion={profileCompletion}
        profileHref={profileHref} token={token} billingLive={probes.billing === 'live' && r !== 'super'}
        signInStamp={session?.user?.last_sign_in_at ?? null} />

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
              orgName={orgName}
              programmeName={programme?.name}
              pinned={pinned}
            />
          </div>
        </aside>

        {mobileNav && (
          <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true"
            aria-label={t('admin.shell.primaryNav')}>
            <div
              className="absolute inset-0 bg-ground-900/40"
              onClick={() => setMobileNav(false)}
              aria-hidden
            />
            {/* The drawer is always open and never chorded: there is no hover on a phone and
                no keyboard to press G on. Same component, different truth about the device. */}
            {/* THE PHONE MENU (Mobile M6a, owner-approved mock-up): who you are and a 44 px close, the
                scope switchers (below `md` they are not in the bar), every destination, then Help, your
                Profile, the theme and Log out — what the bar holds from `md`, so nothing is out of reach. */}
            <div data-admin-drawer className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col overflow-y-auto bg-ground-0 shadow-xl pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] pl-[env(safe-area-inset-left)]">
              <div className="flex min-h-14 shrink-0 items-center gap-3 border-b border-ground-100 py-2 pl-4 pr-1">
                <StaffAvatar name={role?.admin_name} photoUrl={photoUrl} size={36} />
                <div className="min-w-0 flex-1 leading-tight">
                  <p className="truncate text-sm font-semibold text-ground-900">{role?.admin_name}</p>
                  <p className="truncate text-xs text-ground-500">{roleLabel}</p>
                </div>
                <button type="button" onClick={() => setMobileNav(false)} aria-label={t('common.dismiss')}
                  className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-ground-500 hover:bg-ground-50">
                  <span aria-hidden className="text-lg leading-none">✕</span>
                </button>
              </div>
              {scopeSwitchers && (
                <div data-drawer-scopes className="flex min-w-0 flex-wrap items-center gap-x-1 border-b border-ground-100 px-3 py-1 text-sm md:hidden [&>span:first-child]:hidden">
                  {scopeSwitchers}
                </div>
              )}
              <div className="flex-1">
                <Sidebar
                  groups={groups}
                  activeId={activeId}
                  badgeCounts={badgeCounts}
                  orgName={orgName}
                  programmeName={programme?.name}
                  pinned
                  chords={false}
                  fill
                  onNavigate={() => setMobileNav(false)}
                />
              </div>
              <div data-drawer-foot className="shrink-0 space-y-1 border-t border-ground-200 px-2 pb-3 pt-2">
                {guideHref && <Link href={guideHref} onClick={() => setMobileNav(false)} className={drawerLink}><Icon name="guide" />{t('admin.guideNav')}</Link>}
                {faqHref && <Link href={faqHref} onClick={() => setMobileNav(false)} className={drawerLink}><Icon name="help" />{t('admin.faqNav')}</Link>}
                <Link href={profileHref} onClick={() => setMobileNav(false)} className={drawerLink}><Icon name="profile" />{t('admin.profile')}</Link>
                <div className="px-2.5 pt-2">
                  <p className="pb-1.5 text-xs font-semibold uppercase tracking-wide text-ground-500">{t('theme.label')}</p>
                  <ThemeSegments />
                </div>
                <button type="button" onClick={signOut}
                  className="flex min-h-11 w-full items-center gap-3 rounded-lg px-2.5 text-left text-[15px] font-medium text-critical-600 hover:bg-critical-50">
                  <Icon name="signOut" />{t('header.logout')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ⚠ THE PAGE'S WIDTH IS DECIDED HERE, ONCE (owner, 2026-09-08). Every admin page used
            to write its own `max-w-*` and there were EIGHT different answers, so two pages one
            click apart started their text in different places. `lib/pageWidth` holds the rule —
            leads with a table? wide; otherwise reading — and a page can no longer invent a ninth
            answer. Left-aligned, never `mx-auto`: centring is what made the B40 cockpit look like
            a different console. */}
        <main className="min-w-0 flex-1 p-4 md:p-6">
          {/* ⚠ A DESKTOP-ONLY PAGE (Mobile M7b, owner): below md the shared panel REPLACES it — by CSS, so the
              page is rendered once and no door flashes; from md nothing here changes. Layout, not access. */}
          {desktopOnly && <DesktopOnly route={desktopOnly} />}
          <div className={`${WIDTH_CLASS[pageWidthFor(pathname)]}${desktopOnly ? ' max-md:hidden' : ''}`}
            data-desktop-only-page={desktopOnly ? '' : undefined}>
            <OrgScopeProvider value={orgScope}>{children}</OrgScopeProvider>
          </div>
        </main>
      </div>

      <CommandPalette
        groups={groups}
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
      />
    </div>
  )
}
