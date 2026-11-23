'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import { createSponsorReferral } from '@/lib/api'
import { PHONE_SECTION_NO_GAP } from '@/lib/phoneSection'

const CARD = PHONE_SECTION_NO_GAP
const inputCls = 'w-full min-h-11 px-3 py-2 border border-ground-300 rounded-lg focus:ring-2 focus:ring-brand-shape focus:border-brand-shape'

/** Invite a friend + your invitations. Its own chunk: the account page fetches it after first paint. */
export function InviteFriends() {
  const { t } = useT()
  const { token } = useSponsorAuth()
  const { referrals, refreshReferrals } = useSponsorPortal()
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteName, setInviteName] = useState('')
  const [inviteNote, setInviteNote] = useState('')
  const [inviting, setInviting] = useState(false)
  const [inviteError, setInviteError] = useState('')
  const [inviteSent, setInviteSent] = useState(false)

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
      <div className="md:grid lg:grid-cols-2 md:gap-4">
        <div className={CARD}>
          <h2 className="text-lg font-bold text-ground-900">{t('sponsorPortal.referrals.title')}</h2>
          <p className="text-sm text-ground-600 mt-1">{t('sponsorPortal.referrals.subtitle')}</p>
          <div className="mt-3 space-y-3">
            <input value={inviteEmail} onChange={(e) => { setInviteEmail(e.target.value); setInviteSent(false) }}
              type="email" placeholder={t('sponsorPortal.referrals.emailPh')} className={inputCls} />
            <input value={inviteName} onChange={(e) => setInviteName(e.target.value)}
              placeholder={t('sponsorPortal.referrals.namePh')} className={inputCls} />
            <textarea value={inviteNote} onChange={(e) => setInviteNote(e.target.value)} rows={3} maxLength={500}
              placeholder={t('sponsorPortal.referrals.notePh')} className={inputCls} />
            {inviteError && <p className="text-sm text-critical-600">{inviteError}</p>}
            {inviteSent && <p className="text-sm text-positive-700">{t('sponsorPortal.referrals.sent')}</p>}
            <button onClick={sendInvite} disabled={inviting || !inviteEmail.trim()}
              className="w-full min-h-11 rounded-lg bg-brand-fill py-2.5 text-sm font-semibold text-brand-fill-ink disabled:opacity-60">
              {inviting ? t('sponsorPortal.referrals.sending') : t('sponsorPortal.referrals.send')}
            </button>
            <p className="text-xs text-ground-400">{t('sponsorPortal.referrals.privacy')}</p>
          </div>
        </div>
        <div className={CARD}>
          <h2 className="text-lg font-bold text-ground-900">{t('sponsorPortal.referrals.listTitle')}</h2>
          <p className="text-sm text-ground-600 mt-1">{t('sponsorPortal.referrals.listSubtitle')}</p>
          {referrals.length > 0 ? (
            <ul className="mt-3 divide-y divide-ground-100">
              {referrals.map((r) => (
                <li key={r.id} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-ground-700 truncate pr-2">{r.invitee_name || r.invitee_email || '—'}</span>
                  <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    r.status === 'joined' ? 'bg-positive-100 text-positive-700'
                      : r.status === 'expired' ? 'bg-caution-50 text-caution-700' : 'bg-ground-100 text-ground-600'}`}>
                    {t(`sponsorPortal.referrals.status.${r.status}`)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-ground-400">{t('sponsorPortal.referrals.empty')}</p>
          )}
        </div>
      </div>
  )
}
