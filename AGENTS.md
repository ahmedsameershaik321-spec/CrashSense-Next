
# CrashSense — AI Development Instructions

## 1. Project Identity

Project: CrashSense
Repository: CrashSense-Next
Primary branch: main

CrashSense is an intelligent road accident detection and emergency response platform.

Read these documents before development:

1. docs/ARCHITECTURE.md
2. docs/TASKS.md
3. README.md

AGENTS.md is the authoritative shared AI development instruction file.

## 2. AI Development Responsibilities

All AI assistants must follow the same architecture.

ChatGPT:
- System architecture.
- Technical planning.
- Code review.
- Debugging strategy.
- Security review.

Claude:
- Primary implementation.
- Complex backend and frontend development.
- Refactoring.
- Integration.

Gemini:
- Technical research.
- Dataset research.
- Documentation.
- Technology comparisons.

DeepSeek:
- Algorithm analysis.
- Optimization.
- Debugging.
- Independent code review.

GitHub Copilot:
- Inline code completion.
- Small code modifications.
- Development assistance.

Bolt:
- UI prototyping.
- Frontend design exploration.

Other OpenAI models:
- Independent reasoning.
- Implementation review.
- Testing strategy.

These are suggested responsibilities, not permissions to modify unrelated modules.

## 3. Mandatory Development Rules

Before changing files:

1. Inspect the existing implementation.
2. Read relevant documentation.
3. Understand dependencies.
4. Identify affected modules.
5. Explain the proposed changes.

During development:

1. Modify only files relevant to the assigned task.
2. Preserve existing functionality.
3. Follow established naming conventions.
4. Use modular and maintainable code.
5. Validate input.
6. Handle errors properly.
7. Write appropriate tests.
8. Avoid unnecessary dependencies.
9. Never fabricate test results.

After development:

1. Run relevant tests.
2. Fix discovered failures.
3. Report changed files.
4. Report test results.
5. Document unfinished work.
6. Update docs/TASKS.md when a task is verified.

## 4. Security Rules

Never:

- Hardcode passwords or API keys.
- Commit .env files.
- Expose secrets to frontend code.
- Trust client-side authorization.
- Allow public registration to assign privileged roles.
- Allow pending accounts to access protected videos.
- Allow pending accounts to access operational endpoints.
- Disable authentication to make tests pass.
- Send real emergency notifications during development without authorization.

Public registration must create a pending account.

Only authorized administrators can approve monitoring_operator or administrator roles.

All protected resources require server-side authorization.

## 5. Architecture Rules

Frontend:
- Next.js
- React
- TypeScript
- Tailwind CSS

Backend:
- Python 3.11
- FastAPI
- SQLAlchemy
- PostgreSQL

ML Engine:
- PyTorch
- Ultralytics YOLO
- OpenCV
- ByteTrack

Follow docs/ARCHITECTURE.md for all architectural decisions.

Do not introduce a new framework or major dependency without approval.

## 6. Testing Rules

Every feature must have appropriate tests.

Backend:
- Unit tests.
- API integration tests.
- Authentication tests.
- Authorization tests.

Frontend:
- Component tests.
- UI interaction tests.
- API integration tests.

ML:
- Detection evaluation.
- False-positive evaluation.
- Model performance evaluation.

Never claim that a feature works without executing its relevant tests.

## 7. Git Rules

- Primary branch: main.
- Never force-push.
- Never overwrite unrelated changes.
- Never commit secrets.
- Prefer small, meaningful commits.
- Inspect git diff before committing.
- Do not push changes without user authorization.

## 8. Collaboration Protocol

Before implementation, report:

- Assigned task.
- Existing files inspected.
- Proposed files to modify.
- Implementation approach.
- Tests required.

After implementation, report:

- Files created.
- Files modified.
- Important design decisions.
- Tests executed.
- Actual test results.
- Remaining issues.

Only implement the explicitly assigned task.

## 9. Completion Criteria

A feature is complete only when:

- Implementation exists.
- Relevant tests pass.
- Security requirements are satisfied.
- Documentation is updated.
- No unrelated functionality is broken.
