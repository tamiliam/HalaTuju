'use client'

import { Menu, MenuItem, MenuSeparator } from '@/components/admin/Menu'
import { Icon } from '@/components/admin/icons'
import { useT } from '@/lib/i18n'
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
}

function Crumb({ label, options, selectedCode, onSelect, ariaLabel }: {
  label: string
  options: ScopeOption[]
  selectedCode: string
  onSelect: (code: string) => void
  ariaLabel: string
}) {
  // Nothing to switch between: render the name, not a control that suggests otherwise.
  if (options.length <= 1) {
    return <span className="truncate font-medium text-gray-800">{label}</span>
  }

  return (
    <Menu
      label={ariaLabel}
      trigger={
        <>
          <span className="max-w-[16ch] truncate font-medium text-gray-800">{label}</span>
          <Icon name="chevron" size={13} className="shrink-0 text-gray-400" />
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
  const sep = <span aria-hidden className="shrink-0 text-gray-300">/</span>

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
  const programme = programmes.find((p) => p.code === selectedProgramme) ?? programmes[0]

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
      {showProgramme && programme && (
        <>
          {sep}
          <Crumb
            label={programme.name}
            options={programmes}
            selectedCode={programme.code}
            onSelect={onSelectProgramme}
            ariaLabel={t('admin.shell.switchProgramme')}
          />
        </>
      )}
    </>
  )
}
