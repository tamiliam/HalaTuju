'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

import { getInvitations, getPendingSponsorCount } from '@/lib/admin-api'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole, visibleNav, NO_PROBES } from '@/lib/navigation'
import { programmeStaff } from '@/lib/adminStaff'
import { Icon } from '@/components/admin/icons'
import { PageHeader, useStaffAdmin } from '@/components/admin/StaffAdmin'
import GiftProgrammes from '@/components/admin/GiftProgrammes'

/**
 * Organisation → Overview. What this tenant is, and what is waiting on someone.
 *
 * Deliberately NOT a grid of links to the pages beside it: the sidebar already lists every one
 * of them, and the old Administration hub existed only because there was no sidebar to do it.
 * What an overview owes the reader is the state of the place — so this shows counts it can
 * derive from calls the console already makes, and says plainly what needs attention.
 *
 * ⚠ THE GIFT PROGRAMMES LIVE HERE (owner, 2026-09-03), which is that same sentence taken
 * seriously: the gifts an organisation runs are the most direct answer to "what is this place",
 * and they had a sidebar row of their own listing exactly one thing. `/admin/organisation/
 * programmes` is now a permanent redirect and the registry matches it here.
 *
 * No new endpoint for the counts: staff comes from the admins list, sponsors from the pending-
 * vetting count, invitations from the same call the Invitations page makes, and the gifts section
 * calls the programmes endpoint it always did. Anything richer (committed funds, programme totals)
 * needs a summary endpoint that does not exist, and inventing a figure on a financial surface is
 * worse than omitting it.
 *
 * ⚠ **A COUNT ON THIS PAGE IS READ, NEVER DERIVED (2026-09-09).** The staff tile used to compute
 * "invited, not yet accepted" as `all staff − active staff`, which measures something else
 * entirely — who has been REVOKED — and so reported a revoked admin as somebody still to reply.
 * Any number here must come from the surface that owns it.
 */
export default function OrganisationOverviewPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const r = effectiveRole(role)
  const mayView = canAccess('/admin/organisation', r)
  const maySeeGifts = r === 'super' || r === 'org_admin'

  const { admins } = useStaffAdmin(token)
  const [pendingSponsors, setPendingSponsors] = useState(0)
  const [waiting, setWaiting] = useState<number | null>(null)

  useEffect(() => {
    if (!token) return
    getPendingSponsorCount({ token })
      .then((d) => setPendingSponsors(d.count))
      .catch(() => { /* a count is a hint; never block the page on it */ })
  }, [token])

  /**
   * How many invitations are still unanswered — READ FROM THE SERVER, across every kind.
   *
   * ⚠ **THIS TILE USED TO WORK IT OUT ITSELF, AND IT WAS WRONG (owner, 2026-09-09).** It printed
   * `staff.length − activeStaff` under the words "invited, not yet accepted" — which is not what
   * that subtraction measures. It measures who has been SWITCHED OFF. On this tenant it reported
   * one admin who had accepted in June and been revoked afterwards, and sent the owner looking for
   * her on the Invitations page, where she rightly was not. It also missed the only genuinely
   * waiting invitations in the system, because those are sponsors and it only ever looked at staff.
   *
   * `waiting` covers all four kinds regardless of the `kind` asked for, so one call answers it and
   * the number is the same one the Invitations page shows on its buttons — see
   * `invitations.open_only`, the single definition of waiting.
   */
  useEffect(() => {
    if (!token) return
    getInvitations('admins', { token })
      .then((d) => setWaiting(Object.values(d.waiting).reduce((a, b) => a + b, 0)))
      .catch(() => { /* a count is a hint; never block the page on it */ })
  }, [token])

  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  const orgName = role?.owning_org_name || role?.org_name || ''
  const staff = programmeStaff(admins)
  const activeStaff = staff.filter((a) => a.is_active).length
  // The same subtraction as before, finally under its own name: these people are REVOKED. It is a
  // real fact worth showing — it just was never "waiting to reply".
  const revokedStaff = staff.length - activeStaff

  // Where each row of the sidebar's organisation group actually goes — reused so a shortcut
  // here can never point somewhere the menu does not.
  const orgGroup = visibleNav({ role: r, probes: NO_PROBES })
    .find((g) => g.scope === 'organisation')
  const hrefOf = (id: string) => orgGroup?.items.find((i) => i.id === id && !i.placeholder)?.href

  // ⚠ THREE TILES SINCE 2026-09-09, AND EACH NUMBER NOW LIVES WHERE ITS TILE POINTS. The staff
  // tile used to carry both facts and link to Invitations — so the count of people who are IN sent
  // you to the page about people who are not, and its second line named the wrong fact entirely.
  // People / Invitations / Sponsors, one number each, each linking to the page that owns it.
  const tiles = [
    { k: t('admin.nav.reviewers'), v: String(activeStaff),
      d: revokedStaff > 0 ? t('admin.orgPage.revokedStaff', { count: String(revokedStaff) }) : '',
      href: hrefOf('reviewers') },
    { k: t('admin.nav.invitations'), v: waiting === null ? '—' : String(waiting),
      d: t('admin.orgPage.invitesPending'), href: hrefOf('staff') },
    { k: t('admin.sponsors.nav'), v: String(pendingSponsors),
      d: t('admin.orgPage.awaitingVetting'), href: hrefOf('sponsors') },
  ]

  return (
    <div>
      <PageHeader title={orgName || t('admin.nav.group.organisation')}
        subtitle={t('admin.orgPage.sub')} />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
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

      {/* Mirrors the programmes endpoint's own gate (`_ProgrammeScopedBase`: super + org_admin).
          ⚠ VISIBILITY ONLY — the fence is the endpoint, and a plain admin or finance who reaches
          it still gets a 403. Drawing the section for them would show a heading above an error. */}
      {maySeeGifts && <GiftProgrammes token={token} />}
    </div>
  )
}
