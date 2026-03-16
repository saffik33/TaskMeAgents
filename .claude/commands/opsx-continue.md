Continue working on an OpenSpec change by creating the next artifact.

**Input**: $ARGUMENTS — optionally specify a change name.

**Steps**

1. **If no change name provided, prompt for selection**
   Run `openspec list --json` to get available changes. Present top 3-4 most recently modified as options. Do NOT auto-select.

2. **Check current status**
   ```bash
   openspec status --change "<name>" --json
   ```

3. **Act based on status**:
   - **All complete**: Suggest running `/opsx:apply` or `/opsx:archive`
   - **Has ready artifacts**: Get instructions for the next ready artifact, create it
   - **All blocked**: Explain which dependencies are missing

4. **Create ONE artifact per invocation**
   ```bash
   openspec instructions <artifact-id> --change "<name>"
   ```
   Then create the artifact content following the instructions.

5. **Show updated status** after creating the artifact.

**Guardrails**
- Create only ONE artifact per invocation
- Follow the dependency order (only create "ready" artifacts)
- If the user's input contradicts the artifact instructions, ask for clarification
