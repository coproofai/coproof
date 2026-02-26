import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgFor, NgIf } from '@angular/common';

interface Demonstration {
  id: number;
  title: string;
  preview: string;
  naturalFull: string;
  leanFull: string;
}

@Component({
  selector: 'app-proof-search-page',
  standalone: true,
  imports: [FormsModule, NgFor, NgIf],
  template: `
    <div class="max-wrap">
      <h1>Buscar Demostración en la Base de Conocimiento</h1>

      <div class="search-panel">
        <input type="text" [(ngModel)]="query" (input)="filterResults()" placeholder="Buscar por Teorema, Lema, o Resultado..." />
      </div>

      <div class="grid">
        <section>
          <h2>Resultados ({{ filtered.length }})</h2>
          <div class="content-box results-box">
            <div *ngFor="let demo of filtered" class="result-item" (click)="showDetail(demo)">
              <h3>{{ demo.title }}</h3>
              <p>{{ demo.preview }}</p>
            </div>
            <p *ngIf="filtered.length === 0" class="empty">No se encontraron resultados que coincidan.</p>
          </div>
        </section>

        <section *ngIf="selected" class="detail">
          <h2>Detalle de Demostración: {{ selected.title }}</h2>
          <div class="toggles">
            <label><input type="checkbox" [(ngModel)]="showNatural" /> Lenguaje Natural</label>
            <label><input type="checkbox" [(ngModel)]="showLean" /> Formalismo Lean</label>
          </div>

          <div class="detail-columns" [class.single-column]="!(showNatural && showLean)">
            <div *ngIf="showNatural">
              <h3>Lenguaje Natural</h3>
              <pre class="content-box detail-box">{{ selected.naturalFull }}</pre>
            </div>
            <div *ngIf="showLean">
              <h3>Formalismo Lean</h3>
              <pre class="content-box detail-box">{{ selected.leanFull }}</pre>
            </div>
          </div>
        </section>
      </div>
    </div>
  `,
  styles: [`
    .max-wrap { max-width: 1320px; margin: 0 auto; }
    h1 { margin: 0 0 18px 0; }
    h2 { margin: 0 0 10px 0; font-size: 1.2rem; color: #555; }
    h3 { margin: 0 0 8px 0; }
    .search-panel {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 12px;
      margin-bottom: 14px;
    }
    .search-panel input {
      width: 100%;
      box-sizing: border-box;
      padding: 12px;
      border: 2px solid #ccc;
      border-radius: 10px;
      font-size: 1rem;
    }
    .grid { display: grid; grid-template-columns: minmax(280px, 1fr) minmax(420px, 2fr); gap: 16px; }
    .content-box {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 12px;
      overflow: auto;
    }
    .results-box { min-height: 480px; }
    .result-item {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 10px;
      margin-bottom: 8px;
      cursor: pointer;
    }
    .result-item:hover { background: #f9fafb; }
    .result-item p { margin: 0; color: #666; font-size: 0.9rem; }
    .toggles {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 10px;
      display: flex;
      gap: 16px;
      margin-bottom: 10px;
      font-size: 0.95rem;
      font-weight: 600;
      color: #555;
    }
    .detail-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .detail-columns.single-column { grid-template-columns: 1fr; }
    .detail-box { min-height: 390px; white-space: pre-wrap; margin: 0; }
    .empty { color: #666; margin: 0; }
    @media (max-width: 1080px) {
      .grid { grid-template-columns: 1fr; }
    }
  `]
})
export class ProofSearchPageComponent {
  query = '';
  showNatural = true;
  showLean = true;

  readonly demonstrations: Demonstration[] = [
    {
      id: 1,
      title: 'Teorema de la Paridad de n² + n',
      preview: 'Demuestra que la suma de un número natural y su cuadrado es siempre par...',
      naturalFull:
        'La demostración formal establece que n^2 + n es par al factorizar la expresión como n(n+1). Dado que n y n+1 son consecutivos, uno de ellos siempre es par.',
      leanFull: `theorem paridad_n_cuadrado_mas_n (n : nat) : even (n^2 + n) :=
begin
  -- prueba resumida
end`
    },
    {
      id: 2,
      title: 'Lema de la Transitividad de la Igualdad',
      preview: 'Si a=b y b=c, entonces a=c. Un lema fundamental en lógica formal...',
      naturalFull: 'La transitividad es una propiedad central de igualdad en lógica formal.',
      leanFull: `theorem transitive_eq {α : Type*} (a b c : α) (hab : a = b) (hbc : b = c) : a = c :=
by simpa [hab, hbc]`
    },
    {
      id: 3,
      title: 'Corolario de los Números Primos',
      preview: 'Todo número natural mayor que 1 tiene un divisor primo...',
      naturalFull: 'Este corolario se deriva del Teorema Fundamental de la Aritmética.',
      leanFull: `lemma exists_prime_factor {n : ℕ} (hn : n > 1) : ∃ p, Nat.Prime p ∧ p ∣ n := by
  admit`
    }
  ];

  filtered: Demonstration[] = [...this.demonstrations];
  selected: Demonstration | null = null;

  filterResults() {
    const normalized = this.query.trim().toLowerCase();
    this.filtered = this.demonstrations.filter(
      (item) =>
        item.title.toLowerCase().includes(normalized) ||
        item.preview.toLowerCase().includes(normalized)
    );
    this.selected = null;
  }

  showDetail(item: Demonstration) {
    this.selected = item;
  }
}
