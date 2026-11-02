# Cloud Run + Neon Migration Plan

> **For agentic workers:** Execute this plan sequentially. Do not shut down Fly.io before every cutover gate passes.

**Goal:** Move Ok's House Backend and its existing reservation data from Fly.io/SQLite to Cloud Run/Neon PostgreSQL without changing user-visible behavior.

**Architecture:** Keep Fly.io available as rollback while provisioning Neon PostgreSQL and deploying the existing FastAPI Docker app to Cloud Run in Seoul. Import a consistent SQLite snapshot, verify data and API behavior, update both GitHub Pages clients, then shut down Fly and remove the Fly account only after verification succeeds.

**Tech Stack:** FastAPI, SQLAlchemy, Docker, Cloud Run, Neon PostgreSQL, GitHub Pages, Fly.io CLI.

**Spec:** User request on 2026-11-02: copy the Fly database as-is; stop Fly and delete its account to prevent further charges; only perform shutdown and backend cutover after the existing Fly behavior has been reproduced and verified.

## Global Constraints

- Keep Fly.io running until the new service and imported database pass the cutover checks.
- Preserve all existing Fly secrets without printing their values or committing them.
- Preserve all SQLite tables, rows, primary keys, and stored values during migration.
- The two GitHub Pages clients must continue to call the same API paths with their existing API keys and origins.
- Do not delete the Fly account if any unrelated resource is found in its scope.
- Preserve pre-existing workspace changes, including the modified root `.gitignore`.
- Keep the DB dump and any secret material outside the repository and remove temporary copies after successful cutover.

## Review Focus

- Concurrent writes during final cutover: take a consistent online SQLite backup immediately before stopping Fly and compare per-table counts and canonical row digests; the final snapshot matched Neon.
- Neon scale-to-zero stale SQLAlchemy connections: enable `pool_pre_ping`, recycle connections before the idle interval, and use SQLAlchemy 2.0.33 or later.
- Cloud Run instance restarts would erase the current in-memory admin session set; persist sessions in PostgreSQL and expect admins to sign in again once after cutover.
- Cloud Run startup and port contract: bind to the configured `PORT` and confirm health checks pass on the deployed service.
- FCM OAuth credential and egress behavior: verify access-token refresh without sending a real notification to stored recipients.
- Frontend build configuration: ensure both GitHub Pages deployments embed the new API URL and retain the correct CORS origins.

### Task 1: Inventory and secure access

**Files:** None.

- [x] Confirm GCP project billing and Cloud Run/Secret Manager APIs; reauthenticate if the local token is expired.
- [x] Confirm the Neon account and create/use a free PostgreSQL project in a nearby region.
- [x] Confirm Fly account scope contains only the intended app and volume before any deletion.
- [x] Record the current API behavior and frontend GitHub Pages URLs without exposing credentials.

### Task 2: Prepare backend and database migration

**Files:**
- Modify: `app/db/database.py`
- Modify: `requirements.txt` and `pyproject.toml`
- Create: `scripts/migrate_sqlite_to_postgres.py` and `scripts/deploy_cloud_run.sh`
- Create: a repeatable SQLite-to-PostgreSQL data migration utility if needed

- [x] Configure SQLAlchemy PostgreSQL connections with pre-ping and safe pool recycling.
- [x] Ensure the container listens on Cloud Run's configured port.
- [x] Persist admin sessions in PostgreSQL so Cloud Run restarts do not invalidate new sessions.
- [x] Add a repeatable, non-overwriting SQLite-to-PostgreSQL importer with row-digest verification.
- [x] Create Neon schema and import a consistent snapshot with all original rows and IDs.
- [x] Compare schema, row counts, and canonical digests table-by-table.

### Task 3: Deploy and verify the new backend

**Files:** Backend deployment configuration and existing API test/verification paths.

- [x] Configure Cloud Run secrets and environment variables without checking secrets into Git.
- [x] Deploy to Cloud Run Seoul while Fly remains active.
- [x] Verify health, public reservation reads, login/auth flows, admin reads/writes on a staging copy, and FCM token/credential behavior.
- [x] Confirm error-free Neon wake-up and Cloud Run cold-start behavior.

### Task 4: Cut over GitHub Pages clients

**Files:**
- Modify: `../OksHouse-User` API base URL/build configuration
- Modify: `../OksHouse-Admin` API base URL/build configuration

- [x] Set each production build's API URL to Cloud Run while preserving API paths and keys.
- [x] Deploy both GitHub Pages clients and verify browser requests, CORS, authentication, reservations, and admin flows against the migrated DB.
- [x] Take a final consistent export immediately before stopping Fly; all three legacy tables matched Neon by row count and digest, so no additional import was needed.
- [x] Declare cutover passed only when data checks and behavior checks all pass.

### Task 5: Retire Fly only after cutover passes

**Files:** None.

- [x] Confirm Fly scope still contains only the intended app/resources.
- [x] Stop and remove the Fly app and its volume after successful cutover; confirm the app list is empty and the volume no longer exists.
- [ ] Delete the Fly account only if the account is dedicated to this project and Fly confirms no other resources or organizations would be affected.
- [x] Remove local temporary DB exports and report the new service URL, verified behaviors, and final Fly status.
