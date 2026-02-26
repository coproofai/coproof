import { Component } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

interface Project {
  id: number;
  name: string;
  visibility: string;
  collaborators: string[];
}

@Component({
  selector: 'app-open-workspace-page',
  standalone: true,
  imports: [NgFor, NgIf, FormsModule],
  template: `
    <div class="card-wrap">
      <div class="card">
        <h1>Abrir Workspace</h1>

        <div class="field">
          <label>Seleccionar Proyecto</label>
          <select [(ngModel)]="selectedProjectId" name="projectId">
            <option value="">Selecciona un proyecto...</option>
            <option *ngFor="let project of accessibleProjects" [value]="project.id">
              {{ project.name }} ({{ project.visibility }})
            </option>
          </select>
        </div>

        <div class="field">
          <label>Tipo de Sesión</label>
          <label class="option"><input type="radio" name="sessionType" value="individual" [(ngModel)]="sessionType" /> Individual</label>
          <label class="option"><input type="radio" name="sessionType" value="collaborative" [(ngModel)]="sessionType" /> Nueva Sesión Colaborativa</label>
        </div>

        <button (click)="openWorkspace()">Abrir Workspace</button>

        <p *ngIf="message" class="message">{{ message }}</p>
      </div>
    </div>
  `,
  styles: [`
    .card-wrap { display: flex; justify-content: center; padding-top: 24px; }
    .card {
      width: 100%;
      max-width: 620px;
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
      padding: 20px;
    }
    h1 { margin: 0 0 16px 0; }
    .field { margin-bottom: 14px; display: flex; flex-direction: column; gap: 8px; }
    label { font-weight: 700; color: #555; }
    .option {
      font-weight: 500;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 10px;
      background: #f9fafb;
    }
    select {
      border: 1px solid #d1d5db;
      border-radius: 8px;
      padding: 10px;
      font-size: 0.95rem;
    }
    button {
      width: 100%;
      border: none;
      border-radius: 8px;
      background: #333;
      color: #fff;
      padding: 10px;
      font-weight: 700;
      cursor: pointer;
    }
    .message {
      margin: 12px 0 0 0;
      border-radius: 8px;
      background: #dcfce7;
      border: 1px solid #bbf7d0;
      color: #166534;
      padding: 10px;
      font-weight: 600;
    }
  `]
})
export class OpenWorkspacePageComponent {
  readonly currentUser = 'User_Current';

  readonly projects: Project[] = [
    { id: 1, name: 'Teoría de la Computación', visibility: 'Público', collaborators: ['AlanTuring', 'AdaLovelace'] },
    {
      id: 2,
      name: 'Geometría Algebraica Avanzada',
      visibility: 'Privado',
      collaborators: ['User_Current', 'EvaristeGalois', 'SophieGermain']
    },
    {
      id: 3,
      name: 'Fundamentos de la Lógica Matemática',
      visibility: 'Público',
      collaborators: ['KurtGoedel', 'BertrandRussel']
    }
  ];

  selectedProjectId = '';
  sessionType: 'individual' | 'collaborative' = 'individual';
  message = '';

  constructor(private readonly router: Router) {}

  get accessibleProjects(): Project[] {
    return this.projects.filter(
      (project) =>
        project.visibility === 'Público' ||
        (project.visibility === 'Privado' && project.collaborators.includes(this.currentUser))
    );
  }

  openWorkspace() {
    const selected = this.projects.find((project) => String(project.id) === this.selectedProjectId);
    if (!selected) {
      this.message = 'Por favor, selecciona un proyecto para abrir.';
      return;
    }

    this.router.navigate(['/workspace'], {
      queryParams: {
        projectId: selected.id,
        projectName: selected.name,
        sessionType: this.sessionType
      }
    });
  }
}
