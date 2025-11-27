-- Function composition and properties

def compose (f : β → γ) (g : α → β) : α → γ := fun x => f (g x)

theorem composeAssociative (f : γ → δ) (g : β → γ) (h : α → β) :
  compose f (compose g h) = compose (compose f g) h := by
  rfl

def identity (x : α) : α := x

theorem leftIdentityCompose (f : α → β) : compose f identity = f := by
  rfl

theorem rightIdentityCompose (f : α → β) : compose identity f = f := by
  rfl

def isInjective (f : α → β) : Prop :=
  ∀ x y, f x = f y → x = y

def isSurjective (f : α → β) : Prop :=
  ∀ y, ∃ x, f x = y

theorem injectiveComposition (f : β → γ) (g : α → β)
  (hf : isInjective f) (hg : isInjective g) :
  isInjective (compose f g) := by
  intro x y h
  apply hg
  apply hf
  exact h
