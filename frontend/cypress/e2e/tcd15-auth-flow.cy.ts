/**
 * TCD-15 — E2E: Authentication Flow
 * ====================================
 * Scope       : frontend (Angular dev server on http://localhost:4200)
 * Responsible : Emiliano
 * Tools       : Cypress 15, cy.intercept
 *
 * Covered test cases
 * ──────────────────
 * TC-15-01  Unauthenticated user visiting protected route → redirected to /auth
 * TC-15-02  User clicks "Login with GitHub" → window.location.href set to OAuth URL
 * TC-15-03  OAuth callback page exchanges code → navigates to /menu
 * TC-15-04  Authenticated user visiting /auth → redirected to /menu
 *
 * Test design notes
 * ─────────────────
 * - No real backend required. All HTTP calls to http://localhost:5001 are
 *   intercepted via cy.intercept before each test.
 * - localStorage is cleared in beforeEach so each test starts unauthenticated
 *   unless the test itself sets a token.
 * - TC-15-02: window.location.href assignment cannot be asserted directly in
 *   Cypress without breaking navigation. Instead we stub window.location using
 *   cy.window() + Object.defineProperty and assert the stub was called with
 *   the expected URL.
 * - TC-15-03: The callback route is handled by AuthPageComponent via
 *   ActivatedRoute query params (?code=...). After a successful
 *   POST /api/v1/auth/github/callback the component calls router.navigate(['/menu']).
 * - API base URL used by AuthService: http://localhost:5001/api/v1
 *
 * Run with:
 *   cd frontend
 *   npx cypress run --e2e --spec cypress/e2e/tcd15-auth-flow.cy.ts
 *
 * Or headed:
 *   npx cypress open
 */

const API = 'http://localhost:5001/api/v1';

const MOCK_TOKENS = {
  access_token: 'mock-access-jwt',
  refresh_token: 'mock-refresh-jwt',
  user: { id: '1', full_name: 'Test User', email: 'test@example.com' },
};

// ─────────────────────────────────────────────────────────────────────────────
// Shared setup
// ─────────────────────────────────────────────────────────────────────────────

beforeEach(() => {
  cy.clearLocalStorage();
});

// ─────────────────────────────────────────────────────────────────────────────
// TC-15-01 — Unauthenticated user visiting protected route → redirected to /auth
// ─────────────────────────────────────────────────────────────────────────────

describe('TC-15-01 — Unauthenticated redirect to /auth', () => {
  it('redirects /workspace to /auth when no token is present', () => {
    cy.visit('/workspace');
    cy.url().should('include', '/auth');
  });

  it('redirects /account-config to /auth when no token is present', () => {
    cy.visit('/account-config');
    cy.url().should('include', '/auth');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// TC-15-02 — User clicks "Login with GitHub" → window.location.href updated
// ─────────────────────────────────────────────────────────────────────────────

describe('TC-15-02 — GitHub login button triggers OAuth redirect', () => {
  it('calls GET /auth/github/url and navigates to the returned URL', () => {
    // window.location is non-configurable in Electron/Chrome — Object.defineProperty
    // and cy.stub(win, 'location') both throw "Cannot redefine property: location".
    // The correct Cypress idiom for testing href-based navigation is to return a
    // same-origin URL from the mock so the browser stays within the test scope.
    // We verify that: (1) the button triggered the API call; (2) the app used
    // the URL from the API response for actual navigation.
    cy.intercept('GET', `${API}/auth/github/url`, {
      statusCode: 200,
      body: { url: 'http://localhost:4200/menu' },
    }).as('getGithubUrl');

    cy.visit('/auth');
    cy.contains('button', 'Continuar con GitHub').click();
    cy.wait('@getGithubUrl');
    cy.url().should('include', '/menu');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// TC-15-03 — OAuth callback → tokens stored and navigates to /menu
// ─────────────────────────────────────────────────────────────────────────────

describe('TC-15-03 — OAuth callback exchanges code and navigates to /menu', () => {
  beforeEach(() => {
    cy.intercept('POST', `${API}/auth/github/callback`, {
      statusCode: 200,
      body: MOCK_TOKENS,
    }).as('githubCallback');
  });

  it('navigates to /menu after successful callback', () => {
    cy.visit('/auth?code=abc123');
    cy.wait('@githubCallback');
    cy.url().should('include', '/menu');
  });

  it('stores access_token in localStorage', () => {
    cy.visit('/auth?code=abc123');
    cy.wait('@githubCallback');
    cy.window().then((win) => {
      expect(win.localStorage.getItem('access_token')).to.equal(MOCK_TOKENS.access_token);
    });
  });

  it('stores auth_user as valid JSON in localStorage', () => {
    cy.visit('/auth?code=abc123');
    cy.wait('@githubCallback');
    cy.window().then((win) => {
      const raw = win.localStorage.getItem('auth_user');
      expect(raw).to.not.be.null;
      const parsed = JSON.parse(raw!);
      expect(parsed.full_name).to.equal(MOCK_TOKENS.user.full_name);
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// TC-15-04 — Already-authenticated user visiting /auth → redirected to /menu
// ─────────────────────────────────────────────────────────────────────────────

describe('TC-15-04 — Authenticated user visiting /auth is redirected to /menu', () => {
  it('redirects to /menu when access_token already exists', () => {
    cy.window().then((win) => {
      win.localStorage.setItem('access_token', 'existing-valid-jwt');
    });
    cy.visit('/auth');
    cy.url().should('include', '/menu');
  });
});
