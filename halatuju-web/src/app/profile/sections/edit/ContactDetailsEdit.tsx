/** A3.9: moved verbatim from `src/app/profile/page.tsx` (the 1,274-line page); no behaviour change. */
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'
import { updateProfile, sendVerificationEmail, sendPhoneVerification, checkPhoneVerification } from '@/lib/api'
import { formatPhone } from '@/lib/scholarship'
import Toggle from '@/components/Toggle'
import { useToast } from '@/components/ToastContext'
import type { SectionProps } from '../../useProfileEditor'

/** The contactDetails section's edit panel. Fetched as one chunk with the other four (see `useProfileEditors`). */
export default function ContactDetailsEdit({ f, ed }: SectionProps) {
  const { t, locale } = useT()
  const { token } = useAuth()
  const { showToast } = useToast()
  const { contactEmail, setContactEmail, contactPhone, setContactPhone, contactPhoneVerified, setContactPhoneVerified, phoneVerifyEnabled, whatsappOptIn, setWhatsappOptIn, loginMethod, sendingVerification, setSendingVerification, verifyingPhone, setVerifyingPhone, phoneCode, setPhoneCode, sendingPhoneVerify, setSendingPhoneVerify, checkingPhoneCode, setCheckingPhoneCode, saving } = f
  const { cancelEditing, saveSection } = ed
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.loginMethod')}</label>
        <input
          type="text"
          value={loginMethod || '—'}
          disabled
          className="w-full px-3 py-2.5 border border-ground-200 rounded-lg text-sm bg-ground-50 text-ground-500 cursor-not-allowed"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.contactEmail')}</label>
        <div className="flex gap-2">
          <input
            type="email"
            value={contactEmail}
            onChange={e => setContactEmail(e.target.value)}
            className="flex-1 px-3 py-2.5 border border-ground-300 rounded-lg text-sm focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none"
          />
          <button
            onClick={async () => {
              if (!contactEmail || !token) return
              setSendingVerification(true)
              try {
                // Save first, then send verification
                await updateProfile({ contact_email: contactEmail }, { token })
                await sendVerificationEmail(contactEmail, locale, { token })
                showToast(t('profile.verificationSent'), 'success')
                window.dispatchEvent(new Event('profile-updated'))
              } catch {
                showToast('Failed to send verification email.', 'error')
              } finally {
                setSendingVerification(false)
              }
            }}
            disabled={!contactEmail || sendingVerification}
            className="px-4 py-2.5 bg-primary-50 text-primary-700 border border-primary-200 rounded-lg text-sm font-medium hover:bg-primary-100 disabled:opacity-50 whitespace-nowrap"
          >
            {sendingVerification ? '...' : t('profile.verify')}
          </button>
        </div>
        <p className="text-xs text-ground-400 mt-1">{t('profile.emailVerifyNote')}</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-ground-700 mb-1.5">{t('profile.contactPhone')}</label>
        <div className="flex gap-2">
          <input
            type="tel" autoComplete="tel-national"
            value={contactPhone}
            onChange={e => {
              setContactPhone(formatPhone(e.target.value))
              setContactPhoneVerified(false)   // editing the number un-verifies it
              setVerifyingPhone(false)
            }}
            placeholder="012-345 6789"
            className="flex-1 px-3 py-2.5 border border-ground-300 rounded-lg text-sm focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none"
          />
          {phoneVerifyEnabled && (
          <button
            onClick={async () => {
              if (!contactPhone || !token) return
              setSendingPhoneVerify(true)
              try {
                // Save first, then send the code (as in the email Verify flow)
                await updateProfile({ contact_phone: contactPhone }, { token })
                await sendPhoneVerification(contactPhone, { token })
                setVerifyingPhone(true)
                setPhoneCode('')
                showToast(t('profile.phoneCodeSent'), 'success')
              } catch {
                showToast(t('profile.phoneVerifyFailed'), 'error')
              } finally {
                setSendingPhoneVerify(false)
              }
            }}
            disabled={!contactPhone || sendingPhoneVerify}
            className="px-4 py-2.5 bg-primary-50 text-primary-700 border border-primary-200 rounded-lg text-sm font-medium hover:bg-primary-100 disabled:opacity-50 whitespace-nowrap"
          >
            {sendingPhoneVerify ? '...' : t('profile.verify')}
          </button>
          )}
        </div>
        {contactPhoneVerified && (
          <p className="text-xs text-positive-700 mt-1.5 font-medium">✓ {t('profile.phoneVerified')}</p>
        )}
        {!phoneVerifyEnabled && !contactPhoneVerified && (
          <p className="text-xs text-ground-500 mt-1.5">{t('profile.phoneVerifyPaused')}</p>
        )}
        {phoneVerifyEnabled && verifyingPhone && !contactPhoneVerified && (
          <div className="mt-2 space-y-1.5">
            <p className="text-xs text-ground-500">{t('profile.phoneCodeSent')}</p>
            <div className="flex gap-2">
              <input
                type="text"
                inputMode="numeric" autoComplete="one-time-code"
                value={phoneCode}
                onChange={e => setPhoneCode(e.target.value.replace(/\D/g, '').slice(0, 8))}
                placeholder={t('profile.phoneCodePlaceholder')}
                className="flex-1 px-3 py-2.5 border border-ground-300 rounded-lg text-sm tracking-widest focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none"
              />
              <button
                onClick={async () => {
                  if (!phoneCode || !token) return
                  setCheckingPhoneCode(true)
                  try {
                    const res = await checkPhoneVerification(phoneCode, contactPhone, { token })
                    if (res.verified) {
                      setContactPhoneVerified(true)
                      setVerifyingPhone(false)
                      setPhoneCode('')
                      showToast(t('profile.phoneVerified'), 'success')
                      window.dispatchEvent(new Event('profile-updated'))
                    } else {
                      showToast(t('profile.phoneCodeWrong'), 'error')
                    }
                  } catch {
                    showToast(t('profile.phoneCodeWrong'), 'error')
                  } finally {
                    setCheckingPhoneCode(false)
                  }
                }}
                disabled={!phoneCode || checkingPhoneCode}
                className="px-4 py-2.5 bg-brand-fill text-brand-fill-ink rounded-lg text-sm font-medium hover:bg-brand-fill-hover disabled:opacity-50 whitespace-nowrap"
              >
                {checkingPhoneCode ? '...' : t('profile.confirm')}
              </button>
            </div>
          </div>
        )}
        {phoneVerifyEnabled && (
          <p className="text-xs text-ground-400 mt-1.5">{t('profile.phoneVerifyNote')}</p>
        )}
      </div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="text-sm font-medium text-ground-700">{t('profile.whatsappUpdates')}</span>
          <p className="text-xs text-ground-400 mt-0.5">{t('profile.whatsappUpdatesNote')}</p>
        </div>
        <Toggle on={whatsappOptIn} onChange={setWhatsappOptIn} label={t('profile.whatsappUpdates')} />
      </div>
      <div className="flex gap-3 pt-4">
        <button onClick={cancelEditing} className="flex-1 px-4 py-2.5 border border-ground-300 rounded-lg text-sm font-medium text-ground-700 hover:bg-ground-50">
          {t('profile.cancel')}
        </button>
        <button onClick={saveSection} disabled={saving} className="flex-1 px-4 py-2.5 bg-brand-fill text-brand-fill-ink rounded-lg text-sm font-medium hover:bg-brand-fill-hover disabled:opacity-50">
          {saving ? '...' : t('profile.save')}
        </button>
      </div>
    </div>
  )
}
