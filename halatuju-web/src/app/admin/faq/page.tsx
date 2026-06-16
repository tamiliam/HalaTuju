// Reviewer FAQ — administrative + reviewing questions. Static English for now (BM/Tamil to follow).
// Reached only after sign-in (gated by the admin layout).

type QA = { q: React.ReactNode; a: React.ReactNode }

const ADMIN: QA[] = [
  {
    q: <>Is this paid? Do reviewers get any compensation?</>,
    a: <>No — reviewing is <strong>voluntary</strong>, and there&rsquo;s no payment. Thank you for giving your
      time to these students.</>,
  },
  {
    q: <>How do I sign in next time?</>,
    a: <>Go to <strong>halatuju.xyz/admin/login</strong> and enter your email and password, or sign in with
      Google.</>,
  },
  {
    q: <>How do I change or reset my password?</>,
    a: <>On the sign-in page, click <strong>Forgot password</strong>, enter your email, and follow the link we
      send to set a new one.</>,
  },
  {
    q: <>Does my email have to be Gmail?</>,
    a: <>No — any email address works.</>,
  },
  {
    q: <>Is the information I see confidential?</>,
    a: <>Yes. Treat everything about an applicant as <strong>private</strong> — only discuss it with the
      HalaTuju team. Please don&rsquo;t download, share or keep applicant details.</>,
  },
  {
    q: <>I&rsquo;m stuck, or something looks wrong with my account — whom do I contact?</>,
    a: <>Email the HalaTuju team at <strong>tamiliam@gmail.com</strong> and we&rsquo;ll help.</>,
  },
]

const REVIEWING: QA[] = [
  {
    q: <>Why do I only see some applicants?</>,
    a: <>You see <strong>only the applicants assigned to you</strong>, so you can focus on your own. That&rsquo;s
      normal.</>,
  },
  {
    q: <>What is the &ldquo;Student profile (draft)&rdquo;?</>,
    a: <>A short summary written automatically from the student&rsquo;s own application. It&rsquo;s a helpful
      starting point — always check it against the uploaded documents before relying on it.</>,
  },
  {
    q: <>Should I just trust the AI?</>,
    a: <>No — the AI gives a <em>suggestion</em> for each of the four facts and a draft profile.
      <strong> You decide.</strong> Your Pass/Fail rating, based on the documents and your interview, also helps
      improve the AI over time.</>,
  },
  {
    q: <>What do the four checks mean?</>,
    a: <>Identity (is this really them), Academic record (do the grades match the slip), Pathway (is their study
      plan or offer in order), and Income (are they genuinely B40 / in need).</>,
  },
  {
    q: <>How do I ask the student a question?</>,
    a: <>Use <strong>Raise a query</strong> or <strong>Request a document</strong>. They get an email; their
      reply shows in the <strong>Outstanding</strong> box.</>,
  },
  {
    q: <>What does &ldquo;Save verdict &amp; generate final profile&rdquo; do?</>,
    a: <>It records your decision and creates the final, polished profile a sponsor will see.</>,
  },
  {
    q: <>What&rsquo;s the recommended amount for?</>,
    a: <>It&rsquo;s your suggestion of how much assistance would help, set on the slider. It guides the
      sponsor.</>,
  },
  {
    q: <>The student&rsquo;s offer letter doesn&rsquo;t match their stated pathway — what do I do?</>,
    a: <>Note it and ask them in the interview (or raise a query). They may have updated their plan; the
      conversation settles it. You can also ask them to upload the latest offer letter, which replaces the
      old one.</>,
  },
  {
    q: <>The student is already in college and has completed a semester or two — should I ask for more?</>,
    a: <>If they have completed one or more semesters and have their results (CGPA), you may ask them to upload
      their latest result. If it is satisfactory (above 3.0), you may consider recommending them for support.</>,
  },
]

function Section({ title, items }: { title: string; items: QA[] }) {
  return (
    <section className="mt-8">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      <dl className="mt-3 space-y-5">
        {items.map((item, i) => (
          <div key={i} className="rounded-xl border border-gray-200 bg-white p-4">
            <dt className="font-semibold text-gray-900">{item.q}</dt>
            <dd className="mt-1 text-sm leading-relaxed text-gray-700">{item.a}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

export default function ReviewerFaqPage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900">Frequently asked questions</h1>
      <p className="mt-1 text-sm text-gray-500">Quick answers for reviewers. See the Guide for a step-by-step walkthrough.</p>
      <Section title="Administrative" items={ADMIN} />
      <Section title="Reviewing" items={REVIEWING} />
    </div>
  )
}
