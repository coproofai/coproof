import { Component } from '@angular/core';
import { NgClass } from '@angular/common';

@Component({
  selector: 'app-validation-page',
  standalone: true,
  imports: [NgClass],
  templateUrl: './validation-page.html',
  styleUrl: './validation-page.css'
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
