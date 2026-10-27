import { apiFetch } from "./client";
import type {
  AgentExecution,
  ChatRequest,
  ChatResponse,
  DispatchResponse,
  Task,
  TaskStep,
  TaskStatus,
  TaskSummary,
} from "./types";

export interface TaskListParams {
  status?: TaskStatus;
  /** Free-text search over title and request. */
  q?: string;
  projectId?: string;
  limit?: number;
}

export const tasksApi = {
  chat(req: ChatRequest): Promise<ChatResponse> {
    return apiFetch("/chat", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  list(params: TaskListParams = {}): Promise<TaskSummary[]> {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    if (params.q?.trim()) qs.set("q", params.q.trim());
    if (params.projectId) qs.set("project_id", params.projectId);
    qs.set("limit", String(params.limit ?? 200));
    return apiFetch(`/tasks?${qs.toString()}`);
  },

  get(id: string): Promise<Task> {
    return apiFetch(`/tasks/${id}`);
  },

  cancel(id: string): Promise<Task> {
    return apiFetch(`/tasks/${id}/cancel`, { method: "POST" });
  },

  retry(id: string): Promise<Task> {
    return apiFetch(`/tasks/${id}/retry`, { method: "POST" });
  },

  dispatch(id: string): Promise<DispatchResponse> {
    return apiFetch(`/tasks/${id}/dispatch`, { method: "POST" });
  },

  steps(taskId: string): Promise<TaskStep[]> {
    return apiFetch(`/tasks/${taskId}/steps`);
  },

  executions(taskId: string): Promise<AgentExecution[]> {
    return apiFetch(`/tasks/${taskId}/executions`);
  },
};
