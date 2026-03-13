import { redirect } from 'next/navigation'

export default function StpmSearchRedirect() {
  redirect('/search?qualification=STPM')
}
