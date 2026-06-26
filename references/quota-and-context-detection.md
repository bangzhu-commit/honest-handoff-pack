# Quota And Context Detection

Use this reference when deciding whether the handoff skill can warn at an exact
usage threshold, such as 80% or 90%, or should fall back to a qualitative
handoff-risk warning.

## Core Rule

An exact quota warning requires a real numerator and denominator from the
current tool, provider, or billing system:

- used messages / total messages
- used credits / included credits
- remaining credits / configured credit limit
- used tokens / current context window
- current-session or weekly progress bars
- quota, balance, usage, or cost returned by an official API

If the tool only exposes a warning banner, a vague plan multiplier, or a rate
limit error, do not convert that into a fake percentage. Say the exact quota is
not readable and use handoff risk instead.

Do not mix account quota with context-window usage. A 200k-token context window
does not mean the subscription is 200k tokens from exhaustion.

## Detection Tiers

### Tier 1: Directly Readable

Use exact 80% / 90% warnings when the current agent can directly read a reliable
meter without guessing:

- A CLI command, status command, or current app API reports remaining capacity.
- A provider dashboard reports used and remaining allowance.
- A usage API or billing API returns usage, balance, credits, or costs.
- The active tool exposes the current context budget or remaining context.

### Tier 2: UI-Readable With Permission

Use exact warnings only after reading the logged-in page or app UI and finding a
real meter:

- Browser access is available.
- The user is logged in.
- The page gives clear numbers, progress bars, allowance, remaining balance, or
reset time.

If the UI is blocked, hidden, unstable, or only says "near limit", fall back to
handoff risk. Do not scrape private account pages unless the user has asked for
quota checking or the current task clearly needs it.

### Tier 3: Not Reliably Readable

Use qualitative handoff-risk warnings when:

- The provider publishes only variable usage-limit rules.
- The account has rolling caps that depend on model, feature, attachments, or
conversation length.
- The app only shows a temporary warning or rate-limit error.
- The current agent cannot access the relevant dashboard or CLI status.

## Provider Matrix

| Tool or plan | Readability | What can be read | How to use it |
| --- | --- | --- | --- |
| Codex on a ChatGPT plan | Partial to good | Codex usage page, limit banner, credit options, and plan-specific usage notes when visible | Use exact percentages only if the usage page exposes numbers. Otherwise treat a limit banner as high handoff risk. |
| ChatGPT consumer chat | Partial | Visible app banners, model picker warnings, or account usage pages when available | Do not infer exact remaining messages from conversation length. Use visible warnings as risk signals. |
| Claude Code with Pro or Max | Good | Remaining allocation from `/status`, warning messages, and shared Pro/Max limits | Prefer `/status`. If it returns a clear remaining value, use exact thresholds; if it only warns, treat as high risk. |
| Claude web or desktop Pro/Max | Good with UI access | Settings > Usage progress bars for current five-hour session and weekly usage | Use the progress bars if logged-in browser access is available. Otherwise use Claude's own warning messages only as risk signals. |
| Cursor Pro | Good with UI access | Dashboard usage, real-time usage, remaining allowance, on-demand charges, reset date | Use dashboard values for percentages. If only the editor notification is visible, treat it as high risk. |
| GitHub Copilot individual plans | Good with UI/API access | AI credits allowance, used credits, usage dashboard, budget alerts, included-usage alerts | Use dashboard or billing data for exact percentages. GitHub budget alerts commonly fire at 75%, 90%, and 100%, so mirror those thresholds if configured. |
| Devin Desktop / Windsurf-era quota plans | Good with app/page access | Usage meter, remaining daily/weekly quota, reset timing, plan page | Use the usage meter or plan page. If the current agent cannot access the app/page, fall back to risk signals. |
| Gemini Apps on Google AI plans | Partial | Published context windows and visible account/app limits, but usage limits are compute-based and variable | Use visible context-window pressure and app warnings. Do not claim a precise subscription percentage unless the UI exposes a real meter. |
| OpenAI API | Good with admin API access | Organization usage endpoints and cost endpoints | API usage is separate from ChatGPT/Codex plan usage. Use it only for API-funded work. |
| DeepSeek API | Good with API key access | `/user/balance` returns availability and balance information | Use balance for API spend warnings. It does not measure a consumer subscription message cap. |
| OpenRouter API | Good with API key access | Credit totals, usage, key limits, and remaining credits | Use credit or key-limit fields for percentages when a configured limit exists. |
| Opaque consumer apps | Poor | Usually only warnings, reset notices, or rate-limit errors | Never invent an 80% or 90% estimate. Use medium/high handoff risk. |

## Reminder Logic

1. Check direct status first: current app metrics, CLI status, exposed context
   budget, or official usage API.
2. If no direct status exists and the user has asked for quota checking, inspect
   the logged-in dashboard or usage page when available.
3. If a real meter exists:
   - 75% to 80% used: suggest building a handoff pack at the next checkpoint.
   - 90% or more used: recommend building a handoff pack before continuing.
   - 95% or more used, or no meaningful remaining turns: build directly after a
     short confirmation unless the user explicitly wants to continue.
4. If no real meter exists:
   - Medium risk: long conversation, several files, many decisions, or a phase
     just finished.
   - High risk: visible context warning, quota/rate-limit error, repeated retry,
     degraded model behavior, or user says the account may fail soon.
5. When warning the user, name the evidence:
   - "I can read the Cursor dashboard: about 86% of included API usage is used."
   - "Claude Code only gave a remaining-capacity warning, not a number, so I am
     treating this as high handoff risk."
   - "I cannot read this tool's quota meter. This is a context-risk warning, not
     an account-quota percentage."

## Source Links

- OpenAI Codex plan usage:
  <https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan>
- Claude Code Pro/Max usage and `/status`:
  <https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan>
- Claude paid-plan Usage settings:
  <https://support.claude.com/en/articles/9797557-usage-limit-best-practices>
- Cursor usage dashboard and limits:
  <https://cursor.com/help/models-and-usage/usage-limits>
- GitHub Copilot AI credits:
  <https://docs.github.com/en/copilot/concepts/billing/usage-based-billing-for-individuals>
- GitHub budgets and alerts:
  <https://docs.github.com/en/billing/concepts/budgets-and-alerts>
- Devin Desktop quota usage:
  <https://docs.devin.ai/desktop/accounts/quota>
- Google Gemini Apps usage limits and context windows:
  <https://support.google.com/gemini/answer/16275805>
- OpenAI API usage and costs:
  <https://platform.openai.com/docs/api-reference/usage>
- DeepSeek API balance:
  <https://api-docs.deepseek.com/api/get-user-balance>
- OpenRouter key limits and credits:
  <https://openrouter.ai/docs/api/reference/limits>
  <https://openrouter.ai/docs/api/api-reference/credits/get-credits>
