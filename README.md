# AutumnLeaf

AutumnLeaf is a self-hosted data warehouse workbench. Load a CSV, run ETL and ELT step by step, inspect and query the warehouse, and export the same reporting data to Excel.

The stack is React, TypeScript, Tailwind CSS, and Vite on the frontend; Python and Django on the backend; and DuckDB for analytics. The local base uses SQLite; PostgreSQL is planned for hosted application data.

## Repository layout

| Path | Contents |
| --- | --- |
| [frontend](frontend/) | Browser application |
| [backend](backend/) | Django API and pipeline services |
| [fixtures](fixtures/) | Synthetic data for examples and tests |
| [MVP specification](MVP.md) | Product scope, account roles, and acceptance criteria |
| [Technical architecture](ARCHITECTURE.md) | Stack, service boundaries, deployment, and scaling plan |
| [Interface design](DESIGN.md) | Autumn palette, workspace layout, and interaction rules |

## Development

Use Node.js 24 and Python 3.12 for the tested setup.

- **Frontend:** Run `npm ci` and `npm run build` from **frontend** to install dependencies, check types, and build the browser app.
- **Backend:** Install the pinned dependencies from [requirements.txt](backend/requirements.txt) in a Python virtual environment.
- **Access:** AutumnLeaf is invitation-only. If you need an account, contact the repository owner, [@jshlydnzl](https://github.com/jshlydnzl).

The workspace currently supports sign-in and workspace isolation. CSV ingestion, pipelines, browser SQL, and reporting are not implemented yet.
