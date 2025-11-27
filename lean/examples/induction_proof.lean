-- Mathematical induction examples

theorem zeroAddNat (n : Nat) : 0 + n = n := by
  induction n with
  | zero => rfl
  | succ n ih => rw [Nat.add_succ, ih]

theorem succAddNat (n m : Nat) : Nat.succ n + m = Nat.succ (n + m) := by
  induction m with
  | zero => rfl
  | succ m ih => rw [Nat.add_succ, Nat.add_succ, ih]

theorem addAssociative (a b c : Nat) : a + b + c = a + (b + c) := by
  induction c with
  | zero => rfl
  | succ c ih => rw [Nat.add_succ, Nat.add_succ, Nat.add_succ, ih]

theorem listLengthMap (f : α → β) (xs : List α) :
  (xs.map f).length = xs.length := by
  induction xs with
  | nil => rfl
  | cons x xs ih => simp [ih]

theorem listReverseLength (xs : List α) : xs.reverse.length = xs.length := by
  induction xs with
  | nil => rfl
  | cons x xs ih => simp [ih]
