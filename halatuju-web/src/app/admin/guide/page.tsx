/* eslint-disable @next/next/no-img-element */
// Reviewer Guide — a short, friendly walkthrough of the B40 review process.
// Static English content for now (BM/Tamil to follow); images live in /public/reviewer-guide.
// Reviewers reach this only after signing in (gated by the admin layout), so it does not cover
// signing in — it opens with a welcome + a picture of the programme.

const STEPS: { n: number; title: string; body: React.ReactNode; img: string; alt: string }[] = [
  {
    n: 1,
    title: 'Your applicants',
    body: (
      <>On <strong>B40 Applications</strong> you&rsquo;ll see <strong>only the applicants assigned to you</strong> —
      not everyone&rsquo;s. Each row shows the name, source, qualification, merit score and status.</>
    ),
    img: '/reviewer-guide/step1-list.png',
    alt: 'The B40 Applications list showing your assigned applicants',
  },
  {
    n: 2,
    title: 'Opening an applicant',
    body: (
      <>Click a name to open their review screen. Everything is on this one page: their details, the four
      checks, the documents, the interview, and your decision.</>
    ),
    img: '/reviewer-guide/step2-overview.png',
    alt: 'The applicant review screen and details',
  },
  {
    n: 3,
    title: 'The four checks',
    body: (
      <>Your review comes down to <strong>four facts</strong>: <strong>Identity</strong>,
      <strong> Academic record</strong>, <strong>Pathway</strong> (their study plan or offer), and
      <strong> Income (B40 need)</strong>. The &ldquo;Verification verdict&rdquo; shows what the system is
      confident about and what still needs your eye.</>
    ),
    img: '/reviewer-guide/step3-checks.png',
    alt: 'The Verification verdict showing the four checks',
  },
  {
    n: 4,
    title: 'The documents behind each check',
    body: (
      <>The documents the student uploaded sit under those same four facts, each with the system&rsquo;s reading
      and a status. Click to view a document, or &ldquo;Re-run&rdquo; to read it again.</>
    ),
    img: '/reviewer-guide/step4-documents.png',
    alt: 'A student document opened for viewing',
  },
  {
    n: 5,
    title: 'The student profile',
    body: (
      <>The <strong>Student profile (draft)</strong> is a short summary written automatically from the
      student&rsquo;s own application — a helpful starting point, not the final word. It updates itself as the
      student answers questions, and is rewritten into the final version when you save your verdict. You can
      also expand <em>the student&rsquo;s own words</em> underneath.</>
    ),
    img: '/reviewer-guide/step5-profile.png',
    alt: 'The Student profile (draft) card',
  },
  {
    n: 6,
    title: 'Asking the student something',
    body: (
      <>If something&rsquo;s unclear, don&rsquo;t guess. <strong>Raise a query</strong> or
      <strong> request a document</strong> — the student gets an email and replies, and their answer appears in
      the <strong>Outstanding</strong> box. Best done before the interview so your conversation is focused.</>
    ),
    img: '/reviewer-guide/step6-outstanding.png',
    alt: 'The Outstanding box and the raise-a-query controls',
  },
  {
    n: 7,
    title: 'The interview stage',
    body: (
      <>When you&rsquo;re ready to talk to the student, the <strong>Interview Stage</strong> offers suggested
      questions (tap <strong>Suggest interview questions</strong>, or <strong>Generate more</strong> for
      additional ones). Ask your own too. After each point, jot <strong>one line</strong> on what you found,
      then <strong>Submit interview findings</strong>.</>
    ),
    img: '/reviewer-guide/step7-interview.png',
    alt: 'The Interview Stage with suggested questions',
  },
  {
    n: 8,
    title: 'Your decision',
    body: (
      <>In the <strong>Decision</strong> card you:
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>rate the AI&rsquo;s verification — if you think it got a fact right, give it a <strong>Pass</strong>,
          otherwise a <strong>Fail</strong>, for each of the four facts;</li>
          <li>set a <strong>recommended assistance amount</strong> on the slider (an estimated need is shown to
          guide you);</li>
          <li>write a short <strong>conclusion</strong>;</li>
          <li>select <strong>Approve</strong> or <strong>Decline</strong>; and finally</li>
          <li>click <strong>Save verdict &amp; generate final profile</strong>.</li>
        </ul>
        <span className="mt-2 block">That records your decision and produces the final profile a sponsor will
        read.</span></>
    ),
    img: '/reviewer-guide/step8-decision.png',
    alt: 'The Decision card with the four facts, amount slider and buttons',
  },
]

export default function ReviewerGuidePage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900">Your part in the B40 programme</h1>

      <div className="mt-4 rounded-2xl border border-blue-100 bg-blue-50 p-5 text-sm leading-relaxed text-gray-700">
        <p className="text-base font-semibold text-gray-900">Congratulations — and thank you for joining us as a reviewer.</p>
        <p className="mt-2">
          You&rsquo;re helping the <strong>B40 assistance programme</strong>, which supports students from
          lower-income families to continue into further study. Here&rsquo;s where your part fits:
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>Students <strong>apply online</strong> at halatuju.xyz.</li>
          <li>The system checks eligibility and <strong>shortlists</strong> those who qualify — a B40 background,
          a solid academic record, and a clear study pathway.</li>
          <li>Shortlisted students are then <strong>guided to complete</strong> their application: uploading
          documents, confirming family and income details, and answering any follow-up questions.</li>
          <li>When an application is ready, it comes to <strong>you</strong> — to check the key facts, talk to the
          student if needed, and recommend a decision.</li>
        </ul>
        <p className="mt-2">This guide shows you how. It takes about 5 minutes.</p>
      </div>

      <div className="mt-8 space-y-10">
        {STEPS.map((s) => (
          <section key={s.n}>
            <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white">
                {s.n}
              </span>
              {s.title}
            </h2>
            {/* On wider screens the screenshot floats right and the text wraps around it;
                on mobile it stacks below. overflow-hidden contains the float. */}
            <div className="mt-2 overflow-hidden">
              <img
                src={s.img}
                alt={s.alt}
                className="mb-3 block h-auto max-w-full rounded-lg border border-gray-200 shadow-sm sm:float-right sm:ml-6 sm:mb-2 sm:max-w-[340px]"
                loading="lazy"
              />
              <div className="text-sm leading-relaxed text-gray-700">{s.body}</div>
            </div>
          </section>
        ))}
      </div>

      <div className="mt-10 rounded-2xl border border-gray-200 bg-white p-5 text-sm leading-relaxed text-gray-700">
        <strong>Thank you.</strong> Take your time, check the facts, and use a query or the interview whenever
        you&rsquo;re unsure. Your care makes a real difference to these students.
      </div>
    </div>
  )
}
