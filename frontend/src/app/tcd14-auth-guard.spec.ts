/**
 * TCD-14 — Angular authGuard
 * ============================
 * Module      : frontend/src/app/auth.guard.ts
 * Responsible : Emiliano
 * Tools       : Vitest (via @angular/build:unit-test), Angular TestBed,
 *               provideRouter, TestBed.runInInjectionContext
 *
 * Covered test cases
 * ──────────────────
 * TC-14-01  Guard returns true when user is logged in
 * TC-14-02  Guard returns UrlTree to /auth when user is not logged in
 *
 * Test design notes
 * ─────────────────
 * - `authGuard` is a `CanActivateFn` (plain function, not a class). It must be
 *   invoked inside `TestBed.runInInjectionContext(() => authGuard(...))` so
 *   Angular's `inject()` calls resolve correctly.
 * - `AuthService` is provided as a plain value mock
 *   `{ isLoggedIn: () => bool }` — no real HTTP client or router needed inside
 *   the service for these tests.
 * - `provideRouter([])` is required so `Router.createUrlTree` works when the
 *   guard redirects to /auth.
 * - `RouterTestingModule` is deprecated in Angular 18+; use `provideRouter` instead.
 * - The guard passes `null` snapshots because `authGuard` ignores both
 *   `ActivatedRouteSnapshot` and `RouterStateSnapshot` — it only calls
 *   `auth.isLoggedIn()` and `router.createUrlTree(['/auth'])`.
 * - TC-14-02: the return value is a `UrlTree`; assert via `toString()` === `'/auth'`
 *   or check `instanceof UrlTree` (imported from @angular/router).
 *
 * Run with:
 *   cd frontend
 *   npx ng test --include="src/app/tcd14-auth-guard.spec.ts" --watch=false
 */

import { TestBed } from '@angular/core/testing';
import { provideRouter, UrlTree } from '@angular/router';
import { authGuard } from './auth.guard';
import { AuthService } from './auth.service';

function setupTestBed(isLoggedIn: boolean): void {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      {
        provide: AuthService,
        useValue: { isLoggedIn: () => isLoggedIn },
      },
    ],
  });
}

describe('TCD-14 — authGuard', () => {
  afterEach(() => { TestBed.resetTestingModule(); });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-14-01 — Guard returns true when user is logged in
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-14-01 — Guard returns true when user is logged in', () => {
    it('returns true', () => {
      setupTestBed(true);
      const result = TestBed.runInInjectionContext(() =>
        authGuard(null as any, null as any)
      );
      expect(result).toBe(true);
    });
  });

  // ─────────────────────────────────────────────────────────────────────────
  // TC-14-02 — Guard returns UrlTree to /auth when user is not logged in
  // ─────────────────────────────────────────────────────────────────────────

  describe('TC-14-02 — Guard returns UrlTree to /auth when not logged in', () => {
    it('returns a UrlTree instance', () => {
      setupTestBed(false);
      const result = TestBed.runInInjectionContext(() =>
        authGuard(null as any, null as any)
      );
      expect(result).toBeInstanceOf(UrlTree);
    });

    it('UrlTree resolves to /auth', () => {
      setupTestBed(false);
      const result = TestBed.runInInjectionContext(() =>
        authGuard(null as any, null as any)
      ) as UrlTree;
      expect(result.toString()).toBe('/auth');
    });
  });
});

