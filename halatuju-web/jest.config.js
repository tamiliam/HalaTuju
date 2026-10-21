module.exports = {
  transform: {
    // tsconfig.jest.json extends the app tsconfig but sets jsx: react-jsx so ts-jest can
    // compile component (.tsx) tests to runnable JS (the app config uses jsx: preserve for Next).
    '^.+\\.tsx?$': ['ts-jest', { tsconfig: 'tsconfig.jest.json' }],
  },
  testEnvironment: 'node',
  // Raises Testing Library's 1-second async limit for the whole suite — see jest.setup.ts for why
  // (the deploy gate runs this suite on a 2-vCPU worker that is also building the image).
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  moduleNameMapper: {
    // TD-360: a `?slice=` import (cut at build time by scripts/messages-slice-loader.js, which jest
    // does not run) resolves to the WHOLE file here — a superset, so no test changes meaning.
    // `messagesSlice.test.ts` proves the cut itself on the real files. Must precede the `@/` rule.
    '^@/messages/(en|ms|ta)\\.json\\?slice=\\w+$': '<rootDir>/src/messages/$1.json',
    '^@/(.*)$': '<rootDir>/src/$1',
  },
}
