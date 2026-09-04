# PostgreSQL migration

1. Provision an empty PostgreSQL 15+ database.
2. Apply `migrations/postgres/001_initial.sql`, then each later numbered migration (including `002_ghost_revenue.sql`) with `psql`.
3. Set `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME` and restart the API.

The backend uses the same repository calls for SQLite and PostgreSQL. Existing SQLite data is not copied automatically: take a backup and use a controlled ETL/export for production cutover. Run the API test suite against SQLite as usual, then perform a staging smoke test against PostgreSQL before directing traffic to it.