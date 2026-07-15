import type { ManualChapter } from './types'

/** Basics 2 — the four checks + colour code (lifted from the reviewer guide's step 3/4). */
export const basicsFourChecks: ManualChapter = {
  slug: 'basics-four-checks',
  title: 'The four checks',
  group: 'basics',
  blurb: 'The four facts every case turns on, and what the colours mean.',
  sections: [
    {
      anchor: 'the-four-facts',
      title: 'The four facts',
      body: (
        <>Every review comes down to <strong>four facts</strong>: <strong>Identity</strong>,
        <strong> Academic record</strong>, <strong>Pathway</strong> (their study plan or offer), and
        <strong> Income (B40 need)</strong>. The &ldquo;Verification verdict&rdquo; on a case shows what the system
        is confident about and what still needs a human eye.</>
      ),
      img: '/reviewer-guide/step3-checks.png',
      alt: 'The Verification verdict showing the four checks',
    },
    {
      anchor: 'the-colour-code',
      title: 'The colour code',
      body: (
        <>Each fact tile is colour-coded by how certain the evidence is:
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li><strong className="text-green-700">Green — Certain.</strong> The documents back it up.</li>
            <li><strong className="text-blue-700">Blue — Probable.</strong> Likely fine, but worth a glance.</li>
            <li><strong className="text-amber-700">Amber — Unsure.</strong> Needs a human judgement.</li>
            <li><strong className="text-red-700">Red — Can&rsquo;t verify.</strong> The evidence is missing or
            unreadable — someone must act on it.</li>
          </ul>
          <span className="mt-2 block">Green tiles you can move past quickly; the real work is the
          <strong> amber</strong> and <strong>red</strong> ones. A red <em>Pathway</em> usually means no offer
          letter yet; an amber <em>Income</em> often means the STR proof isn&rsquo;t clearly approved; an amber
          <em> Academic</em> means the results slip needs re-reading against the grades.</span></>
      ),
    },
    {
      anchor: 'the-documents',
      title: 'The documents behind each check',
      body: (
        <>The documents the student uploaded sit under those same four facts, each with the system&rsquo;s
        reading and a status. Click to view a document, or <strong>Re-run</strong> to read it again. The
        system&rsquo;s reading is a <em>starting point, not the last word</em> — a person always decides.</>
      ),
      img: '/reviewer-guide/step4-documents.png',
      alt: 'A student document opened for viewing',
    },
  ],
}
