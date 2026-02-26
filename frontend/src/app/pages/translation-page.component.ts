import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-translation-page',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="max-wrap">
      <h1>Traducción a Formalismo Lean</h1>

      <div class="panel">
        <h2>Editor de Traducción</h2>
        <button class="btn-primary" (click)="simulateTranslation()" [disabled]="translating">
          {{ translating ? 'Traduciendo...' : 'Traducir a Lean' }}
        </button>
      </div>

      <div class="columns">
        <div>
          <h3>Lenguaje Natural (Entrada)</h3>
          <textarea
            [(ngModel)]="naturalText"
            class="text-area"
            placeholder="Escribe aquí el teorema o proposición que deseas formalizar en Lean."
          ></textarea>
        </div>

        <div>
          <h3>Formalismo Lean (Salida)</h3>
          <pre class="text-area output">{{ leanOutput }}</pre>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .max-wrap { max-width: 1320px; margin: 0 auto; }
    h1 { margin: 0 0 20px 0; }
    .panel {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border: 1px solid #e5e7eb;
      background: #fff;
      border-radius: 12px;
      padding: 14px;
      margin-bottom: 16px;
      gap: 10px;
      flex-wrap: wrap;
    }
    .panel h2 { margin: 0; font-size: 1.1rem; color: #555; }
    .btn-primary {
      background: #333;
      color: white;
      border: none;
      border-radius: 8px;
      padding: 10px 18px;
      font-weight: 700;
      cursor: pointer;
    }
    .btn-primary:disabled { opacity: 0.65; cursor: wait; }
    .columns { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .text-area {
      width: 100%;
      min-height: 460px;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      background: #fff;
      padding: 14px;
      font-size: 0.9rem;
      box-sizing: border-box;
      resize: vertical;
    }
    .output { margin: 0; white-space: pre-wrap; background: #f9fafb; }
    h3 { margin: 0 0 8px 0; color: #555; }
    @media (max-width: 980px) {
      .columns { grid-template-columns: 1fr; }
    }
  `]
})
export class TranslationPageComponent {
  naturalText =
    'Proposición: Demostrar que para todo número natural n, si n es mayor que 2, entonces n al cuadrado es mayor que 4.';
  leanOutput = '// Presiona "Traducir a Lean" para generar el código.';
  translating = false;

  simulateTranslation() {
    const text = this.naturalText.trim();
    if (!text) {
      this.leanOutput = '// Por favor, introduce texto en lenguaje natural para traducir.';
      return;
    }

    this.translating = true;
    this.leanOutput = '// Generando código formal...';

    setTimeout(() => {
      this.leanOutput = `import data.nat.prime
import tactic

theorem n_cuadrado_mayor_que_cuatro (n : ℕ) (hn : n > 2) : n^2 > 4 :=
begin
  exact nat.pow_le_pow_of_le_left (show 2 ≤ n, by linarith) (by norm_num : 2 > 0)
end`;
      this.translating = false;
    }, 1200);
  }
}
