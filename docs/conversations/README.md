# Conversation Archives

This directory is reserved for raw conversation exports.

The repository cannot automatically recover the original chat window if the remote session, IDE, or browser state is lost. To preserve a full conversation, export it from the chat UI as Markdown or text and commit it here.

Suggested naming:

```text
YYYY-MM-DD-stage-summary.md
```

Examples:

```text
2026-05-27-stage-2-to-5a.md
2026-05-27-report-debugging.md
```

Recommended structure for an exported archive:

```markdown
# Conversation Archive: <topic>

- Date:
- Environment:
- Related commit:
- Related files:

## Summary

Short human-readable summary.

## Raw Conversation

Paste or attach the exported conversation here.
```

For day-to-day agent continuity, prefer updating `docs/agent_handoff.md`. Raw chat exports are useful as evidence and for detailed reconstruction, but the handoff document is faster for future agents to read.
