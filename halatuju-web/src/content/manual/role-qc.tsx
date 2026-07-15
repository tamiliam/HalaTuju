import type { ManualChapter } from './types'

/** QC chapter — the second pair of eyes, plus the review-all powers and the no-conflict rule. */
export const roleQc: ManualChapter = {
  slug: 'role-qc',
  title: 'QC',
  group: 'role',
  role: 'qc',
  blurb: 'The second pair of eyes on a recommendation — and an overflow reviewer.',
  sections: [
    {
      anchor: 'qc-what-it-is',
      title: 'What QC is',
      body: (
        <>QC is the <strong>second pair of eyes</strong>. After a reviewer records their verdict, the case waits at
        <strong> Interviewed (awaiting QC)</strong> for you to check the work before it becomes a recommendation a
        sponsor can see. You see <strong>every</strong> application in your organisation, not just assigned ones.</>
      ),
      img: '/manual/qc-queue.png',
      alt: 'The awaiting-QC queue (placeholder — screenshot pass pending)',
    },
    {
      anchor: 'qc-accept-reopen',
      title: 'Accept or Reopen',
      body: (
        <>On an awaiting-QC case, the <strong>Quality control</strong> box gives you two choices:
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li><strong>Accept</strong> — you&rsquo;re satisfied. The case becomes <strong>Recommended</strong>
            and the student becomes visible to sponsors. This is the single point that publishes a student.</li>
            <li><strong>Reopen</strong> — something&rsquo;s missing. Write what the reviewer must address; the case
            goes back to them at <em>Interviewing</em> and they&rsquo;re emailed your comments.</li>
          </ul></>
      ),
    },
    {
      anchor: 'qc-gap-floor',
      title: 'The gap floor',
      body: (
        <>If any of the four facts is still <strong className="text-red-700">red</strong>, <strong>Accept is
        blocked</strong> — a red fact must not reach sponsors unexamined. Resolve the gap (or reopen to the
        reviewer). If you&rsquo;re certain despite the red — say you verified it offline — you may
        <strong> override with a recorded reason</strong>, which is kept on the case.</>
      ),
    },
    {
      anchor: 'qc-review-all',
      title: 'You can review, not just QC',
      body: (
        <>You&rsquo;re also a <strong>review-all</strong> role: you can act on any case in your organisation, so
        you can step in as an <strong>overflow reviewer</strong> when the team is stretched, or pick up a case
        nobody&rsquo;s assigned. Assignment still routes most cases to reviewers — this is for when you need to
        help clear the queue.</>
      ),
    },
    {
      anchor: 'qc-no-conflict',
      title: 'The no-conflict rule',
      noConflictBanner: true,
      body: (
        <>Two-person control means you can <strong>never QC a case whose verdict you recorded</strong>, and never
        QC a case you were the assigned reviewer of — it routes to another QC. Now that you can also review cases,
        this matters: if you review or record a verdict on a case, someone else must QC it. (A super-admin is the
        only exception, as the owner override.)</>
      ),
    },
  ],
}
