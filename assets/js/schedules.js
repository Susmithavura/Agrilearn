import { canAccess } from "./auth.js";
import { deactivateRecord, listRecords, saveSession, titleCase } from "./data.js";
import { emptyState, escapeHtml, formatDate, showDialog, statusPill, toast } from "./ui.js";

const today = () => new Date().toISOString().slice(0, 10);

function sessionForm(session, user, programs, trainers, farmers) {
  const isTrainer = user.role === "trainer";
  const programChoices = programs.filter((program) => program.status === "active" || String(program.id) === String(session.programId));
  const trainerChoices = trainers.filter((trainer) => trainer.status === "active" || String(trainer.id) === String(session.trainerId));
  const selectedFarmers = new Set((session.farmerIds || []).map(String));
  return `<div class="row g-3">
    <div class="col-md-6"><label class="form-label" for="session-program">Training program *</label><select class="form-select" id="session-program" name="programId" ${isTrainer ? "disabled" : ""} required><option value="">Select a program</option>${programChoices.map((item) => `<option value="${item.id}" ${String(item.id) === String(session.programId || "") ? "selected" : ""}>${escapeHtml(item.title)}</option>`).join("")}</select>${isTrainer ? `<input type="hidden" name="programId" value="${session.programId}">` : ""}</div>
    <div class="col-md-6"><label class="form-label" for="session-trainer">Assigned trainer *</label><select class="form-select" id="session-trainer" name="trainerId" ${isTrainer ? "disabled" : ""} required><option value="">Select a trainer</option>${trainerChoices.map((item) => `<option value="${item.id}" ${String(item.id) === String(session.trainerId || "") ? "selected" : ""}>${escapeHtml(item.name)} · ${escapeHtml(item.specialization)}</option>`).join("")}</select>${isTrainer ? `<input type="hidden" name="trainerId" value="${session.trainerId}">` : ""}</div>
    <div class="col-md-6"><label class="form-label" for="session-date">Training date *</label><input class="form-control" type="date" id="session-date" name="date" value="${escapeHtml(session.date || today())}" min="${session.date || today()}" required></div>
    <div class="col-md-3"><label class="form-label" for="session-time">Start time *</label><input class="form-control" type="time" id="session-time" name="time" value="${escapeHtml(session.time || "09:00")}" required></div>
    <div class="col-md-3"><label class="form-label" for="session-end-time">End time</label><input class="form-control" type="time" id="session-end-time" name="endTime" value="${escapeHtml(session.end_time || "")}"></div>
    <div class="col-12"><label class="form-label" for="session-location">Training location *</label><input class="form-control" id="session-location" name="location" value="${escapeHtml(session.location || "")}" maxlength="200" required></div>
    <div class="col-12"><label class="form-label" for="session-details">Session details</label><textarea class="form-control" id="session-details" name="details" rows="2">${escapeHtml(session.details || "")}</textarea></div>
    ${!isTrainer ? `<div class="col-12"><label class="form-label" for="session-farmers">Enroll farmers into this program</label><select class="form-select" id="session-farmers" name="farmerIds" multiple size="4">${farmers.map((farmer) => `<option value="${farmer.id}" ${selectedFarmers.has(String(farmer.id)) ? "selected" : ""}>${escapeHtml(farmer.name)} · ${escapeHtml(farmer.village)}</option>`).join("")}</select><small class="muted">Enrollment applies to the training program and makes its sessions visible to those farmers.</small></div>` : ""}
    ${session.id ? `<div class="col-md-6"><label class="form-label" for="session-status">Session status</label><select class="form-select" name="status" id="session-status">${[["scheduled","Scheduled"],["completed","Completed"],["cancelled","Cancelled"]].map(([value,label]) => `<option value="${value}" ${session.status === value ? "selected" : ""}>${label}</option>`).join("")}</select></div>` : ""}
  </div>`;
}

export async function renderSchedules(user) {
  if (!canAccess("schedules", user)) return emptyState("Access restricted", "Your role cannot view training schedules.", "bi-shield-lock");
  let [sessions, programs, trainers, farmers] = await Promise.all([
    listRecords("sessions"),
    listRecords("programs"),
    user.role === "farmer" ? Promise.resolve([]) : listRecords("trainers"),
    ["admin", "coordinator"].includes(user.role) ? listRecords("farmers") : Promise.resolve([])
  ]);
  const canManage = ["coordinator", "admin"].includes(user.role);
  const canEditAssigned = user.role === "trainer";
  const visibleSessions = () => sessions;
  const now = new Date();
  let year = now.getFullYear();
  let month = now.getMonth();
  const content = document.createElement("div");
  content.className = "module-container";
  content.innerHTML = `
    <div class="page-title-row"><div><span class="eyebrow">Training calendar</span><h1>Training schedules</h1><p>Coordinate programs, trainers, dates, locations and program participants.</p></div><div class="page-actions">${canManage ? `<button class="btn-brand" data-add><i class="bi bi-calendar-plus"></i> Schedule session</button>` : ""}</div></div>
    <div class="module-note"><i class="bi bi-info-circle"></i><span>Schedules and enrollments are loaded from the AgriLearn database. Trainer edits are restricted to assigned sessions.</span></div>
    <section class="panel"><div class="calendar-head"><button class="icon-btn" data-month="-1" aria-label="Previous month"><i class="bi bi-chevron-left"></i></button><h2 data-month-title></h2><button class="icon-btn" data-month="1" aria-label="Next month"><i class="bi bi-chevron-right"></i></button></div><div class="calendar-grid" data-calendar></div></section>
    <section class="panel"><div class="panel-head"><h2>Scheduled sessions</h2><span class="muted small" data-session-count></span></div><div class="data-table-wrap" data-sessions-table></div></section>`;

  const detailsMarkup = (session) => {
    const program = programs.find((item) => String(item.id) === String(session.program_id));
    const trainer = trainers.find((item) => String(item.id) === String(session.trainer_id));
    return `<div class="row g-3"><div class="col-12"><span class="muted small">Program</span><strong class="d-block">${escapeHtml(program?.title || session.program_title || "Program unavailable")}</strong></div><div class="col-6"><span class="muted small">Trainer</span><strong class="d-block">${escapeHtml(trainer?.name || session.trainer_name || "Unassigned")}</strong></div><div class="col-6"><span class="muted small">Date & time</span><strong class="d-block">${escapeHtml(formatDate(session.date))} · ${escapeHtml(session.time)}</strong></div><div class="col-6"><span class="muted small">Location</span><strong class="d-block">${escapeHtml(session.location)}</strong></div><div class="col-6"><span class="muted small">Enrolled farmers</span><strong class="d-block">${session.farmerIds?.length || 0}</strong></div><div class="col-12">${statusPill(titleCase(session.status))}</div></div>`;
  };
  const viewSession = (session) => {
    const canEdit = canManage || canEditAssigned;
    showDialog({
      title: session.program_title || programs.find((item) => String(item.id) === String(session.program_id))?.title || "Training session",
      body: detailsMarkup(session),
      submitLabel: canEdit ? "Edit session" : "Done",
      onSubmit: () => {
        if (!canEdit) { document.getElementById("record-dialog").close(); return; }
        openSessionForm(session, false);
      }
    });
  };
  const openSessionForm = (session = {}, isNew = false) => {
    showDialog({
      title: `${isNew ? "Schedule" : "Edit"} training session`,
      body: sessionForm(session, user, programs, trainers, farmers),
      submitLabel: isNew ? "Schedule session" : "Save changes",
      onSubmit: async (formData) => {
        const next = {
          ...session,
          programId: Number(formData.get("programId")),
          trainerId: Number(formData.get("trainerId")),
          date: formData.get("date"),
          time: formData.get("time"),
          endTime: formData.get("endTime"),
          location: String(formData.get("location") || "").trim(),
          details: String(formData.get("details") || "").trim(),
          status: formData.get("status") || "scheduled",
          farmerIds: formData.getAll("farmerIds").map(Number)
        };
        try {
          await saveSession(next, isNew);
          sessions = await listRecords("sessions");
          document.getElementById("record-dialog").close();
          toast(`Training session ${isNew ? "scheduled" : "updated"} successfully.`);
          renderCalendar();
          renderSessionTable();
        } catch (error) { toast(error.message, "error"); }
      }
    });
  };
  const renderCalendar = () => {
    const first = new Date(year, month, 1);
    const startDay = first.getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const previousDays = new Date(year, month, 0).getDate();
    content.querySelector("[data-month-title]").textContent = first.toLocaleDateString(undefined, { month: "long", year: "numeric" });
    const slots = [];
    for (let index = 0; index < 42; index++) {
      let day = index - startDay + 1;
      let cellMonth = month;
      let cellYear = year;
      let other = false;
      if (day < 1) { day = previousDays + day; cellMonth -= 1; other = true; }
      else if (day > daysInMonth) { day -= daysInMonth; cellMonth += 1; other = true; }
      if (cellMonth < 0) { cellMonth = 11; cellYear -= 1; }
      if (cellMonth > 11) { cellMonth = 0; cellYear += 1; }
      const dateKey = `${cellYear}-${String(cellMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
      const events = visibleSessions().filter((session) => session.date === dateKey && session.status !== "cancelled");
      slots.push(`<div class="calendar-cell ${other ? "is-other" : ""} ${dateKey === today() ? "is-today" : ""}"><span class="calendar-date">${day}</span>${events.map((session) => {
        const title = programs.find((program) => String(program.id) === String(session.program_id))?.title || session.program_title || "Training";
        return `<button type="button" class="calendar-event border-0 text-start w-100" data-view-session="${session.id}" title="${escapeHtml(title)}">${escapeHtml(session.time)} · ${escapeHtml(title)}</button>`;
      }).join("")}</div>`);
    }
    content.querySelector("[data-calendar]").innerHTML = `<div class="calendar-weekday">Sun</div><div class="calendar-weekday">Mon</div><div class="calendar-weekday">Tue</div><div class="calendar-weekday">Wed</div><div class="calendar-weekday">Thu</div><div class="calendar-weekday">Fri</div><div class="calendar-weekday">Sat</div>${slots.join("")}`;
  };
  const renderSessionTable = () => {
    const rows = [...visibleSessions()].sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time));
    content.querySelector("[data-session-count]").textContent = `${rows.length} session${rows.length === 1 ? "" : "s"}`;
    if (!rows.length) {
      content.querySelector("[data-sessions-table]").innerHTML = emptyState("No scheduled sessions", "Training sessions will appear here after they are created.", "bi-calendar2-week");
      return;
    }
    content.querySelector("[data-sessions-table]").innerHTML = `<table class="data-table"><thead><tr><th>Training session</th><th>Trainer</th><th>Date</th><th>Time</th><th>Location</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows.map((session) => `<tr data-session="${session.id}"><td><strong>${escapeHtml(programs.find((p) => String(p.id) === String(session.program_id))?.title || session.program_title)}</strong></td><td>${escapeHtml(trainers.find((t) => String(t.id) === String(session.trainer_id))?.name || session.trainer_name || "—")}</td><td>${escapeHtml(formatDate(session.date))}</td><td>${escapeHtml(session.time)}</td><td>${escapeHtml(session.location)}</td><td>${statusPill(titleCase(session.status))}</td><td><div class="table-actions"><button class="icon-btn" data-view-session="${session.id}" aria-label="View session"><i class="bi bi-eye"></i></button>${canManage || canEditAssigned ? `<button class="icon-btn" data-edit-session="${session.id}" aria-label="Edit session"><i class="bi bi-pencil"></i></button>` : ""}${canManage ? `<button class="icon-btn danger" data-cancel-session="${session.id}" aria-label="Cancel session"><i class="bi bi-x-circle"></i></button>` : ""}</div></td></tr>`).join("")}</tbody></table>`;
  };
  content.querySelectorAll("[data-month]").forEach((button) => button.addEventListener("click", () => {
    month += Number(button.dataset.month);
    if (month < 0) { month = 11; year -= 1; }
    if (month > 11) { month = 0; year += 1; }
    renderCalendar();
  }));
  content.querySelector("[data-add]")?.addEventListener("click", () => openSessionForm({}, true));
  content.addEventListener("click", async (event) => {
    const view = event.target.closest("[data-view-session]");
    const edit = event.target.closest("[data-edit-session]");
    const cancel = event.target.closest("[data-cancel-session]");
    const sessionId = view?.dataset.viewSession || edit?.dataset.editSession || cancel?.dataset.cancelSession;
    if (!sessionId) return;
    const session = sessions.find((item) => String(item.id) === String(sessionId));
    if (!session) return;
    if (view) viewSession(session);
    else if (edit) openSessionForm(session);
    else if (cancel && window.confirm("Cancel this session? Its training history will be preserved.")) {
      try {
        await deactivateRecord("sessions", session.id);
        sessions = await listRecords("sessions");
        toast("Training session cancelled.");
        renderCalendar();
        renderSessionTable();
      } catch (error) { toast(error.message, "error"); }
    }
  });
  renderCalendar();
  renderSessionTable();
  return content;
}
