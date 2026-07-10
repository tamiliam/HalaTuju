module.exports = {
  transform: {
    // tsconfig.jest.json extends the app tsconfig but sets jsx: react-jsx so ts-jest can
    // compile component (.tsx) tests to runnable JS (the app config uses jsx: preserve for Next).
    '^.+\\.tsx?$': ['ts-jest', { tsconfig: 'tsconfig.jest.json' }],
  },
  testEnvironment: 'node',
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
}
