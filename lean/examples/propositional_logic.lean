-- Propositional logic proofs

theorem modusPonens (P Q : Prop) (hpq : P → Q) (hp : P) : Q := by
  exact hpq hp

theorem andCommutative (P Q : Prop) : P ∧ Q → Q ∧ P := by
  intro h
  exact ⟨h.right, h.left⟩

theorem orCommutative (P Q : Prop) : P ∨ Q → Q ∨ P := by
  intro h
  cases h with
  | inl hp => exact Or.inr hp
  | inr hq => exact Or.inl hq

theorem doubleNegationIntro (P : Prop) : P → ¬¬P := by
  intro hp hnp
  exact hnp hp

theorem deMorganNotAnd (P Q : Prop) : ¬(P ∧ Q) → ¬P ∨ ¬Q := by
  intro h
  by_cases hp : P
  · by_cases hq : Q
    · exact absurd ⟨hp, hq⟩ h
    · exact Or.inr hq
  · exact Or.inl hp

theorem implicationTransitive (P Q R : Prop) :
  (P → Q) → (Q → R) → (P → R) := by
  intro hpq hqr hp
  exact hqr (hpq hp)
