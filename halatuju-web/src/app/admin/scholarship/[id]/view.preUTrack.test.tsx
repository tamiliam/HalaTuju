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
