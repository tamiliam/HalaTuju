'use client'

import { MALAYSIAN_STATES } from '@/lib/scholarship'
import { CardFrame, inputCls, labelCls, type CardProps } from './shared'

/** "Address" — street, postcode, city, state; private (unchanged fields). Holders of `review`,
 *  never a super. */
export default function AddressCard({ state }: CardProps) {
  const { t, draft, setRev } = state
  const rev = draft.reviewer
  return (
    <CardFrame title={t('admin.reviewer.address')} subtitle={t('admin.reviewer.contactSubtitle')}
      icon="🔒" testId="address">
      <div>
        <label htmlFor="profile-street" className={labelCls}>{t('admin.reviewer.street')}</label>
        <input id="profile-street" type="text" value={rev?.street_address ?? ''}
          onChange={(e) => setRev({ street_address: e.target.value })} className={inputCls} />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label htmlFor="profile-postcode" className={labelCls}>{t('admin.reviewer.postcode')}</label>
          <input id="profile-postcode" type="text" inputMode="numeric" value={rev?.postcode ?? ''}
            onChange={(e) => setRev({ postcode: e.target.value.replace(/[^0-9]/g, '').slice(0, 5) })}
            className={inputCls} />
        </div>
        <div>
          <label htmlFor="profile-city" className={labelCls}>{t('admin.reviewer.city')}</label>
          <input id="profile-city" type="text" value={rev?.city ?? ''}
            onChange={(e) => setRev({ city: e.target.value })} className={inputCls} />
        </div>
        <div>
          <label htmlFor="profile-state" className={labelCls}>{t('admin.reviewer.state')}</label>
          <select id="profile-state" value={rev?.state ?? ''} onChange={(e) => setRev({ state: e.target.value })}
            className={inputCls}>
            <option value="">{t('admin.reviewer.selectState')}</option>
            {MALAYSIAN_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>
    </CardFrame>
  )
}
