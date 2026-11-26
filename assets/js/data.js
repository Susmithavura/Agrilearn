import { apiRequest, apiUrl } from "./api.js";

const paths = Object.freeze({
  farmers: "/farmers",
  trainers: "/trainers",
  programs: "/programs",
  users: "/users",
  sessions: "/sessions",
  enrollments: "/enrollments",
  attendance: "/attendance",
  progress: "/progress"
});

export function createId(prefix) {
  return `${prefix}-${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`;
}

export const titleCase = (value = "") => String(value).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const timeValue = (value) => String(value || "").slice(0, 5);
const dateValue = (value) => {
  const raw = String(value || "");
  if (/^\d{4}-\d{2}-\d{2}/.test(raw)) return raw.slice(0, 10);
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toISOString().slice(0, 10);
};

function normalize(resource, row) {
  if (resource === "farmers") return { ...row, farmerCode: row.farmer_id, name: row.name, village: row.village, joined: dateValue(row.created_at), status: row.status };
  if (resource === "trainers") return { ...row, trainerCode: row.trainer_id, name: row.name };
  if (resource === "programs") return { ...row, title: row.title, status: row.status, description: row.description };
  if (resource === "users") return { ...row, name: row.full_name, status: row.account_status === "active" ? "Active" : "Inactive" };
  if (resource === "sessions") return { ...row, time: timeValue(row.time), date: dateValue(row.date), farmerIds: row.farmer_ids || [] };
  if (resource === "enrollments") return { ...row, enrollment_date: dateValue(row.enrollment_date), participation_status: row.participation_status };
  if (resource === "attendance") return { ...row, status: row.attendance_status, submittedAt: row.recorded_at?.slice(0, 10) };
  if (resource === "progress") return { ...row, percent: Number(row.progress_percent), result: row.completion_status, resultText: row.result || "", notes: row.progress_details || "" };
  return row;
}

export async function listRecords(resource, query = {}) {
  const rows = await apiRequest(apiUrl(paths[resource], { per_page: 100, ...query }));
  if (!Array.isArray(rows)) throw new Error(`The server returned an invalid ${resource} list.`);
  if (resource === "sessions") {
    const enrollments = await apiRequest(apiUrl(paths.enrollments, { per_page: 100 }));
    const farmersByProgram = new Map();
    enrollments.forEach((enrollment) => {
      const farmerIds = farmersByProgram.get(enrollment.program_id) || [];
      farmerIds.push(String(enrollment.farmer_id));
      farmersByProgram.set(enrollment.program_id, farmerIds);
    });
    return rows.map((row) => normalize(resource, { ...row, farmer_ids: farmersByProgram.get(row.program_id) || [] }));
  }
  return rows.map((row) => normalize(resource, row));
}

export async function saveRecord(resource, record, isNew = false) {
  const id = record.id;
  let endpoint = paths[resource];
  let method = "POST";
  let body = record;
  if (!isNew) {
    endpoint = `${endpoint}/${encodeURIComponent(id)}`;
    method = "PUT";
  }
  if (resource === "farmers") body = {
    farmer_id: record.farmer_id || record.farmerCode || record.farmerId,
    full_name: record.name,
    village: record.village,
    phone: record.phone,
    email: record.email || null
  };
  if (resource === "trainers") body = {
    trainer_id: record.trainer_id || record.trainerCode || record.trainerId,
    full_name: record.name,
    specialization: record.specialization,
    phone: record.phone,
    email: record.email || null
  };
  if (resource === "programs") body = {
    program_name: record.title,
    category: record.category,
    level: record.level,
    description: record.description,
    objectives: record.objectives || "",
    duration: record.duration,
    status: String(record.status).toLowerCase()
  };
  if (resource === "users") body = isNew ? {
    full_name: record.name,
    username: record.username,
    password: record.password,
    role: record.role,
    account_status: String(record.status).toLowerCase(),
    email: record.email || null,
    phone: record.phone || null,
    ...(record.role === "farmer" ? {
      farmer_id: record.farmer_id,
      village: record.village,
      farmer_phone: record.phone
    } : {}),
    ...(record.role === "trainer" ? {
      trainer_id: record.trainer_id,
      specialization: record.specialization,
      trainer_phone: record.phone
    } : {})
  } : {
    full_name: record.name,
    email: record.email || null,
    phone: record.phone || null,
    role: record.role,
    language_preference: record.language_preference || "en"
  };
  const saved = await apiRequest(endpoint, { method, body });
  return normalize(resource, saved);
}

export async function deactivateRecord(resource, id) {
  return apiRequest(`${paths[resource]}/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function setUserStatus(id, status) {
  return apiRequest(`/users/${encodeURIComponent(id)}/status`, {
    method: "PATCH",
    body: { account_status: String(status).toLowerCase() }
  });
}

export async function saveSession(record, isNew = false) {
  const body = {
    program_id: Number(record.programId),
    trainer_id: Number(record.trainerId),
    session_date: record.date,
    start_time: record.time,
    end_time: record.endTime || null,
    location: record.location,
    session_details: record.details || "",
    status: record.status || "scheduled",
    farmer_ids: (record.farmerIds || []).map(Number)
  };
  return apiRequest(isNew ? "/sessions" : `/sessions/${encodeURIComponent(record.id)}`, {
    method: isNew ? "POST" : "PUT",
    body
  });
}

export async function saveAttendance(sessionId, records) {
  return apiRequest("/attendance", {
    method: "POST",
    body: {
      session_id: Number(sessionId),
      records: records.map(({ farmerId, status }) => ({
        farmer_id: Number(farmerId),
        attendance_status: String(status).toLowerCase()
      }))
    }
  });
}

export async function saveProgress(record, isNew = false) {
  const body = {
    farmer_id: Number(record.farmerId),
    program_id: Number(record.programId),
    progress_percent: Number(record.percent),
    completion_status: String(record.result).toLowerCase().replaceAll(" ", "_"),
    progress_details: record.notes || "",
    result: record.resultText || ""
  };
  return apiRequest(isNew ? "/progress" : `/progress/${encodeURIComponent(record.id)}`, {
    method: isNew ? "POST" : "PUT",
    body
  });
}

export function apiResourcePath(resource) {
  return paths[resource];
}
