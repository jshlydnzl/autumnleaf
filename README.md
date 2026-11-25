# AutumnLeaf

AutumnLeaf is a self-hosted data warehouse workbench. Upload an orders CSV or pull a supported dataset from Kaggle, run ETL or ELT, then inspect, query, and export published sales.

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

The corrected sample replaces the month with one order totaling **₱1,300.00** after approval. The invalid sample must leave the last published batch unchanged. Use **Data Explorer** to inspect the raw, staging, and published sales tables.

On a workspace with local automation enabled, upload an ELT file and choose **Run with Airflow + dbt** before starting the manual steps. Airflow runs the load and dbt build; AutumnLeaf imports the tested result while you monitor the run or after you reopen it. A correction still requires approval.

## Import orders from Kaggle

1. In **Pipeline Lab**, set **Source** to **Kaggle** and choose **E-commerce & retail**.
2. Select **Retail Sales**, keep **February 2023**, and click **Preview dataset**. The pinned dataset contains 85 orders for that month. **Sample Sales · Shipped orders** is also available.
3. Select **ELT · SQL transform**, then click **Create ELT run**. In the Batch Trail, run **Extract → Load → Transform**. For ETL, choose **ETL · Python transform** and run **Extract → Transform → Load**.

Only order IDs, dates, and amounts are brought into the warehouse. AutumnLeaf does not convert currencies; use the imported totals as test data. Repeating an unchanged import for the same month and mode does not add duplicate rows. A different batch for the same month and mode needs approval before replacing published data.

## Query and export a published batch

1. In **SQL Workspace**, select the month and mode of a published batch. Pick **mart.daily_sales** for daily totals or **mart.orders** for individual published orders.
2. Write a read-only query, such as `SELECT SUM(revenue) AS total FROM mart.daily_sales;`, then click **Run query**. Enter a name and click **Save query** to keep the SQL text.
3. In **Reports**, choose the same month and mode. Set **From** and **To** if you only want part of the month. **Export to Excel** downloads the same filtered sales figures.
