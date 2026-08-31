'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

import { getPendingSponsorCount } from '@/lib/admin-api'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole, visibleNav, NO_PROBES } from '@/lib/navigation'
import { programmeStaff } from '@/lib/adminStaff'
import { Icon } from '@/components/admin/icons'
import { PageHeader, useStaffAdmin } from '@/components/admin/StaffAdmin'

/**
 * Organisation → Overview. What this tenant is, and what is waiting on someone.
 *
 * Deliberately NOT a grid of links to the pages beside it: the sidebar already lists every one
 * of them, and the old Administration hub existed only because there was no sidebar to do it.
 * What an overview owes the reader is the state of the place — so this shows counts it can
 * derive from calls the console already makes, and says plainly what needs attention.
 *
 * No new endpoint: staff comes from the admins list, sponsors from the pending-vetting count.
 * Anything richer (committed funds, programme totals) needs a summary endpoint that does not
 * exist, and inventing a figure on a financial surface is worse than omitting it.
 */
export default function OrganisationOverviewPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const r = effectiveRole(role)
  const mayView = canAccess('/admin/organisation', r)

  const { admins } = useStaffAdmin(token)
  const [pendingSponsors, setPendingSponsors] = useState(0)

  useEffect(() => {
    if (!token) return
    getPendingSponsorCount({ token })
      .then((d) => setPendingSponsors(d.count))
      .catch(() => { /* a count is a hint; never block the page on it */ })
  }, [token])

  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  const orgName = role?.owning_org_name || role?.org_name || ''
  const staff = programmeStaff(admins)
  const activeStaff = staff.filter((a) => a.is_active).length
  const pendingInvites = staff.length - activeStaff

  // Where each row of the sidebar's organisation group actually goes — reused so a shortcut
  // here can never point somewhere the menu does not.
  const orgGroup = visibleNav({ role: r, probes: NO_PROBES })
    .find((g) => g.scope === 'organisation')
  const hrefOf = (id: string) => orgGroup?.items.find((i) => i.id === id && !i.placeholder)?.href

  const tiles = [
    { k: t('admin.nav.staff'), v: String(activeStaff),
      d: pendingInvites > 0 ? t('admin.orgPage.invitesPending', { count: String(pendingInvites) }) : '',
      href: hrefOf('staff') },
    { k: t('admin.sponsors.nav'), v: String(pendingSponsors),
      d: t('admin.orgPage.awaitingVetting'), href: hrefOf('sponsors') },
  ]

  return (
    <div className="max-w-4xl">
      <PageHeader title={orgName || t('admin.nav.group.organisation')}
        subtitle={t('admin.orgPage.sub')} />

      <div className="grid gap-3 sm:grid-cols-2">
        {tiles.map((tile) => {
          const body = (
            <>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-ground-500">{tile.k}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-ground-900">{tile.v}</p>
              <p className="mt-0.5 text-xs text-ground-400">{tile.d || ' '}</p>
            </>
          )
          return tile.href
            ? <Link key={tile.k} href={tile.href}
                className="rounded-xl border bg-ground-0 p-4 shadow-sm transition-colors hover:border-primary-300">
                {body}
              </Link>
            : <div key={tile.k} className="rounded-xl border bg-ground-0 p-4 shadow-sm">{body}</div>
        })}
      </div>

      {pendingSponsors > 0 && hrefOf('sponsors') && (
        <div className="mt-6 rounded-xl border border-caution-200 bg-caution-50 p-4">
          <p className="text-sm font-semibold text-caution-900">
            {t('admin.orgPage.needsAttention')}
          </p>
          <Link href={hrefOf('sponsors')!}
            className="mt-2 inline-flex items-center gap-2 text-sm font-medium text-caution-800 hover:underline">
            <Icon name="sponsors" size={15} />
            {t('admin.shell.attn.sponsors', { count: String(pendingSponsors) })}
          </Link>
        </div>
      )}
    </div>
  )
}
