# Locking & Concurrency Strategy
## Git Engine + Collaborative Editing Architecture

This document defines the locking patterns, fetch strategy, concurrency guarantees, and implementation requirements for two collaboration models:

- **Option A — Overleaf Model (Real-Time Collaborative Editing)**
- **Option B — PR / Branch Model (Feature Branch Isolation)**

---

# Global Design Principles

## 1. Separation of Concerns

We must strictly separate:

1. Real-time editing state
2. Git persistence layer
3. Repository mutation operations
4. Branch-level operations

Git is a persistence and versioning engine.
It is NOT a real-time collaboration engine.

---

# Lock Types

We define three lock scopes across the system:

| Lock Type        | Key Format                    | Scope              | Used For |
|------------------|------------------------------|--------------------|----------|
| Repo Lock       | `project_id`                  | Entire repository  | Clone, delete, corruption recovery |
| Branch Lock     | `project_id:branch_name`      | Single branch      | Commit, push, merge, rebase |
| Document Lock   | `project_id:document_id`      | Live document      | CRDT/OT mutation protection |

---

# FETCH STRATEGY (CRITICAL FOR BOTH OPTIONS)

## Required Refspec

Fetch MUST update remote tracking refs only:

```

+refs/heads/*:refs/remotes/origin/*

```

Never fetch into:

```

refs/heads/*

```

### Why?

Fetching into local branch refs will fail if:
- That branch is checked out in a worktree
- Multiple worktrees exist

Git will error:
```

fatal: refusing to fetch into branch 'refs/heads/main' checked out at ...

```

### Safe Fetch Rule

Fetch may run:
- Without branch lock (generally safe)
- Inside branch lock (safest)
- Never during repo deletion/reset

---

# OPTION A — OVERLEAF MODEL (REAL-TIME COLLABORATION)

## Overview

Users edit a shared `.latex` file in real time.

Git is used only for:
- Periodic snapshots
- Version history
- Persistence

Live edits do NOT directly write to Git.

---

## Architecture

```

Frontend (WebSocket / CRDT)
↓
Realtime State Store (Redis / Memory)
↓
Snapshot Service (Scheduled / Event-based)
↓
Git Engine (Celery)
↓
GitHub

```

---

# Locking Strategy — Option A

## 1️⃣ Document Lock (Realtime Layer)

**Key:**
```

project_id:document_id

```

### Protects:
- CRDT operations
- Operational transforms
- Shared memory state mutation

### Required When:
- Applying user edits
- Rebroadcasting updates

### Does NOT protect:
- Git repo
- Branch operations

---

## 2️⃣ Snapshot Branch Lock

Snapshots write to Git.

**Key:**
```

project_id:main

```

### Protects:
- Commit
- Push
- Rebase
- Snapshot consistency

### Snapshot Flow:

1. Acquire branch lock (`main`)
2. Fetch remote updates
3. Write document snapshot
4. Commit
5. Push
6. Release lock

---

## 3️⃣ Repo Lock (Rare)

**Key:**
```

project_id

```

Used only for:
- Initial clone
- Corruption recovery
- Hard reset
- Remote change
- Git GC

### Never hold repo lock during live editing.

---

# Concurrency Matrix — Option A

| Operation | Concurrent Safe? | Lock Required |
|------------|------------------|---------------|
| Multiple live editors | ✅ | Document lock |
| Snapshot + snapshot | ❌ | Branch lock |
| Snapshot + clone | ❌ | Repo lock |
| Fetch during snapshot | ⚠️ | Prefer inside branch lock |
| Clone during editing | ❌ | Repo lock |

---

# Risks — Option A

- CRDT complexity
- WebSocket scaling
- Snapshot drift
- State persistence reliability
- Harder debugging

---

# TODO — Option A

- [ ] Implement CRDT/OT engine
- [ ] Add Redis-backed document state
- [ ] Implement WebSocket gateway
- [ ] Implement snapshot scheduler
- [ ] Enforce branch lock during snapshot
- [ ] Add repo-level lock for destructive ops
- [ ] Add orphan worktree cleanup job
- [ ] Implement push retry on non-fast-forward
- [ ] Add token refresh handling
- [ ] Add lock timeout + crash recovery

---

# OPTION B — PR / BRANCH MODEL (RECOMMENDED)

## Overview

Each collaborator works in a separate branch.

Example:

```

main
user-alice
user-bob
feature-proof-lemma

```

Frontend abstracts branches as:

- Working copy
- Proposed changes
- Submit for merge

Users never see Git.

---

## Architecture

```

Frontend
↓
Flask API
↓
Celery Task
↓
RepoPool (Bare Repo)
↓
Worktree (Per Branch)
↓
Commit + Push
↓
GitHub

```

---

# Locking Strategy — Option B

## 1️⃣ Branch Lock (Primary Lock)

**Key:**
```

project_id:branch_name

```

### Protects:
- Worktree creation
- File writes
- Commit
- Push
- Rebase
- Merge

---

## Save Flow (Per Branch)

1. Acquire branch lock
2. Ensure repo exists
3. Fetch updates
4. Create worktree
5. Write file
6. Commit
7. Push
8. Delete worktree
9. Release lock

---

## 2️⃣ Repo Lock (Destructive Only)

**Key:**
```

project_id

```

Used for:

- Clone
- Delete repo
- Corruption recovery
- Remote change
- Git GC

---

## Lock Ordering Rule (CRITICAL)

Always acquire locks in this order:

```

Repo Lock → Branch Lock

```

Never reverse.

Prevents deadlocks.

---

## 3️⃣ Fetch Behavior (Option B)

Fetch must:

```

+refs/heads/*:refs/remotes/origin/*

```

### Safe Patterns

- Fetch inside branch lock (recommended)
- Avoid fetch during repo deletion
- Avoid concurrent destructive repo operations

---

# Concurrency Matrix — Option B

| Scenario | Safe? | Lock Used |
|------------|--------|------------|
| User A edits branch A | ✅ | Branch lock A |
| User B edits branch B | ✅ | Branch lock B |
| Two users edit same branch | ❌ | Serialized via branch lock |
| Merge feature into main | ❌ | Branch lock main |
| Clone during edit | ❌ | Repo lock |
| Multiple fetches | ✅ | Safe (remote refs only) |

---

# Merge Flow — Option B

1. Acquire branch lock for `main`
2. Fetch
3. Merge feature branch
4. Handle conflicts (surface to UI)
5. Commit merge
6. Push
7. Release lock

---

# Risks — Option B

- Merge conflicts in `.latex`
- Long-lived stale branches
- Branch explosion
- Push retries
- Lock timeout handling

---

# TODO — Option B

- [ ] Implement branch-level lock manager
- [ ] Implement repo-level lock manager
- [ ] Enforce lock ordering rule
- [ ] Add push retry with rebase strategy
- [ ] Implement branch cleanup job
- [ ] Add merge conflict detection
- [ ] Surface conflicts to frontend
- [ ] Add lock timeout + crash recovery
- [ ] Add orphan worktree cleanup
- [ ] Add GitHub rate limit handling

---

# Final Recommendation

For your system (2 files, academic workflow, owner merges contributions):

**Option B — Branch / PR Model is strongly recommended.**

Reasons:

- Simpler architecture
- No CRDT complexity
- Predictable locking
- Clean isolation
- Scales cleanly
- Aligns with your current Git engine

Option A should only be chosen if:

- True multi-cursor live editing is mandatory
- You are ready to implement CRDT infrastructure
- You accept significantly higher complexity

---

# Final Locking Rules Summary

1. Never fetch into local branch refs.
2. Always lock per branch for commits.
3. Only lock repo for destructive operations.
4. Always acquire Repo Lock before Branch Lock.
5. Never raise retry inside context managers.
6. Always clean worktrees in `finally`.
7. Always use remote-tracking refs for fetch.
8. Locks must have timeouts.
9. Locks must auto-release on worker crash.
10. Destructive repo operations must never run concurrently.

---
