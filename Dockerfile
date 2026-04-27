FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AML_QC_DB_PATH=data/aml_qc.sqlite3
ENV AML_QC_SOURCE_TABLE=aml_alert_reviews
ENV AML_QC_SEED_SAMPLE=true

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "app.py"]
