import { canAccess, ROLE_LABELS } from "./auth.js";
import { listRecords, titleCase } from "./data.js";
import { apiRequest } from "./api.js";
import { emptyState, escapeHtml, formatDate, statusPill } from "./ui.js";

const dashboardCopy = {
  farmer: ["Your learning journey", "Explore available programs, check upcoming sessions and follow your own training progress."],
  trainer: ["Your training workspace", "Review assigned sessions, prepare farmer lists and record participation."],
  coordinator: ["Training operations", "Coordinate farmer records, trainer assignments, program delivery and participation reporting."],
  management: ["Program overview", "Review training activity, participation and learning outcomes."],
  admin: ["System administration", "Manage user accounts and maintain the core training records."]
};

function cardsForRole(role, data) {
  if (role === "farmer") return [
    ["Available Programs", data.available_programs, "Open for enrollment", "bi-journal-richtext"],
    ["My Enrollments", data.enrolled_programs, "Programs you joined", "bi-bookmark-check"],
    ["Upcoming Sessions", data.upcoming_sessions?.length || 0, "On your schedule", "bi-calendar-event"],
    ["Attendance Records", data.attendance_records, "Your recorded participation", "bi-person-check"]
  ];
  if (role === "trainer") return [
    ["Assigned Programs", data.assigned_programs, "Programs with your sessions", "bi-journal-richtext"],
    ["Assigned Sessions", data.assigned_sessions, "Your training schedule", "bi-calendar-event"],
    ["Farmers in Programs", data.farmers_invited, "Across your assigned programs", "bi-people"],
    ["Attendance Records", data.attendance_records, "Recorded for your sessions", "bi-person-check"]
  ];
  if (role === "management") return [
    ["Active Farmers", data.farmers, "Available for training", "bi-people"],
    ["Active Programs", data.programs, "Available for scheduling", "bi-journal-richtext"],
    ["Attendance Records", data.attendance_records, "Saved participation", "bi-person-check"],
    ["Completed Trainings", data.completed_progress, "Recorded completions", "bi-award"]
  ];
  if (role === "admin") return [
    ["User Accounts", data.users, "All registered accounts", "bi-shield-lock"],
    ["Inactive Accounts", data.inactive_users, "Currently disabled", "bi-person-lock"],
    ["Active Farmers", data.farmers, "Available for training", "bi-people"],
    ["Active Trainers", data.trainers, "Available for assignment", "bi-person-badge"],
    ["Active Programs", data.programs, "Available for scheduling", "bi-journal-richtext"],
    ["Upcoming Sessions", data.upcoming_sessions, "Scheduled from today", "bi-calendar-event"]
  ];
  return [
    ["Active Farmers", data.farmers, "Available for training", "bi-people"],
    ["Active Trainers", data.trainers, "Available for assignment", "bi-person-badge"],
    ["Active Programs", data.programs, "Available for scheduling", "bi-journal-richtext"],
    ["Upcoming Sessions", data.upcoming_sessions, "Scheduled from today", "bi-calendar-event"]
  ];
}

function updateApiStatus(connected) {
  const badge = document.querySelector(".overview-shell [data-api-status]");
  if (!badge) return;
  badge.dataset.apiStatus = connected ? "connected" : "unavailable";
  badge.setAttribute("aria-label", connected ? "AgriLearn API connected" : "AgriLearn API unavailable");
  badge.innerHTML = connected
    ? '<i class="bi bi-cloud-check" aria-hidden="true"></i><span>Connected</span>'
    : '<i class="bi bi-cloud-slash" aria-hidden="true"></i><span>Unavailable</span>';
}

function attendanceChart(records) {
  const labels = [];
  const values = [];
  for (let offset = 5; offset >= 0; offset--) {
    const date = new Date();
    date.setDate(1);
    date.setMonth(date.getMonth() - offset);
    labels.push(date.toLocaleDateString(undefined, { month: "short" }));
    values.push(records.filter((record) => {
      const stamp = new Date(record.recorded_at || record.submittedAt || "");
      return stamp.getMonth() === date.getMonth() && stamp.getFullYear() === date.getFullYear();
    }).length);
  }
  const max = Math.max(1, ...values);
  const points = values.map((value, index) => `${45 + index * 64},${172 - (value / max) * 125}`).join(" ");
  const area = `${points} 365,185 45,185`;
  return `<div class="chart-area"><svg viewBox="0 0 410 210" role="img" aria-label="Attendance records by month">${[45,85,125,165].map((y) => `<line x1="38" y1="${y}" x2="390" y2="${y}" class="chart-grid-line"></line>`).join("")}<defs><linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#6da875" stop-opacity=".24"></stop><stop offset="1" stop-color="#6da875" stop-opacity="0"></stop></linearGradient></defs><polygon points="${area}" class="chart-area-fill"></polygon><polyline points="${points}" class="chart-line"></polyline>${values.map((value,index) => `<circle cx="${45+index*64}" cy="${172-(value/max)*125}" r="4" class="chart-dot"><title>${labels[index]}: ${value} records</title></circle>`).join("")}${labels.map((label,index) => `<text x="${45+index*64}" y="202" text-anchor="middle" class="chart-label">${label}</text>`).join("")}</svg></div>`;
}

const actions = {
  farmer: [["Browse programs","programs","bi-journal-richtext"],["My schedule","schedules","bi-calendar-week"],["My progress","progress","bi-graph-up-arrow"]],
  trainer: [["Farmer roster","farmers","bi-people"],["Record attendance","attendance","bi-person-check"],["My sessions","schedules","bi-calendar-week"],["Training progress","progress","bi-graph-up-arrow"]],
  coordinator: [["Manage farmers","farmers","bi-people"],["Manage trainers","trainers","bi-person-badge"],["Programs & schedules","programs","bi-journal-richtext"],["Review reports","reports","bi-file-earmark-bar-graph"]],
  management: [["Training schedules","schedules","bi-calendar-week"],["Participation progress","progress","bi-graph-up-arrow"],["Open reports","reports","bi-file-earmark-bar-graph"]],
  admin: [["System users","users","bi-shield-lock"],["Farmer records","farmers","bi-people"],["Trainer records","trainers","bi-person-badge"],["Program records","programs","bi-journal-richtext"]]
};

function sessionRows(items) {
  if (!items.length) return emptyState("Nothing scheduled yet", "New training sessions will appear here when available.", "bi-calendar2-week");
  return `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Training session</th><th>Trainer</th><th>Date</th><th>Time</th><th>Location</th></tr></thead><tbody>${items.slice(0,5).map((session) => `<tr><td><strong>${escapeHtml(session.program_name || session.program_title || "Training")}</strong></td><td>${escapeHtml(session.trainer_name || "—")}</td><td>${escapeHtml(formatDate(session.session_date || session.date))}</td><td>${escapeHtml(String(session.start_time || session.time || "").slice(0,5))}</td><td>${escapeHtml(session.location || "—")}</td></tr>`).join("")}</tbody></table></div>`;
}

export async function renderDashboard(user) {
  const role = user.role;
  const content = document.createElement("div");
  content.className = "dashboard-container";
  content.dataset.role = role;
  content.innerHTML = `<div class="empty-state"><span class="spinner-border text-success" aria-hidden="true"></span><strong>Loading your dashboard</strong><span>Retrieving current training data…</span></div>`;
  try {
    const data = await apiRequest(`/dashboard/${role}`);
    const attendance = await listRecords("attendance");
    const sessions = ["farmer", "trainer"].includes(role)
      ? data.upcoming_sessions || []
      : (await listRecords("sessions")).filter((session) => session.status === "scheduled" && session.date >= new Date().toISOString().slice(0,10)).sort((a,b) => a.date.localeCompare(b.date)).slice(0,5);
    updateApiStatus(true);
    const profilePanel = role === "farmer" && data.profile
      ? `<section class="panel"><div class="panel-head"><div><span class="eyebrow">Your account</span><h2>Farmer profile</h2></div></div><div class="row g-3"><div class="col-sm-6"><span class="muted small">Farmer ID</span><strong class="d-block">${escapeHtml(data.profile.farmer_id)}</strong></div><div class="col-sm-6"><span class="muted small">Village</span><strong class="d-block">${escapeHtml(data.profile.village)}</strong></div><div class="col-sm-6"><span class="muted small">Phone</span><strong class="d-block">${escapeHtml(data.profile.phone || "—")}</strong></div><div class="col-sm-6"><span class="muted small">Email</span><strong class="d-block">${escapeHtml(data.profile.email || "—")}</strong></div></div></section>`
      : "";
    content.innerHTML = `
      <div class="dashboard-welcome"><div><span class="eyebrow">${escapeHtml(ROLE_LABELS[role])} workspace</span><h1>${escapeHtml(dashboardCopy[role][0])}, ${escapeHtml(user.name.split(" ")[0])}.</h1><p>${escapeHtml(dashboardCopy[role][1])}</p></div><div class="welcome-mark"><i class="bi bi-flower1"></i></div></div>
      ${profilePanel}
      <div class="stats-grid">${cardsForRole(role, data).map(([label,value,note,icon]) => `<article class="stat-card"><span class="stat-label">${escapeHtml(label)}</span><strong class="stat-value">${escapeHtml(value ?? 0)}</strong><small class="stat-hint">${escapeHtml(note)}</small><span class="stat-icon" aria-hidden="true"><i class="bi ${icon}"></i></span></article>`).join("")}</div>
      <div class="dashboard-grid"><section class="panel chart-panel"><div class="panel-head"><div><span class="eyebrow">Participation activity</span><h2>Attendance overview</h2></div><span class="status-pill status-green">Live records</span></div>${attendanceChart(attendance)}</section><section class="panel quick-panel"><div class="panel-head"><div><span class="eyebrow">Your workspace</span><h2>Quick actions</h2></div></div><div class="quick-links">${actions[role].filter(([, route]) => canAccess(route, user)).map(([label,route,icon]) => `<a href="#/${route}" class="quick-link"><span class="quick-link-icon" aria-hidden="true"><i class="bi ${icon}"></i></span><span class="quick-link-label">${escapeHtml(label)}</span><i class="bi bi-arrow-up-right quick-link-arrow" aria-hidden="true"></i></a>`).join("")}</div></section></div>
      <section class="panel dashboard-sessions"><div class="panel-head"><div><span class="eyebrow">Training calendar</span><h2>Upcoming sessions</h2></div><a class="text-link" href="#/schedules">View schedule <i class="bi bi-arrow-right"></i></a></div>${sessionRows(sessions)}</section>`;
  } catch (error) {
    updateApiStatus(false);
    content.innerHTML = `<section class="panel">${emptyState("Dashboard data unavailable", error.message, "bi-cloud-slash")}</section>`;
  }
  return content;
}
