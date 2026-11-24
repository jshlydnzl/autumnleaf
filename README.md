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

## Run locally

Use Node.js 24 and Python 3.12 for the tested setup.

**Terminal 1 — Django**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export AUTUMNLEAF_DEBUG=1
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

**Terminal 2 — React**

```bash
cd frontend
npm ci
npm run dev
```

Open the URL printed by Vite. The page checks Django through the Vite proxy at **/api/health/**. The base does not yet include sign-in, warehouse workflows, or a production deployment.

## Checks

- **Frontend:** Run `npm run build` from **frontend** for TypeScript checks and the production bundle.
- **Backend:** Run `AUTUMNLEAF_DEBUG=1 python manage.py test` from **backend** with its virtual environment active.
