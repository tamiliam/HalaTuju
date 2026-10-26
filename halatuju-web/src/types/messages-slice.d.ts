/**
 * TD-360: a message file cut to one slice at build time by `scripts/messages-slice-loader.js`
 * (wired in `next.config.js`). Each is a parsed catalogue: nested objects of strings.
 *
 * ⚠ Only these three slice names exist. Another is a new line here AND in the loader's `SLICES`.
 * `documents` = the student Documents tab's words (`lib/messagesDocuments.ts`, third results route S3).
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
