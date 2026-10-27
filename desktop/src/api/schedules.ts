import type {
  CreateScheduledTaskRequest,
  ScheduledTask,
  ScheduledTaskStatus,
  ScheduledTaskSummary,
  UpdateScheduledTaskRequest,
} from "./types";

const API_BASE = "http://localhost:8000";

export async function createSchedule(
  request: CreateScheduledTaskRequest
): Promise<ScheduledTask> {
  const resp = await fetch(`${API_BASE}/schedules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!resp.ok) throw new Error(`Create schedule failed: ${resp.status}`);
  return resp.json();
}

export async function listSchedules(
  status?: ScheduledTaskStatus,
  limit?: number
): Promise<ScheduledTaskSummary[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (limit) params.set("limit", limit.toString());
  const query = params.toString();
  const resp = await fetch(
    `${API_BASE}/schedules${query ? `?${query}` : ""}`
  );
  if (!resp.ok) throw new Error(`List schedules failed: ${resp.status}`);
  return resp.json();
}

export async function getSchedule(id: string): Promise<ScheduledTask> {
  const resp = await fetch(`${API_BASE}/schedules/${id}`);
  if (!resp.ok) throw new Error(`Get schedule failed: ${resp.status}`);
  return resp.json();
}

export async function updateSchedule(
  id: string,
  request: UpdateScheduledTaskRequest
): Promise<ScheduledTask> {
  const resp = await fetch(`${API_BASE}/schedules/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!resp.ok) throw new Error(`Update schedule failed: ${resp.status}`);
  return resp.json();
}

export async function pauseSchedule(id: string): Promise<ScheduledTask> {
  const resp = await fetch(`${API_BASE}/schedules/${id}/pause`, {
    method: "POST",
  });
  if (!resp.ok) throw new Error(`Pause schedule failed: ${resp.status}`);
  return resp.json();
}

export async function resumeSchedule(id: string): Promise<ScheduledTask> {
  const resp = await fetch(`${API_BASE}/schedules/${id}/resume`, {
    method: "POST",
  });
  if (!resp.ok) throw new Error(`Resume schedule failed: ${resp.status}`);
  return resp.json();
}

export async function cancelSchedule(id: string): Promise<ScheduledTask> {
  const resp = await fetch(`${API_BASE}/schedules/${id}/cancel`, {
    method: "POST",
  });
  if (!resp.ok) throw new Error(`Cancel schedule failed: ${resp.status}`);
  return resp.json();
}
