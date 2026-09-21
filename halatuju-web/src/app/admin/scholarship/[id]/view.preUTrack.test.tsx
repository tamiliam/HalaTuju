/**
 * @jest-environment jsdom
 *
 * THE MALAY PRE-U TRACK LABEL ON THE OFFICER COCKPIT — the words, after TD-280 moved the lookup
 * to the server (code health H18).
 *
 * **What changed, and what did not.** Until H18 this label was computed in the browser, by
 * `lib/preUPlan.preUTrackMalay`, out of a static `import ms from '@/messages/ms.json'`. That one
 * import was **130 kB of first-load JS on `/admin/scholarship/[id]`** — the whole Malay catalogue,
 * downloaded by an officer who is usually reading English, to look up **sixteen words**. The api
 * already held the same map, so the api resolves the label now and serves it on the payload as
 * `pre_u_track_label`; the cockpit renders what it is given (served, not mirrored).
 *
 * **This file is the proof that the officer reads the same words as before.** Nothing else can
 * give it: `tsc` proves the field exists, the api's `TestCockpitTrackLabelParity` proves the
 * served word matches `messages/ms.json`, and only a RENDER proves the word reaches the screen —
 * in the right field, after the right course name, with the middot the officer is used to.
 *
 * ⚠ The harness's `t` echoes its key, so the programme NAME here reads as a dotted path. The
 * label under test is a real Malay word either way: it is data, not copy, and it is exactly what
 * a sponsor card and an email would print.
 */
import { screen } from '@testing-library/react'

import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')

/** An STPM applicant whose stream the api has resolved — the shape the cockpit now receives. */
const stpm = (label: string | null) => ({
  stage: 'interviewing' as const,
  role: 'reviewer' as const,
  build: {
    chosen_pathway: 'stpm',
    pre_u_track: 'sains_sosial',
    pre_u_track_label: label,
    chosen_programme: { course_name: 'Tingkatan Enam' },
    chosen_programme_display: { title: 'Tingkatan Enam', stream: '' },
  },
})

describe('the officer reads the SERVED Malay pre-U track label', () => {
  it('⚠ renders the Malay word beside the programme, exactly as it always has', async () => {
    renderCockpit(stpm('Sains Sosial'))
    await loaded()
    // ⚠ BITE (d). Change the served label — in `card_display._TRACK_LABEL`, in
    // `_COCKPIT_ONLY_TRACK_LABEL`, or in the payload — and this line is red with the word it got.
    expect(screen.getByText('· Sains Sosial')).toBeTruthy()
  })

  it('⚠ renders "Belum pasti" for the undecided stream, which the sponsor card never shows', async () => {
    // The one code the cockpit labels and `preu_label` deliberately ignores: on a sponsor card
    // "STPM · Belum pasti" would read as a specialisation. The cockpit has always shown it,
    // because the FE read the whole `plan.stream` block; serving the label kept that.
    renderCockpit({ ...stpm('Belum pasti'), build: { ...stpm('Belum pasti').build,
      pre_u_track: 'not_sure' } })
    await loaded()
    expect(screen.getByText('· Belum pasti')).toBeTruthy()
  })

  it('⚠ shows NO suffix when the api resolved none — it never re-derives one', async () => {
    // ⚠ BITE (e). The cockpit holds no track map any more. If this ever passes while
    // `pre_u_track_label` is null AND a word appears, somebody has put a second home for these
    // labels back into the bundle — which is the whole of TD-280 arriving again.
    renderCockpit(stpm(null))
    await loaded()
    expect(screen.queryByText(/· Sains Sosial/)).toBeNull()
    expect(screen.queryByText(/Sains Sosial/)).toBeNull()
  })
})

/**
 * THE STAGED-DEPLOY WINDOW — the api one revision behind (audit 2026-09-21, finding G).
 *
 * `pre_u_track_label` was typed `string | null`, REQUIRED. The two services deploy together but
 * not atomically, and the browser also holds cached payloads: an api revision that predates
 * TD-280 does not send the field at all, so the value is `undefined` and the type is a lie the
 * compiler cannot see. Everything downstream — a `.trim()`, a `.length`, a `??` that never fires
 * — is then written against a guarantee that does not hold, and `tsc` is a deploy gate here.
 *
 * ⚠ **THE MISSING FIELD SHOWS NOTHING, ON PURPOSE, AND THAT IS NOT LAZINESS.** The obvious
 * "fallback" would be to look the code up in the browser — which is precisely TD-280, the 130 kB
 * of Malay catalogue H18 removed from this route, and re-adding it is refused by
 * `oneLocalePerVisitor.test.ts` and by the bundle budget. The payload carries no English track
 * label to fall back on either. So the parenthesis is omitted: the officer reads the programme
 * name without a suffix for the length of one deploy, rather than a raw `sains_sosial` or the
 * word `undefined`.
 */
describe('an api one revision behind, which does not send the label at all', () => {
  it('⚠ the TYPE admits a payload without the field — the whole of the finding', () => {
    // RED before the fix, in `npm run typecheck` — the FIRST gate `npm run gates` runs — with
    // "Property 'pre_u_track_label' is missing in type Omit<…> but required in type
    // AdminScholarshipDetail". No runtime assertion can catch a type lie: a field the api simply
    // does not send arrives as `undefined` whatever the declaration claims, and the only
    // instrument that sees the difference is the compiler.
    const fromAnOlderApi = (
      payload: Omit<AdminScholarshipDetail, 'pre_u_track_label'>,
    ): AdminScholarshipDetail => payload
    expect(typeof fromAnOlderApi).toBe('function')
  })

  it('renders the programme with no suffix — never a raw code, never the word "undefined"', async () => {
    const build = { ...stpm(null).build } as Record<string, unknown>
    delete build.pre_u_track_label
    renderCockpit({ ...stpm(null), build })
    await loaded()
    expect(screen.getByText('Tingkatan Enam')).toBeTruthy()
    expect(screen.queryByText(/undefined/)).toBeNull()
    expect(screen.queryByText(/sains_sosial/)).toBeNull()
    expect(screen.queryByText(/·\s*$/)).toBeNull()
  })
})
