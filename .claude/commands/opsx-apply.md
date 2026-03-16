Implement tasks from an OpenSpec change.

**Input**: $ARGUMENTS — optionally specify a change name.

**Steps**

1. **Select change** (prompt if not specified, use `openspec list --json`)
2. **Read context files**: proposal, spec, design from the change directory
3. **Show task progress** with status indicators
4. **Loop through pending tasks**:
   - Read task file for requirements
   - Implement the task (write code, tests, etc.)
   - Mark task complete: `openspec task done <task-id> --change "<name>"`
   - Show updated progress
5. **When all tasks done**: Suggest `/opsx:verify` then `/opsx:archive`

**Guardrails**
- Implement tasks in order (respect task dependencies)
- Follow the design document's architecture decisions
- Run tests after each task if applicable
- Do NOT skip tasks or mark incomplete tasks as done
