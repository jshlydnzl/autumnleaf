# AutumnLeaf Interface Design Specification

## 1. Design direction

AutumnLeaf is a desktop-first data workbench with a warm autumn palette. Use [Snowsight Workspaces](https://docs.snowflake.com/en/user-guide/ui-snowsight/workspaces) as a reference for the **interaction pattern**: browse data objects, write SQL, and inspect results without leaving the workspace. Do not copy Snowflake's branding, icons, terminology, or screen design.

AutumnLeaf's identity comes from dark bark and warm charcoal surfaces, a maple-orange action color, and an original leaf mark. Keep the editor and data tables quiet. Use accents to tell users where to act or what needs attention, not as decoration across every panel.

## 2. Color and typography

| Design token | Color | Use |
| --- | --- | --- |
| **canvas** | **#1B1715** | Dark bark page background and primary button text |
| **surface** | **#2A221E** | Warm charcoal sidebar, cards, and result panels |
| **primary** | **#E58A4E** | Maple orange for actions such as **Run query** and **Upload CSV** |
| **highlight** | **#F4BA55** | Golden amber for focus, warnings, and selections |
| **danger** | **#F07B72** | Cranberry for errors and destructive-action cues |
| **text** | **#F5EDE1** | Parchment for headings, editor text, and data values |
| **text-muted** | **#C7B5A7** | Secondary labels, timestamps, and helper text |
| **control-border** | **#967B6B** | Boundaries that identify inputs and outlined controls |
| **success** | **#A6BE91** | Muted leaf green for published or successful states |

Map these roles to shared Tailwind theme tokens. Do not scatter hex values through individual components. Use dark bark text on maple buttons: the pair has **6.84:1** contrast, while parchment on maple has only **2.24:1**. Use an offset amber focus outline so it is visible against the dark surface, including around maple buttons.

Use a system sans-serif for the interface and a system monospace for SQL only. Start at 16 px for body text and 14 px for controls and table labels. Right-align numeric data and use tabular numerals in result grids and revenue summaries. Meet [WCAG AA text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) and [non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html). Pair every status color with text.

## 3. Workspace layout

| Area | Interface behavior |
| --- | --- |
| **App navigation** | A compact sidebar leads to **Data Explorer**, **SQL Workspace**, **Pipeline Lab**, and **Reports**. Show **Accounts** to Admins only. Keep the signed-in account and sign-out control in the shell. |
| **Data Explorer** | Use an expandable schema and table tree, with a column list and row preview in the main pane. In the SQL Workspace, the explorer can collapse so the editor keeps its width. |
| **SQL Workspace** | Put the editor above the results grid. Keep **Run query** and **Save query** near the editor. Show result count, execution status, and errors in the results area without hiding or clearing the SQL. |
| **Pipeline Lab** | Put file selection and ETL or ELT mode at the top. Below, show the ordered pipeline steps, the current step's output, and recent runs. |
| **Reports** | Put the date filter and **Export to Excel** above one revenue KPI and one daily sales chart. The chart and export must represent the same selected data. |
| **Accounts** | Show account status, role, and available management actions to authorized users only. Django enforces permission on every request. |

On narrower screens, collapse navigation and the data explorer rather than shrinking the editor or table text. Stack the editor and results. Allow wide tables to scroll inside their own area. Keep links, controls, and dialogs usable with the keyboard.

## 4. What makes AutumnLeaf distinct

### 4.1 Batch Trail

Show the actual order of work: **Extract, Transform, Load** for ETL and **Extract, Load, Transform** for ELT. Each step shows its input, row count when available, and outcome. Selecting a completed step reveals its preview or validation errors. A compact run receipt identifies the source file, batch month, and whether the run was published.

### 4.2 Compare and replace

Compare ETL and ELT output with the same row-count and revenue measures. Mark a mismatch in text and show the difference. Before replacing a published month, show the before-and-after row count and revenue, then ask for confirmation. If the replacement fails, state that the last published batch is unchanged.

## 5. Implementation and review

Start with the shared shell, sign-in, and Accounts page. Apply the same buttons, inputs, tables, and status labels to later screens. Do not put inactive future features in the navigation or expose milestone names in the interface.

Review each screen for loading, empty, success, and error states where applicable. Verify that the keyboard focus is visible, the SQL stays intact after an error, the mobile layout does not cause page-wide overflow, Members do not see account controls, and a failed pipeline cannot appear published.
