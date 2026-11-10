# Project: Nexora WhatsApp Menu Bot

Build a multilingual WhatsApp menu bot for Nexora Consulting.

## Project Rules

- V1 is a deterministic menu-based bot, NOT a RAG or LLM chatbot.
- Support English and Arabic.
- Use FastAPI, PostgreSQL and Meta WhatsApp Cloud API.
- Keep business logic separate from API routes.
- Store menu content and translations in the database.
- Use stable action IDs for routing, never translated button titles.
- Keep the code simple, clean and minimal.

## 1. Before Coding
- Read this file and relevant project documentation.
- Inspect existing code before making changes.
- Follow the existing architecture.
- Ask if an important requirement is unclear.

## 2. Code Quality
- Write the minimum code needed.
- Avoid unnecessary abstractions, classes and files.
- Reuse existing functions instead of duplicating logic.
- Avoid unnecessary dependencies.
- Initialize reusable resources only once.

## 3. Security
- Never hardcode API keys or credentials.
- Use environment variables.
- Validate incoming requests and user input.
- Verify webhook requests.
- Never expose sensitive customer information.

## 4. Debugging & Testing
- Identify the root cause before changing code.
- Fix the actual issue instead of hiding errors.
- Run relevant tests after changes.
- Never claim a test passed unless you actually ran it.

## 5. Change Management
- Make only the changes required for the task.
- Do not modify unrelated files.
- Do not overwrite existing work.
- Check Git status before major changes.
- Do not commit, push, reset or rebase without permission.

## 6. Token Efficiency
- Keep responses short and clear.
- Avoid unnecessary explanations.
- Do not generate documentation unless requested or necessary.
- Do not dump entire files when a small change is sufficient.
- Ask before making large or irreversible changes.

## 7. Scope

- WhatsApp is the only channel; there is no web frontend.
- Backend lives in `backend/`; architecture is described in `docs/architecture.md`.

## Completion Report

After completing a task, briefly mention:
1. What changed.
2. Which files were modified.
3. Tests performed.
4. Any remaining issues.