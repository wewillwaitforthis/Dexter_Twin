# Contributing to DexterTwin
 
This file describes how the DexterTwin team gets work merged and how we record who contributed what. It is a shared team commitment: everyone follows it, and anyone can propose changes to it through a pull request. AI tool context lives in `AGENTS.md`.
 
## Workflow
 
1. Pick up a task from the team's task list and make sure it has Acceptance Criteria. If it doesn't, write them before starting.
2. Create a branch for the task and keep changes focused on that one task.
3. Open a pull request (PR) that links the task and states how each Acceptance Criterion is met.
4. Respond to review comments, then merge once the PR is approved and passes the checks below.
## Definition of Done
 
A change is done, and may merge, only when all of the following are true:
 
1. **Tests pass.** All relevant tests pass.
2. **Linting passes.** The project's linter and formatter report no errors on the change.
3. **Security checks pass.** No secrets, keys, tokens, or credentials are committed, and the automated security checks (secret scanning and dependency vulnerability scanning) report no unresolved issues.
4. **Documentation is updated.** The README, `docs/`, and `AGENTS.md` are updated when behavior, setup, or structure changes, and the PR description says what was updated or why nothing needed updating.
5. **Acceptance Criteria are met.** The change satisfies the Acceptance Criteria of the task it completes, and the PR description says how.
6. **One approval.** At least one teammate other than the author has reviewed and approved the PR.
## How each check is enforced
 
| Check | Enforced by | Status | Lands in | Owner |
|---|---|---|---|---|
| Relevant tests pass | CI job running the test suite | Not yet created (no code yet) | Sprint 2 | Quality Owner (Katarina) |
| Linting passes | CI job running the linter and formatter check | Not yet created (no code yet) | Sprint 2 | Quality Owner (Katarina) |
| Security checks pass | CI job running secret scanning and a dependency vulnerability scan | Not yet created | Sprint 3 | Quality Owner (Katarina) |
| Documentation updated | PR template with a documentation checklist item, checked by the reviewer | Not yet created | Sprint 1 | Project Manager (Nour) |
| Acceptance Criteria met | PR template with an Acceptance Criteria checklist, checked by the reviewer | Not yet created | Sprint 1 | Quality Owner (Katarina) |
| One approving review before merge | GitHub branch protection rule on the main branch | Not yet enabled | Sprint 1 | Quality Owner (Katarina) |
 
Until a gate exists, the reviewer checks that item by hand and says so in the review.
 
## The Contribution Norm
 
Every team member owns at least one piece of accepted work in every sprint. Owning a piece of work means you authored or drove it, answered review on it, and saw it accepted.
 
### Where our work lives
 
- **The repository:** code, tests, documentation, and anything else tracked in version control. This is where almost all of our work lives.
- **The team Discord server:** discussion, decisions, and any work product that isn't in the repository, such as meeting notes or findings. Each piece of work posted there should be in a clearly titled message or thread that can be linked to.
### What "accepted" means
 
| Kind of work | Accepted when |
|---|---|
| Code, tests, or documentation in the repository | The PR is approved by someone other than the author and merged |
| Work posted in Discord (findings, notes, proposals) | A teammate other than the author has reviewed it and explicitly approved it in the thread, and any resulting action items are recorded |
| A task or issue | It is closed with its outcome recorded |
 
What does not count as a contribution: formatter runs, lockfile bumps, bulk renames, generated files, dependency updates, status updates, and anything else that is purely mechanical. Lines of code are not a measure of contribution. These are normal work, but they do not count toward the one-piece-per-sprint norm.
 
## Recording contributions
 
At the end of each sprint, each member writes their own contribution line with three parts:
 
1. **Work you owned:** one or more pieces, each with a link (PR, task, or Discord message).
2. **Work you reviewed:** whose work you reviewed and the one specific change you asked for. "LGTM" is not a review.
3. **Most consequential thing you shipped:** one human-written sentence on what it is and how the team knows it works.
If a teammate had nothing accepted in a sprint, their line says so plainly.
 
## Making the norm workable
 
These are our defaults. Edit them as the team learns what works.
 
- **Sizing:** keep PRs small enough to review in one sitting. If a task is too big for a single PR, split it.
- **Review turnaround:** reviewers respond within 2 days. If you are blocked on a review, ask in Discord.
- **Pairing:** when a teammate is stuck, pair on the task. The person who drives the work and answers review owns it.
- **Everyone reviews:** spread reviews across the team so that everyone reviews and everyone is reviewed.
- **Early check:** halfway through each sprint, make sure everyone has a piece of work in progress so nobody ends the sprint with nothing accepted.
## Changing this file
 
Changes to `CONTRIBUTING.md` go through the same PR process as everything else.
