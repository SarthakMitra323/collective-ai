# Governance

This document describes how **Collective AI** is governed and how decisions are made.

## Project Owner (BDFL model)

Collective AI uses a **BDFL (Benevolent Dictator For Life)** governance model.

- The **Project Owner** is the final decision-maker for the project.
- Community input is welcome and strongly encouraged, but the Project Owner has final say on:
  - roadmap and priorities
  - architectural decisions
  - security posture and incident response
  - release readiness and timelines
  - moderation and Code of Conduct enforcement

## Roles

### Project Owner / Maintainer

**Initial (and current) Project Owner / Maintainer:**
- GitHub: `SarthakMitra323`

Responsibilities:
- triage issues and pull requests
- review and merge changes
- maintain releases and production stability
- enforce quality, security, and project direction

## Decision-making process

### Proposals (features, refactors, behavior changes)

- Open an Issue describing the proposal and rationale.
- For implementation, open a Pull Request referencing the Issue.
- The Project Owner reviews and either:
  - approves/merges,
  - requests changes,
  - or closes/declines with rationale.

### Breaking changes

Breaking changes (including API changes) should:
- be clearly labeled in the PR description
- include upgrade notes when applicable
- be documented in `CHANGELOG.md`

## Pull request review policy

- PRs may be merged only after review by the Project Owner.
- Additional required reviews are enforced via `CODEOWNERS` for:
  - `backend/**`
  - `security.js`

(See `.github/CODEOWNERS`.)

## Security and responsible disclosure

Security issues must be reported privately.

Contact:
- **hello.connectsphere.offical@gmail.com**

Please see `SECURITY.md` for reporting guidelines.

## Code of Conduct

All contributors must follow `CODE_OF_CONDUCT.md`.

## Amendments

This governance document may be updated by the Project Owner as the project evolves.
