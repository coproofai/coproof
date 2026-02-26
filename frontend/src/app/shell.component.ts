import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { NgFor } from '@angular/common';

interface NavItem {
  label: string;
  route: string;
}

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, NgFor],
  template: `
    <div class="app-shell">
      <header class="shell-header">
        <div class="shell-header-main">
          <div class="shell-title">CoProof</div>
          <button class="menu-toggle" (click)="menuOpen = !menuOpen">
            {{ menuOpen ? 'Hide Menu' : 'Show Menu' }}
          </button>
        </div>

        <nav class="shell-nav" [class.hidden]="!menuOpen">
          <a
            *ngFor="let item of navItems"
            [routerLink]="item.route"
            routerLinkActive="active-link"
            class="nav-link"
          >
            {{ item.label }}
          </a>
        </nav>
      </header>

      <main class="shell-content">
        <router-outlet />
      </main>
    </div>
  `,
  styles: [`
    .app-shell { min-height: 100vh; background: #f7f7f7; color: #333; }
    .shell-header {
      position: sticky;
      top: 0;
      z-index: 20;
      background: #ffffff;
      border-bottom: 1px solid #e5e7eb;
      padding: 10px 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .shell-header-main {
      width: 100%;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .shell-title { font-size: 1.15rem; font-weight: 700; white-space: nowrap; }
    .menu-toggle {
      border: 1px solid #d1d5db;
      background: #fff;
      color: #374151;
      border-radius: 8px;
      padding: 7px 10px;
      font-size: 0.85rem;
      font-weight: 700;
      cursor: pointer;
    }
    .shell-nav {
      width: 100%;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .shell-nav.hidden { display: none; }
    .nav-link {
      text-decoration: none;
      color: #4b5563;
      border: 1px solid transparent;
      border-radius: 8px;
      padding: 8px 10px;
      font-size: 0.85rem;
      font-weight: 600;
      white-space: nowrap;
      transition: all 0.15s;
    }
    .nav-link:hover { background: #f3f4f6; color: #111827; }
    .active-link { background: #111827; color: #fff; border-color: #111827; }
    .shell-content { padding: 18px; }
  `]
})
export class ShellComponent {
  menuOpen = false;

  navItems: NavItem[] = [
    { label: 'Main Menu', route: '/menu' },
    { label: 'Validation', route: '/validation' },
    { label: 'Translation', route: '/translation' },
    { label: 'Proof Search', route: '/proof-search' },
    { label: 'Lineage Search', route: '/lineage-search' },
    { label: 'Create Project', route: '/create-project' },
    { label: 'Project Search', route: '/project-search' },
    { label: 'Open Workspace', route: '/open-workspace' },
    { label: 'Account Config', route: '/account-config' },
    { label: 'Environment Config', route: '/environment-config' },
    { label: 'Debug Code Executors', route: '/debug-executors' }
  ];
}
