# General Coding Guidelines

- Rehydrate each session with `.github/work_routine.md` and `planning/change_log.md`, then run `git status -sb` and work inside the `i4g` Conda env (`conda run -n i4g ...`).
- Prefer configuration-driven code: fetch settings through `i4g.settings.get_settings()` and honor the environment-aware factories in `src/i4g/services/factories.py`.
- Keep edits ASCII unless a file already depends on Unicode, and never revert user-authored changes without explicit direction.
- Run relevant tests or smoke flows (`pytest tests/unit`, targeted `tests/adhoc/` scripts, `python scripts/bootstrap_local_sandbox.py --reset`) before shipping changes; note any skipped suites in summaries.
- Keep documentation and planning artifacts in sync with code—material changes should update `planning/change_log.md`, `docs/architecture.md`, or `docs/dev_guide.md` as appropriate.

## Python Style
- Use full type hints on new or modified Python code.
- Write Google-style docstrings and concise explanatory comments when logic is non-obvious.
- Format with Black and manage imports with isort; both use a shared 120-character line limit.

## Collaboration & Review
- Treat collaboration as a two-person team (you + Copilot); you own prioritization and approvals.
- When preparing to merge, request (or expect) a “picky reviewer” pass: verify style conformance, remove dead code, ensure tests/docs reflect behavior across all repositories, and confirm deployment instructions (e.g., Cloud Run) are accurate.
