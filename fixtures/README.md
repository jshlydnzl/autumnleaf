# Fixtures

Commit only synthetic datasets and expected outputs. Keep real uploads, user data, generated workbooks, and local database files out of the repository.

| November 2026 sample | Expected result |
| --- | --- |
| [Original orders](orders/november.csv) | Two orders totaling ₱2,000.00 |
| [Corrected batch](orders/november-corrected.csv) | One order totaling ₱1,300.00 after replacement approval |
| [Invalid batch](orders/november-invalid.csv) | Duplicate order IDs; the previous published batch stays intact |
