/**
 * TCD-13 — Angular TaskService
 * ==============================
 * Module      : frontend/src/app/task.service.ts
 * Responsible : Emiliano
 * Tools       : Vitest (via @angular/build:unit-test), Angular TestBed,
 *               provideHttpClient + provideHttpClientTesting
 *
 * Covered test cases
 * ──────────────────
 * TC-13-01  getTokenType returns "access" for valid access JWT
 * TC-13-02  getTokenType returns "refresh" for valid refresh JWT
 * TC-13-03  getTokenType returns null for malformed token string
 * TC-13-04  getTokenType returns null for empty string
 * TC-13-05  setAccessToken normalizes whitespace and stores in localStorage
 * TC-13-06  clearAccessToken removes access_token, refresh_token, auth_user
 * TC-13-07  shouldClearAccessTokenOnError returns true for HTTP 401 + JWT hint
 * TC-13-08  shouldClearAccessTokenOnError returns false for HTTP 500
 *
 * Test design notes
 * ─────────────────
 * - Runner is Vitest — use provideHttpClient() + provideHttpClientTesting().
 * - TC-13-01/02: getTokenType base64url-decodes the JWT payload and reads
 *   payload.type. A makeJwt() helper constructs a syntactically valid 3-part
 *   JWT with a real base64url-encoded payload (uses btoa + standard replacements).
 * - TC-13-03: A token with more than 3 parts still has parts.length >= 2;
 *   "not.a.valid.jwt.at.all" has 6 parts — the payload part "valid" is not valid
 *   base64url so JSON.parse throws and getTokenType returns null.
 * - TC-13-05: setAccessToken calls normalizeAccessToken which trims whitespace
 *   and also strips "Bearer " prefixes. TC only tests the trim path.
 * - TC-13-07/08: shouldClearAccessTokenOnError requires BOTH status === 401 AND
 *   a JWT hint string inside error.error.message (see jwtHints array in the
 *   service). Passing only status is not enough — the error object must include
 *   a message with a recognised hint (e.g. "token has expired").
 *   TC-13-08 uses status 500 with a JWT hint message — the service still returns
 *   false because status !== 401.
 *
 * Run with:
 *   cd frontend
 *   npx ng test --include="src/app/tcd13-task-service.spec.ts" --watch=false
 */

import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { TaskService } from './task.service';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Build a syntactically valid JWT with the given payload (no real signing). */
function makeJwt(payload: object): string {
  const b64url = (obj: object): string =>
    btoa(JSON.stringify(obj))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '');
  const header = b64url({ alg: 'HS256', typ: 'JWT' });
  const body   = b64url(payload);
  return `${header}.${body}.fakesig`;
}

/** JWT error object structure expected by shouldClearAccessTokenOnError. */
function jwtError(status: number, message: string): object {
  return { status, error: { message } };
}

function setupTestBed(): TaskService {
  TestBed.configureTestingModule({
    providers: [
      TaskService,
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([]),
    ],
  });
  return TestBed.inject(TaskService);
}

// ─────────────────────────────────────────────────────────────────────────────

describe('TCD-13 — TaskService', () => {
  beforeEach(() => { localStorage.clear(); });
  afterEach(() => { TestBed.resetTestingModule(); localStorage.clear(); });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-13-01 — getTokenType returns "access" for valid access JWT
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-13-01 — getTokenType returns "access" for valid access JWT', () => {
    it('returns "access"', () => {
      const service = setupTestBed();
      const token = makeJwt({ sub: '1', type: 'access' });
      expect(service.getTokenType(token)).toBe('access');
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-13-02 — getTokenType returns "refresh" for valid refresh JWT
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-13-02 — getTokenType returns "refresh" for valid refresh JWT', () => {
    it('returns "refresh"', () => {
      const service = setupTestBed();
      const token = makeJwt({ sub: '1', type: 'refresh' });
      expect(service.getTokenType(token)).toBe('refresh');
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-13-03 — getTokenType returns null for malformed token string
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-13-03 — getTokenType returns null for malformed token string', () => {
    it('returns null for "not.a.valid.jwt.at.all"', () => {
      const service = setupTestBed();
      expect(service.getTokenType('not.a.valid.jwt.at.all')).toBeNull();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-13-04 — getTokenType returns null for empty string
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-13-04 — getTokenType returns null for empty string', () => {
    it('returns null', () => {
      const service = setupTestBed();
      expect(service.getTokenType('')).toBeNull();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-13-05 — setAccessToken normalizes whitespace and stores in localStorage
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-13-05 — setAccessToken normalizes whitespace', () => {
    it('trims leading and trailing whitespace before storing', () => {
      const service = setupTestBed();
      service.setAccessToken('  mytoken  ');
      expect(localStorage.getItem('access_token')).toBe('mytoken');
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-13-06 — clearAccessToken removes access_token, refresh_token, auth_user
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-13-06 — clearAccessToken removes all auth keys', () => {
    it('removes access_token', () => {
      localStorage.setItem('access_token', 'a');
      localStorage.setItem('refresh_token', 'b');
      localStorage.setItem('auth_user', '{}');
      const service = setupTestBed();
      service.clearAccessToken();
      expect(localStorage.getItem('access_token')).toBeNull();
    });

    it('removes refresh_token', () => {
      localStorage.setItem('access_token', 'a');
      localStorage.setItem('refresh_token', 'b');
      localStorage.setItem('auth_user', '{}');
      const service = setupTestBed();
      service.clearAccessToken();
      expect(localStorage.getItem('refresh_token')).toBeNull();
    });

    it('removes auth_user', () => {
      localStorage.setItem('access_token', 'a');
      localStorage.setItem('refresh_token', 'b');
      localStorage.setItem('auth_user', '{}');
      const service = setupTestBed();
      service.clearAccessToken();
      expect(localStorage.getItem('auth_user')).toBeNull();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-13-07 — shouldClearAccessTokenOnError returns true for HTTP 401 + hint
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-13-07 — shouldClearAccessTokenOnError returns true for HTTP 401', () => {
    it('returns true when status is 401 and message contains a JWT hint', () => {
      const service = setupTestBed();
      // The service requires BOTH status === 401 AND a JWT hint in the message.
      const err = jwtError(401, 'token has expired');
      expect(service.shouldClearAccessTokenOnError(err)).toBe(true);
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-13-08 — shouldClearAccessTokenOnError returns false for HTTP 500
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-13-08 — shouldClearAccessTokenOnError returns false for HTTP 500', () => {
    it('returns false even when message contains a JWT hint', () => {
      const service = setupTestBed();
      // Status 500 → false regardless of message content.
      const err = jwtError(500, 'token has expired');
      expect(service.shouldClearAccessTokenOnError(err)).toBe(false);
    });
  });
});

