# Development Methodology — CoProof

CoProof was developed by a three-person team using a hybrid methodology that combined elements of Scrum with a phase-gated architecture discipline. The overall process can be described in three layers: how work was planned, how it was executed, and how quality was maintained throughout.

## Planning: spec-first, phase-gated

Before writing any code, the team produced a full specification layer. User stories were written in the standard format — as a [role], I want [action], in order to [goal] — each accompanied by explicit, checkbox-style acceptance criteria that defined what "done" meant for that story. Wireframes were prototyped as static HTML files for every principal view of the system. Architecture was committed to documents before it was committed to code: component responsibilities, layer contracts (API → Services → Domain → Infrastructure), design patterns, and inter-service communication protocols were all written down first. UML class diagrams were produced for the backend, frontend, and Lean verification service independently.

With the specification stable, the backend was then built across six sequential phases, each with a defined scope and an explicit exit condition that had to be met before the next phase began. Phase 1 established the application factory, configuration management, Docker stack, and error handling. Phase 2 defined the PostgreSQL schema and SQLAlchemy models. Phase 3 implemented the stateless Git engine with distributed locking. Phase 4 built the domain service layer. Phase 5 exposed the RESTful API. Phase 6 wired the asynchronous task workers and real-time notifications. Only once all six phases were complete did the team switch to a sprint-based cadence for frontend development and end-to-end integration.

## Execution: short sprints and a fixed delivery date

The integration and UI work was organised into three one-week sprints with fixed scopes and a hard feature-freeze date. Work items lived as GitHub Issues. Each sprint had a milestone, and the criterion for closing a sprint was zero open high-priority Issues inside that milestone. The schedule was published in a ROADMAP file visible to all team members and updated at the start of each sprint if the scope changed.

Daily coordination was asynchronous by default: questions and decisions went into Issue comments and pull request threads rather than calls, preserving focus time. The team held brief synchronous check-ins only when a decision required immediate consensus.

## Quality: CI, code review, and a zero-defects rule

Every proposed change went through a pull request. Branch protection on `main` blocked all direct pushes; a merge required a green CI run and an approved peer review. The CI pipeline ran two parallel jobs on every push and every PR: the backend job rebuilt all Docker images from scratch and ran the pytest integration suite against a live PostgreSQL instance; the frontend job ran Vitest unit tests and verified that the production Angular bundle compiled cleanly. Failure in either job blocked the merge.

Bug tracking was formalised from the start. Every reported defect was filed as a GitHub Issue using a structured template, assigned a priority label, and attached to a "Zero Known Bugs" milestone. The team enforced a strict priority rule: no new feature work began while any high-priority bug remained open. This is a direct application of the zero-defects principle described by Joel Spolsky, which holds that bugs become exponentially more expensive to fix the longer they age. The same logic drove the decision to keep CI fast — under five minutes from push to result — so that integration failures surfaced and were addressed while the relevant code was still fresh.

Code review served a dual purpose: catching defects and distributing knowledge across the team. Reviewers were required to run the full stack locally and exercise the affected user flow before approving. A PR template checklist enforced this: no approval was valid without confirming the build passed, the flow was manually tested, no secrets were introduced, and the relevant Issue was referenced with a closing keyword.

Usability was treated as a quality dimension alongside correctness. Two structured sessions with participants external to the development team were scheduled during the final phase of the project. Each session assigned a specific task to the participant and had a silent observer recording where the user paused, hesitated, or failed — not to help, but to identify friction. Every friction point was logged as a GitHub Issue with a `ux` label and addressed before the final delivery.

