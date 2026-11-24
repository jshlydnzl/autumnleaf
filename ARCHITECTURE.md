# AutumnLeaf Technical Architecture and Services

## 1. System overview

AutumnLeaf is a full-stack, self-hosted web application for learning data engineering. The browser provides a warehouse explorer, SQL editor, pipeline lab, dashboard, and account controls. The server manages identity, access, file ingestion, pipeline execution, and exports. Persistent storage keeps account records, source files, analytical tables, and results.

The first release has two layers in one repository: a React frontend and a **modular Django backend**. Accounts, warehouse access, pipelines, and reporting are separate modules within one backend deployment, not separate servers. The [MVP specification](MVP.md) defines the required behavior and acceptance tests.

## 2. Technology stack

| Layer | Selected technology | Responsibility |
| --- | --- | --- |
| Browser interface | React, TypeScript, and Tailwind CSS | Build the account screens, data explorer, SQL editor, pipeline controls, and reports. |
| Frontend tooling | Node.js, npm, and Vite | Run the development server and build static production assets. Node.js is not needed to serve the production build. |
| Backend API | Python and Django 5.2 LTS, using a supported patch release | Provide JSON endpoints, accept CSV uploads and return Excel downloads, manage sessions, enforce roles, and run warehouse workflows. |
| Application database | SQLite locally; PostgreSQL when hosted | Store accounts, roles, sessions, workspace ownership, saved SQL text, and account audit events. |
| Analytical database | DuckDB, one private database file per account | Handle ETL and ELT outputs, warehouse tables, run receipts, and analytical queries. |
| Browser SQL | DuckDB-Wasm in a browser worker | Run user-written SQL against an authorized dataset snapshot without exposing the server warehouse to that SQL. |
| Charts and workbooks | Chart.js and openpyxl | Draw the daily sales chart and create a filtered Excel export. |
| Production runtime | Gunicorn on Linux, an HTTPS proxy or managed ingress, and a persistent volume | Serve the built frontend and route API requests to Django under one origin. Keep warehouse files across restarts. |

[React with TypeScript](https://react.dev/learn/typescript) · [Tailwind CSS with Vite](https://tailwindcss.com/docs/installation/using-vite) · [Django release support](https://www.djangoproject.com/download/) · [Django with Gunicorn](https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/gunicorn/) · [DuckDB-Wasm](https://duckdb.org/docs/current/clients/wasm/query) · [Chart.js](https://www.chartjs.org/docs/latest/) · [openpyxl](https://openpyxl.readthedocs.io/en/stable/tutorial.html)

### 2.1 Frontend and backend boundary

React owns the screens and interaction state. It calls Django under **/api/** using relative URLs. Django owns sessions, role checks, workspace ownership, input validation, and the published warehouse. The frontend may hide actions based on the session response, but it cannot grant permissions. If the session expires, the API returns **401 Unauthorized** and the frontend returns to sign-in. A signed-in Member requesting an Admin action receives **403 Forbidden**.

Use Django session cookies rather than tokens stored in the browser. React requests a Django-issued CSRF token and sends it on state-changing requests, including sign-in. In development, Vite proxies the API; in production, the HTTPS entry point serves the static frontend and routes **/api/** to Django. [Django CSRF protection for browser requests](https://docs.djangoproject.com/en/5.2/howto/csrf/#using-csrf-protection-with-ajax)

## 3. Services and functions

| Service | Functions available in the MVP |
| --- | --- |
| **Identity and accounts** | Sign in with a local username and password, sign out, set or reset a password through a single-use link. Admins create accounts, assign roles, and disable or reactivate other accounts. |
| **Ingestion** | Upload a retail orders CSV, associate it with a batch month, validate the file, calculate its checksum, and retain the source for inspection. |
| **Pipeline Lab** | Run Python ETL or SQL ELT step by step; compare validated rows and revenue; preview a replacement batch; see why a run failed. |
| **Warehouse Explorer** | Browse raw, staging, and reporting tables. Inspect column types and preview rows, scoped to the signed-in account. |
| **SQL Workspace** | Write and save SQL, execute it on a permitted snapshot in the browser, and review the result or error. |
| **Reporting and Excel** | View total revenue and daily sales for a selected date range. Download an Excel snapshot from the same reporting dataset. |
| **Run history** | See source filename, mode, batch, timestamps, outcome, row counts, and validation errors. Trace a published batch back to its input. |

The hosted application supports invite-only installations. The first Admin is created on the host. Members do not see account-management controls, and the server refuses their requests to those functions. Admin status does not give a user access to other accounts' warehouse data.

## 4. Data flow and storage boundaries

### 4.1 From CSV to report

1. The server checks the user's session and resolves the user's workspace. It validates the upload size and required CSV fields, then stores the source under a server-generated identifier.
2. In **ETL**, Python transforms and validates the source before DuckDB loads the clean rows. In **ELT**, DuckDB loads the source values first, then runs the deployed SQL transformation. The two modes keep separate outputs.
3. The pipeline verifies the batch month, order IDs, and fixed-precision amounts. If a file replaces an existing batch, the server checks that the published batch still matches the version shown in the replacement preview.
4. DuckDB commits the published data and successful run receipt in one transaction. A failed replacement leaves the previous batch intact. Resubmitting the same accepted file does not duplicate data.
5. The dashboard and Excel generator use the same published sales model, date filter, and pipeline mode. The SQL editor consumes a separately authorized snapshot; it does not write back to the warehouse.

### 4.2 Data ownership

| Data | Authoritative store |
| --- | --- |
| Accounts, permissions, sessions, workspace registry, saved SQL, and account audit | Application database |
| Uploaded source files | Private volume at launch, keyed by workspace and upload ID |
| Raw and clean rows, published batch state, and pipeline receipts | The owner's DuckDB database |
| SQL scratch results and changes | Browser worker; temporary. Saving query text does not save results. |
| Dashboard and Excel output | Derived from published warehouse data; not separate sources of truth |

The application database does not copy the authoritative warehouse publication state. If background processing is introduced later, job status can live in PostgreSQL, but a retry must consult the warehouse receipt before publishing again.

## 5. Security and operational requirements

- **Identity and permissions:** Use Django password hashing, session cookies, and cross-site request forgery protection. Rate-limit sign-in, invalidate sessions on disable or password reset, and check role and ownership before returning any protected data or export. Hide account controls for Members without relying on the UI for enforcement.
- **Execution boundary:** Run only repository-controlled Python and transformation SQL on the host. Keep free-form SQL in a browser worker on bounded, authorized snapshots. Disable network and extension loading for the scratch runtime, cap results, and stop long-running queries. Do not accept Python or DuckDB database uploads. [DuckDB security model](https://duckdb.org/security)
- **Data protection:** Keep files outside public paths, store secrets outside Git, set upload and workspace limits, and log identifiers and error categories rather than contents or credentials. Serve protected pages, results, and downloads over HTTPS and prevent shared caching of private responses.
- **Recovery:** Back up PostgreSQL and the workspace files together using a consistent backup window or coordinated snapshots. Test restoration of a workspace and its ownership record before treating a hosted instance as durable.

## 6. Scaling plan

### 6.1 Start with one instance

Use one web application instance and one worker process that owns the native DuckDB connections. In the first release this can be the same web process; it is not an extra service. Serialize writes within a workspace and cap concurrent pipeline runs across the host. All reads of the live database go through the owning process while it is writable; separate processes may read immutable exports instead. Do not mount the same writable DuckDB file across several web workers or replicas. Stop the old writer before starting a replacement during deployment. [DuckDB concurrency rules](https://duckdb.org/docs/current/connect/concurrency)

Set configurable limits for upload size, rows, retained files, query time, and result size. Paginate table previews and use bulk loads rather than row-by-row inserts. Measure request latency, pipeline duration, memory, storage use, and failed or queued runs on representative datasets before raising the limits.

### 6.2 Add capacity only when needed

| Growth signal | Next change | Rule to preserve |
| --- | --- | --- |
| Imports delay ordinary page requests or time out | Move pipeline runs to a background runner with a durable PostgreSQL-backed queue, job timeouts, and retryable failure states. | Route warehouse access through the owning process. Keep one writer per workspace and make retries safe after a crash. |
| Source files and snapshots fill the host volume or limit recovery | Move uploads and immutable Parquet snapshots to private object storage. Keep the app's storage interface unchanged. | Scope object access to the workspace. Do not treat object storage as a shared writable DuckDB disk. |
| More signed-in users need simultaneous page access | Scale Django web replicas after moving live warehouse access to its owning service. Distribute work by workspace and use versioned snapshots for read-heavy reports. | Web replicas do not open live DuckDB files directly. Authorization remains in force for every request. |
| Teams need concurrent writes to a shared analytical dataset | Reassess the warehouse engine or table format behind the existing pipeline interface. | Treat shared writes, shared permissions, and migration as new requirements, not a configuration switch. |

External connectors, scheduled jobs, team workspaces, live BI connections, and distributed compute are extensions. The MVP requires no Redis, Kubernetes, or microservices.

## 7. Deployment and verification

**Local installation:** Run the Vite frontend and Django API with SQLite and workspace files on the machine. Create the first Admin from the host. Use the synthetic order fixtures to test ETL, ELT, replacement batches, and Excel export.

**Hosted installation:** Build the frontend with Vite and serve it over HTTPS on the same origin as the Django API. Run Django with PostgreSQL and a persistent volume, test on a temporary host URL, and then attach the .dev domain. Publish source code and synthetic fixtures under the proposed MIT license; do not publish installation data or secrets. Keep the private installation invite-only.

**Release verification:** Test the Admin and Member access matrix, direct requests across workspaces, invalid and repeated uploads, replacement atomicity, ETL and ELT equivalence, report and export parity, browser SQL isolation, and persistence after restart. Run Django's production checks and verify a backup restore before relying on the hosted installation. [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
