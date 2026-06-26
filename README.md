# Honest Handoff Pack

`honest-handoff-pack` is a Codex/agent skill for packaging an unfinished content task so another AI tool or teammate can continue it safely.

It is useful when a task is halfway done and you need to switch tools because of token limits, subscription limits, model instability, or a handoff to another person.

## What It Does

The skill scans the current workspace, identifies the selected task, and builds a portable handoff folder plus a zip file.

The handoff pack keeps these boundaries explicit:

- Publicly verifiable facts
- User-provided or internal-source claims
- Editorial judgment
- Claims that still need confirmation

This helps the next AI continue the task without mixing unrelated work, inventing quotes, or treating draft assumptions as facts.

## Pack Contents

A generated pack includes:

- `HANDOFF.md`: human-readable task background, current state, boundaries, and next steps
- `RESUME_PROMPT.md`: prompt to paste into the next AI tool
- `content_state.md`: target output, style constraints, current version, and next action
- `task_boundary.md`: why included files belong to this task and why other files were excluded
- `manifest.json`: machine-readable file manifest
- `excluded_files.md`: skipped files and reasons
- `sources/`: source materials, transcripts, references, and input files
- `artifacts/`: drafts, reports, HTML deliverables, and generated work
- `conversation/`: optional task-related conversation snippets, only when explicitly requested

## Install

Copy this folder into your agent skills directory, for example:

```bash
mkdir -p ~/.codex/skills
cp -R honest-handoff-pack ~/.codex/skills/
```

You can also place it in another agent-compatible skills folder.

## Use In Natural Language

Ask your AI agent something like:

```text
Use honest-handoff-pack to package this unfinished task for Claude.
```

Or:

```text
Generate a handoff pack so I can continue this task in another AI tool.
```

The agent should first show candidate task clusters when the task boundary is unclear. It should only build the final pack after a clear task name, core file, or user confirmation.

## When To Trigger

Do not package every task at every turn. Trigger handoff at clear risk points or phase boundaries.

Manual triggers:

- The user says they want to switch AI tools, continue elsewhere, or hand the task to another person.
- The user mentions token limits, subscription limits, account limits, context overflow, model instability, or a task getting stuck halfway.
- The user asks to include the same-task conversation, current context, or files for another AI.

Proactive soft triggers:

- The task already has multiple source files, drafts, decisions, and pending confirmations.
- The work just reached a stable checkpoint: research finished, outline finished, first draft finished, fact check finished, or before a major rewrite.
- The next step depends on preserving source boundaries, user preferences, or "what has already been tried."
- The agent notices that continuing in the current session may lose useful context.

Default behavior:

- If the user explicitly asks for a handoff pack, build it once the task boundary is clear.
- If the agent only detects risk, ask a short confirmation first.
- If the task is small, single-file, and easy to restate in one message, do not package it.
- Package at "checkpoint moments," not after every message.

## Quota And Context Warnings

Exact quota warnings are only possible when the current AI tool exposes reliable usage data, such as remaining messages, token budget, or a usage API. If that data is available, the agent can use simple thresholds:

- Around 80% used: suggest creating a handoff pack at the next checkpoint.
- Around 90% used: strongly recommend creating a handoff pack before continuing.

Different tools expose different signals:

| Tool type | Can it support exact warnings? | Practical rule |
| --- | --- | --- |
| Claude Code, Cursor, GitHub Copilot, Devin Desktop | Usually yes, if the status command, usage dashboard, usage meter, or plan page is readable | Use the real meter, then warn around 75-80% and 90%. |
| Codex on a ChatGPT plan | Sometimes | Use the Codex usage page or limit banner when visible. Do not guess from conversation length. |
| Claude web/desktop paid plans | Often, with UI access | Use Settings > Usage progress bars when available. Otherwise treat warning messages as risk signals. |
| Gemini Apps and other opaque consumer apps | Usually no exact account percentage | Use context-window pressure, visible warnings, rate-limit errors, and task complexity as risk signals. |
| API-funded tools, such as OpenAI API or DeepSeek API | Yes, if the API key can read usage, costs, balance, or credits | Treat API usage separately from consumer subscription limits. |

Detailed provider notes live in [`references/quota-and-context-detection.md`](references/quota-and-context-detection.md).

If the tool does not expose reliable quota data, do not pretend to know the exact percentage. Use a handoff risk level instead:

- Medium risk: long conversation, several files, multiple decisions, or a completed phase.
- High risk: context warnings, rate-limit or quota errors, repeated retries, model instability, or the user says the current account/tool may fail soon.

In medium risk, ask lightly. In high risk, interrupt with a clear handoff recommendation.

## Use Directly

Discovery pass:

```bash
python3 ~/.codex/skills/honest-handoff-pack/scripts/build_handoff_pack.py --workspace "$PWD"
```

Build from a task name:

```bash
python3 ~/.codex/skills/honest-handoff-pack/scripts/build_handoff_pack.py --workspace "$PWD" --task "TASK NAME" --target-ai "Claude" --yes
```

Build from a core file:

```bash
python3 ~/.codex/skills/honest-handoff-pack/scripts/build_handoff_pack.py --workspace "$PWD" --core-file "draft.md" --target-ai "ChatGPT" --yes
```

Include related Codex conversation snippets:

```bash
python3 ~/.codex/skills/honest-handoff-pack/scripts/build_handoff_pack.py --workspace "$PWD" --task "TASK NAME" --include-codex-conversation --yes
```

Conversation snippets are not included by default. When included, they are only context for intent, preferences, and prior decisions. They are not treated as factual source material.

## Safety

The skill excludes obvious sensitive files such as `.env`, private keys, local databases, dependency folders, caches, and files that appear to contain credentials.

Still, always review the generated handoff pack before sharing it.
