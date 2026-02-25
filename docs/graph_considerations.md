# Collaborative DAG + Tree Architecture — Implementation Plan (Updated)

## 1. Data Layer Restructuring (Database)

We need a clear separation between **canonical nodes** (verified knowledge) and **work-in-progress nodes** (proposed, draft, or collaborative contributions).

**1.1 Canonical Graph (GraphNode table)**

* Holds **verified nodes only**.
* Fields: `id`, `project_id`, `title`, `node_type`, `parent_id`, `prerequisites`, `commit_hash`, `file_path`, `latex_file_path`.
* Status enum simplified to: `verified`, `error` (for historical provenance).
* Goal: **main.lean is generated strictly from canonical nodes**.
* Relationships:

  * `parent_id` → Tree structure
  * `prerequisites` → DAG structure

**1.2 Proposed Node Table (ProposedNode table)**

* Stores **draft nodes for author or collaborators**.

* Fields:

  * `id`, `project_id`, `user_id`, `title`, `node_type`
  * `lean_file_path`, `latex_file_path`
  * `branch_name` (feature branch simulated for GitHub)
  * `proposed_parent_title`, `proposed_dependencies` (JSONB)
  * `status`: `draft`, `verifying`, `valid`, `invalid`, `submitted`, `merged`, `rejected`
  * `verification_log`, optional `pr_id` for internal tracking

* Purpose: **store nodes before merging into canonical DAG**.

* Proposed nodes can represent partial proofs (`sorry`) or unverified contributions.

---

## 2. DAG & Tree Isolation from Files

**Key principle:** The **graph structure exists independently of Lean/LaTeX files**.

* Each node’s Lean/LaTeX file is **modular**.
* Ephemeral DAGs are **built in-memory** for verification and compilation.
* Tree structure (parent-child) is for **human-readable decomposition**.
* DAG (prerequisites) ensures **dependency order for Lean compilation**.
* Verified nodes become canonical → main.lean regenerated.
* Unverified nodes remain `sorry` placeholders.
* **UI reflects status:** verified, draft, unverified, hidden → collaborators only see nodes approved/exposed by author.
* Author controls **visibility of incomplete nodes**; collaborators may propose children under canonical nodes or exposed nodes, pending verification.

---

## 3. GitHub Integration & Authentication (Detailed)

Since users **must never interact directly with GitHub**, we use **GitHub Apps** for repository and branch management.

### 3.1 GitHub Apps vs OAuth

* **OAuth** continues for **identity only** (signup/login).
* **GitHub App** handles:

  * Repository creation
  * Branch management (feature branches per proposed node)
  * Pull request simulation (internal to the app)
  * File creation, updates, and deletion
  * Permissions scoped to selected repos

### 3.2 GitHub App Installation Flow

1. User signs up/logs in via OAuth → authenticated identity in the system.
2. User is prompted to **install GitHub App**.

   * If the user does not grant access to all repositories, the system must check:

     * `repos` scope → includes the project repository
     * Otherwise, **warn user** and restrict functionality
3. Upon installation:

   * App creates **canonical repo** for project under the owner’s account.
   * Sets up **main branch with main.lean skeleton** (Goal only, no solution).
   * Author may later create **feature branches** for nodes (`feat/user-x/node-y`)

### 3.3 Repo Ownership and Authority

* The **original author of the project** need not be an organization; a **personal account is sufficient**.
* All canonical nodes, main.lean, and verified contributions reside in this repo.
* Proposed nodes (drafts) may live in **user-specific forks or branches**, still under app control, until merged by author/maintainer.
* GitHub App ensures **backend-only operations**: no user GitHub knowledge required.

### 3.4 File Operations

* Creation of `.lean` and `.latex` files for proposed nodes is done **automatically by the app** in the user’s fork/branch.
* Updates to main.lean happen **only after verification and canonical promotion**, preserving DAG order.
* **Ephemeral DAG** is built in memory for verification:

  1. Fetch canonical nodes from DB → build DAG + tree
  2. Fetch proposed nodes (from user’s branch/fork) → append temporarily to DAG
  3. Resolve dependencies and parent relationships → topological sort
  4. Generate **temporary main.lean** for Lean compilation
  5. Verification logs captured; status updated in ProposedNode table

**Key Point:** No direct user GitHub interaction; GitHub App executes all branch, file, and commit operations programmatically.


## 4. Proposal / Draft Node Pipeline

All contributions — from the author or collaborators — follow the **same verification workflow** before becoming canonical.

### 4.1 Draft Node Creation

1. **User submits a draft node** (author or collaborator):

 
   * Provides `.lean` and `.latex` files
   * Defines **title, node type, parent, dependencies**
   * System creates **ProposedNode** in DB with status `draft`
   * GitHub App automatically:

     * Creates a **feature branch** for the proposed node, files saved in users own GH account (e.g., `feat/user-x/node-y`)
     * Commits `.lean` and `.latex` files to that branch

2. **UI behavior:**

   * Draft nodes **not visible** in canonical tree by default
   * Author can optionally mark them **exposed to collaborators**
   * Nodes that havent passed "local" DAG verification either verified or trusted ( if uses `sorry`) are not exposed to the author to mark as "expose to collaborators" 

---

### 4.2 Verification Pipeline

Before merging, each proposed node is **verified in an ephemeral DAG**:

1. **Build Ephemeral DAG:**

   * Fetch **canonical GraphNodes** → in-memory DAG
   * Fetch **ProposedNode(s)** (current submission or batch) → append to ephemeral DAG
   * Resolve **dependencies (prerequisites)** and **parent-child relationships**
   * Detect **cycles** → fail verification if present

2. **Generate Temporary main.lean:**

   * Topologically sort ephemeral DAG
   * Include Lean code for verified nodes
   * Insert `sorry` for unverified dependencies
   * Maintain proper parent/child hierarchy in code blocks

3. **Run Lean Compiler:**

   * Compile temporary main.lean
   * Record success/failure, errors, and warnings in `verification_log`
   * Update ProposedNode status: `valid`, `invalid`, or keep `draft` if partial

4. **Feedback to UI:**

   * Author/collaborators see verification results of proposed nodes only if it was valid or trusted (e.i. relied on `sorry`)
   * Nodes that fail verification cannot be merged into canonical graph

---

## 5. Merge and Canonical Promotion

Once verification passes, a **ProposedNode can be merged** into the canonical DAG.

### 5.1 Merge Process

1. **Author/maintainer triggers merge**:

   * Backend verifies ephemeral DAG again to ensure no changes occurred since last verification

2. **Canonical DAG update:**

   * Create new **GraphNode** from ProposedNode
   * Resolve **parent_id** and **prerequisites** → convert titles to canonical UUIDs
   * Store Lean/LaTeX paths and commit hash

3. **main.lean regeneration:**

   * Fetch all canonical nodes → rebuild DAG in memory
   * Topological sort ensures **all dependencies satisfied**
   * Concatenate Lean code in topological order
   * Insert `sorry` placeholders for any exposed but unverified children
   * Commit new main.lean via GitHub App to canonical repo

4. **Clean up ProposedNode:**

   * Delete or archive draft node
   * Delete feature branch via GitHub App

5. **UI update:**

   * DAG/tree now shows canonical node as verified
   * Exposed but unverified children (if any) appear with status `sorry`
   * Collaborators can propose child nodes under verified or exposed nodes

---

### 5.2 Verification on Merge

* **Critical:** Even if a ProposedNode passed ephemeral verification before, **rebuild the ephemeral DAG at merge time**.
* Reasons:

  1. Other nodes may have merged in the meantime, potentially creating new cycles or breaking dependencies
  2. Ensures **main.lean remains consistent**
* Merge only proceeds if the ephemeral DAG passes verification

---

## 6. DAG and Tree UI Representation

**Key principles:**

* **Canonical nodes:** verified → main.lean code included → shown in UI tree
* **Proposed/exposed nodes:** draft or partial proof → shown with `sorry` or “unverified” status
* **Collaborator nodes:** can be proposed anywhere under:

  * Root (problem statement)
  * Any canonical node
  * Author-approved proposed node
* **Topological ordering** is used for Lean compilation and optional for tree rendering
* **Author controls visibility** of incomplete nodes to avoid clutter or confusion

**Example: Root + L1/L2 scenario**

```
Root (Goal)
|
+-- L1: verified (main.lean contains Lean code)
|
+-- L2: draft/unverified (main.lean contains sorry)
    |
    +-- Collaborator Node A: draft/unverified
```

* L1 is canonical → visible and verified
* L2 is exposed → visible, `sorry` placeholder in main.lean
* Collaborator Node A can extend L2, pending verification

---

## 7. Lean File Generation and Integration

**Ephemeral DAG ensures correctness:**

1. Each node’s `.lean` file is modular
2. Temporary main.lean is generated **from topological sort** of DAG
3. Verified nodes → full Lean code
4. Unverified nodes → `sorry` placeholder
5. Lean compiler validates **entire concatenated file**

**No LLM or heuristic merging is needed**, only:

* DAG topological sort
* Concatenation of `.lean` files respecting dependencies
* Optional insertion of metadata/comments

---

## 8. Summary of Workflow

1. Author creates project → root node (problem statement) in plain text or LaTeX
2. Author may propose initial decomposition nodes (lemmas) → go through same verification pipeline
3. Collaborators propose nodes under canonical or exposed nodes → ephemeral DAG + Lean compilation ensures correctness
4. Verified nodes are merged → canonical DAG updated → main.lean regenerated
5. Author controls which unverified nodes are **exposed** in tree UI for collaboration (e.i. author should be able to fetch all verified or 'sorry trusted' proposed nodes that are childern of a certain node ) and either merge or expose. 
6. All Git operations handled via GitHub App; user does not interact with GitHub directly

---

At this stage, we have a **robust architecture**:

* Clear **canonical vs proposed separation**
* **Ephemeral DAG verification** ensures correctness and prevents broken merges
* **Topological main.lean generation** guarantees Lean code validity
* **UI tree** reflects verification status and author-controlled exposure
* **GitHub App** abstracts all repository and branch operations

