Archive a completed OpenSpec change.

**Input**: $ARGUMENTS — optionally specify a change name.

**Steps**

1. **Select change** (prompt if not specified)
2. **Check readiness**:
   - All artifacts complete?
   - All tasks done?
   - Delta specs synced? (if applicable)
3. **If not ready**: Show what's missing and suggest next steps
4. **If ready**: Archive the change
   ```bash
   openspec archive --change "<name>"
   ```
5. **Show summary**: What was archived, where it went

**Guardrails**
- Do NOT archive incomplete changes without explicit user confirmation
- Warn if delta specs haven't been synced
- Show what will be archived before doing it
