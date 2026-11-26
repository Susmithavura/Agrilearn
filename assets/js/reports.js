import { canAccess } from "./auth.js";
import { listRecords, titleCase } from "./data.js";
import { apiRequest, apiUrl } from "./api.js";
import { emptyState, escapeHtml, formatDate, statusPill, toast } from "./ui.js";

const reports = {
  farmers: { label: "Farmer information", columns: [["farmer_id", "Farmer ID"], ["full_name", "Farmer name"], ["village", "Village"], ["phone", "Phone"], ["email", "Email"], ["record_status", "Status"]] },
  trainers: { label: "Trainer information", columns: [["trainer_id", "Trainer ID"], ["full_name", "Trainer"], ["specialization", "Specialization"], ["phone", "Phone"], ["email", "Email"], ["record_status", "Status"]] },
  programs: { label: "Training programs", columns: [["id", "Program ID"], ["program_name", "Program"], ["category", "Category"], ["level", "Level"], ["duration", "Duration"], ["enrolled_farmers", "Enrolled farmers"], ["scheduled_sessions", "Sessions"], ["status", "Status"]] },
  schedules: { label: "Training schedules", columns: [["program_name", "Program"], ["trainer_name", "Trainer"], ["session_date", "Date"], ["start_time", "Time"], ["location", "Location"], ["status", "Status"]] },
  attendance: { label: "Attendance", columns: [["farmer_id", "Farmer ID"], ["farmer_name", "Farmer"], ["program_name", "Program"], ["session_date", "Session date"], ["location", "Location"], ["attendance_status", "Attendance"], ["recorded_by", "Recorded by"]] },
  progress: { label: "Training progress", columns: [["farmer_id", "Farmer ID"], ["farmer_name", "Farmer"], ["program_name", "Program"], ["progress_percent", "Completion %"], ["completion_status", "Completion"], ["result", "Assessment result"], ["progress_details", "Progress details"]] }
};

const reportPaths = { farmers: "/reports/farmers", trainers: "/reports/trainers", programs: "/reports/programs", schedules: "/reports/schedules", attendance: "/reports/attendance", progress: "/reports/progress" };
const fmtCell = (key, value) => {
  if (["created_at", "session_date", "updated_at"].includes(key)) return escapeHtml(formatDate(String(value || "").slice(0, 10)));
  if (["record_status", "status", "attendance_status", "completion_status"].includes(key)) return statusPill(titleCase(value));
  if (key === "start_time") return escapeHtml(String(value || "").slice(0, 5));
  return escapeHtml(value ?? "—");
};

export async function renderReports(user) {
  if (!canAccess("reports", user)) return emptyState("Access restricted", "Your role cannot generate reports.", "bi-shield-lock");
  let reportKey = "farmers";
  let query = "";
  let filterValue = "";
  let startDate = "";
  let endDate = "";
  let records = [];
  let programs = [];
  const content = document.createElement("div");
  content.className = "module-container";
  content.innerHTML = `
    <div class="page-title-row"><div><span class="eyebrow">Reporting & review</span><h1>Training reports</h1><p>Review and export training reports generated from saved records.</p></div><div class="page-actions"><button class="btn-outline-brand" data-export><i class="bi bi-download"></i> Export CSV</button><button class="btn-brand" data-print><i class="bi bi-printer"></i> Print report</button></div></div>
    <div class="module-note"><i class="bi bi-info-circle"></i><span>Report information is retrieved from the AgriLearn database. Access and filters are enforced by the server.</span></div>
    <div class="print-header"><strong>VVITU · AgriLearn</strong><br><span>Farmer Training Management System · Academic Year 2026–27</span><h2 data-print-title></h2></div>
    <section class="panel"><div class="table-toolbar"><div class="table-toolbar-left"><select class="form-select" data-report-type aria-label="Report type">${Object.entries(reports).map(([key, report]) => `<option value="${key}">${report.label}</option>`).join("")}</select><select class="form-select" data-report-filter aria-label="Filter report records"><option value="">All records</option></select><label class="search-control"><i class="bi bi-search"></i><input class="form-control" type="search" data-search placeholder="Search report" aria-label="Search report"></label><label class="form-label mb-0 small">From <input class="form-control" type="date" data-start></label><label class="form-label mb-0 small">To <input class="form-control" type="date" data-end></label></div><span class="muted small" data-row-count></span></div><div data-report-table></div></section>
    <p class="muted small">Report generated from server records on <span data-generated-at></span>.</p>`;
  try { programs = await listRecords("programs"); }
  catch (error) { toast(`Could not load report filters: ${error.message}`, "error"); }

  const populateFilters = () => {
    const selector = content.querySelector("[data-report-filter]");
    const options = reportKey === "programs"
      ? [["active","Active"],["draft","Draft"],["archived","Archived"]]
      : ["attendance", "progress", "schedules"].includes(reportKey)
        ? programs.map((program) => [program.id, program.title])
        : reportKey === "farmers" ? [...new Set(records.map((row) => row.village).filter(Boolean))]
          : reportKey === "trainers" ? [...new Set(records.map((row) => row.specialization).filter(Boolean))] : [];
    const label = reportKey === "programs" ? "All program statuses" : ["attendance","progress","schedules"].includes(reportKey) ? "All training programs" : reportKey === "farmers" ? "All villages" : reportKey === "trainers" ? "All specializations" : "All records";
    selector.innerHTML = `<option value="">${label}</option>${options.map((item) => {
      const [value, text] = Array.isArray(item) ? item : [item, item];
      return `<option value="${escapeHtml(value)}">${escapeHtml(text)}</option>`;
    }).join("")}`;
  };
  const queryRows = () => {
    const report = reports[reportKey];
    return records.filter((row) => {
      const text = Object.values(row).join(" ").toLowerCase();
      const field = reportKey === "farmers" ? "village" : reportKey === "trainers" ? "specialization" : reportKey === "programs" ? "status" : "program_id";
      const value = reportKey === "programs" ? String(row.status || "") : reportKey === "farmers" || reportKey === "trainers" ? String(row[field] || "") : String(row.program_id || "");
      return text.includes(query) && (!filterValue || value === filterValue);
    });
  };
  const render = () => {
    const report = reports[reportKey];
    const rows = queryRows();
    content.querySelector("[data-print-title]").textContent = report.label;
    content.querySelector("[data-row-count]").textContent = `${rows.length} record${rows.length === 1 ? "" : "s"}`;
    content.querySelector("[data-generated-at]").textContent = new Date().toLocaleString();
    if (!rows.length) {
      content.querySelector("[data-report-table]").innerHTML = emptyState("No report records", "Try changing the filters or date range.");
      return;
    }
    content.querySelector("[data-report-table]").innerHTML = `<div class="data-table-wrap"><table class="data-table"><thead><tr>${report.columns.map(([, label]) => `<th>${escapeHtml(label)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${report.columns.map(([key]) => `<td>${fmtCell(key, row[key])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  };
  const loadReport = async () => {
    const params = { per_page: 100, start_date: startDate, end_date: endDate };
    if (filterValue && ["programs"].includes(reportKey)) params.status = filterValue;
    else if (filterValue && ["schedules", "attendance", "progress"].includes(reportKey)) params.program_id = filterValue;
    const response = await apiRequest(apiUrl(reportPaths[reportKey], params));
    if (!Array.isArray(response)) throw new Error("The server returned an invalid report.");
    records = response;
    if (["farmers", "trainers"].includes(reportKey)) populateFilters();
    render();
  };
  const reload = async () => {
    content.querySelector("[data-report-table]").innerHTML = emptyState("Loading report", "Retrieving current records from the server.", "bi-arrow-repeat");
    try { await loadReport(); }
    catch (error) { content.querySelector("[data-report-table]").innerHTML = emptyState("Could not load report", error.message, "bi-cloud-slash"); }
  };
  const refetchOnFilter = async () => {
    if (["programs", "schedules", "attendance", "progress"].includes(reportKey)) await reload();
    else render();
  };
  await reload();
  content.querySelector("[data-report-type]").addEventListener("change", async (event) => {
    reportKey = event.target.value;
    filterValue = "";
    populateFilters();
    await reload();
  });
  content.querySelector("[data-report-filter]").addEventListener("change", async (event) => {
    filterValue = event.target.value;
    await refetchOnFilter();
  });
  content.querySelector("[data-search]").addEventListener("input", (event) => { query = event.target.value.trim().toLowerCase(); render(); });
  content.querySelector("[data-start]").addEventListener("change", async (event) => { startDate = event.target.value; await reload(); });
  content.querySelector("[data-end]").addEventListener("change", async (event) => { endDate = event.target.value; await reload(); });
  content.querySelector("[data-print]").addEventListener("click", () => window.print());
  content.querySelector("[data-export]").addEventListener("click", () => {
    const report = reports[reportKey];
    const rows = queryRows();
    const csvEscape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const csv = [report.columns.map(([, label]) => csvEscape(label)).join(","), ...rows.map((row) => report.columns.map(([key]) => csvEscape(row[key])).join(","))].join("\r\n");
    const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `agrilearn-${reportKey}-report.csv`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Report exported as CSV.");
  });
  return content;
}
