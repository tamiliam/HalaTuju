/**
 * The "Born in" requirement's tick boxes — request #31 (BrightPath, 2026-10-08).
 *
 * An intake year stores the KEYS of the states a student must have been born in
 * (`allowed_birth_states`); the server reads the place-of-birth code in the student's IC against
 * them (`halatuju_api/apps/scholarship/birth_state.py`). An EMPTY list is the rule switched off —
 * the same "the value is the switch" rule as every other requirement, in list form.
 *
 * ⚠ THE KEYS ARE THE SERVER'S, AND A TEST HOLDS THEM THERE. A key offered here that the server does
 * not know is refused on save; a key the server knows and this list lacks could never be ticked.
 * drift-test: halatuju-web/src/lib/__tests__/birthStatesDrift.test.ts
 *
 * The NAMES are the platform's own spelling (`MALAYSIAN_STATES` in `lib/scholarship.ts`, the list
 * the profile stores) and are proper names, shown untranslated in every language as that list is —
 * which is also why this adds no message strings for them (TD-360: every string rides every route).
 */
export const BIRTH_STATES = [
  { key: 'johor', name: 'Johor' },
  { key: 'kedah', name: 'Kedah' },
  { key: 'kelantan', name: 'Kelantan' },
  { key: 'melaka', name: 'Melaka' },
  { key: 'negeri_sembilan', name: 'Negeri Sembilan' },
  { key: 'pahang', name: 'Pahang' },
  { key: 'perak', name: 'Perak' },
  { key: 'perlis', name: 'Perlis' },
  { key: 'pulau_pinang', name: 'Pulau Pinang' },
  { key: 'sabah', name: 'Sabah' },
  { key: 'sarawak', name: 'Sarawak' },
  { key: 'selangor', name: 'Selangor' },
  { key: 'terengganu', name: 'Terengganu' },
  { key: 'wp_kuala_lumpur', name: 'W.P. Kuala Lumpur' },
  { key: 'wp_putrajaya', name: 'W.P. Putrajaya' },
  { key: 'wp_labuan', name: 'W.P. Labuan' },
] as const

const ORDER: readonly string[] = BIRTH_STATES.map((s) => s.key)

/**
 * Tick or untick one state, returning a NEW list in the server's own order.
 *
 * ⚠ A KEY THIS LIST DOES NOT KNOW IS KEPT, at the end, never dropped. Only a hand edit can store
 * one; dropping it on the next save would change the rule without anybody choosing to — the server
 * refuses it instead, and the screen says the save failed.
 */
export function toggleBirthState(current: readonly string[], key: string, on: boolean): string[] {
  const next = new Set(current)
  if (on) next.add(key)
  else next.delete(key)
  return [
    ...ORDER.filter((k) => next.has(k)),
    ...[...next].filter((k) => !ORDER.includes(k)),
  ]
}
