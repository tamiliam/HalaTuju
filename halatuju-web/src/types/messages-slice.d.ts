/**
 * TD-360: a message file cut to one slice at build time by `scripts/messages-slice-loader.js`
 * (wired in `next.config.js`). Each is a parsed catalogue: nested objects of strings.
 *
 * ⚠ Only these five slice names exist. Another is a new line here AND in the loader's `SLICES`.
 * `documents` = the student Documents tab's words (`lib/messagesDocuments.ts`, third results route S3).
 * `scholarship` = the student scholarship screens' words (`lib/messagesScholarship.ts`, TD-416).
 * `sponsor` = the sponsor routes' words (`lib/messagesSponsor.ts`, TD-416).
 */
declare module '*.json?slice=core' {
  const catalogue: Record<string, unknown>
  export default catalogue
}

declare module '*.json?slice=admin' {
  const catalogue: Record<string, unknown>
  export default catalogue
}

declare module '*.json?slice=documents' {
  const catalogue: Record<string, unknown>
  export default catalogue
}

declare module '*.json?slice=scholarship' {
  const catalogue: Record<string, unknown>
  export default catalogue
}

declare module '*.json?slice=sponsor' {
  const catalogue: Record<string, unknown>
  export default catalogue
}

declare module '*.json?slice=bursary' {
  const catalogue: Record<string, unknown>
  export default catalogue
}
