import type { ManualChapter } from './types'

/** Basics 3 — the statuses glossary (lifted + extended from the reviewer FAQ answer). */
export const basicsStatuses: ManualChapter = {
  slug: 'basics-statuses',
  title: 'Statuses',
  group: 'basics',
  blurb: 'What each application status means.',
  sections: [
    {
      anchor: 'status-glossary',
      title: 'The status glossary',
      body: (
        <>An application&rsquo;s status tells you which stage it&rsquo;s at:
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li><strong>Shortlisted</strong> — passed the first checks and invited to complete their
            application.</li>
            <li><strong>Awaiting review</strong> — the student has confirmed their details and documents; the
            case is with us and not yet reviewed.</li>
            <li><strong>Interviewing</strong> — interview times proposed or booked.</li>
            <li><strong>Interviewed</strong> — the interview is done and findings submitted; the case is now
            <strong> awaiting QC</strong>.</li>
            <li><strong>Recommended</strong> — QC has accepted it; the student is now visible to sponsors.</li>
            <li><strong>Awarded → Active → Maintenance → Closed</strong> — the post-award lifecycle once a
            sponsor funds the student.</li>
            <li><strong>Rejected</strong> / <strong>Expired</strong> — declined, or lapsed without completing.</li>
          </ul>
          <span className="mt-2 block">Most review work happens on <em>Awaiting review</em> and
          <em> Interviewing</em>; QC work is on <em>Interviewed</em> (awaiting QC).</span></>
      ),
    },
    {
      anchor: 'status-colours',
      title: 'Reopened',
      body: (
        <>If a recorded decision is <strong>reopened</strong> (only a super-admin can do this), the case shows a
        <strong> Reopened</strong> banner and returns to the reviewer to revise. It&rsquo;s the one way a
        finished case comes back — everything else moves forward.</>
      ),
    },
  ],
}
