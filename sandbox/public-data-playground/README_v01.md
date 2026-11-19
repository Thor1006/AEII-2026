# Public data playground

An online database trial for TrueRehab-RF public reference datasets. At the user's explicit request, it lives in the existing **AEII - 2026** Supabase project, in its own schema named `reference_playground`.

**Current status: imported into Supabase and verified.** This is logical separation within the same PostgreSQL database/project, not a separate physical database. Only `reference_playground` was created/seeded. The project's `public` schema had zero tables before import and still has zero. No current application configuration or training input was changed.

[Open the trial tables](https://supabase.com/dashboard/project/dpzmtmgfqudhfgykkcbf/editor?schema=reference_playground). Existing authorized members of the GI 04 organization can inspect them through the Supabase dashboard according to their role. No new invitations or public API access were added.

## Prepared data

- Five source-dataset records, including links, population, modalities, labels and reuse status.
- Four original-file references, with byte counts, SHA-256 and publisher download URLs. These records are references to existing local files; the binary files have not been uploaded to Supabase Storage.
- Twelve Minho trials for published subject 1. This is a healthy research participant, not a patient tested by TrueRehab-RF.
- Thirty-six constant-label segments covering 200,581 source fatigue-label observations. Every label can be reconstructed in original sample order. The segment boundaries retain actual first/last source timestamps; this is not an import of every raw timestamp or any sEMG signal.

All records have an external-reference purpose. The dataset table enforces `training_eligible = false`. The experiment does not feed the radar network, recorder, dashboard or deployment database.

## Files

- `prepare_v01.py`: standard-library Python builder. Reads only the reviewed public catalog and sample copies; writes only a new `generated/v01/` directory beneath itself. No network calls or credentials.
- `generated/v01/01_schema_v01.sql`: isolated schema and four tables, row security enabled, no anonymous/app-user access granted.
- `generated/v01/02_seed_v01.sql`: source metadata and actual sample labels. Re-running the seed preserves existing IDs without duplication.
- `generated/v01/03_queries_v01.sql`: counts, biceps-trial labels, source/license lookup and timestamp anomaly query.
- `generated/v01/seed_data_v01.json`: portable equivalent of the seed records.
- `generated/v01/validation_v01.json`: expected counts and the local validation boundary.
- `deployment_v01.json`: actual provisioning/import status; update only from confirmed provider results.

Generated data stay out of Git through this folder's `.gitignore`. Existing sample files remain in `model/data/external_reference_v01/`, also ignored. The source catalog is `CLAUDE/output/2026-11-09-clinical-data-sources_v01.json`.

## Import into the isolated online project

1. Verify the selected project is the user-authorized `AEII - 2026`, ID `dpzmtmgfqudhfgykkcbf`. Use only schema `reference_playground`. Do not apply the scripts to CoCommit or another project.
2. Collaboration follows existing project/organization permissions. Obtain recipient identities and access requirements before sending any new invitation. The user chose the existing project after a new project could not be created.
3. Run `01_schema_v01.sql`, then `02_seed_v01.sql` using this project's owner SQL editor/authorized connector.
4. Run `03_queries_v01.sql`. Counts must be 5 datasets, 4 file references, 12 trials and 36 segments. Check source links and licenses, including the biceps-specific Trials 5 and 6.
5. Cloud verification passed: all four tables have RLS enabled; `anon` and `authenticated` have no schema USAGE; zero dataset records are training-eligible. Dashboard access remains governed by existing organization roles.
6. Deployment details and live verification counts are recorded in `deployment_v01.json`. Do not connect the main application's training or live session paths to this experimental schema.

The standard SQL/data subset passed an in-memory SQLite check for foreign keys, repeatable seed import, constraints and exact reconstruction of original label sequences. The actual Supabase PostgreSQL import also passed row counts, source fingerprints, reference-only status and schema/RLS access checks. Verification hashes use `ORDER BY id COLLATE "C"` to match the local deterministic ordering.

## Source timing and meaning

Nominal sampling is 50 Hz, but many source timestamps jitter by about a millisecond. Trial 11 contains one non-increasing timestamp step; its maximum deviation from the nominal grid is about 81 ms. The preparation keeps source row order, actual segment-boundary times and anomaly counts. It does not sort, resample or repair the original data. The original ZIP and CSV hashes remain available for a later full timestamp import.

The 0–2 labels represent self-perceived fatigue. They are not a clinical diagnosis, muscle force, a validated radar fatigue percentage or compensation labels. Full raw sEMG is in the separate publisher archive and is not included in this trial.

## Rebuild

From the repository root, with the reviewed public samples already present:

```text
python sandbox/public-data-playground/prepare_v01.py
```

The builder refuses to overwrite `generated/v01/`; use a new numbered generation for a requested revision. It does not create or contact an online database.

## Sources

- [Public-data research and source links](../../CLAUDE/output/2026-11-09-clinical-data-sources_v01.md).
- Minho data: Cerqueira, Vilas-Boas, Figueiredo and Santos, [Zenodo v2, DOI 10.5281/zenodo.14182446](https://zenodo.org/records/14182446), CC BY 4.0. Labels retain their original values.
- Clinical sample reference: Lucchetti, Bailo and Lencioni, [ST03 DOI 10.6084/m9.figshare.28596086.v1](https://figshare.com/articles/dataset/ST_03/28596086), CC BY 4.0; binary sample remains local.
- [Supabase pricing](https://supabase.com/pricing), checked 9 Nov 2026: Free includes 500 MB database and 1 GB file storage, with two active Free projects and pausing after a week of inactivity.
- [Tables](https://supabase.com/docs/guides/database/tables), [row security](https://supabase.com/docs/guides/database/postgres/row-level-security) and [organization access](https://supabase.com/docs/guides/platform/access-control).
