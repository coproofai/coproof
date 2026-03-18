import { Component } from '@angular/core';
import { NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { TaskService } from '../../task.service';
import { finalize, timeout } from 'rxjs/operators';

@Component({
  selector: 'app-create-project-page',
  standalone: true,
  imports: [NgIf, FormsModule],
  templateUrl: './create-project-page.html',
  styleUrl: './create-project-page.css'
})
export class CreateProjectPageComponent {
  projectName = '';
  goal = '';
  goalImportsText = '';
  goalDefinitions = '';
  description = '';
  visibility: 'public' | 'private' = 'public';
  statusMessage = '';
  statusKind: 'info' | 'success' | 'error' = 'info';
  loading = false;

  constructor(
    private readonly taskService: TaskService,
    private readonly router: Router
  ) {}

  createProject() {
    if (!this.projectName.trim()) {
      this.statusKind = 'error';
      this.statusMessage = 'El nombre del proyecto es obligatorio.';
      return;
    }

    if (!this.goal.trim()) {
      this.statusKind = 'error';
      this.statusMessage = 'El objetivo lógico (goal) es obligatorio.';
      return;
    }

    if (!this.taskService.getAccessToken()) {
      this.statusKind = 'error';
      this.statusMessage = 'No hay access token. Agrégalo en Auth antes de crear proyectos.';
      return;
    }

    this.loading = true;
    this.statusKind = 'info';
    this.statusMessage = 'Creando proyecto en backend...';

    this.taskService.createProject({
      name: this.projectName.trim(),
      goal: this.goal.trim(),
      goal_imports: this.parseGoalImports(this.goalImportsText),
      goal_definitions: this.goalDefinitions.trim() || undefined,
      description: this.description.trim() || undefined,
      visibility: this.visibility
    }).pipe(
      // Avoid indefinite UI lock when backend/network hangs.
      timeout(45000),
      finalize(() => {
        this.loading = false;
      })
    ).subscribe({
      next: (project) => {
        this.statusKind = 'success';
        this.statusMessage = `Proyecto '${project.name}' creado.`;
        this.router.navigate(['/workspace'], {
          queryParams: {
            projectId: project.id,
            projectName: project.name,
            sessionType: 'individual'
          }
        });
      },
      error: (error) => {
        const backendMessage = this.extractBackendErrorMessage(error);
        if (this.isAuthError(error, backendMessage)) {
          this.taskService.clearAccessToken();
          this.statusKind = 'error';
          this.statusMessage = 'Tu sesion expiro o es invalida. Vuelve a Auth e inicia sesion con GitHub.';
          return;
        }

        if (error?.name === 'TimeoutError') {
          this.statusKind = 'error';
          this.statusMessage = 'La creacion del proyecto excedio el tiempo de espera. Reintenta en unos segundos.';
          return;
        }

        this.statusKind = 'error';
        this.statusMessage =
          backendMessage ||
          `No se pudo crear el proyecto (HTTP ${error?.status ?? 'desconocido'}).`;
      }
    });
  }

  private extractBackendErrorMessage(error: any): string {
    const payload = error?.error;
    if (typeof payload === 'string') {
      return payload;
    }

    const baseMessage = payload?.message || payload?.error || payload?.msg || '';
    const validationErrors = payload?.validation_errors || payload?.verification?.errors || [];
    if (!Array.isArray(validationErrors) || validationErrors.length === 0) {
      return baseMessage;
    }

    const details = validationErrors
      .slice(0, 6)
      .map((item: any) => {
        const line = item?.line ?? '?';
        const column = item?.column ?? '?';
        const message = item?.message || 'Error de compilacion Lean';
        return `L${line}:C${column} ${message}`;
      });

    const extra = validationErrors.length > 6
      ? `\n... y ${validationErrors.length - 6} error(es) mas.`
      : '';

    const detailBlock = details.join('\n');
    return [baseMessage, detailBlock].filter(Boolean).join('\n') + extra;
  }

  private isAuthError(error: any, backendMessage: string): boolean {
    if (error?.status === 401) {
      return true;
    }

    if (error?.status !== 422) {
      return false;
    }

    const msg = (backendMessage || '').toLowerCase();
    return msg.includes('signature verification failed')
      || msg.includes('token has expired')
      || msg.includes('not enough segments')
      || msg.includes('missing authorization header')
      || msg.includes('invalid header');
  }

  private parseGoalImports(rawImports: string): string[] | undefined {
    const imports = rawImports
      .split(/\r?\n/)
      .map(line => line.trim())
      .filter(line => !!line)
      .map(line => line.startsWith('import ') ? line.slice(7).trim() : line)
      .filter(line => !!line);

    return imports.length > 0 ? Array.from(new Set(imports)) : undefined;
  }
}
