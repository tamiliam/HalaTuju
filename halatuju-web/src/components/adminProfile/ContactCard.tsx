'use client'

import Toggle from '@/components/Toggle'
import { CardFrame, labelCls, PhoneField, Req, type CardProps } from './shared'

/** "Contact details" — the phone (required, as it always was for a reviewer) and whether students
 *  the person interviews may see it. S1: holders of `review` only (S2 widens it to everyone). */
export default function ContactCard({ state }: CardProps) {
  const { t, draft, setRev } = state
  const rev = draft.reviewer
  const share = rev?.share_phone_with_students ?? true
  return (
    <CardFrame title={t('admin.reviewer.contactTitle')} subtitle={t('admin.reviewer.contactSubtitle')}
      icon="🔒" testId="contact">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="profile-phone" className={labelCls}>{t('admin.reviewer.phone')}<Req /></label>
          <PhoneField id="profile-phone" value={rev?.phone ?? ''} onChange={(v) => setRev({ phone: v })} />
        </div>
      </div>
      <div className="flex items-start gap-3 text-sm text-ground-700">
        <Toggle on={share} label={t('admin.reviewer.sharePhone')}
          onChange={(v) => setRev({ share_phone_with_students: v })} />
        <span>{t('admin.reviewer.sharePhone')}</span>
      </div>
    </CardFrame>
  )
}
