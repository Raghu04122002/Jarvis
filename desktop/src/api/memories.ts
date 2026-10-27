import { apiFetch } from "./client";
import type {
  CreateMemoryRequest,
  Memory,
  MemorySummary,
  UpdateMemoryRequest,
} from "./types";

export const memoriesApi = {
  list(projectId?: string): Promise<MemorySummary[]> {
    const params = projectId ? `?project_id=${projectId}` : "";
    return apiFetch(`/memory${params}`);
  },

  search(query: string, projectId?: string): Promise<MemorySummary[]> {
    const params = new URLSearchParams({ q: query });
    if (projectId) params.set("project_id", projectId);
    return apiFetch(`/memory/search?${params}`);
  },

  get(id: string): Promise<Memory> {
    return apiFetch(`/memory/${id}`);
  },

  create(req: CreateMemoryRequest): Promise<Memory> {
    return apiFetch("/memory", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  update(id: string, req: UpdateMemoryRequest): Promise<Memory> {
    return apiFetch(`/memory/${id}`, {
      method: "PATCH",
      body: JSON.stringify(req),
    });
  },

  delete(id: string): Promise<void> {
    return apiFetch(`/memory/${id}`, { method: "DELETE" });
  },
};
