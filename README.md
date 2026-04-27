# AML QC Engine

Python-based quality control engine for AML investigation remarks.

## What It Checks

- Investigation remarks minimum and maximum word limit.
- Mandatory investigation template sections.
- Restricted terms and short forms, for example `suspicious`, `ca`, `sa`, `txn`.
- Missing alert IDs.
- Missing investigation remarks.

## Quick Start

```powershell
python -m aml_qc_engine.cli init-db --seed
python -m aml_qc_engine.cli run --input data/sample_alerts.csv --output data/qc_results.csv --save-db
python -m aml_qc_engine.cli web
```

Then open:

```text
http://127.0.0.1:8000
```

## Production Setup With Superset

The engine expects a source table or view with these columns:

- `alert_id`
- `analyst`
- `investigation_remarks`
- `updated_at`
- `case_status`
- `risk_level`

Default source table:

```text
aml_alert_reviews
```

Set it using:

```powershell
$env:AML_QC_SOURCE_TABLE="your_superset_source_table"
```

The QC output table is:

```text
aml_qc_results
```

Superset can build dashboards directly from that table.

## Rule Configuration

Rules live in:

```text
config/rules.json
```

Update that file to change the word limits, mandatory template sections, or banned terms.

## Make It Live With GitHub

GitHub should store the code and run checks. A Python hosting service should run the live app.
GitHub Pages cannot run this dashboard because it is a Python backend app.

Recommended simple deployment:

1. Create a new GitHub repository.
2. Push this project to the repository.
3. Create a free Render web service from the GitHub repo.
4. Use this start command:

```text
python app.py
```

5. Set environment variables in the hosting service:

```text
AML_QC_DB_PATH=data/aml_qc.sqlite3
AML_QC_SOURCE_TABLE=aml_alert_reviews
AML_QC_SEED_SAMPLE=true
```

For production, replace the local SQLite database with your real Superset database connector and keep credentials in hosting secrets, not in GitHub.
