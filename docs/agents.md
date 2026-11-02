# AGENTS.md
 
Context for AI coding tools working in the DexterTwin repository. This file is intentionally short: it points to the docs rather than duplicating them. Per-tool files (e.g. `CLAUDE.md`) should point here instead of repeating this content.
 
## Project overview
 
**Team:** DexterTwin
 
DexterTwin is a VR/AR app that lets a user control a robot hand by moving their arm in real life.
 
The repository has no application code yet. Sections marked TBD below will be filled in by the listed owner once the relevant code or decision exists (see "Section owners and updates").
 
- Docs: `docs/` (TBD: confirm path or link)
- README: `README.md`
- Contribution workflow and Definition of Done: `CONTRIBUTING.md`
## Team and roles
 
- **AI Coordinator (Jackson):** owns this file, the AI tool guidelines, and the rules on what may be shared with AI tools.
- **Quality Owner (Katarina):** repository and code management, definition of done, CI health, releases, and clean PR and commit history.
- **Project Manager (Nour):** communication with the project partner and project documentation.
## Stack
 
- Language(s): TBD
- Framework(s): TBD
- Database / storage: TBD
- Hosting / deployment: TBD
## Repository layout
 
TBD: add a short map of top-level directories and what lives in each.
 
## Setup and commands
 
- Install: TBD
- Run locally: TBD
- Test: TBD
- Lint / format: TBD
- Build: TBD
## Conventions
 
- Follow existing patterns in the codebase before introducing new ones.
- Keep changes small and focused; one concern per pull request.
- Write clear commit messages that say what changed and why.
- Add or update tests for behavior changes.
- Update the relevant docs when behavior or setup changes.
- Code style: TBD (link to linter/formatter config once it exists)
## Constraints and confidentiality
 
- No NDA applies to DexterTwin's work. That does not mean everything can be shared with AI tools: follow the sharing rules below.
- Never commit secrets, API keys, tokens, or credentials. Use environment variables and keep `.env` files out of version control.
- Do not add dependencies, change the stack, or alter project structure without discussing it with the team first.
- Do not modify files outside the scope of the requested task.
### What may be shared with AI tools
 
| Kind of content | Rule |
|---|---|
| Project code and repository docs | May be shared, including code, error messages, and logs needed for the task. |
| Secrets and credentials | Never share API keys, tokens, passwords, or `.env` contents, including in screenshots or logs. |
| Project partner information | Share only what the task needs. Remove names, email addresses, phone numbers, Discord handles, and other contact details first. Do not share anything the partner has asked us to keep private. |
| Meeting content | Summaries, decisions, and action items may be shared. Full transcripts and recordings may not be shared unless everyone who took part agrees. |
 
- When in doubt, do not share, and ask the AI Coordinator (Jackson).
- If something cannot be shared, describe the problem in general terms instead, such as a simplified example or an error message with the sensitive parts removed.
## Working with AI tools
 
- Ask for clarification instead of guessing when requirements are ambiguous.
- Explain non-obvious changes in the PR description.
- Say in the PR description where AI contributed meaningfully.
- A DexterTwin teammate reviews and is responsible for everything merged, including AI-generated code.
## Section owners and updates
 
The AI Coordinator (Jackson) owns this file overall and reviews every change to it. Any teammate can propose a change through a pull request. Each section below also has an owner who keeps it current.
 
| Section | Owner | Status | Update when |
|---|---|---|---|
| Project overview | Project Manager (Nour) | Drafted | The project's scope or partner requirements change |
| Stack | AI Coordinator (Jackson) | Not started | A language, framework, storage, or hosting choice is made |
| Repository layout | AI Coordinator (Jackson) | Not started | Top-level directories are added or reorganized |
| Setup and commands | Quality Owner (Katarina) | Not started | Install, run, test, lint, or build commands exist or change |
| Testing guidance | Quality Owner (Katarina) | Not started | The test suite or CI is added or changes |
| Code style and linting rules | Quality Owner (Katarina) | Not started | Linter or formatter config is added or changes |
| Architecture notes / links to docs | AI Coordinator (Jackson) | Not started | Design docs are written or the architecture changes |
| Known gotchas | AI Coordinator (Jackson) | Not started | Someone hits a non-obvious problem worth warning about |
| What may be shared with AI tools | AI Coordinator (Jackson) | Drafted | The team's or partner's rules on AI use change |
