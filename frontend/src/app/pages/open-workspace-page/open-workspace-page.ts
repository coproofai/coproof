import { Component } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { TaskService } from '../../task.service';
import { NewProjectDto } from '../../task.models';

@Component({
  selector: 'app-open-workspace-page',
  standalone: true,
  imports: [NgFor, NgIf, FormsModule],
  templateUrl: './open-workspace-page.html',
  styleUrl: './open-workspace-page.css'
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
