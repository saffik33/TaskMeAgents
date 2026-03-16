Start a new OpenSpec change using the artifact-driven workflow.

**Input**: $ARGUMENTS — change name (kebab-case) OR description of what to build.

**Steps**

1. **If no clear input provided, ask what they want to build**
   Ask: "What change do you want to work on? Describe what you want to build or fix."
   From their description, derive a kebab-case name (e.g., "add user authentication" → `add-user-auth`).

2. **Determine the workflow schema**
   Use the default schema (omit `--schema`) unless the user explicitly requests a different workflow.

3. **Create the change directory**
   ```bash
   openspec new change "$ARGUMENTS"
   ```
   This creates a scaffolded change at `openspec/changes/<name>/`.

4. **Show the artifact status**
   ```bash
   openspec status --change "$ARGUMENTS"
   ```

5. **Get instructions for the first artifact**
   Check status output to find the first "ready" artifact.
   ```bash
   openspec instructions <first-artifact-id> --change "$ARGUMENTS"
   ```

6. **STOP and wait for user direction**

**Output**: Summarize change name, location, workflow, status (0/N artifacts), first artifact template.

**Guardrails**
- Do NOT create any artifacts yet — just show instructions
- Do NOT advance beyond the first artifact template
- If name is invalid (not kebab-case), ask for a valid name
- If change already exists, suggest continuing instead
