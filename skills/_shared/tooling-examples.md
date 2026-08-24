# Tooling Examples

Canonical call shapes used by the bundle's "Asking the user" workflow. Each skill's SKILL.md references this file rather than restating the example.

## AskUserQuestion via ToolSearch (Claude Code)

`AskUserQuestion` is a deferred tool. Load its schema once per session before calling:

```
ToolSearch(query="select:AskUserQuestion", max_results=1)
```

After the schema loads, call directly:

```
AskUserQuestion(questions=[
  {
    "question": "Which option fits?",
    "header": "Header",
    "multiSelect": false,
    "options": [
      {"label": "Recommended option (Recommended)", "description": "Why this is the default."},
      {"label": "Alternative", "description": "When to pick this."}
    ]
  }
])
```

Up to 4 questions per call. The user can always pick "Other" to type a custom answer.

## Codex `ask_user_question` (Codex CLI interactive TUI)

Native, no schema loader needed:

```
ask_user_question(
  question="Which option fits?",
  options=[
    "Recommended option (Recommended)",
    "Alternative"
  ]
)
```

For free-text input, use `request_user_input` instead.

## omp `ask` (Oh My Pi)

Native, no schema loader:

```
ask(questions=[
  {
    "id": "approach",
    "question": "Which option fits?",
    "header": "Approach",
    "multi": false,
    "recommended": 0,
    "options": [
      {"label": "Recommended option", "description": "Why this is the default."},
      {"label": "Alternative", "description": "When to pick this."}
    ]
  }
])
```

`recommended` is a zero-based index; the runtime appends ` (Recommended)` itself, so never write it into a label. The runtime also owns the labels `Other (type your own)`, `Chat about this`, and `Next →` — sending any of them is rejected. Up to 4 questions per call; `ask` must be the only tool call in its message.

## Fallback (any harness without a structured-question tool)

Print a clearly-formatted numbered question and wait for the user's reply:

```
Question: Which option fits?
1. Recommended option (Recommended) — why this is the default.
2. Alternative — when to pick this.
3. Other — type your answer.
```

Use this only when the structured-question tool is not callable (e.g., `codex exec` non-interactive runs).
