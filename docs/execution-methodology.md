# Execution Methodology — CoProof Application Flow

This document describes how the CoProof platform works at runtime: the sequence of operations from user authentication through project creation, collaborative node decomposition, formal verification, computation, and merge.


## 1. Authentication

Every interaction begins with GitHub OAuth 2.0. The user is redirected to GitHub, grants the required scopes (repo, read:user, user:email), and is returned to the platform with a short-lived access token. The backend exchanges this for a stored GitHub token tied to the user's account in PostgreSQL, and issues a JWT pair (access + refresh) for subsequent API calls. The GitHub token is refreshed automatically before any operation that touches the remote repository.


## 2. Project Creation

A project is created by submitting a name, a goal statement written in natural language or Lean syntax, and optional contextual imports and definitions. Before any GitHub repository is created, the backend pre-compiles the provided goal context (Definitions + GoalDef + root theorem) through the Lean verification service to fail fast on invalid input. If that passes, the backend creates a private or public GitHub repository under the user's account, pushes three seed files (Definitions.lean, root/main.lean, root/main.tex), and persists the project metadata and a single root node in PostgreSQL. The root node starts in the sorry state, meaning its proof is acknowledged but not yet provided.


## 3. Proof Graph: the DAG

Each project is represented internally as a directed acyclic graph (DAG) of nodes. Every node corresponds to one .lean file in the GitHub repository. The root node holds the top-level theorem. The tree structure expresses human-readable decomposition (parent → children); the DAG structure expressed through Lean import statements expresses the dependency order required for compilation. PostgreSQL stores node metadata and states; GitHub stores the actual .lean and .tex file content. The frontend renders this graph and lets users navigate, inspect, and act on individual nodes.


## 4. Node Split

When a proof obligation is too large to solve directly, the user submits a split: a Lean snippet that replaces the current node's sorry with a structured proof referencing new child lemmas, each marked with sorry themselves. The backend fetches every .lean file in the repository from GitHub, builds the full import tree in memory, assembles the combined verification payload, and dispatches it synchronously to the Lean worker via the lean_queue Celery task. If Lean returns errors the operation stops and the errors are returned to the client. If the snippet compiles, the backend creates a feature branch on GitHub, commits the updated parent file and all new child .lean and .tex files, and opens a pull request targeting the project's default branch. Each new child node is represented in the PR body and, once the PR is merged, the webhook triggers reindexation that creates the corresponding Node records in PostgreSQL with state sorry. The parent's state is recomputed based on the states of its children and propagated upward through the graph.


## 5. Node Solve

When a user has a complete proof for a leaf node, they submit it via the solve endpoint. The flow is identical to a split in terms of verification: the backend fetches the full repository file map, resolves the import tree for that node, builds a unified compilation payload, and sends it to the Lean worker. If compilation succeeds, the backend checks whether the submitted code is materially different from what is already on the default branch. If there is no diff, the node state is updated directly in PostgreSQL without creating a branch. If there is a diff, a feature branch is created, the solved file is committed, and a pull request is opened. Merging that PR (via the platform's merge endpoint) marks the node as validated and propagates the validated state upward through all ancestors whose children are now fully validated.


## 6. Computation Nodes

Some theorems require empirical or numerical evidence rather than a pure symbolic proof. For these, a computation node can be created as a child of a proof node. The backend extracts the parent theorem's Lean signature, generates a child .lean stub (using an axiom as placeholder) and a Python program template, injects an import and usage of the child axiom into the parent's main.lean, verifies that the parent + child axiom compile together, and opens a PR with all generated files. Once merged and indexed, the user runs the computation node by submitting a Python payload (source code + entrypoint + input data) through the compute endpoint. The backend dispatches this to the computation_queue Celery worker, which executes the user's Python code in a sandboxed subprocess with an isolated scope. The worker returns a structured result containing an evidence value, a boolean sufficient flag, and optional records. If the computation completes and marks evidence as sufficient, the backend replaces the axiom placeholder in the child .lean with a concrete Lean definition embedding the evidence, re-verifies this updated file through the Lean worker, and then opens a PR with the finalized artifact bundle. If the evidence is insufficient, the result is persisted in the node's metadata but no PR is created.


## 7. Collaboration

Multiple users can be added to a project as contributors. Each contributor operates on their own feature branches; no one pushes directly to the default branch. The pull request workflow is mediated entirely through the platform: the backend opens, tracks, and merges PRs via the GitHub REST API on behalf of the authenticated user. The merge endpoint verifies that the PR was actually merged (GitHub may return HTTP 200 with merged: false) before applying any state updates to the database. Concurrent access to the same repository is protected by Redis-based distributed locks (Redlock), ensuring that two simultaneous operations on the same project cannot corrupt the repository.


## 8. GitHub Webhook and Reindexation

The platform registers a GitHub push webhook on each project repository. When a pull request is merged and a push event fires on the default branch, the webhook endpoint receives the payload, identifies the affected project, and enqueues an asynchronous reindexation task on the git_engine_queue. The Celery worker fetches the updated file tree from GitHub, parses all .lean files to extract theorem and lemma declarations and their import dependencies, and synchronizes the Node table in PostgreSQL to reflect the current state of the repository. This keeps the platform's operational index consistent with GitHub as the authoritative content store.


## 9. Lean Verification Worker

The Lean worker runs in a dedicated Ubuntu 22.04 container with Lean 4 installed via elan and Mathlib4 pre-compiled at a pinned commit. It consumes tasks from lean_queue. For each task it receives a single concatenated Lean snippet, writes it to a temporary file, invokes the Lean executable, and parses the output to extract return code, error messages, warning positions, and detected theorem/lemma names. The response includes a valid boolean, structured error and message lists, and processing time. The 45-second timeout on the backend client side prevents indefinitely blocking API requests; the Lean worker itself has no internal timeout beyond the process execution time.


## 10. End-to-End Flow Summary

A complete proof lifecycle proceeds as follows. A user authenticates via GitHub OAuth and creates a project with a goal statement; the system pre-compiles the goal and scaffolds a GitHub repository with initial Lean files. The user sees the root node in sorry state in the workspace DAG view. They split the root into sub-goals, which are verified by Lean and committed to a feature branch as a PR; merging the PR creates child nodes in the platform. Contributors work on individual leaf nodes, each collaborating through isolated feature branches and PRs. Leaf nodes that require numerical evidence receive a computation child, which runs user-provided Python code to produce the evidence, embeds it in a Lean axiom, turns it into a concrete definition once sufficient, and commits the artifact. As leaf nodes are solved and their PRs merged, validated states propagate upward through the DAG. The project reaches a fully validated state when every node in the graph is validated, meaning the root theorem is completely proven in Lean with all dependencies satisfied.
