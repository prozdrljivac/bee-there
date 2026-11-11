# Agent Instructions

## Code Readability and Simplicity

- Code must be simple and easy to read. Passing tests alone is not enough.
- Keep each function focused on one clear job. Keep the main flow easy to follow.
- When a function mixes workflow with detailed checks or processing, extract small, clearly named helpers where this makes the code easier to understand.
- Use clear names, named limits, and simple control flow. Avoid unnecessary nesting.
- Do not split code merely to make functions shorter. Avoid needless helpers, layers, and abstractions.
- Prefer clear code over comments or documentation that repeat what the code does. Keep explanations for non-obvious reasons and constraints.
- Before requesting review, check changed code for readability and simplicity. Refactor with tests green and rerun relevant tests after each material change.

## Visual Change Review

- After each feature, bug fix, refactor, or code implementation, read and follow `.agents/skills/change-review/SKILL.md` before reporting completion.
- Run this review again after implementation changes made from user feedback. Do not run it after every edit or test cycle.
- Create the HTML review only in a unique directory under `/tmp`. Include the overview, reasons, visual flow, every in-scope changed file, and test results. Discussion and feedback happen in chat, not in the HTML page.
- Share the report link with the user. Keep reports out of the repository and leave all changes uncommitted until approved.

## Commit Policy

- All work must be reviewed and accepted by the user before it is committed.
- Do not create a Git commit unless the user has explicitly approved the current changes and asked for them to be committed.
- After making changes, provide a short, simple and clear summary of what changed and why.
- If review feedback requires further changes, leave those changes uncommitted until they are also reviewed and accepted.

