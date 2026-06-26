# Content Workflow Handoff Patterns

Use these patterns to classify files and write the honest layer. Do not use this file to continue writing the task itself.

## Pre-Interview Projects

Typical files:
- war-room research dossier
- company and guest profile
- interview outline
- video structure
- fact check and risk list
- official input docs or PPTs

Handoff requirements:
- Keep `公开可核实事实`, `输入材料口径`, `编辑判断`, and `待采访确认` separate.
- State the protagonist and supporting party clearly. In Tencent Cloud customer cases, the customer or partner usually carries the story unless the user says otherwise.
- Preserve the selected business scenarios and the unverified metrics that must be confirmed in interview.
- Warn the next AI not to turn supplied internal claims into public facts.

## Post-Interview Script Projects

Typical files:
- transcript or 速记
- prior outline or research brief
- quote map
- short-video script
- title options and revision notes

Handoff requirements:
- Mark the transcript as the source of truth for guest speech.
- Guest quotes must remain transcript-bound and timecoded when timecodes exist.
- Prior outlines can guide story priority but cannot override the transcript.
- If the user gave a length limit, platform, title direction, or forbidden framing, write it in `content_state.md`.

## Case-Study Articles

Typical files:
- interview transcript
- reference articles
- customer case draft
- style sample
- user correction notes

Handoff requirements:
- State whether the target is a short-video script, long case-study article, social post, or another format.
- Include reference articles and accepted style logic when available.
- Preserve user corrections such as "this should be an article, not a script".
- Record forbidden AI-sounding patterns and style constraints.

## Deep Research And HTML Reports

Typical files:
- Markdown report
- self-contained HTML report
- source list
- risk notes
- final recommendations

Handoff requirements:
- Keep Markdown and HTML versions together when they represent the same deliverable.
- Keep source credibility tiers and risk notes visible.
- State whether the HTML is the final readable deliverable or a visual companion to the Markdown source.
- Do not let the next AI omit caveats, date sensitivity, or source uncertainty.

## Training Or Methodology HTML

Typical files:
- self-contained HTML lecture or guide
- source notes
- images or visual assets
- script or speaking notes

Handoff requirements:
- State that the HTML is an editable deliverable if it is the source of truth.
- Preserve audience, speaking duration, and chapter structure.
- Keep visual assets and generated images with the HTML when possible.
- Explain whether the next action is content revision, visual refinement, or export.
