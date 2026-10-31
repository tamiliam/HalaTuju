'use client'

import { CardFrame, inputCls, labelCls, readOnlyCls, Req, type CardProps } from './shared'

/** "You" — the person's own name (required) and the sign-in email, shown, never edited.
 *  Everyone. (S2 adds the photo, job title and About.) */
export default function YouCard({ state }: CardProps) {
  const { t, draft, set, email } = state
  return (
    <CardFrame title={t('admin.myProfile.you')} testId="you">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="profile-name" className={labelCls}>{t('admin.name')}<Req /></label>
          <input id="profile-name" type="text" required value={draft.name}
            onChange={(e) => set({ name: e.target.value })} className={inputCls} />
        </div>
        <div>
          <label htmlFor="profile-email" className={labelCls}>{t('admin.myProfile.signInEmail')}</label>
          <input id="profile-email" className={readOnlyCls} value={email} disabled readOnly />
        </div>
      </div>
    </CardFrame>
  )
}
