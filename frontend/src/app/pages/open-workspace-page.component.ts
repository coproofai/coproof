import { Component } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { NewProjectDto, TaskService } from '../task.service';

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
            <optgroup label="Mis proyectos" *ngIf="ownedProjects.length > 0">
              <option *ngFor="let project of ownedProjects" [value]="project.id">
                {{ project.name }} ({{ project.visibility === 'public' ? 'Público' : 'Privado' }})
              </option>
            </optgroup>
            <optgroup label="Proyectos donde colaboro" *ngIf="collaboratorProjects.length > 0">
              <option *ngFor="let project of collaboratorProjects" [value]="project.id">
                {{ project.name }} (Colaborador)
              </option>
            </optgroup>
            <optgroup label="Proyectos públicos" *ngIf="publicProjects.length > 0">
              <option *ngFor="let project of publicProjects" [value]="project.id">
                {{ project.name }} (Público)
              </option>
            </optgroup>
          </select>
          <small *ngIf="loading">Cargando proyectos...</small>
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
  projects: NewProjectDto[] = [];
  currentUserId = '';

  selectedProjectId = '';
  sessionType: 'individual' | 'collaborative' = 'individual';
  message = '';
  loading = false;

  constructor(
    private readonly router: Router,
    private readonly taskService: TaskService
  ) {
    this.loadProjects();
  }

  get accessibleProjects(): NewProjectDto[] {
    return this.projects;
  }

  get ownedProjects(): NewProjectDto[] {
    if (!this.currentUserId) {
      return this.projects;
    }
    return this.projects.filter((project) => project.author_id === this.currentUserId);
  }

  get collaboratorProjects(): NewProjectDto[] {
    if (!this.currentUserId) {
      return [];
    }

    return this.projects.filter((project) => {
      const contributors = project.contributor_ids || [];
      return project.author_id !== this.currentUserId && contributors.includes(this.currentUserId);
    });
  }

  get publicProjects(): NewProjectDto[] {
    return this.projects.filter((project) => {
      if (project.visibility !== 'public') {
        return false;
      }
      if (project.author_id === this.currentUserId) {
        return false;
      }
      const contributors = project.contributor_ids || [];
      return !contributors.includes(this.currentUserId);
    });
  }

  private loadProjects() {
    if (!this.taskService.getAccessToken()) {
      this.message = 'No hay access token. Agrégalo en Auth para listar proyectos.';
      return;
    }

    this.currentUserId = this.taskService.getCurrentUserIdFromToken() || '';

    this.loading = true;
    this.taskService.getAccessibleProjects().subscribe({
      next: (response) => {
        this.projects = response.projects;
        this.loading = false;
      },
      error: (error) => {
        this.loading = false;
        if (this.handleAuthError(error)) {
          return;
        }
        this.message = this.getBackendErrorMessage(error) || 'No se pudieron cargar los proyectos.';
      }
    });
  }

  private getBackendErrorMessage(error: any): string {
    return error?.error?.message || error?.error?.error || error?.error?.msg || '';
  }

  private handleAuthError(error: any): boolean {
    const message = this.getBackendErrorMessage(error);
    if (message === 'Signature verification failed' || error?.status === 401 || error?.status === 422) {
      this.taskService.clearAccessToken();
      this.message = 'Tu sesion expiro o es invalida. Vuelve a Auth para pegar un access token nuevo.';
      return true;
    }
    return false;
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
