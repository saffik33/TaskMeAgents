Fast-forward through artifact creation — generate ALL remaining artifacts in one operation.

**Input**: $ARGUMENTS — change description or name.

**Steps**

1. If no change exists, ask for description and create one (`openspec new change "<name>"`)
2. Loop: check status → get instructions → create artifact → repeat until all done
3. Show final status when complete

**Output**: All artifacts created, change is ready for `/opsx:apply`.

**Guardrails**
- Ask for the change description upfront if not provided
- Create artifacts in dependency order (respect "ready" status)
- Stop and ask if any artifact requires user decision
