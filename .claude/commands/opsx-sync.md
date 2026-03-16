Sync delta specs from a change to main specs.

**Input**: $ARGUMENTS — optionally specify a change name.

**Steps**

1. **Select change** (prompt if not specified)
2. **Read delta specs** from the change directory
3. **Read current main specs** from `openspec/specs/`
4. **Intelligent merge**: Apply delta changes to main specs
   - ADD new requirements
   - MODIFY existing requirements
   - REMOVE deprecated requirements
   - RENAME requirements
   - Do NOT wholesale-replace spec files
5. **Show diff summary** of what changed
6. **Write updated main specs**

**Guardrails**
- Preview changes before writing
- Preserve existing spec content not affected by the delta
- Handle conflicts (delta modifies something that was already changed)
