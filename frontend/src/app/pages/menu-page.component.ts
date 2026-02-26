import { Component } from '@angular/core';
import { NgFor } from '@angular/common';
import { RouterLink } from '@angular/router';

interface MenuItem {
  title: string;
  route: string;
}

@Component({
  selector: 'app-menu-page',
  standalone: true,
  imports: [NgFor, RouterLink],
  template: `
    <h1 class="title">Menú Principal</h1>

    <div class="menu-grid">
      <a *ngFor="let item of menuItems" [routerLink]="item.route" class="menu-item">
        <p class="menu-item-title">{{ item.title }}</p>
      </a>
    </div>
  `,
  styles: [`
    .title { margin: 0 0 22px 0; border-bottom: 2px solid #ddd; padding-bottom: 10px; }
    .menu-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
    .menu-item {
      text-decoration: none;
      color: inherit;
      background: #fff;
      padding: 24px;
      border-radius: 8px;
      border: 1px solid #eee;
      box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
      transition: all 0.2s;
    }
    .menu-item:hover { transform: translateY(-2px); box-shadow: 0 6px 14px rgba(0, 0, 0, 0.1); }
    .menu-item-title { margin: 0; font-size: 1.05rem; font-weight: 700; color: #555; }
  `]
})
export class MenuPageComponent {
  menuItems: MenuItem[] = [
    { title: 'Validar Demostración', route: '/validation' },
    { title: 'Traducir a Lean', route: '/translation' },
    { title: 'Buscar Demostración', route: '/proof-search' },
    { title: 'Buscar Linaje', route: '/lineage-search' },
    { title: 'Crear Proyecto (Privado o Público)', route: '/create-project' },
    { title: 'Buscar Proyectos', route: '/project-search' },
    { title: 'Abrir Workspace', route: '/open-workspace' },
    { title: 'Debug Code Executors', route: '/debug-executors' }
  ];
}
