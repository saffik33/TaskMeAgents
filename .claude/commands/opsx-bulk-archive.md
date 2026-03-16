Archive multiple completed OpenSpec changes in batch.

**Input**: $ARGUMENTS — optional filter or "all completed".

**Steps**

1. **List all changes**: `openspec list --json`
2. **Identify completed changes** (all artifacts done, all tasks done)
3. **Detect spec conflicts** between changes:
   - If multiple changes modify the same spec, check codebase for implementation evidence
   - Resolve conflicts agentically (the implemented version wins)
4. **Show consolidated status table** with archive readiness
5. **Confirm batch operation** with user
6. **Execute archives** one by one, showing progress

**Guardrails**
- Always show what will be archived before executing
- Handle spec conflicts before archiving
- Skip changes that aren't ready (show reason)
