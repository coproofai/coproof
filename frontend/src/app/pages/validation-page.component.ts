import { Component } from '@angular/core';
import { NgClass } from '@angular/common';

@Component({
  selector: 'app-validation-page',
  standalone: true,
  imports: [NgClass],
  template: `
    <h1>Validar Demostración</h1>
    <div class="control-panel">
      <button class="upload-button" (click)="simulateValidation()">Subir Archivo de Validación</button>
      <div class="validation-result" [ngClass]="validated ? 'result-validated' : 'result-pending'">
        Resultado: {{ validated ? 'Validación Exitosa' : 'Pendiente de Subida/Validación' }}
      </div>
    </div>

    <div class="columns-container">
      <div class="column">
        <div class="column-header">1. Demostración Original (Usuario)</div>
        <pre>{{ originalContent }}</pre>
      </div>

      <div class="column">
        <div class="column-header">2. Versión en Lean (Generada)</div>
        <pre>{{ leanContent }}</pre>
      </div>

      <div class="column">
        <div class="column-header">3. Versión en Lenguaje Natural</div>
        <pre>{{ naturalContent }}</pre>
      </div>
    </div>
  `,
  styles: [`
    h1 { margin: 0 0 20px 0; }
    .control-panel {
      background: #fff;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
      margin-bottom: 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      border: 1px solid #eee;
      flex-wrap: wrap;
    }
    .upload-button {
      padding: 10px 20px;
      background: #333;
      color: #fff;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-weight: 700;
    }
    .validation-result { font-size: 1.1em; font-weight: 700; padding: 10px; border-radius: 4px; }
    .result-pending { background: #ffc; color: #880; border: 1px solid #cc0; }
    .result-validated { background: #e6ffe6; color: #080; border: 1px solid #0c0; }
    .columns-container { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
    .column {
      background: #fff;
      border: 1px solid #eee;
      border-radius: 8px;
      padding: 14px;
      min-height: 340px;
    }
    .column-header { font-weight: 700; color: #555; margin-bottom: 10px; border-bottom: 1px solid #ddd; padding-bottom: 5px; }
    pre {
      white-space: pre-wrap;
      margin: 0;
      background: #f7f7f7;
      border: 1px solid #eee;
      border-radius: 4px;
      padding: 10px;
      font-size: 0.9rem;
      height: calc(100% - 36px);
    }
    @media (max-width: 1080px) {
      .columns-container { grid-template-columns: 1fr; }
    }
  `]
})
export class ValidationPageComponent {
  validated = false;
  originalContent = '// Contenido subido (código, texto, PDF)\n// Ej: "La suma de dos números pares es par."';
  leanContent = `-- Código Lean generado
theorem sum_even_is_even (h1 : even x) (h2 : even y) : even (x + y) :=
begin
  -- Demostración en Lean
end`;
  naturalContent = `Demostración:
1. Asumimos que x y y son números pares.
2. Por definición, x=2k y y=2m para enteros k, m.
3. Entonces x+y = 2k + 2m = 2(k+m).
4. Como k+m es un entero, x+y es par.`;

  simulateValidation() {
    this.validated = true;
  }
}
