'use client'

import Link from 'next/link'
import BrandLogo from '@/components/BrandLogo'
import ProgressStepper from '@/components/ProgressStepper'

/**
 * The onboarding header: the logo and where she is in the three steps (Mobile M2, Stitch M2c2).
 * One component for the five onboarding pages, which each carried their own copy of it.
 *
 * ⚠ THE LOGO NEVER SHRINKS (`shrink-0`). It used to be a flex item that could, and in Malay the
 * step indicator beside it squeezed it to 74 px at 390 and 44 px at 360. The indicator is stacked
 * now (`ProgressStepper`), so logo + indicator measure 120 + 12 + 152 = 284 px in Malay, inside the
 * 328 px a 360 px phone leaves. `navLayout.test.ts` pins both.
 * On a phone the logo link is padded to 44 px tall (a tap target), with a matching negative margin
 * so the header keeps its height (Mobile M8).
 */
export default function FlowHeader({ step }: { step: number }) {
  return (
    <div className="sticky top-0 z-10 border-b border-ground-100 bg-ground-0 pt-[env(safe-area-inset-top)]">
      <div className="container mx-auto flex items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center max-md:-my-0.5 max-md:py-0.5">
          <BrandLogo width={120} height={40} />
        </Link>
        <ProgressStepper currentStep={step} />
      </div>
    </div>
  )
}
