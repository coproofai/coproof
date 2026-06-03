/**
 * TCD-12 — Angular AuthService
 * ==============================
 * Module      : frontend/src/app/auth.service.ts
 * Responsible : Emiliano
 * Tools       : Vitest (via @angular/build:unit-test), Angular TestBed,
 *               provideHttpClient + provideHttpClientTesting
 *
 * Covered test cases
 * ──────────────────
 * TC-12-01  isLoggedIn() returns false when localStorage is empty
 * TC-12-02  isLoggedIn() returns true when token exists in localStorage
 * TC-12-03  handleOAuthCallback stores tokens and user in localStorage
 * TC-12-04  handleOAuthCallback emits true on isLoggedIn$
 * TC-12-05  refreshAccessToken returns false when no refresh token exists
 * TC-12-06  refreshAccessToken stores new access token and returns true
 * TC-12-07  refreshAccessToken returns false on HTTP error
 * TC-12-08  getUser returns null when no user in localStorage
 * TC-12-09  getUser returns parsed AuthUser when stored in localStorage
 * TC-12-10  initiateGitHubLogin fetches OAuth URL and assigns window.location.href
 *
 * Test design notes
 * ─────────────────
 * - Test runner is Vitest (not Jest). `pending()` is Jasmine-only and
 *   does not exist in Vitest globals — the skeleton placeholder must be removed.
 * - Use `provideHttpClient()` + `provideHttpClientTesting()` (the post-Angular-18
 *   pattern). `HttpClientTestingModule` / `RouterTestingModule` are deprecated.
 * - `AuthService._isLoggedIn$` is a BehaviorSubject initialised from
 *   `localStorage` at construction time. For TC-12-02, `localStorage` must be
 *   pre-seeded BEFORE `TestBed.inject(AuthService)` is called. A helper
 *   `setupTestBed()` defers injection so each test can control this.
 * - TC-12-10: `window.location` is non-configurable in browser environments.
 *   `vi.stubGlobal('location', { href: '' })` replaces `globalThis.location`
 *   with a plain writable object before the service call, then
 *   `vi.unstubAllGlobals()` restores it in afterEach.
 * - HTTP error responses (TC-12-07) use
 *   `req.flush(body, { status: 401, statusText: 'Unauthorized' })` which
 *   produces an `HttpErrorResponse`; the service catches it and returns false.
 *
 * Run with:
 *   cd frontend
 *   npx ng test --include="src/app/tcd12-auth-service.spec.ts" --watch=false
 */

import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { vi } from 'vitest';
import { AuthService } from './auth.service';

const API = 'http://localhost:5001/api/v1';

const MOCK_USER = { id: '1', full_name: 'Test User', email: 'test@example.com' };
const MOCK_TOKENS = {
  access_token: 'mock-access-jwt',
  refresh_token: 'mock-refresh-jwt',
  user: MOCK_USER,
};

/** Configures and returns a fresh TestBed environment. Injection is deferred so
 *  individual tests can seed localStorage before the service is constructed. */
function setupTestBed(): { service: AuthService; httpMock: HttpTestingController } {
  TestBed.configureTestingModule({
    providers: [
      AuthService,
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([]),
    ],
  });
  return {
    service: TestBed.inject(AuthService),
    httpMock: TestBed.inject(HttpTestingController),
  };
}

describe('TCD-12 — AuthService', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-12-01 — isLoggedIn() returns false when localStorage is empty
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-12-01 — isLoggedIn() returns false when localStorage is empty', () => {
    it('returns false', () => {
      const { service, httpMock } = setupTestBed();
      expect(service.isLoggedIn()).toBe(false);
      httpMock.verify();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-12-02 — isLoggedIn() returns true when token exists in localStorage
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-12-02 — isLoggedIn() returns true when token exists', () => {
    it('returns true', () => {
      // localStorage must be seeded BEFORE service construction so the
      // BehaviorSubject initialises to true.
      localStorage.setItem('access_token', 'test.jwt.token');
      const { service, httpMock } = setupTestBed();
      expect(service.isLoggedIn()).toBe(true);
      httpMock.verify();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-12-03 — handleOAuthCallback stores tokens and user in localStorage
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-12-03 — handleOAuthCallback stores tokens and user', () => {
    it('stores access_token in localStorage', async () => {
      const { service, httpMock } = setupTestBed();
      const promise = service.handleOAuthCallback('code_abc');
      const req = httpMock.expectOne(`${API}/auth/github/callback`);
      req.flush(MOCK_TOKENS);
      await promise;
      expect(localStorage.getItem('access_token')).toBe(MOCK_TOKENS.access_token);
      httpMock.verify();
    });

    it('stores auth_user as valid JSON in localStorage', async () => {
      const { service, httpMock } = setupTestBed();
      const promise = service.handleOAuthCallback('code_abc');
      const req = httpMock.expectOne(`${API}/auth/github/callback`);
      req.flush(MOCK_TOKENS);
      await promise;
      const stored = JSON.parse(localStorage.getItem('auth_user')!);
      expect(stored.full_name).toBe(MOCK_USER.full_name);
      httpMock.verify();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-12-04 — handleOAuthCallback emits true on isLoggedIn$
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-12-04 — handleOAuthCallback emits true on isLoggedIn$', () => {
    it('isLoggedIn$ emits true after callback', async () => {
      const { service, httpMock } = setupTestBed();
      const promise = service.handleOAuthCallback('code_abc');
      const req = httpMock.expectOne(`${API}/auth/github/callback`);
      req.flush(MOCK_TOKENS);
      await promise;
      const emitted = await firstValueFrom(service.isLoggedIn$);
      expect(emitted).toBe(true);
      httpMock.verify();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-12-05 — refreshAccessToken returns false when no refresh token exists
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-12-05 — refreshAccessToken returns false when no refresh token', () => {
    it('returns false without making an HTTP request', async () => {
      const { service, httpMock } = setupTestBed();
      const result = await service.refreshAccessToken();
      expect(result).toBe(false);
      httpMock.expectNone(`${API}/auth/refresh`);
      httpMock.verify();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-12-06 — refreshAccessToken stores new token and returns true
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-12-06 — refreshAccessToken stores new access token and returns true', () => {
    it('returns true', async () => {
      localStorage.setItem('refresh_token', 'old-refresh-jwt');
      const { service, httpMock } = setupTestBed();
      const promise = service.refreshAccessToken();
      const req = httpMock.expectOne(`${API}/auth/refresh`);
      req.flush({ access_token: 'new.jwt' });
      const result = await promise;
      expect(result).toBe(true);
      httpMock.verify();
    });

    it('stores the new access token in localStorage', async () => {
      localStorage.setItem('refresh_token', 'old-refresh-jwt');
      const { service, httpMock } = setupTestBed();
      const promise = service.refreshAccessToken();
      const req = httpMock.expectOne(`${API}/auth/refresh`);
      req.flush({ access_token: 'new.jwt' });
      await promise;
      expect(localStorage.getItem('access_token')).toBe('new.jwt');
      httpMock.verify();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-12-07 — refreshAccessToken returns false on HTTP error
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-12-07 — refreshAccessToken returns false on HTTP 401', () => {
    it('returns false', async () => {
      localStorage.setItem('refresh_token', 'old-refresh-jwt');
      const { service, httpMock } = setupTestBed();
      const promise = service.refreshAccessToken();
      const req = httpMock.expectOne(`${API}/auth/refresh`);
      req.flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });
      const result = await promise;
      expect(result).toBe(false);
      httpMock.verify();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-12-08 — getUser returns null when no user in localStorage
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-12-08 — getUser returns null when localStorage is empty', () => {
    it('returns null', () => {
      const { service, httpMock } = setupTestBed();
      expect(service.getUser()).toBeNull();
      httpMock.verify();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-12-09 — getUser returns parsed AuthUser when stored in localStorage
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-12-09 — getUser returns parsed AuthUser from localStorage', () => {
    it('returns the stored user object', () => {
      const user = { id: '1', full_name: 'Alice', email: 'a@b.com' };
      localStorage.setItem('auth_user', JSON.stringify(user));
      const { service, httpMock } = setupTestBed();
      expect(service.getUser()).toEqual(user);
      httpMock.verify();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-12-10 — initiateGitHubLogin fetches OAuth URL and assigns location.href
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-12-10 — initiateGitHubLogin fetches OAuth URL and navigates', () => {
    it('makes GET request to /auth/github/url', async () => {
      const mockLocation = { href: '' };
      vi.stubGlobal('location', mockLocation);
      const { service, httpMock } = setupTestBed();
      const promise = service.initiateGitHubLogin();
      const req = httpMock.expectOne(`${API}/auth/github/url`);
      expect(req.request.method).toBe('GET');
      req.flush({ url: 'https://github.com/login/oauth/authorize?client_id=x' });
      await promise;
      httpMock.verify();
    });

    it('assigns window.location.href to the URL from the API', async () => {
      // vi.stubGlobal replaces globalThis.location with a plain writable object,
      // bypassing the non-configurable browser property restriction.
      const mockLocation = { href: '' };
      vi.stubGlobal('location', mockLocation);
      const { service, httpMock } = setupTestBed();
      const promise = service.initiateGitHubLogin();
      const req = httpMock.expectOne(`${API}/auth/github/url`);
      req.flush({ url: 'https://github.com/login/oauth/authorize?client_id=x' });
      await promise;
      expect(mockLocation.href).toBe('https://github.com/login/oauth/authorize?client_id=x');
      httpMock.verify();
    });
  });
});

