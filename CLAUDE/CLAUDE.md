# TrueRehab-RF (AEII 2026) — Claude instructions

@PROJECT.md
@CONTEXT.md

## Commands
None yet — no code in the project. Stack to be decided (see CONTEXT.md open questions).

## Session routine
1. **Start:** read `CLAUDE/CONTEXT.md` (and `git status -sb` once this is a git repo), then post a short kickoff:
   `Goal:` · `Done means:` · `Plan:` (3–5 lines total).
2. **Before non-trivial work** (new code, multi-file change, anything risky): write a proposal to `CLAUDE/plans/YYYY-MM-DD-<slug>.md` using `_TEMPLATE.md`, status `proposed`, and wait for OK. When a plan-mode plan is approved, copy it there with status `approved`.
3. **During:** one-line check-ins after each step. Verify before saying done.
4. **After each loop** (task finished or stopping point): run `/wrap-up` — report to `CLAUDE/output/`, update `CONTEXT.md`, log decisions in `DECISIONS.md`, set the plan's status to `done`.

## Conventions
- Source docs are mostly Thai; technical terms in English.
- Code conventions: unknown — set once the stack is chosen.

## Off-limits / ask first
- **Read-only:** `T-Proposal-Radar (1).docx`, `AEII 2026. TrueRehab-RF Poster.pdf`, `message-2.txt`. Never edit; write derived material elsewhere.
- **Never flash firmware** to the AWR1843BOOST or DCA1000EVM, and don't change their configuration, without asking first.

## Working with me
- Be direct and honest. Push back when you disagree or see a flaw — don't just agree.
- Plan before code.
- Keep updates short.
- I'm on macOS (zsh): one command per code block.
- I'm learning git: explain git commands in plain words; don't commit or push unless I ask.
