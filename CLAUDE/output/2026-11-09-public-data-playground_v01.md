# Public reference data trial on Supabase

Date: 9 November 2026

## Result

Saved the public-reference trial in the existing **AEII - 2026** Supabase project, ID `dpzmtmgfqudhfgykkcbf`, organization GI 04. The user explicitly chose the existing project after being unable to create a new one. All experiment tables are in **`reference_playground`**, providing logical schema separation within the same database/project. It is not a separate physical database.

[Open the saved dataset table](https://supabase.com/dashboard/project/dpzmtmgfqudhfgykkcbf/editor/17646?schema=reference_playground).

| Table | Rows | Contents |
|---|---:|---|
| datasets | 5 | Reviewed public datasets, provenance, labels and license status |
| file_references | 4 | Original filename, size, hash and download URL; binaries remain local |
| fatigue_trials | 12 | Minho published subject 1 trial summaries and source CSV hashes |
| fatigue_segments | 36 | Constant-label runs representing 200,581 original self-perceived-fatigue observations |

This saves actual external reference labels as well as source records. Full raw sEMG, clinical MAT binaries and all individual timestamps have not been uploaded. Full sample files remain under the existing ignored `model/data/external_reference_v01/`.

## Isolation and access

- Only the `reference_playground` schema was created and seeded. The `public` schema had zero tables before and after the import; CoCommit was not modified.
- No recorder, model, frontend, deployment or production data path/configuration was changed. Every dataset row has `training_eligible=false`, enforced by a constraint.
- All four tables have RLS enabled. The `anon` and `authenticated` API roles have no schema USAGE, and no public access policies were created. The custom schema was not added to exposed API schemas.
- Authorized existing GI 04 organization/project members can inspect the data through Supabase's dashboard according to their role. No invitations, credentials, public sharing, paid upgrades or main-application integration were added.

## Verification

The local standard-library preparation checks source SHA-256, foreign keys, repeated seed import, constraints and exact reconstruction of all original label sequences from their segments. Source times were not resampled or sorted. Trial 11 contains one non-increasing timestamp step; its quality fields preserve that fact.

The import was executed in Supabase's authenticated SQL editor and verified on the actual PostgreSQL database. Readback returned the expected counts and these source fingerprints, with `ORDER BY id COLLATE "C"` to match the local ordering:

- Segment identity/index/label MD5: `7ad4497513e4b9cdbc28405885a81f73`.
- Trial identity/count/source-hash MD5: `ed131d37d5eb332e94a4a954505bb6c2`.
- File identity/size/source-hash MD5: `3532778761ace9b8bcb8b3e9018b8ed3`.
- Trial counts and segment lengths both total 200,581 observations.
- Four RLS-enabled tables; anonymous/app-user schema usage false; zero training-eligible rows; public table count zero.

The Table Editor visibly showed schema `reference_playground`, all four tables and all five dataset records.

## Reproducibility and handoff

`sandbox/public-data-playground/` contains numbered preparation source, README, plan/deployment details, and an ignored `generated/v01/` SQL/JSON import bundle. The bundle uses only reviewed public data and published participant codes. No authentication credentials are stored.

Sources and interpretation limits remain in [the clinical-data review](2026-11-09-clinical-data-sources_v01.md). The data are external examples, not measurements from TrueRehab-RF users or validated radar training data. No model training or threshold change was performed. No Git commit or push.
