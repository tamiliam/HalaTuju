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
      perm: 'qc',
      title: 'What QC is',
      body: (
        <>QC is the <strong>second pair of eyes</strong>. After a reviewer records their verdict, the case waits at
        <strong> Interviewed (awaiting QC)</strong> for you to check the work before it becomes a recommendation a
        sponsor can see. You see <strong>every</strong> application in your organisation, not just assigned ones.
        <br /><br />
        <em>Your organisation may have given you more than this role&rsquo;s usual set</em> &mdash; for
        example the Spending page. If it has, the parts of the Guide that describe it appear in the
        sidebar under the role they come from.</>
      ),
      img: '/manual/qc-queue.png',
      alt: 'The awaiting-QC queue (placeholder — screenshot pass pending)',
    },
    {
      anchor: 'qc-overview',
      title: 'Where you land: the queue',
      body: (
        <>Signing in brings you to <strong>Overview</strong>, the first entry under your gift in the menu. It
        opens on <strong>the cases waiting for QC</strong> — how many there are, <strong>how long the oldest
        one has been waiting</strong>, and the list itself with the longest wait at the top, so the case most
        at risk of being forgotten is the one you see first. Beside it is a short note on your own pace: how
        many you have checked, and how long a case sat with QC before you got to it. It is a measure of the
        wait, not a score on you.
        <br /><br />
        The page shows <strong>your work and nothing wider</strong> — no money, and none of the
        programme&rsquo;s overall figures, which belong to the people who run the gift. An <strong>intake
        year</strong> picker at the top narrows the queue to one round, if you want it.</>
      ),
    },
    {
      anchor: 'qc-accept-reopen',
      perm: 'qc',
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
      anchor: 'qc-facts-in-doubt',
      perm: 'qc',
      title: 'Facts in doubt',
      body: (
        <>Above the buttons, a small <strong>Facts in doubt</strong> box lists only the facts where the reviewer
        and the AI did not agree: the AI said green and the reviewer said Fail, or the reviewer said Fail but
        still recommended the student. Each one shows what the AI said, what the reviewer said and their
        reason. <strong>Doing nothing means you agree with the reviewer.</strong> If you do not, tap
        <strong> Disagree with the reviewer</strong> on that fact; tap it again to undo. Your answer is sent with
        your Accept, Reopen or Reject. On <strong>Accept</strong>, a fact you did not touch is recorded as
        &ldquo;agreed&rdquo;. On <strong>Reopen</strong> or <strong>Reject</strong>, only a Disagree tap is
        recorded; a fact you did not touch records nothing. It never blocks or delays your decision. The
        answers feed the <strong> checked by the QC</strong> numbers on the AI prediction card, so the team can
        see how often the QC agreed with the reviewer on these facts.</>
      ),
    },
    {
      anchor: 'qc-gap-floor',
      perm: 'qc',
      title: 'The gap floor',
      body: (
        <>If any of the four facts is still <strong className="text-critical-700">red</strong>, <strong>Accept is
        blocked</strong> — a red fact must not reach sponsors unexamined. Resolve the gap (or reopen to the
        reviewer). If you&rsquo;re certain despite the red — say you verified it offline — you may
        <strong> override with a recorded reason</strong>, which is kept on the case.</>
      ),
    },
    {
      anchor: 'qc-review-all',
      perm: 'qc',
      title: 'You can review, not just QC',
      body: (
        <>You&rsquo;re also a <strong>review-all</strong> role: you can act on any case in your organisation, so
        you can step in as an <strong>overflow reviewer</strong> when the team is stretched, or pick up a case
        nobody&rsquo;s assigned. Assignment still routes most cases to reviewers — this is for when you need to
        help clear the queue.</>
      ),
    },
    {
      anchor: 'qc-reviewer-notes',
      perm: 'qc',
      title: 'Org admin and reviewer notes',
      body: (
        <>A case may carry <strong>Org admin and reviewer notes</strong>, under <strong>Reviewer
        assigned</strong>: what the organisation admin asked the reviewer to explore, and the reviewer&rsquo;s
        replies, each marked with its side and date. They are read-only for you. When you check a case, it is
        worth seeing whether the review answered them.</>
      ),
    },
    {
      anchor: 'qc-no-conflict',
      perm: 'qc',
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
