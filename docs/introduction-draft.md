# Introduction Draft — CoProof Manuscript

> **Purpose:** Draft text for `\section{Introduction}` in `coproof-manuscript.tex`.  
> Follows the four-part structure: Background → Gap → Objective → Structure preview.  
> Language registers align with IEEE conference style.

---

## Draft

The rigorous verification of mathematical knowledge has long been
recognised as a cornerstone of scientific reliability. Over the past two
decades, interactive theorem provers (ITPs) have matured from
specialised research tools into viable environments for formalising
non-trivial mathematics. Systems such as Isabelle/HOL \[CITE\],
Coq/Rocq \[CITE\], and, more recently, Lean~4 \[ref:lean4\] and the
emerging Gauss assistant \[CITE\] have demonstrated that large bodies
of undergraduate and graduate-level mathematics can be mechanically
verified. The Lean~4 ecosystem has been particularly active: the
community-maintained Mathlib4 library \[ref:mathlib4\] already contains
tens of thousands of formalised theorems spanning algebra, analysis,
topology, and number theory, and there has been growing interest in
leveraging these foundations to certify novel mathematical results in a
machine-checkable form.

Despite this progress, several structural barriers continue to limit the
practical adoption of formal proof development in the broader mathematical
community. First, the learning curve imposed by languages such as Lean~4
remains steep for researchers whose training is in mathematics rather than
computer science. Mastering dependent type theory, tactic-mode proof
scripts, and the idiosyncrasies of a compiled functional language
represents a significant investment that most practising mathematicians
are not positioned to make. As a result, formalisation efforts remain
concentrated among a small community of specialists, while the
overwhelming majority of published mathematical results exist only in
informal natural-language form. Second, the tooling landscape for
collaborative proof development is fragmented. Existing ITP workflows are
predominantly single-user or rely on general-purpose version control with
no domain-aware collaboration primitives. There is currently no dedicated
platform that provides structured, multi-contributor proof decomposition
with formal verification as a first-class gating mechanism, limiting the
degree to which geographically distributed teams of mathematicians can
co-author a large formalisation project with the kind of accountability
and provenance tracking that the task demands.

A third challenge has emerged with the rapid proliferation of large
language models (LLMs) in scientific research. Recently, there has been
growing interest in AI-assisted theorem proving, with systems such as
LeanDojo \[ref:leandojo\] and LeanCopilot \[CITE\] demonstrating that
retrieval-augmented and neural-guided search can accelerate proof
exploration in Lean~4. However, few studies have addressed a critical
limitation of current LLM-based approaches: these models produce
natural-language or tactic-style suggestions that cannot be
deterministically verified without invoking the underlying proof
checker. The well-documented tendency of LLMs to hallucinate in
mathematical contexts---generating plausible-looking but incorrect
derivations---means that unverified model output can introduce
soundness errors that are difficult to detect by inspection. Without a
tight coupling between AI suggestion and a formal verification oracle,
the productivity gain from LLM assistance comes at the cost of
reliability.

A fourth, less-discussed barrier concerns proofs that are inherently
computational in nature. A growing number of modern mathematical results
depend on exhaustive case analysis or large-scale numerical verification,
from the original computer-assisted proof of the four-color theorem to
recent results in combinatorics and number theory. Research institutions
such as CIMAT maintain dedicated high-performance computing (HPC)
clusters with MPI-capable nodes specifically for this kind of scientific
computation. However, the majority of mathematicians who could benefit
from these resources lack the systems-programming knowledge required to
write parallel, distributed code that leverages them. Compounding this,
mainstream ITPs are not well-suited to hybrid proofs that combine
symbolic deduction with large-scale numerical evidence: Lean~4, for
instance, has no native mechanism for embedding external computational
witnesses as first-class proof artefacts, leaving the gap between
formal proof and computational verification largely unaddressed.

This paper aims to develop a scalable, modular, and ready-to-deploy
collaborative platform---CoProof---that addresses all four of these
challenges in a unified system. Concretely, the contributions of this
work are as follows:

1. **Accessible formal proof authoring.** A natural-language-to-Lean
   translation pipeline, built on a retrieval-and-retry loop that feeds
   Lean compiler feedback back to a configurable LLM, lowers the entry
   barrier for mathematicians unfamiliar with Lean~4 syntax. All
   AI-generated suggestions are deterministically verified by the Lean
   worker before reaching the user, providing a hard guarantee against
   unverified hallucinations propagating into the proof record.

2. **Collaborative DAG-based proof development.** A proof graph
   model---a directed acyclic graph (DAG) in which each node maps to
   a `.lean` file in a GitHub repository---provides structured
   decomposition of large proof obligations into independently assignable
   sub-goals. GitHub pull requests serve as the collaboration primitive,
   giving teams traceable, reviewable, version-controlled contributions
   with formal verification as a merge gate.

3. **Hybrid formal/computational proof nodes.** A computation node
   mechanism allows users to submit Python programs that produce
   numerical evidence; the platform executes these in a sandboxed
   subprocess, embeds sufficient evidence as a concrete Lean definition,
   and verifies the result through the Lean worker. This bridges the gap
   between symbolic proof and HPC-scale computation, enabling
   mathematicians to leverage cluster resources through a high-level
   interface without writing MPI or Slurm code directly.

4. **End-to-end platform delivered as a reproducible stack.** All
   services---backend API, Lean verification worker, NL-to-Lean
   worker, AI suggestion microservice, computation worker, and Angular
   frontend---are containerised and orchestrated with Docker Compose,
   deployable in a single command on any Docker-capable host including
   the described Raspberry Pi HPC cluster.

The remainder of this paper is organised as follows.
Section~\ref{sec:related} surveys related work on interactive theorem
provers, AI-assisted proof systems, and collaborative formalisation
platforms. Section~\ref{sec:materials-methods} describes the hardware
and software stack and the development and execution methodologies.
Section~\ref{sec:results} presents the quantitative results of the Lean
verification benchmark and the full feature delivery record.
Section~\ref{sec:discussion} interprets those results, characterises the
current limitations of the system, and proposes a prioritised roadmap
for future work. Section~\ref{sec:conclusion} summarises the principal
contributions.

---

## References to add to the .bib / `thebibliography`

The following entries are referenced in the draft above and are not yet
present in `coproof-manuscript.tex`:

| Tag | Work | Notes |
|---|---|---|
| `ref:leandojo` | Yang et al., "LeanDojo: Theorem Proving with Retrieval-Augmented Language Models," NeurIPS 2023 | Already in manuscript |
| `ref:lean4` | de Moura & Ullrich, CADE-28, 2021 | Already in manuscript |
| `ref:mathlib4` | The Mathlib Community, 2024 | Already in manuscript |
| `ref:leancopilot` | Song et al., "LeanCopilot: Large Language Models as Copilots for Theorem Proving in Lean 4," NeurIPS 2024 | **Add** |
| `ref:coq` | The Coq Development Team, "The Coq Proof Assistant," Zenodo, 2024 | **Add** |
| `ref:isabelle` | T. Nipkow, L. C. Paulson, M. Wenzel, *Isabelle/HOL: A Proof Assistant for Higher-Order Logic*, Springer, 2002 | **Add** |
| `ref:gauss` | Verify correct citation for the Gauss proof assistant | **Confirm and add** |
| `ref:fourcolor` | G. Gonthier, "Formal Proof — The Four-Color Theorem," *Notices of the AMS*, 2008 | **Add** (supports computational proofs motivation) |

---

## Notes for revision

- The LeanCopilot reference needs a confirmed venue/year before submission; double-check whether the NeurIPS 2024 citation is the correct one.
- "Gauss" as a proof assistant should be confirmed with a citable source before the final manuscript; if no peer-reviewed citation is available, consider replacing with a more established recent system (e.g., Lean 4 itself post-v4.0, or Agda 2).
- The four-color theorem example in paragraph 4 is illustrative; if a more domain-relevant example from CIMAT's work is available it would strengthen the motivation.
- The contribution list can be condensed to 2–3 items if the IEEE page budget is tight.
