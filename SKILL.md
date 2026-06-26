---
name: honest-handoff-pack
description: |
  Build an honest handoff pack when the user needs to switch AI tools, continue work in another assistant,
  hand work to a teammate, or recover from token/subscription limits. Use when the user says 打包交接,
  换 AI 继续, 额度快满了, 生成 handoff 包, 把上下文打包, 无缝接到 ChatGPT/Claude/Gemini/Cursor,
  把聊天记录一起打包, 把同一任务的对话带过去, or asks to package a writing, article, interview,
  script, report, HTML, or research task with context.
  The skill identifies the current task boundary first, then packages only files and context that belong
  to that same task, with clear fact boundaries and resume instructions.
metadata:
  short-description: Package a content task for honest cross-AI handoff
---

# Honest Handoff Pack

## Core Goal

Create a portable handoff pack for an in-progress content task so another AI or teammate can continue without mixing unrelated tasks, inventing context, or losing fact boundaries.

This skill does not write the next article or script. It captures the current work state, files, source boundaries, user preferences, and next actions.

## Default Behavior

Use `scripts/build_handoff_pack.py` from this skill directory.

1. Run a discovery pass first. Without an explicit task name or core file, do not build the pack immediately.
2. Show the user the candidate task clusters and the recommended task.
3. Build the pack only after the user confirms, or when the user has already provided a clear task name or core file.
4. Output the pack under the current workspace:
   `handoffs/<timestamp>-<task-name>/`
5. Also create a zip next to the folder.

Example discovery:

```bash
python3 ~/.codex/skills/honest-handoff-pack/scripts/build_handoff_pack.py --workspace "$PWD"
```

Example build after confirmation:

```bash
python3 ~/.codex/skills/honest-handoff-pack/scripts/build_handoff_pack.py --workspace "$PWD" --task "Customer case article" --target-ai "Claude" --yes
```

Example build from a core file:

```bash
python3 ~/.codex/skills/honest-handoff-pack/scripts/build_handoff_pack.py --workspace "$PWD" --core-file "customer-case-draft.md" --yes
```

Example build with task-related Codex conversation snippets:

```bash
python3 ~/.codex/skills/honest-handoff-pack/scripts/build_handoff_pack.py --workspace "$PWD" --task "Customer case article" --include-codex-conversation --yes
```

Example build with an explicit conversation file:

```bash
python3 ~/.codex/skills/honest-handoff-pack/scripts/build_handoff_pack.py --workspace "$PWD" --core-file "customer-case-draft.md" --conversation-file "task-conversation-notes.md" --yes
```

## Task Boundary Rules

Never use "files modified in the last 14 days" as the task boundary. Recent modification is only a discovery signal.

Group files by:

- Entity names in filenames and titles, such as company, guest, project, or product names.
- Headings and purpose lines in Markdown, HTML, and DOCX files.
- File relationships, such as `.md + .html`, research brief + script, transcript + script, reference article + rewrite.
- Recent co-editing, as a weak supporting signal.
- User-provided task name, core file, target output, or target AI.
- Content role: source material, transcript, reference style, research brief, script draft, final article, HTML deliverable.

Before building without a clear task name or core file, present a concise candidate list:

```text
我识别到当前可能有 3 个任务：
1. Customer case interview project
2. Product launch article
3. Market research report

推荐打包：Customer case interview project
将包含：
- 调研作战手册
- 访谈脚本
- 事实核查与风险清单

疑似无关，不打包：
- Market research report
- Unrelated industry deep research
```

## Trigger Timing

Do not build a handoff pack after every normal task turn. Trigger at risk points
and checkpoint moments.

Build directly when the user explicitly says:

- 打包交接, 换 AI 继续, 额度快满了, 上下文快满了
- 生成 handoff 包, 把上下文打包, 把同一任务的对话带过去
- hand this to Claude, ChatGPT, Gemini, Cursor, a teammate, or another AI

Offer a short confirmation first when:

- The task has multiple source files, drafts, decisions, and pending confirmations.
- A phase has just finished: research, outline, first draft, fact check, or final revision.
- Continuing in the current session risks losing important context.
- The user says the task is stuck, unstable, or likely to move to another account/tool.

Do not package when the task is small, single-file, and can be restated in one
message. Package at checkpoint moments, not after every message.

## Pack Contents

Every built pack must contain:

- `HANDOFF.md`: human-readable background, current state, completed work, unfinished work, and honest boundaries.
- `RESUME_PROMPT.md`: prompt to paste into another AI.
- `content_state.md`: output type, audience, style, length, forbidden language, current version, and next action.
- `task_boundary.md`: why included files belong to the same task, and why excluded files were left out.
- `manifest.json`: machine-readable file list with original path, copied path, role, size, modification time, confidence, and inclusion reason.
- `excluded_files.md`: unrelated, sensitive, too-large, or skipped files and reasons.
- `artifacts/`: generated deliverables and drafts.
- `sources/`: transcripts, source materials, references, media, and supporting inputs.
- `conversation/`: optional task-related conversation snippets when the user explicitly asks to include chat history or passes a conversation file.

Conversation files, when enabled:

- `conversation/task_conversation.md`: filtered user/assistant conversation snippets related to the selected task.
- `conversation/conversation_manifest.json`: source sessions, matched terms, included turn count, warnings, and selection policy.
- `conversation/README.md`: usage rules and exclusions.

Do not include conversations by default. Enable them only when:

- The user explicitly says to include 同一任务对话、聊天记录、上下文聊天, or similar.
- The user provides `--conversation-file`.
- The handoff would clearly lose important decisions without the task conversation.

Conversation collection rules:

- Only include user/assistant natural-language messages.
- Exclude system/developer instructions, tool calls, tool outputs, environment context, and runtime metadata.
- Match Codex sessions by selected task title, task keywords, core-file entities, and optional `--conversation-query`.
- Add nearby turns only as local context around matched turns.
- Treat conversation as background evidence for intent, preferences, and decisions, not as factual source material.
- If a turn appears to contain API keys, tokens, passwords, private keys, or credentials, skip it.

## Honest Layer

Always make these distinctions explicit:

- `公开可核实事实`: facts backed by public sources in the packaged files. Do not newly verify unless the user asks.
- `输入材料口径`: claims from user-provided docs, PPTs, transcripts, briefs, or internal material.
- `编辑判断`: synthesis, storyline, framing, suggested wording, or risk interpretation.
- `待确认`: claims, metrics, identities, dates, and attribution that still require user, source, or interview confirmation.

Do not package API keys, tokens, passwords, credentials, `.env` files, private keys, or obvious local databases.

## Content Workflow Rules

For detailed content-task patterns, read `references/content-workflow-patterns.md` only when the task involves writing, scripts, interviews, reports, or HTML deliverables.

For sensitive file handling and redaction policy, read `references/privacy-and-redaction.md` when a candidate file looks private, credential-like, or unusually broad.

Default rules:

- Pre-interview projects must preserve `公开事实 / 输入材料口径 / 编辑判断 / 待采访确认`.
- Post-interview scripts must mark transcripts as the source of truth. Guest quotes cannot be invented or polished beyond the transcript.
- Case-study articles must state whether the target output is a short-video script or long article, and include style references when available.
- Research and HTML reports must keep Markdown, HTML, sources, risk notes, and final recommendations together.
- Training or methodology HTML should be described as an editable deliverable, not merely an export.

## Final Response

After building, reply with:

- Handoff folder path.
- Zip path.
- Recommended next action: paste `RESUME_PROMPT.md` into the target AI and upload the zip or selected files.
- Any skipped sensitive or high-risk files.

Keep the response concise.
