# Engineering Lessons — HalaTuju

Cross-cutting lessons from sprint retrospectives. Only items that affect future work regardless of feature area.

- Bulk data loading via MCP tools should always be delegated to subagents to avoid context exhaustion. Each batch consumes significant context; 20+ batches will overflow the main window. (STPM Sprint 3)
