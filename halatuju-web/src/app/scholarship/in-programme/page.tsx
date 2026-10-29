import { redirect } from 'next/navigation'

/** `/scholarship/in-programme` became "My Bursary" (`/scholarship/bursary`, student maintenance S3).
 *  Kept as a redirect so an old bookmark or email link still lands on the hub. */
export default function InProgrammeRedirect() {
  redirect('/scholarship/bursary')
}
