import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, firstValueFrom } from 'rxjs';

export interface AuthUser {
  id: string;
  full_name: string;
  email: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly apiBase = 'http://localhost:5001/api/v1';
  private readonly accessTokenKey = 'access_token';
  private readonly refreshTokenKey = 'refresh_token';
  private readonly authUserKey = 'auth_user';

  private _isLoggedIn$ = new BehaviorSubject<boolean>(this._hasValidToken());
  readonly isLoggedIn$ = this._isLoggedIn$.asObservable();

  constructor(private http: HttpClient, private router: Router) {}

  private _hasValidToken(): boolean {
    return !!localStorage.getItem('access_token');
  }

  getUser(): AuthUser | null {
    const raw = localStorage.getItem(this.authUserKey);
    if (!raw) return null;
    try { return JSON.parse(raw) as AuthUser; } catch { return null; }
  }

  getAccessToken(): string {
    return localStorage.getItem(this.accessTokenKey) || '';
  }

  getRefreshToken(): string {
    return localStorage.getItem(this.refreshTokenKey) || '';
  }

  isLoggedIn(): boolean {
    return this._isLoggedIn$.getValue();
  }

  async initiateGitHubLogin(): Promise<void> {
    const resp = await firstValueFrom(
      this.http.get<{ url: string }>(`${this.apiBase}/auth/github/url`)
    );
    window.location.href = resp.url;
  }

  async handleOAuthCallback(code: string): Promise<void> {
    const resp = await firstValueFrom(
      this.http.post<{ access_token: string; refresh_token: string; user: AuthUser }>(
        `${this.apiBase}/auth/github/callback`,
        { code }
      )
    );
    localStorage.setItem(this.accessTokenKey, resp.access_token);
    localStorage.setItem(this.refreshTokenKey, resp.refresh_token);
    localStorage.setItem(this.authUserKey, JSON.stringify(resp.user));
    this._isLoggedIn$.next(true);
  }

  async refreshAccessToken(): Promise<boolean> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) return false;
    try {
      const resp = await firstValueFrom(
        this.http.post<{ access_token: string }>(
          `${this.apiBase}/auth/refresh`,
          {},
          { headers: new HttpHeaders({ Authorization: `Bearer ${refreshToken}` }) }
        )
      );
      localStorage.setItem(this.accessTokenKey, resp.access_token);
      this._isLoggedIn$.next(true);
      return true;
    } catch {
      return false;
    }
  }

  logout(): void {
    localStorage.removeItem(this.accessTokenKey);
    localStorage.removeItem(this.refreshTokenKey);
    localStorage.removeItem(this.authUserKey);
    this._isLoggedIn$.next(false);
    this.router.navigate(['/auth']);
  }
}
