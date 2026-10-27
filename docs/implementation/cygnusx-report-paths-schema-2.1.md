# Report paths schema 2.1 implementation record

## Scope

This change makes `report.paths.json` the report metadata source for report registration and Copilot snapshots. It preserves the P1 preview grant and sandboxed HTML preview path, and preserves the P2 three read-only Copilot tools and the preview `postMessage` anchor bridge.

## Implementation

- Added report metadata columns and the `report_id` project index through Alembic revision `reportpaths01`; the existing required `ReportModel.user_id` remains the owner. `project_user_id` records the project's owning user for cross-checks.
- Added a contract parser for sidecar schema 2.0.0 and 2.1.0. Schema 2.1 requires project owner identity and validates the report/task binding, indexed file roles, descriptions, formats, and normalized relative paths.
- At completion, report registration writes or validates the sidecar and persists project identity, statistics, enrichment summary, and indexed files. New reports are emitted by the RNAFlow and ATACFlow report steps as 2.0-compatible sidecars, then bound and promoted by the platform to 2.1. Parse failures mark the report failed and retain a bounded error summary.
- Copilot metadata snapshots read validated 2.1 metadata. Legacy 2.0 reports use persisted Task and file-index fallback and carry `legacy_degraded` status. `query_project_results` accepts a file `role` and reads only matching registered CSV/TSV artifacts; `list_artifacts` also uses the persisted index. Query-time directory traversal is not used.
- File access rejects absolute and parent-traversal paths and reads through a pinned, no-follow file descriptor. Report and project ownership are checked against the authenticated user.
- Added `scripts/backfill_report_paths_registry.py`, which audits an explicitly supplied report root and database and emits `success.json`, `failed.json`, and `manual.json`. It requires explicit paths and defaults to audit mode; applying changes requires `--apply`.
- Removed the report mock data module. A source scan found no production references to `mockData`, `mockReports`, or `mockStats` under `frontend/src`.

## Verification

- `uv run pytest tests/integration/test_report_copilot_isolated.py -q`: 8 passed.
- `frontend` type check and targeted report component tests passed (2 files, 9 tests).
- Ruff and mypy passed for the changed Python modules and script.
- `uv run python scripts/check_migrations.py` passed static migration checks.
- RNAFlow and ATACFlow sidecar helpers passed `py_compile` and Ruff. Snakemake dry-runs could not complete because the configured reference genome files are absent on this machine; this is not evidence of full workflow execution.
- No real report-root backfill, production database update, or live model conversation was performed. Production report correctness and human acceptance remain outstanding.

## Submodule commits

- RNAFlow: `951f4f2` (`feat(report): emit BioReport paths sidecar`)
- ATACFlow: `e4e2805` (`feat(report): emit BioReport paths sidecar`)
