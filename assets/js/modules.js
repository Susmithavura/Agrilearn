import { canAccess } from "./auth.js";
import { createId, deactivateRecord, listRecords, saveRecord, setUserStatus, titleCase } from "./data.js";
import { apiRequest } from "./api.js";
import { emptyState, escapeHtml, formatDate, showDialog, statusPill, toast } from "./ui.js";

const definitions = {
  farmers: {
    singular: "Farmer", plural: "Farmers", icon: "bi-people",
    description: "Maintain farmer identities and contact details for training participation.",
    codeField: "farmer_id", codeLabel: "Farmer ID", codePrefix: "F",
    columns: [["farmerCode", "Farmer ID"], ["name", "Farmer"], ["village", "Village"], ["phone", "Phone"], ["joined", "Registered"]]
  },
  trainers: {
    singular: "Trainer", plural: "Trainers", icon: "bi-person-badge",
    description: "Manage agricultural officers, contact information and training specializations.",
    codeField: "trainer_id", codeLabel: "Trainer ID", codePrefix: "T",
    columns: [["trainerCode", "Trainer ID"], ["name", "Trainer"], ["specialization", "Specialization"], ["phone", "Phone"], ["email", "Email"]]
  },
  programs: {
    singular: "Training program", plural: "Training programs", icon: "bi-journal-richtext",
    description: "Create and maintain structured farmer training programs and learning details.",
    columns: [["id", "Program ID"], ["title", "Program"], ["category", "Category"], ["duration", "Duration"], ["level", "Level"], ["status", "Status"]]
  },
  users: {
    singular: "User", plural: "System users", icon: "bi-shield-lock",
    description: "Create real accounts, assign roles and control account access.",
    columns: [["id", "User ID"], ["username", "Username"], ["name", "Name"], ["role", "Role"], ["status", "Status"]]
  }
};

const roleTitle = {
  farmer: "Farmer", trainer: "Trainer / Agricultural Officer", coordinator: "Training Coordinator",
  management: "Agricultural Department / Management", admin: "System Administrator"
};
const today = () => new Date().toISOString().slice(0, 10);
const roleOptions = Object.entries(roleTitle).map(([value, label]) => [value, label]);
const optionMarkup = (options, selected = "") => options.map((option) => {
  const [value, label] = Array.isArray(option) ? option : [option, option];
  return `<option value="${escapeHtml(value)}" ${String(value) === String(selected) ? "selected" : ""}>${escapeHtml(label)}</option>`;
}).join("");

function fieldsFor(route, record, isNew) {
  if (route === "farmers") return [
    { key: "farmerCode", label: "Farmer ID", value: isNew ? createId("F") : record.farmerCode, readonly: !isNew },
    { key: "name", label: "Farmer name", value: record.name || "", required: true },
    { key: "village", label: "Village", value: record.village || "", required: true },
    { key: "phone", label: "Phone number", value: record.phone || "", type: "tel", pattern: "[0-9+() .-]{7,32}", required: true },
    { key: "email", label: "Email address", value: record.email || "", type: "email" }
  ];
  if (route === "trainers") return [
    { key: "trainerCode", label: "Trainer ID", value: isNew ? createId("T") : record.trainerCode, readonly: !isNew },
    { key: "name", label: "Trainer name", value: record.name || "", required: true },
    { key: "specialization", label: "Specialization", value: record.specialization || "", required: true },
    { key: "phone", label: "Phone number", value: record.phone || "", type: "tel", pattern: "[0-9+() .-]{7,32}", required: true },
    { key: "email", label: "Email address", value: record.email || "", type: "email" }
  ];
  if (route === "programs") return [
    { key: "title", label: "Program title", value: record.title || "", required: true },
    { key: "category", label: "Training category", value: record.category || "", required: true },
    { key: "duration", label: "Duration", value: record.duration || "", required: true, placeholder: "e.g. 2 days" },
    { key: "level", label: "Learning level", value: record.level || "Foundation", type: "select", options: ["Foundation", "Intermediate", "Advanced"], required: true },
    { key: "status", label: "Program status", value: record.status || "active", type: "select", options: [["active", "Active"], ["draft", "Draft"], ["archived", "Archived"]], required: true },
    { key: "description", label: "Program overview", value: record.description || "", type: "textarea", required: true, wide: true },
    { key: "objectives", label: "Learning objectives", value: record.objectives || "", type: "textarea", wide: true }
  ];
  const userRole = record.role || "farmer";
  return [
    { key: "username", label: "Username", value: record.username || "", required: true, readonly: !isNew },
    { key: "name", label: "Full name", value: record.name || "", required: true },
    { key: "role", label: "Account role", value: userRole, type: "select", options: roleOptions, required: true, disabled: !isNew },
    ...(isNew ? [{ key: "password", label: "Initial password", value: "", type: "password", minlength: 12, required: true, help: "At least 12 characters. It is hashed by the server and never returned." }] : []),
    { key: "email", label: "Email address", value: record.email || "", type: "email" },
    { key: "phone", label: "Phone number", value: record.phone || "", type: "tel", pattern: "[0-9+() .-]{7,32}" },
    ...(isNew ? [{ key: "status", label: "Account status", value: record.account_status || "active", type: "select", options: [["active", "Active"], ["inactive", "Inactive"]], required: true }] : []),
    ...(isNew ? [
      { key: "farmer_id", label: "Farmer ID (required for farmer role)", value: createId("F") },
      { key: "village", label: "Village (required for farmer role)", value: "" },
      { key: "trainer_id", label: "Trainer ID (required for trainer role)", value: createId("T") },
      { key: "specialization", label: "Specialization (required for trainer role)", value: "" }
    ] : [])
  ];
}

function formMarkup(route, fields, isNew) {
  const controls = fields.map((field) => {
    const id = `field-${field.key}`;
    const required = field.required ? "required" : "";
    const readonly = field.readonly ? "readonly" : "";
    const common = `class="form-control" id="${escapeHtml(id)}" name="${escapeHtml(field.key)}" ${required} ${readonly} ${field.minlength ? `minlength="${field.minlength}"` : ""} ${field.pattern ? `pattern="${escapeHtml(field.pattern)}"` : ""} ${field.placeholder ? `placeholder="${escapeHtml(field.placeholder)}"` : ""}`;
    let control;
    if (field.type === "select") control = `<select class="form-select" id="${escapeHtml(id)}" name="${escapeHtml(field.key)}" ${required} ${field.disabled ? "disabled" : ""}>${optionMarkup(field.options, field.value)}</select>${field.disabled ? `<input type="hidden" name="${escapeHtml(field.key)}" value="${escapeHtml(field.value)}">` : ""}`;
    else if (field.type === "textarea") control = `<textarea ${common} rows="3">${escapeHtml(field.value)}</textarea>`;
    else control = `<input ${common} type="${escapeHtml(field.type || "text")}" value="${escapeHtml(field.value)}">`;
    return `<div class="${field.wide ? "col-12" : "col-md-6"}"><label class="form-label" for="${escapeHtml(id)}">${escapeHtml(field.label)}${field.required ? " *" : ""}</label>${control}${field.help ? `<small class="muted">${escapeHtml(field.help)}</small>` : ""}</div>`;
  }).join("");
  return `<div class="row g-3">${controls}</div>`;
}

const displayValue = (key, value) => {
  if (key === "status") return statusPill(key === "status" && ["active", "draft", "archived"].includes(value) ? titleCase(value) : value);
  if (key === "joined") return escapeHtml(formatDate(value));
  if (key === "role") return escapeHtml(roleTitle[value] || value);
  return escapeHtml(value ?? "—");
};

async function farmerDetails(record) {
  const [attendance, progress] = await Promise.all([
    listRecords("attendance", { farmer_id: record.id }),
    listRecords("progress", { farmer_id: record.id })
  ]);
  return `<div class="row g-3">
    <div class="col-6"><span class="muted small">Farmer ID</span><strong class="d-block">${escapeHtml(record.farmerCode)}</strong></div>
    <div class="col-6"><span class="muted small">Phone</span><strong class="d-block">${escapeHtml(record.phone)}</strong></div>
    <div class="col-6"><span class="muted small">Village</span><strong class="d-block">${escapeHtml(record.village)}</strong></div>
    <div class="col-6"><span class="muted small">Attendance records</span><strong class="d-block">${attendance.length}</strong></div>
    <div class="col-12"><hr><strong>Training progress</strong>${progress.length ? progress.map((item) => `<div class="progress-row"><div class="progress-row-head"><span>${escapeHtml(item.program_name || "Training program")}</span><span>${item.percent}%</span></div><div class="progress-track"><div class="progress-fill" style="width:${item.percent}%"></div></div><small>${escapeHtml(titleCase(item.result))}</small></div>`).join("") : emptyState("No progress recorded", "Training results will appear here when available.")}</div>
  </div>`;
}

async function openRecordView(route, record) {
  if (route === "farmers") {
    try {
      showDialog({ title: `${record.name} · Farmer details`, body: await farmerDetails(record), submitLabel: "Done", onSubmit: () => document.getElementById("record-dialog").close() });
    } catch (error) { toast(error.message, "error"); }
    return;
  }
  const fields = definitions[route].columns.map(([key, label]) => `<div class="mb-3"><span class="muted small d-block">${escapeHtml(label)}</span><strong>${displayValue(key, record[key])}</strong></div>`).join("");
  showDialog({ title: record.name || record.title || record.username, body: fields, submitLabel: "Done", onSubmit: () => document.getElementById("record-dialog").close() });
}

export async function renderDirectory(route, user) {
  const definition = definitions[route];
  if (!definition) return document.createElement("section");
  const canWrite = user.role === "admin" || user.role === "coordinator";
  const canView = route === "farmers" && ["trainer", "management"].includes(user.role);
  const farmerEnroll = route === "programs" && user.role === "farmer";
  let records;
  let enrollments = [];
  try {
    records = await listRecords(route);
    if (farmerEnroll) enrollments = await listRecords("enrollments");
  }
  catch (error) {
    const failed = document.createElement("section");
    failed.className = "panel";
    failed.innerHTML = emptyState("Could not load records", error.message, "bi-cloud-slash");
    return failed;
  }
  let page = 1;
  let search = "";
  let filter = "";
  const pageSize = 8;
  const fields = definitions[route].columns.map(([key]) => key);
  const filterKey = route === "farmers" ? "village" : route === "programs" ? "status" : route === "users" ? "status" : "";
  const filterOptions = [...new Set(records.map((record) => record[filterKey]).filter(Boolean))];
  const content = document.createElement("div");
  content.className = "module-container";
  content.innerHTML = `
    <div class="page-title-row"><div><span class="eyebrow">${escapeHtml(definition.plural)}</span><h1>${escapeHtml(definition.plural)}</h1><p>${escapeHtml(definition.description)}</p></div><div class="page-actions">${canWrite ? `<button class="btn-brand" data-add><i class="bi bi-plus-lg"></i> Add ${escapeHtml(definition.singular)}</button>` : ""}</div></div>
    <div class="module-note"><i class="bi bi-info-circle"></i><span>Records are retrieved from the AgriLearn server. Changes are saved to the connected database. ${route === "users" ? "Initial passwords are used only to create secure accounts." : ""}</span></div>
    <section class="panel"><div class="table-toolbar"><div class="table-toolbar-left"><label class="search-control"><i class="bi bi-search"></i><input class="form-control" data-search type="search" placeholder="Search ${escapeHtml(definition.plural.toLowerCase())}" aria-label="Search ${escapeHtml(definition.plural.toLowerCase())}"></label><select class="form-select" data-filter aria-label="Filter records"><option value="">All ${escapeHtml(definition.plural)}</option>${optionMarkup(filterOptions.map((option) => [option, route === "programs" || route === "users" ? titleCase(option) : option]))}</select></div><span class="muted small" data-count></span></div><div class="data-table-wrap" data-table></div><div class="table-footer"><span data-page-label></span><div class="pagination-buttons" data-pagination></div></div></section>`;

  const renderRows = () => {
    const filtered = records.filter((record) => {
      const searchMatch = !search || Object.values(record).some((value) => String(value ?? "").toLowerCase().includes(search));
      const matchesFilter = !filter || String(filterKey === "status" && route === "users" ? record.account_status : record[filterKey]) === filter;
      return searchMatch && matchesFilter;
    });
    const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
    page = Math.min(page, pageCount);
    const visible = filtered.slice((page - 1) * pageSize, page * pageSize);
    content.querySelector("[data-count]").textContent = `${filtered.length} record${filtered.length === 1 ? "" : "s"}`;
    content.querySelector("[data-page-label]").textContent = filtered.length ? `Showing ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, filtered.length)} of ${filtered.length}` : "No records to display";
    content.querySelector("[data-pagination]").innerHTML = Array.from({ length: pageCount }, (_, index) => `<button type="button" class="${index + 1 === page ? "active" : ""}" data-page="${index + 1}" aria-label="Page ${index + 1}">${index + 1}</button>`).join("");
    const actions = canWrite || canView || farmerEnroll;
    if (!visible.length) {
      content.querySelector("[data-table]").innerHTML = emptyState("No matching records", "Try changing the search or filter, or add a new record.");
      return;
    }
    content.querySelector("[data-table]").innerHTML = `<table class="data-table"><thead><tr>${definition.columns.map(([, label]) => `<th>${escapeHtml(label)}</th>`).join("")}${actions ? "<th>Actions</th>" : ""}</tr></thead><tbody>${visible.map((record) => {
      const name = record.name || record.title || record.username || definition.singular;
      const status = route === "users" ? record.account_status : record.status;
      const enrolled = farmerEnroll && enrollments.some((item) => String(item.program_id) === String(record.id) && item.participation_status !== "withdrawn");
      return `<tr data-record="${escapeHtml(record.id)}">${definition.columns.map(([key]) => {
        let value = record[key];
        if (key === "status" && route === "users") value = status === "active" ? "Active" : "Inactive";
        if (key === "status" && route === "programs") value = titleCase(value);
        if (key === "role") value = roleTitle[value] || value;
        if (key === "joined") value = formatDate(value);
        return `<td>${key === "name" || key === "title" ? `<strong>${escapeHtml(value || "—")}</strong>` : key === "status" ? statusPill(value) : escapeHtml(value ?? "—")}</td>`;
      }).join("")}${actions ? `<td><div class="table-actions">${canWrite ? route === "users" ? `<button class="icon-btn" type="button" data-action="edit" aria-label="Edit ${escapeHtml(name)}"><i class="bi bi-pencil"></i></button><button class="icon-btn ${status === "active" ? "danger" : ""}" type="button" data-action="toggle-status" aria-label="${status === "active" ? "Deactivate" : "Activate"} ${escapeHtml(name)}"><i class="bi ${status === "active" ? "bi-person-x" : "bi-person-check"}"></i></button>` : `<button class="icon-btn" type="button" data-action="edit" aria-label="Edit ${escapeHtml(name)}"><i class="bi bi-pencil"></i></button><button class="icon-btn danger" type="button" data-action="delete" aria-label="Deactivate ${escapeHtml(name)}"><i class="bi bi-person-dash"></i></button>` : farmerEnroll ? enrolled ? `<button class="btn-outline-brand btn-sm" type="button" disabled>Enrolled</button>` : `<button class="btn-outline-brand btn-sm" type="button" data-action="enroll">Enroll</button>` : `<button class="icon-btn" type="button" data-action="view" aria-label="View ${escapeHtml(name)}"><i class="bi bi-eye"></i></button>`}</div></td>` : ""}</tr>`;
    }).join("")}</tbody></table>`;
  };
  const refresh = async () => {
    try { records = await listRecords(route); renderRows(); }
    catch (error) { toast(`Could not refresh records: ${error.message}`, "error"); }
  };
  const openForm = (record = {}, isNew = false) => {
    const formFields = fieldsFor(route, record, isNew);
    showDialog({
      title: `${isNew ? "Add" : "Edit"} ${definition.singular}`,
      body: formMarkup(route, formFields, isNew),
      submitLabel: isNew ? `Add ${definition.singular}` : "Save changes",
      onSubmit: async (formData) => {
        const next = { ...record };
        formFields.forEach((field) => {
          if (field.readonly) return;
          const value = String(formData.get(field.key) || "");
          next[field.key] = field.key === "password" ? value : value.trim();
        });
        if (route === "farmers") next.farmer_id = next.farmerCode;
        if (route === "trainers") next.trainer_id = next.trainerCode;
        try {
          await saveRecord(route, next, isNew);
          document.getElementById("record-dialog").close();
          toast(`${definition.singular} ${isNew ? "created" : "updated"} successfully.`);
          await refresh();
        } catch (error) { toast(error.message, "error"); }
      }
    });
    if (route === "users" && isNew) {
      const roleControl = document.getElementById("field-role");
      const syncRoleFields = () => {
        const role = roleControl.value;
        const phone = document.getElementById("field-phone");
        if (phone) phone.required = role === "farmer" || role === "trainer";
        ["farmer_id", "village", "trainer_id", "specialization"].forEach((key) => {
          const input = document.getElementById(`field-${key}`);
          const group = input?.closest(".col-md-6");
          if (!input || !group) return;
          const active = role === "farmer" ? ["farmer_id", "village"].includes(key) : role === "trainer" && ["trainer_id", "specialization"].includes(key);
          group.hidden = !active;
          input.required = active && key !== "specialization" ? true : active;
        });
      };
      roleControl.addEventListener("change", syncRoleFields);
      syncRoleFields();
    }
  };

  renderRows();
  content.querySelector("[data-search]").addEventListener("input", (event) => { search = event.target.value.trim().toLowerCase(); page = 1; renderRows(); });
  content.querySelector("[data-filter]").addEventListener("change", (event) => {
    filter = event.target.value === "Active" ? "active" : event.target.value === "Inactive" ? "inactive" : event.target.value;
    page = 1;
    renderRows();
  });
  content.querySelector("[data-pagination]").addEventListener("click", (event) => {
    const button = event.target.closest("[data-page]");
    if (!button) return;
    page = Number(button.dataset.page);
    renderRows();
  });
  content.querySelector("[data-add]")?.addEventListener("click", () => openForm({}, true));
  content.querySelector("[data-table]").addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const row = button.closest("[data-record]");
    const record = records.find((item) => String(item.id) === row.dataset.record);
    if (!record) return;
    if (button.dataset.action === "edit") { openForm(record); return; }
    if (button.dataset.action === "view") { await openRecordView(route, record); return; }
    if (button.dataset.action === "toggle-status") {
      const next = record.account_status === "active" ? "inactive" : "active";
      if (!window.confirm(`${next === "inactive" ? "Deactivate" : "Activate"} ${record.name}'s account?`)) return;
      try { await setUserStatus(record.id, next); toast(`Account ${next === "active" ? "activated" : "deactivated"}.`); await refresh(); }
      catch (error) { toast(error.message, "error"); }
      return;
    }
    if (button.dataset.action === "delete") {
      if (!window.confirm(`Deactivate ${record.name || record.title || record.username}? Existing training history will be preserved.`)) return;
      try { await deactivateRecord(route, record.id); toast(`${definition.singular} deactivated.`); await refresh(); }
      catch (error) { toast(error.message, "error"); }
      return;
    }
    if (button.dataset.action === "enroll") {
      try {
        await apiRequest("/enrollments", { method: "POST", body: { program_id: Number(record.id) } });
        toast("You are enrolled in this training program.");
        enrollments = await listRecords("enrollments");
        renderRows();
      } catch (error) { toast(error.message, "error"); }
    }
  });
  return content;
}

export async function renderDirectoryPage(route, user) {
  if (!canAccess(route, user)) {
    const denied = document.createElement("section");
    denied.className = "access-denied";
    denied.innerHTML = `<i class="bi bi-shield-lock"></i><h1 class="h4 mt-3">Access restricted</h1><p class="muted">Your ${escapeHtml(user.role)} account cannot access this module.</p><a class="btn-brand" href="#/dashboard">Return to dashboard</a>`;
    return denied;
  }
  return renderDirectory(route, user);
}
