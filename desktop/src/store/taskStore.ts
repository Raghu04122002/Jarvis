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
  currentTask: Task | null;
  steps: TaskStep[];
  executions: AgentExecution[];
  loading: boolean;
  fetchTasks: () => Promise<void>;
  fetchTask: (id: string) => Promise<void>;
  fetchSteps: (taskId: string) => Promise<void>;
  fetchExecutions: (taskId: string) => Promise<void>;
  dispatchTask: (id: string) => Promise<void>;
  cancelTask: (id: string) => Promise<void>;
  retryTask: (id: string) => Promise<void>;
  handleEvent: (event: SSEEvent) => void;
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  currentTask: null,
  steps: [],
  executions: [],
  loading: false,

  fetchTasks: async () => {
    set({ loading: true });
    try {
      const tasks = await tasksApi.list();
      set({ tasks, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  fetchTask: async (id) => {
    set({ loading: true });
    try {
      const task = await tasksApi.get(id);
      set({ currentTask: task, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  fetchSteps: async (taskId) => {
    try {
      const steps = await tasksApi.steps(taskId);
      set({ steps });
    } catch {
      // ignore
    }
  },

  fetchExecutions: async (taskId) => {
    try {
      const executions = await tasksApi.executions(taskId);
      set({ executions });
    } catch {
      // ignore
    }
  },

  dispatchTask: async (id) => {
    await tasksApi.dispatch(id);
  },

  cancelTask: async (id) => {
    await tasksApi.cancel(id);
    const current = get().currentTask;
    if (current?.id === id) {
      get().fetchTask(id);
    }
    get().fetchTasks();
  },

  retryTask: async (id) => {
    await tasksApi.retry(id);
    get().fetchTasks();
  },

  handleEvent: (event) => {
    const type = event.type;
    if (
      type.startsWith("task_") &&
      !type.startsWith("task_step_")
    ) {
      // Refresh task list on any task event
      get().fetchTasks();
      const current = get().currentTask;
      if (current && current.id === event.task_id) {
        get().fetchTask(current.id);
      }
    }
    if (type.startsWith("task_step_")) {
      const current = get().currentTask;
      if (current && current.id === event.task_id) {
        get().fetchSteps(current.id);
      }
    }
    if (type.startsWith("agent_execution_")) {
      const current = get().currentTask;
      if (current && current.id === event.task_id) {
        get().fetchExecutions(current.id);
      }
    }
  },
}));
