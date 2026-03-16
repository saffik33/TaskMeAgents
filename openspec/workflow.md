# OpenSpec Workflow — TaskMeAgents

## Artifact Sequence (spec-driven)

1. **Proposal** — What and why (problem, solution, scope)
2. **Spec** — Requirements (functional, non-functional, acceptance criteria)
3. **Design** — How (architecture, data model, API contracts, Temporal workflow design)
4. **Tasks** — Implementation steps (ordered, with dependencies)
5. **Implementation** — Code changes via `/opsx:apply`
6. **Verification** — Review via `/opsx:verify`

## Commands

| Command | Purpose |
|---------|---------|
| `/opsx:new` | Start a new change |
| `/opsx:continue` | Create next artifact |
| `/opsx:ff` | Fast-forward all artifacts |
| `/opsx:apply` | Implement tasks |
| `/opsx:verify` | Verify implementation |
| `/opsx:archive` | Archive completed change |
| `/opsx:sync` | Sync delta specs to main |
| `/opsx:explore` | Think/investigate without implementing |
| `/opsx:onboard` | Guided tutorial |

## Directory Structure
```
openspec/
  workflow.md          This file
  specs/               Main specification files
  changes/             Active changes
    <change-name>/     Each change has its own directory
      proposal.md
      spec.md
      design.md
      tasks/
    archive/           Completed changes
      YYYY-MM-DD-<name>/
```
