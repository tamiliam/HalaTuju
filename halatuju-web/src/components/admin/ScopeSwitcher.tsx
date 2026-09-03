'use client'

import { Menu, MenuItem } from '@/components/admin/Menu'
import { Icon } from '@/components/admin/icons'
import { useT } from '@/lib/i18n'
import { useProgrammeScope } from '@/lib/programmeScope'
import type { NavScope } from '@/lib/navigation'

/**
 * The breadcrumb's organisation and programme switchers (nav/IA N3a).
 *
 * ⚠ THIS IS A DISPLAY PREFERENCE. IT IS NOT AN AUTH CONTEXT, AND MUST NEVER BECOME ONE.
 *
 * The selection does not travel as a header, a cookie, or anything ambient, and no request is
 * re-signed or re-scoped because of it. Doing any of that would relocate the organisation fence
 * into the client — which is the 2026-07-15 surface-partition incident in a new costume, where
 * the nav hid something the backend did not. The fence is `_org_scoped` / `_org_allows`,
 * server-side, and it is unchanged by anything here.
 *
 * ⚠ THE PROGRAMME CRUMB NOW DRIVES PAGE CONTENT (TD-193, 2026-09-03) AND THE RULE ABOVE STILL
 * HOLDS. `lib/programmeScope` holds the choice and hands it to each Programme-scope page, which
 * passes it to its endpoint as an EXPLICIT value the server re-fences on the caller's own
 * `owning_organisation` — the `?programme=<code>` contract `AdminProgrammeConfigurationView` has
 * always had. Nothing became ambient; the control simply stopped being decorative. The slot was
 * left inert in N3a with a written trigger ("a second organisation or programme going active"),
 * and BrightPath Sabah is that trigger.
 *
 * ⚠ NO PROGRAMME SELECTED SHOWS A PROMPT, NEVER THE FIRST ONE. With several gifts and no choice
 * made, `programmeScope` resolves to nothing on purpose, so a crumb reading "BrightPath Bursary"
 * would be the console asserting an answer the rest of the page is still asking for.
 *
 * What the list means: `GET admin/scholarship/scopes/` answers "what may I LOOK AT", derived
 * server-side from the same `owning_organisation` the fence uses. So it can never offer a tenant
 * the caller cannot open, and ignoring it entirely reaches exactly the same data.
 *
 * With one organisation and one programme — production today — each control renders as PLAIN
 * TEXT rather than a dropdown with a single entry. A chevron that opens a menu of one is a
 * promise the data does not keep, and the owner's own design showed switchers precisely because
 * they expect more than one. Until then the breadcrumb reads the way it always has, which is why
 * this sprint changes nothing visible on the current tenant.
 */

export interface ScopeOption {
  id: number
  code: string
  name: string
  /** Programmes only. False for a gift not switched on yet — see `notActiveLabel` below. */
  isActive?: boolean
}

function Crumb({ label, options, selectedCode, onSelect, ariaLabel, notActiveLabel }: {
  label: string
  options: ScopeOption[]
  selectedCode: string
  onSelect: (code: string) => void
  ariaLabel: string
  /** Shown beside a gift that is not switched on yet. Absent for organisations. */
  notActiveLabel?: string
}) {
  // Nothing to switch between: render the name, not a control that suggests otherwise.
  if (options.length <= 1) {
    return <span className="truncate font-medium text-ground-800">{label}</span>
  }

  return (
    <Menu
      label={ariaLabel}
      trigger={
        <>
          <span className="max-w-[16ch] truncate font-medium text-ground-800">{label}</span>
          <Icon name="chevron" size={13} className="shrink-0 text-ground-400" />
        </>
      }
    >
      {options.map((o) => (
        <MenuItem
          key={o.code}
          onClick={() => onSelect(o.code)}
          icon={o.code === selectedCode ? <Icon name="dot" size={13} /> : <span className="w-[13px]" />}
        >
          {o.name}
          {/* ⚠ A DRAFT GIFT IS OFFERED AND MUST SAY SO. It is offered because configuring a gift
              before switching it on is the normal flow; it is LABELLED because a crumb naming it
              plainly would read as the live programme. */}
          {notActiveLabel && o.isActive === false && (
            <span className="ml-2 text-xs font-normal text-ground-400">{notActiveLabel}</span>
          )}
        </MenuItem>
      ))}
    </Menu>
  )
}

export function ScopeSwitcher({
  organisations, programmes, selectedOrg, selectedProgramme, onSelectOrg, onSelectProgramme,
  scope,
}: {
  organisations: ScopeOption[]
  programmes: ScopeOption[]
  selectedOrg: string
  selectedProgramme: string
  onSelectOrg: (code: string) => void
  onSelectProgramme: (code: string) => void
  /** The scope of the page being viewed — from the route registry, never guessed. */
  scope?: NavScope
}) {
  const { t } = useT()
  const sep = <span aria-hidden className="shrink-0 text-ground-300">/</span>

  /*
   * The breadcrumb says WHERE YOU ARE, not what exists (owner, 2026-07-28). A platform page is
   * outside any organisation, so it shows HalaTuju alone; an organisation page adds the tenant;
   * a programme page adds the gift beneath it.
   *
   * The scope comes from the ROUTE REGISTRY (`NavItem.scope`) — the same field that groups the
   * sidebar into Platform / Organisation / Programme, so the two can never disagree about which
   * level a page belongs to. Nothing here is inferred from the URL.
   *
   * `utility` (Profile, Guide, FAQ) shows HalaTuju alone: the registry calls that scope "yours,
   * not any scope's", and those pages belong to the person rather than to a tenant.
   */
  const showOrg = scope === 'organisation' || scope === 'programme'
  const showProgramme = scope === 'programme'

  const org = organisations.find((o) => o.code === selectedOrg) ?? organisations[0]
  // ⚠ NO `?? programmes[0]`. An unresolved selection is a real state (several gifts, none chosen)
  // and the crumb must say so rather than naming one — see the note at the top of this file.
  const programme = programmes.find((p) => p.code === selectedProgramme) ?? null

  return (
    <>
      {showOrg && org && (
        <>
          {sep}
          <Crumb
            label={org.name}
            options={organisations}
            selectedCode={org.code}
            onSelect={onSelectOrg}
            ariaLabel={t('admin.shell.switchOrg')}
          />
        </>
      )}
      {showProgramme && programmes.length > 0 && (
        <>
          {sep}
          <Crumb
            label={programme?.name ?? t('admin.shell.chooseProgramme')}
            options={programmes}
            selectedCode={programme?.code ?? ''}
            onSelect={onSelectProgramme}
            ariaLabel={t('admin.shell.switchProgramme')}
            notActiveLabel={t('admin.programmes.notActive')}
          />
        </>
      )}
    </>
  )
}

/**
 * The switcher as the shell mounts it: organisations still come from the shell, the PROGRAMME
 * comes from `lib/programmeScope`.
 *
 * ⚠ ONE SOURCE OF TRUTH, AND THAT IS THE WHOLE REASON THIS WRAPPER EXISTS. If the shell held the
 * selection in its own state and the pages read it from a context, the crumb and the page could
 * disagree about which gift is open — and the crumb is the only thing on screen claiming to answer
 * that question. Both read `useProgrammeScope()`, so the resolved value (which fills itself in
 * when there is exactly one gift, and stays empty when there are several and none chosen) is the
 * same value the tabs act on.
 */
export function BreadcrumbScopes({ organisations, selectedOrg, onSelectOrg, scope }: {
  organisations: ScopeOption[]
  selectedOrg: string
  onSelectOrg: (code: string) => void
  scope?: NavScope
}) {
  const { choices, chosen, select } = useProgrammeScope()

  return (
    <ScopeSwitcher
      organisations={organisations}
      programmes={choices.map((c, i) => ({ id: i, code: c.code, name: c.name, isActive: c.isActive }))}
      selectedOrg={selectedOrg}
      selectedProgramme={chosen}
      onSelectOrg={onSelectOrg}
      onSelectProgramme={select}
      scope={scope}
    />
  )
}
