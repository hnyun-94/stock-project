---
name: e2e-test-suite
description: "Test execution skill forcing Codex to run both unit tests and e2e-dryrun tests before commits to ensure zero regression."
---

# E2E Test Suite Skill

This skill automates the test phase to strictly guarantee safe behavior for `models.py` or `.local/DEPENDENCY_MAP.md` changes.

## Usage Trigger

Use this skill _before_ any git commit or immediately after modifying core configuration logic (`ai_summarizer.py`, `database.py`, `models.py`).

## Instructions

1. Run standard unit tests for isolation logic:
   `python -m pytest tests/services/ -v -q`
2. Run the E2E dry-run test to check system integration flow safely:
   `python -m pytest tests/test_e2e_dryrun.py -v -q`
3. Analyze output. If anything fails, DO NOT COMMIT. Fix the bug, optionally updating `errorCase/` and `todo/todo.md`.
4. Proceed to commit only on 100% green output.

## Essential Command

```bash
python -m pytest tests/services/ tests/test_e2e_dryrun.py -v -q
```
