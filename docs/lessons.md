# Engineering Lessons — HalaTuju

Cross-cutting lessons from sprint retrospectives. Only items that affect future work regardless of feature area.

- Bulk data loading via MCP tools should always be delegated to subagents to avoid context exhaustion. Each batch consumes significant context; 20+ batches will overflow the main window. (STPM Sprint 3)
- When modifying grade scales or lookup tables, always run golden master tests immediately — parsed data may contain legacy values not visible in the UI-facing code. (STPM Sprint 5)
- Use constants for localStorage keys instead of string literals to prevent key mismatch bugs across pages built in different sprints. (STPM Sprint 5)
