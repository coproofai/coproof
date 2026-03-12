import { Component } from '@angular/core';
import { NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { TaskService } from '../task.service';
import { finalize, timeout } from 'rxjs/operators';

@Component({
  selector: 'app-create-project-page',
  standalone: true,
  imports: [NgIf, FormsModule],
  template: `
    <div class="max-wrap">
      <h1>Crear Nuevo Proyecto de Formalización</h1>

      <form class="card" (submit)="$event.preventDefault()">
        <div class="field">
          <label>Nombre del Proyecto *</label>
          <input [(ngModel)]="projectName" name="projectName" placeholder="Ej: Fundamentos de la Teoría de Conjuntos" />
        </div>

        <div class="field">
          <label>Objetivo lógico (goal) *</label>
          <textarea [(ngModel)]="goal" name="goal" rows="4" placeholder="Ej: ∀ a b : Nat, a + b = b + a"></textarea>
        </div>

        <div class="field">
          <label>Imports de Mathlib (opcional)</label>
          <textarea
            [(ngModel)]="goalImportsText"
            name="goalImportsText"
            rows="3"
            placeholder="Una línea por módulo, ej:\nMathlib.Data.Real.Basic\nMathlib.Algebra.Group.Defs"
          ></textarea>
        </div>

        <div class="field">
          <label>Definiciones Lean para el Goal (opcional)</label>
          <textarea
            [(ngModel)]="goalDefinitions"
            name="goalDefinitions"
            rows="5"
            placeholder="Ej:\nabbrev Monotona (f : Nat → Nat) : Prop :=\n  ∀ (a b : Nat), a ≤ b → f a ≤ f b"
          ></textarea>
        </div>

        <div class="field">
          <label>Descripción</label>
          <textarea [(ngModel)]="description" name="description" rows="3" placeholder="Descripción opcional"></textarea>
        </div>

        <div class="field">
          <label>Grado de Visibilidad</label>
          <div class="row">
            <label><input type="radio" name="visibility" value="public" [(ngModel)]="visibility" /> Público</label>
            <label><input type="radio" name="visibility" value="private" [(ngModel)]="visibility" /> Privado</label>
          </div>
        </div>

        <button class="btn-primary" type="button" [disabled]="loading" (click)="createProject()">
          {{ loading ? 'Creando...' : 'Crear Proyecto' }}
        </button>
        <p
          *ngIf="statusMessage"
          class="status"
          [class.success]="statusKind === 'success'"
          [class.error]="statusKind === 'error'"
          [class.info]="statusKind === 'info'"
        >{{ statusMessage }}</p>
      </form>
    </div>
  `,
  styles: [`
    .max-wrap { max-width: 920px; margin: 0 auto; }
    h1 { margin: 0 0 18px 0; }
    .card {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 18px;
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
    }
    .field { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
    label { font-size: 0.93rem; font-weight: 700; color: #555; }
    input, select {
      border: 1px solid #d1d5db;
      border-radius: 8px;
      padding: 10px;
      font-size: 0.95rem;
    }
    textarea {
      border: 1px solid #d1d5db;
      border-radius: 8px;
      padding: 10px;
      font-size: 0.95rem;
      resize: vertical;
      font-family: inherit;
    }
    .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
    .btn-primary {
      border: none;
      background: #333;
      color: #fff;
      font-weight: 700;
      border-radius: 8px;
      padding: 10px 18px;
      cursor: pointer;
    }
    .btn-primary:disabled { opacity: 0.7; cursor: default; }
    .status {
      margin: 12px 0 0 0;
      padding: 10px;
      border-radius: 8px;
      font-size: 0.9rem;
      font-weight: 600;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .status.info {
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      color: #1e3a8a;
    }
    .status.success {
      background: #ecfdf5;
      border: 1px solid #bbf7d0;
      color: #166534;
    }
    .status.error {
      background: #fef2f2;
      border: 1px solid #fecaca;
      color: #991b1b;
    }
  `]
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
