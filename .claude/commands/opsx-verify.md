Verify that implementation matches OpenSpec change artifacts.

**Input**: $ARGUMENTS — optionally specify a change name.

**Steps**

1. **Select change** and read all artifacts (proposal, spec, design, tasks)
2. **Generate verification report** across three dimensions:

   **Completeness** — Are all tasks/spec requirements implemented?
   - Check each task's acceptance criteria against codebase
   - Search for TODO/FIXME markers

   **Correctness** — Does the implementation match requirements?
   - Verify each spec requirement has corresponding code
   - Check edge cases mentioned in design are handled

   **Coherence** — Does implementation follow the design?
   - Architecture decisions respected
   - Naming conventions followed
   - No unnecessary deviations

3. **Prioritize issues**: CRITICAL / WARNING / SUGGESTION
4. **Output report** with actionable items

**Guardrails**
- Read the actual codebase, don't rely on assumptions
- Reference specific files and line numbers
- Be thorough but practical — focus on what matters
