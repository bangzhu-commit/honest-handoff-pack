# Privacy And Redaction Rules

The handoff pack should be useful but conservative. Exclude secrets and broad local state by default.

## Always Exclude

- `.env`, `.env.*`, `.npmrc`, `.pypirc`, `.netrc`
- private keys, certificates, and credential files: `.pem`, `.key`, `.p12`, `.pfx`, `id_rsa`, `id_ed25519`
- filenames containing `secret`, `token`, `password`, `credential`, `apikey`, `api_key`
- local databases and app state: `.sqlite`, `.db`, browser profiles, cache folders
- dependency and build folders: `.git`, `node_modules`, `__pycache__`, `.cache`, `dist`, `build`

## Content Scan Signals

If a text file contains likely credential assignments, exclude it and record the reason in `excluded_files.md`.

Examples:
- `API_KEY: <redacted>`
- `OPENAI_API_KEY: <redacted>`
- `token: <redacted>`
- `password: <redacted>`
- `client_secret`
- `private_key`

## Conversation Snippets

When packaging task-related chat history, include only user/assistant natural-language messages that match the selected task. Exclude system instructions, developer instructions, tool calls, tool outputs, runtime metadata, environment context, and any turn that appears to contain credentials.

Conversation snippets are context for intent, preferences, and prior decisions. They are not public facts, transcript quotes, or source material.

## Do Not Over-Redact

Normal article sources, public URLs, titles, company names, guest names, interview notes, and generated drafts should be included when they belong to the selected task.

If a file is useful but too sensitive to include, list it in `excluded_files.md` with a short note so the next AI knows it exists but cannot rely on its contents.
