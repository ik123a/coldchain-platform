# ColdChain Rescue — Agent Workspace Rules

## 1. Documentation & README Synchronization Invariant
- **Synchronize on Update**: Whenever a new feature, script, test suite milestone, demo recording, or deliverable is created or modified, you MUST inspect and update the corresponding `README.md` (and any related component guides in `docs/`) before concluding the task.
- **Factual Integrity**: Never report stale metrics. Verify exact numbers (e.g., test counts, route counts, video durations, blob scans) against live system probes before committing documentation.
- **Deliverables Visibility**: Any newly rendered video, benchmark report, or major artifact must be explicitly linked in `README.md` with its technical specifications (resolution, framerate, duration, file size).

## 2. Background Process & Daemon Discipline
- When launching development servers, API listeners, or long-running support processes (e.g., FastAPI on port 8000, Next.js on port 3000), ALWAYS set `IsDaemon: true` to prevent process termination when subshells exit.
- When running authenticated API calls in recording scripts, ensure bearer authentication tokens are acquired and forwarded in headers.

## 3. Security & Git Hygiene
- Run `tools/scan_history_secrets.py` before committing to guarantee 0 credential leaks across all git history blobs.
- Keep large scratch recordings (`.webm`) and cache directories properly gitignored.
