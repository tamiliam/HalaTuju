/**
 * THE ONE INVITE-FORM LAYOUT every Invite-as tab on Organisation → Invitations wears (I1, 2026-11-08,
 * roadmap `docs/plans/2026-11-08-invitations-consistency-roadmap.md`).
 *
 * Owner: *"Source button is on the right, unlike others."* The five tabs had grown two layouts —
 * placeholder-only boxes with the button under them (Admin / Reviewer / Sponsor), and labelled boxes
 * with the button pushed right beside a note (Source / Mentor). One now: a label ABOVE every box, the
 * tab's explanatory note UNDER the fields, and Send Invite on the LEFT under the note.
 *
 * ⚠ Tiny and dependency-free on purpose: the page imports it statically and the Source / Mentor forms
 * (one lazy chunk, `lazySource`) import it too, so it must not drag anything into either.
 */

export const FIELD_LABEL = 'mb-1 block text-sm font-medium text-ground-700'

/** One labelled box: the label sits above it and names it for a screen reader. */
export function InviteField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className={FIELD_LABEL}>{label}</span>
      {children}
    </label>
  )
}

/** The foot of every invite form: the tab's note (if it has one), then Send Invite at the left. */
export function InviteFoot({ note, busy, label }: {
  note?: React.ReactNode
  busy: boolean
  /** The button's words (`admin.sendInvite`). */
  label: string
}) {
  return (
    <div className="space-y-3" data-testid="invite-foot">
      {note && <p className="text-sm text-ground-500" data-testid="invite-note">{note}</p>}
      <button type="submit" disabled={busy}
        className="rounded-lg bg-brand-fill px-6 py-2.5 font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
        {label}
      </button>
    </div>
  )
}
