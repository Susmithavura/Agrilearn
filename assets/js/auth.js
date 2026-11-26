import { apiRequest, setSessionExpiredHandler } from "./api.js";
import { toast } from "./ui.js";

export const ROLE_LABELS = Object.freeze({
  farmer: "Farmer",
  trainer: "Trainer / Agricultural Officer",
  coordinator: "Training Coordinator",
  management: "Agricultural Department / Management",
  admin: "System Administrator"
});

const routeRoles = {
  dashboard: Object.keys(ROLE_LABELS),
  farmers: ["admin", "coordinator", "trainer", "management", "farmer"],
  trainers: ["admin", "coordinator", "trainer", "management"],
  programs: ["admin", "coordinator", "trainer", "management", "farmer"],
  schedules: Object.keys(ROLE_LABELS),
  attendance: ["admin", "coordinator", "trainer", "farmer", "management"],
  progress: Object.keys(ROLE_LABELS),
  reports: ["admin", "coordinator", "management"],
  users: ["admin"]
};

let authenticatedUser = null;

export function currentUser() {
  return authenticatedUser;
}

export function canAccess(route, user = authenticatedUser) {
  return Boolean(user && routeRoles[route]?.includes(user.role));
}

export async function authenticate(username, password, expectedRole) {
  const result = await apiRequest("/auth/login", {
    method: "POST",
    body: { username: username.trim(), password }
  });
  if (expectedRole && result.user.role !== expectedRole) {
    await apiRequest("/auth/logout", { method: "POST" });
    throw new Error("The selected portal does not match the role assigned to this account.");
  }
  authenticatedUser = result.user;
  return authenticatedUser;
}

export async function restoreSession() {
  try {
    const result = await apiRequest("/auth/me");
    authenticatedUser = result.user;
    return authenticatedUser;
  } catch (error) {
    authenticatedUser = null;
    if (error.status !== 401) throw error;
    return null;
  }
}

export async function logout() {
  try {
    if (authenticatedUser) await apiRequest("/auth/logout", { method: "POST" });
  } catch (error) {
    if (error.status !== 401) toast(`Could not sign out cleanly: ${error.message}`, "error");
  } finally {
    authenticatedUser = null;
    location.hash = "#/login";
  }
}

setSessionExpiredHandler(() => {
  if (!authenticatedUser) return;
  authenticatedUser = null;
  toast("Your session has expired. Please sign in again.", "error");
  location.hash = "#/login";
});
