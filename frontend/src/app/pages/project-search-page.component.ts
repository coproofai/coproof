import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgFor, NgIf } from '@angular/common';

interface Project {
  id: number;
  name: string;
  visibility: 'Público' | 'Privado';
  collaborators: string[];
  demonstrated: number;
  total: number;
}

@Component({
  selector: 'app-project-search-page',
  standalone: true,
  imports: [FormsModule, NgFor, NgIf],
  template: `
    <div class="max-wrap">
      <h1>Buscar Proyectos de Formalización</h1>

      <div class="layout">
        <section class="left">
          <input class="search" [(ngModel)]="query" (input)="filterProjects()" placeholder="Buscar por nombre del proyecto..." />
          <h2>Resultados</h2>
          <div *ngFor="let project of filtered" class="project-item" [class.selected]="project.id === selected?.id" (click)="select(project)">
            <span>{{ project.name }}</span>
            <small>{{ project.visibility }}</small>
          </div>
          <p *ngIf="filtered.length === 0" class="empty">No se encontraron proyectos.</p>
        </section>

        <section class="right">
          <ng-container *ngIf="selected; else welcome">
            <h2>{{ selected.name }}</h2>
            <p class="visibility" [class.public]="selected.visibility === 'Público'" [class.private]="selected.visibility === 'Privado'">
              {{ selected.visibility }}
            </p>

            <h3>Colaboradores</h3>
            <div class="collaborators">
              <span *ngFor="let user of selected.collaborators">{{ user }}</span>
            </div>

            <h3>Progreso General de Metas</h3>
            <div class="progress-row">
              <span>Demostrado: {{ selected.demonstrated }}</span>
              <span>Por demostrar: {{ selected.total - selected.demonstrated }}</span>
            </div>
            <div class="bar"><div class="fill" [style.width.%]="progress(selected)"></div></div>
            <p class="progress-label">{{ progress(selected) }}% del total de nodos completado.</p>
          </ng-container>

          <ng-template #welcome>
            <h2>Detalle del Proyecto</h2>
            <p>Selecciona un proyecto para ver su información y progreso.</p>
          </ng-template>
        </section>
      </div>
    </div>
  `,
  styles: [`
    .max-wrap { max-width: 1320px; margin: 0 auto; }
    h1 { margin: 0 0 18px 0; }
    .layout { display: grid; grid-template-columns: 1fr 2fr; gap: 16px; }
    .left, .right {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 14px;
      min-height: 420px;
    }
    .search {
      width: 100%;
      padding: 10px;
      border: 2px solid #e5e7eb;
      border-radius: 10px;
      box-sizing: border-box;
      margin-bottom: 12px;
    }
    h2 { margin: 0 0 10px 0; color: #555; }
    .project-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border: 1px solid #f3f4f6;
      border-radius: 8px;
      padding: 10px;
      margin-bottom: 8px;
      cursor: pointer;
      background: #fff;
    }
    .project-item:hover { background: #f9fafb; }
    .project-item.selected { background: #e5e5e5; border-color: #333; }
    .project-item small { font-weight: 700; color: #555; }
    .visibility {
      display: inline-block;
      margin: 0 0 10px 0;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 700;
    }
    .public { background: #dcfce7; color: #166534; }
    .private { background: #fee2e2; color: #991b1b; }
    h3 { margin: 12px 0 8px 0; color: #555; }
    .collaborators { display: flex; flex-wrap: wrap; gap: 8px; }
    .collaborators span {
      background: #e5e7eb;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 0.84rem;
      font-weight: 600;
    }
    .progress-row { display: flex; justify-content: space-between; font-size: 0.9rem; font-weight: 600; color: #555; }
    .bar { height: 12px; border-radius: 6px; overflow: hidden; background: #e5e7eb; margin-top: 8px; }
    .fill { height: 100%; background: #333; }
    .progress-label { margin: 6px 0 0 0; color: #666; font-size: 0.88rem; }
    .empty { color: #666; }
    @media (max-width: 980px) { .layout { grid-template-columns: 1fr; } }
  `]
})
export class ProjectSearchPageComponent {
  query = '';

  readonly projects: Project[] = [
    { id: 1, name: 'Teoría de la Computación', visibility: 'Público', collaborators: ['AlanTuring', 'AdaLovelace'], demonstrated: 15, total: 20 },
    {
      id: 2,
      name: 'Geometría Algebraica Avanzada',
      visibility: 'Privado',
      collaborators: ['User_Current', 'EvaristeGalois', 'SophieGermain'],
      demonstrated: 8,
      total: 30
    },
    {
      id: 3,
      name: 'Fundamentos de la Lógica Matemática',
      visibility: 'Público',
      collaborators: ['KurtGoedel', 'BertrandRussel'],
      demonstrated: 50,
      total: 50
    },
    {
      id: 4,
      name: 'Cálculo Integral para Ingeniería',
      visibility: 'Privado',
      collaborators: ['User_Current', 'IsaacNewton'],
      demonstrated: 12,
      total: 25
    }
  ];

  filtered: Project[] = [...this.projects];
  selected: Project | null = this.projects[0];

  filterProjects() {
    const normalized = this.query.trim().toLowerCase();
    this.filtered = this.projects.filter((p) => p.name.toLowerCase().includes(normalized));
    if (!this.selected || !this.filtered.some((project) => project.id === this.selected?.id)) {
      this.selected = this.filtered[0] ?? null;
    }
  }

  select(project: Project) {
    this.selected = project;
  }

  progress(project: Project): number {
    if (project.total === 0) {
      return 0;
    }

    return Math.round((project.demonstrated / project.total) * 100);
  }
}
