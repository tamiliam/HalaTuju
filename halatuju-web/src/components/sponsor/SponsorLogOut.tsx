'use client'

/**
 * The sponsor's Log out — ONE implementation for every place it is drawn (Mobile M5): the desktop top
 * row, the slim phone header on the screens without tabs (details form, terms wizard, pending,
 * inactive), and My Account on a phone (where it lives once the tabs are shown).
 *
 * ⚠ BEHAVIOUR IS EXACTLY WHAT THE PORTAL SHELL DID BEFORE M5, moved, not changed: `sponsorSignOut()`
 * ends the SPONSOR session only (`scope: 'local'` on the sponsor's own isolated client — the student
 * and admin sessions on this device are untouched), then the tab goes to `/sponsor/login`. Eager, never
 * lazy: it is the only way out (the M2 lesson).
 */
import { useRouter } from 'next/navigation'
import { useT } from '@/lib/i18n'
import { sponsorSignOut } from '@/lib/sponsor-supabase'

export default function SponsorLogOut({ className }: { className: string }) {
  const { t } = useT()
  const router = useRouter()
  const signOut = async () => {
    await sponsorSignOut()
    router.replace('/sponsor/login')
  }
  return (
    <button type="button" onClick={signOut} className={className} data-testid="sponsor-logout">
      {t('header.logout')}
    </button>
  )
}
