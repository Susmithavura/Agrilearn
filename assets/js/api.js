import { resolveApiBaseUrl } from "./api-config.mjs";

const configuredApiBase = document.querySelector('meta[name="agrilearn-api-base"]')?.content;
export const API_CONFIG = Object.freeze({
  baseUrl: resolveApiBaseUrl(configuredApiBase, window.location.origin),
  endpoints: Object.freeze({
    auth: "/auth",
    users: "/users",
    farmers: "/farmers",
    trainers: "/trainers",
    programs: "/programs",
    sessions: "/sessions",
    enrollments: "/enrollments",
    attendance: "/attendance",
    progress: "/progress",
    reports: "/reports",
    dashboard: "/dashboard"
  })
});

export class APIError extends Error {
  constructor(message, status, code) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.code = code;
  }
}

let csrfToken = "";
let refreshInFlight = null;
let sessionExpiredHandler = null;

export function setSessionExpiredHandler(handler) {
  sessionExpiredHandler = handler;
}

export async function refreshCsrfToken() {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_CONFIG.baseUrl}/auth/csrf`, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" }
    }).then(async (response) => {
      const body = await response.json();
      if (!response.ok) throw new APIError(body?.error?.message || "Could not initialize a secure session.", response.status, body?.error?.code);
      csrfToken = body.data.csrf_token;
      return csrfToken;
    }).catch((error) => {
      if (error instanceof APIError) throw error;
      throw new APIError(`Cannot reach the AgriLearn API at ${API_CONFIG.baseUrl}. Start Flask and check the API URL.`, 0, "network_error");
    }).finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

export function setCsrfToken(token) {
  csrfToken = token || "";
}

export async function apiRequest(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  let body = options.body;
  if (body !== undefined && typeof body !== "string" && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    if (path === "/auth/login" || !csrfToken) await refreshCsrfToken();
    headers["X-CSRF-Token"] = csrfToken;
  }
  let response;
  try {
    response = await fetch(`${API_CONFIG.baseUrl}${path}`, {
      ...options,
      method,
      headers,
      body,
      credentials: "include"
    });
  } catch (error) {
    throw new APIError(`Cannot reach the AgriLearn API at ${API_CONFIG.baseUrl}. Start Flask and check the API URL.`, 0, "network_error");
  }
  let payload = null;
  if (response.status !== 204) {
    try { payload = await response.json(); }
    catch { throw new APIError("The server returned an invalid response.", response.status, "invalid_response"); }
  }
  if (!response.ok) {
    if (response.status === 401 && sessionExpiredHandler) sessionExpiredHandler();
    throw new APIError(payload?.error?.message || `Request failed (${response.status}).`, response.status, payload?.error?.code || "request_failed");
  }
  if (payload?.data === undefined) throw new APIError("The server response did not contain data.", response.status, "invalid_response");
  if (payload.data?.csrf_token) setCsrfToken(payload.data.csrf_token);
  return payload.data;
}

export function apiUrl(resource, query = {}) {
  const parameters = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") parameters.set(key, String(value));
  });
  const queryString = parameters.toString();
  return `${resource}${queryString ? `?${queryString}` : ""}`;
}
