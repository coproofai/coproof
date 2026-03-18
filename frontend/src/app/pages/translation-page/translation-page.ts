import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-translation-page',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './translation-page.html',
  styleUrl: './translation-page.css'
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
