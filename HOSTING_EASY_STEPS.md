# Easy Hosting Steps

Use this simple path. Do not change advanced settings unless needed.

## 1. Check Files Before Uploading

These files must be at the top level of your GitHub repo:

```text
app.py
requirements.txt
render.yaml
deploy_check.py
data/sample_alerts.csv
```

This version can run with only these files.

## 2. Test Before Push

Run:

```powershell
python deploy_check.py
python app.py
```

Open:

```text
http://127.0.0.1:8000
```

If it opens locally, it should be ready for hosting.

## 3. Push To GitHub

```powershell
git add .
git commit -m "Ready for hosting"
git push
```

## 4. Render Settings

Use these exact settings:

```text
Build Command:
python deploy_check.py && pip install -r requirements.txt

Start Command:
python app.py
```

Environment variables:

```text
AML_QC_DB_PATH=data/aml_qc.sqlite3
AML_QC_SEED_SAMPLE=true
```

Leave `Root Directory` blank if `app.py` is visible at the first page of your GitHub repo.

## 5. Deploy

In Render:

```text
Manual Deploy -> Clear build cache & deploy
```

## Common Error Fixes

`No module named aml_qc_engine`

This is fixed in the latest version because `app.py` is standalone. Push the latest code.

`Exited with status 1`

Scroll up in Render logs. The new deploy check will show which file is missing or if Python syntax failed.

Page opens but has no results

Set:

```text
AML_QC_SEED_SAMPLE=true
```

Also confirm this file is in GitHub:

```text
data/sample_alerts.csv
```

That file is created from your `sample.xlsx` workbook and is used as the hosted sample dataset.
