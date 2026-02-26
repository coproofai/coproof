import { Component } from '@angular/core';
import { NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { TaskService } from '../task.service';

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
        <p *ngIf="statusMessage" class="status">{{ statusMessage }}</p>
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
      background: #ecfdf5;
      border: 1px solid #bbf7d0;
      color: #166534;
      padding: 10px;
      border-radius: 8px;
      font-size: 0.9rem;
      font-weight: 600;
    }
  `]
})
export class CreateProjectPageComponent {
  projectName = '';
  goal = '';
  description = '';
  visibility: 'public' | 'private' = 'public';
  statusMessage = '';
  loading = false;

  constructor(
    private readonly taskService: TaskService,
    private readonly router: Router
  ) {}

  createProject() {
    if (!this.projectName.trim()) {
      this.statusMessage = 'El nombre del proyecto es obligatorio.';
      return;
    }

    if (!this.goal.trim()) {
      this.statusMessage = 'El objetivo lógico (goal) es obligatorio.';
      return;
    }

    if (!this.taskService.getAccessToken()) {
      this.statusMessage = 'No hay access token. Agrégalo en Auth antes de crear proyectos.';
      return;
    }

    this.loading = true;
    this.statusMessage = 'Creando proyecto en backend...';

    this.taskService.createProject({
      name: this.projectName.trim(),
      goal: this.goal.trim(),
      description: this.description.trim() || undefined,
      visibility: this.visibility
    }).subscribe({
      next: (project) => {
        this.loading = false;
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
        this.loading = false;
        this.statusMessage = error?.error?.error || 'No se pudo crear el proyecto.';
      }
    });
  }
}
