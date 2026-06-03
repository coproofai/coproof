import { defineConfig } from 'cypress';

export default defineConfig({
  e2e: {
    // The Angular dev server must be running on this base URL before tests run.
    // Start it with: ng serve --port 4200
    baseUrl: 'http://localhost:4200',
    specPattern: 'cypress/e2e/**/*.cy.ts',
    supportFile: false,
    // Keep a reasonable timeout for CI-like environments.
    defaultCommandTimeout: 8000,
    viewportWidth: 1280,
    viewportHeight: 800,
  },
});
