import { apiFetch } from "./client";
import type {
  AgentExecution,
  ChatRequest,
  ChatResponse,
  DispatchResponse,
  Task,
  TaskStep,
  TaskSummary,
} from "./types";

export const tasksApi = {
  chat(req: ChatRequest): Promise<ChatResponse> {
    return apiFetch("/chat", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  list(): Promise<TaskSummary[]> {
    return apiFetch("/tasks");
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
