# AutumnLeaf

AutumnLeaf is a self-hosted data warehouse workbench. Load a CSV, run ETL and ELT step by step, inspect and query the warehouse, and export the same reporting data to Excel.

The planned stack is React, TypeScript, Tailwind CSS, and Vite on the frontend; Python and Django on the backend; and DuckDB for analytics. PostgreSQL stores hosted application data, while SQLite supports local development.

## Repository layout

| Path | Contents |
| --- | --- |
| [frontend](frontend/) | Browser application |
| [backend](backend/) | Django API and pipeline services |
| [fixtures](fixtures/) | Synthetic data for examples and tests |
| [MVP specification](MVP.md) | Product scope, account roles, and acceptance criteria |
| [Technical architecture](ARCHITECTURE.md) | Stack, service boundaries, deployment, and scaling plan |

The repository currently contains the project structure and documentation. There is no runnable application yet.
