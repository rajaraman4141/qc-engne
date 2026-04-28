from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import traceback
import uuid
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class AlertRecord:
    alert_id: str
    analyst: str
    investigation_remarks: str
    l1_agent: str = ""
    l1_remarks: str = ""
    l2_agent: str = ""
    l2_remarks: str = ""
    updated_at: str = ""
    case_status: str = ""
    risk_level: str = ""


@dataclass
class QCResult:
    alert_id: str
    analyst: str
    status: str
    score: int
    word_count: int
    issues: list[str]
    checked_at: str

    @property
    def issue_text(self) -> str:
        return " | ".join(self.issues)


DEFAULT_RULES = {
    "min_words": 40,
    "max_words": 250,
    "required_sections": [
        "Customer Profile:",
        "Alert Trigger:",
        "Transaction Review:",
        "Red Flags:",
        "Disposition:",
        "Rationale:",
    ],
    "banned_terms": ["txn", "ca", "sa", "amt","suspicious"],
}

EMBEDDED_SAMPLE_ROWS = [
    {
        "alert_id": "R4_12323497_2025-10-04",
        "analyst": "Raktim Lahkar",
        "l1_agent": "Kajal Singh",
        "l1_remarks": "The customer is 24 years old, SALARIED, Income 10L-20L. It was observed that the customer initiated debit to self acc on 3 Oct. Upon further investigation, it has been found that the flagged transactions appear legitimate and hence resolving the alert as false positive.",
        "l2_agent": "Raktim Lahkar",
        "l2_remarks": "The customer is salaried. Own savings fund from other bank has been transferred, made debit of fund towards self account for personal requirement. Transactions are mostly associated to customer self account. Transaction appears to be normal and hence the alert is being closed as a false positive.",
        "investigation_remarks": "The customer is salaried. Own savings fund from other bank has been transferred, made debit of fund towards self account for personal requirement. Transactions are mostly associated to customer self account. Transaction appears to be normal and hence the alert is being closed as a false positive.",
        "updated_at": "2025-10-16T00:00:00",
        "case_status": "WHITELIST",
        "risk_level": "2",
    },
    {
        "alert_id": "R9_12982627_2026-02-23",
        "analyst": "Mithu Neog",
        "l1_agent": "Preetam Rohan",
        "l1_remarks": "Customer Details: Customer is aged 27 years, occupation: SELF_EMPLOYED with an annual income of 20-50L. Account Status: FIXED DEPOSIT(Closed). Transaction Activity: It was observed that customer received credits from TD closure on 22-Feb-2026. Apart from that no saving and current account is observed. Hence, it has been concluded that the flagged transaction is legitimate, and the alert is being resolved as a false positive. EDD Outcome: EDD not required. Conclusion: Hence, no anomalies were identified. Accordingly, the alert is closed as a false positive.",
        "l2_agent": "Mithu Neog",
        "l2_remarks": "Customer is aged 27 years, occupation: SELF_EMPLOYED with an annual income of 20-50L. Triggered transaction is related to closure of FD. No unusual patterns were observed in the transaction activity and hence the alert is closed as a false positive.",
        "investigation_remarks": "Customer is aged 27 years, occupation: SELF_EMPLOYED with an annual income of 20-50L. Triggered transaction is related to closure of FD. No unusual patterns were observed in the transaction activity and hence the alert is closed as a false positive.",
        "updated_at": "2026-03-05T00:00:00",
        "case_status": "WHITELIST",
        "risk_level": "1",
    },
    {
        "alert_id": "R4_11872184_2026-02-22",
        "analyst": "Biswajit Kundu",
        "l1_agent": "Harsh Kumar Jha",
        "l1_remarks": "Customer Details: Customer is aged 67 years, occupation: Retired with an annual income of 1-5L. Account Status: TD Closed. Transaction Activity: TD Closure proceeds were noted. After a thorough review of the overall transactions, it has been concluded that the flagged transaction is legitimate, the activity appears to be Usual. EDD Outcome: Not applicable. Conclusion: Based on the above observations, the transaction activity is consistent with the customer's profile and no red flags were identified; accordingly, the alert is closed as a false positive.",
        "l2_agent": "Biswajit Kundu",
        "l2_remarks": "Customer Details: Customer is aged 67 years, occupation: Retired with an annual income of 1-5L. Account Status: TD Closed. Transaction Activity: Noted a TD payout debit BOD Rs 500153.00. After a thorough review of the overall transactions, it has been concluded that the flagged transaction is legitimate, the activity appears to be Usual. EDD Outcome: EDD not required. Conclusion: Based on the above observations, the transaction activity is consistent with the customer's profile and no red flags were identified; accordingly, the alert is closed as a false positive.",
        "investigation_remarks": "Customer Details: Customer is aged 67 years, occupation: Retired with an annual income of 1-5L. Account Status: TD Closed. Transaction Activity: Noted a TD payout debit BOD Rs 500153.00. After a thorough review of the overall transactions, it has been concluded that the flagged transaction is legitimate, the activity appears to be Usual. EDD Outcome: EDD not required. Conclusion: Based on the above observations, the transaction activity is consistent with the customer's profile and no red flags were identified; accordingly, the alert is closed as a false positive.",
        "updated_at": "2026-03-05T00:00:00",
        "case_status": "WHITELIST",
        "risk_level": "1",
    },
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS aml_alert_reviews (
  alert_id TEXT PRIMARY KEY,
  analyst TEXT,
  l1_agent TEXT,
  l1_remarks TEXT,
  l2_agent TEXT,
  l2_remarks TEXT,
  investigation_remarks TEXT NOT NULL,
  updated_at TEXT,
  case_status TEXT,
  risk_level TEXT
);

CREATE TABLE IF NOT EXISTS aml_qc_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  alert_id TEXT NOT NULL,
  analyst TEXT,
  qc_status TEXT NOT NULL,
  qc_score INTEGER NOT NULL,
  word_count INTEGER NOT NULL,
  qc_issues TEXT,
  checked_at TEXT NOT NULL
);
"""

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AML QC Engine</title>
  <style>
    :root { --bg:#f3f6f7; --panel:#fff; --ink:#172026; --muted:#66717a; --line:#dbe3e8; --accent:#176b87; --ok:#177245; --warn:#a86600; --fail:#b42318; font-family:Inter,"Segoe UI",Arial,sans-serif; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); }
    .shell { min-height:100vh; padding:20px; display:grid; gap:18px; }
    header, section { background:var(--panel); border:1px solid var(--line); border-radius:8px; box-shadow:0 18px 50px rgba(23,32,38,.08); }
    header { display:flex; align-items:center; justify-content:space-between; gap:18px; padding:18px 24px; }
    .brand { display:flex; align-items:center; gap:18px; min-width:0; }
    .brand-mark { width:150px; max-width:34vw; height:auto; display:block; }
    .brand-copy { display:grid; gap:3px; min-width:0; }
    h1,h2,p { margin:0; letter-spacing:0; }
    h1 { font-size:1.55rem; }
    h2 { font-size:1rem; }
    .eyebrow { margin-bottom:4px; color:#0f4f65; font-size:.78rem; font-weight:900; text-transform:uppercase; }
    .muted { color:var(--muted); font-size:.88rem; }
    .summary { display:grid; grid-template-columns:repeat(4,minmax(110px,1fr)); gap:12px; }
    .metric { padding:16px; }
    .metric strong { display:block; margin-top:8px; font-size:1.65rem; }
    .toolbar { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:16px 18px; }
    button { min-height:40px; border:0; border-radius:6px; padding:0 14px; background:var(--accent); color:#fff; font-weight:800; cursor:pointer; }
    button.secondary { background:#eaf5f8; color:#0f4f65; border:1px solid #bfdee7; }
    .table-wrap { overflow-x:auto; }
    table { width:100%; border-collapse:collapse; min-width:1180px; }
    th,td { padding:12px; border-top:1px solid var(--line); text-align:left; vertical-align:top; font-size:.9rem; }
    th { color:var(--muted); font-size:.78rem; text-transform:uppercase; background:#f7fafb; }
    .remarks { max-width:310px; color:#3b4750; line-height:1.4; }
    .reviewer { display:block; margin-bottom:5px; color:var(--ink); font-weight:800; }
    .status { display:inline-grid; min-width:86px; place-items:center; border-radius:999px; padding:5px 9px; font-size:.78rem; font-weight:900; }
    .Pass { background:#edf8f2; color:var(--ok); }
    .Review { background:#fff6e8; color:var(--warn); }
    .Fail { background:#fff0ee; color:var(--fail); }
    @media (max-width:760px) { .shell{padding:10px;} header,.toolbar{align-items:flex-start; flex-direction:column;} .summary{grid-template-columns:1fr 1fr;} }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div class="brand">
        <img class="brand-mark" src="/logo.svg" alt="Slice">
        <div class="brand-copy">
        <p class="eyebrow">AML QC Engine</p>
        <h1>Investigation Remarks Quality Console</h1>
        <p class="muted">Runs word-limit, template, and restricted-term checks.</p>
        </div>
      </div>
      <button id="runButton">Run QC Now</button>
    </header>
    <section class="summary">
      <div class="metric"><p class="muted">Checked</p><strong id="checked">0</strong></div>
      <div class="metric"><p class="muted">Passed</p><strong id="passed">0</strong></div>
      <div class="metric"><p class="muted">Review</p><strong id="review">0</strong></div>
      <div class="metric"><p class="muted">Failed</p><strong id="failed">0</strong></div>
    </section>
    <section>
      <div class="toolbar">
        <div><h2>Latest QC Results</h2><p id="message" class="muted">Loading results...</p></div>
        <button class="secondary" id="refreshButton">Refresh</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Alert ID</th><th>L1 Review</th><th>L2 Review</th><th>Status</th><th>Score</th><th>Words</th><th>Issues</th><th>Checked At</th></tr></thead>
          <tbody id="resultsBody"></tbody>
        </table>
      </div>
    </section>
  </main>
  <script>
    const resultsBody = document.querySelector("#resultsBody");
    const message = document.querySelector("#message");
    function escapeHtml(value) {
      return String(value ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
    }
    function setSummary(rows) {
      document.querySelector("#checked").textContent = rows.length;
      document.querySelector("#passed").textContent = rows.filter((row) => row.qc_status === "Pass").length;
      document.querySelector("#review").textContent = rows.filter((row) => row.qc_status === "Review").length;
      document.querySelector("#failed").textContent = rows.filter((row) => row.qc_status === "Fail").length;
    }
    function renderRows(rows) {
      setSummary(rows);
      if (!rows.length) {
        resultsBody.innerHTML = '<tr><td colspan="8">No QC results yet. Run QC now.</td></tr>';
        return;
      }
      resultsBody.innerHTML = rows.map((row) => `
        <tr>
          <td><strong>${escapeHtml(row.alert_id)}</strong></td>
          <td class="remarks"><span class="reviewer">${escapeHtml(row.l1_agent || "N/A")}</span>${escapeHtml(row.l1_remarks || "No L1 remarks")}</td>
          <td class="remarks"><span class="reviewer">${escapeHtml(row.l2_agent || row.analyst || "N/A")}</span>${escapeHtml(row.l2_remarks || "No L2 remarks")}</td>
          <td><span class="status ${escapeHtml(row.qc_status)}">${escapeHtml(row.qc_status)}</span></td>
          <td>${escapeHtml(row.qc_score)}</td>
          <td>${escapeHtml(row.word_count)}</td>
          <td>${escapeHtml(row.qc_issues || "All rules passed")}</td>
          <td>${escapeHtml(row.checked_at)}</td>
        </tr>
      `).join("");
    }
    async function loadResults() {
      const response = await fetch("/api/results");
      const payload = await response.json();
      renderRows(payload.results);
      message.textContent = `${payload.results.length} latest result rows loaded.`;
    }
    async function runQc() {
      message.textContent = "Running QC...";
      const response = await fetch("/api/run", { method: "POST" });
      const payload = await response.json();
      message.textContent = payload.message;
      await loadResults();
    }
    document.querySelector("#runButton").addEventListener("click", runQc);
    document.querySelector("#refreshButton").addEventListener("click", loadResults);
    loadResults();
  </script>
</body>
</html>
"""

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="640" height="220" viewBox="0 0 640 220" role="img" aria-label="Slice logo">
  <rect width="640" height="220" rx="24" fill="#ffffff"/>
  <text x="34" y="158" fill="#8a08d4" font-family="Inter, Arial, sans-serif" font-size="144" font-weight="900" letter-spacing="-4">slice</text>
  <path d="M252 48h40v40c-22 0-40-18-40-40Z" fill="#8a08d4"/>
</svg>
"""


def database_path() -> str:
    return os.getenv("AML_QC_DB_PATH", "data/aml_qc.sqlite3")


def load_rules() -> dict:
    rules_path = Path(os.getenv("AML_QC_RULES_PATH", "config/rules.json"))
    if not rules_path.exists():
        return DEFAULT_RULES
    with rules_path.open("r", encoding="utf-8") as handle:
        return {**DEFAULT_RULES, **json.load(handle)}


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str) -> None:
    with connect(db_path) as connection:
        connection.executescript(SCHEMA)
        existing = {
            row["name"] for row in connection.execute("PRAGMA table_info(aml_alert_reviews)").fetchall()
        }
        for column in ("l1_agent", "l1_remarks", "l2_agent", "l2_remarks"):
            if column not in existing:
                connection.execute(f"ALTER TABLE aml_alert_reviews ADD COLUMN {column} TEXT")


def fetch_alerts(db_path: str) -> list[AlertRecord]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT alert_id, analyst, l1_agent, l1_remarks, l2_agent, l2_remarks,
                   investigation_remarks, updated_at, case_status, risk_level
            FROM aml_alert_reviews
            WHERE investigation_remarks IS NOT NULL
            """
        ).fetchall()
    return [
        AlertRecord(
            alert_id=row["alert_id"] or "",
            analyst=row["analyst"] or "",
            investigation_remarks=row["investigation_remarks"] or "",
            l1_agent=row["l1_agent"] or "",
            l1_remarks=row["l1_remarks"] or "",
            l2_agent=row["l2_agent"] or "",
            l2_remarks=row["l2_remarks"] or "",
            updated_at=row["updated_at"] or "",
            case_status=row["case_status"] or "",
            risk_level=row["risk_level"] or "",
        )
        for row in rows
    ]


def seed_sample_alerts(db_path: str) -> None:
    sample_csv = ROOT / "data" / "sample_alerts.csv"
    if sample_csv.exists():
        alerts = load_alerts_from_csv(sample_csv)
        print(f"Loaded sample dataset from {sample_csv}")
    else:
        alerts = [alert_from_mapping(row) for row in EMBEDDED_SAMPLE_ROWS]
        print("data/sample_alerts.csv not found. Loaded embedded sample records.")

    with connect(db_path) as connection:
        connection.execute("DELETE FROM aml_qc_results")
        connection.execute("DELETE FROM aml_alert_reviews")
        connection.executemany(
            """
            INSERT OR REPLACE INTO aml_alert_reviews (
              alert_id, analyst, l1_agent, l1_remarks, l2_agent, l2_remarks,
              investigation_remarks, updated_at, case_status, risk_level
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    alert.alert_id,
                    alert.analyst,
                    alert.l1_agent,
                    alert.l1_remarks,
                    alert.l2_agent,
                    alert.l2_remarks,
                    alert.investigation_remarks,
                    alert.updated_at,
                    alert.case_status,
                    alert.risk_level,
                )
                for alert in alerts
            ],
        )


def load_alerts_from_csv(path: Path) -> list[AlertRecord]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        return [alert_from_mapping(row) for row in rows]


def alert_from_mapping(row: dict[str, str]) -> AlertRecord:
    return AlertRecord(
        alert_id=row.get("alert_id", ""),
        analyst=row.get("analyst", ""),
        l1_agent=row.get("l1_agent", ""),
        l1_remarks=row.get("l1_remarks", ""),
        l2_agent=row.get("l2_agent", ""),
        l2_remarks=row.get("l2_remarks", ""),
        investigation_remarks=row.get("investigation_remarks", ""),
        updated_at=row.get("updated_at", ""),
        case_status=row.get("case_status", ""),
        risk_level=row.get("risk_level", ""),
    )


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def full_word_used(text: str, term: str) -> bool:
    return bool(re.search(rf"\b{re.escape(term)}\b", text or "", flags=re.IGNORECASE))


def evaluate_alert(alert: AlertRecord, rules: dict) -> QCResult:
    remarks = alert.investigation_remarks or ""
    count = word_count(remarks)
    issues: list[str] = []

    if not alert.alert_id:
        issues.append("Missing alert_id")
    if not remarks.strip():
        issues.append("Missing investigation remarks")
    has_low_word_count = count < int(rules["min_words"])
    if has_low_word_count:
        issues.append(f"Investigation remarks below minimum word limit ({count}/{rules['min_words']})")
    if count > int(rules["max_words"]):
        issues.append(f"Investigation remarks above maximum word limit ({count}/{rules['max_words']})")

    lowered = remarks.lower()
    missing = [section for section in rules["required_sections"] if section.lower() not in lowered]
    if missing:
        issues.append(f"Template sections missing: {', '.join(missing)}")

    banned = [term for term in rules["banned_terms"] if full_word_used(remarks, term)]
    if banned:
        issues.append(f"Restricted terms used: {', '.join(banned)}")

    penalty = 0
    for issue in issues:
        if issue.startswith("Restricted terms") or issue == "Missing investigation remarks":
            penalty += 30
        elif issue.startswith("Template sections"):
            penalty += 20
        else:
            penalty += 10

    score = max(0, 100 - penalty)
    has_restricted_terms = bool(banned)
    if has_low_word_count or has_restricted_terms:
        status = "Fail"
    else:
        status = "Pass"
    return QCResult(
        alert_id=alert.alert_id or "Missing ID",
        analyst=alert.analyst or "N/A",
        status=status,
        score=score,
        word_count=count,
        issues=issues,
        checked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def save_results(db_path: str, run_id: str, results: list[QCResult]) -> None:
    with connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO aml_qc_results (
              run_id, alert_id, analyst, qc_status, qc_score, word_count, qc_issues, checked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    result.alert_id,
                    result.analyst,
                    result.status,
                    result.score,
                    result.word_count,
                    result.issue_text,
                    result.checked_at,
                )
                for result in results
            ],
        )


def latest_results(db_path: str) -> list[dict]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT q.run_id, q.alert_id, q.analyst, q.qc_status, q.qc_score, q.word_count,
                   q.qc_issues, q.checked_at, a.l1_agent, a.l1_remarks, a.l2_agent, a.l2_remarks
            FROM aml_qc_results q
            LEFT JOIN aml_alert_reviews a ON a.alert_id = q.alert_id
            ORDER BY q.id DESC
            LIMIT 100
            """
        ).fetchall()
    return [dict(row) for row in rows]


def json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(db_path: str):
    class AMLQCHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def do_GET(self) -> None:
            route = urlparse(self.path).path
            if route == "/logo.svg":
                body = LOGO_SVG.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if route == "/":
                body = INDEX_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if route == "/api/results":
                json_response(self, {"results": latest_results(db_path)})
                return

            json_response(self, {"error": "Not found"}, status=404)

        def do_POST(self) -> None:
            route = urlparse(self.path).path
            if route != "/api/run":
                json_response(self, {"error": "Not found"}, status=404)
                return

            rules = load_rules()
            alerts = fetch_alerts(db_path)
            results = [evaluate_alert(alert, rules) for alert in alerts]
            run_id = str(uuid.uuid4())
            save_results(db_path, run_id, results)
            passed = sum(1 for result in results if result.status == "Pass")
            review = sum(1 for result in results if result.status == "Review")
            failed = sum(1 for result in results if result.status == "Fail")
            json_response(
                self,
                {
                    "run_id": run_id,
                    "message": (
                        f"QC complete: {len(results)} checked, {passed} passed, "
                        f"{review} review, {failed} failed."
                    ),
                },
            )

    return AMLQCHandler


def main() -> None:
    db_path = database_path()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT") or "8000")

    print("Starting AML QC Engine")
    print(f"Project root: {ROOT}")
    print(f"Database path: {db_path}")
    print(f"Host: {host}")
    print(f"Port: {port}")

    init_db(db_path)
    if os.getenv("AML_QC_SEED_SAMPLE", "true").lower() in {"1", "true", "yes"}:
        seed_sample_alerts(db_path)

    if not latest_results(db_path):
        alerts = fetch_alerts(db_path)
        if alerts:
            results = [evaluate_alert(alert, load_rules()) for alert in alerts]
            save_results(db_path, str(uuid.uuid4()), results)
            print(f"Auto-ran QC for {len(results)} sample alerts.")

    server = ThreadingHTTPServer((host, port), make_handler(db_path))
    print(f"AML QC dashboard running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("AML QC Engine failed during startup.")
        traceback.print_exc()
        raise
