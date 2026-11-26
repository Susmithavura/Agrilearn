export function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

export function toast(message, type = "success") {
  const region = document.getElementById("toast-region");
  if (!region) return;
  const element = document.createElement("div");
  element.className = `app-toast${type === "error" ? " error" : ""}`;
  element.setAttribute("role", type === "error" ? "alert" : "status");
  element.innerHTML = `<i class="bi ${type === "error" ? "bi-exclamation-circle" : "bi-check-circle"}"></i><span>${escapeHtml(message)}</span>`;
  region.append(element);
  window.setTimeout(() => element.remove(), 4200);
}

export function showDialog({ title, body, submitLabel = "Save", onSubmit, confirm = false }) {
  const dialog = document.getElementById("record-dialog");
  const target = document.getElementById("dialog-content");
  target.innerHTML = `
    <form id="record-form">
      <div class="dialog-head"><h2 id="dialog-title">${escapeHtml(title)}</h2><button class="dialog-close" type="button" aria-label="Close dialog" data-dialog-close><i class="bi bi-x-lg"></i></button></div>
      <div class="dialog-body">${body}</div>
      <div class="dialog-foot"><button class="btn-outline-brand" type="button" data-dialog-close>Cancel</button><button class="${confirm ? "btn btn-danger" : "btn-brand"}" type="submit">${escapeHtml(submitLabel)}</button></div>
    </form>`;
  const form = target.querySelector("#record-form");
  target.querySelectorAll("[data-dialog-close]").forEach((button) => button.addEventListener("click", () => dialog.close()));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    await onSubmit(new FormData(form), form);
  });
  dialog.showModal();
  const firstInput = form.querySelector("input, select, textarea, button");
  firstInput?.focus();
}

export function emptyState(title, message, icon = "bi-inbox") {
  return `<div class="empty-state"><i class="bi ${icon}"></i><strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span></div>`;
}

export function formatDate(dateString, options = { month: "short", day: "numeric", year: "numeric" }) {
  if (!dateString) return "—";
  const value = String(dateString);
  const parsed = new Date(value);
  const dateOnly = Number.isNaN(parsed.getTime()) ? null : parsed.toISOString().slice(0, 10);
  const date = dateOnly ? new Date(`${dateOnly}T00:00:00`) : new Date(NaN);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString(undefined, options);
}

export function statusPill(status) {
  const normalized = String(status || "").toLowerCase();
  const tone = normalized.includes("present") || normalized.includes("complete") || normalized === "active"
    ? "green"
    : normalized.includes("absent") || normalized.includes("not started") || normalized.includes("inactive")
      ? "red"
      : normalized.includes("progress") || normalized.includes("scheduled")
        ? "amber"
        : "grey";
  return `<span class="status-pill status-${tone}">${escapeHtml(status || "Not recorded")}</span>`;
}

export function initials(name = "") {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0] || "").join("").toUpperCase() || "U";
}
