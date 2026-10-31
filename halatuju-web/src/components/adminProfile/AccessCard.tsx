'use client'

import { accessLines } from '@/lib/profileCards'
import { CardFrame, type CardProps } from './shared'

/**
 * "Your access" — READ ONLY, everyone: the role, the organisation (or source, or referral partner),
 * the gifts, and what the person can do in plain words (`accessLines`, from the role and the
 * RESOLVED permissions `admin/role/` served). Nobody changes their own access here; anyone but a
 * super is told who can.
 */
export default function AccessCard({ state }: CardProps) {
  const { t, me, role, isSuper, permissions } = state
  const rows: [string, string][] = [[t('admin.roleLabel'), role ? t(`admin.role.${role}`) : '']]
  if (me?.source) rows.push([t('admin.myProfile.source'), me.source.name])
  if (me?.organisation) rows.push([t('admin.myProfile.organisation'), me.organisation.name])
  if (me?.referral_partner) rows.push([t('admin.myProfile.referralPartner'), me.referral_partner.name])
  if (me && role !== 'partner') {
    const gifts = me.programmes === 'all' ? t('admin.shell.allGifts')
      : me.programmes.length ? me.programmes.map((p) => p.name).join(', ') : t('admin.myProfile.none')
    rows.push([t('admin.myProfile.gifts'), gifts])
  }
  const lines = accessLines({ role, permissions, isSuper })
  return (
    <CardFrame title={t('admin.myProfile.access')} testId="access">
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ground-500">{k}</dt>
            <dd className="text-ground-900">{v}</dd>
          </div>
        ))}
      </dl>
      <div>
        <h3 className="text-sm font-medium text-ground-700 mb-1">{t('admin.myProfile.youCan')}</h3>
        <ul className="list-disc ml-5 text-sm text-ground-800 space-y-0.5">
          {lines.map((k) => <li key={k}>{t(k)}</li>)}
        </ul>
      </div>
      {!isSuper && <p className="text-xs text-ground-500">{t('admin.myProfile.onlyOrgAdmin')}</p>}
    </CardFrame>
  )
}
