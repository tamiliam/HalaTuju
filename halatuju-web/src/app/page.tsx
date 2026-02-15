import Link from 'next/link'

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      {/* Navigation */}
      <nav className="container mx-auto px-6 py-4 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 bg-primary-500 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-xl">H</span>
          </div>
          <span className="text-xl font-semibold text-gray-900">HalaTuju</span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/about" className="text-gray-600 hover:text-gray-900">
            About
          </Link>
          <Link href="/login" className="btn-primary">
            Get Started
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="container mx-auto px-6 py-20 text-center">
        <h1 className="text-5xl md:text-6xl font-bold text-gray-900 mb-6">
          Find Your Perfect
          <span className="text-primary-500"> Course</span>
        </h1>
        <p className="text-xl text-gray-600 mb-10 max-w-2xl mx-auto">
          Discover the right path for your future based on your SPM results.
          Get personalised recommendations from over 300 courses across
          polytechnics, universities, and TVET institutions.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="/onboarding/stream" className="btn-primary text-lg px-8 py-4">
            Start Your Journey
          </Link>
          <Link href="/about" className="btn-secondary text-lg px-8 py-4">
            Learn More
          </Link>
        </div>
      </section>

      {/* Features Section */}
      <section className="container mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
          How It Works
        </h2>
        <div className="grid md:grid-cols-3 gap-8">
          <FeatureCard
            step="1"
            title="Enter Your Grades"
            description="Tell us your SPM results and we'll find courses you're eligible for."
          />
          <FeatureCard
            step="2"
            title="Share Your Interests"
            description="Answer a few questions about what you enjoy to get personalised matches."
          />
          <FeatureCard
            step="3"
            title="Get Recommendations"
            description="See courses ranked by how well they fit your profile and preferences."
          />
        </div>
      </section>

      {/* Stats Section */}
      <section className="bg-primary-500 py-16">
        <div className="container mx-auto px-6">
          <div className="grid md:grid-cols-4 gap-8 text-center text-white">
            <StatCard number="310" label="Courses" />
            <StatCard number="212" label="Institutions" />
            <StatCard number="3" label="Languages" />
            <StatCard number="100%" label="Free" />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="container mx-auto px-6 py-20 text-center">
        <h2 className="text-3xl font-bold text-gray-900 mb-6">
          Ready to Find Your Path?
        </h2>
        <p className="text-lg text-gray-600 mb-8 max-w-xl mx-auto">
          Join thousands of SPM leavers who have found their ideal course using HalaTuju.
        </p>
        <Link href="/onboarding/stream" className="btn-primary text-lg px-8 py-4">
          Get Started - It's Free
        </Link>
      </section>

      {/* Footer */}
      <footer className="bg-gray-50 py-12">
        <div className="container mx-auto px-6">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold">H</span>
              </div>
              <span className="font-semibold text-gray-900">HalaTuju</span>
            </div>
            <div className="flex gap-6 text-sm text-gray-600">
              <Link href="/about">About</Link>
              <Link href="/privacy">Privacy</Link>
              <Link href="/terms">Terms</Link>
            </div>
            <p className="text-sm text-gray-500">
              2026 HalaTuju. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </main>
  )
}

function FeatureCard({
  step,
  title,
  description,
}: {
  step: string
  title: string
  description: string
}) {
  return (
    <div className="card text-center">
      <div className="w-12 h-12 bg-primary-100 text-primary-500 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
        {step}
      </div>
      <h3 className="text-xl font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  )
}

function StatCard({ number, label }: { number: string; label: string }) {
  return (
    <div>
      <div className="text-4xl font-bold mb-2">{number}</div>
      <div className="text-primary-100">{label}</div>
    </div>
  )
}
