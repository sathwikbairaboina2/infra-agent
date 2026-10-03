# ADR-0001: The LLM proposes whole files; git computes the diff

- Status: accepted (2026-10-04)

## Context
The design had the proposer emit a unified diff through `submit_patch`. Local 27B models often write broken hunk headers and wrong line counts. Then `git apply --check` fails, and that failure tells us nothing about what the model meant. We want the retries spent on policy feedback, not on diff syntax.

## Decision
The proposer has exactly three tools: `list_files`, `read_file` and `submit_change(files=[{path, content|null}], summary)`. `content` is the full new text of the file, and `null` deletes it. The patch step copies the target repo into a fresh scratch git repo and commits it as `base`. It then writes the files, runs `git add -A`, and takes `git diff --cached` as the reviewable diff. `patch_sha256` is the SHA-256 of that diff. Before anything is written, it enforces the path allowlist, the forbidden-content check and the `max_changed_lines` cap (from `git diff --cached --numstat`).

The prototype on 2026-10-04 showed `qwen3.8:27b` returning a correct `submit_change` call with a whole-file payload on the first try.

## Consequences
- The human still reviews a real unified diff, and its hash is in the audit log.
- Big files cost more tokens per proposal. v0.1 caps readable files at 64 KB.

## What I gave up
- Token-efficient diffs for large files.
- Letting the model make partial edits to files it has not fully read.
