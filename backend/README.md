# Backend

The Django base uses SQLite and serves a read-only health check at **/api/health/**. The identity module owns sign-in, account roles, setup links, audit events, and workspace access. Install the pinned dependencies into a virtual environment, apply migrations, and bootstrap the first Admin from the host. DuckDB, openpyxl, psycopg, and Gunicorn are installed for later warehouse and hosting work. See the [local setup](../README.md#run-locally).
