import { create } from "zustand";
import { projectsApi } from "@/api/projects";
import type {
  CreateProjectRequest,
  Project,
  ProjectSummary,
  UpdateProjectRequest,
} from "@/api/types";

interface ProjectState {
  projects: ProjectSummary[];
  activeProject: Project | null;
  loading: boolean;
  fetchProjects: () => Promise<void>;
  fetchProject: (id: string) => Promise<void>;
  createProject: (req: CreateProjectRequest) => Promise<Project>;
  updateProject: (id: string, req: UpdateProjectRequest) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
  setActiveProject: (project: Project | null) => void;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  activeProject: null,
  loading: false,

  fetchProjects: async () => {
    set({ loading: true });
    try {
      const projects = await projectsApi.list();
      set({ projects, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  fetchProject: async (id) => {
    const project = await projectsApi.get(id);
    set({ activeProject: project });
  },

  createProject: async (req) => {
    const project = await projectsApi.create(req);
    get().fetchProjects();
    return project;
  },

  updateProject: async (id, req) => {
    await projectsApi.update(id, req);
    get().fetchProjects();
    const active = get().activeProject;
    if (active?.id === id) {
      get().fetchProject(id);
    }
  },

  deleteProject: async (id) => {
    await projectsApi.delete(id);
    const active = get().activeProject;
    if (active?.id === id) {
      set({ activeProject: null });
    }
    get().fetchProjects();
  },

  setActiveProject: (project) => set({ activeProject: project }),
}));
