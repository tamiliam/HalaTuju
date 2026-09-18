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
    '^@/(.*)$': '<rootDir>/src/$1',
  },
}
