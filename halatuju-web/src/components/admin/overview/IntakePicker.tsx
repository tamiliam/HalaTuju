'use client'
/**
 * Which intake year the Overview is describing.
 *
 * ⚠ A NATIVE `<select>`, not a menu we drew. The rounds are a short, flat, known list and the
 * native control already works on a phone, with a keyboard and with a screen reader; a custom
 * popover would be three of those again, badly. (The console's other picker of this shape — the
 * Configuration tab's vocabulary rows — made the same call.)
 *
 * ⚠ "ALL INTAKES" IS THE EMPTY VALUE, AND IT SENDS NO PARAMETER AT ALL. Sending nothing is what
 * says "no narrowing was asked for" rather than "narrow to nothing" — the same distinction the
 * gift query draws (`admin-api.giftQuery`).
 *
 * ⚠ NOTHING IS DRAWN UNLESS THERE ARE AT LEAST TWO ROUNDS. A gift with no intakes, or no gift
 * chosen at all, gets an empty list from the server; a picker with one option that changes nothing
 * is furniture. A gift with exactly ONE round is the same furniture: "All intakes" and that round
 * describe the same cases, so the choice changes nothing (owner, 2026-09-29).
 * The server still sends that one round, and must: a round chosen by URL is named under the
 * heading from the payload's own `intake` ("Showing the … intake only"), not from this list, and
 * choosing nothing sends no parameter at all — so hiding the picker leaves both exactly as they were.
 */
import { useT } from '@/lib/i18n'
import type { OverviewIntake } from '@/lib/admin-api'

/** ⚠ The i18n guard resolves `${K}.` templates by this LITERAL name. */
const K = 'admin.programmeOverview'

export default function IntakePicker({ intakes, value, onChange }: {
  intakes: OverviewIntake[]
  /** The chosen cohort id, or `undefined` for every round. */
  value?: number
  onChange: (intake: number | undefined) => void
}) {
  const { t } = useT()
  if (intakes.length < 2) return null

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <label className="text-sm text-ground-600" htmlFor="overview-intake">
        {t(`${K}.intakes.label`)}
      </label>
      <select
        id="overview-intake"
        data-testid="intake-picker"
        value={value === undefined ? '' : String(value)}
        onChange={(e) => onChange(e.target.value === '' ? undefined : Number(e.target.value))}
        className="rounded-lg border border-ground-200 bg-ground-0 px-3 py-1.5 text-sm text-ground-900">
        <option value="">{t(`${K}.intakes.all`)}</option>
        {intakes.map((intake) => (
          // The year is in the option because two rounds may share a name across years, and the
          // state is there because a draft round's figures are not a story anybody should quote.
          <option key={intake.id} value={String(intake.id)}>
            {`${intake.name} (${intake.year}) · ${t(`${K}.intakes.state.${intake.state}`)}`}
          </option>
        ))}
      </select>
    </div>
  )
}
