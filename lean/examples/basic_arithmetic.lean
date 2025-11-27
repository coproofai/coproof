-- Basic arithmetic proofs demonstrating fundamental properties

theorem additionCommutative (a b : Nat) : a + b = b + a := by
  rw [Nat.add_comm]

theorem additionAssociative (a b c : Nat) : (a + b) + c = a + (b + c) := by
  rw [Nat.add_assoc]

theorem multiplicationCommutative (a b : Nat) : a * b = b * a := by
  rw [Nat.mul_comm]

theorem zeroIsAdditiveIdentity (n : Nat) : n + 0 = n := by
  rw [Nat.add_zero]

theorem oneIsMultiplicativeIdentity (n : Nat) : n * 1 = n := by
  rw [Nat.mul_one]

theorem distributiveLaw (a b c : Nat) : a * (b + c) = a * b + a * c := by
  rw [Nat.mul_add]
