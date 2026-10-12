---
name: wrap-up
description: End-of-loop wrap-up for this project — writes a report to CLAUDE/output/, updates CLAUDE/CONTEXT.md, logs decisions, and closes out plans. Use when the user types /wrap-up, says "wrap up", "we're done", "end the session", or when a task in this project is finished.
---

# Wrap-up

1. **Gather facts** (don't guess): run `git status -sb` and `git diff --stat` if this is a git repo (otherwise list changed files with `ls -lt`); recall what was done and how it was verified this loop.
2. **Write the report** to `CLAUDE/output/YYYY-MM-DD-HHMM-<slug>.md` using `CLAUDE/output/_TEMPLATE.md`. Use the real current date/time. Short and factual.
3. **Update `CLAUDE/CONTEXT.md`:**
   - Set "Last updated".
   - Rewrite "Current focus" and "Next steps" to reflect now.
   - Add one line to "Recent changes" linking the report; keep only the ~5 most recent.
   - Update "Open questions".
4. **Decisions:** if a real choice was made (library, structure, approach), add an entry at the top of `CLAUDE/DECISIONS.md`.
5. **Plans:** if this loop implemented a file in `CLAUDE/plans/`, set its status to `done` (or note what's left).
6. **Reply** with a 3–5 line summary: result, report link, next step, and whether there's uncommitted work (with the git command to commit it, explained in plain words — but don't run it unless asked).
