'use client'

/**
 * "Which programme are you applying to?" — asked before the apply form when several gifts are open
 * and nothing named one. Reached ONLY through `LazyGiftChooser` (most students arrive on a gift's
 * own link and never see it, so it stays out of `/scholarship/apply`'s first-load JS).
 *
 * ⚠ PF-1'S REFUSAL, MOVED EARLIER — NOT A RELAXATION OF IT. The server still refuses to guess
 * between two open rounds, because guessing once filed a student under the wrong foundation, funded
 * from the wrong money, with no error anywhere. What changed is WHEN the student meets it: as a
 * question before the first keystroke, instead of a 409 after filling in the whole form.
 *
 * ⚠ IT OFFERS; IT NEVER PRE-SELECTS. Defaulting to the first round would be the same guess in a
 * friendlier costume — and it would be OUR guess recorded as the student's choice. The selection is
 * local state, so every showing (including after "Change") starts empty.
 */
import { useState } from 'react'

import type { IntakeChoice } from '@/lib/api'
import { useT } from '@/lib/i18n'

export default function GiftChooser({ choices, onPick }: {
  choices: IntakeChoice[]
  onPick: (code: string) => void
}) {
  const { t } = useT()
  const [chosen, setChosen] = useState('')
  return (
    <div className="bg-ground-0 border rounded-2xl p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-ground-900">
        {t('scholarship.apply.chooseTitle')}
      </h2>
      <p className="mt-1 text-sm text-ground-600">{t('scholarship.apply.chooseBody')}</p>
      <div className="mt-4 space-y-2">
        {choices.map((c) => (
          <label key={c.code}
            className={`flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-sm ${
              chosen === c.code
                ? 'border-brand-shape bg-primary-50 text-ground-900'
                : 'border-ground-300 text-ground-700 hover:bg-ground-50'}`}>
            <input type="radio" name="apply-programme" value={c.code}
              checked={chosen === c.code}
              onChange={() => setChosen(c.code)}
              className="h-4 w-4 accent-primary-600" />
            {c.name}
          </label>
        ))}
      </div>
      <button type="button" disabled={!chosen} data-testid="apply-choose-continue"
        onClick={() => onPick(chosen)}
        className="mt-5 w-full rounded-lg bg-brand-fill px-4 py-2.5 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
        {t('scholarship.apply.chooseCta')}
      </button>
    </div>
  )
}
