import { Component } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-create-project-page',
  standalone: true,
  imports: [NgFor, NgIf, FormsModule],
  template: `
    <div class="max-wrap">
      <h1>Crear Nuevo Proyecto de Formalización</h1>

      <form class="card" (submit)="$event.preventDefault()">
        <div class="field">
          <label>Nombre del Proyecto *</label>
          <input [(ngModel)]="projectName" name="projectName" placeholder="Ej: Fundamentos de la Teoría de Conjuntos" />
        </div>

        <div class="field">
          <label>Grado de Visibilidad</label>
          <div class="row">
            <label><input type="radio" name="visibility" value="public" [(ngModel)]="visibility" /> Público</label>
            <label><input type="radio" name="visibility" value="private" [(ngModel)]="visibility" /> Privado</label>
          </div>
        </div>

        <div class="field light-box">
          <label><input type="checkbox" [(ngModel)]="importEnabled" name="importEnabled" /> Importar premisas de un proyecto existente</label>
          <select *ngIf="importEnabled" [(ngModel)]="importProject" name="importProject">
            <option value="">Selecciona un proyecto...</option>
            <option value="Lean 4 Core Library">Lean 4 Core Library</option>
            <option value="Matemática Elemental Verificada">Matemática Elemental Verificada</option>
            <option value="Teoría de Categorías">Teoría de Categorías</option>
          </select>
        </div>

        <div *ngIf="visibility === 'private'" class="field light-red">
          <label>Añadir Colaboradores</label>
          <div class="tags">
            <span class="tag" *ngFor="let collaborator of collaborators">
              {{ collaborator }}
              <button type="button" (click)="removeCollaborator(collaborator)">×</button>
            </span>
          </div>
          <div class="row">
            <input [(ngModel)]="collaboratorInput" name="collaboratorInput" placeholder="Usuario" (keyup.enter)="addCollaborator()" />
            <button type="button" class="btn-secondary" (click)="addCollaborator()">Añadir</button>
          </div>
        </div>

        <button class="btn-primary" type="button" (click)="createProject()">Crear Proyecto</button>
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
    .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
    .light-box { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
    .light-red { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 12px; }
    .tags { display: flex; gap: 8px; flex-wrap: wrap; }
    .tag {
      background: #e5e7eb;
      border-radius: 999px;
      padding: 5px 10px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.85rem;
    }
    .tag button {
      border: none;
      background: transparent;
      cursor: pointer;
      font-size: 1rem;
      line-height: 1;
      color: #444;
    }
    .btn-primary {
      border: none;
      background: #333;
      color: #fff;
      font-weight: 700;
      border-radius: 8px;
      padding: 10px 18px;
      cursor: pointer;
    }
    .btn-secondary {
      border: none;
      background: #555;
      color: #fff;
      border-radius: 8px;
      padding: 10px 14px;
      cursor: pointer;
    }
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
  visibility: 'public' | 'private' = 'public';
  importEnabled = false;
  importProject = '';
  collaboratorInput = '';
  collaborators: string[] = ['usuario_ejemplo1', 'usuario_ejemplo2'];
  statusMessage = '';

  addCollaborator() {
    const value = this.collaboratorInput.trim();
    if (!value || this.collaborators.includes(value)) {
      return;
    }

    this.collaborators = [...this.collaborators, value];
    this.collaboratorInput = '';
  }

  removeCollaborator(username: string) {
    this.collaborators = this.collaborators.filter((item) => item !== username);
  }

  createProject() {
    if (!this.projectName.trim()) {
      this.statusMessage = 'El nombre del proyecto es obligatorio.';
      return;
    }

    this.statusMessage = `¡Proyecto '${this.projectName}' creado exitosamente!`;
  }
}
