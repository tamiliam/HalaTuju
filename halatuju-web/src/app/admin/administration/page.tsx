'use client'

import { useState, useEffect, type ReactNode } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import {
  getOrgs, inviteAdmin, getAdmins, revokeAdmin, resendAdminInvite,
  type OrgItem, type AdminItem,
} from '@/lib/admin-api'
import { programmeStaff, referralPartners, tenantAdmins } from '@/lib/adminStaff'
import { useT } from '@/lib/i18n'

// The Administration panel (Stitch v2): a cPanel-style icon grid split into a PLATFORM
// section (super only — referral partners + add-tenant + the ALL-staff table across
// organisations) and an ORGANISATION section (super + org_admin — programme staff +
// billing). The org section's table shows PROGRAMME roles only (lib/adminStaff.ts):
// the platform super and referral partners belong to the platform world and never
// appear inside an organisation's staff list.

type Panel = null | 'partner' | 'tenant' | 'staff'
type StaffRole = 'reviewer' | 'admin' | 'qc'
const STAFF_ROLES: StaffRole[] = ['reviewer', 'admin', 'qc']

const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

function IconCard({ icon, title, subtitle, onClick, active, disabled, comingSoon }: {
  icon: string; title: string; subtitle: string
  onClick?: () => void; active?: boolean; disabled?: boolean; comingSoon?: string
}) {
  return (
    <button type="button" onClick={disabled ? undefined : onClick} disabled={disabled}
      className={`text-left rounded-xl border p-4 flex items-start gap-3 transition-colors w-full ${
        disabled ? 'opacity-50 cursor-not-allowed bg-gray-50 border-gray-200'
        : active ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-200'
        : 'bg-white border-gray-200 hover:border-blue-300 hover:bg-blue-50/40'}`}>
      <span aria-hidden className="text-2xl leading-none mt-0.5">{icon}</span>
      <span className="min-w-0">
        <span className="flex items-center gap-2">
          <span className="font-semibold text-gray-900">{title}</span>
          {comingSoon && <span className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded-full bg-gray-200 text-gray-500">{comingSoon}</span>}
        </span>
        <span className="block text-sm text-gray-500 mt-0.5">{subtitle}</span>
      </span>
    </button>
  )
}

export default function AdministrationPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()

  const isSuper = !!(role?.is_super_admin || role?.role === 'super')
  const isOrgAdmin = role?.role === 'org_admin'
  // Admin-General (matrix 2026-07-15): READ-ONLY view of the org staff table — no invite
  // forms, no resend/revoke, no acting icon-cards. Only super + org_admin may manage.
  const isAdminGeneral = role?.role === 'admin'
  const canManage = isSuper || isOrgAdmin

  const [panel, setPanel] = useState<Panel>(null)
  const [admins, setAdmins] = useState<AdminItem[]>([])
  const [orgs, setOrgs] = useState<OrgItem[]>([])
  const [message, setMessage] = useState<{ type: 'success' | 'warning' | 'error'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [revoking, setRevoking] = useState<number | null>(null)
  const [resending, setResending] = useState<number | null>(null)

  // Referral-partner form
  const [pOrgMode, setPOrgMode] = useState<'existing' | 'new'>('existing')
  const [pOrgId, setPOrgId] = useState<number | ''>('')
  const [pName, setPName] = useState(''); const [pEmail, setPEmail] = useState('')
  const [pNewName, setPNewName] = useState(''); const [pNewCode, setPNewCode] = useState('')
  // Add-tenant form
  const [tName, setTName] = useState(''); const [tCode, setTCode] = useState('')
  const [tAdminName, setTAdminName] = useState(''); const [tAdminEmail, setTAdminEmail] = useState('')
  // Staff-invite form
  const [sRole, setSRole] = useState<StaffRole>('reviewer')
  const [sName, setSName] = useState(''); const [sEmail, setSEmail] = useState('')

  const loadAdmins = () => { if (token) getAdmins({ token }).then((d) => setAdmins(d.admins)).catch(() => {}) }
  useEffect(() => {
    if (!token) return
    loadAdmins()
    if (isSuper) getOrgs({ token }).then((d) => setOrgs(d.orgs)).catch(() => {})
  }, [token, isSuper])

  if (role && !isSuper && !isOrgAdmin && !isAdminGeneral) {
    return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>
  }

  // The sole active org_admin of a tenant cannot be revoked (matrix; backend enforces).
  // Hide the Revoke affordance for that row, derived from the already-loaded staff list.
  const isSoleActiveOrgAdmin = (a: AdminItem) =>
    a.role === 'org_admin' && a.is_active && a.owning_org_id != null &&
    admins.filter((x) => x.role === 'org_admin' && x.is_active && x.owning_org_id === a.owning_org_id).length <= 1

  const roleBadge = (rl: string) =>
    rl === 'super' ? 'bg-purple-100 text-purple-700'
    : rl === 'org_admin' ? 'bg-amber-100 text-amber-700'
    : rl === 'admin' ? 'bg-indigo-100 text-indigo-700'
    : rl === 'qc' ? 'bg-orange-100 text-orange-700'
    : rl === 'partner' ? 'bg-teal-100 text-teal-700'
    : rl === 'reviewer' ? 'bg-blue-100 text-blue-700'
    : 'bg-gray-100 text-gray-600'

  const afterInvite = (result: { message: string; emailed: boolean }) => {
    setMessage({ type: result.emailed === false ? 'warning' : 'success', text: result.message })
    loadAdmins()
    if (isSuper && token) getOrgs({ token }).then((d) => setOrgs(d.orgs)).catch(() => {})
  }
  const onError = (err: unknown) => {
    const code = (err as { code?: string })?.code
    setMessage({ type: 'error', text: code === 'last_org_admin'
      ? t('admin.administration.lastOrgAdmin')
      : err instanceof Error ? err.message : t('admin.actionFailed') })
  }

  const submitPartner = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setMessage(null)
    try {
      const data: Parameters<typeof inviteAdmin>[0] = { email: pEmail, name: pName, role: 'partner' }
      if (pOrgMode === 'existing' && pOrgId) data.org_id = Number(pOrgId)
      else if (pOrgMode === 'new') { data.new_org_name = pNewName; data.new_org_code = pNewCode }
      afterInvite(await inviteAdmin(data, { token: token! }))
      setPName(''); setPEmail(''); setPOrgId(''); setPNewName(''); setPNewCode('')
    } catch (err) { onError(err) }
    setBusy(false)
  }

  const submitTenant = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setMessage(null)
    try {
      afterInvite(await inviteAdmin(
        { email: tAdminEmail, name: tAdminName, role: 'org_admin', new_org_name: tName, new_org_code: tCode },
        { token: token! }))
      setTName(''); setTCode(''); setTAdminName(''); setTAdminEmail('')
    } catch (err) { onError(err) }
    setBusy(false)
  }

  const submitStaff = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setMessage(null)
    try {
      // No org fields — the backend forces the owning org (org_admin → own org; super → org #1).
      afterInvite(await inviteAdmin({ email: sEmail, name: sName, role: sRole }, { token: token! }))
      setSName(''); setSEmail('')
    } catch (err) { onError(err) }
    setBusy(false)
  }

  const ownOrgName = role?.owning_org_name || ''
  const orgHeading = ownOrgName
    ? t('admin.administration.orgHeadingNamed', { org: ownOrgName })
    : t('admin.administration.orgHeading')

  // One table, three uses: the org section renders programme rows; the platform
  // panels render their own world's rows (partners / tenant admins — with the
  // owning-organisation column for tenants). No general all-staff table (owner model).
  const staffTable = (rows: AdminItem[], showOrg = false, canAct = true) => {
    const cols = 3 + (showOrg ? 1 : 0) + (canAct ? 1 : 0)
    return (
    <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
      <table className="w-full text-sm min-w-[560px]">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.nameHeader')}</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.emailHeader')}</th>
            {showOrg && <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.orgHeader')}</th>}
            <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.roleHeader')}</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.statusHeader')}</th>
            {canAct && <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.actionHeader')}</th>}
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((a) => (
            <tr key={a.id}>
              <td className="px-4 py-3">{a.name}</td>
              <td className="px-4 py-3 text-gray-500">{a.email}</td>
              {showOrg && <td className="px-4 py-3 text-gray-500">{a.owning_org_name || '—'}</td>}
              <td className="px-4 py-3"><span className={`inline-block px-2 py-0.5 text-xs rounded-full ${roleBadge(a.role)}`}>{t(`admin.role.${a.role}`)}</span></td>
              <td className="px-4 py-3">
                {a.is_active
                  ? <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700">{t('admin.active')}</span>
                  : <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-600">{t('admin.revoked')}</span>}
              </td>
              {canAct && (
              <td className="px-4 py-3">
                {!a.is_super_admin && a.role !== 'super' && (
                  <div className="flex items-center gap-3">
                    {a.is_active && (
                      <button disabled={resending === a.id}
                        onClick={async () => {
                          setResending(a.id)
                          try { setMessage({ type: 'success', text: (await resendAdminInvite(a.id, { token: token! })).message }) }
                          catch (err) { onError(err) }
                          setResending(null)
                        }}
                        className="text-xs font-medium text-blue-600 hover:text-blue-800 disabled:opacity-50">
                        {resending === a.id ? t('admin.resending') : t('admin.resend')}
                      </button>
                    )}
                    {/* Sole active org_admin of a tenant can't be revoked (backend enforces). */}
                    {!(a.is_active && isSoleActiveOrgAdmin(a)) && (
                      <button disabled={revoking === a.id}
                        onClick={async () => {
                          setRevoking(a.id)
                          try { await revokeAdmin(a.id, a.is_active ? 'revoke' : 'restore', { token: token! }); loadAdmins() }
                          catch (err) { onError(err) }
                          setRevoking(null)
                        }}
                        className={`text-xs font-medium ${a.is_active ? 'text-red-600 hover:text-red-800' : 'text-blue-600 hover:text-blue-800'} disabled:opacity-50`}>
                        {a.is_active ? t('admin.revoke') : t('admin.restore')}
                      </button>
                    )}
                  </div>
                )}
              </td>
              )}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={cols} className="px-4 py-6 text-center text-gray-400">{t('admin.noAdmins')}</td></tr>
          )}
        </tbody>
      </table>
    </div>
    )
  }

  const Section = ({ title, badge, badgeCls, children }: { title: string; badge: string; badgeCls: string; children: ReactNode }) => (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-lg font-bold text-gray-900">{title}</h2>
        <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${badgeCls}`}>{badge}</span>
      </div>
      {children}
    </section>
  )

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">{t('admin.administration.title')}</h1>

      {message && (
        <div className={`rounded-lg p-4 mb-6 ${
          message.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700'
          : message.type === 'warning' ? 'bg-amber-50 border border-amber-200 text-amber-700'
          : 'bg-red-50 border border-red-200 text-red-600'}`}>{message.text}</div>
      )}

      {/* PLATFORM section — super only */}
      {isSuper && (
        <Section title={t('admin.administration.platform')} badge={t('admin.administration.superOnly')} badgeCls="bg-purple-100 text-purple-700">
          <div className="grid gap-3 sm:grid-cols-2">
            <IconCard icon="🤝" title={t('admin.administration.invitePartner')} subtitle={t('admin.administration.invitePartnerSub')}
              active={panel === 'partner'} onClick={() => setPanel(panel === 'partner' ? null : 'partner')} />
            <IconCard icon="🏢" title={t('admin.administration.addTenant')} subtitle={t('admin.administration.addTenantSub')}
              active={panel === 'tenant'} onClick={() => setPanel(panel === 'tenant' ? null : 'tenant')} />
          </div>

          {panel === 'partner' && (<div className="mt-4 space-y-4">
            <form onSubmit={submitPartner} className="bg-white rounded-xl border shadow-sm p-6 space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <input className={inputCls} placeholder={t('admin.name')} value={pName} onChange={(e) => setPName(e.target.value)} required />
                <input className={inputCls} type="email" placeholder={t('admin.emailLabel')} value={pEmail} onChange={(e) => setPEmail(e.target.value)} required />
              </div>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm"><input type="radio" checked={pOrgMode === 'existing'} onChange={() => setPOrgMode('existing')} />{t('admin.existing')}</label>
                <label className="flex items-center gap-2 text-sm"><input type="radio" checked={pOrgMode === 'new'} onChange={() => setPOrgMode('new')} />{t('admin.newOrganisation')}</label>
              </div>
              {pOrgMode === 'existing' ? (
                <select className={inputCls} value={pOrgId} onChange={(e) => setPOrgId(e.target.value ? Number(e.target.value) : '')}>
                  <option value="">{t('admin.selectOrg')}</option>
                  {orgs.map((o) => <option key={o.id} value={o.id}>{o.name} ({o.code})</option>)}
                </select>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  <input className={inputCls} placeholder={t('admin.orgName')} value={pNewName} onChange={(e) => setPNewName(e.target.value)} />
                  <input className={inputCls} placeholder={t('admin.urlCode')} value={pNewCode} onChange={(e) => setPNewCode(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))} />
                </div>
              )}
              <button type="submit" disabled={busy} className="px-6 bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50">{t('admin.sendInvite')}</button>
            </form>
            {staffTable(referralPartners(admins))}
          </div>)}

          {panel === 'tenant' && (<div className="mt-4 space-y-4">
            <form onSubmit={submitTenant} className="bg-white rounded-xl border shadow-sm p-6 space-y-4">
              <p className="text-sm text-gray-500">{t('admin.administration.addTenantHelp')}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <input className={inputCls} placeholder={t('admin.administration.tenantName')} value={tName} onChange={(e) => setTName(e.target.value)} required />
                <input className={inputCls} placeholder={t('admin.urlCode')} value={tCode} onChange={(e) => setTCode(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))} required />
                <input className={inputCls} placeholder={t('admin.administration.tenantAdminName')} value={tAdminName} onChange={(e) => setTAdminName(e.target.value)} required />
                <input className={inputCls} type="email" placeholder={t('admin.administration.tenantAdminEmail')} value={tAdminEmail} onChange={(e) => setTAdminEmail(e.target.value)} required />
              </div>
              <button type="submit" disabled={busy} className="px-6 bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50">{t('admin.administration.createTenant')}</button>
            </form>
            {staffTable(tenantAdmins(admins), true)}
          </div>)}
        </Section>
      )}

      {/* ORGANISATION section — super + org_admin manage; Admin-General views read-only */}
      <Section title={orgHeading} badge={t('admin.administration.orgBadge')} badgeCls="bg-blue-100 text-blue-700">
        {canManage ? (<>
          <div className="grid gap-3 sm:grid-cols-2">
            <IconCard icon="👥" title={t('admin.administration.inviteStaff')} subtitle={t('admin.administration.inviteStaffSub')}
              active={panel === 'staff'} onClick={() => setPanel(panel === 'staff' ? null : 'staff')} />
            <IconCard icon="💳" title={t('admin.administration.billing')} subtitle={t('admin.administration.billingSub')}
              disabled comingSoon={t('admin.administration.comingSoon')} />
          </div>

          {panel === 'staff' && (
            <div className="mt-4 space-y-6">
              <form onSubmit={submitStaff} className="bg-white rounded-xl border shadow-sm p-6 space-y-4">
                <div>
                  <p className="text-sm font-semibold text-gray-900 mb-2">{t('admin.inviteAs')}</p>
                  <div className="grid grid-cols-3 gap-2 max-w-md">
                    {STAFF_ROLES.map((rl) => (
                      <button key={rl} type="button" onClick={() => setSRole(rl)}
                        className={`px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
                          sRole === rl ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}`}>
                        {t(`admin.administration.staffRole.${rl}`)}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <input className={inputCls} placeholder={t('admin.name')} value={sName} onChange={(e) => setSName(e.target.value)} required />
                  <input className={inputCls} type="email" placeholder={t('admin.emailLabel')} value={sEmail} onChange={(e) => setSEmail(e.target.value)} required />
                </div>
                <button type="submit" disabled={busy} className="px-6 bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50">{t('admin.sendInvite')}</button>
              </form>

              {staffTable(programmeStaff(admins))}
            </div>
          )}
        </>) : (
          // Admin-General (matrix): read-only staff table, no invite / resend / revoke.
          <div className="space-y-3">
            <p className="text-sm text-gray-500">{t('admin.administration.viewOnlyNote')}</p>
            {staffTable(programmeStaff(admins), false, false)}
          </div>
        )}
      </Section>
    </div>
  )
}
