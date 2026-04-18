import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { NgFor, NgIf, AsyncPipe } from '@angular/common';
import { AuthService, AuthUser } from './auth.service';
import { Observable } from 'rxjs';

interface NavItem {
  label: string;
  route: string;
  protected?: boolean;
}

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, NgFor, NgIf, AsyncPipe],
  template: `
    <div class="app-shell" [class.nav-open]="menuOpen">
      <header class="shell-header">
        <div class="shell-header-inner">
          <a routerLink="/menu" class="shell-brand" (click)="menuOpen = false">CoProof</a>

          <div class="shell-header-right">
            <ng-container *ngIf="isLoggedIn$ | async; else loginLink">
              <span *ngIf="user" class="user-label">{{ user.full_name }}</span>
              <button class="btn-outline-sm" (click)="logout()">Cerrar sesión</button>
            </ng-container>
            <ng-template #loginLink>
              <a routerLink="/auth" class="btn-outline-sm">Iniciar sesión</a>
            </ng-template>

            <button class="hamburger" (click)="menuOpen = !menuOpen" [attr.aria-expanded]="menuOpen" aria-label="Menú">
              <span></span><span></span><span></span>
            </button>
          </div>
        </div>
      </header>

      <div class="nav-overlay" *ngIf="menuOpen" (click)="menuOpen = false"></div>

      <nav class="side-nav" [class.open]="menuOpen">
        <div class="side-nav-header">
          <span class="side-nav-title">Navegación</span>
          <button class="side-nav-close" (click)="menuOpen = false" aria-label="Cerrar menú">&#x2715;</button>
        </div>

        <div class="nav-section">
          <p class="nav-section-label">Herramientas</p>
          <ng-container *ngFor="let item of navItems">
            <a
              *ngIf="!item.protected"
              [routerLink]="item.route"
              routerLinkActive="nav-active"
              class="nav-item"
              (click)="menuOpen = false"
            >{{ item.label }}</a>
          </ng-container>
        </div>

        <div class="nav-section">
          <p class="nav-section-label">Workspace</p>
          <ng-container *ngFor="let item of navItems">
            <a
              *ngIf="item.protected && (isLoggedIn$ | async)"
              [routerLink]="item.route"
              routerLinkActive="nav-active"
              class="nav-item"
              (click)="menuOpen = false"
            >{{ item.label }}</a>
            <span
              *ngIf="item.protected && !(isLoggedIn$ | async)"
              class="nav-item nav-item-locked"
              title="Requiere autenticación"
            >{{ item.label }}<span class="lock-badge">Auth</span></span>
          </ng-container>
        </div>
      </nav>

      <main class="shell-content">
        <router-outlet />
      </main>
    </div>
  `,
  styles: [`
    *, *::before, *::after { box-sizing: border-box; }
    .app-shell { min-height: 100vh; background: #f7f8fa; color: #1a1a2e; }

    /* ── HEADER ── */
    .shell-header {
      position: sticky; top: 0; z-index: 100;
      background: #fff;
      border-bottom: 1px solid #e5e7eb;
      height: 56px;
    }
    .shell-header-inner {
      max-width: 1600px; margin: 0 auto; padding: 0 20px;
      height: 100%;
      display: flex; align-items: center; justify-content: space-between;
    }
    .shell-brand {
      font-size: 1.15rem; font-weight: 800; letter-spacing: -0.02em;
      color: #111827; text-decoration: none;
    }
    .shell-brand:hover { color: #374151; }
    .shell-header-right { display: flex; align-items: center; gap: 10px; }
    .user-label { font-size: 0.82rem; color: #6b7280; font-weight: 500; white-space: nowrap; }
    .btn-outline-sm {
      font-size: 0.8rem; font-weight: 600;
      padding: 6px 12px; border-radius: 7px;
      border: 1px solid #d1d5db; background: #fff; color: #374151;
      cursor: pointer; text-decoration: none; white-space: nowrap;
      transition: background 0.15s;
    }
    .btn-outline-sm:hover { background: #f3f4f6; }

    /* ── HAMBURGER ── */
    .hamburger {
      display: flex; flex-direction: column; justify-content: center;
      gap: 5px; width: 36px; height: 36px;
      border: 1px solid #e5e7eb; border-radius: 7px;
      background: #fff; cursor: pointer; padding: 8px;
    }
    .hamburger span {
      display: block; width: 100%; height: 2px;
      background: #374151; border-radius: 2px;
      transition: transform 0.2s, opacity 0.2s;
    }
    .nav-open .hamburger span:nth-child(1) { transform: translateY(7px) rotate(45deg); }
    .nav-open .hamburger span:nth-child(2) { opacity: 0; }
    .nav-open .hamburger span:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }

    /* ── OVERLAY ── */
    .nav-overlay {
      position: fixed; inset: 0; z-index: 110;
      background: rgba(0,0,0,0.35);
    }

    /* ── SIDE NAV ── */
    .side-nav {
      position: fixed; top: 0; left: 0; z-index: 120;
      width: 280px; height: 100vh;
      background: #fff; border-right: 1px solid #e5e7eb;
      display: flex; flex-direction: column;
      transform: translateX(-100%);
      transition: transform 0.25s cubic-bezier(0.4,0,0.2,1);
      overflow-y: auto;
    }
    .side-nav.open { transform: translateX(0); }
    .side-nav-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 16px 20px; border-bottom: 1px solid #f1f5f9;
      flex-shrink: 0;
    }
    .side-nav-title { font-weight: 700; font-size: 0.9rem; color: #111827; }
    .side-nav-close {
      width: 28px; height: 28px; border-radius: 6px;
      border: 1px solid #e5e7eb; background: #fff;
      cursor: pointer; font-size: 0.9rem; color: #6b7280;
      display: flex; align-items: center; justify-content: center;
    }
    .side-nav-close:hover { background: #f3f4f6; }
    .nav-section { padding: 12px 0; border-bottom: 1px solid #f1f5f9; }
    .nav-section:last-child { border-bottom: none; }
    .nav-section-label {
      margin: 0 0 4px 0; padding: 0 20px;
      font-size: 0.7rem; font-weight: 700; letter-spacing: 0.07em;
      text-transform: uppercase; color: #9ca3af;
    }
    .nav-item {
      display: flex; align-items: center; justify-content: space-between;
      padding: 9px 20px;
      font-size: 0.88rem; font-weight: 500; color: #374151;
      text-decoration: none; cursor: pointer;
      transition: background 0.12s;
    }
    .nav-item:hover { background: #f9fafb; color: #111827; }
    .nav-active { color: #111827; font-weight: 700; background: #f3f4f6; }
    .nav-item-locked { color: #c4c9d4; cursor: default; }
    .nav-item-locked:hover { background: transparent; color: #c4c9d4; }
    .lock-badge {
      font-size: 0.65rem; font-weight: 700; letter-spacing: 0.05em;
      padding: 2px 6px; border-radius: 4px;
      background: #f1f5f9; color: #9ca3af; border: 1px solid #e5e7eb;
    }

    /* ── CONTENT ── */
    .shell-content { padding: 20px; max-width: 1600px; margin: 0 auto; }
  `]
})
export class ShellComponent {
  menuOpen = false;
  user: AuthUser | null;
  isLoggedIn$: Observable<boolean>;

  constructor(private readonly auth: AuthService) {
    this.user = this.auth.getUser();
    this.isLoggedIn$ = this.auth.isLoggedIn$;
  }

  logout(): void {
    this.auth.logout();
  }

  navItems: NavItem[] = [
    { label: 'Main Menu',              route: '/menu' },
    { label: 'Validation',             route: '/validation' },
    { label: 'Translation',            route: '/translation' },
    { label: 'Proof Search',           route: '/proof-search' },
    { label: 'Lineage Search',         route: '/lineage-search' },
    { label: 'Project Search',         route: '/project-search' },
    { label: 'Environment Config',     route: '/environment-config' },
    { label: 'Debug Code Executors',   route: '/debug-executors' },
    { label: 'Create Project',         route: '/create-project',  protected: true },
    { label: 'Open Workspace',         route: '/open-workspace',  protected: true },
    { label: 'Account Config',         route: '/account-config',  protected: true },
  ];
}
