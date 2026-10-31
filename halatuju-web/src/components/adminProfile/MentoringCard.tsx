'use client'

import { useEffect } from 'react'
import { CardFrame, inputCls, labelCls, Req, type CardProps } from './shared'

/** `Mentor.area`'s width, the cap `PATCH admin/me/` enforces (`MENTORING_AREA_MAX`). */
export const MENTORING_AREA_MAX = 120

/**
 * "Mentoring" — a MENTOR's own area of mentoring (student maintenance S7a, 2026-10-31; the
 * MentorProfile board). Required: Save sleeps while it is blank. Written by the mentor alone, with the
 * page's Save, through `admin/me/` (`mentoring_area`); staff use it to match the mentor with students,
 * and the mentor's students see it too.
 */
export default function MentoringCard({ state }: CardProps) {
  const { t, draft, set, report } = state
  const blank = !draft.mentoringArea.trim()
  useEffect(() => { report('mentoringArea', blank) }, [blank, report])
  return (
    <CardFrame title={t('admin.mentors.profile.title')} testId="mentoring">
      <div>
        <label htmlFor="profile-mentoring-area" className={labelCls}>
          {t('admin.mentors.profile.area')}<Req />
        </label>
        <input id="profile-mentoring-area" type="text" className={inputCls} maxLength={MENTORING_AREA_MAX}
          value={draft.mentoringArea} placeholder={t('admin.mentors.profile.areaPlaceholder')}
          onChange={(e) => set({ mentoringArea: e.target.value })} />
      </div>
      <p className="text-xs text-ground-500">{t('admin.mentors.profile.areaHint')}</p>
    </CardFrame>
  )
}
