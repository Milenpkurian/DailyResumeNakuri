---
name: copilot-instructions
scope: workspace
description: "Project-wide instructions to guide the agent when authoring code, handling secrets, and editing files in this repository. Use when assisting with code changes, running scripts, or reading project files."
---

Purpose
-------
- Provide workspace-level instructions for the coding assistant so behavior is consistent across edits and suggestions.

Key rules
---------
- **Apply Scope**: These instructions apply to all files in the repository unless a file-specific instruction overrides them.
- **Formatting**: Use project style and minimal changes. Prefer small, focused edits.
- **Testing**: When edits affect runnable code, suggest or include minimal test steps and a short run command.

Secrets and environment variables (required rule)
-----------------------------------------------
- Never read, reference, or include content from files named `.env` or any file starting with `.env`.
- If a user query requires environment variables, ask the user to provide them manually or use clearly labeled placeholders in the form `ENV_VAR_PLACEHOLDER`.
- Do not attempt to load local environment files from the workspace or infer secret values from other files.

File safety
-----------
- Avoid modifying unrelated files. Keep changes surgical and explain any non-obvious edits.
- If a change may expose secrets, halt and request explicit user approval before proceeding.

Examples (prompts)
------------------
- "Update `updateDaily.py` to accept `username` and `password` from function args instead of hardcoding them; don't read `.env` files."
- "Create a minimal `requirements.txt` and include a command to run tests in the README. Ask for any missing env values as placeholders."

Notes for maintainers
--------------------
- To scope this instruction to specific file types later, add an `applyTo` YAML key with glob patterns (e.g., `applyTo: ['**/*.py']`).
- Keep the `description` clear and include trigger phrases used by team members.

Contact
-------
- If you want this changed (scope, wording, or additional rules), update this file and commit; the agent will pick up revisions on next session.
