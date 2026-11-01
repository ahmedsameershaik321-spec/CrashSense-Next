@'
# CrashSense - Claude Instructions

Before doing any work:

1. Read the complete root AGENTS.md.
2. Read docs/ARCHITECTURE.md.
3. Read docs/TASKS.md.
4. Follow all project security and development rules.

AGENTS.md is the authoritative shared instruction file.

Do not independently change the architecture.
Do not rewrite unrelated files.
Do not fabricate test results.
Implement only the explicitly assigned task.

Before editing, explain the proposed changes.
After editing, run relevant tests and report actual results.
'@ | Set-Content -Encoding utf8 CLAUDE.md