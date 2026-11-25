# AutumnLeaf

AutumnLeaf is a self-hosted data warehouse workbench. Load a CSV, run ETL and ELT step by step, inspect and query the warehouse, and export the same reporting data to Excel.

The stack is React, TypeScript, Tailwind CSS, and Vite on the frontend; Python and Django on the backend; and DuckDB for analytics. The local base uses SQLite; PostgreSQL is planned for hosted application data.

## Repository layout

| Path | Contents |
| --- | --- |
| [frontend](frontend/) | Browser application |
| [backend](backend/) | Django API and pipeline services |
| [fixtures](fixtures/) | Synthetic data for examples and tests |
| [automation](automation/) | Optional local Airflow workflow and dbt models |
| [MVP specification](MVP.md) | Product scope, account roles, and acceptance criteria |
| [Technical architecture](ARCHITECTURE.md) | Stack, service boundaries, deployment, and scaling plan |
| [Interface design](DESIGN.md) | Autumn palette, workspace layout, and interaction rules |

## Development

Use Node.js 24 and Python 3.12 for the tested setup.

- **Frontend:** Run `npm ci` and `npm run build` from **frontend** to install dependencies, check types, and build the browser app.
- **Backend:** Install the pinned dependencies from [requirements.txt](backend/requirements.txt) in a Python virtual environment.
- **Kaggle source:** Install [requirements-kaggle.txt](backend/requirements-kaggle.txt) in the same virtual environment to enable Kaggle imports.
- **Access:** AutumnLeaf is invitation-only. If you need an account, contact the repository owner, [@jshlydnzl](https://github.com/jshlydnzl).

## Try the Pipeline Lab

Open **Pipeline Lab**, choose **November 2026**, and download the original sample from **Try the sample CSVs**. Upload the same file once in **ELT** and once in **ETL**, then run each step in the Batch Trail. The comparison should show two matching orders totaling **₱2,000.00** in each mode.

The corrected sample replaces the month with one order totaling **₱1,300.00** after approval. The invalid sample must leave the last published batch unchanged. Use **Data Explorer** to inspect the raw, staging, and published sales tables. Free-form browser SQL, dashboards, and Excel export are not part of this release.

On a workspace with local automation enabled, upload an ELT file and choose **Run with Airflow + dbt** before starting the manual steps. Airflow runs the load and dbt build; AutumnLeaf imports the tested result while you monitor the run or after you reopen it. A correction still requires approval.

With Kaggle enabled, choose **Source → Kaggle → E-commerce & retail**, select a dataset, and preview a month before creating an ETL or ELT run. The catalog uses pinned public dataset versions and imports only order IDs, dates, and amounts. It does not convert currencies. A different batch for the same month and mode still requires replacement approval.
