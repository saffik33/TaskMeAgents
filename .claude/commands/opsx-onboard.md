Guided onboarding walkthrough for the OpenSpec workflow system.

**Input**: $ARGUMENTS — optional ("quick" for abbreviated tour).

**Phases** (11 total, can exit anytime):

1. **Welcome**: Explain OpenSpec — structured artifact-driven development
2. **Task Selection**: Scan codebase for improvement candidates (TODOs, missing tests, optimization opportunities)
3. **Explore Demo**: Show `/opsx:explore` thinking mode
4. **New Change**: Create a practice change with `/opsx:new`
5. **Proposal**: Create the first artifact (proposal)
6. **Spec**: Create specification artifact
7. **Design**: Create design artifact
8. **Tasks**: Create task artifacts
9. **Apply**: Implement one task with `/opsx:apply`
10. **Archive**: Archive the completed change
11. **Recap**: Command reference and next steps

**Guardrails**
- Let the user drive the pace — wait for "next" or "continue"
- Allow graceful exit at any phase ("skip", "done", "exit")
- Use real codebase examples from TaskMeAgents
- If "quick" mode: summarize phases 1-4, then do 5-10 hands-on
