'use client'

/**
 * TD-254 — "this IC number is already registered". The step a student sees when the IC they
 * typed belongs to an account that already exists.
 *
 * **WHAT IT DOES NOT DO, AND THAT IS THE POINT.** It never learns who the holder is: the server
 * answers `exists` with the challenge CHANNELS and nothing else, so there is no name to render,
 * no masked address to leak, and no prop here that could carry one. The old build put the
 * holder's name in a confirm dialog and offered a one-click takeover; that dialog is what this
 * file replaces.
 *
 * The student proves the account is theirs by answering a code sent to a contact ALREADY ON it
 * that is ALREADY VERIFIED. If there is no such contact the honest answer is a person, not a
 * button — `channels: []` lands straight on the support copy.
 *
 * It lives in its own file so `AuthGateModal.tsx` stays inside the 600-line standard, and it
 * borrows that modal's existing styles rather than inventing a layout (a new layout would need
 * a design prototype first).
 */
import { useState } from 'react'

import { sendClaimCode, confirmClaimCode } from '@/lib/api'
import { useT } from '@/lib/i18n'
import {
  claimChannelKey, claimCodeHelpKey, claimHelpKey, claimRefusalKey, type ClaimChannel,
} from '@/lib/profileClaim'

interface IcClaimPanelProps {
  /** The formatted IC the student typed. Never anybody's name — there is nothing else to pass. */
  ic: string
  token: string
  lang: string
  /** Bare channel types, exactly as the server listed them. Empty = no self-service route. */
  channels: ClaimChannel[]
  onClaimed: () => void | Promise<void>
  onNotMe: () => void
}

/** The stable refusal code the API put on the thrown error (see `apiRequest`). */
function refusalCodeOf(err: unknown): string | undefined {
  return (err as { code?: string } | null)?.code
}

export default function IcClaimPanel({
  ic, token, lang, channels, onClaimed, onNotMe,
}: IcClaimPanelProps) {
  const { t } = useT()
  const [step, setStep] = useState<'offer' | 'code'>('offer')
  const [channel, setChannel] = useState<ClaimChannel>(channels[0] ?? 'email')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  // No door at all is not an error the student caused — it is the answer, shown straight away.
  const [messageKey, setMessageKey] = useState<string | null>(
    channels.length === 0 ? 'authGate.claim.refusal.noContact' : null,
  )

  const handleSend = async (pick: ClaimChannel) => {
    setChannel(pick)
    setLoading(true)
    setMessageKey(null)
    try {
      await sendClaimCode(ic, pick, lang, { token })
      setCode('')
      setStep('code')
    } catch (err) {
      setMessageKey(claimRefusalKey(refusalCodeOf(err)))
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMessageKey(null)
    try {
      await confirmClaimCode(ic, code, { token })
      await onClaimed()
    } catch (err) {
      setMessageKey(claimRefusalKey(refusalCodeOf(err)))
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-ground-600 text-center">{t('authGate.icExistsMessage')}</p>

      {step === 'offer' && channels.length > 0 && (
        <p className="text-ground-600 text-center text-sm">{t(claimHelpKey(channels))}</p>
      )}

      {messageKey && (
        <div className="bg-critical-50 border border-critical-200 rounded-lg p-3">
          <p className="text-critical-600 text-sm">{t(messageKey)}</p>
        </div>
      )}

      {step === 'offer' && channels.length > 0 && (
        <>
          <p className="text-ground-700 text-sm font-medium text-center">
            {t('authGate.icYesMe')}
          </p>
          <div className="space-y-2">
            {channels.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => handleSend(option)}
                disabled={loading}
                className="btn-primary w-full disabled:opacity-50"
              >
                {loading && channel === option
                  ? t('authGate.claim.sending')
                  : t(claimChannelKey(option))}
              </button>
            ))}
          </div>
        </>
      )}

      {step === 'code' && (
        <form onSubmit={handleConfirm} className="space-y-3">
          <p className="text-ground-600 text-sm text-center">{t(claimCodeHelpKey(channel))}</p>
          <div>
            <label
              htmlFor="ic-claim-code"
              className="block text-sm font-medium text-ground-700 mb-1"
            >
              {t('authGate.claim.codeLabel')}
            </label>
            <input
              id="ic-claim-code"
              type="text"
              inputMode="numeric"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="000000"
              maxLength={6}
              className="input text-center text-2xl tracking-widest"
            />
          </div>
          <button
            type="submit"
            disabled={loading || code.length !== 6}
            className="btn-primary w-full disabled:opacity-50"
          >
            {loading ? t('authGate.claim.confirming') : t('authGate.claim.confirm')}
          </button>
        </form>
      )}

      <button
        type="button"
        onClick={onNotMe}
        className="w-full px-4 py-2 border border-ground-300 rounded-lg text-ground-700 hover:bg-ground-50"
      >
        {t('authGate.icNotMe')}
      </button>
    </div>
  )
}
