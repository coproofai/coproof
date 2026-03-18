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
  templateUrl: './project-search-page.html',
  styleUrl: './project-search-page.css'
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
