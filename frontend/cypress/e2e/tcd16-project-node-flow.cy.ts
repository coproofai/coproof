/**
 * TCD-16 — E2E: Project & Node Flow
 * ====================================
 * Scope       : frontend (Angular dev server on http://localhost:4200)
 * Responsible : Emiliano
 * Tools       : Cypress 15.14.2, cy.intercept (no MSW)
 *
 * Covered test cases
 * ──────────────────
 * TC-16-01  Authenticated user creates a new project via the UI
 * TC-16-02  Creating a project with empty name shows validation error
 * TC-16-03  User submits a node for Lean validation and sees success result
 * TC-16-04  Lean validation with compiler errors shows diagnostics
 * TC-16-05  User initiates NL→FL translation and sees loading state
 * TC-16-06  Translation result polling shows final Lean code when task completes
 *
 * Test design notes
 * ─────────────────
 * - All HTTP calls are intercepted via cy.intercept — no real backend required.
 * - beforeEach: cy.clearLocalStorage() ensures each test starts unauthenticated.
 * - Protected routes (/create-project) require seeding access_token BEFORE the
 *   final cy.visit(). Pattern: visit any public page first so localhost:4200 is
 *   loaded, then window().localStorage.setItem(...), then visit the guarded route.
 *   On the second visit the Angular app bootstraps with the token in localStorage,
 *   so AuthService._hasValidToken() returns true and authGuard passes.
 * - TC-16-01: full create-project flow — type name → type goal (Manual tab is
 *   default) → select model in Confirm section → click "Generar vista previa" →
 *   wait for FL→NL timer (2000 ms initial delay) → click confirm → submit.
 *   Intercepts: translate/models, translate/api-key/m1, translate/fl2nl/submit,
 *   translate/fl2nl/f-001/result, POST /projects, workspace secondary calls.
 * - TC-16-02: goal and name both blank → button enabled (disabled only when
 *   !!goal.trim() && !goalTexConfirmed); clicking fires createProject() which
 *   returns immediately with the empty-name error, no HTTP call made.
 * - TC-16-03/04: /validation is a public route; component uses timer(500, 500)
 *   so results arrive quickly; assertions use cy.contains(..., { timeout: 8000 }).
 * - TC-16-05: startWith({ state: 'translating' }) makes the loading label appear
 *   immediately after submit(); the status bar label is "Traduciendo y verificando…".
 * - TC-16-06: result endpoint returns final Lean on every call; timer(2000, 3000)
 *   fires the first poll at ~2000 ms; cy.get('.code-block', { timeout: 8000 }) waits.
 *
 * Run with:
 *   cd frontend
 *   npx cypress run --e2e --spec cypress/e2e/tcd16-project-node-flow.cy.ts
 */

const API = 'http://localhost:5001/api/v1';
const FAKE_TOKEN = 'any-non-empty-access-token';

// ─────────────────────────────────────────────────────────────────────────────
// Shared setup
// ─────────────────────────────────────────────────────────────────────────────

beforeEach(() => {
  cy.clearLocalStorage();
});

// ─────────────────────────────────────────────────────────────────────────────
// TC-16-01 — Authenticated user creates a new project via the UI
// ─────────────────────────────────────────────────────────────────────────────

describe('TC-16-01 — Authenticated user creates a new project', () => {
  it('navigates to /workspace after successful project creation', () => {
    // Intercept all endpoints touched during the create-project flow
    cy.intercept('GET', `${API}/translate/models`, [
      { id: 'm1', provider: 'Test', name: 'Model' },
    ]).as('models');
    cy.intercept('GET', `${API}/translate/api-key/m1`, { has_key: false, masked_key: null });
    cy.intercept('POST', `${API}/translate/fl2nl/submit`, { task_id: 'f-001' }).as('fl2nlSubmit');
    cy.intercept('GET', `${API}/translate/fl2nl/f-001/result`, {
      natural_text: 'For all naturals, addition is commutative.',
      processing_time_seconds: 1,
    }).as('fl2nlResult');
    cy.intercept('POST', `${API}/projects`, {
      id: 'p-001',
      name: 'My Formalization',
      goal: '∀ a b : Nat, a + b = b + a',
      visibility: 'public',
      created_at: '2026-04-30',
    }).as('createProject');
    // WorkspacePageComponent.ngOnInit fires these calls after router.navigate(['/workspace'])
    cy.intercept('GET', `${API}/projects/p-001/graph/simple`, {
      project_name: 'My Formalization', is_owner: true, nodes: [],
    });
    cy.intercept('GET', `${API}/projects/p-001/pulls/open`, { pulls: [] });
    cy.intercept('GET', `${API}/projects/p-001/definitions`, { content: '', file_path: '' });

    // Seed auth: visit any public page to load localhost:4200, set token, then
    // visit the guarded route (Angular re-bootstraps with token in localStorage)
    cy.visit('/validation');
    cy.window().then(win => win.localStorage.setItem('access_token', FAKE_TOKEN));
    cy.visit('/create-project');
    cy.wait('@models');

    // Fill the form — Manual tab is active by default
    cy.get('input[name="projectName"]').type('My Formalization');
    cy.get('textarea[name="goal"]').type('∀ a b : Nat, a + b = b + a');

    // Confirm section appears once goal is non-empty; select model
    cy.get('select[name="confirmModelId"]').should('be.visible').select('Test · Model');

    // Generate FL→NL theorem preview
    cy.contains('button', 'Generar vista previa del enunciado').click();
    cy.wait('@fl2nlSubmit');
    // goalTexVm$ uses timer(2000, 3000) — first poll fires at ~2000 ms
    cy.contains('Sí, este es el teorema', { timeout: 10000 }).click();

    // Submit project creation
    cy.contains('button', 'Crear Proyecto').click();
    cy.wait('@createProject');

    cy.url().should('include', '/workspace');
    cy.contains('My Formalization').should('be.visible');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// TC-16-02 — Creating a project with empty name shows validation error
// ─────────────────────────────────────────────────────────────────────────────

describe('TC-16-02 — Empty project name shows validation error', () => {
  it('shows inline error and does not call POST /projects', () => {
    cy.intercept('GET', `${API}/translate/models`, []);
    cy.intercept('POST', `${API}/projects`).as('createProject');

    cy.visit('/validation');
    cy.window().then(win => win.localStorage.setItem('access_token', FAKE_TOKEN));
    cy.visit('/create-project');

    // Name and goal both blank → button is enabled (disabled only when !!goal && !confirmed)
    cy.contains('button', 'Crear Proyecto').click();

    cy.contains('El nombre del proyecto es obligatorio').should('be.visible');
    cy.get('@createProject.all').should('have.length', 0);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// TC-16-03 — User submits a node for Lean validation and sees success result
// ─────────────────────────────────────────────────────────────────────────────

describe('TC-16-03 — Lean validation succeeds', () => {
  it('displays "La demostración es válida" after successful verification', () => {
    cy.intercept('POST', `${API}/nodes/tools/verify-snippet`, { task_id: 'v-001' }).as('submit');
    cy.intercept('GET', `${API}/nodes/tools/verify-snippet/v-001/result`, {
      valid: true,
      errors: [],
      theorem_count: 1,
      processing_time_seconds: 0.5,
    }).as('result');

    cy.visit('/validation');
    cy.get('textarea.code-editor').type('theorem hello : True := trivial');
    cy.contains('button', 'Verificar').click();
    cy.wait('@submit');

    cy.contains('La demostración es válida', { timeout: 8000 }).should('be.visible');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// TC-16-04 — Lean validation with compiler errors shows diagnostics
// ─────────────────────────────────────────────────────────────────────────────

describe('TC-16-04 — Lean validation with compiler errors shows diagnostics', () => {
  it('displays error diagnostic with line number', () => {
    cy.intercept('POST', `${API}/nodes/tools/verify-snippet`, { task_id: 'v-002' }).as('submit');
    cy.intercept('GET', `${API}/nodes/tools/verify-snippet/v-002/result`, {
      valid: false,
      errors: [{ line: 3, column: 0, message: 'type mismatch' }],
      theorem_count: 1,
      processing_time_seconds: 0.8,
    }).as('result');

    cy.visit('/validation');
    cy.get('textarea.code-editor').type('theorem bad : False := trivial');
    cy.contains('button', 'Verificar').click();
    cy.wait('@submit');

    cy.contains('L3', { timeout: 8000 }).should('be.visible');
    cy.contains('type mismatch').should('be.visible');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// TC-16-05 — User initiates NL→FL translation and sees loading state
// ─────────────────────────────────────────────────────────────────────────────

describe('TC-16-05 — NL→FL translation shows loading state after submit', () => {
  it('shows "Traduciendo y verificando…" immediately after clicking Translate', () => {
    cy.intercept('GET', `${API}/translate/models`, [
      { id: 'm1', provider: 'Test', name: 'Model' },
    ]).as('models');
    cy.intercept('POST', `${API}/translate/submit`, { task_id: 't-001' }).as('submit');
    // Keep result pending so the test asserts the loading state before result arrives
    cy.intercept('GET', `${API}/translate/t-001/result`, { status: 'pending' });

    cy.visit('/translation');

    // Open settings panel and select model (models$ is lazy via defer, loads on open)
    cy.contains('Configuración').click();
    cy.wait('@models');
    cy.get('#model-select').select('Test · Model');

    cy.get('textarea.text-area').type('For all naturals a and b, a + b = b + a');

    cy.contains('button', 'Traducir a Lean').click();
    cy.wait('@submit');

    // vm$ startWith({ state: 'translating' }) fires immediately; status-bar shows label
    cy.contains('Traduciendo y verificando…').should('be.visible');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// TC-16-06 — Translation result polling shows final Lean code
// ─────────────────────────────────────────────────────────────────────────────

describe('TC-16-06 — Translation polling shows final Lean code when task completes', () => {
  it('displays the generated Lean code block after polling resolves', () => {
    cy.intercept('GET', `${API}/translate/models`, [
      { id: 'm1', provider: 'Test', name: 'Model' },
    ]).as('models');
    cy.intercept('POST', `${API}/translate/submit`, { task_id: 't-001' }).as('submit');
    // Return final result on every call — filter(res => res.status !== 'pending') passes;
    // timer(2000, 3000) fires the first poll at ~2000 ms so result appears within 3 s
    cy.intercept('GET', `${API}/translate/t-001/result`, {
      status: 'SUCCESS',
      final_lean: 'theorem comm : ∀ a b : Nat, a + b = b + a := by ring',
      valid: true,
      history: [],
      attempts: 1,
      processing_time_seconds: 2.5,
    }).as('result');

    cy.visit('/translation');

    cy.contains('Configuración').click();
    cy.wait('@models');
    cy.get('#model-select').select('Test · Model');
    cy.get('textarea.text-area').type('For all naturals a and b, a + b = b + a');

    cy.contains('button', 'Traducir a Lean').click();
    cy.wait('@submit');
    cy.wait('@result', { timeout: 6000 });

    cy.get('.code-block', { timeout: 8000 }).should('contain', 'theorem comm');
  });
});
