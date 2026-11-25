# AutumnLeaf MVP Specification

## 1. Product concept

AutumnLeaf is a self-hosted web workspace for learning data engineering. A user can sign in, load a retail CSV, run ETL or ELT one step at a time, or hand an ELT run to local Airflow and dbt. The roadmap adds a SQL worksheet, a dashboard, and an Excel export backed by the same published data.

The software is intended to be open source. Accounts, uploaded files, and warehouse data are private to each installation. Publishing the source code does not open registration or grant access to a running installation.

## 2. Accounts and permissions

### 2.1 Sign-in and access

Access is by invitation, with no public registration or required Google or GitHub account. The instance operator handles account setup and recovery privately. Disabling an account revokes its sessions without deleting its data.

### 2.2 Role-based access control

| Action | Admin | Member |
| --- | --- | --- |
| Use personal warehouse, pipeline lab, dashboard, and exports | Yes | Yes |
| See **Accounts** and its management controls | Yes | No |
| Manage access for other accounts | Yes | No |
| Open another user's warehouse, runs, or exports | No | No |

Account management is not data access. An Admin can see account details and status, not another user's imported rows through the app. Every protected request checks permissions on the server. Signed-out visitors are sent to sign-in. A signed-in Member visiting an account-management URL or submitting the corresponding request directly receives **403 Forbidden**. Workspace records and export downloads are restricted to their owner. These controls do not protect data from someone who already controls the host or its backups.

## 3. Warehouse and pipeline workflow

### 3.1 First dataset

The first workflow uses synthetic retail orders. A CSV contains **order_id**, **order_date**, and **amount**. Each file represents a complete export for one month, not a partial update. The load checks required columns, duplicate order IDs, dates within the selected month, and valid amounts. Currency is stored as a fixed-precision decimal, not a floating-point value.

### 3.2 ETL and ELT

| Step | ETL | ELT |
| --- | --- | --- |
| Extract | Read the uploaded CSV with Python. | Read the same uploaded CSV. |
| Next step | Transform in Python: validate IDs and dates, normalize amounts, and produce clean rows. | Load source field values into **raw.orders** before cleaning them. |
| Final step | Load the clean rows into DuckDB. | Transform in DuckDB using SQL and publish the clean rows. |

The lab keeps ETL and ELT results separate so one run cannot overwrite the other. The user can inspect the files, raw data where applicable, clean rows, and revenue totals after each step. The hosted runner executes only pipeline code and SQL deployed with the application. Users edit their own Python scripts and pipeline SQL in a local checkout for unrestricted experiments. Hosting the app does not give it access to scripts on the user's laptop.

When local automation is configured, Airflow loads a fresh ELT batch into a separate DuckDB database and runs the deployed dbt models and tests. Django imports the successful result. Corrections still require approval before publication, and failed runs leave the last published batch intact.

### 3.3 Repeated and corrected batches

- **Unchanged input:** Within a workspace and pipeline mode, resubmitting the same file for the same month does not add rows or change totals.
- **Corrected input:** A different file for the same month requires an explicit replacement. The app previews the change in row count and revenue. A valid replacement replaces the whole month, including rows removed from the new file.
- **Failed input:** A bad file does not change the last published batch. For ELT, source rows that loaded successfully can remain available for debugging if validation later fails. Publication and its success record commit together.
- **Run history:** Store the mode, batch month, input filename and checksum, timestamp, row counts, outcome, and a short failure reason. Show affected row numbers and reasons where available, without logging private row contents in server logs.

## 4. Browser workspace and reporting

| Screen | MVP behavior |
| --- | --- |
| **Data Explorer** | Browse raw, staging, and reporting objects; inspect columns and preview rows. |
| **SQL Workspace** | Write and save SQL, run it on a bounded copy of a permitted dataset, and see results or errors below the editor. |
| **Pipeline Lab** | Upload a CSV, choose ETL or ELT, run each step, inspect errors, and compare clean rows and totals. |
| **Reports** | Show one revenue total, one daily sales chart, a date filter, and an Excel export from **mart.daily_sales**. |
| **Accounts** | Admin-only page for provisioning accounts and managing access. |

Use the desktop-first layout, autumn palette, and interaction patterns in the [interface design specification](DESIGN.md). The Excel download is a snapshot of the selected report data, not a live Excel connection.

## 5. Architecture, deployment, and open source

- **Web app:** Build the browser interface with React, TypeScript, Tailwind CSS, and Vite. Use Python and Django for the API, built-in authentication, sessions, and authorization. Store account and application settings in SQLite locally, with PostgreSQL for the hosted installation. See the [technical architecture](ARCHITECTURE.md).
- **Warehouse:** Use one private DuckDB file per account. Keep the files outside public web paths and serialize writes for each workspace through a single writer process. Keep uploads bounded, accept CSV only, and derive the workspace from the signed-in account, not a user-supplied file path. [DuckDB concurrency](https://duckdb.org/docs/current/connect/concurrency)
- **SQL execution:** Run free-form SQL in an isolated browser worker using DuckDB-Wasm on authorized snapshots only. The browser cannot publish query changes back to the server warehouse. Do not forward free-form SQL to the server, accept Python uploads for execution, or enable external data access in the browser lab. [DuckDB security model](https://duckdb.org/security)
- **Hosting:** Serve the built frontend and Django API under the same HTTPS origin on the .dev domain. Start with one Django application instance and persistent storage for warehouse files and uploads. Protect sessions, rate-limit sign-in attempts, log account-management actions without secrets, and verify a backup restore before storing important data. Keep the default installation invite-only. [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- **Public source:** MIT is the proposed license. Publish the source, local setup instructions, configuration examples, and synthetic fixtures. Keep passwords, keys, invite links, account records, database files, uploads, backups, and exports out of Git. [MIT License](https://opensource.org/license/mit)

## 6. Build sequence and acceptance tests

| Phase | Status | Scope and acceptance |
| --- | --- | --- |
| **1. Identity and isolation** | Complete; on GitHub | Invite-only accounts, Admin and Member roles, and private workspaces. Verify that Members cannot manage accounts or read another workspace and that disabling an account revokes its sessions. |
| **2. Pipeline Lab and local automation** | Complete | Manual ETL and ELT, Batch Trail, run history, Data Explorer, optional local Airflow + dbt, and curated Kaggle imports. Verify that the sample totals ₱2,000.00 in both modes, an approved correction publishes ₱1,300.00, and a failed correction preserves the last good batch. |
| **3. SQL Workspace, reports, and export** | Next | Start with a table browser, SQL editor, Run button, saved queries, and results grid. Run SQL in the browser on an authorized snapshot with no writeback. Then add a date-filtered report and Excel export; verify that both match the worksheet total for the same batch and mode. |
| **4. Local Warehouse Setup** | Planned | Let an Admin create a named local compute profile (for example, `dbt_wh`) and grant permission to run jobs on it. Select it from Pipeline Lab for Airflow + dbt runs. Verify that Django denies unauthorized runs, the runner enforces a one-job-at-a-time limit and a timeout, and a timed-out job never publishes. |
| **5. Optional self-hosted release** | Planned | Verify a clean local installation and the synthetic demo. Before any hosted release, verify HTTPS, sign-in rate limiting, account isolation, persistence after restart, and backup restoration. No hosting purchase or cloud service is required to finish the local phases. |

**Compute and storage stay separate.** A Phase 4 profile controls how pipeline jobs run on the local machine. It does not own data or create a second database server. Each account keeps its private DuckDB file, and a compute grant never grants access to another account's data. Build the setup screen and enforce the limits before considering an AutumnLeaf-specific admin command such as `CREATE WAREHOUSE`. The SQL Workspace remains isolated from admin commands and pipeline writes.

## 7. Outside the MVP

Public registration, social sign-in, shared warehouse data, scheduled pipelines, general-purpose API connectors, drag-and-drop dashboard building, live Excel refresh, and server execution of user-supplied code are outside the first release. Snowflake-compatible administrative SQL and cloud compute provisioning are also out of scope.
