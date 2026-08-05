# Vestige Admin Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert the existing CLI pipeline and Bee React Admin template into a local Admin product for managing companies, discovery runs, persisted results, and run comparisons.

**Architecture:** Use a modular monolith. FastAPI exposes REST endpoints, SQLAlchemy persists SQLite records, and a separate worker process claims queued runs and invokes the existing discovery pipeline. React Admin consumes the API; authentication and multi-workspace isolation are deferred.

**Tech Stack:** Python 3.10, FastAPI, SQLAlchemy 2, SQLite, Pydantic 2, pytest, React 19, TypeScript, Vite, Ant Design, TanStack Query.

---

## Scope

### Included

- Dashboard metrics and recent runs.
- Company CRUD with identity anchors.
- Create, list, inspect, cancel, and retry discovery runs.
- Persist run status, settings snapshot, sources, errors, and timing.
- Compare two successful runs for added, removed, reclassified, and confidence-changed sources.
- Download the existing Excel export by run ID.
- Local development without authentication.

### Deferred

- User login, workspaces, API keys, and role permissions.
- Gold-set evaluation UI.
- Redis/Celery, distributed workers, and multi-host deployment.
- Relationship graph UI and vector storage.

## API Contract

- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/companies`
- `POST /api/companies`
- `GET /api/companies/{company_id}`
- `PUT /api/companies/{company_id}`
- `DELETE /api/companies/{company_id}`
- `POST /api/companies/{company_id}/runs`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `POST /api/runs/{run_id}/cancel`
- `POST /api/runs/{run_id}/retry`
- `GET /api/runs/{run_id}/sources`
- `GET /api/runs/{run_id}/export`
- `GET /api/companies/{company_id}/compare?base_run_id=...&target_run_id=...`

Responses use `{ "code": 0, "message": "success", "data": ... }` to match the existing Admin API client.

## Data Model

- `companies`: identity anchor and lifecycle timestamps.
- `runs`: company, status, stage, progress, settings snapshot, timestamps, error, previous run.
- `run_sources`: canonical URL, source classification, confidence, discovery metadata, extraction details.
- `run_events`: ordered progress and diagnostic events.

Run statuses: `queued`, `running`, `succeeded`, `failed`, `cancel_requested`, `cancelled`.

## Task 1: Backend Foundation

**Files:**
- Create: `server/__init__.py`
- Create: `server/app.py`
- Create: `server/database.py`
- Create: `server/models.py`
- Create: `server/schemas.py`
- Create: `server/responses.py`
- Test: `tests/api/test_health.py`
- Modify: `requirements.txt`

**Steps:**
1. Write a failing API health test using FastAPI TestClient and a temporary SQLite database.
2. Run `pytest tests/api/test_health.py -q`; expect failure because `server.app` does not exist.
3. Implement application factory, database session lifecycle, tables, and response envelope.
4. Run the test and full Python suite.

## Task 2: Company CRUD

**Files:**
- Create: `server/repositories/companies.py`
- Create: `server/routes/companies.py`
- Test: `tests/api/test_companies.py`

**Steps:**
1. Test create/list/update/delete and validation of name/domain/aliases.
2. Verify tests fail.
3. Implement repository and REST routes.
4. Verify company tests and full suite pass.

## Task 3: Run Queue and Status API

**Files:**
- Create: `server/repositories/runs.py`
- Create: `server/routes/runs.py`
- Create: `server/services/run_queue.py`
- Test: `tests/api/test_runs.py`

**Steps:**
1. Test run creation, status transitions, cancel, retry, and company scoping.
2. Verify tests fail.
3. Implement queue records and API routes.
4. Verify tests pass.

## Task 4: Pipeline Application Service and Worker

**Files:**
- Create: `application/run_company.py`
- Create: `server/worker.py`
- Modify: `pipeline.py`
- Modify: `export/excel.py`
- Test: `tests/test_run_company_service.py`
- Test: `tests/api/test_worker.py`

**Steps:**
1. Test that the application service returns structured results without mandatory printing or export.
2. Test worker atomic claim and success/failure persistence.
3. Verify tests fail.
4. Refactor pipeline configuration into request-scoped settings while keeping CLI compatibility.
5. Persist source rows and run events; export to run-specific paths.
6. Verify service, worker, and regression suites.

## Task 5: Run Comparison

**Files:**
- Create: `application/compare_runs.py`
- Create: `server/routes/comparisons.py`
- Test: `tests/api/test_comparisons.py`

**Steps:**
1. Test added, removed, unchanged, reclassified, and confidence-changed canonical URLs.
2. Verify tests fail.
3. Implement pure comparison logic and endpoint.
4. Verify tests pass.

## Task 6: Admin Product Shell

**Files:**
- Modify: `admin/src/global-config.ts`
- Modify: `admin/src/main.tsx`
- Modify: `admin/src/routes/sections/dashboard/frontend.tsx`
- Modify: `admin/src/layouts/dashboard/nav/nav-data/nav-data-frontend.tsx`
- Modify: `admin/src/routes/components/login-auth-guard.tsx`
- Create: `admin/src/types/vestige.ts`
- Create: `admin/src/api/services/vestigeService.ts`
- Modify: `admin/vite.config.ts`

**Steps:**
1. Add frontend test tooling and write tests for API mapping and product routes.
2. Verify tests fail against template routes.
3. Rename product, disable MSW/auth in local mode, replace navigation and routes, point Vite proxy at FastAPI.
4. Verify frontend tests and build.

## Task 7: Admin Core Pages

**Files:**
- Create: `admin/src/pages/vestige/dashboard/index.tsx`
- Create: `admin/src/pages/vestige/companies/index.tsx`
- Create: `admin/src/pages/vestige/companies/company-form.tsx`
- Create: `admin/src/pages/vestige/runs/index.tsx`
- Create: `admin/src/pages/vestige/runs/detail.tsx`
- Create: `admin/src/pages/vestige/companies/compare.tsx`

**Steps:**
1. Write component tests for empty, loading, failure, and populated states.
2. Verify tests fail.
3. Implement dashboard, CRUD, run controls, source table, and comparison views with TanStack Query.
4. Verify tests and production build.

## Task 8: Integration and Operations

**Files:**
- Create: `scripts/run-api.sh`
- Create: `scripts/run-worker.sh`
- Modify: `README.md`
- Modify: `.env.example`
- Test: `tests/api/test_end_to_end.py`

**Steps:**
1. Test API create company → queue run → mocked worker → persisted sources → compare.
2. Verify failure before integration glue.
3. Add startup scripts, CORS/local configuration, migration/bootstrap command, and documentation.
4. Run `pytest -q`.
5. Run `pnpm --dir admin build`.

## Verification Gates

- All Python tests pass.
- Admin TypeScript build passes.
- API can create a company and queue a run.
- Worker survives restart because queued/running state is persisted.
- Re-running a company creates a new immutable result version.
- Comparison is based on canonical URL, not display URL.
- Existing CLI entry remains functional.

