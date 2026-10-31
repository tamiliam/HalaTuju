'use client'

import Toggle from '@/components/Toggle'
import { CardFrame, labelCls, PhoneField, Req, type CardProps } from './shared'

/**
 * "Contact details" — everyone (common profile S2): the phone (+60), required only for a holder of
 * `review` (the onboarding rule), and who may see it:
 *  - staff: "Show my phone to my team" (the Team / People page), off by default;
 *  - a referral partner or a source user has no team: a note that the organisation that invited
 *    them can see the number instead;
 *  - a holder of `review` also: "Share my phone with students I interview" (unchanged behaviour).
 * Saved with the page's Save, through `admin/me/`.
 */
export default function ContactCard({ state }: CardProps) {
  const { t, draft, setCard, reviews, role } = state
  const card = draft.card
  const outside = role === 'source_partner' || role === 'partner'
  return (
    <CardFrame title={t('admin.reviewer.contactTitle')} icon="🔒" testId="contact">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="profile-phone" className={labelCls}>{t('admin.reviewer.phone')}{reviews && <Req />}</label>
          <PhoneField id="profile-phone" value={card.phone} onChange={(v) => setCard({ phone: v })} />
        </div>
      </div>
      {outside ? (
        <p className="text-sm text-ground-600" data-testid="phone-seen-by-inviter">{t('admin.myProfile.inviterSees')}</p>
      ) : (
        <div className="flex items-start gap-3 text-sm text-ground-700">
          <Toggle on={card.share_phone_with_team} label={t('admin.myProfile.showToTeam')}
            onChange={(v) => setCard({ share_phone_with_team: v })} />
          <span>{t('admin.myProfile.showToTeam')}</span>
        </div>
      )}
      {reviews && (
        <div className="flex items-start gap-3 text-sm text-ground-700">
          <Toggle on={card.share_phone_with_students} label={t('admin.reviewer.sharePhone')}
            onChange={(v) => setCard({ share_phone_with_students: v })} />
          <span>{t('admin.reviewer.sharePhone')}</span>
        </div>
      )}
      {/* Review fix M1: whoever can be assigned cases is reachable by the people who assign them
          (the reviewer detail, 2026-08-02), so "nobody else" would not be true for them. */}
      {!outside && (
        <p className="text-xs text-ground-500 italic" data-testid="phone-who-sees">
          {t(reviews ? 'admin.myProfile.assignerSees' : 'admin.myProfile.contactPrivate')}
        </p>
      )}
    </CardFrame>
  )
}
