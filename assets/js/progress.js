import { canAccess } from "./auth.js";
import { listRecords, saveProgress, titleCase } from "./data.js";
import { emptyState, escapeHtml, showDialog, statusPill, toast } from "./ui.js";

export async function renderProgress(user) {
  if (!canAccess("progress", user)) return emptyState("Access restricted", "Your role cannot view training progress.", "bi-shield-lock");
  let [records, farmers, programs, enrollments] = await Promise.all([
    listRecords("progress"),
    listRecords("farmers"),
    listRecords("programs"),
    listRecords("enrollments")
  ]);
  const canEdit = ["trainer", "coordinator", "admin"].includes(user.role);
  let search = "";
  let selectedStatus = "";
  const content = document.createElement("div");
  content.className = "module-container";
  content.innerHTML = `
    <div class="page-title-row"><div><span class="eyebrow">Learning outcomes</span><h1>Training progress & results</h1><p>Monitor participation, completion and results for each farmer and program.</p></div>${canEdit ? `<div class="page-actions"><button class="btn-brand" data-add-progress><i class="bi bi-plus-lg"></i> Update progress</button></div>` : ""}</div>
    <div class="module-note"><i class="bi bi-info-circle"></i><span>Progress and results are loaded from the database. Farmers can view only their own training record.</span></div>
    <section class="panel"><div class="table-toolbar"><div class="table-toolbar-left"><label class="search-control"><i class="bi bi-search"></i><input class="form-control" type="search" data-search placeholder="Search farmer or program" aria-label="Search progress"></label><select class="form-select" data-status aria-label="Filter by completion status"><option value="">All statuses</option><option value="not_started">Not started</option><option value="in_progress">In progress</option><option value="completed">Completed</option></select></div><span class="muted small" data-count></span></div><div class="data-table-wrap" data-progress-table></div></section>`;
  const renderRows = () => {
    const filtered = records.filter((record) => {
      const farmerName = farmers.find((farmer) => String(farmer.id) === String(record.farmer_id))?.name || record.farmer_name || "";
      const programName = programs.find((program) => String(program.id) === String(record.program_id))?.title || record.program_name || "";
      return `${farmerName} ${programName}`.toLowerCase().includes(search) && (!selectedStatus || record.result === selectedStatus);
    });
    content.querySelector("[data-count]").textContent = `${filtered.length} result${filtered.length === 1 ? "" : "s"}`;
    if (!filtered.length) {
      content.querySelector("[data-progress-table]").innerHTML = emptyState("No progress records", user.role === "farmer" ? "Your training results will appear here when recorded." : "Try another filter or record a training result.", "bi-graph-up-arrow");
      return;
    }
    content.querySelector("[data-progress-table]").innerHTML = `<table class="data-table"><thead><tr><th>Farmer</th><th>Training program</th><th>Progress</th><th>Completion</th><th>Result / trainer notes</th>${canEdit ? "<th>Actions</th>" : ""}</tr></thead><tbody>${filtered.map((record) => {
      const farmer = farmers.find((item) => String(item.id) === String(record.farmer_id));
      const program = programs.find((item) => String(item.id) === String(record.program_id));
      const percent = Math.max(0, Math.min(100, Number(record.percent) || 0));
      return `<tr><td><strong>${escapeHtml(farmer?.name || record.farmer_name || "Farmer unavailable")}</strong><br><span class="muted">${escapeHtml(farmer?.farmer_id || record.farmer_code || "")}</span></td><td>${escapeHtml(program?.title || record.program_name || "Program unavailable")}</td><td><div class="d-flex align-items-center gap-2"><div class="progress-track" style="width:90px"><div class="progress-fill" style="width:${percent}%"></div></div><strong>${percent}%</strong></div></td><td>${statusPill(titleCase(record.result))}</td><td>${escapeHtml(record.resultText || record.notes || "—")}</td>${canEdit ? `<td><button class="icon-btn" type="button" data-edit-progress="${record.id}" aria-label="Edit progress"><i class="bi bi-pencil"></i></button></td>` : ""}</tr>`;
    }).join("")}</tbody></table>`;
  };
  const refresh = async () => {
    try { records = await listRecords("progress"); renderRows(); }
    catch (error) { toast(error.message, "error"); }
  };
  const openForm = (existing) => {
    const eligible = enrollments.filter((item) => item.participation_status !== "withdrawn");
    const farmerIds = new Set(eligible.map((item) => String(item.farmer_id)));
    const programIds = new Set(eligible.map((item) => String(item.program_id)));
    const availableFarmers = farmers.filter((farmer) => farmerIds.has(String(farmer.id)));
    const availablePrograms = programs.filter((program) => programIds.has(String(program.id)));
    showDialog({
      title: existing ? "Update training progress" : "Record training progress",
      body: `<div class="row g-3">
        <div class="col-md-6"><label class="form-label" for="progress-farmer">Farmer *</label><select class="form-select" id="progress-farmer" name="farmerId" ${existing ? "disabled" : ""} required><option value="">Select farmer</option>${availableFarmers.map((farmer) => `<option value="${farmer.id}" ${String(existing?.farmer_id || "") === String(farmer.id) ? "selected" : ""}>${escapeHtml(farmer.name)} · ${escapeHtml(farmer.farmer_id)}</option>`).join("")}</select>${existing ? `<input type="hidden" name="farmerId" value="${existing.farmer_id}">` : ""}</div>
        <div class="col-md-6"><label class="form-label" for="progress-program">Program *</label><select class="form-select" id="progress-program" name="programId" ${existing ? "disabled" : ""} required><option value="">Select program</option>${availablePrograms.map((program) => `<option value="${program.id}" ${String(existing?.program_id || "") === String(program.id) ? "selected" : ""}>${escapeHtml(program.title)}</option>`).join("")}</select>${existing ? `<input type="hidden" name="programId" value="${existing.program_id}">` : ""}</div>
        <div class="col-md-6"><label class="form-label" for="progress-percent">Completion percentage *</label><input class="form-control" id="progress-percent" name="percent" type="number" min="0" max="100" step="1" value="${existing?.percent ?? 0}" required></div>
        <div class="col-md-6"><label class="form-label" for="progress-result">Completion status *</label><select class="form-select" id="progress-result" name="result" required>${[["not_started","Not started"],["in_progress","In progress"],["completed","Completed"]].map(([value,label]) => `<option value="${value}" ${existing?.result === value ? "selected" : ""}>${label}</option>`).join("")}</select></div>
        <div class="col-12"><label class="form-label" for="progress-details">Progress details</label><textarea class="form-control" id="progress-details" name="notes" rows="3" maxlength="10000">${escapeHtml(existing?.notes || "")}</textarea></div>
        <div class="col-12"><label class="form-label" for="progress-result-text">Assessment result</label><input class="form-control" id="progress-result-text" name="resultText" maxlength="255" value="${escapeHtml(existing?.resultText || "")}"></div>
      </div>`,
      submitLabel: existing ? "Save progress" : "Record progress",
      onSubmit: async (data) => {
        const percent = Number(data.get("percent"));
        const result = data.get("result");
        if (!Number.isInteger(percent) || percent < 0 || percent > 100) { toast("Progress must be a whole number between 0 and 100.", "error"); return; }
        if ((result === "completed" && percent !== 100) || (result === "not_started" && percent !== 0)) { toast("Match the completion percentage to the selected result status.", "error"); return; }
        const next = {
          id: existing?.id,
          farmerId: data.get("farmerId"),
          programId: data.get("programId"),
          percent,
          result,
          notes: String(data.get("notes") || "").trim(),
          resultText: String(data.get("resultText") || "").trim()
        };
        try {
          await saveProgress(next, !existing);
          document.getElementById("record-dialog").close();
          toast("Training progress saved.");
          await refresh();
        } catch (error) { toast(error.message, "error"); }
      }
    });
  };
  renderRows();
  content.querySelector("[data-search]").addEventListener("input", (event) => { search = event.target.value.trim().toLowerCase(); renderRows(); });
  content.querySelector("[data-status]").addEventListener("change", (event) => { selectedStatus = event.target.value; renderRows(); });
  content.querySelector("[data-add-progress]")?.addEventListener("click", () => openForm(null));
  content.addEventListener("click", (event) => {
    const button = event.target.closest("[data-edit-progress]");
    if (button) openForm(records.find((item) => String(item.id) === button.dataset.editProgress));
  });
  return content;
}
