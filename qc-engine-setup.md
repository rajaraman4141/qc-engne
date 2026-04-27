# AML QC Engine Setup

## Target Flow

1. FRM tool updates alert investigation remarks.
2. Superset stores or exposes the alert dataset.
3. QC engine pulls new or updated alerts on a schedule.
4. Engine validates each alert against configurable AML remark rules.
5. Failed alerts are routed back for correction and stored in a QC results table.
6. Superset dashboard shows pass rate, repeated defects, analyst coaching themes, and pending rework.

## Minimum Fields Needed

- `alert_id`
- `analyst`
- `investigation_remarks`
- `updated_at`
- `case_status`
- `risk_level`
- `qc_status`
- `qc_score`
- `qc_issues`

## Current Rule Types

- Word limit for investigation remarks.
- Mandatory template sections.
- Restricted words and short forms, such as `suspicious`, `ca`, `sa`, and `txn`.
- Missing alert ID or missing investigation remarks.

## Suggested Database Tables

`aml_alert_reviews`

- Stores latest alert and investigation fields coming from FRM or Superset source data.

`aml_qc_results`

- Stores one QC result per alert per run.
- Columns: `run_id`, `alert_id`, `qc_status`, `qc_score`, `qc_issues`, `checked_at`.

`aml_qc_rules`

- Stores configurable rules.
- Columns: `rule_name`, `rule_type`, `rule_value`, `severity`, `is_active`.

## Automation Options

- Simple first version: scheduled Python job queries Superset database directly and writes QC results back to a table.
- Better production version: FRM update event triggers a QC API immediately after remarks are changed.
- Dashboard version: Superset reads `aml_qc_results` for QA reporting and exception management.

## Rule Examples

Template sections:

- `Customer Profile:`
- `Alert Trigger:`
- `Transaction Review:`
- `Red Flags:`
- `Disposition:`
- `Rationale:`

Banned terms:

- `suspicious`
- `ca`
- `sa`
- `txn`

The word filter should match full words only, so `ca` does not accidentally fail words like `case`.
