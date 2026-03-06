---
name: pr-creator
description: "Safe and automated PR creation skill avoiding terminal hang by using file-based PR body arguments."
---

# PR Creator Skill

This skill ensures that Codex automatically creates Pull Requests (PRs) safely over the `gh` CLI without triggering interactive prompts that cause terminal freezes.

## Usage Trigger

Use this skill when you have completed a feature or bug fix and need to create a `Pull Request` and optionally merge it.

## Instructions

1. Make sure you are on a feature branch (e.g., `feat/<name>`).
2. Run standard tests to guarantee stability `python -m pytest tests/services/`.
3. Construct the PR description in a temporary file `.tmp/pr_body.md`.
4. Run `gh pr create` with `--body-file`.
5. Run `gh pr merge --squash` if the user gave explicit auto-merge instruction.
6. Clean up `.tmp/pr_body.md`.

## Example Execution Script (Internal Use)

```bash
# Example
echo "## Summary\nImplemented feature X." > .tmp/pr_body.md
gh pr create --head "$(git branch --show-current)" --base master --title "feat: added X" --body-file .tmp/pr_body.md
rm -f .tmp/pr_body.md
```
