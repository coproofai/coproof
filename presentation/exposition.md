# CoProof — Exposition Plan

---

## 1. Opening Anecdote — Sir Michael Atiyah and the Riemann Hypothesis

**Hook:** Start with the name and the claim.

> *"In September 2018, one of the greatest living mathematicians — Sir Michael Atiyah,
> Fields Medal and Abel Prize laureate — announced a proof of the Riemann Hypothesis,
> one of the seven Millennium Prize Problems, unsolved for 160 years."*

- The announcement drew immediate worldwide attention.
- Within hours, mathematicians across the globe began reading, sharing, and arguing about
  whether the 5-page sketch was valid.
- Atiyah passed away in January 2019. **Five months later**, after extensive community
  review, the consensus was clear: **the proof contained a fatal logical gap**.

**Transition:** The tragedy is not just that it was wrong — it is *how hard it was to agree
that it was wrong*, and *how long it took*.

---

## 2. The Problem — Async Collaboration on Logical Correctness

**Core tension:** Mathematical verification is fundamentally a social process today.

- Peer review is slow, asynchronous, and based on **trust in the reader's judgment**.
- There is no shared, machine-checkable standard for "this step logically follows from
  the previous one."
- For a distributed team of collaborators, agreeing on the correctness of a single
  logical inference can take weeks of email threads, annotations, and counter-examples.
- **No tool exists** that acts as a neutral arbiter: *"this argument is valid"* or
  *"this step does not follow."*

**Key question posed to the audience:**
> *What if there was a way to make logical correctness as unambiguous as a compiler error?*

---

## 3. What Is Logical Correctness? — From Math to Pure Logic

**Goal:** Demystify "formal proof" by showing it is just rigorous logic, not magic.

### Step A — Math example
Present a familiar theorem (e.g. sum of first n integers):

> **Theorem:** If $n \geq 1$, then $\sum_{i=1}^n i = \frac{n(n+1)}{2}$.
>
> *Proof by induction. Base case: n=1 → 1 = 1. ✓
> Inductive step: assume true for k, show for k+1 ...*

### Step B — Strip the math, keep the logic
Show the same argument as pure logical structure:

```
Premise P:   "Property holds for n = 1"                    (base case)
Premise Q:   "If property holds for k, it holds for k+1"   (inductive step)
Conclusion:  "Property holds for all n ≥ 1"                (by induction)
```

- This is just: **P, P→Q ⊢ Q** (modus ponens, applied inductively).
- Every mathematical proof, no matter how complex, reduces to a chain of such inferences:
  implication, conjunction, universal quantification, contradiction.
- **Logical correctness = every step follows from admitted rules.**

---

## 4. The Complexity Problem — A Real Proof

**Goal:** Show that even "simple" theorems generate enormous chains of inference.

Present a non-trivial example (e.g. Euclid's infinitude of primes, or the irrationality
of √2) and walk through how many individual logical steps it actually contains when
fully expanded.

**Key point:**
- A human can skip steps because of shared intuition.
- A machine cannot — and **that is a feature, not a bug**.
- For async collaboration, skipped steps are exactly where disagreements live.
- Checking a full proof manually across a distributed team is **O(reviewers × steps)**
  with no shared ground truth.

---

## 5. DAG Structure of Proofs — The Hamburger Analogy

**Insight:** Large proofs are not linear — they are **directed acyclic graphs**.

### The Hamburger
Making a hamburger can be broken into independent parallel tasks:
- Toast the bun ← independent
- Grill the patty ← independent
- Slice tomatoes ← independent
- Assemble ← depends on all of the above

You can distribute independent steps to different people simultaneously.
The final assembly only happens once all dependencies are done.

### Proofs work the same way
- The **root theorem** depends on several **lemmas**.
- Each lemma may depend on sub-lemmas.
- Sub-lemmas that share no common premises can be proved **in parallel by different people**.
- The proof is complete when every leaf node is validated and the state propagates up to
  the root.

**Visual:** Draw a simple DAG on the board (3 levels, 5–6 nodes).

---

## 6. Lean 4 — The Solution That Is Too Hard to Use

**Lean 4** is a formal proof assistant that acts as exactly that neutral arbiter:
- You write a proof in its language.
- It either **compiles** (logically valid) or **does not** (error with exact location).
- Used to verify Mathlib4 — tens of thousands of university-level theorems.

**The problem:**
- Lean 4 requires mastering dependent type theory and tactic-mode scripting.
- Most mathematicians are not software engineers.
- There is no collaboration infrastructure — it is a single-user compiler, not a platform.
- No way to distribute sub-lemmas to teammates, track progress, or manage contributions.

> *Lean solves the correctness problem. It does not solve the collaboration problem.*

---

## 7. Introducing CoProof

**CoProof** is a web platform that wraps Lean 4 inside a collaborative workflow:

| What you get | How |
|---|---|
| Formal verification | Every node submitted is compiled by a Lean 4 worker |
| Collaboration | GitHub as source of truth; Pull Requests as the contribution mechanism |
| Accessibility | Write in natural language — NL2FL translates it to Lean automatically |
| Distribution | Assign sub-lemmas to teammates; work in parallel |
| HPC | Computationally intensive nodes run on a real MPI cluster |

**One sentence:** CoProof is the platform that would have let the mathematical community
verify — or falsify — Atiyah's proof in hours, not months.

---

## 8. The Three Core Operations — From Hamburger to Factorions

Replace the hamburger with the **Factorion** example (a real theorem proved in CoProof):

> **Theorem:** The only factorions in base 10 are 1, 2, 145, and 40585.

Show the DAG:
- Root: `IsFactorion n ↔ n ∈ {1, 2, 145, 40585}`
- Branch 1 (logical): `factorion_upper_bound` → `sum_fact_digits_bound`, `n_gt_sum_bound`
- Branch 2 (computational): `factorion_bounded_exhaustion` → HPC verification nodes

**The three operations:**

| Operation | What it does |
|---|---|
| **Create** | Define the root theorem and its goal in Lean; pre-compiled before saving |
| **Split** | Divide a node into child sub-lemmas; author decides the decomposition |
| **Solve** | A collaborator writes the proof (Lean or natural language); triggers verification |

---

## 9. Walkthrough — Live Demo

Walk through the three operations on a live instance of CoProof:

1. **Create project** — enter the Factorion theorem; watch the pre-compilation gate run.
2. **Split root** — create `factorion_upper_bound` and `factorion_bounded_exhaustion` as children.
3. **Solve a node** — type a natural language description of `sum_fact_digits_bound`;
   watch NL2FL generate Lean code; watch the Lean worker verify it.
4. **Merge** — the verified node opens a PR on GitHub automatically; author merges;
   state propagates upward.
5. **Computation node** — show the HPC node dispatched to the Raspberry Pi cluster.

**Closing line:**
> *Atiyah's proof had a gap nobody could formally pin down for months.
> With CoProof, that gap would have been a compiler error on day one.*
