const dataInput = document.querySelector("#dataInput");
const resultsBody = document.querySelector("#resultsBody");
const resultSummary = document.querySelector("#resultSummary");
const passRate = document.querySelector("#passRate");
const minWords = document.querySelector("#minWords");
const maxWords = document.querySelector("#maxWords");
const bannedWords = document.querySelector("#bannedWords");
const templateSections = document.querySelector("#templateSections");
let latestResults = [];

function getRules() {
  return {
    minWords: Number(minWords.value) || 1,
    maxWords: Number(maxWords.value) || 9999,
    bannedWords: bannedWords.value
      .split(",")
      .map((word) => word.trim())
      .filter(Boolean),
    templateSections: templateSections.value
      .split("\n")
      .map((section) => section.trim())
      .filter(Boolean)
  };
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let insideQuote = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === '"' && insideQuote && next === '"') {
      cell += '"';
      index += 1;
    } else if (char === '"') {
      insideQuote = !insideQuote;
    } else if (char === "," && !insideQuote) {
      row.push(cell.trim());
      cell = "";
    } else if ((char === "\n" || char === "\r") && !insideQuote) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(cell.trim());
      if (row.some(Boolean)) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }

  row.push(cell.trim());
  if (row.some(Boolean)) rows.push(row);

  const headers = rows.shift()?.map((header) => header.toLowerCase().trim()) || [];
  return rows.map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] || ""])));
}

function parseInput(text) {
  const trimmed = text.trim();
  if (!trimmed) return [];

  if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
    const parsed = JSON.parse(trimmed);
    return Array.isArray(parsed) ? parsed : [parsed];
  }

  return parseCsv(trimmed);
}

function wordCount(text) {
  return (text.match(/\b[\w'-]+\b/g) || []).length;
}

function findBannedWords(text, blockedWords) {
  return blockedWords.filter((word) => {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const pattern = new RegExp(`\\b${escaped}\\b`, "i");
    return pattern.test(text);
  });
}

function checkAlert(alert, rules) {
  const remarks = String(alert.investigation_remarks || alert.remarks || alert.review_remarks || "");
  const issues = [];
  const count = wordCount(remarks);
  const missingSections = rules.templateSections.filter((section) => !remarks.toLowerCase().includes(section.toLowerCase()));
  const blocked = findBannedWords(remarks, rules.bannedWords);

  if (!alert.alert_id && !alert.alertid && !alert.id) {
    issues.push("Missing alert_id");
  }

  if (!remarks.trim()) {
    issues.push("Missing investigation remarks");
  }

  if (count < rules.minWords) {
    issues.push(`Investigation remarks below minimum word limit (${count}/${rules.minWords})`);
  }

  if (count > rules.maxWords) {
    issues.push(`Investigation remarks above maximum word limit (${count}/${rules.maxWords})`);
  }

  if (missingSections.length) {
    issues.push(`Template sections missing: ${missingSections.join(", ")}`);
  }

  if (blocked.length) {
    issues.push(`Restricted words used: ${blocked.join(", ")}`);
  }

  const severityPenalty = issues.reduce((score, issue) => {
    if (issue.includes("Restricted words") || issue.includes("Missing investigation")) return score + 30;
    if (issue.includes("Template sections")) return score + 20;
    return score + 10;
  }, 0);
  const score = Math.max(0, 100 - severityPenalty);
  const status = issues.length === 0 ? "Pass" : score >= 70 ? "Review" : "Fail";

  return {
    alertId: alert.alert_id || alert.alertid || alert.id || "Missing ID",
    analyst: alert.analyst || alert.user || alert.owner || "N/A",
    l1Agent: alert.l1_agent || alert.L1_agent || "",
    l1Remarks: alert.l1_remarks || alert.L1_remarks || "",
    l2Agent: alert.l2_agent || alert.L2_agent || alert.analyst || "",
    l2Remarks: alert.l2_remarks || alert.L2_remarks || remarks,
    status,
    score,
    wordCount: count,
    issues
  };
}

function renderResults(results) {
  latestResults = results;

  if (!results.length) {
    resultsBody.innerHTML = `<tr><td colspan="6" class="empty-cell">No alert records found.</td></tr>`;
    resultSummary.textContent = "No checks run.";
    passRate.textContent = "0%";
    return;
  }

  const passed = results.filter((result) => result.status === "Pass").length;
  const failed = results.filter((result) => result.status === "Fail").length;
  const review = results.filter((result) => result.status === "Review").length;
  passRate.textContent = `${Math.round((passed / results.length) * 100)}%`;
  resultSummary.textContent = `${results.length} alerts checked. ${passed} passed, ${review} need review, ${failed} failed.`;

  resultsBody.innerHTML = results.map((result) => `
    <tr>
      <td>
        <strong>${escapeHtml(result.alertId)}</strong><br>
        <span>${result.wordCount} words</span>
      </td>
      <td>
        <strong>${escapeHtml(result.l1Agent || "N/A")}</strong><br>
        <span>${escapeHtml(result.l1Remarks || "No L1 remarks")}</span>
      </td>
      <td>
        <strong>${escapeHtml(result.l2Agent || result.analyst || "N/A")}</strong><br>
        <span>${escapeHtml(result.l2Remarks || "No L2 remarks")}</span>
      </td>
      <td><span class="status ${result.status.toLowerCase()}">${result.status}</span></td>
      <td>${result.score}</td>
      <td>
        ${result.issues.length
          ? `<ul class="issues-list">${result.issues.map((issue) => `<li>${escapeHtml(issue)}</li>`).join("")}</ul>`
          : "All rules passed"}
      </td>
    </tr>
  `).join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function runQc() {
  try {
    const alerts = parseInput(dataInput.value);
    const rules = getRules();
    renderResults(alerts.map((alert) => checkAlert(alert, rules)));
  } catch (error) {
    resultsBody.innerHTML = `<tr><td colspan="6" class="empty-cell">Unable to parse input. Use CSV headers or JSON records.</td></tr>`;
    resultSummary.textContent = error.message;
    passRate.textContent = "0%";
  }
}

function exportResults() {
  if (!latestResults.length) runQc();
  const headers = ["alert_id", "l1_agent", "l1_remarks", "l2_agent", "l2_remarks", "status", "score", "word_count", "issues"];
  const rows = latestResults.map((result) => [
    result.alertId,
    result.l1Agent,
    result.l1Remarks,
    result.l2Agent,
    result.l2Remarks,
    result.status,
    result.score,
    result.wordCount,
    result.issues.join(" | ")
  ]);
  const csv = [headers, ...rows]
    .map((row) => row.map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "aml-qc-results.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}

document.querySelector("#loadSample").addEventListener("click", () => {
  loadSampleDataset();
});

document.querySelector("#runQc").addEventListener("click", runQc);
document.querySelector("#exportResults").addEventListener("click", exportResults);

async function loadSampleDataset() {
  try {
    const response = await fetch("data/sample_alerts.csv", { cache: "no-store" });
    if (!response.ok) throw new Error("Sample CSV not found");
    const csvText = await response.text();
    const sampleAlerts = parseCsv(csvText);
    dataInput.value = JSON.stringify(sampleAlerts, null, 2);
  } catch {
    dataInput.value = "";
    resultsBody.innerHTML = `<tr><td colspan="6" class="empty-cell">Sample dataset not found. Add data/sample_alerts.csv.</td></tr>`;
    resultSummary.textContent = "No sample dataset loaded.";
    passRate.textContent = "0%";
    return;
  }
  runQc();
}

loadSampleDataset();
