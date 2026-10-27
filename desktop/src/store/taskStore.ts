import { create } from "zustand";
import { tasksApi } from "@/api/tasks";
import type {
  AgentExecution,
  SSEEvent,
  Task,
  TaskStep,
  TaskSummary,
} from "@/api/types";

interface TaskState {
  tasks: TaskSummary[];
  /** Search text applied to the task list (server-side). */
  query: string;
  currentTask: Task | null;
  steps: TaskStep[];
  executions: AgentExecution[];
  loading: boolean;
  /** True until the first list fetch finishes, for skeletons. */
  loaded: boolean;
  error: string | null;
  setQuery: (q: string) => void;
  fetchTasks: () => Promise<void>;
  fetchTask: (id: string) => Promise<void>;
  fetchSteps: (taskId: string) => Promise<void>;
  fetchExecutions: (taskId: string) => Promise<void>;
  dispatchTask: (id: string) => Promise<void>;
  cancelTask: (id: string) => Promise<void>;
  retryTask: (id: string) => Promise<void>;
  handleEvent: (event: SSEEvent) => void;
}

let listRequest = 0;

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  query: "",
  currentTask: null,
  steps: [],
  executions: [],
  loading: false,
  loaded: false,
  error: null,

  setQuery: (query) => {
    set({ query });
    void get().fetchTasks();
  },

  fetchTasks: async () => {
    // Ignore responses that arrive after a newer request (fast typing).
    const req = ++listRequest;
    set({ loading: true });
    try {
      const tasks = await tasksApi.list({ q: get().query });
      if (req === listRequest) set({ tasks, loading: false, loaded: true, error: null });
    } catch (e) {
      if (req === listRequest)
        set({
          loading: false,
          loaded: true,
          error: e instanceof Error ? e.message : "Couldn't load tasks",
        });
    }
  },

  fetchTask: async (id) => {
    set({ loading: true });
    try {
      const task = await tasksApi.get(id);
      set({ currentTask: task, loading: false, error: null });
    } catch (e) {
      set({
        currentTask: null,
        loading: false,
        error: e instanceof Error ? e.message : "Couldn't load task",
      });
    }
  },

  fetchSteps: async (taskId) => {
    try {
      set({ steps: await tasksApi.steps(taskId) });
    } catch {
      // keep previous steps
    }
  },

  fetchExecutions: async (taskId) => {
    try {
      set({ executions: await tasksApi.executions(taskId) });
    } catch {
      // keep previous executions
    }
  },

  dispatchTask: async (id) => {
    await tasksApi.dispatch(id);
    await get().fetchTask(id);
  },

  cancelTask: async (id) => {
    await tasksApi.cancel(id);
    await Promise.all([get().fetchTask(id), get().fetchTasks()]);
  },

  retryTask: async (id) => {
    await tasksApi.retry(id);
    // Retry moves the task back to planning; dispatch it again.
    await tasksApi.dispatch(id).catch(() => undefined);
    await Promise.all([get().fetchTask(id), get().fetchTasks()]);
  },

  handleEvent: (event) => {
    const { type } = event;
    if (type.startsWith("task_") && !type.startsWith("task_step_")) {
      void get().fetchTasks();
    }
    const current = get().currentTask;
    if (!current || current.id !== event.task_id) return;
    if (type.startsWith("task_")) {
      void get().fetchTask(current.id);
      void get().fetchSteps(current.id);
    }
    if (type.startsWith("agent_")) {
      void get().fetchExecutions(current.id);
    }
  },
}));
