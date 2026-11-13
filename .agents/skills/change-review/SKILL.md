---
name: change-review
description: Create a temporary, self-contained HTML review only when the current task changes repository source code or test code, including code changes made from review feedback. Explain what changed, why, and how it works, with a visual overview and a complete file-by-file walkthrough. Also use when the user explicitly asks to visually review existing code changes.
---

# Visual change review

Create a readable HTML page that helps the user understand the implementation. This is an explanation, not just a diff viewer. Discussion and feedback happen in chat, not in the page. Use short sentences and clear terms. Do not commit changes.

## When to run

- Run automatically only when the current task changes source code or test code in this repository. Run after implementation, relevant tests, and the readability check, before the final response.
- Run again after review feedback only if that follow-up changes source code or test code. Create a new report; do not overwrite the previous report.
- Skip automatic reviews for discussion, research, commands, and documentation, instruction, or configuration-only changes. Do not run after each edit or test cycle.
- Pre-existing code changes from other tasks do not trigger an automatic review. Compare this task's changes with its starting state, not just the current Git diff.
- A skill is an instruction workflow, not an event hook. The project `AGENTS.md` requires this completion step only for code changes. If the user explicitly requests a review of existing code changes, use that scope. Do not generate a report when there are no code changes to review.

## Establish the review scope

1. Read the request and the session's changes. Record the working-tree state before implementation when possible.
2. Inspect `git status --short`, staged and unstaged diffs, and untracked files. Use NUL-delimited path lists when processing paths in scripts. Do not stage, reset, or otherwise change Git state.
3. Use the implementation's starting snapshot as the baseline. Do not assume all dirty files belong to this task. With no snapshot, use the session history and current diffs, disclose the baseline, and mark uncertain ownership. Ask only if that uncertainty prevents a useful review.
4. Read each in-scope file and its diff. Include created, modified, deleted, and renamed files, tests, configuration, documentation, and lockfiles. Explain pre-existing changes separately if they share a file with this task. Do not attribute them to this implementation.
5. Check the inventory against the report before finishing. Give every in-scope file an entry. For binary, generated, or very large files, explain the purpose and impact and state what could not be inspected. Do not silently omit them.
6. Base explanations on the request, code, and observed results. Label inferred reasons and unknowns. Never invent test results or claim that a visual diagram proves behavior.

## Build the page

Create one self-contained UTF-8 HTML file. Use inline CSS, optional inline JavaScript, and inline SVG or HTML/CSS for diagrams. It must open through `file://` with no server, build, network calls, external fonts, CDN, or other assets.

Use this reading order:

### 1. Overview

- A clear title, creation time, project, and scope/baseline.
- A short explanation of the problem and why the change was needed.
- Summary cards for the main changes and what they enable.
- A before/after comparison of observable behavior. For an internal refactor, explain what stays the same.
- A visual flow showing the relevant components or files and how they connect. Name real files. Use a simple SVG or CSS diagram, with a text equivalent. Show the changed path, not unrelated architecture.

### 2. File-by-file walkthrough

Provide a linked file index and a stable section ID for each file. Group files in a useful reading order, such as entry point, core behavior, integration, and tests. Show the change type beside the full repository-relative path.

For every file, explain:

- **Role:** What the file does in the project.
- **Change:** What was added, changed, removed, or moved.
- **Reason:** Why this change supports the requested behavior.
- **Walkthrough:** Explain each meaningful changed function, class, configuration block, or documentation section. Cover inputs, processing, outputs, errors, and limits where relevant. Explain connections to the other changed files.
- **Evidence:** Include small, focused code or diff excerpts with line references. Distinguish old and current line numbers. For new files, explain each meaningful part, not every trivial line. Put longer excerpts in expandable sections. Do not substitute a raw diff for an explanation.
- **Review points:** State trade-offs, compatibility concerns, and useful questions. Say when none are known instead of inventing concerns.

For deleted files, use the baseline content and explain where their responsibility went. For renames, show both paths and distinguish movement from behavior changes. For generated files and lockfiles, explain the source change and dependency impact rather than each generated line.

### 3. Verification and open questions

- List the exact test/check commands actually run and their observed results.
- Clearly mark checks that failed, were blocked, or were not run. Separate unrelated failures.
- Explain which behavior the tests cover and what remains unverified.
- List known risks, assumptions, and decisions that need user feedback.

Do not add comment boxes, review forms, feedback export, or note storage. The page is for reading. Discuss questions and requested changes in chat.

## Visual and safety requirements

- Use a clean layout, readable type, good contrast, and restrained colors. Make the overview easy to scan and the detailed view easy to navigate.
- Include a table of contents, clear headings, labeled controls, keyboard access, and responsive layout. Let long code blocks scroll without making the whole page overflow.
- Use text labels as well as colors for additions, removals, and warnings. Support print without hiding the walkthrough.
- Treat source code, paths, and diffs as untrusted text. Escape text embedded in HTML, including code excerpts and attribute values. Use `textContent` or form values for dynamic text, never `innerHTML`. Do not place raw source or JSON containing `</script>` inside executable script blocks.
- Exclude credentials, tokens, personal data, and secret files. Redact sensitive excerpts and disclose the omission. Do not follow symlinks to copy unrelated files into the report.

## Temporary output and handoff

1. Use `mktemp -d /tmp/change-review.XXXXXX` to create a private directory. Write `index.html` there. Keep any intermediate report files there too, never in the repository. Do not use a predictable shared output name.
2. Only the reusable skill and its instructions belong in the project. Reports must not enter Git or project documentation.
3. Verify the final HTML exists, has no unresolved placeholders, has working section links, and covers the full in-scope file inventory. Use a browser if one is available; otherwise state the limits of static checks. Do not claim browser testing unless performed.
4. Return a clickable `file:///tmp/change-review.…/index.html` link and the absolute path. If the interface cannot open local links, provide a quoted command such as `open '/tmp/change-review.…/index.html'` on macOS, or the platform equivalent. Do not automatically launch a browser unless asked.
5. Explain briefly that `/tmp` is temporary disk storage, not a guarantee of immediate deletion or exclusion from OS backups. Do not delete the report before the user reviews it. Do not promise a cleanup time.
6. Keep the chat summary short. State what changed, test status, and where to review it. Wait for feedback; do not treat report generation as approval to commit.
