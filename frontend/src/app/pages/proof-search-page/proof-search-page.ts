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
  templateUrl: './proof-search-page.html',
  styleUrl: './proof-search-page.css'
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
