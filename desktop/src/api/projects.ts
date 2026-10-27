import { apiFetch } from "./client";
import type {
  CreateProjectRequest,
  Project,
  ProjectSummary,
  UpdateProjectRequest,
} from "./types";

export const projectsApi = {
  list(): Promise<ProjectSummary[]> {
    return apiFetch("/projects");
  },

  get(id: string): Promise<Project> {
    return apiFetch(`/projects/${id}`);
  },

  create(req: CreateProjectRequest): Promise<Project> {
    return apiFetch("/projects", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  update(id: string, req: UpdateProjectRequest): Promise<Project> {
    return apiFetch(`/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(req),
    });
  },

  delete(id: string): Promise<void> {
    return apiFetch(`/projects/${id}`, { method: "DELETE" });
  },
};
