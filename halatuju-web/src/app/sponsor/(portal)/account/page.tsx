'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import { createSponsorReferral } from '@/lib/api'
import SponsorNotifyPrefs from '@/components/SponsorNotifyPrefs'

/**
 * My Account — profile, email cadence, and "invite a friend". R4 adds the giving
 * statement (two ledgers) here; R5 adds the trust/assurance surfaces.
 */
export default function AccountPage() {
  const { t } = useT()
  const { account } = useSponsorAuth()
  const { referrals, refreshReferrals } = useSponsorPortal()

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteName, setInviteName] = useState('')
  const [inviteNote, setInviteNote] = useState('')
  const [inviting, setInviting] = useState(false)
  const [inviteError, setInviteError] = useState('')
  const [inviteSent, setInviteSent] = useState(false)
  const { token } = useSponsorAuth()

  const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

  const sendInvite = async () => {
    if (!token || !inviteEmail.trim() || inviting) return
    setInviting(true); setInviteError(''); setInviteSent(false)
    try {
      await createSponsorReferral(
        { invitee_email: inviteEmail.trim(), invitee_name: inviteName.trim(), note: inviteNote.trim() },
        { token },
      )
      setInviteEmail(''); setInviteName(''); setInviteNote(''); setInviteSent(true)
      await refreshReferrals()
    } catch (e) {
      const code = (e as Error & { code?: string }).code
      setInviteError(code === 'bad_email'
        ? t('sponsorPortal.referrals.errorEmail') : t('sponsorPortal.referrals.errorGeneric'))
    } finally { setInviting(false) }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">{t('sponsorPortal.account.title')}</h1>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Profile */}
        <div className="rounded-2xl border bg-white p-5">
          <h2 className="font-semibold text-gray-900 mb-3">{t('sponsorPortal.account.detailsTitle')}</h2>
          <dl className="text-sm space-y-2">
            <div className="flex justify-between gap-3"><dt className="text-gray-500">{t('sponsorAuth.fullName')}</dt><dd className="font-medium text-gray-900 text-right">{account?.name || '—'}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-gray-500">{t('sponsorPortal.account.email')}</dt><dd className="font-medium text-gray-900 text-right break-all">{account?.email || '—'}</dd></div>
            {account?.phone && <div className="flex justify-between gap-3"><dt className="text-gray-500">{t('sponsorAuth.phone')}</dt><dd className="font-medium text-gray-900 text-right">{account.phone}</dd></div>}
          </dl>
          <div className="mt-4">
            <span className="inline-block px-2 py-1 text-xs font-semibold rounded-full bg-green-50 text-green-700">
              ✓ {t('sponsorPortal.myStudents.approvedPill')}
            </span>
          </div>
        </div>

        {/* Notifications */}
        <div className="rounded-2xl border bg-white p-5">
          <SponsorNotifyPrefs />
        </div>
      </div>

      {/* Invite a friend + your invitations */}
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="rounded-2xl border bg-white p-5">
          <h2 className="text-lg font-bold text-gray-900">{t('sponsorPortal.referrals.title')}</h2>
          <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.referrals.subtitle')}</p>
          <div className="mt-3 space-y-3">
            <input value={inviteEmail} onChange={(e) => { setInviteEmail(e.target.value); setInviteSent(false) }}
              type="email" placeholder={t('sponsorPortal.referrals.emailPh')} className={inputCls} />
            <input value={inviteName} onChange={(e) => setInviteName(e.target.value)}
              placeholder={t('sponsorPortal.referrals.namePh')} className={inputCls} />
            <textarea value={inviteNote} onChange={(e) => setInviteNote(e.target.value)} rows={3} maxLength={500}
              placeholder={t('sponsorPortal.referrals.notePh')} className={inputCls} />
            {inviteError && <p className="text-sm text-red-600">{inviteError}</p>}
            {inviteSent && <p className="text-sm text-green-600">{t('sponsorPortal.referrals.sent')}</p>}
            <button onClick={sendInvite} disabled={inviting || !inviteEmail.trim()}
              className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
              {inviting ? t('sponsorPortal.referrals.sending') : t('sponsorPortal.referrals.send')}
            </button>
            <p className="text-xs text-gray-400">{t('sponsorPortal.referrals.privacy')}</p>
          </div>
        </div>
        <div className="rounded-2xl border bg-white p-5">
          <h2 className="text-lg font-bold text-gray-900">{t('sponsorPortal.referrals.listTitle')}</h2>
          <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.referrals.listSubtitle')}</p>
          {referrals.length > 0 ? (
            <ul className="mt-3 divide-y divide-gray-100">
              {referrals.map((r) => (
                <li key={r.id} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-gray-700 truncate pr-2">{r.invitee_name || r.invitee_email || '—'}</span>
                  <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    r.status === 'joined' ? 'bg-green-100 text-green-700'
                      : r.status === 'expired' ? 'bg-amber-50 text-amber-600' : 'bg-gray-100 text-gray-600'}`}>
                    {t(`sponsorPortal.referrals.status.${r.status}`)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-gray-400">{t('sponsorPortal.referrals.empty')}</p>
          )}
        </div>
      </div>
    </div>
  )
}
