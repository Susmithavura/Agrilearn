import { authenticate, canAccess, currentUser, logout, restoreSession, ROLE_LABELS } from "./auth.js";
import { renderDashboard } from "./dashboard.js";
import { renderDirectoryPage } from "./modules.js";
import { renderSchedules } from "./schedules.js";
import { renderAttendance } from "./attendance.js";
import { renderProgress } from "./progress.js";
import { renderReports } from "./reports.js";
import { escapeHtml, initials, showDialog, toast } from "./ui.js";
import { apiRequest } from "./api.js";

const app = document.getElementById("app");
const routeTitles = {
  dashboard: "Overview", farmers: "Farmers", trainers: "Trainers", programs: "Training programs",
  schedules: "Training schedules", attendance: "Attendance", progress: "Training progress",
  reports: "Reports", users: "System users"
};
const navByRole = {
  farmer: [["dashboard", "Overview", "bi-grid-1x2"], ["programs", "Available programs", "bi-journal-richtext"], ["schedules", "My schedule", "bi-calendar-week"], ["attendance", "My attendance", "bi-person-check"], ["progress", "My progress", "bi-graph-up-arrow"]],
  trainer: [["dashboard", "Overview", "bi-grid-1x2"], ["programs", "Assigned programs", "bi-journal-richtext"], ["schedules", "My sessions", "bi-calendar-week"], ["farmers", "Farmer lists", "bi-people"], ["attendance", "Attendance", "bi-person-check"], ["progress", "Training progress", "bi-graph-up-arrow"]],
  coordinator: [["dashboard", "Overview", "bi-grid-1x2"], ["farmers", "Farmers", "bi-people"], ["trainers", "Trainers", "bi-person-badge"], ["programs", "Training programs", "bi-journal-richtext"], ["schedules", "Training schedules", "bi-calendar-week"], ["attendance", "Participation", "bi-person-check"], ["progress", "Training progress", "bi-graph-up-arrow"], ["reports", "Reports", "bi-file-earmark-bar-graph"]],
  management: [["dashboard", "Overview", "bi-grid-1x2"], ["farmers", "Participants", "bi-people"], ["trainers", "Trainers", "bi-person-badge"], ["programs", "Training programs", "bi-journal-richtext"], ["schedules", "Training schedules", "bi-calendar-week"], ["attendance", "Attendance", "bi-person-check"], ["progress", "Training progress", "bi-graph-up-arrow"], ["reports", "Reports", "bi-file-earmark-bar-graph"]],
  admin: [["dashboard", "Overview", "bi-grid-1x2"], ["users", "User management", "bi-shield-lock"], ["farmers", "Farmers", "bi-people"], ["trainers", "Trainers", "bi-person-badge"], ["programs", "Training programs", "bi-journal-richtext"], ["schedules", "Training schedules", "bi-calendar-week"], ["attendance", "Attendance", "bi-person-check"], ["progress", "Training progress", "bi-graph-up-arrow"], ["reports", "Reports", "bi-file-earmark-bar-graph"]]
};
const aliases = {
  "farmer-dashboard": "farmer", "trainer-dashboard": "trainer", "coordinator-dashboard": "coordinator",
  "management-dashboard": "management", "admin-dashboard": "admin"
};
let renderVersion = 0;

function getRoute() {
  return location.hash.startsWith("#/") ? location.hash.slice(2).split("?")[0] : "landing";
}

function brandMarkup(onLanding = false, onLogin = false) {
  return `<a class="brand-mark" href="${onLanding || onLogin ? "#/" : "#/dashboard"}" aria-label="AgriLearn home">
    <span class="brand-symbol"><i class="bi bi-flower1"></i></span>
    <span><span class="brand-name">AgriLearn</span><span class="brand-caption">Farmer Training Management System</span></span>
  </a>`;
}

function renderLanding() {
  app.innerHTML = `<div class="demo-banner"><i class="bi bi-info-circle"></i>VVITU · Software Engineering · Academic Year 2026–27</div>
    <header class="landing-nav d-flex align-items-center justify-content-between">
      ${brandMarkup(true)}
      <nav class="d-flex align-items-center gap-3" aria-label="Main navigation">
        <a class="nav-link d-none d-sm-inline" href="#landing-modules">Platform</a>
        <a class="nav-link d-none d-sm-inline" href="#project-intro">About</a>
        <a class="btn-outline-brand" href="#/login"><i class="bi bi-box-arrow-in-right"></i> Sign in</a>
      </nav>
    </header>
    <main>
      <section class="hero">
        <span class="leaf"><i class="bi bi-leaf"></i></span><span class="leaf leaf-two"><i class="bi bi-leaf-fill"></i></span>
        <div class="hero-content">
          <span class="eyebrow text-white">VVITU · SOFTWARE ENGINEERING · 2026–27</span>
          <h1>Better learning.<br><span>Stronger communities.</span></h1>
          <p class="hero-copy">A considered digital workspace for the people behind farmer training — connecting participants, trainers and coordinators from first session to final result.</p>
          <div class="hero-actions"><a class="btn-brand" href="#/login">Explore AgriLearn <i class="bi bi-arrow-up-right"></i></a><a class="btn-outline-brand" href="#project-intro">Discover the project</a></div>
          <div class="hero-meta"><span>II Year B.Tech – I Semester</span><span>Software Engineering</span><span>Farmer Training Management System</span></div>
        </div>
      </section>
      <section class="section-wrap" id="landing-modules">
        <div class="section-heading"><span class="eyebrow">One connected workflow</span><h2>Training management, thoughtfully brought together.</h2><p>AgriLearn is built specifically for organizing farmer education — not general farm operations. Keep people, programs, sessions and learning outcomes connected in one clear view.</p></div>
        <div class="row g-3">
          ${[
            ["bi-people", "Farmer records", "Maintain organized participant profiles and make relevant training information easy to find."],
            ["bi-person-badge", "Trainer coordination", "Keep agricultural officer contact details, areas of expertise and assignments together."],
            ["bi-journal-richtext", "Training programs", "Create clear program records with learning themes, duration and training details."],
            ["bi-calendar2-week", "Session scheduling", "Coordinate dates, times, locations, invitations and assigned trainers in a shared calendar."],
            ["bi-person-check", "Attendance", "Give trainers a straightforward way to record participation for each training session."],
            ["bi-graph-up-arrow", "Progress & reports", "Follow recorded completion, review participation and prepare readable reports."]
          ].map(([icon, title, copy]) => `<div class="col-md-6 col-lg-4"><article class="feature-card"><span class="feature-icon"><i class="bi ${icon}"></i></span><h3>${title}</h3><p>${copy}</p></article></div>`).join("")}
        </div>
      </section>
      <section class="section-wrap pt-0" id="project-intro">
        <div class="intro-panel">
          <div><span class="eyebrow">The project</span><h2>Less paperwork between people and practical learning.</h2>
            <p class="muted">Traditional training administration often relies on separate manual records for farmers, trainers, programs, schedules, attendance and results. That can mean time-consuming updates, hard-to-trace participation and delayed reporting.</p>
            <p class="muted mb-0">AgriLearn proposes a centralized web-based management information system to organize those activities, support role-appropriate access and make the training journey easier to follow.</p>
          </div>
          <div><strong class="d-block mb-3 text-success">Project objectives</strong><ul class="objective-list">
            ${["Centralize farmer records", "Organize trainer information", "Manage training programs", "Schedule and assign sessions", "Record participation", "Monitor learning progress", "Provide training results", "Generate useful reports", "Support role-based access", "Reduce manual administration"].map((item) => `<li><i class="bi bi-check-circle-fill"></i>${item}</li>`).join("")}
          </ul></div>
        </div>
        <div class="quote-card mt-3"><span class="eyebrow" style="color:#d4ef79">AgriLearn</span><p>“Empowering Farmers Through Digital Learning and Training Management.”</p><span class="small text-white-50">Vasireddy Venkatadri International Technological University · Academic Year 2026–27</span></div>
      </section>
      <section class="section-wrap pt-0">
        <div class="section-heading"><span class="eyebrow">Five connected roles</span><h2>Clear views for everyone involved.</h2><p>Secure, role-based workspaces connect farmers, trainers, coordinators, management and system administrators.</p></div>
        <div class="d-flex flex-wrap gap-2">${["Farmer", "Trainer / Agricultural Officer", "Training Coordinator", "Agricultural Department / Management", "System Administrator"].map((name) => `<span class="status-pill status-green"><i class="bi bi-person-check"></i>${name}</span>`).join("")}</div>
      </section>
    </main>
    <footer class="site-footer d-flex flex-wrap justify-content-between gap-2"><span><strong>VVITU</strong> · AgriLearn Farmer Training Management System</span><span>II Year B.Tech – I Semester · Software Engineering · 2026–27</span></footer>`;
}

function renderLogin() {
  if (currentUser()) {
    location.hash = "#/dashboard";
    return;
  }
  app.innerHTML = `<div class="demo-banner"><i class="bi bi-shield-check"></i>Secure AgriLearn account · Contact your system administrator if you need access</div>
    <main class="login-page">
      <section class="login-visual"><div class="login-visual-copy"><span class="eyebrow text-white">VVITU · AGRILEARN</span><h1>Learning that reaches every field community.</h1><p>One connected place for farmer training programs, people, participation and progress.</p><span class="small text-white-50">Farmer Training Management System · Academic Year 2026–27</span></div></section>
      <section class="login-main"><div class="login-card">
        ${brandMarkup(false, true)}
        <h2>Welcome back</h2><p class="muted mb-4">Sign in to your role-based training workspace.</p>
        <form id="login-form" novalidate>
          <div class="mb-3"><label class="form-label" for="login-username">Username</label><input class="form-control" id="login-username" name="username" autocomplete="username" required minlength="2" placeholder="Enter your username"></div>
          <div class="mb-3"><label class="form-label" for="login-role">Expected portal</label><select class="form-select" id="login-role" name="role" required>${Object.entries(ROLE_LABELS).map(([role, label]) => `<option value="${role}">${escapeHtml(label)}</option>`).join("")}</select><small class="muted">Your account's role is verified by AgriLearn.</small></div>
          <div class="mb-3"><label class="form-label" for="login-password">Password</label><div class="password-wrap"><input class="form-control" id="login-password" name="password" type="password" autocomplete="current-password" required minlength="12" placeholder="Enter your password"><button class="password-toggle" type="button" aria-label="Show password" data-password-toggle><i class="bi bi-eye"></i></button></div></div>
          <div class="login-error" id="login-error" role="alert"></div>
          <button class="btn-brand w-100 mt-2" type="submit" id="login-submit"><span data-login-label>Sign in</span></button>
        </form>
        <div class="demo-credentials"><strong><i class="bi bi-shield-lock me-1"></i>Account security</strong><br>Accounts are created by an authorized administrator. Passwords are securely verified by the AgriLearn server.</div>
        <a class="back-link" href="#/"><i class="bi bi-arrow-left"></i> Back to AgriLearn</a>
        <p class="muted small mt-4"><i class="bi bi-shield-check me-1"></i>Access is checked by the AgriLearn server for every protected request.</p>
      </div></section>
    </main>`;
  const form = document.getElementById("login-form");
  const username = document.getElementById("login-username");
  const role = document.getElementById("login-role");
  const password = document.getElementById("login-password");
  const error = document.getElementById("login-error");
  const submit = document.getElementById("login-submit");
  document.querySelector("[data-password-toggle]").addEventListener("click", (event) => {
    const visible = password.type === "password";
    password.type = visible ? "text" : "password";
    event.currentTarget.setAttribute("aria-label", visible ? "Hide password" : "Show password");
    event.currentTarget.innerHTML = `<i class="bi ${visible ? "bi-eye-slash" : "bi-eye"}"></i>`;
    password.focus();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.classList.remove("is-visible");
    if (!form.reportValidity()) return;
    submit.disabled = true;
    submit.innerHTML = `<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Signing in…`;
    try {
      const user = authenticate(username.value, password.value, role.value);
      const signedInUser = await user;
      location.hash = `#/${signedInUser.role}-dashboard`;
    } catch (reason) {
      error.textContent = reason.message;
      error.classList.add("is-visible");
      password.focus();
    } finally {
      submit.disabled = false;
      submit.innerHTML = `<span data-login-label>Sign in</span>`;
    }
  });
}

async function renderShell(user, route) {
  const version = renderVersion;
  const nav = navByRole[user.role].filter(([key]) => canAccess(key, user));
  const active = aliases[route] ? "dashboard" : route;
  const isOverview = active === "dashboard" && (!aliases[route] || aliases[route] === user.role);
  const roleName = ROLE_LABELS[user.role];
  app.innerHTML = `<div class="app-layout${isOverview ? " overview-shell" : ""}">
    <aside class="sidebar" id="app-sidebar">
      <div class="sidebar-brand">${brandMarkup(false)}</div>
      <div class="institution-tag"><strong>VVITU · 2026–27</strong>II Year B.Tech – I Semester<br>Software Engineering</div>
      <div class="nav-section-label">Workspace</div>
      <nav class="side-nav" aria-label="Workspace navigation">${nav.map(([key, label, icon]) => `<a href="#/${key}" class="${active === key ? "active" : ""}" ${active === key ? 'aria-current="page"' : ""}><i class="bi ${icon}"></i><span>${label}</span></a>`).join("")}</nav>
      <div class="side-footer"><div class="role-mini"><span class="avatar">${initials(user.name)}</span><div><strong>${escapeHtml(user.name)}</strong><span>${escapeHtml(roleName)}</span></div></div><button class="logout-link" type="button" data-logout><i class="bi bi-box-arrow-left"></i> Sign out</button></div>
    </aside>
    <main class="app-main">
      <header class="topbar"><div class="topbar-left"><button class="mobile-menu-btn" data-menu-toggle aria-label="Open navigation menu" aria-controls="app-sidebar" aria-expanded="false"><i class="bi bi-list"></i></button><span class="breadcrumb-line">AgriLearn <span class="mx-1">/</span><strong>${routeTitles[active] || "Overview"}</strong></span></div><div class="topbar-right"><span class="topbar-date">${new Date().toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</span>${isOverview ? '<span class="demo-chip" data-api-status="checking" role="status" aria-live="polite" aria-label="Checking AgriLearn API"><i class="bi bi-arrow-repeat" aria-hidden="true"></i><span>Checking</span></span>' : '<span class="demo-chip"><i class="bi bi-cloud-check"></i> Connected workspace</span>'}<button class="btn-outline-brand btn-sm" type="button" data-change-password aria-label="Change password">${isOverview ? '<i class="bi bi-key" aria-hidden="true"></i><span class="overview-password-label">Change password</span>' : "Change password"}</button><span class="avatar">${initials(user.name)}</span></div></header>
      <div class="page-content"><div class="print-header mb-3"><strong>VVITU · AgriLearn</strong><br><span>Farmer Training Management System · Academic Year 2026–27</span></div><div id="route-content"></div></div>
    </main>
  </div>`;
  const page = document.getElementById("route-content");
  if (aliases[route] && aliases[route] !== user.role) {
    page.innerHTML = `<div class="access-denied"><i class="bi bi-shield-lock"></i><h1 class="h4 mt-3">Access restricted</h1><p class="muted">This dashboard belongs to a different role.</p><a class="btn-brand" href="#/dashboard">Return to your dashboard</a></div>`;
  } else {
    page.innerHTML = `<div class="empty-state"><span class="spinner-border text-success" aria-hidden="true"></span><strong>Loading ${escapeHtml(routeTitles[active] || "workspace")}</strong><span>Retrieving current records from AgriLearn…</span></div>`;
    try {
      let rendered;
      switch (active) {
        case "dashboard": rendered = await renderDashboard(user); break;
        case "farmers":
        case "trainers":
        case "programs":
        case "users": rendered = await renderDirectoryPage(active, user); break;
        case "schedules": rendered = await renderSchedules(user); break;
        case "attendance": rendered = await renderAttendance(user); break;
        case "progress": rendered = await renderProgress(user); break;
        case "reports": rendered = await renderReports(user); break;
        default: rendered = await renderDashboard(user);
      }
      if (version === renderVersion && page.isConnected) page.replaceChildren(rendered);
    } catch (error) {
      console.error("Could not render AgriLearn page:", error);
      if (version === renderVersion && page.isConnected) page.innerHTML = `<div class="access-denied"><i class="bi bi-cloud-slash"></i><h1 class="h4 mt-3">Could not load this page</h1><p class="muted">${escapeHtml(error.message)}</p><button class="btn-outline-brand" type="button" onclick="location.reload()">Retry</button></div>`;
    }
  }
  if (version !== renderVersion) return;
  document.querySelector("[data-logout]").addEventListener("click", logout);
  document.querySelector("[data-change-password]").addEventListener("click", () => {
    showDialog({
      title: "Change password",
      body: `<div class="mb-3"><label class="form-label" for="current-password">Current password *</label><input class="form-control" id="current-password" name="current_password" type="password" autocomplete="current-password" minlength="12" required></div><div class="mb-3"><label class="form-label" for="new-password">New password *</label><input class="form-control" id="new-password" name="new_password" type="password" autocomplete="new-password" minlength="12" required><small class="muted">Use at least 12 characters. You will need to sign in again after changing it.</small></div><div><label class="form-label" for="confirm-password">Confirm new password *</label><input class="form-control" id="confirm-password" name="confirm_password" type="password" autocomplete="new-password" minlength="12" required></div>`,
      submitLabel: "Update password",
      onSubmit: async (formData) => {
        const newPassword = formData.get("new_password");
        if (newPassword !== formData.get("confirm_password")) {
          toast("The new password entries do not match.", "error");
          return;
        }
        try {
          await apiRequest("/auth/change-password", {
            method: "POST",
            body: { current_password: formData.get("current_password"), new_password: newPassword }
          });
          document.getElementById("record-dialog").close();
          toast("Password changed. Sign in again with your new password.");
          await logout();
        } catch (error) { toast(error.message, "error"); }
      }
    });
  });
  const menuButton = document.querySelector("[data-menu-toggle]");
  menuButton.addEventListener("click", () => {
    const sidebar = document.getElementById("app-sidebar");
    sidebar.classList.toggle("is-open");
    const isOpen = sidebar.classList.contains("is-open");
    menuButton.setAttribute("aria-expanded", isOpen);
    menuButton.setAttribute("aria-label", isOpen ? "Close navigation menu" : "Open navigation menu");
  });
  document.querySelectorAll(".side-nav a").forEach((link) => link.addEventListener("click", () => {
    document.getElementById("app-sidebar").classList.remove("is-open");
    menuButton.setAttribute("aria-expanded", "false");
    menuButton.setAttribute("aria-label", "Open navigation menu");
  }));
}

async function render() {
  renderVersion += 1;
  let route = getRoute();
  if (!["landing", "login", ...Object.keys(routeTitles), ...Object.keys(aliases)].includes(route)) route = "landing";
  if (route !== "landing" && route !== "login" && !currentUser()) {
    location.hash = "#/login";
    route = "login";
  }
  if (route === "landing") { renderLanding(); return; }
  if (route === "login") { renderLogin(); return; }
  const user = currentUser();
  const moduleRoute = aliases[route] ? "dashboard" : route;
  if (routeTitles[moduleRoute] && !canAccess(moduleRoute, user)) {
    toast("Access denied for this role. You have been returned to your dashboard.", "error");
    location.hash = "#/dashboard";
    route = "dashboard";
  }
  await renderShell(user, route);
}

async function start() {
  window.addEventListener("hashchange", () => {
    if (!location.hash || location.hash.startsWith("#/")) void render();
  });
  app.innerHTML = `<main class="container py-5"><div class="empty-state"><span class="spinner-border text-success" aria-hidden="true"></span><strong>Connecting to AgriLearn</strong><span>Checking your secure session…</span></div></main>`;
  try {
    await restoreSession();
  } catch (error) {
    console.error("Could not restore AgriLearn session:", error);
    toast(error.message, "error");
  }
  await render();
}

void start();
