# Resume Prompt

You are taking over this content task from another AI session.

First read:
1. `HANDOFF.md`
2. `content_state.md`
3. `task_boundary.md`
4. `conversation/task_conversation.md` if it exists
5. The files listed as highest-priority in `manifest.json`

Task: {{TASK_TITLE}}

Target output: {{TARGET_OUTPUT}}

Current next action: {{NEXT_ACTION}}

Important rules:
- Keep public facts, user-provided/internal claims, editorial judgment, and unconfirmed claims separate.
- Do not invent guest quotes. If a transcript is present, it is the source of truth for guest speech.
- Do not treat prior outlines as stronger evidence than transcripts or source files.
- If conversation snippets are included, use them only for intent, preferences, and prior decisions. Do not treat them as factual sources.
- Preserve the user's stated style constraints and forbidden phrasing.
- If source files conflict, surface the conflict instead of smoothing it over.

The handoff pack includes the files needed to continue. Do not assume missing files exist unless `excluded_files.md` lists them.
