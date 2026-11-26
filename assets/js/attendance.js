import { canAccess } from "./auth.js";
import { listRecords, saveAttendance, titleCase } from "./data.js";
import { emptyState, escapeHtml, formatDate, statusPill, toast } from "./ui.js";

export async function renderAttendance(user) {
  if (!canAccess("attendance", user)) return emptyState("Access restricted", "Your role cannot record attendance.", "bi-shield-lock");
  if (["farmer", "management"].includes(user.role)) {
    const records = await listRecords("attendance");
    const content = document.createElement("div");
    content.className = "module-container";
    content.innerHTML = `<div class="page-title-row"><div><span class="eyebrow">Participation records</span><h1>${user.role === "farmer" ? "My attendance" : "Attendance"}</h1><p>${user.role === "farmer" ? "Review attendance for your training sessions." : "Review saved attendance across training sessions."}</p></div></div><div class="module-note"><i class="bi bi-info-circle"></i><span>Attendance is read-only in this portal and comes from the AgriLearn database.</span></div><section class="panel"><div class="table-toolbar"><label class="search-control"><i class="bi bi-search"></i><input class="form-control" type="search" data-search placeholder="Search attendance" aria-label="Search attendance"></label><span class="muted small" data-count></span></div><div class="data-table-wrap" data-table></div></section>`;
    const draw = () => {
      const search = content.querySelector("[data-search]").value.trim().toLowerCase();
      const visible = records.filter((row) => `${row.program_name || ""} ${row.session_date || ""} ${row.status || ""} ${row.farmer_name || ""}`.toLowerCase().includes(search));
      content.querySelector("[data-count]").textContent = `${visible.length} record${visible.length === 1 ? "" : "s"}`;
      content.querySelector("[data-table]").innerHTML = visible.length
        ? `<table class="data-table"><thead><tr>${user.role === "management" ? "<th>Farmer</th>" : ""}<th>Training program</th><th>Session date</th><th>Attendance</th><th>Recorded</th></tr></thead><tbody>${visible.map((row) => `<tr>${user.role === "management" ? `<td><strong>${escapeHtml(row.farmer_name || row.farmer_code)}</strong></td>` : ""}<td>${escapeHtml(row.program_name || "Training")}</td><td>${escapeHtml(formatDate(row.session_date))}</td><td>${statusPill(titleCase(row.status))}</td><td>${escapeHtml(formatDate(row.submittedAt))}</td></tr>`).join("")}</tbody></table>`
        : emptyState("No attendance records", "Attendance will appear here after it has been recorded.", "bi-person-check");
    };
    content.querySelector("[data-search]").addEventListener("input", draw);
    draw();
    return content;
  }
  const [sessions, programs, farmers] = await Promise.all([
    listRecords("sessions"),
    listRecords("programs"),
    listRecords("farmers")
  ]);
  const content = document.createElement("div");
  content.className = "module-container";
  content.innerHTML = `
    <div class="page-title-row"><div><span class="eyebrow">Participation management</span><h1>Attendance</h1><p>Choose an assigned session, mark each enrolled farmer, then submit.</p></div></div>
    <div class="module-note"><i class="bi bi-info-circle"></i><span>Attendance is recorded against enrolled farmers and saved in the AgriLearn database. Trainer access is limited to assigned sessions.</span></div>
    <section class="panel"><div class="session-select-row"><div><label class="form-label" for="attendance-program">Training program</label><select class="form-select" id="attendance-program"><option value="">Select a program</option></select></div><div><label class="form-label" for="attendance-session">Training session</label><select class="form-select" id="attendance-session" disabled><option value="">Select a session</option></select></div><button type="button" class="btn-brand" data-load-session><i class="bi bi-people"></i> Load farmer list</button></div><div data-roster>${emptyState("Select a training session", "The registered farmer list will appear here.", "bi-card-checklist")}</div></section>`;
  const programSelect = content.querySelector("#attendance-program");
  const sessionSelect = content.querySelector("#attendance-session");
  const validSessions = sessions.filter((session) => session.status !== "cancelled");
  const programIds = new Set(validSessions.map((session) => String(session.program_id)));
  programSelect.innerHTML += programs.filter((program) => programIds.has(String(program.id))).map((program) => `<option value="${program.id}">${escapeHtml(program.title)}</option>`).join("");
  programSelect.addEventListener("change", () => {
    const assigned = validSessions.filter((session) => String(session.program_id) === programSelect.value);
    sessionSelect.innerHTML = `<option value="">Select a session</option>${assigned.map((session) => `<option value="${session.id}">${escapeHtml(formatDate(session.date))} · ${escapeHtml(session.time)} · ${escapeHtml(session.location)}</option>`).join("")}`;
    sessionSelect.disabled = assigned.length === 0;
  });
  content.querySelector("[data-load-session]").addEventListener("click", async () => {
    const session = validSessions.find((item) => String(item.id) === sessionSelect.value);
    const roster = content.querySelector("[data-roster]");
    if (!session) { toast("Select an available training session first.", "error"); sessionSelect.focus(); return; }
    const program = programs.find((item) => String(item.id) === String(session.program_id));
    const enrolledIds = new Set((session.farmerIds || []).map(String));
    const participants = farmers.filter((farmer) => enrolledIds.has(String(farmer.id)));
    let existing;
    try { existing = await listRecords("attendance", { session_id: session.id }); }
    catch (error) { toast(`Could not load attendance: ${error.message}`, "error"); return; }
    if (!participants.length) {
      roster.innerHTML = emptyState("No enrolled farmers", "Enroll farmers into this training program before recording attendance.");
      return;
    }
    roster.innerHTML = `<form data-attendance-form><div class="panel-head"><h2>${escapeHtml(program?.title || "Training")} · ${escapeHtml(formatDate(session.date))}</h2><span class="muted small">${participants.length} enrolled farmers</span></div><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Farmer</th><th>Farmer ID</th><th>Village</th><th>Attendance status</th></tr></thead><tbody>${participants.map((farmer) => {
      const state = existing.find((item) => String(item.farmer_id) === String(farmer.id))?.status;
      return `<tr><td><strong>${escapeHtml(farmer.name)}</strong></td><td>${escapeHtml(farmer.farmer_id)}</td><td>${escapeHtml(farmer.village)}</td><td><div class="attendance-mark"><label><input class="form-check-input" type="radio" name="farmer-${farmer.id}" value="present" ${state === "present" ? "checked" : ""} required> Present</label><label class="ms-2"><input class="form-check-input" type="radio" name="farmer-${farmer.id}" value="absent" ${state === "absent" ? "checked" : ""}> Absent</label>${state ? `<span class="ms-2">${statusPill(titleCase(state))}</span>` : ""}</div></td></tr>`;
    }).join("")}</tbody></table></div><div class="d-flex justify-content-end p-3"><button class="btn-brand" type="submit"><i class="bi bi-check2-circle"></i> Submit attendance</button></div></form>`;
    roster.querySelector("[data-attendance-form]").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      if (!form.reportValidity()) return;
      const formData = new FormData(form);
      const records = participants.map((farmer) => ({ farmerId: farmer.id, status: formData.get(`farmer-${farmer.id}`) }));
      try {
        await saveAttendance(session.id, records);
        toast(`Attendance saved for ${records.length} farmers.`);
        content.querySelector("[data-load-session]").click();
      } catch (error) { toast(error.message, "error"); }
    });
  });
  return content;
}
