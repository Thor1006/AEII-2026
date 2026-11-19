# Plan: Isolated public data database trial

**Status:** done
**Date:** 2026-11-09

## Why
The user asked to try saving the researched public data online, separated from real project data. They confirmed Supabase and then explicitly requested using the existing AEII - 2026 project because a new project could not be created. The final authorized design uses a dedicated `reference_playground` schema inside that existing project. No paid upgrade, main application integration or unrelated-project changes are authorized.

## Approach
1. Inspect current repository/data and available database providers.
2. Prepare a small versioned import bundle in `sandbox/public-data-playground/` with source catalog/file references and one public participant's fatigue labels.
3. Verify label reconstruction, constraints, foreign keys, repeatability and source hashes locally.
4. Use only the explicitly authorized AEII - 2026 project (`dpzmtmgfqudhfgykkcbf`), creating/using schema `reference_playground` exclusively. Browser login was completed by the user; no new account credentials were collected.
5. Import and verify through the project's SQL editor and Table Editor. Existing organization permissions govern collaborator access; no new invitations were sent.

## Files touched
- `sandbox/public-data-playground/` — isolated preparation source, README, verified deployment manifest, ignored generated SQL/data.
- `CLAUDE/output/2026-11-09-public-data-playground_v01.md` — progress/verification and next action.
- `CLAUDE/CONTEXT.md`, `CLAUDE/DECISIONS.md` — trial scope and status.

## Risks / needs OK
- Same-project schema separation is logical, not physical. It shares Supabase project resources and organization-level administrators.
- No fees, main application changes, public sharing, new account credentials or invitations.
- Online import and verification completed; source binaries remain local and are linked, not stored as SQL blobs.

## How we'll verify
- Local checks passed: 5 datasets, 4 file references, 12 trials, 36 label segments covering 200,581 original labels; exact reconstruction, source hashes, foreign keys and idempotency.
- Trial 11's one non-increasing time step is retained and flagged, not repaired.
- Verified on the actual Free project: expected counts and source fingerprints, four RLS-enabled tables, no anonymous/app-user schema usage, zero training-eligible records, and `public` table count unchanged at zero.
- Opened `reference_playground` in Table Editor and retained its live URL.
